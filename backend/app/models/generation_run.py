"""
GenerationRun model for tracking background question generation status.
Persisted to database so status is visible across all devices/sessions.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base


class GenerationRun(Base):
    """Tracks background question generation runs for topics."""
    
    __tablename__ = "generation_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    
    # Foreign keys
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    
    # Status tracking
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # pending, generating, completed, failed, cancelled
    
    in_progress: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
    # Progress tracking
    current_question: Mapped[int] = mapped_column(Integer, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    target_count: Mapped[int] = mapped_column(Integer, default=30)
    
    # Additional info
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Relationships
    subject = relationship("Subject")
    topic = relationship("Topic")
    
    def __repr__(self) -> str:
        return f"<GenerationRun {self.id} topic={self.topic_id} status={self.status}>"
    
    def to_status_dict(self) -> dict:
        """Convert to status dictionary for API response."""
        return {
            "run_id": self.id,
            "subject_id": self.subject_id,
            "topic_id": self.topic_id,
            "in_progress": self.in_progress,
            "status": self.status,
            "progress": int((self.current_question / max(1, self.total_questions)) * 100) if self.total_questions else 0,
            "current_question": self.current_question,
            "total_questions": self.total_questions,
            "target_total_questions": self.target_count,
            "message": self.message,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
