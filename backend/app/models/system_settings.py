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
}
