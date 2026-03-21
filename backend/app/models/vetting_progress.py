"""Teacher vetting progress persistence model."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
import uuid

from app.core.database import Base
from app.core.types import UUIDString


class TeacherVettingProgress(Base):
    """Server-side snapshot of a teacher's vetting loop progress."""

    __tablename__ = "teacher_vetting_progress"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    progress_key: Mapped[str] = mapped_column(String(255), nullable=False)

    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True
    )

    mixed_topics_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    selected_mixed_topic_ids: Mapped[Optional[List[str]]] = mapped_column(JSONB)

    generation_batch_size: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    allow_no_pdf_generation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    questions_snapshot: Mapped[List[dict]] = mapped_column(JSONB, nullable=False)
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approved_question_ids: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    rejected_question_ids: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    batch_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "progress_key", name="uq_teacher_vetting_progress_user_key"),
    )

    def __repr__(self) -> str:
        return f"<TeacherVettingProgress user={self.user_id} key={self.progress_key}>"
