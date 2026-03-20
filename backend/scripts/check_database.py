#!/usr/bin/env python3
"""
Database Health Check Script

Checks for common database issues before running migrations.
Detects type conflicts, missing extensions, and other problems.

Usage:
    python scripts/check_database.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine
from app.core.config import settings


async def check_database():
    """Check database for common issues."""
    
    print("🔍 Checking database health...\n")
    
    issues = []
    warnings = []
    
    async with engine.begin() as conn:
        # Check 1: Database connection
        try:
            await conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
        except Exception as e:
            issues.append(f"Cannot connect to database: {e}")
            return issues, warnings
        
        # Check 2: Required extensions
        result = await conn.execute(text("""
            SELECT extname FROM pg_extension 
            WHERE extname IN ('vector', 'pg_trgm')
        """))
        extensions = {row[0] for row in result}
        
        if 'vector' not in extensions:
            warnings.append("pgvector extension not installed (will be created on startup)")
        else:
            print("✅ pgvector extension installed")
        
        if 'pg_trgm' not in extensions:
            warnings.append("pg_trgm extension not installed")
        else:
            print("✅ pg_trgm extension installed")
        
        # Check 3: Type name conflicts
        result = await conn.execute(text("""
            SELECT typname 
            FROM pg_type 
            WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            AND typname IN ('subjects', 'topics', 'questions', 'users', 'training_jobs', 
                           'training_pairs', 'model_versions', 'model_evaluations')
        """))
        conflicting_types = [row[0] for row in result]
        
        if conflicting_types:
            issues.append(
                f"Type name conflicts detected: {', '.join(conflicting_types)}\n"
                f"   These type names conflict with table names.\n"
                f"   Run: python scripts/reset_database.py"
            )
        else:
            print("✅ No type name conflicts")
        
        # Check 4: Existing tables
        result = await conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """))
        tables = [row[0] for row in result]
        
        if tables:
            print(f"ℹ️  Found {len(tables)} existing tables")
            if 'alembic_version' in tables:
                # Check migration version
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                version = result.scalar_one_or_none()
                if version:
                    print(f"✅ Alembic version: {version}")
                else:
                    warnings.append("Alembic version table exists but is empty")
            else:
                warnings.append(
                    "No alembic_version table found. "
                    "Run 'alembic upgrade head' to initialize migrations."
                )
        else:
            print("ℹ️  No tables found (fresh database)")
            print("   Run: alembic upgrade head")
        
        # Check 5: Database size
        result = await conn.execute(text("""
            SELECT pg_size_pretty(pg_database_size(current_database()))
        """))
        db_size = result.scalar_one()
        print(f"ℹ️  Database size: {db_size}")
    
    return issues, warnings


async def main():
    print(f"Database: {settings.POSTGRES_DB}")
    print(f"Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
    print(f"User: {settings.POSTGRES_USER}\n")
    
    try:
        issues, warnings = await check_database()
        
        print("\n" + "="*60)
        
        if issues:
            print("\n❌ ISSUES FOUND:")
            for issue in issues:
                print(f"\n{issue}")
            print("\n" + "="*60)
            sys.exit(1)
        
        if warnings:
            print("\n⚠️  WARNINGS:")
            for warning in warnings:
                print(f"   • {warning}")
        
        print("\n✅ Database health check passed!")
        print("\nYou can safely run: alembic upgrade head")
        print("="*60)
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error during health check: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
