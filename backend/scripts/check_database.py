#!/usr/bin/env python3
"""Database health check script.

Validates:
- PostgreSQL connectivity
- Required extensions
- Alembic migration table presence
- Required application tables for first-run safety
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.core.database import engine
from app.core.config import settings


REQUIRED_TABLES = {
    "subjects",
    "topics",
    "documents",
    "document_chunks",
    "questions",
    "generation_sessions",
    "rubrics",
    "vetting_logs",
    "training_pairs",
    "model_versions",
    "training_jobs",
}


async def check_database() -> tuple[list[str], list[str]]:
    """Check database for setup issues and return (issues, warnings)."""
    print("\n🔍 Checking database health...\n")

    issues: list[str] = []
    warnings: list[str] = []

    # Check auth database permissions first
    print("0. Checking auth database permissions...")
    try:
        from app.core.auth_database import auth_db_path
        import os

        auth_db_path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(auth_db_path.parent, 0o755)
        if auth_db_path.exists():
            os.chmod(auth_db_path, 0o664)
            print("✅ Auth database permissions verified")
        else:
            print("ℹ️  Auth database will be created on startup")
    except Exception as e:
        warnings.append(f"Auth DB permission check failed: {e}")

    print("\n1. Testing PostgreSQL connection...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")

            print("\n2. Checking required extensions...")
            ext_result = await conn.execute(
                text(
                    """
                    SELECT extname
                    FROM pg_extension
                    WHERE extname IN ('vector', 'pg_trgm')
                    """
                )
            )
            extensions = {row[0] for row in ext_result}
            if "vector" in extensions:
                print("✅ pgvector extension installed")
            else:
                warnings.append("pgvector extension not installed (will be created on startup)")

            if "pg_trgm" in extensions:
                print("✅ pg_trgm extension installed")
            else:
                warnings.append("pg_trgm extension not installed")

            print("\n3. Checking migration state...")
            tables_result = await conn.execute(
                text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                    """
                )
            )
            tables = {row[0] for row in tables_result}

            if "alembic_version" not in tables:
                issues.append(
                    "No alembic_version table found. Run: alembic upgrade head"
                )
            else:
                version_result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                version = version_result.scalar_one_or_none()
                if version:
                    print(f"✅ Alembic version: {version}")
                else:
                    issues.append("alembic_version table exists but is empty. Run: alembic upgrade head")

            print("\n4. Checking required tables...")
            missing_tables = sorted(REQUIRED_TABLES - tables)
            if missing_tables:
                issues.append(
                    "Missing required tables: "
                    + ", ".join(missing_tables)
                    + "\n   Run: alembic upgrade head"
                )
            else:
                print(f"✅ Required tables present ({len(REQUIRED_TABLES)})")

            print("\n5. Checking database size...")
            size_result = await conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
            db_size = size_result.scalar_one()
            print(f"ℹ️  Database size: {db_size}")

    except Exception as e:
        issues.append(f"Database connection failed: {e}")

    return issues, warnings


async def main():
    print(f"Database: {settings.POSTGRES_DB}")
    print(f"Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
    print(f"User: {settings.POSTGRES_USER}\n")

    try:
        issues, warnings = await check_database()

        print("\n" + "=" * 60)

        if issues:
            print("\n❌ ISSUES FOUND:")
            for issue in issues:
                print(f"\n{issue}")
            print("\n" + "=" * 60)
            sys.exit(1)

        if warnings:
            print("\n⚠️  WARNINGS:")
            for warning in warnings:
                print(f"   • {warning}")

        print("\n✅ Database health check passed!")
        print("\nDatabase schema is ready for application startup.")
        print("=" * 60)
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error during health check: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
