"""
Analytics API endpoints for real-time activity tracking and historical data.
"""

import uuid
import logging
import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.auth_database import get_auth_db
from app.api.v1.deps import get_current_user
from app.models.document import Document
from app.models.question import Question
from app.models.user import User, ROLE_ADMIN
from app.models.subject import Subject, Topic
from app.models.training import VettingLog
from app.models.generation_run import GenerationRun
from app.services.analytics_websocket_manager import analytics_ws_manager

logger = logging.getLogger(__name__)
_PENDING_RECONCILIATION_CACHE_TTL_SECONDS = 5.0
_pending_reconciliation_cache: dict[str, object] = {
    "expires_at": 0.0,
    "items": [],
}

router = APIRouter()


class ActivityItem(BaseModel):
    user_id: str
    username: str
    email: str
    activity: str
    subject_name: str | None
    topic_name: str | None
    started_at: str
    duration_seconds: int


class ActiveUsersResponse(BaseModel):
    active_users: list[ActivityItem]
    vetting_count: int
    generating_count: int
    queued_count: int
    eligible_topics_count: int
    generated_questions_total: int
    target_questions_total: int
    remaining_questions: int
    topics_below_target_count: int
    topic_backlog_questions_total: int
    surplus_questions_total: int
    generating_items: list["GenerationWorkItem"]
    queued_items: list["GenerationWorkItem"]
    timestamp: str


class GenerationWorkItem(BaseModel):
    run_id: str
    subject_id: str
    subject_name: str | None
    topic_id: str | None = None
    topic_name: str | None = None
    topic_ids: list[str] = Field(default_factory=list)
    topic_names: list[str] = Field(default_factory=list)
    current_question: int
    total_questions: int
    progress: int
    status: str
    queue_position: int | None = None
    updated_at: str | None = None
    message: str | None = None


class HistoricalActivityItem(BaseModel):
    date: str
    hour: int | None = None
    vetting_count: int
    generation_count: int
    questions_vetted: int
    questions_generated: int
    unique_vetters: int
    unique_generators: int


class HistoricalResponse(BaseModel):
    items: list[HistoricalActivityItem]
    total_vetting_sessions: int
    total_generation_runs: int
    total_questions_vetted: int
    total_questions_generated: int


class RecentActivityItem(BaseModel):
    id: str
    user_id: str
    username: str
    activity_type: str
    subject_name: str | None
    topic_name: str | None
    count: int
    started_at: str
    ended_at: str | None


class RecentActivityResponse(BaseModel):
    items: list[RecentActivityItem]


def _ensure_admin(current_user: User) -> None:
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access analytics",
        )


def _dedupe_string_values(values: list[object]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _extract_topic_ids(topic_id: object, topic_ids: object) -> list[str]:
    return _dedupe_string_values(
        ([topic_id] if topic_id else []) + list(topic_ids or [])
    )


def _coerce_iso_timestamp(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return None


def _allocate_topic_totals(total_questions: int, topic_count: int) -> list[int]:
    if topic_count <= 0:
        return []

    sanitized_total = max(0, int(total_questions or 0))
    base_total = sanitized_total // topic_count
    remaining = sanitized_total % topic_count
    return [base_total + (1 if index < remaining else 0) for index in range(topic_count)]


def _distribute_progress(current_question: int, topic_totals: list[int]) -> list[int]:
    if not topic_totals:
        return []

    total_capacity = sum(topic_totals)
    if total_capacity <= 0:
        return [0 for _ in topic_totals]

    clamped_current = max(0, min(int(current_question or 0), total_capacity))
    if clamped_current <= 0:
        return [0 for _ in topic_totals]

    provisional: list[int] = []
    fractional_parts: list[tuple[float, int]] = []
    for index, topic_total in enumerate(topic_totals):
        raw_value = (clamped_current * topic_total) / total_capacity
        allocated = min(topic_total, int(raw_value))
        provisional.append(allocated)
        fractional_parts.append((raw_value - allocated, index))

    remaining = clamped_current - sum(provisional)
    for _, index in sorted(fractional_parts, reverse=True):
        if remaining <= 0:
            break
        if provisional[index] >= topic_totals[index]:
            continue
        provisional[index] += 1
        remaining -= 1

    return provisional


def _resolve_topic_entries(
    *,
    explicit_topic_id: object,
    explicit_topic_name: object,
    topic_ids: list[str],
    topic_names: list[str],
    topic_name_map: dict[str, str],
) -> list[tuple[str | None, str | None]]:
    entries: list[tuple[str | None, str | None]] = []
    if topic_ids:
        for index, topic_id in enumerate(topic_ids):
            resolved_name = topic_name_map.get(topic_id)
            if index < len(topic_names) and topic_names[index]:
                resolved_name = topic_names[index]
            entries.append((topic_id, resolved_name))
    elif explicit_topic_id or explicit_topic_name:
        normalized_topic_id = str(explicit_topic_id or "").strip() or None
        resolved_name = str(explicit_topic_name or "").strip() or None
        if normalized_topic_id and not resolved_name:
            resolved_name = topic_name_map.get(normalized_topic_id)
        entries.append((normalized_topic_id, resolved_name))
    elif topic_names:
        entries.extend((None, topic_name) for topic_name in topic_names)

    deduped_entries: list[tuple[str | None, str | None]] = []
    seen_keys: set[tuple[str | None, str | None]] = set()
    for topic_id, topic_name in entries:
        normalized_name = str(topic_name or "").strip() or None
        dedupe_key = (topic_id, normalized_name)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        deduped_entries.append((topic_id, normalized_name))

    return deduped_entries


def _build_topic_scoped_work_items(
    *,
    run_id: str,
    subject_id: str,
    subject_name: str | None,
    explicit_topic_id: object,
    explicit_topic_name: object,
    topic_ids: list[str],
    topic_names: list[str],
    topic_name_map: dict[str, str],
    current_question: int,
    total_questions: int,
    progress: int,
    status: str,
    queue_position: int | None,
    updated_at: str | None,
    message: str | None,
) -> list[GenerationWorkItem]:
    topic_entries = _resolve_topic_entries(
        explicit_topic_id=explicit_topic_id,
        explicit_topic_name=explicit_topic_name,
        topic_ids=topic_ids,
        topic_names=topic_names,
        topic_name_map=topic_name_map,
    )

    if len(topic_entries) <= 1:
        topic_id, topic_name = topic_entries[0] if topic_entries else (None, None)
        return [
            GenerationWorkItem(
                run_id=run_id,
                subject_id=subject_id,
                subject_name=subject_name,
                topic_id=topic_id,
                topic_name=topic_name,
                topic_ids=[topic_id] if topic_id else [],
                topic_names=[topic_name] if topic_name else [],
                current_question=max(0, int(current_question or 0)),
                total_questions=max(0, int(total_questions or 0)),
                progress=max(0, min(100, int(progress or 0))),
                status=status,
                queue_position=queue_position,
                updated_at=updated_at,
                message=message,
            )
        ]

    topic_totals = _allocate_topic_totals(total_questions, len(topic_entries))
    topic_progress_counts = _distribute_progress(current_question, topic_totals)
    scoped_items: list[GenerationWorkItem] = []

    for index, (topic_entry, topic_total, topic_current) in enumerate(
        zip(topic_entries, topic_totals, topic_progress_counts)
    ):
        topic_id, topic_name = topic_entry
        scoped_progress = int((topic_current / max(1, topic_total)) * 100) if topic_total > 0 else max(0, min(100, int(progress or 0)))
        scoped_items.append(
            GenerationWorkItem(
                run_id=f"{run_id}:{topic_id or index}",
                subject_id=subject_id,
                subject_name=subject_name,
                topic_id=topic_id,
                topic_name=topic_name,
                topic_ids=[topic_id] if topic_id else [],
                topic_names=[topic_name] if topic_name else [],
                current_question=topic_current,
                total_questions=topic_total,
                progress=scoped_progress,
                status=status,
                queue_position=queue_position,
                updated_at=updated_at,
                message=message,
            )
        )

    return scoped_items


async def _get_pending_reconciliation_backlog_summary() -> dict[str, object]:
    now = time.monotonic()
    cached_expires_at = float(_pending_reconciliation_cache.get("expires_at") or 0.0)
    cached_items = _pending_reconciliation_cache.get("items")
    if now < cached_expires_at and isinstance(cached_items, dict):
        summary = dict(cached_items)
        summary["items"] = [dict(item) for item in list(summary.get("items") or [])]
        return summary

    from app.api.v1.endpoints.questions import _topic_has_generation_content
    from app.services.provider_service import get_provider_service

    provider_service = get_provider_service()
    provider_config = await provider_service.get_config()
    batch_size = int(provider_config.generation_batch_size or 0)
    if batch_size <= 0:
        summary = {
            "items": [],
            "eligible_topics_count": 0,
            "generated_questions_total": 0,
            "target_questions_total": 0,
            "remaining_questions_total": 0,
            "topics_below_target_count": 0,
            "topic_backlog_questions_total": 0,
            "surplus_questions_total": 0,
        }
        _pending_reconciliation_cache.update({"expires_at": now + _PENDING_RECONCILIATION_CACHE_TTL_SECONDS, "items": summary})
        return dict(summary)

    async with AsyncSessionLocal() as db:
        subject_result = await db.execute(
            select(Subject)
            .options(selectinload(Subject.topics))
            .where(Subject.user_id.isnot(None))
        )
        subjects = list(subject_result.scalars().all())
        if not subjects:
            summary = {
                "items": [],
                "eligible_topics_count": 0,
                "generated_questions_total": 0,
                "target_questions_total": 0,
                "remaining_questions_total": 0,
                "topics_below_target_count": 0,
                "topic_backlog_questions_total": 0,
                "surplus_questions_total": 0,
            }
            _pending_reconciliation_cache.update({"expires_at": now + _PENDING_RECONCILIATION_CACHE_TTL_SECONDS, "items": summary})
            return dict(summary)

        subject_ids = [str(subject.id) for subject in subjects]
        topic_stats: dict[str, dict[str, dict[str, int]]] = {
            str(subject.id): {
                str(topic.id): {"generated": 0, "pending": 0}
                for topic in subject.topics
            }
            for subject in subjects
        }
        orphan_stats: dict[str, dict[str, int]] = {
            str(subject.id): {"generated": 0, "pending": 0}
            for subject in subjects
        }

        question_rows = await db.execute(
            select(Question.subject_id, Question.topic_id, Question.vetting_status, func.count(Question.id))
            .where(
                Question.subject_id.in_(subject_ids),
                Question.is_archived == False,
                Question.is_latest == True,
            )
            .group_by(Question.subject_id, Question.topic_id, Question.vetting_status)
        )
        for subject_key, topic_key, vetting_status, question_count in question_rows.all():
            subject_id = str(subject_key) if subject_key else None
            if not subject_id or subject_id not in topic_stats:
                continue

            count_value = int(question_count or 0)
            normalized_topic_id = str(topic_key) if topic_key else None
            if normalized_topic_id and normalized_topic_id in topic_stats[subject_id]:
                topic_stats[subject_id][normalized_topic_id]["generated"] += count_value
                if (vetting_status or "pending") == "pending":
                    topic_stats[subject_id][normalized_topic_id]["pending"] += count_value
                continue

            orphan_stats[subject_id]["generated"] += count_value
            if (vetting_status or "pending") == "pending":
                orphan_stats[subject_id]["pending"] += count_value

        for subject in subjects:
            subject_id = str(subject.id)
            if len(subject.topics) != 1:
                continue
            only_topic_id = str(subject.topics[0].id)
            topic_stats[subject_id][only_topic_id]["generated"] += orphan_stats[subject_id]["generated"]
            topic_stats[subject_id][only_topic_id]["pending"] += orphan_stats[subject_id]["pending"]

        reference_doc_rows = await db.execute(
            select(Document.subject_id, Document.topic_id, func.count(Document.id))
            .where(
                Document.subject_id.in_(subject_ids),
                Document.topic_id.isnot(None),
                Document.index_type.in_(("reference_book", "template_paper")),
            )
            .group_by(Document.subject_id, Document.topic_id)
        )
        reference_doc_counts = {
            (str(subject_key), str(topic_key)): int(doc_count or 0)
            for subject_key, topic_key, doc_count in reference_doc_rows.all()
            if subject_key and topic_key
        }

        pending_items: list[dict[str, object]] = []
        eligible_topics_count = 0
        generated_questions_total = 0
        topic_backlog_questions_total = 0
        surplus_questions_total = 0
        for subject in subjects:
            subject_id = str(subject.id)
            sorted_topics = sorted(subject.topics, key=lambda topic: topic.order_index or 0)
            for topic in sorted_topics:
                topic_id = str(topic.id)
                reference_doc_count = reference_doc_counts.get((subject_id, topic_id), 0)
                if not _topic_has_generation_content(topic, reference_doc_count):
                    continue

                eligible_topics_count += 1
                stats = topic_stats[subject_id].get(topic_id, {"generated": 0, "pending": 0})
                generated_questions = int(stats["generated"] or 0)
                generated_questions_total += generated_questions
                remaining_questions = max(batch_size - generated_questions, 0)
                topic_backlog_questions_total += remaining_questions
                surplus_questions_total += max(generated_questions - batch_size, 0)
                if remaining_questions <= 0:
                    continue

                pending_items.append(
                    {
                        "subject_id": subject_id,
                        "subject_name": subject.name,
                        "topic_id": topic_id,
                        "topic_name": topic.name,
                        "generated_questions": generated_questions,
                        "total_questions": batch_size,
                        "remaining_questions": remaining_questions,
                        "progress": int((generated_questions / max(1, batch_size)) * 100),
                    }
                )

    summary = {
        "items": [dict(item) for item in pending_items],
        "eligible_topics_count": eligible_topics_count,
        "generated_questions_total": generated_questions_total,
        "target_questions_total": eligible_topics_count * batch_size,
        "remaining_questions_total": max((eligible_topics_count * batch_size) - generated_questions_total, 0),
        "topics_below_target_count": len(pending_items),
        "topic_backlog_questions_total": topic_backlog_questions_total,
        "surplus_questions_total": surplus_questions_total,
    }

    _pending_reconciliation_cache.update(
        {
            "expires_at": now + _PENDING_RECONCILIATION_CACHE_TTL_SECONDS,
            "items": summary,
        }
    )
    return dict(summary)


async def _build_background_generation_work_items() -> tuple[list[GenerationWorkItem], list[GenerationWorkItem], dict[str, object]]:
    from app.api.v1.endpoints.questions import (
        _BACKGROUND_GENERATION_QUEUE,
        _BACKGROUND_GENERATION_STATUS,
        _BACKGROUND_GENERATION_TASKS,
        _get_current_running_count,
    )

    backlog_summary = await _get_pending_reconciliation_backlog_summary()
    pending_backlog_items = list(backlog_summary.get("items") or [])

    _get_current_running_count()
    queued_snapshot = list(_BACKGROUND_GENERATION_QUEUE)
    running_snapshot: list[tuple[str, dict]] = []
    for task_key, task in list(_BACKGROUND_GENERATION_TASKS.items()):
        if task.done():
            continue
        status = _BACKGROUND_GENERATION_STATUS.get(task_key) or {}
        if not status or status.get("in_progress") is False or status.get("status") == "queued":
            continue
        running_snapshot.append((task_key, status))

    subject_ids: set[str] = set()
    topic_ids: set[str] = set()

    for queue_item in queued_snapshot:
        subject_id = str(queue_item.get("subject_id") or "").strip()
        if subject_id:
            subject_ids.add(subject_id)
        request_data = queue_item.get("request_data") or {}
        topic_ids.update(_extract_topic_ids(request_data.get("topic_id"), request_data.get("topic_ids")))

    for task_key, status in running_snapshot:
        _, _, derived_subject_id = task_key.partition(":")
        subject_id = str(status.get("subject_id") or derived_subject_id or "").strip()
        if subject_id:
            subject_ids.add(subject_id)
        topic_ids.update(_extract_topic_ids(status.get("topic_id"), status.get("topic_ids")))

    subject_name_map: dict[str, str] = {}
    topic_name_map: dict[str, str] = {}
    if subject_ids or topic_ids:
        async with AsyncSessionLocal() as db:
            if subject_ids:
                subject_rows = await db.execute(
                    select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
                )
                subject_name_map = {str(subject_id): name for subject_id, name in subject_rows.all() if subject_id and name}
            if topic_ids:
                topic_rows = await db.execute(
                    select(Topic.id, Topic.name).where(Topic.id.in_(topic_ids))
                )
                topic_name_map = {str(topic_id): name for topic_id, name in topic_rows.all() if topic_id and name}

    generating_items: list[GenerationWorkItem] = []
    queued_items: list[GenerationWorkItem] = []
    scheduled_topic_keys: set[tuple[str, str]] = set()
    opaque_scheduled_subject_ids: set[str] = set()

    for task_key, status in running_snapshot:
        _, _, derived_subject_id = task_key.partition(":")
        subject_id = str(status.get("subject_id") or derived_subject_id or "").strip()
        resolved_topic_ids = _extract_topic_ids(status.get("topic_id"), status.get("topic_ids"))
        resolved_topic_names = _dedupe_string_values(status.get("topic_names") or [])
        if not resolved_topic_names:
            resolved_topic_names = [topic_name_map[topic_id] for topic_id in resolved_topic_ids if topic_id in topic_name_map]

        generating_items.extend(
            _build_topic_scoped_work_items(
                run_id=str(status.get("run_id") or task_key),
                subject_id=subject_id,
                subject_name=str(status.get("subject_name") or subject_name_map.get(subject_id) or "") or None,
                explicit_topic_id=status.get("topic_id"),
                explicit_topic_name=status.get("topic_name"),
                topic_ids=resolved_topic_ids,
                topic_names=resolved_topic_names,
                topic_name_map=topic_name_map,
                current_question=int(status.get("current_question") or 0),
                total_questions=int(status.get("total_questions") or 0),
                progress=int(status.get("progress") or 0),
                status=str(status.get("status") or "generating"),
                queue_position=None,
                updated_at=_coerce_iso_timestamp(status.get("updated_at")),
                message=str(status.get("message") or "") or None,
            )
        )
        if resolved_topic_ids:
            scheduled_topic_keys.update((subject_id, topic_id) for topic_id in resolved_topic_ids)
        else:
            opaque_scheduled_subject_ids.add(subject_id)

    generating_items.sort(key=lambda item: (item.updated_at or "", item.subject_name or ""), reverse=True)

    for position, queue_item in enumerate(queued_snapshot, start=1):
        request_data = queue_item.get("request_data") or {}
        subject_id = str(queue_item.get("subject_id") or "").strip()
        resolved_topic_ids = _extract_topic_ids(request_data.get("topic_id"), request_data.get("topic_ids"))
        resolved_topic_names = [topic_name_map[topic_id] for topic_id in resolved_topic_ids if topic_id in topic_name_map]

        queued_items.extend(
            _build_topic_scoped_work_items(
                run_id=str(queue_item.get("run_id") or f"queued-{position}"),
                subject_id=subject_id,
                subject_name=subject_name_map.get(subject_id),
                explicit_topic_id=request_data.get("topic_id"),
                explicit_topic_name=request_data.get("topic_name"),
                topic_ids=resolved_topic_ids,
                topic_names=resolved_topic_names,
                topic_name_map=topic_name_map,
                current_question=0,
                total_questions=int(queue_item.get("count") or 0),
                progress=0,
                status="queued",
                queue_position=position,
                updated_at=_coerce_iso_timestamp(queue_item.get("added_at")),
                message=f"Waiting for capacity in queue position {position}",
            )
        )
        if resolved_topic_ids:
            scheduled_topic_keys.update((subject_id, topic_id) for topic_id in resolved_topic_ids)
        else:
            opaque_scheduled_subject_ids.add(subject_id)

    scheduled_subject_ids = {subject_id for subject_id, _ in scheduled_topic_keys} | opaque_scheduled_subject_ids
    for pending_item in pending_backlog_items:
        subject_id = str(pending_item.get("subject_id") or "").strip()
        topic_id = str(pending_item.get("topic_id") or "").strip()
        if not subject_id or not topic_id:
            continue
        if subject_id in opaque_scheduled_subject_ids:
            continue
        if (subject_id, topic_id) in scheduled_topic_keys:
            continue

        subject_is_already_busy = subject_id in scheduled_subject_ids
        remaining_questions = int(pending_item.get("remaining_questions") or 0)
        target_questions = int(pending_item.get("total_questions") or 0)
        generated_questions = int(pending_item.get("generated_questions") or 0)
        queued_items.append(
            GenerationWorkItem(
                run_id=f"pending:{subject_id}:{topic_id}",
                subject_id=subject_id,
                subject_name=str(pending_item.get("subject_name") or "") or None,
                topic_id=topic_id,
                topic_name=str(pending_item.get("topic_name") or "") or None,
                topic_ids=[topic_id],
                topic_names=[str(pending_item.get("topic_name") or "")] if pending_item.get("topic_name") else [],
                current_question=generated_questions,
                total_questions=target_questions,
                progress=int(pending_item.get("progress") or 0),
                status="queued",
                queue_position=None,
                updated_at=None,
                message=(
                    f"{remaining_questions} more questions needed to reach {target_questions}; waiting for the current subject generation to finish"
                    if subject_is_already_busy
                    else f"{remaining_questions} more questions needed to reach {target_questions}; waiting for generation capacity"
                ),
            )
        )

    queued_items.sort(
        key=lambda item: (
            item.queue_position is None,
            item.queue_position or 10**9,
            item.subject_name or "",
            item.topic_name or "",
        )
    )
    return generating_items, queued_items, backlog_summary


async def _build_live_activity_response() -> ActiveUsersResponse:
    all_active_users = await analytics_ws_manager.get_active_users()
    active_users = [user for user in all_active_users if user["activity"] == "vetting"]
    generating_items, queued_items, backlog_summary = await _build_background_generation_work_items()

    return ActiveUsersResponse(
        active_users=[ActivityItem(**u) for u in active_users],
        vetting_count=len(active_users),
        generating_count=len(generating_items),
        queued_count=len(queued_items),
        eligible_topics_count=int(backlog_summary.get("eligible_topics_count") or 0),
        generated_questions_total=int(backlog_summary.get("generated_questions_total") or 0),
        target_questions_total=int(backlog_summary.get("target_questions_total") or 0),
        remaining_questions=int(backlog_summary.get("remaining_questions_total") or 0),
        topics_below_target_count=int(backlog_summary.get("topics_below_target_count") or 0),
        topic_backlog_questions_total=int(backlog_summary.get("topic_backlog_questions_total") or 0),
        surplus_questions_total=int(backlog_summary.get("surplus_questions_total") or 0),
        generating_items=generating_items,
        queued_items=queued_items,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _dump_model(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@router.get("/active", response_model=ActiveUsersResponse)
async def get_active_users(
    current_user: User = Depends(get_current_user),
):
    """Get live vetting sessions and automatic generation queue counts."""
    _ensure_admin(current_user)

    return await _build_live_activity_response()


@router.get("/historical", response_model=HistoricalResponse)
async def get_historical_analytics(
    days: int = Query(default=7, ge=1, le=90),
    group_by: str = Query(default="day", pattern="^(day|hour)$"),
    current_user: User = Depends(get_current_user),
):
    """Get historical analytics data grouped by day or hour."""
    _ensure_admin(current_user)
    
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    
    async with AsyncSessionLocal() as db:
        # Get vetting stats
        vetting_query = select(
            func.date(VettingLog.created_at).label("date"),
            func.count(VettingLog.id).label("vetting_count"),
            func.count(func.distinct(VettingLog.vetter_id)).label("unique_vetters"),
        ).where(
            VettingLog.created_at >= start_date
        ).group_by(
            func.date(VettingLog.created_at)
        )
        
        vetting_result = await db.execute(vetting_query)
        vetting_by_date = {str(r.date): {"count": r.vetting_count, "unique": r.unique_vetters} for r in vetting_result}
        
        # Get generation stats
        gen_query = select(
            func.date(GenerationRun.started_at).label("date"),
            func.count(GenerationRun.id).label("gen_count"),
            func.sum(GenerationRun.current_question).label("questions_generated"),
            func.count(func.distinct(GenerationRun.user_id)).label("unique_generators"),
        ).where(
            GenerationRun.started_at >= start_date
        ).group_by(
            func.date(GenerationRun.started_at)
        )
        
        gen_result = await db.execute(gen_query)
        gen_by_date = {
            str(r.date): {
                "count": r.gen_count,
                "questions": r.questions_generated or 0,
                "unique": r.unique_generators
            } for r in gen_result
        }
        
        # Combine into response
        items = []
        all_dates = set(vetting_by_date.keys()) | set(gen_by_date.keys())
        
        for date_str in sorted(all_dates):
            vetting = vetting_by_date.get(date_str, {"count": 0, "unique": 0})
            gen = gen_by_date.get(date_str, {"count": 0, "questions": 0, "unique": 0})
            
            items.append(HistoricalActivityItem(
                date=date_str,
                vetting_count=vetting["count"],
                generation_count=gen["count"],
                questions_vetted=vetting["count"],  # 1 log per question
                questions_generated=gen["questions"],
                unique_vetters=vetting["unique"],
                unique_generators=gen["unique"],
            ))
        
        # Calculate totals
        total_vetting = sum(v["count"] for v in vetting_by_date.values())
        total_gen = sum(g["count"] for g in gen_by_date.values())
        total_questions_vetted = total_vetting
        total_questions_generated = sum(g["questions"] for g in gen_by_date.values())
        
        return HistoricalResponse(
            items=items,
            total_vetting_sessions=total_vetting,
            total_generation_runs=total_gen,
            total_questions_vetted=total_questions_vetted,
            total_questions_generated=total_questions_generated,
        )


@router.get("/recent", response_model=RecentActivityResponse)
async def get_recent_activity(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """Get recent activity log."""
    _ensure_admin(current_user)
    
    items = []
    
    async with AsyncSessionLocal() as db:
        # Get recent generation runs
        gen_query = select(GenerationRun).order_by(
            GenerationRun.started_at.desc()
        ).limit(limit // 2)
        
        gen_result = await db.execute(gen_query)
        for run in gen_result.scalars():
            items.append(RecentActivityItem(
                id=str(run.id),
                user_id=str(run.user_id) if run.user_id else "system",
                username=run.user_id or "System",
                activity_type="generation",
                subject_name=None,  # Would need to join
                topic_name=None,
                count=run.generated_count or 0,
                started_at=run.started_at.isoformat() if run.started_at else "",
                ended_at=run.completed_at.isoformat() if run.completed_at else None,
            ))
    
    # Get recent vetting from auth db
    auth_db = None
    try:
        async for db in get_auth_db():
            auth_db = db
            break
        
        if auth_db:
            # Get user lookup for vetting
            pass  # VettingLog is in main DB, users in auth DB
    except Exception as e:
        logger.warning(f"Could not get auth db for user lookup: {e}")
    
    # Sort by time
    items.sort(key=lambda x: x.started_at, reverse=True)
    
    return RecentActivityResponse(items=items[:limit])


@router.websocket("/ws")
async def analytics_websocket(
    websocket: WebSocket,
    token: str = Query(None, description="Auth token for admin identification"),
):
    """
    WebSocket endpoint for real-time analytics updates.
    
    Connect and receive:
    - {"type": "activity_update", "data": {...}}
    
    Send:
    - {"action": "ping"} -> {"type": "pong"}
    """
    connection_id = str(uuid.uuid4())
    
    # For now, allow connections with a token (production would validate)
    user_id = token or "anonymous"
    is_admin = bool(token)  # In production, validate token and check admin role
    
    try:
        await analytics_ws_manager.connect(websocket, connection_id, user_id, is_admin)
        
        # Send initial state
        live_snapshot = await _build_live_activity_response()
        await websocket.send_json({
            "type": "connected",
            "connection_id": connection_id,
        })
        await websocket.send_json({
            "type": "activity_update",
            "data": _dump_model(live_snapshot),
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                action = data.get("action")
                
                if action == "ping":
                    await websocket.send_json({"type": "pong"})
                    await websocket.send_json({
                        "type": "activity_update",
                        "data": _dump_model(await _build_live_activity_response()),
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}",
                    })
            
            except ValueError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid message format: {str(e)}",
                })
    
    except WebSocketDisconnect:
        logger.info(f"Analytics WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"Analytics WebSocket error for {connection_id}: {e}")
    finally:
        await analytics_ws_manager.disconnect(connection_id)
