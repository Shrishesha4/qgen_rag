"""
Provider usage tracking model for non-question generation interactions.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.core.database import Base
from app.core.types import UUIDString


class ProviderUsageLog(Base):
    """Tracks provider usage for interactions that don't generate Question records, such as GEL Train conversational inquiry."""
    
    __tablename__ = "provider_usage_logs"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    
    # Provider info
    provider_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(100))
    provider_model: Mapped[Optional[str]] = mapped_column(String(100))
    
    # User and context
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subject_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    topic_id: Mapped[Optional[str]] = mapped_column(String(36))
    
    # Usage type: conversational_inquiry, chat, etc.
    usage_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Session grouping (for multi-turn conversations)
    session_id: Mapped[Optional[str]] = mapped_column(UUIDString(), index=True)
    
    # Additional metadata (JSON)
    usage_metadata: Mapped[Optional[dict]] = mapped_column(Text)  # Store as JSON string
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    
    def __repr__(self) -> str:
        return f"<ProviderUsageLog {self.id} provider={self.provider_key} type={self.usage_type}>"
