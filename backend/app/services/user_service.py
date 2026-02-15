"""
User service for authentication and user management.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import uuid
import hashlib

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.auth import RefreshToken, AuditLog
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings


class UserService:
    """Service for user-related operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        # Check if email exists
        existing_email = await self.db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing_email.scalar_one_or_none():
            raise ValueError("Email already registered")

        # Check if username exists
        existing_username = await self.db.execute(
            select(User).where(User.username == user_data.username.lower())
        )
        if existing_username.scalar_one_or_none():
            raise ValueError("Username already taken")

        # Create user
        user = User(
            email=user_data.email,
            username=user_data.username.lower(),
            password_hash=hash_password(user_data.password),
            full_name=user_data.full_name,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate_user(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[User]:
        """Authenticate user with email and password."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            # Log failed attempt
            await self._log_auth_event(
                user_id=None,
                event_type="login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="User not found",
            )
            return None

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            await self._log_auth_event(
                user_id=user.id,
                event_type="login_blocked",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="Account locked",
            )
            raise ValueError("Account is locked. Please try again later.")

        # Verify password
        if not verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            
            await self.db.commit()
            
            await self._log_auth_event(
                user_id=user.id,
                event_type="login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="Invalid password",
            )
            return None

        # Check if user is active
        if not user.is_active:
            await self._log_auth_event(
                user_id=user.id,
                event_type="login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="Account deactivated",
            )
            raise ValueError("Account is deactivated")

        # Reset failed attempts and update last login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()

        # Log successful login
        await self._log_auth_event(
            user_id=user.id,
            event_type="login_success",
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )

        return user

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update_user(self, user_id: uuid.UUID, update_data: UserUpdate) -> User:
        """Update user profile."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(user, key, value)

        user.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user password."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if not verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")

        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        await self.db.commit()
        return True

    async def create_refresh_token(
        self,
        user_id: uuid.UUID,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
        device_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[str, str]:
        """Create access and refresh tokens for user."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Generate tokens
        access_token = create_access_token(
            data={"sub": str(user_id), "email": user.email, "username": user.username}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user_id)},
            device_id=device_id,
        )

        # Store refresh token hash
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_token_record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        self.db.add(refresh_token_record)
        await self.db.commit()

        return access_token, refresh_token

    async def refresh_access_token(self, refresh_token: str) -> Optional[tuple[str, str]]:
        """Refresh access token using refresh token."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        # Verify token in database
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            return None

        # Get user
        user_id = uuid.UUID(payload["sub"])
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return None

        # Update last used
        token_record.last_used_at = datetime.now(timezone.utc)
        await self.db.commit()

        # Generate new access token
        access_token = create_access_token(
            data={"sub": str(user_id), "email": user.email, "username": user.username}
        )

        # Optionally rotate refresh token
        new_refresh_token = create_refresh_token(
            data={"sub": str(user_id)},
            device_id=token_record.device_id,
        )

        # Revoke old token and create new one
        token_record.is_revoked = True
        token_record.revoked_at = datetime.now(timezone.utc)

        new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
        new_token_record = RefreshToken(
            user_id=user_id,
            token_hash=new_token_hash,
            device_id=token_record.device_id,
            device_name=token_record.device_name,
            device_type=token_record.device_type,
            ip_address=token_record.ip_address,
            user_agent=token_record.user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(new_token_record)
        await self.db.commit()

        return access_token, new_refresh_token

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a single refresh token."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token_record = result.scalar_one_or_none()
        
        if token_record:
            token_record.is_revoked = True
            token_record.revoked_at = datetime.now(timezone.utc)
            await self.db.commit()
            return True
        return False

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> int:
        """Revoke all refresh tokens for a user."""
        result = await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        await self.db.commit()
        return result.rowcount

    async def get_user_sessions(self, user_id: uuid.UUID, current_token: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user."""
        current_token_hash = hashlib.sha256(current_token.encode()).hexdigest()
        
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        tokens = result.scalars().all()
        
        sessions = []
        for token in tokens:
            sessions.append({
                "id": token.id,
                "device_name": token.device_name,
                "device_type": token.device_type,
                "ip_address": token.ip_address,
                "last_activity": token.last_used_at,
                "is_current": token.token_hash == current_token_hash,
            })
        
        return sessions

    async def _log_auth_event(
        self,
        user_id: Optional[uuid.UUID],
        event_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """Log authentication event."""
        audit_log = AuditLog(
            user_id=user_id,
            event_type=event_type,
            event_category="auth",
            severity="info" if success else "warning",
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )
        self.db.add(audit_log)
        await self.db.commit()
