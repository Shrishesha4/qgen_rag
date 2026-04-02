"""
Persistent state for GEL Train tutoring sessions.

Each row represents one student's session on a subject/topic. Sessions are
soft-deleted (is_active flag) so history is preserved.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, Integer, DateTime, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.core.database import Base
from app.core.types import UUIDString


class InquirySession(Base):
    """Persists the full state of a GEL Train tutoring session (PostgreSQL)."""

    __tablename__ = "inquiry_sessions"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # References auth SQLite user — stored as plain string (cross-DB)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Subject / topic context
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    topic_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Session progress
    current_level: Mapped[str] = mapped_column(String(20), nullable=False, default="beginner")
    # e.g. {"beginner": 2, "advanced": 0, "pro": 0}
    completed_turns_by_level: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # [{role: "user"|"assistant", content: "..."}]
    messages: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    current_phase: Mapped[str] = mapped_column(String(30), nullable=False, default="awaiting-answer")
    current_question_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<InquirySession {self.id} user={self.user_id} level={self.current_level}>"
