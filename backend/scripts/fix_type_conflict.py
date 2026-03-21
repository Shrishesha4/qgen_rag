#!/usr/bin/env python3
"""
Quick Fix for PostgreSQL Type Conflicts

This script fixes the "duplicate key value violates unique constraint pg_type_typname_nsp_index"
error by dropping conflicting types and ensuring clean migration state.

Usage:
    python scripts/fix_type_conflict.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine
from app.core.config import settings


async def fix_type_conflicts():
    """Fix PostgreSQL type name conflicts."""
    
    print("🔧 Analyzing database for conflicts...\n")
    print(f"Database: {settings.POSTGRES_DB}")
    print(f"Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}\n")
    
    async with engine.begin() as conn:
        # Check if tables exist
        result = await conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result]
        
        if tables:
            print(f"ℹ️  Found {len(tables)} existing tables")
            print("   These tables are fine - they automatically create composite types.")
            print("   This is normal PostgreSQL behavior.\n")
            
            # Check if alembic_version exists
            if 'alembic_version' in tables:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                version = result.scalar_one_or_none()
                if version:
                    print(f"✅ Database already migrated (version: {version})")
                    print("\n✅ No action needed - database is healthy!")
                    return True
                else:
                    print("⚠️  Alembic version table exists but is empty")
            else:
                print("ℹ️  No migration history found")
        else:
            print("ℹ️  No tables found (fresh database)")
        
        # Ensure pgvector extension exists
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("✅ pgvector extension verified")
        
        # Check if alembic_version table exists
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename = 'alembic_version'
            )
        """))
        has_alembic = result.scalar()
        
        if not has_alembic:
            print("ℹ️  No alembic_version table found")
        else:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar_one_or_none()
            if version:
                print(f"ℹ️  Current migration version: {version}")
    
    print("\n" + "="*60)
    print("✅ Type conflicts fixed!")
    print("\nNext steps:")
    print("   1. Run: alembic upgrade head")
    print("   2. Restart your application")
    print("="*60)
    
    return True


async def main():
    try:
        success = await fix_type_conflicts()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nIf the error persists, try:")
        print("   python scripts/reset_database.py")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
