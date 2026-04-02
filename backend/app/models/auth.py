"""
Authentication-related database models.

Stored in SQLite (auth.db), decoupled from PostgreSQL/pgvector.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.auth_database import AuthBase


class RefreshToken(AuthBase):
    """Refresh token model for session management (SQLite)."""
    
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    
    # Device tracking
    device_id: Mapped[Optional[str]] = mapped_column(String(255))
    device_name: Mapped[Optional[str]] = mapped_column(String(100))
    device_type: Mapped[Optional[str]] = mapped_column(String(20))  # mobile, tablet, desktop
    
    # Network info
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 max length
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    
    # Token lifecycle
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")
    
    def __repr__(self) -> str:
        return f"<RefreshToken {self.id}>"


class AuditLog(AuthBase):
    """Audit log model for security events (SQLite)."""
    
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36))
    
    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_category: Mapped[Optional[str]] = mapped_column(String(20))  # auth, data, security, system
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info, warning, error, critical
    
    # Context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    device_id: Mapped[Optional[str]] = mapped_column(String(255))
    endpoint: Mapped[Optional[str]] = mapped_column(String(255))
    http_method: Mapped[Optional[str]] = mapped_column(String(10))
    
    # Details (JSON instead of JSONB for SQLite)
    event_data: Mapped[Optional[dict]] = mapped_column(JSON)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamp
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type} at {self.timestamp}>"


class AdminNotification(AuthBase):
    """Per-admin notification items stored in the auth database."""

    __tablename__ = "admin_notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    recipient_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    target_user_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    target_user_email: Mapped[Optional[str]] = mapped_column(String(255))
    target_username: Mapped[Optional[str]] = mapped_column(String(50))

    action_url: Mapped[Optional[str]] = mapped_column(String(500))
    action_label: Mapped[Optional[str]] = mapped_column(String(50))
    payload: Mapped[Optional[dict]] = mapped_column(JSON)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<AdminNotification {self.notification_type} for {self.recipient_user_id}>"
