"""
System settings model for global application configuration.

Stored in SQLite (auth.db) alongside user data.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.auth_database import AuthBase


class SystemSettings(AuthBase):
    """System-wide settings stored as key-value pairs."""
    
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    description: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(36))  # User ID who last updated

    def __repr__(self) -> str:
        return f"<SystemSettings {self.key}>"


# Default settings keys
SETTING_SIGNUP_ENABLED = "signup_enabled"
SETTING_PROVIDER_GENERATION_CONFIG = "provider_generation_config"
SETTING_GEL_CONFIG = "gel_config"
SETTING_STUDENT_SIGNUP_ENABLED = "student_signup_enabled"

# Default values
DEFAULT_SETTINGS = {
    SETTING_SIGNUP_ENABLED: {"enabled": True},
    SETTING_PROVIDER_GENERATION_CONFIG: {
        "providers": [
            {
                "key": "deepseek",
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com/v1",
                "enabled": True,
                "questions_per_batch": 10,
                "model": "deepseek-chat",
                "api_key": "",
            },
            {
                "key": "gemini",
                "name": "Gemini",
                "base_url": "https://generativelanguage.googleapis.com",
                "enabled": False,
                "questions_per_batch": 10,
                "model": "gemini-2.0-flash",
                "api_key": "",
            },
            {
                "key": "ollama",
                "name": "Ollama (Local)",
                "base_url": "http://localhost:11434",
                "enabled": False,
                "questions_per_batch": 10,
                "model": "llama3.1:8b",
                "api_key": "",
            },
        ],
    },
    SETTING_STUDENT_SIGNUP_ENABLED: {"enabled": False},  # Student self-signup disabled by default
    SETTING_GEL_CONFIG: {
        "enabled": True,
        "default_rubric_weights": {
            "detection": 0.35,
            "reasoning": 0.25,
            "correction": 0.20,
            "confidence_calibration": 0.20,
        },
        "default_max_attempts": 1,
        "default_time_limit_minutes": None,
        "show_feedback_immediately": False,
        "require_consent": True,
        "overconfidence_penalty_factor": 1.5,
        "passing_score": 60,
    },
}
