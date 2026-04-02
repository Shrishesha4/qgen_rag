"""Helpers for reading and writing global settings stored in auth.db."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_settings import (
    DEFAULT_SETTINGS,
    PASSWORD_RESET_METHOD_SECURITY_QUESTION,
    PASSWORD_RESET_METHOD_SMTP,
    SETTING_PASSWORD_RESET,
    SystemSettings,
)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged


def _password_reset_defaults() -> dict[str, Any]:
    return deepcopy(DEFAULT_SETTINGS.get(SETTING_PASSWORD_RESET, {}))


def normalize_password_reset_settings(value: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize password-reset settings and merge them with defaults."""
    merged = _deep_merge(_password_reset_defaults(), value or {})
    method = str(merged.get("method") or "").strip().lower()
    if method not in {PASSWORD_RESET_METHOD_SMTP, PASSWORD_RESET_METHOD_SECURITY_QUESTION}:
        method = _password_reset_defaults().get("method", PASSWORD_RESET_METHOD_SECURITY_QUESTION)
    self_service_enabled = bool(merged.get("self_service_enabled", True))

    smtp = merged.get("smtp") or {}
    use_ssl = bool(smtp.get("use_ssl", False))
    normalized = {
        "method": method,
        "self_service_enabled": self_service_enabled,
        "smtp": {
            "host": str(smtp.get("host") or "").strip(),
            "port": int(smtp.get("port") or 587),
            "username": str(smtp.get("username") or "").strip(),
            "password": str(smtp.get("password") or ""),
            "from_email": str(smtp.get("from_email") or "").strip(),
            "from_name": str(smtp.get("from_name") or "VQuest").strip() or "VQuest",
            "use_tls": bool(smtp.get("use_tls", True)) and not use_ssl,
            "use_ssl": use_ssl,
            "timeout_seconds": max(1, int(smtp.get("timeout_seconds") or 20)),
            "password_reset_url_template": str(smtp.get("password_reset_url_template") or "").strip(),
        },
    }
    return normalized


async def get_setting(db: AsyncSession, key: str) -> dict[str, Any]:
    """Get a setting value, returning defaults when no row exists."""
    result = await db.execute(select(SystemSettings).where(SystemSettings.key == key))
    setting = result.scalar_one_or_none()
    stored = setting.value if setting and isinstance(setting.value, dict) else {}
    defaults = deepcopy(DEFAULT_SETTINGS.get(key, {}))
    return _deep_merge(defaults, stored)


async def set_setting(
    db: AsyncSession,
    key: str,
    value: dict[str, Any],
    user_id: str,
    *,
    description: str | None = None,
) -> SystemSettings:
    """Create or update a system setting row."""
    result = await db.execute(select(SystemSettings).where(SystemSettings.key == key))
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = value
        setting.updated_by = user_id
        if description is not None:
            setting.description = description
    else:
        setting = SystemSettings(
            key=key,
            value=value,
            description=description,
            updated_by=user_id,
        )
        db.add(setting)

    await db.commit()
    await db.refresh(setting)
    return setting


async def get_password_reset_settings(
    db: AsyncSession,
    *,
    include_secret: bool = False,
) -> dict[str, Any]:
    """Return password-reset settings with optional SMTP secret exposure."""
    normalized = normalize_password_reset_settings(await get_setting(db, SETTING_PASSWORD_RESET))
    password = normalized["smtp"].get("password", "")
    if include_secret:
        return normalized

    sanitized = deepcopy(normalized)
    sanitized["smtp_password_set"] = bool(password)
    sanitized["smtp"]["password"] = ""
    return sanitized


async def update_password_reset_settings(
    db: AsyncSession,
    value: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Persist password-reset settings while preserving the stored SMTP password when omitted."""
    existing = await get_password_reset_settings(db, include_secret=True)
    normalized = normalize_password_reset_settings(value)
    if not normalized["smtp"].get("password"):
        normalized["smtp"]["password"] = existing.get("smtp", {}).get("password", "")

    await set_setting(
        db,
        SETTING_PASSWORD_RESET,
        normalized,
        user_id,
        description="Password reset strategy and SMTP configuration",
    )
    return await get_password_reset_settings(db, include_secret=False)