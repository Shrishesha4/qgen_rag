"""
Provider Usage Tracking Service.

Tracks non-question-generation provider interactions (chat, analysis, etc.)
in a non-blocking, fire-and-forget manner to avoid database performance impact.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.provider_usage import ProviderUsageLog


logger = logging.getLogger(__name__)


class ProviderUsageTrackingService:
    """
    Non-blocking service for tracking provider usage.
    
    Uses fire-and-forget pattern with error handling to ensure
    tracking failures don't impact application performance.
    """
    
    @staticmethod
    def track_usage(
        *,
        provider_key: str,
        user_id: str,
        usage_type: str,
        provider_name: Optional[str] = None,
        provider_model: Optional[str] = None,
        subject_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        session_id: Optional[str] = None,
        usage_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track provider usage in the background (non-blocking).
        
        This method returns immediately - the database write happens
        in the background and errors are logged but don't propagate.
        
        Args:
            provider_key: Provider identifier (e.g., "openai", "deepseek")
            user_id: User who made the request
            usage_type: Type of usage (e.g., "chat", "analysis", "improvement")
            provider_name: Human-readable provider name
            provider_model: Model used (e.g., "gpt-4", "deepseek-chat")
            subject_id: Optional subject context
            topic_id: Optional topic context
            session_id: Optional session grouping for multi-turn conversations
            usage_metadata: Optional additional metadata as dict
        """
        # Create background task - fire and forget
        asyncio.create_task(
            ProviderUsageTrackingService._track_usage_async(
                provider_key=provider_key,
                user_id=user_id,
                usage_type=usage_type,
                provider_name=provider_name,
                provider_model=provider_model,
                subject_id=subject_id,
                topic_id=topic_id,
                session_id=session_id,
                usage_metadata=usage_metadata,
            )
        )
    
    @staticmethod
    async def _track_usage_async(
        *,
        provider_key: str,
        user_id: str,
        usage_type: str,
        provider_name: Optional[str],
        provider_model: Optional[str],
        subject_id: Optional[str],
        topic_id: Optional[str],
        session_id: Optional[str],
        usage_metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Internal async method that performs the actual database write."""
        try:
            # Use a new database session for background tracking
            async with AsyncSessionLocal() as db:
                # Serialize metadata dict to JSON string
                metadata_json = None
                if usage_metadata:
                    try:
                        metadata_json = json.dumps(usage_metadata)
                    except Exception as e:
                        logger.warning(f"Failed to serialize usage_metadata: {e}")
                
                usage_log = ProviderUsageLog(
                    id=str(uuid.uuid4()),
                    provider_key=provider_key.lower().strip(),
                    provider_name=provider_name,
                    provider_model=provider_model,
                    user_id=user_id,
                    subject_id=subject_id,
                    topic_id=topic_id,
                    usage_type=usage_type.lower().strip(),
                    session_id=session_id,
                    usage_metadata=metadata_json,
                    created_at=datetime.now(timezone.utc),
                )
                
                db.add(usage_log)
                await db.commit()
                
                logger.debug(
                    f"Tracked provider usage: {provider_key} for {usage_type} "
                    f"(user={user_id}, session={session_id})"
                )
        
        except Exception as e:
            # Log error but don't propagate - tracking failures shouldn't
            # impact the main application flow
            logger.error(
                f"Failed to track provider usage for {provider_key}/{usage_type}: {e}",
                exc_info=True
            )
    
    @staticmethod
    async def track_usage_sync(
        *,
        db: AsyncSession,
        provider_key: str,
        user_id: str,
        usage_type: str,
        provider_name: Optional[str] = None,
        provider_model: Optional[str] = None,
        subject_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        session_id: Optional[str] = None,
        usage_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track provider usage synchronously using an existing session.
        
        Use this when you already have a database session and want
        tracking to be part of the same transaction. This is blocking
        but can be more efficient when batching multiple operations.
        
        Args:
            db: Existing database session
            (other args same as track_usage)
        """
        try:
            # Serialize metadata dict to JSON string
            metadata_json = None
            if usage_metadata:
                try:
                    metadata_json = json.dumps(usage_metadata)
                except Exception as e:
                    logger.warning(f"Failed to serialize usage_metadata: {e}")
            
            usage_log = ProviderUsageLog(
                id=str(uuid.uuid4()),
                provider_key=provider_key.lower().strip(),
                provider_name=provider_name,
                provider_model=provider_model,
                user_id=user_id,
                subject_id=subject_id,
                topic_id=topic_id,
                usage_type=usage_type.lower().strip(),
                session_id=session_id,
                usage_metadata=metadata_json,
                created_at=datetime.now(timezone.utc),
            )
            
            db.add(usage_log)
            # Note: Caller must commit the session
            
            logger.debug(
                f"Tracked provider usage (sync): {provider_key} for {usage_type} "
                f"(user={user_id}, session={session_id})"
            )
        
        except Exception as e:
            logger.error(
                f"Failed to track provider usage (sync) for {provider_key}/{usage_type}: {e}",
                exc_info=True
            )
            # Don't raise - let the main operation continue


# Convenience singleton instance
provider_usage_tracker = ProviderUsageTrackingService()
