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
from sqlalchemy import event
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
    async with auth_engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)
    
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
