"""Helpers for recording structured user activity in the auth database."""

from __future__ import annotations

import logging
from typing import Optional, Any

from fastapi import Request

from app.core.auth_database import AuthSessionLocal
from app.models.auth import ActivityLog
from app.models.user import User


logger = logging.getLogger(__name__)


def _normalize_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _user_display_name(user: User) -> str:
    return user.full_name or user.username or user.email or "Unknown user"


def _extract_request_context(request: Optional[Request]) -> dict[str, Optional[str]]:
    if request is None:
        return {
            "ip_address": None,
            "user_agent": None,
            "endpoint": None,
            "http_method": None,
        }

    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("User-Agent"),
        "endpoint": request.url.path,
        "http_method": request.method,
    }


async def record_activity(
    *,
    user: User,
    action_key: str,
    action_label: str,
    category: str,
    source_area: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    entity_name: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_name: Optional[str] = None,
    topic_id: Optional[str] = None,
    topic_name: Optional[str] = None,
    group_id: Optional[str] = None,
    group_name: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    request: Optional[Request] = None,
) -> None:
    """Persist a structured activity event in the auth database."""
    request_context = _extract_request_context(request)

    async with AuthSessionLocal() as auth_db:
        auth_db.add(
            ActivityLog(
                actor_user_id=user.id,
                actor_role=_normalize_string(user.role),
                actor_name=_user_display_name(user),
                actor_email=_normalize_string(user.email),
                action_key=action_key,
                action_label=action_label,
                category=category,
                source_area=_normalize_string(source_area),
                entity_type=_normalize_string(entity_type),
                entity_id=_normalize_string(entity_id),
                entity_name=_normalize_string(entity_name),
                subject_id=_normalize_string(subject_id),
                subject_name=_normalize_string(subject_name),
                topic_id=_normalize_string(topic_id),
                topic_name=_normalize_string(topic_name),
                group_id=_normalize_string(group_id),
                group_name=_normalize_string(group_name),
                ip_address=_normalize_string(request_context["ip_address"]),
                user_agent=_normalize_string(request_context["user_agent"]),
                endpoint=_normalize_string(request_context["endpoint"]),
                http_method=_normalize_string(request_context["http_method"]),
                details=details or None,
                success=success,
                error_message=_normalize_string(error_message),
            )
        )
        await auth_db.commit()


async def safe_record_activity(**kwargs: Any) -> None:
    """Best-effort activity logging that never breaks user-facing flows."""
    try:
        await record_activity(**kwargs)
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.warning("Failed to record activity log: %s", exc)