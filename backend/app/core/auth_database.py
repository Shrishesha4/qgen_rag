"""
SQLite database for authentication and user management.

Decoupled from PostgreSQL/pgvector to keep auth simple, portable,
and independent of the vector database.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

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
