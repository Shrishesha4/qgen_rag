#!/usr/bin/env python3
"""
Database Reset Script

This script safely resets the PostgreSQL database to a clean state.
Use this when setting up the project on a new machine or when encountering
database schema conflicts.

Usage:
    python scripts/reset_database.py [--confirm]
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine
from app.core.config import settings
import argparse


async def reset_database(confirm: bool = False):
    """Reset the database to a clean state."""
    
    if not confirm:
        print("⚠️  WARNING: This will DROP ALL TABLES and DATA in the database!")
        print(f"   Database: {settings.POSTGRES_DB}")
        print(f"   Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        print()
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Aborted.")
            return False
    
    print("\n🔄 Resetting database...")
    
    async with engine.begin() as conn:
        # Drop all tables in the public schema
        print("   Dropping all tables...")
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        
        # Enable required extensions
        print("   Enabling extensions...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        
        # Create index management functions
        print("   Creating index management functions...")
        init_sql_path = Path(__file__).parent.parent / "init_db.sql"
        if init_sql_path.exists():
            init_sql = init_sql_path.read_text()
            # Split into individual statements and execute
            # PostgreSQL functions are delimited by $$ ... $$
            statements = []
            current_stmt = []
            in_function = False
            
            for line in init_sql.split('\n'):
                line_stripped = line.strip()
                
                # Skip comments and empty lines
                if not line_stripped or line_stripped.startswith('--'):
                    continue
                
                current_stmt.append(line)
                
                # Track if we're inside a function definition
                if '$$' in line:
                    in_function = not in_function
                
                # End of statement (semicolon outside of function)
                if ';' in line and not in_function:
                    stmt = '\n'.join(current_stmt)
                    if stmt.strip():
                        statements.append(stmt)
                    current_stmt = []
            
            # Execute each statement separately
            for stmt in statements:
                if stmt.strip():
                    await conn.execute(text(stmt))
        else:
            print("   ⚠️  Warning: init_db.sql not found, skipping function creation")
        
    print("✅ Database reset complete!")
    print()
    print("Next steps:")
    print("   1. Run migrations: alembic upgrade head")
    print("   2. Start the application")
    return True


async def main():
    parser = argparse.ArgumentParser(description="Reset the PostgreSQL database")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )
    args = parser.parse_args()
    
    try:
        success = await reset_database(confirm=args.confirm)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
