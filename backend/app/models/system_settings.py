"""
System settings model for global application configuration.

Stored in SQLite (auth.db) alongside user data.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.auth_database import AuthBase
from app.core.config import settings


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
SETTING_PASSWORD_RESET = "password_reset"

PASSWORD_RESET_METHOD_SMTP = "smtp"
PASSWORD_RESET_METHOD_SECURITY_QUESTION = "security_question"


def _default_password_reset_settings() -> dict:
    smtp_config = {
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
        "username": settings.SMTP_USERNAME,
        "password": settings.SMTP_PASSWORD,
        "from_email": settings.SMTP_FROM_EMAIL,
        "from_name": settings.SMTP_FROM_NAME,
        "use_tls": settings.SMTP_USE_TLS,
        "use_ssl": settings.SMTP_USE_SSL,
        "timeout_seconds": settings.SMTP_TIMEOUT_SECONDS,
        "password_reset_url_template": settings.PASSWORD_RESET_URL_TEMPLATE,
    }
    smtp_ready = bool(
        str(settings.SMTP_HOST or "").strip()
        and str(settings.SMTP_FROM_EMAIL or "").strip()
        and str(settings.PASSWORD_RESET_URL_TEMPLATE or "").strip()
    )
    return {
        "method": PASSWORD_RESET_METHOD_SMTP if smtp_ready else PASSWORD_RESET_METHOD_SECURITY_QUESTION,
        "self_service_enabled": True,
        "smtp": smtp_config,
    }

# Default values
DEFAULT_SETTINGS = {
    SETTING_SIGNUP_ENABLED: {"enabled": True},
    SETTING_PASSWORD_RESET: _default_password_reset_settings(),
}
