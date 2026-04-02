"""
User database model.

Stored in SQLite (auth.db), decoupled from PostgreSQL/pgvector.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, Integer, DateTime, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.auth_database import AuthBase


# User roles
ROLE_TEACHER = "teacher"
ROLE_VETTER = "vetter"
ROLE_ADMIN = "admin"
VALID_ROLES = {ROLE_TEACHER, ROLE_VETTER, ROLE_ADMIN}
DEFAULT_SECURITY_QUESTION = "What is your security reset word?"

# Permission keys for action-level authorization
PERMISSION_MANAGE_GROUPS = "can_manage_groups"
PERMISSION_GENERATE = "can_generate"
PERMISSION_VET = "can_vet"


def default_permissions_for_role(role: str) -> dict[str, bool]:
    """Return default action permissions for the given role."""
    normalized_role = (role or ROLE_TEACHER).strip().lower()
    if normalized_role == ROLE_ADMIN:
        return {
            PERMISSION_MANAGE_GROUPS: True,
            PERMISSION_GENERATE: True,
            PERMISSION_VET: True,
        }
    if normalized_role == ROLE_VETTER:
        return {
            PERMISSION_MANAGE_GROUPS: False,
            PERMISSION_GENERATE: False,
            PERMISSION_VET: True,
        }
    # Teachers keep current behavior by default.
    return {
        PERMISSION_MANAGE_GROUPS: True,
        PERMISSION_GENERATE: True,
        PERMISSION_VET: True,
    }


class User(AuthBase):
    """User model for authentication and authorization (SQLite)."""
    
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Profile
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    language: Mapped[str] = mapped_column(String(10), default="en")
    
    # Role: "teacher" (default), "vetter", or "admin"
    role: Mapped[str] = mapped_column(String(20), default=ROLE_TEACHER, nullable=False)

    # Action-level authorization flags managed by admins.
    can_manage_groups: Mapped[bool] = mapped_column(Boolean, default=True)
    can_generate: Mapped[bool] = mapped_column(Boolean, default=True)
    can_vet: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36))
    
    # Security
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    security_question: Mapped[Optional[str]] = mapped_column(String(255), default=DEFAULT_SECURITY_QUESTION)
    security_answer_hash: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Preferences (JSON instead of JSONB for SQLite)
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    
    # Subject-level Reference Materials (stored per subject)
    # Format: {"subject_id": {"reference_books": [...], "template_papers": [...]}}
    subject_reference_materials: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    
    # Relationships (within auth DB only)
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User {self.username}>"
