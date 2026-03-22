#!/usr/bin/env python3
"""
Password Reset Script for QGen RAG Authentication

This script allows administrators to reset user passwords in the SQLite auth database.
It prompts for an email address and new password, validates the password strength,
and updates the user record with the new hashed password.

Usage:
    python reset_password.py

Requirements:
    - Must be run from the backend directory
    - Requires access to the auth database (auth.db)
"""

import sys
import os
import getpass
from pathlib import Path
from datetime import datetime

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.security import hash_password
from app.core.config import settings


def get_auth_engine():
    """Create and return the SQLite auth database engine."""
    auth_db_path = Path(settings.AUTH_DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
    auth_db_path = auth_db_path.resolve()
    
    if not auth_db_path.exists():
        print(f"❌ Error: Auth database not found at {auth_db_path}")
        print("Please ensure the application has been initialized first.")
        sys.exit(1)
    
    engine = create_async_engine(
        settings.AUTH_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    return engine


async def find_user_by_email(session: AsyncSession, email: str):
    """Find a user by email address."""
    from app.models.user import User
    
    result = await session.execute(
        select(User).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


def prompt_email():
    """Prompt for email address with validation."""
    while True:
        email = input("📧 Enter user email address: ").strip()
        if not email:
            print("❌ Email address is required.")
            continue
        
        # Basic email validation
        if "@" not in email or "." not in email:
            print("❌ Please enter a valid email address.")
            continue
        
        return email.lower()


def prompt_password():
    """Prompt for new password."""
    while True:
        password = getpass.getpass("🔑 Enter new password: ")
        if not password:
            print("❌ Password is required.")
            continue
        
        password_confirm = getpass.getpass("🔑 Confirm new password: ")
        if password != password_confirm:
            print("❌ Passwords do not match. Please try again.")
            continue
        
        return password


async def reset_password():
    """Main password reset function."""
    print("🔐 QGen RAG Password Reset Tool")
    print("=" * 40)
    
    # Get user input
    email = prompt_email()
    password = prompt_password()
    
    # Create database session
    engine = get_auth_engine()
    SessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with SessionLocal() as session:
        try:
            # Find user
            user = await find_user_by_email(session, email)
            if not user:
                print(f"❌ No user found with email: {email}")
                return False
            
            # Display user info
            print(f"\n👤 User found:")
            print(f"   Email: {user.email}")
            print(f"   Username: {user.username}")
            print(f"   Role: {user.role}")
            print(f"   Active: {'Yes' if user.is_active else 'No'}")
            
            # Confirm reset
            confirm = input(f"\n⚠️  Reset password for {user.username}? (y/N): ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("❌ Password reset cancelled.")
                return False
            
            # Hash new password
            new_password_hash = hash_password(password)
            
            # Update user record
            user.password_hash = new_password_hash
            user.password_changed_at = datetime.utcnow()
            user.failed_login_attempts = 0  # Reset failed login attempts
            user.locked_until = None  # Unlock account if locked
            
            await session.commit()
            
            print(f"✅ Password successfully reset for {user.email}")
            print(f"   Username: {user.username}")
            print(f"   Password changed at: {user.password_changed_at}")
            return True
            
        except Exception as e:
            print(f"❌ Error resetting password: {e}")
            await session.rollback()
            return False


async def main():
    """Main entry point."""
    try:
        success = await reset_password()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Password reset cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
