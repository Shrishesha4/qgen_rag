"""
Service for managing generation run status in the database.
Provides methods to create, update, and query generation runs,
and broadcasts updates via WebSocket.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation_run import GenerationRun
from app.services.websocket_manager import generation_ws_manager

logger = logging.getLogger(__name__)


class GenerationStatusService:
    """Service for managing generation run status with database persistence."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_run(
        self,
        run_id: str,
        subject_id: str,
        topic_id: str,
        user_id: str,
        target_count: int = 30,
        status: str = "pending",
        message: str = "Generation scheduled",
    ) -> GenerationRun:
        """Create a new generation run record."""
        run = GenerationRun(
            id=run_id,
            subject_id=subject_id,
            topic_id=topic_id,
            user_id=user_id,
            status=status,
            in_progress=True,
            current_question=0,
            total_questions=target_count,
            target_count=target_count,
            message=message,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        
        # Broadcast the new run
        await self._broadcast_update(run)
        
        logger.info(f"Created generation run {run_id} for topic {topic_id}")
        return run
    
    async def update_progress(
        self,
        run_id: str,
        current_question: int,
        total_questions: Optional[int] = None,
        status: str = "generating",
        message: Optional[str] = None,
    ) -> Optional[GenerationRun]:
        """Update the progress of a generation run."""
        result = await self.db.execute(
            select(GenerationRun).where(GenerationRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        
        if not run:
            logger.warning(f"Generation run {run_id} not found for progress update")
            return None
        
        run.current_question = current_question
        if total_questions is not None:
            run.total_questions = total_questions
        run.status = status
        if message:
            run.message = message
        run.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(run)
        
        # Broadcast the update
        await self._broadcast_update(run)
        
        return run
    
    async def complete_run(
        self,
        run_id: str,
        final_count: int,
        status: str = "completed",
        message: str = "Generation completed",
    ) -> Optional[GenerationRun]:
        """Mark a generation run as completed."""
        result = await self.db.execute(
            select(GenerationRun).where(GenerationRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        
        if not run:
            logger.warning(f"Generation run {run_id} not found for completion")
            return None
        
        run.current_question = final_count
        run.status = status
        run.message = message
        run.in_progress = False
        run.completed_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(run)
        
        # Broadcast the completion
        await self._broadcast_update(run)
        
        logger.info(f"Completed generation run {run_id} with {final_count} questions")
        return run
    
    async def fail_run(
        self,
        run_id: str,
        error_message: str,
    ) -> Optional[GenerationRun]:
        """Mark a generation run as failed."""
        result = await self.db.execute(
            select(GenerationRun).where(GenerationRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        
        if not run:
            logger.warning(f"Generation run {run_id} not found for failure")
            return None
        
        run.status = "failed"
        run.message = "Generation failed"
        run.error_message = error_message
        run.in_progress = False
        run.completed_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(run)
        
        # Broadcast the failure
        await self._broadcast_update(run)
        
        logger.error(f"Failed generation run {run_id}: {error_message}")
        return run
    
    async def get_run(self, run_id: str) -> Optional[GenerationRun]:
        """Get a generation run by ID."""
        result = await self.db.execute(
            select(GenerationRun).where(GenerationRun.id == run_id)
        )
        return result.scalar_one_or_none()
    
    async def get_active_runs_for_subject(self, subject_id: str) -> List[GenerationRun]:
        """Get all active generation runs for a subject."""
        result = await self.db.execute(
            select(GenerationRun).where(
                and_(
                    GenerationRun.subject_id == subject_id,
                    GenerationRun.in_progress == True,
                )
            )
        )
        return list(result.scalars().all())
    
    async def get_active_run_for_topic(self, topic_id: str) -> Optional[GenerationRun]:
        """Get the active generation run for a topic (if any)."""
        result = await self.db.execute(
            select(GenerationRun).where(
                and_(
                    GenerationRun.topic_id == topic_id,
                    GenerationRun.in_progress == True,
                )
            ).order_by(GenerationRun.started_at.desc())
        )
        return result.scalar_one_or_none()
    
    async def get_recent_runs_for_subject(
        self,
        subject_id: str,
        limit: int = 10,
    ) -> List[GenerationRun]:
        """Get recent generation runs for a subject."""
        result = await self.db.execute(
            select(GenerationRun)
            .where(GenerationRun.subject_id == subject_id)
            .order_by(GenerationRun.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def _broadcast_update(self, run: GenerationRun) -> None:
        """Broadcast a generation status update via WebSocket."""
        try:
            await generation_ws_manager.broadcast_generation_update(
                subject_id=run.subject_id,
                topic_id=run.topic_id,
                status_data=run.to_status_dict(),
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast generation update: {e}")


async def broadcast_generation_update(
    subject_id: str,
    topic_id: str,
    status_data: dict,
) -> None:
    """Standalone function to broadcast generation updates."""
    try:
        await generation_ws_manager.broadcast_generation_update(
            subject_id=subject_id,
            topic_id=topic_id,
            status_data=status_data,
        )
    except Exception as e:
        logger.warning(f"Failed to broadcast generation update: {e}")
