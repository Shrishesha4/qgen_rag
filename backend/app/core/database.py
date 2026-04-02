"""
Database connection and session management.
"""

import os
import time
from typing import AsyncGenerator
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def calculate_pool_settings() -> dict:
    """Calculate DB pool settings based on configured worker count."""
    worker_count = max(1, int(os.getenv("API_WORKERS", settings.API_WORKERS)))

    # Each process has its own pool; keep a safe minimum for bursty workloads.
    pool_size = max(20, settings.DB_POOL_SIZE_BASE * worker_count)
    max_overflow = max(10, settings.DB_POOL_MAX_OVERFLOW * worker_count)

    return {
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    }


_pool_settings = calculate_pool_settings()

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    **_pool_settings,
    # Verify connections before checkout to avoid using stale/broken connections
    pool_pre_ping=True,
    # Always rollback on return so interrupted transactions don't poison the pool
    pool_reset_on_return="rollback",
)

logger.info(
    "Database pool configured",
    extra={
        "pool_size": _pool_settings["pool_size"],
        "max_overflow": _pool_settings["max_overflow"],
        "pool_timeout": _pool_settings["pool_timeout"],
        "pool_recycle": _pool_settings["pool_recycle"],
    },
)


if settings.DB_ENABLE_POOL_MONITORING:
    @event.listens_for(engine.sync_engine.pool, "checkout")
    def _on_pool_checkout(dbapi_conn, connection_record, connection_proxy):
        connection_record.info["checked_out_at"] = time.monotonic()
        logger.debug("DB pool checkout: %s", engine.sync_engine.pool.status())


    @event.listens_for(engine.sync_engine.pool, "checkin")
    def _on_pool_checkin(dbapi_conn, connection_record):
        checked_out_at = connection_record.info.pop("checked_out_at", None)
        if checked_out_at is not None:
            held_seconds = time.monotonic() - checked_out_at
            logger.debug("DB pool checkin after %.3fs: %s", held_seconds, engine.sync_engine.pool.status())
        else:
            logger.debug("DB pool checkin: %s", engine.sync_engine.pool.status())

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def init_db():
    """Initialize database and create tables.
    
    Note: This only sets up extensions and indexes.
    Tables should be created via Alembic migrations: `alembic upgrade head`
    """
    # Initialize PostgreSQL (pgvector) database
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # DO NOT use Base.metadata.create_all() here!
        # It can cause type conflicts and bypasses migration tracking.
        # Always use: alembic upgrade head
    
    # Initialize SQLite auth database
    from app.core.auth_database import init_auth_db
    await init_auth_db()
    
    # Create indexes after tables exist (safe to run multiple times)
    await create_indexes()


async def create_indexes():
    """Create database indexes for optimal query performance."""
    async with AsyncSessionLocal() as session:
        lock_id = 820240115
        lock_acquired = False
        try:
            # Ensure only one worker performs index creation during multi-worker startup.
            lock_result = await session.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": lock_id},
            )
            lock_acquired = bool(lock_result.scalar())
            if not lock_acquired:
                logger.info("Skipping index creation in this worker (startup lock held by another worker)")
                return

            # Create B-tree indexes (always safe)
            await session.execute(text("SELECT create_btree_indexes()"))
            logger.info("B-tree indexes created/verified")
            
            # Try to create vector indexes (requires minimum rows)
            await session.execute(text("SELECT create_vector_indexes()"))
            logger.info("Vector indexes created/verified")
            
            await session.commit()
        except Exception as e:
            # Functions may not exist on first run before init_db.sql runs
            logger.warning(f"Could not create indexes (will retry on next startup): {e}")
            await session.rollback()
        finally:
            if lock_acquired:
                try:
                    await session.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": lock_id},
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()


async def ensure_vector_indexes():
    """
    Ensure vector indexes exist. Call this periodically or after bulk inserts.
    IVFFlat indexes require a minimum number of rows to be created.
    """
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("SELECT create_vector_indexes()"))
            await session.commit()
            logger.info("Vector indexes ensured")
        except Exception as e:
            logger.warning(f"Could not ensure vector indexes: {e}")
            await session.rollback()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
