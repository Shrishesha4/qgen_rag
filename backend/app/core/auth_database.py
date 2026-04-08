"""
SQLite database for authentication and user management.

Decoupled from PostgreSQL/pgvector to keep auth simple, portable,
and independent of the vector database.
"""

from typing import AsyncGenerator
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Ensure auth database directory exists and has correct permissions
auth_db_path = Path(settings.AUTH_DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
auth_db_path = auth_db_path.resolve()

# Create directory if it doesn't exist
auth_db_path.parent.mkdir(parents=True, exist_ok=True)

# Set correct permissions on directory (755)
os.chmod(auth_db_path.parent, 0o755)

# If database file exists, ensure correct permissions (664)
if auth_db_path.exists():
    os.chmod(auth_db_path, 0o664)

# Create async SQLite engine for auth
auth_engine = create_async_engine(
    settings.AUTH_DATABASE_URL,
    echo=False,
    future=True,
    # SQLite doesn't support pool_size/max_overflow the same way,
    # but we use StaticPool for aiosqlite compatibility
    connect_args={"check_same_thread": False},
)

# Enable WAL mode and foreign keys for SQLite via event listener
@event.listens_for(auth_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Create async session factory for auth
AuthSessionLocal = async_sessionmaker(
    auth_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Separate Base for auth models (SQLite)
AuthBase = declarative_base()


async def init_auth_db():
    """Initialize SQLite auth database and create tables."""
    from app.models.user import User  # noqa: F401
    from app.models.auth import RefreshToken, AuditLog, AdminNotification, UserFavorite, ActivityLog  # noqa: F401
    from app.models.system_settings import SystemSettings  # noqa: F401
    from app.models.custom_theme import CustomTheme  # noqa: F401

    async with auth_engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)

        from app.core.security import hash_security_answer
        from app.models.user import DEFAULT_SECURITY_QUESTION

        # Lightweight schema evolution for existing SQLite deployments.
        table_info = await conn.execute(text("PRAGMA table_info(users)"))
        existing_columns = {row[1] for row in table_info.fetchall()}

        if "can_manage_groups" not in existing_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN can_manage_groups BOOLEAN"))
        if "can_generate" not in existing_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN can_generate BOOLEAN"))
        if "can_vet" not in existing_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN can_vet BOOLEAN"))
        if "security_question" not in existing_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN security_question VARCHAR(255)"))
        if "security_answer_hash" not in existing_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN security_answer_hash VARCHAR(255)"))
        if "is_approved" not in existing_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN is_approved BOOLEAN"))
        if "approved_at" not in existing_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN approved_at DATETIME"))
        if "approved_by" not in existing_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN approved_by VARCHAR(36)"))

        # Backfill defaults for legacy rows where new columns are null.
        await conn.execute(
            text(
                """
                UPDATE users
                SET can_manage_groups = CASE
                    WHEN role IN ('teacher', 'admin') THEN 1
                    ELSE 0
                END
                WHERE can_manage_groups IS NULL
                """
            )
        )
        await conn.execute(
            text(
                """
                UPDATE users
                SET can_generate = CASE
                    WHEN role IN ('teacher', 'admin') THEN 1
                    ELSE 0
                END
                WHERE can_generate IS NULL
                """
            )
        )
        await conn.execute(
            text(
                """
                UPDATE users
                SET can_vet = CASE
                    WHEN role IN ('teacher', 'vetter', 'admin') THEN 1
                    ELSE 0
                END
                WHERE can_vet IS NULL
                """
            )
        )
        await conn.execute(
            text(
                """
                UPDATE users
                SET security_question = :security_question
                WHERE security_question IS NULL OR TRIM(security_question) = ''
                """
            ),
            {"security_question": DEFAULT_SECURITY_QUESTION},
        )
        await conn.execute(
            text(
                """
                UPDATE users
                SET security_answer_hash = :security_answer_hash
                WHERE security_answer_hash IS NULL OR TRIM(security_answer_hash) = ''
                """
            ),
            {"security_answer_hash": hash_security_answer("reset")},
        )
        await conn.execute(
            text(
                """
                UPDATE users
                SET is_approved = 1
                WHERE is_approved IS NULL
                """
            )
        )
        await conn.execute(
            text(
                """
                UPDATE users
                SET approved_at = COALESCE(approved_at, created_at, CURRENT_TIMESTAMP)
                WHERE is_approved = 1 AND approved_at IS NULL
                """
            )
        )
        
        # Schema evolution for custom_themes table
        theme_info = await conn.execute(text("PRAGMA table_info(custom_themes)"))
        theme_columns = {row[1] for row in theme_info.fetchall()}
        
        if "is_builtin" not in theme_columns:
            await conn.execute(text("ALTER TABLE custom_themes ADD COLUMN is_builtin BOOLEAN DEFAULT 0"))
    
    # Ensure database file has correct permissions after creation
    if auth_db_path.exists():
        os.chmod(auth_db_path, 0o664)
    
    logger.info("Auth database (SQLite) initialized")


async def get_auth_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get auth database session."""
    async with AuthSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
