"""
Topic Audit Log model for tracking changes to topics.
Provides a history/timeline view of who modified what.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.core.database import Base


class TopicAuditLog(Base):
    """Audit log entry for topic modifications."""

    __tablename__ = "topic_audit_log"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    topic_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    user_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    # Action: 'create', 'update', 'delete', 'upload_pdf', 'delete_pdf'
    action: Mapped[str] = mapped_column(String(50), nullable=False)

    # Field that was changed (e.g. 'topic_name', 'description', 'syllabus_content', 'reference_pdf')
    field_name: Mapped[Optional[str]] = mapped_column(String(100))

    # Old and new values (truncated for large text fields)
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<TopicAuditLog {self.action} on {self.field_name} by {self.user_name}>"
