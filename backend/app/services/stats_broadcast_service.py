"""
Service for broadcasting stats updates via WebSocket.
Called when questions are vetted, generated, or deleted.
"""

import logging
from typing import Optional
from sqlalchemy import select, func, Integer, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.models.subject import Subject, Topic
from app.services.websocket_manager import generation_ws_manager

logger = logging.getLogger(__name__)


async def broadcast_vetting_stats_update(
    db: AsyncSession,
    subject_id: str,
    topic_id: Optional[str] = None,
) -> None:
    """
    Broadcast updated stats after a vetting action.
    Calculates current stats from the database and broadcasts to all subscribers.
    """
    try:
        # Get subject stats
        subject_stats = await _get_subject_stats(db, subject_id)
        
        if subject_stats:
            await generation_ws_manager.broadcast_subject_stats_update(
                subject_id=subject_id,
                stats_data=subject_stats,
            )
        
        # Get topic stats if topic_id provided
        if topic_id:
            topic_stats = await _get_topic_stats(db, subject_id, topic_id)
            if topic_stats:
                await generation_ws_manager.broadcast_topic_stats_update(
                    subject_id=subject_id,
                    topic_id=topic_id,
                    stats_data=topic_stats,
                )
        
        # Broadcast global stats update
        global_stats = await _get_global_stats(db)
        if global_stats:
            await generation_ws_manager.broadcast_stats_update(global_stats)
            
    except Exception as e:
        logger.warning(f"Failed to broadcast stats update: {e}")


async def _get_subject_stats(db: AsyncSession, subject_id: str) -> Optional[dict]:
    """Get stats for a specific subject."""
    try:
        # Get question counts by status
        result = await db.execute(
            select(
                func.count(Question.id).label('total'),
                func.sum(case((Question.vetting_status == 'approved', 1), else_=0)).label('approved'),
                func.sum(case((Question.vetting_status == 'rejected', 1), else_=0)).label('rejected'),
            ).where(Question.subject_id == subject_id)
        )
        row = result.one_or_none()
        
        if not row:
            return None
        
        total = int(row.total or 0)
        approved = int(row.approved or 0)
        rejected = int(row.rejected or 0)
        pending = total - approved - rejected
        vetted = approved + rejected
        approval_rate = round((approved / vetted * 100) if vetted > 0 else 0)
        
        return {
            "subject_id": subject_id,
            "total_questions": total,
            "total_approved": approved,
            "total_rejected": rejected,
            "total_pending": pending,
            "total_vetted": vetted,
            "approval_rate": approval_rate,
        }
    except Exception as e:
        logger.warning(f"Failed to get subject stats: {e}")
        return None


async def _get_topic_stats(db: AsyncSession, subject_id: str, topic_id: str) -> Optional[dict]:
    """Get stats for a specific topic."""
    try:
        result = await db.execute(
            select(
                func.count(Question.id).label('total'),
                func.sum(case((Question.vetting_status == 'approved', 1), else_=0)).label('approved'),
                func.sum(case((Question.vetting_status == 'rejected', 1), else_=0)).label('rejected'),
            ).where(
                Question.subject_id == subject_id,
                Question.topic_id == topic_id,
            )
        )
        row = result.one_or_none()
        
        if not row:
            return None
        
        total = int(row.total or 0)
        approved = int(row.approved or 0)
        rejected = int(row.rejected or 0)
        pending = total - approved - rejected
        vetted = approved + rejected
        approval_rate = round((approved / vetted * 100) if vetted > 0 else 0)
        
        return {
            "topic_id": topic_id,
            "subject_id": subject_id,
            "generated": total,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "vetted": vetted,
            "approval_rate": approval_rate,
        }
    except Exception as e:
        logger.warning(f"Failed to get topic stats: {e}")
        return None


async def _get_global_stats(db: AsyncSession) -> Optional[dict]:
    """Get global stats across all subjects."""
    try:
        result = await db.execute(
            select(
                func.count(Question.id).label('total'),
                func.sum(case((Question.vetting_status == 'approved', 1), else_=0)).label('approved'),
                func.sum(case((Question.vetting_status == 'rejected', 1), else_=0)).label('rejected'),
            )
        )
        row = result.one_or_none()
        
        if not row:
            return None
        
        total = int(row.total or 0)
        approved = int(row.approved or 0)
        rejected = int(row.rejected or 0)
        pending = total - approved - rejected
        vetted = approved + rejected
        approval_rate = round((approved / vetted * 100) if vetted > 0 else 0)
        
        return {
            "total_questions": total,
            "total_approved": approved,
            "total_rejected": rejected,
            "total_pending": pending,
            "total_vetted": vetted,
            "approval_rate": approval_rate,
        }
    except Exception as e:
        logger.warning(f"Failed to get global stats: {e}")
        return None
