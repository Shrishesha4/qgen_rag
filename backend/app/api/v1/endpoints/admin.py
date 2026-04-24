"""
Admin Dashboard API endpoints.

Provides aggregate statistics across the entire platform:
subjects, topics, questions generated, vetting stats, per-user breakdowns.
"""

from typing import Optional, List, Any, Dict
from collections import Counter
from datetime import datetime, timezone, timedelta
import base64
import csv
import io
import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_, case, distinct, delete, or_, literal, false
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.auth_database import AuthSessionLocal, get_auth_db
from app.api.v1.deps import get_client_info, get_current_admin
from app.models.user import User, VALID_ROLES, default_permissions_for_role
from app.models.question import Question, GenerationSession
from app.models.subject import Subject, Topic
from app.models.document import Document
from app.models.vetting_progress import TeacherVettingProgress
from app.models.training import VettingLog, TrainingPair
from app.models.provider_usage import ProviderUsageLog
from app.core.security import hash_password, hash_security_answer
from app.schemas.auth import MessageResponse
from app.services.admin_notification_service import AdminNotificationService
from app.services.subject_group_filter_service import get_subject_ids_for_group
from app.services.user_service import UserService


router = APIRouter()

_ADMIN_QUESTION_FEED_DEFAULT_LIMIT = 40
_ADMIN_QUESTION_FEED_MAX_LIMIT = 80
_ADMIN_QUESTION_EXPORT_BATCH_SIZE = 500
_ADMIN_QUESTION_EXPORT_PREVIEW_LIMIT = 5
_ADMIN_QUESTION_EXPORT_DEFAULT_FIELDS = (
    "question_text",
    "correct_answer",
    "answer_options",
    "subject_name",
    "topic_name",
    "difficulty_level",
)


# ============== Schemas ==============


class ProviderMetric(BaseModel):
    provider_key: str
    total_generated: int
    api_calls: int
    avg_questions_per_call: float
    total_rejected: int
    total_regenerated: int
    total_vetted: int
    rejection_rate: float
    regeneration_rate: float
    inferred_preference: str
    top_rejection_reasons: List[str]


class ProviderMetricsResponse(BaseModel):
    window_days: int
    total_generated: int
    total_rejected: int
    total_regenerated: int
    providers: List[ProviderMetric]


class VetterBreakdown(BaseModel):
    """Stats for a single vetter."""
    user_id: str
    username: str
    full_name: Optional[str]
    email: str
    total_vetted: int
    total_approved: int
    total_rejected: int


class UserStats(BaseModel):
    """Per-user generation and vetting stats."""
    user_id: str
    username: str
    full_name: Optional[str]
    email: str
    role: str
    total_generated: int
    total_vetted: int
    total_approved: int
    total_rejected: int
    total_pending: int
    subjects_count: int
    topics_count: int


class AdminDashboard(BaseModel):
    """Full admin dashboard payload."""
    total_subjects: int
    total_topics: int
    total_questions: int
    total_vetted: int
    total_approved: int
    total_rejected: int
    total_pending: int
    total_users: int
    total_teachers: int
    total_vetters: int
    total_admins: int
    vetters: List[VetterBreakdown]
    users: List[UserStats]


class AdminTopicSummary(BaseModel):
    id: str
    name: str
    description: Optional[str]
    order_index: int
    has_syllabus: bool
    total_questions: int
    total_approved: int
    total_rejected: int
    total_pending: int


class AdminSubjectSummary(BaseModel):
    id: str
    name: str
    code: str
    description: Optional[str]
    teacher_id: str
    teacher_name: Optional[str]
    teacher_email: Optional[str]
    total_topics: int
    total_questions: int
    total_approved: int
    total_rejected: int
    total_pending: int
    syllabus_coverage: int
    created_at: datetime


class AdminSubjectDetail(AdminSubjectSummary):
    topics: List[AdminTopicSummary]


class AdminTeacherProgressSummary(BaseModel):
    teacher_id: str
    username: str
    full_name: Optional[str]
    email: str
    subjects_count: int
    total_topics: int
    total_questions: int
    total_approved: int
    total_rejected: int
    total_pending: int
    subject_search_text: str


class AdminVetterProgressSummary(BaseModel):
    user_id: str
    username: str
    full_name: Optional[str]
    email: str
    total_vetted: int
    total_approved: int
    total_rejected: int
    subjects_count: int
    topics_count: int


class AdminQuestionSummary(BaseModel):
    id: str
    document_id: Optional[str]
    session_id: Optional[str]
    question_text: str
    correct_answer: Optional[str]
    options: Optional[List[str]]
    question_type: Optional[str]
    difficulty_level: Optional[str]
    marks: Optional[int]
    bloom_taxonomy_level: Optional[str]
    vetting_status: str
    vetted_by: Optional[str]
    vetted_at: Optional[datetime]
    generated_at: datetime
    explanation: Optional[str]
    answerability_score: Optional[float]
    specificity_score: Optional[float]
    generation_confidence: Optional[float]
    novelty_score: Optional[float]
    max_similarity: Optional[float]
    similarity_source: Optional[str]
    generation_attempt_count: int
    used_reference_materials: bool
    generation_status: str
    discard_reason: Optional[str]
    replaced_by_id: Optional[str]
    replaces_id: Optional[str]
    version_number: int
    is_latest: bool
    is_archived: bool
    subject_id: Optional[str]
    subject_name: Optional[str]
    topic_id: Optional[str]
    topic_name: Optional[str]
    learning_outcome_id: Optional[str]
    vetting_notes: Optional[str]
    provider_key: str


class AdminQuestionFeedResponse(BaseModel):
    questions: List[AdminQuestionSummary]
    total_count: int
    next_cursor: Optional[str]
    has_more: bool


class AdminQuestionExportField(BaseModel):
    key: str
    label: str
    group: str
    description: str
    selected_by_default: bool


class AdminQuestionExportColumn(BaseModel):
    key: str
    label: str


class AdminQuestionExportPreviewResponse(BaseModel):
    available_fields: List[AdminQuestionExportField]
    selected_fields: List[AdminQuestionExportColumn]
    preview_count: int
    rows: List[Dict[str, str]]


class AdminUserSummary(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_approved: bool
    is_superuser: bool
    can_manage_groups: bool
    can_generate: bool
    can_vet: bool
    approved_at: Optional[datetime]
    created_at: Optional[datetime]
    last_login_at: Optional[datetime]


class AdminUserCreateRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None
    security_question: str
    security_answer: str
    role: str = "teacher"
    is_active: bool = True
    can_manage_groups: Optional[bool] = None
    can_generate: Optional[bool] = None
    can_vet: Optional[bool] = None


class AdminUserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    can_manage_groups: Optional[bool] = None
    can_generate: Optional[bool] = None
    can_vet: Optional[bool] = None


class AdminUserPasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminUserDeleteRequest(BaseModel):
    delete_subjects: bool = False
    delete_questions: bool = False
    delete_vetting_data: bool = False


class AdminUserDeleteResponse(BaseModel):
    message: str
    deleted_subjects: int = 0
    deleted_questions: int = 0
    deleted_vetting_logs: int = 0
    deleted_vetting_progress: int = 0

class AdminBulkApproveUsersRequest(BaseModel):
    user_ids: List[str] = Field(default_factory=list, min_length=1, max_length=500)

class AdminBulkApproveUsersResponse(BaseModel):
    approved_users: List[AdminUserSummary]
    approved_count: int


class AdminNotificationSummary(BaseModel):
    id: str
    notification_type: str
    title: str
    message: str
    target_user_id: Optional[str]
    target_user_email: Optional[str]
    target_username: Optional[str]
    action_url: Optional[str]
    action_label: Optional[str]
    payload: Optional[Dict[str, Any]]
    is_read: bool
    created_at: Optional[datetime]


class AdminNotificationListResponse(BaseModel):
    notifications: List[AdminNotificationSummary]
    unread_count: int


# ============== Helpers ==============


async def _get_all_users() -> dict:
    """Fetch all users from the auth (SQLite) database and return a dict keyed by id."""
    async with AuthSessionLocal() as auth_session:
        result = await auth_session.execute(select(User))
        users = result.scalars().all()
        return {
            u.id: {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
            }
            for u in users
        }


async def _build_admin_subject_summaries(
    db: AsyncSession,
    users_map: dict,
    teacher_id: Optional[str] = None,
) -> List[AdminSubjectSummary]:
    subject_query = select(Subject)
    if teacher_id:
        subject_query = subject_query.where(Subject.user_id == teacher_id)
    subject_query = subject_query.order_by(Subject.name.asc())

    result = await db.execute(subject_query)
    subjects = result.scalars().all()

    subject_ids = [subject.id for subject in subjects]
    topic_count_map = {}
    subject_stats_map = {}

    if subject_ids:
        topic_counts = await db.execute(
            select(Topic.subject_id, func.count(Topic.id).label("total_topics"))
            .where(Topic.subject_id.in_(subject_ids))
            .group_by(Topic.subject_id)
        )
        topic_count_map = {row.subject_id: int(row.total_topics or 0) for row in topic_counts.all()}

        subject_stats = await db.execute(
            select(Question.subject_id, *_question_count_columns())
            .where(
                Question.subject_id.in_(subject_ids),
                *_live_question_filters(),
            )
            .group_by(Question.subject_id)
        )
        subject_stats_map = {
            row.subject_id: {
                "total_questions": int(row.total_questions or 0),
                "total_approved": int(row.total_approved or 0),
                "total_rejected": int(row.total_rejected or 0),
                "total_pending": int(row.total_pending or 0),
            }
            for row in subject_stats.all()
        }

    return [
        AdminSubjectSummary(
            id=subject.id,
            name=subject.name,
            code=subject.code,
            description=subject.description,
            teacher_id=subject.user_id,
            teacher_name=users_map.get(subject.user_id, {}).get("full_name") or users_map.get(subject.user_id, {}).get("username"),
            teacher_email=users_map.get(subject.user_id, {}).get("email"),
            total_topics=topic_count_map.get(subject.id, 0),
            total_questions=subject_stats_map.get(subject.id, {}).get("total_questions", 0),
            total_approved=subject_stats_map.get(subject.id, {}).get("total_approved", 0),
            total_rejected=subject_stats_map.get(subject.id, {}).get("total_rejected", 0),
            total_pending=subject_stats_map.get(subject.id, {}).get("total_pending", 0),
            syllabus_coverage=subject.syllabus_coverage,
            created_at=subject.created_at,
        )
        for subject in subjects
    ]


def _question_count_columns():
    return (
        func.count(Question.id).label("total_questions"),
        func.count(case((Question.vetting_status == "approved", 1))).label("total_approved"),
        func.count(case((Question.vetting_status == "rejected", 1))).label("total_rejected"),
        func.count(case((Question.vetting_status == "pending", 1))).label("total_pending"),
    )


def _live_question_filters():
    return (
        Question.generation_status == "accepted",
        Question.is_archived == False,
        Question.is_latest == True,
    )


def _managed_live_question_filters():
    return (*_live_question_filters(), Question.subject_id.isnot(None))


async def _get_user_assignment_count_maps(db: AsyncSession) -> tuple[Dict[str, int], Dict[str, int]]:
    user_subject_q = (
        select(
            Subject.user_id,
            func.count(distinct(Subject.id)).label("subjects_count"),
        )
        .where(Subject.user_id.isnot(None))
        .group_by(Subject.user_id)
    )
    user_subject_rows = (await db.execute(user_subject_q)).all()
    user_subject_map = {
        str(row.user_id): int(row.subjects_count or 0)
        for row in user_subject_rows
        if row.user_id
    }

    user_topic_q = (
        select(
            Subject.user_id,
            func.count(distinct(Topic.id)).label("topics_count"),
        )
        .select_from(Subject)
        .outerjoin(Topic, Topic.subject_id == Subject.id)
        .where(Subject.user_id.isnot(None))
        .group_by(Subject.user_id)
    )
    user_topic_rows = (await db.execute(user_topic_q)).all()
    user_topic_map = {
        str(row.user_id): int(row.topics_count or 0)
        for row in user_topic_rows
        if row.user_id
    }

    return user_subject_map, user_topic_map


async def _get_subject_owner_question_stats_map(db: AsyncSession) -> Dict[str, Dict[str, int]]:
    owner_question_stats_q = (
        select(
            Subject.user_id,
            *_question_count_columns(),
        )
        .select_from(Subject)
        .outerjoin(
            Question,
            and_(Question.subject_id == Subject.id, *_live_question_filters()),
        )
        .where(Subject.user_id.isnot(None))
        .group_by(Subject.user_id)
    )
    owner_question_rows = (await db.execute(owner_question_stats_q)).all()
    return {
        str(row.user_id): {
            "total_questions": int(row.total_questions or 0),
            "total_approved": int(row.total_approved or 0),
            "total_rejected": int(row.total_rejected or 0),
            "total_pending": int(row.total_pending or 0),
        }
        for row in owner_question_rows
        if row.user_id
    }


async def _get_subject_owner_search_text_map(db: AsyncSession) -> Dict[str, str]:
    subject_rows = (
        await db.execute(
            select(Subject.user_id, Subject.name, Subject.code)
            .where(Subject.user_id.isnot(None))
            .order_by(Subject.created_at.desc())
        )
    ).all()

    search_parts_by_user: Dict[str, List[str]] = {}
    for user_id, subject_name, subject_code in subject_rows:
        if not user_id:
            continue
        user_key = str(user_id)
        search_parts_by_user.setdefault(user_key, []).append(
            " ".join(part for part in [subject_name or "", subject_code or ""] if part).strip()
        )

    return {
        user_id: " ".join(part for part in parts if part)
        for user_id, parts in search_parts_by_user.items()
    }


async def _get_user_vetting_stats_map(db: AsyncSession) -> Dict[str, Dict[str, int]]:
    user_vet_q = (
        select(
            Question.vetted_by,
            func.count(Question.id).label("total_vetted"),
            func.count(case((Question.vetting_status == "approved", 1))).label("approved"),
            func.count(case((Question.vetting_status == "rejected", 1))).label("rejected"),
        )
        .where(*_managed_live_question_filters(), Question.vetted_by.isnot(None))
        .group_by(Question.vetted_by)
    )
    user_vet_rows = (await db.execute(user_vet_q)).all()
    return {
        str(row.vetted_by): {
            "total_vetted": int(row.total_vetted or 0),
            "approved": int(row.approved or 0),
            "rejected": int(row.rejected or 0),
        }
        for row in user_vet_rows
        if row.vetted_by
    }


def _normalize_admin_question_status(vetting_status: Optional[str]) -> Optional[str]:
    normalized = (vetting_status or "").strip().lower()
    if not normalized or normalized in {"all", "any"}:
        return None
    if normalized not in {"pending", "approved", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid vetting_status. Use pending, approved, rejected, or all.",
        )
    return normalized


def _normalize_admin_question_choice(
    value: Optional[str],
    *,
    allowed: set[str],
    field_name: str,
    default: Optional[str] = None,
) -> Optional[str]:
    normalized = (value or "").strip().lower()
    if not normalized:
        return default
    if normalized in {"all", "any"}:
        return None
    if normalized not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {field_name}",
        )
    return normalized


def _apply_nullable_text_filter(query, column, value: Optional[str]):
    if not value:
        return query
    if value == "unspecified":
        return query.where(or_(column.is_(None), column == ""))
    return query.where(func.lower(column) == value)


async def _normalize_admin_question_filters(
    db: AsyncSession,
    *,
    group_id: Optional[str],
    subject_id: Optional[str],
    subject_scope: Optional[str],
    topic_id: Optional[str],
    vetting_status: Optional[str],
    question_type: Optional[str],
    difficulty_level: Optional[str],
    bloom_taxonomy_level: Optional[str],
    generation_status: Optional[str],
    reference_mode: Optional[str],
    provider_key: Optional[str],
    version_scope: Optional[str],
    archived_state: Optional[str],
) -> Dict[str, Any]:
    normalized_status = _normalize_admin_question_status(vetting_status)
    normalized_question_type = _normalize_admin_question_choice(
        question_type,
        allowed={"mcq", "short_answer", "long_answer", "essay", "true_false", "unspecified"},
        field_name="question_type",
    )
    normalized_difficulty = _normalize_admin_question_choice(
        difficulty_level,
        allowed={"easy", "medium", "hard", "unspecified"},
        field_name="difficulty_level",
    )
    normalized_bloom = _normalize_admin_question_choice(
        bloom_taxonomy_level,
        allowed={"remember", "understand", "apply", "analyze", "evaluate", "create", "unspecified"},
        field_name="bloom_taxonomy_level",
    )
    normalized_generation_status = _normalize_admin_question_choice(
        generation_status,
        allowed={"accepted", "discarded"},
        field_name="generation_status",
    )
    normalized_reference_mode = _normalize_admin_question_choice(
        reference_mode,
        allowed={"with_reference", "without_reference"},
        field_name="reference_mode",
        default=None,
    )
    normalized_provider_key = (provider_key or "").strip().lower() or None
    normalized_group_id = (group_id or "").strip() or None
    normalized_subject_scope = _normalize_admin_question_choice(
        subject_scope,
        allowed={"all", "assigned", "orphaned"},
        field_name="subject_scope",
        default="all",
    )
    normalized_version_scope = _normalize_admin_question_choice(
        version_scope,
        allowed={"latest", "all"},
        field_name="version_scope",
        default="latest",
    )
    normalized_archived_state = _normalize_admin_question_choice(
        archived_state,
        allowed={"active", "archived"},
        field_name="archived_state",
        default="active",
    )

    if normalized_subject_scope == "orphaned":
        if normalized_group_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Group filtering is unavailable for orphaned questions",
            )
        if topic_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Topic filtering is unavailable for orphaned questions",
            )
        subject_id = None

    group_subject_ids: Optional[List[str]] = None
    if normalized_group_id:
        group_subject_ids = await get_subject_ids_for_group(db, normalized_group_id)
        if subject_id and subject_id not in group_subject_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Selected subject does not belong to the selected group",
            )

    if topic_id:
        topic_subject_id = await _resolve_topic_subject_id(db, topic_id)
        if subject_id and topic_subject_id != subject_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Selected topic does not belong to the selected subject",
            )
        if group_subject_ids is not None and topic_subject_id not in group_subject_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Selected topic does not belong to the selected group",
            )
        subject_id = subject_id or topic_subject_id

    return {
        "group_id": normalized_group_id,
        "normalized_group_subject_ids": group_subject_ids,
        "subject_id": subject_id,
        "normalized_subject_scope": normalized_subject_scope,
        "topic_id": topic_id,
        "normalized_status": normalized_status,
        "normalized_question_type": normalized_question_type,
        "normalized_difficulty": normalized_difficulty,
        "normalized_bloom": normalized_bloom,
        "normalized_generation_status": normalized_generation_status,
        "normalized_reference_mode": normalized_reference_mode,
        "normalized_provider_key": normalized_provider_key,
        "normalized_version_scope": normalized_version_scope,
        "normalized_archived_state": normalized_archived_state,
    }


def _build_admin_question_base_query(*columns):
    return (
        select(*columns)
        .outerjoin(Subject, Subject.id == Question.subject_id)
        .outerjoin(Topic, Topic.id == Question.topic_id)
    )


def _apply_admin_question_filters(
    query,
    *,
    group_id: Optional[str],
    normalized_group_subject_ids: Optional[List[str]],
    subject_id: Optional[str],
    normalized_subject_scope: Optional[str],
    topic_id: Optional[str],
    normalized_status: Optional[str],
    normalized_question_type: Optional[str],
    normalized_difficulty: Optional[str],
    normalized_bloom: Optional[str],
    normalized_generation_status: Optional[str],
    normalized_reference_mode: Optional[str],
    normalized_provider_key: Optional[str],
    normalized_version_scope: Optional[str],
    normalized_archived_state: Optional[str],
):
    if normalized_subject_scope == "assigned":
        query = query.where(Question.subject_id.isnot(None))
    elif normalized_subject_scope == "orphaned":
        query = query.where(Question.subject_id.is_(None))

    if group_id:
        if normalized_group_subject_ids:
            query = query.where(Question.subject_id.in_(normalized_group_subject_ids))
        else:
            query = query.where(false())

    if subject_id:
        query = query.where(Question.subject_id == subject_id)
    if topic_id:
        query = query.where(Question.topic_id == topic_id)
    if normalized_status:
        query = query.where(Question.vetting_status == normalized_status)
    if normalized_version_scope == "latest":
        query = query.where(Question.is_latest == True)
    if normalized_archived_state == "active":
        query = query.where(Question.is_archived == False)
    elif normalized_archived_state == "archived":
        query = query.where(Question.is_archived == True)
    if normalized_generation_status:
        query = query.where(Question.generation_status == normalized_generation_status)
    if normalized_reference_mode == "with_reference":
        query = query.where(Question.used_reference_materials == True)
    elif normalized_reference_mode == "without_reference":
        query = query.where(Question.used_reference_materials == False)
    if normalized_provider_key:
        query = query.where(func.lower(_provider_key_expr()) == normalized_provider_key)
    if normalized_question_type:
        query = _apply_nullable_text_filter(query, Question.question_type, normalized_question_type)
    if normalized_difficulty:
        query = _apply_nullable_text_filter(query, Question.difficulty_level, normalized_difficulty)
    if normalized_bloom:
        query = _apply_nullable_text_filter(query, Question.bloom_taxonomy_level, normalized_bloom)
    return query


def _admin_question_export_fields(provider_expr):
    return [
        {
            "key": "question_text",
            "label": "Question",
            "group": "Core",
            "description": "Full question text",
            "selected_by_default": True,
            "expression": Question.question_text.label("question_text"),
        },
        {
            "key": "correct_answer",
            "label": "Correct Answer",
            "group": "Core",
            "description": "Stored answer value or MCQ answer label",
            "selected_by_default": True,
            "expression": Question.correct_answer.label("correct_answer"),
        },
        {
            "key": "answer_options",
            "label": "Answer Options",
            "group": "Core",
            "description": "MCQ options exported into a single cell",
            "selected_by_default": True,
            "expression": Question.options.label("answer_options"),
        },
        {
            "key": "subject_name",
            "label": "Subject",
            "group": "Core",
            "description": "Resolved subject name",
            "selected_by_default": True,
            "expression": Subject.name.label("subject_name"),
        },
        {
            "key": "topic_name",
            "label": "Topic",
            "group": "Core",
            "description": "Resolved topic name",
            "selected_by_default": True,
            "expression": Topic.name.label("topic_name"),
        },
        {
            "key": "difficulty_level",
            "label": "Difficulty",
            "group": "Core",
            "description": "Difficulty classification",
            "selected_by_default": True,
            "expression": Question.difficulty_level.label("difficulty_level"),
        },
        {
            "key": "question_type",
            "label": "Question Type",
            "group": "Core",
            "description": "MCQ, short answer, essay, and related types",
            "selected_by_default": False,
            "expression": Question.question_type.label("question_type"),
        },
        {
            "key": "marks",
            "label": "Marks",
            "group": "Core",
            "description": "Assigned marks for the question",
            "selected_by_default": False,
            "expression": Question.marks.label("marks"),
        },
        {
            "key": "bloom_taxonomy_level",
            "label": "Bloom Level",
            "group": "Core",
            "description": "Bloom taxonomy label",
            "selected_by_default": False,
            "expression": Question.bloom_taxonomy_level.label("bloom_taxonomy_level"),
        },
        {
            "key": "explanation",
            "label": "Explanation",
            "group": "Core",
            "description": "Stored answer explanation",
            "selected_by_default": False,
            "expression": Question.explanation.label("explanation"),
        },
        {
            "key": "learning_outcome_id",
            "label": "Learning Outcome",
            "group": "Core",
            "description": "Mapped learning outcome id",
            "selected_by_default": False,
            "expression": Question.learning_outcome_id.label("learning_outcome_id"),
        },
        {
            "key": "vetting_status",
            "label": "Review Status",
            "group": "Review",
            "description": "Pending, approved, or rejected",
            "selected_by_default": False,
            "expression": Question.vetting_status.label("vetting_status"),
        },
        {
            "key": "vetted_by",
            "label": "Vetted By",
            "group": "Review",
            "description": "Admin or vetter id/email stored on the record",
            "selected_by_default": False,
            "expression": Question.vetted_by.label("vetted_by"),
        },
        {
            "key": "vetted_at",
            "label": "Vetted At",
            "group": "Review",
            "description": "Review timestamp",
            "selected_by_default": False,
            "expression": Question.vetted_at.label("vetted_at"),
        },
        {
            "key": "vetting_notes",
            "label": "Vetting Notes",
            "group": "Review",
            "description": "Reviewer notes captured during vetting",
            "selected_by_default": False,
            "expression": Question.vetting_notes.label("vetting_notes"),
        },
        {
            "key": "generated_at",
            "label": "Generated At",
            "group": "Generation",
            "description": "Creation timestamp",
            "selected_by_default": False,
            "expression": Question.generated_at.label("generated_at"),
        },
        {
            "key": "generation_status",
            "label": "Generation Result",
            "group": "Generation",
            "description": "Accepted or discarded generation result",
            "selected_by_default": False,
            "expression": Question.generation_status.label("generation_status"),
        },
        {
            "key": "used_reference_materials",
            "label": "Used References",
            "group": "Generation",
            "description": "Whether references were used during generation",
            "selected_by_default": False,
            "expression": Question.used_reference_materials.label("used_reference_materials"),
        },
        {
            "key": "provider_key",
            "label": "Provider",
            "group": "Generation",
            "description": "Resolved provider key",
            "selected_by_default": False,
            "expression": provider_expr,
        },
        {
            "key": "generation_confidence",
            "label": "Confidence",
            "group": "Generation",
            "description": "Generation confidence score",
            "selected_by_default": False,
            "expression": Question.generation_confidence.label("generation_confidence"),
        },
        {
            "key": "answerability_score",
            "label": "Answerability",
            "group": "Generation",
            "description": "Answerability score",
            "selected_by_default": False,
            "expression": Question.answerability_score.label("answerability_score"),
        },
        {
            "key": "specificity_score",
            "label": "Specificity",
            "group": "Generation",
            "description": "Specificity score",
            "selected_by_default": False,
            "expression": Question.specificity_score.label("specificity_score"),
        },
        {
            "key": "novelty_score",
            "label": "Novelty",
            "group": "Generation",
            "description": "Novelty score",
            "selected_by_default": False,
            "expression": Question.novelty_score.label("novelty_score"),
        },
        {
            "key": "max_similarity",
            "label": "Max Similarity",
            "group": "Generation",
            "description": "Highest similarity detected",
            "selected_by_default": False,
            "expression": Question.max_similarity.label("max_similarity"),
        },
        {
            "key": "similarity_source",
            "label": "Similarity Source",
            "group": "Generation",
            "description": "Where the max similarity was found",
            "selected_by_default": False,
            "expression": Question.similarity_source.label("similarity_source"),
        },
        {
            "key": "generation_attempt_count",
            "label": "Generation Attempts",
            "group": "Generation",
            "description": "How many generation attempts were used",
            "selected_by_default": False,
            "expression": Question.generation_attempt_count.label("generation_attempt_count"),
        },
        {
            "key": "discard_reason",
            "label": "Discard Reason",
            "group": "Generation",
            "description": "Reason recorded for discarded questions",
            "selected_by_default": False,
            "expression": Question.discard_reason.label("discard_reason"),
        },
        {
            "key": "id",
            "label": "Question ID",
            "group": "Traceability",
            "description": "Primary question id",
            "selected_by_default": False,
            "expression": Question.id.label("id"),
        },
        {
            "key": "document_id",
            "label": "Document ID",
            "group": "Traceability",
            "description": "Source document id",
            "selected_by_default": False,
            "expression": Question.document_id.label("document_id"),
        },
        {
            "key": "session_id",
            "label": "Session ID",
            "group": "Traceability",
            "description": "Generation session id",
            "selected_by_default": False,
            "expression": Question.session_id.label("session_id"),
        },
        {
            "key": "subject_id",
            "label": "Subject ID",
            "group": "Traceability",
            "description": "Raw subject id",
            "selected_by_default": False,
            "expression": Question.subject_id.label("subject_id"),
        },
        {
            "key": "topic_id",
            "label": "Topic ID",
            "group": "Traceability",
            "description": "Raw topic id",
            "selected_by_default": False,
            "expression": Question.topic_id.label("topic_id"),
        },
        {
            "key": "replaced_by_id",
            "label": "Replaced By",
            "group": "Traceability",
            "description": "Successor question id",
            "selected_by_default": False,
            "expression": Question.replaced_by_id.label("replaced_by_id"),
        },
        {
            "key": "replaces_id",
            "label": "Replaces",
            "group": "Traceability",
            "description": "Predecessor question id",
            "selected_by_default": False,
            "expression": Question.replaces_id.label("replaces_id"),
        },
        {
            "key": "version_number",
            "label": "Version Number",
            "group": "Traceability",
            "description": "Stored version number",
            "selected_by_default": False,
            "expression": Question.version_number.label("version_number"),
        },
        {
            "key": "is_latest",
            "label": "Is Latest",
            "group": "Traceability",
            "description": "Whether this row is the current version",
            "selected_by_default": False,
            "expression": Question.is_latest.label("is_latest"),
        },
        {
            "key": "is_archived",
            "label": "Is Archived",
            "group": "Traceability",
            "description": "Archive flag",
            "selected_by_default": False,
            "expression": Question.is_archived.label("is_archived"),
        },
        {
            "key": "topic_tags",
            "label": "Topic Tags",
            "group": "Structured",
            "description": "Stored topic tags array",
            "selected_by_default": False,
            "expression": Question.topic_tags.label("topic_tags"),
        },
        {
            "key": "source_chunk_ids",
            "label": "Source Chunk IDs",
            "group": "Structured",
            "description": "Linked source chunk ids",
            "selected_by_default": False,
            "expression": Question.source_chunk_ids.label("source_chunk_ids"),
        },
        {
            "key": "course_outcome_mapping",
            "label": "Course Outcome Mapping",
            "group": "Structured",
            "description": "Stored course outcome mapping JSON",
            "selected_by_default": False,
            "expression": Question.course_outcome_mapping.label("course_outcome_mapping"),
        },
        {
            "key": "novelty_metadata",
            "label": "Novelty Metadata",
            "group": "Structured",
            "description": "Detailed novelty metadata JSON",
            "selected_by_default": False,
            "expression": Question.novelty_metadata.label("novelty_metadata"),
        },
        {
            "key": "generation_metadata",
            "label": "Generation Metadata",
            "group": "Structured",
            "description": "Stored generation metadata JSON",
            "selected_by_default": False,
            "expression": Question.generation_metadata.label("generation_metadata"),
        },
    ]


def _normalize_admin_question_export_fields(
    requested_fields: List[str],
    fields_by_key: Dict[str, Dict[str, Any]],
) -> List[str]:
    if not requested_fields:
        return [field_key for field_key in _ADMIN_QUESTION_EXPORT_DEFAULT_FIELDS if field_key in fields_by_key]

    normalized_fields: List[str] = []
    invalid_fields: List[str] = []
    for raw_field in requested_fields:
        field_key = (raw_field or "").strip()
        if not field_key:
            continue
        if field_key not in fields_by_key:
            invalid_fields.append(field_key)
            continue
        if field_key not in normalized_fields:
            normalized_fields.append(field_key)

    if invalid_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid export fields: {', '.join(invalid_fields)}",
        )

    if not normalized_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select at least one export field.",
        )

    return normalized_fields


def _serialize_admin_question_export_value(field_key: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if field_key == "answer_options" and isinstance(value, list):
        return "\n".join(str(item) for item in value)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _encode_admin_question_cursor(generated_at: datetime, question_id: str) -> str:
    payload = json.dumps(
        {
            "generated_at": generated_at.isoformat(),
            "question_id": question_id,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_admin_question_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
        generated_at = datetime.fromisoformat(payload["generated_at"])
        question_id = str(payload["question_id"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid cursor",
        ) from exc

    if not question_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid cursor",
        )

    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    return generated_at, question_id


async def _resolve_topic_subject_id(db: AsyncSession, topic_id: str) -> str:
    result = await db.execute(select(Topic.subject_id).where(Topic.id == topic_id))
    subject_id = result.scalar_one_or_none()
    if not subject_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    return subject_id


def _validate_role(role: str) -> str:
    normalized = (role or "").strip().lower()
    if normalized not in VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role")
    return normalized


def _validate_username(username: str) -> str:
    normalized = (username or "").strip().lower()
    if not re.match(r"^[a-zA-Z0-9_]{3,50}$", normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username must be 3-50 chars and contain only letters, numbers, underscores",
        )
    return normalized


def _resolve_permissions(role: str, payload: dict) -> dict[str, bool]:
    defaults = default_permissions_for_role(role)
    return {
        "can_manage_groups": payload.get("can_manage_groups", defaults["can_manage_groups"]),
        "can_generate": payload.get("can_generate", defaults["can_generate"]),
        "can_vet": payload.get("can_vet", defaults["can_vet"]),
    }


def _serialize_admin_notification(notification) -> AdminNotificationSummary:
    return AdminNotificationSummary(
        id=notification.id,
        notification_type=notification.notification_type,
        title=notification.title,
        message=notification.message,
        target_user_id=notification.target_user_id,
        target_user_email=notification.target_user_email,
        target_username=notification.target_username,
        action_url=notification.action_url,
        action_label=notification.action_label,
        payload=notification.payload,
        is_read=bool(notification.is_read),
        created_at=notification.created_at,
    )

def _serialize_admin_user(user: User) -> AdminUserSummary:
    return AdminUserSummary(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=bool(user.is_active),
        is_approved=bool(user.is_approved),
        is_superuser=bool(user.is_superuser),
        can_manage_groups=bool(user.can_manage_groups),
        can_generate=bool(user.can_generate),
        can_vet=bool(user.can_vet),
        approved_at=user.approved_at,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _count_rows(result) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


async def _delete_admin_user_data(
    db: AsyncSession,
    *,
    user_id: str,
    delete_subjects: bool,
    delete_questions: bool,
    delete_vetting_data: bool,
) -> dict[str, int]:
    counts = {
        "deleted_subjects": 0,
        "deleted_questions": 0,
        "deleted_vetting_logs": 0,
        "deleted_vetting_progress": 0,
    }

    subject_ids = [
        str(subject_id)
        for subject_id in (
            await db.execute(select(Subject.id).where(Subject.user_id == user_id))
        ).scalars().all()
    ]

    topic_ids: list[str] = []
    if subject_ids:
        topic_ids = [
            str(topic_id)
            for topic_id in (
                await db.execute(select(Topic.id).where(Topic.subject_id.in_(subject_ids)))
            ).scalars().all()
        ]

    question_ids: list[str] = []
    if delete_questions and (subject_ids or topic_ids):
        question_filters = []
        if subject_ids:
            question_filters.append(Question.subject_id.in_(subject_ids))
        if topic_ids:
            question_filters.append(Question.topic_id.in_(topic_ids))

        question_ids = [
            str(question_id)
            for question_id in (
                await db.execute(select(Question.id).where(or_(*question_filters)))
            ).scalars().all()
        ]
        if question_ids:
            question_vetting_log_ids = [
                str(log_id)
                for log_id in (
                    await db.execute(select(VettingLog.id).where(VettingLog.question_id.in_(question_ids)))
                ).scalars().all()
            ]
            training_pair_filters = [
                TrainingPair.chosen_question_id.in_(question_ids),
                TrainingPair.rejected_question_id.in_(question_ids),
            ]
            if question_vetting_log_ids:
                training_pair_filters.append(TrainingPair.vetting_log_id.in_(question_vetting_log_ids))

            await db.execute(delete(TrainingPair).where(or_(*training_pair_filters)))
            counts["deleted_questions"] = _count_rows(
                await db.execute(delete(Question).where(Question.id.in_(question_ids)))
            )

    if delete_vetting_data:
        user_vetting_log_ids = [
            str(log_id)
            for log_id in (
                await db.execute(select(VettingLog.id).where(VettingLog.vetter_id == user_id))
            ).scalars().all()
        ]
        if user_vetting_log_ids:
            await db.execute(delete(TrainingPair).where(TrainingPair.vetting_log_id.in_(user_vetting_log_ids)))

        counts["deleted_vetting_logs"] = _count_rows(
            await db.execute(delete(VettingLog).where(VettingLog.vetter_id == user_id))
        )
        counts["deleted_vetting_progress"] = _count_rows(
            await db.execute(delete(TeacherVettingProgress).where(TeacherVettingProgress.user_id == user_id))
        )

    if delete_subjects and subject_ids:
        document_filters = [Document.subject_id.in_(subject_ids)]
        if topic_ids:
            document_filters.append(Document.topic_id.in_(topic_ids))

        document_ids = [
            str(document_id)
            for document_id in (
                await db.execute(select(Document.id).where(or_(*document_filters)))
            ).scalars().all()
        ]

        generation_session_filters = [GenerationSession.subject_id.in_(subject_ids)]
        if topic_ids:
            generation_session_filters.append(GenerationSession.topic_id.in_(topic_ids))
        if document_ids:
            generation_session_filters.append(GenerationSession.document_id.in_(document_ids))
        await db.execute(delete(GenerationSession).where(or_(*generation_session_filters)))

        if document_ids:
            await db.execute(delete(Document).where(Document.id.in_(document_ids)))

        counts["deleted_subjects"] = _count_rows(
            await db.execute(delete(Subject).where(Subject.id.in_(subject_ids)))
        )

    return counts


# ============== Helpers ==============


def _provider_key_expr():
    """Extract provider_key from Question, preferring the direct column over JSONB."""
    base_url_expr = func.lower(func.coalesce(Question.generation_metadata["base_url"].astext, ""))
    inferred_from_base_url = case(
        (base_url_expr.like("%api.x.ai%"), literal("grok")),
        (base_url_expr.like("%api.deepseek.com%"), literal("deepseek")),
        (base_url_expr.like("%generativelanguage.googleapis.com%"), literal("gemini")),
        (base_url_expr.like("%localhost:11434%"), literal("ollama")),
        else_=literal("unknown"),
    )

    return func.coalesce(
        func.nullif(Question.provider_key, ""),
        func.nullif(Question.generation_metadata["provider_key"].astext, ""),
        func.nullif(Question.generation_metadata["provider"].astext, ""),
        func.nullif(Question.generation_metadata["llm_provider"].astext, ""),
        inferred_from_base_url,
        literal("unknown"),
    )


# ============== Endpoints ==============


@router.get("/dashboard", response_model=AdminDashboard)
async def get_admin_dashboard(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Return full admin dashboard statistics.
    Queries PostgreSQL for content stats and SQLite for user info.
    """
    # 1) Aggregate counts from PostgreSQL
    subject_count_q = select(func.count(Subject.id))
    topic_count_q = select(func.count(Topic.id))

    live_question_filters = _managed_live_question_filters()

    total_questions_q = select(func.count(Question.id)).where(*live_question_filters)
    vetted_q = select(func.count(Question.id)).where(
        *live_question_filters,
        Question.vetting_status.in_(["approved", "rejected"])
    )
    approved_q = select(func.count(Question.id)).where(
        *live_question_filters,
        Question.vetting_status == "approved"
    )
    rejected_q = select(func.count(Question.id)).where(
        *live_question_filters,
        Question.vetting_status == "rejected"
    )
    pending_q = select(func.count(Question.id)).where(
        *live_question_filters,
        Question.vetting_status == "pending",
    )

    (
        subject_count,
        topic_count,
        total_questions,
        total_vetted,
        total_approved,
        total_rejected,
        total_pending,
    ) = (
        (await db.execute(subject_count_q)).scalar() or 0,
        (await db.execute(topic_count_q)).scalar() or 0,
        (await db.execute(total_questions_q)).scalar() or 0,
        (await db.execute(vetted_q)).scalar() or 0,
        (await db.execute(approved_q)).scalar() or 0,
        (await db.execute(rejected_q)).scalar() or 0,
        (await db.execute(pending_q)).scalar() or 0,
    )

    # 2) Per-vetter breakdown (who vetted, how many approved/rejected)
    vetter_stats_q = (
        select(
            Question.vetted_by,
            func.count(Question.id).label("total_vetted"),
            func.count(case((Question.vetting_status == "approved", 1))).label("approved"),
            func.count(case((Question.vetting_status == "rejected", 1))).label("rejected"),
        )
        .where(*live_question_filters, Question.vetted_by.isnot(None))
        .group_by(Question.vetted_by)
    )
    vetter_rows = (await db.execute(vetter_stats_q)).all()

    # 3) Per-user generation stats via generation_sessions
    user_gen_q = (
        select(
            GenerationSession.user_id,
            func.sum(GenerationSession.questions_generated).label("total_generated"),
        )
        .group_by(GenerationSession.user_id)
    )
    user_gen_rows = (await db.execute(user_gen_q)).all()
    user_gen_map = {row.user_id: int(row.total_generated or 0) for row in user_gen_rows}

    # 4) Per-user subject and topic counts
    user_subject_q = (
        select(
            Subject.user_id,
            func.count(distinct(Subject.id)).label("subjects_count"),
        )
        .group_by(Subject.user_id)
    )
    user_subject_rows = (await db.execute(user_subject_q)).all()
    user_subject_map = {row.user_id: int(row.subjects_count or 0) for row in user_subject_rows}

    user_topic_q = (
        select(
            Subject.user_id,
            func.count(distinct(Topic.id)).label("topics_count"),
        )
        .select_from(Subject)
        .join(Topic, Topic.subject_id == Subject.id)
        .group_by(Subject.user_id)
    )
    user_topic_rows = (await db.execute(user_topic_q)).all()
    user_topic_map = {row.user_id: int(row.topics_count or 0) for row in user_topic_rows}

    # 5) Per-user vetting stats (questions they vetted)
    user_vet_q = (
        select(
            Question.vetted_by,
            func.count(Question.id).label("total_vetted"),
            func.count(case((Question.vetting_status == "approved", 1))).label("approved"),
            func.count(case((Question.vetting_status == "rejected", 1))).label("rejected"),
        )
        .where(*live_question_filters, Question.vetted_by.isnot(None))
        .group_by(Question.vetted_by)
    )
    user_vet_rows = (await db.execute(user_vet_q)).all()
    user_vet_map = {
        row.vetted_by: {
            "total_vetted": int(row.total_vetted or 0),
            "approved": int(row.approved or 0),
            "rejected": int(row.rejected or 0),
        }
        for row in user_vet_rows
    }

    # 6) Per-user pending count (questions they generated that are still pending)
    user_pending_q = (
        select(
            GenerationSession.user_id,
            func.count(Question.id).label("pending_count"),
        )
        .select_from(Question)
        .join(GenerationSession, Question.session_id == GenerationSession.id, isouter=True)
        .where(
            *live_question_filters,
            Question.vetting_status == "pending",
        )
        .group_by(GenerationSession.user_id)
    )
    user_pending_rows = (await db.execute(user_pending_q)).all()
    user_pending_map = {row.user_id: int(row.pending_count or 0) for row in user_pending_rows}

    # 7) Fetch all users from auth DB
    users_map = await _get_all_users()

    # Build vetter breakdown list
    vetters_list: List[VetterBreakdown] = []
    for row in vetter_rows:
        u = users_map.get(row.vetted_by, {})
        vetters_list.append(
            VetterBreakdown(
                user_id=row.vetted_by,
                username=u.get("username", "unknown"),
                full_name=u.get("full_name"),
                email=u.get("email", ""),
                total_vetted=int(row.total_vetted or 0),
                total_approved=int(row.approved or 0),
                total_rejected=int(row.rejected or 0),
            )
        )
    vetters_list.sort(key=lambda v: v.total_vetted, reverse=True)

    # Build per-user stats list
    users_list: List[UserStats] = []
    for uid, u in users_map.items():
        vet_info = user_vet_map.get(uid, {"total_vetted": 0, "approved": 0, "rejected": 0})
        users_list.append(
            UserStats(
                user_id=uid,
                username=u["username"],
                full_name=u.get("full_name"),
                email=u["email"],
                role=u["role"],
                total_generated=user_gen_map.get(uid, 0),
                total_vetted=vet_info["total_vetted"],
                total_approved=vet_info["approved"],
                total_rejected=vet_info["rejected"],
                total_pending=user_pending_map.get(uid, 0),
                subjects_count=user_subject_map.get(uid, 0),
                topics_count=user_topic_map.get(uid, 0),
            )
        )
    users_list.sort(key=lambda u: u.total_generated, reverse=True)

    # Role counts
    total_teachers = sum(1 for u in users_map.values() if u["role"] == "teacher")
    total_vetters = sum(1 for u in users_map.values() if u["role"] == "vetter")
    total_admins = sum(1 for u in users_map.values() if u["role"] == "admin")

    return AdminDashboard(
        total_subjects=subject_count,
        total_topics=topic_count,
        total_questions=total_questions,
        total_vetted=total_vetted,
        total_approved=total_approved,
        total_rejected=total_rejected,
        total_pending=total_pending,
        total_users=len(users_map),
        total_teachers=total_teachers,
        total_vetters=total_vetters,
        total_admins=total_admins,
        vetters=vetters_list,
        users=users_list,
    )


@router.get("/teachers/progress", response_model=List[AdminTeacherProgressSummary])
async def list_admin_teacher_progress(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    users_map = await _get_all_users()
    subject_count_map, topic_count_map = await _get_user_assignment_count_maps(db)
    question_stats_map = await _get_subject_owner_question_stats_map(db)
    search_text_map = await _get_subject_owner_search_text_map(db)

    teacher_rows: List[AdminTeacherProgressSummary] = []
    for user_id, user_info in users_map.items():
        if user_info.get("role") != "teacher":
            continue
        question_stats = question_stats_map.get(
            user_id,
            {
                "total_questions": 0,
                "total_approved": 0,
                "total_rejected": 0,
                "total_pending": 0,
            },
        )
        teacher_rows.append(
            AdminTeacherProgressSummary(
                teacher_id=user_id,
                username=user_info.get("username", "unknown"),
                full_name=user_info.get("full_name"),
                email=user_info.get("email", ""),
                subjects_count=int(subject_count_map.get(user_id, 0) or 0),
                total_topics=int(topic_count_map.get(user_id, 0) or 0),
                total_questions=int(question_stats["total_questions"] or 0),
                total_approved=int(question_stats["total_approved"] or 0),
                total_rejected=int(question_stats["total_rejected"] or 0),
                total_pending=int(question_stats["total_pending"] or 0),
                subject_search_text=search_text_map.get(user_id, ""),
            )
        )

    teacher_rows.sort(
        key=lambda row: (row.total_questions, row.total_pending, row.subjects_count),
        reverse=True,
    )
    return teacher_rows


@router.get("/vetters/progress", response_model=List[AdminVetterProgressSummary])
async def list_admin_vetter_progress(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    users_map = await _get_all_users()
    subject_count_map, topic_count_map = await _get_user_assignment_count_maps(db)
    vetting_stats_map = await _get_user_vetting_stats_map(db)

    vetter_rows: List[AdminVetterProgressSummary] = []
    for user_id, user_info in users_map.items():
        if user_info.get("role") != "vetter":
            continue
        vetting_stats = vetting_stats_map.get(
            user_id,
            {
                "total_vetted": 0,
                "approved": 0,
                "rejected": 0,
            },
        )
        vetter_rows.append(
            AdminVetterProgressSummary(
                user_id=user_id,
                username=user_info.get("username", "unknown"),
                full_name=user_info.get("full_name"),
                email=user_info.get("email", ""),
                total_vetted=int(vetting_stats["total_vetted"] or 0),
                total_approved=int(vetting_stats["approved"] or 0),
                total_rejected=int(vetting_stats["rejected"] or 0),
                subjects_count=int(subject_count_map.get(user_id, 0) or 0),
                topics_count=int(topic_count_map.get(user_id, 0) or 0),
            )
        )

    vetter_rows.sort(
        key=lambda row: (row.total_vetted, row.total_approved, row.subjects_count),
        reverse=True,
    )
    return vetter_rows


@router.get("/subjects", response_model=List[AdminSubjectSummary])
async def list_admin_subjects(
    teacher_id: Optional[str] = Query(None, description="Filter subjects by teacher/user ID"),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    users_map = await _get_all_users()
    return await _build_admin_subject_summaries(db, users_map, teacher_id=teacher_id)


@router.get("/subjects/{subject_id}", response_model=AdminSubjectDetail)
async def get_admin_subject(
    subject_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.topics))
        .where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )

    users_map = await _get_all_users()
    topics = sorted(subject.topics, key=lambda item: item.order_index)
    topic_ids = [topic.id for topic in topics]

    subject_stats_result = await db.execute(
        select(*_question_count_columns())
        .where(
            Question.subject_id == subject.id,
            *_live_question_filters(),
        )
    )
    subject_stats_row = subject_stats_result.one()

    topic_stats_map = {}
    if topic_ids:
        topic_stats_result = await db.execute(
            select(Question.topic_id, *_question_count_columns())
            .where(
                Question.topic_id.in_(topic_ids),
                *_live_question_filters(),
            )
            .group_by(Question.topic_id)
        )
        topic_stats_map = {
            row.topic_id: {
                "total_questions": int(row.total_questions or 0),
                "total_approved": int(row.total_approved or 0),
                "total_rejected": int(row.total_rejected or 0),
                "total_pending": int(row.total_pending or 0),
            }
            for row in topic_stats_result.all()
        }

    return AdminSubjectDetail(
        id=subject.id,
        name=subject.name,
        code=subject.code,
        description=subject.description,
        teacher_id=subject.user_id,
        teacher_name=users_map.get(subject.user_id, {}).get("full_name") or users_map.get(subject.user_id, {}).get("username"),
        teacher_email=users_map.get(subject.user_id, {}).get("email"),
        total_topics=len(topics),
        total_questions=int(subject_stats_row.total_questions or 0),
        total_approved=int(subject_stats_row.total_approved or 0),
        total_rejected=int(subject_stats_row.total_rejected or 0),
        total_pending=int(subject_stats_row.total_pending or 0),
        syllabus_coverage=subject.syllabus_coverage,
        created_at=subject.created_at,
        topics=[
            AdminTopicSummary(
                id=topic.id,
                name=topic.name,
                description=topic.description,
                order_index=topic.order_index,
                has_syllabus=topic.has_syllabus,
                total_questions=topic_stats_map.get(topic.id, {}).get("total_questions", 0),
                total_approved=topic_stats_map.get(topic.id, {}).get("total_approved", 0),
                total_rejected=topic_stats_map.get(topic.id, {}).get("total_rejected", 0),
                total_pending=topic_stats_map.get(topic.id, {}).get("total_pending", 0),
            )
            for topic in topics
        ],
    )


@router.get("/questions", response_model=AdminQuestionFeedResponse)
async def list_admin_questions(
    group_id: Optional[str] = Query(None, description="Filter by group ID, including nested descendant groups"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    subject_scope: Optional[str] = Query(None, description="Filter by all, assigned, or orphaned subject linkage"),
    topic_id: Optional[str] = Query(None, description="Filter by topic ID"),
    vetting_status: Optional[str] = Query(None, description="Filter by pending, approved, rejected, or all"),
    question_type: Optional[str] = Query(None, description="Filter by question type"),
    difficulty_level: Optional[str] = Query(None, description="Filter by difficulty or unspecified"),
    bloom_taxonomy_level: Optional[str] = Query(None, description="Filter by Bloom level or unspecified"),
    generation_status: Optional[str] = Query(None, description="Filter by generation status accepted, discarded, or all"),
    reference_mode: str = Query("all", description="Filter by with_reference, without_reference, or all"),
    provider_key: Optional[str] = Query(None, description="Filter by AI provider key"),
    version_scope: str = Query("latest", description="Filter by latest or all versions"),
    archived_state: str = Query("active", description="Filter by active, archived, or all"),
    cursor: Optional[str] = Query(None, description="Opaque cursor from the previous admin questions response"),
    limit: int = Query(
        _ADMIN_QUESTION_FEED_DEFAULT_LIMIT,
        ge=1,
        le=_ADMIN_QUESTION_FEED_MAX_LIMIT,
        description="Batch size for the admin questions feed",
    ),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Stream admin questions using keyset pagination to avoid expensive counts and offsets."""
    normalized_filters = await _normalize_admin_question_filters(
        db,
        group_id=group_id,
        subject_id=subject_id,
        subject_scope=subject_scope,
        topic_id=topic_id,
        vetting_status=vetting_status,
        question_type=question_type,
        difficulty_level=difficulty_level,
        bloom_taxonomy_level=bloom_taxonomy_level,
        generation_status=generation_status,
        reference_mode=reference_mode,
        provider_key=provider_key,
        version_scope=version_scope,
        archived_state=archived_state,
    )

    cursor_generated_at: Optional[datetime] = None
    cursor_question_id: Optional[str] = None
    if cursor:
        cursor_generated_at, cursor_question_id = _decode_admin_question_cursor(cursor)

    provider_expr = _provider_key_expr().label("provider_key")

    count_query = _build_admin_question_base_query(func.count(Question.id))
    count_query = _apply_admin_question_filters(count_query, **normalized_filters)

    total_count = int((await db.execute(count_query)).scalar() or 0)

    query = _build_admin_question_base_query(
        Question.id,
        Question.document_id,
        Question.session_id,
        Question.question_text,
        Question.correct_answer,
        Question.options,
        Question.question_type,
        Question.difficulty_level,
        Question.marks,
        Question.bloom_taxonomy_level,
        Question.vetting_status,
        Question.vetted_by,
        Question.vetted_at,
        Question.generated_at,
        Question.explanation,
        Question.answerability_score,
        Question.specificity_score,
        Question.generation_confidence,
        Question.novelty_score,
        Question.max_similarity,
        Question.similarity_source,
        Question.generation_attempt_count,
        Question.used_reference_materials,
        Question.generation_status,
        Question.discard_reason,
        Question.replaced_by_id,
        Question.replaces_id,
        Question.version_number,
        Question.is_latest,
        Question.is_archived,
        Question.subject_id,
        Subject.name.label("subject_name"),
        Question.topic_id,
        Topic.name.label("topic_name"),
        Question.learning_outcome_id,
        Question.vetting_notes,
        provider_expr,
    )
    query = _apply_admin_question_filters(query, **normalized_filters)
    if cursor_generated_at and cursor_question_id:
        query = query.where(
            or_(
                Question.generated_at < cursor_generated_at,
                and_(
                    Question.generated_at == cursor_generated_at,
                    Question.id < cursor_question_id,
                ),
            )
        )

    result = await db.execute(
        query
        .order_by(Question.generated_at.desc(), Question.id.desc())
        .limit(limit + 1)
    )
    rows = result.all()
    visible_rows = rows[:limit]
    has_more = len(rows) > limit

    vetted_by_ids = {
        row.vetted_by
        for row in visible_rows
        if row.vetted_by
    }
    users_map = await _get_all_users() if vetted_by_ids else {}

    next_cursor = None
    if has_more and visible_rows:
        last_row = visible_rows[-1]
        next_cursor = _encode_admin_question_cursor(last_row.generated_at, last_row.id)

    return AdminQuestionFeedResponse(
        questions=[
            AdminQuestionSummary(
                id=row.id,
                document_id=row.document_id,
                session_id=row.session_id,
                question_text=row.question_text,
                correct_answer=row.correct_answer,
                options=row.options,
                question_type=row.question_type,
                difficulty_level=row.difficulty_level,
                marks=row.marks,
                bloom_taxonomy_level=row.bloom_taxonomy_level,
                vetting_status=row.vetting_status,
                vetted_by=(users_map.get(row.vetted_by, {}).get("full_name") or users_map.get(row.vetted_by, {}).get("username") or "Unknown vetter"),
                vetted_at=row.vetted_at,
                generated_at=row.generated_at,
                explanation=row.explanation,
                answerability_score=row.answerability_score,
                specificity_score=row.specificity_score,
                generation_confidence=row.generation_confidence,
                novelty_score=row.novelty_score,
                max_similarity=row.max_similarity,
                similarity_source=row.similarity_source,
                generation_attempt_count=int(row.generation_attempt_count or 0),
                used_reference_materials=bool(row.used_reference_materials),
                generation_status=row.generation_status,
                discard_reason=row.discard_reason,
                replaced_by_id=row.replaced_by_id,
                replaces_id=row.replaces_id,
                version_number=int(row.version_number or 1),
                is_latest=bool(row.is_latest),
                is_archived=bool(row.is_archived),
                subject_id=row.subject_id,
                subject_name=row.subject_name,
                topic_id=row.topic_id,
                topic_name=row.topic_name,
                learning_outcome_id=row.learning_outcome_id,
                vetting_notes=row.vetting_notes,
                provider_key=row.provider_key,
            )
            for row in visible_rows
        ],
        total_count=total_count,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/questions/export/preview", response_model=AdminQuestionExportPreviewResponse)
async def preview_admin_question_export(
    group_id: Optional[str] = Query(None, description="Filter by group ID, including nested descendant groups"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    topic_id: Optional[str] = Query(None, description="Filter by topic ID"),
    vetting_status: Optional[str] = Query(None, description="Filter by pending, approved, rejected, or all"),
    question_type: Optional[str] = Query(None, description="Filter by question type"),
    difficulty_level: Optional[str] = Query(None, description="Filter by difficulty or unspecified"),
    bloom_taxonomy_level: Optional[str] = Query(None, description="Filter by Bloom level or unspecified"),
    generation_status: Optional[str] = Query(None, description="Filter by generation status accepted, discarded, or all"),
    reference_mode: str = Query("all", description="Filter by with_reference, without_reference, or all"),
    provider_key: Optional[str] = Query(None, description="Filter by AI provider key"),
    version_scope: str = Query("latest", description="Filter by latest or all versions"),
    archived_state: str = Query("active", description="Filter by active, archived, or all"),
    field: Optional[List[str]] = Query(None, description="Selected export field keys"),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    provider_expr = _provider_key_expr().label("provider_key")
    export_fields = _admin_question_export_fields(provider_expr)
    fields_by_key = {item["key"]: item for item in export_fields}
    selected_keys = _normalize_admin_question_export_fields(field or [], fields_by_key)
    normalized_filters = await _normalize_admin_question_filters(
        db,
        group_id=group_id,
        subject_id=subject_id,
        topic_id=topic_id,
        vetting_status=vetting_status,
        question_type=question_type,
        difficulty_level=difficulty_level,
        bloom_taxonomy_level=bloom_taxonomy_level,
        generation_status=generation_status,
        reference_mode=reference_mode,
        provider_key=provider_key,
        version_scope=version_scope,
        archived_state=archived_state,
    )

    query = _build_admin_question_base_query(*[fields_by_key[key]["expression"] for key in selected_keys])
    query = _apply_admin_question_filters(query, **normalized_filters)
    result = await db.execute(
        query.order_by(Question.generated_at.desc(), Question.id.desc()).limit(_ADMIN_QUESTION_EXPORT_PREVIEW_LIMIT)
    )
    rows = result.mappings().all()

    return AdminQuestionExportPreviewResponse(
        available_fields=[
            AdminQuestionExportField(
                key=item["key"],
                label=item["label"],
                group=item["group"],
                description=item["description"],
                selected_by_default=bool(item["selected_by_default"]),
            )
            for item in export_fields
        ],
        selected_fields=[
            AdminQuestionExportColumn(key=key, label=fields_by_key[key]["label"])
            for key in selected_keys
        ],
        preview_count=len(rows),
        rows=[
            {
                key: _serialize_admin_question_export_value(key, row.get(key))
                for key in selected_keys
            }
            for row in rows
        ],
    )


@router.get("/questions/export")
async def export_admin_questions(
    group_id: Optional[str] = Query(None, description="Filter by group ID, including nested descendant groups"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    topic_id: Optional[str] = Query(None, description="Filter by topic ID"),
    vetting_status: Optional[str] = Query(None, description="Filter by pending, approved, rejected, or all"),
    question_type: Optional[str] = Query(None, description="Filter by question type"),
    difficulty_level: Optional[str] = Query(None, description="Filter by difficulty or unspecified"),
    bloom_taxonomy_level: Optional[str] = Query(None, description="Filter by Bloom level or unspecified"),
    generation_status: Optional[str] = Query(None, description="Filter by generation status accepted, discarded, or all"),
    reference_mode: str = Query("all", description="Filter by with_reference, without_reference, or all"),
    provider_key: Optional[str] = Query(None, description="Filter by AI provider key"),
    version_scope: str = Query("latest", description="Filter by latest or all versions"),
    archived_state: str = Query("active", description="Filter by active, archived, or all"),
    field: Optional[List[str]] = Query(None, description="Selected export field keys"),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    provider_expr = _provider_key_expr().label("provider_key")
    export_fields = _admin_question_export_fields(provider_expr)
    fields_by_key = {item["key"]: item for item in export_fields}
    selected_keys = _normalize_admin_question_export_fields(field or [], fields_by_key)
    normalized_filters = await _normalize_admin_question_filters(
        db,
        group_id=group_id,
        subject_id=subject_id,
        topic_id=topic_id,
        vetting_status=vetting_status,
        question_type=question_type,
        difficulty_level=difficulty_level,
        bloom_taxonomy_level=bloom_taxonomy_level,
        generation_status=generation_status,
        reference_mode=reference_mode,
        provider_key=provider_key,
        version_scope=version_scope,
        archived_state=archived_state,
    )
    selected_columns = [fields_by_key[key]["expression"] for key in selected_keys]
    header_labels = [fields_by_key[key]["label"] for key in selected_keys]

    async def generate_csv():
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(header_labels)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        batch_cursor_generated_at: Optional[datetime] = None
        batch_cursor_question_id: Optional[str] = None

        while True:
            query = _build_admin_question_base_query(
                Question.generated_at.label("__cursor_generated_at"),
                Question.id.label("__cursor_question_id"),
                *selected_columns,
            )
            query = _apply_admin_question_filters(query, **normalized_filters)
            if batch_cursor_generated_at and batch_cursor_question_id:
                query = query.where(
                    or_(
                        Question.generated_at < batch_cursor_generated_at,
                        and_(
                            Question.generated_at == batch_cursor_generated_at,
                            Question.id < batch_cursor_question_id,
                        ),
                    )
                )

            result = await db.execute(
                query.order_by(Question.generated_at.desc(), Question.id.desc()).limit(_ADMIN_QUESTION_EXPORT_BATCH_SIZE)
            )
            rows = result.mappings().all()
            if not rows:
                break

            for row in rows:
                writer.writerow([
                    _serialize_admin_question_export_value(key, row.get(key))
                    for key in selected_keys
                ])

            chunk = buffer.getvalue()
            if chunk:
                yield chunk
            buffer.seek(0)
            buffer.truncate(0)

            last_row = rows[-1]
            batch_cursor_generated_at = last_row["__cursor_generated_at"]
            batch_cursor_question_id = last_row["__cursor_question_id"]

            if len(rows) < _ADMIN_QUESTION_EXPORT_BATCH_SIZE:
                break

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="admin_questions_export_{timestamp}.csv"',
        },
    )


@router.get("/questions/providers", response_model=List[str])
async def list_admin_question_providers(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    provider_expr = _provider_key_expr().label("provider_key")
    result = await db.execute(
        select(provider_expr)
        .where(provider_expr.isnot(None), provider_expr != "")
        .distinct()
        .order_by(provider_expr.asc())
    )
    return [row.provider_key for row in result.all() if row.provider_key]


@router.get("/users", response_model=List[AdminUserSummary])
async def list_admin_users(
    current_user: User = Depends(get_current_admin),
):
    """List all auth users with role and action-level permissions."""
    async with AuthSessionLocal() as auth_db:
        result = await auth_db.execute(select(User).order_by(User.created_at.desc(), User.username.asc()))
        users = result.scalars().all()

    return [
        AdminUserSummary(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            is_active=bool(user.is_active),
            is_approved=bool(user.is_approved),
            is_superuser=bool(user.is_superuser),
            can_manage_groups=bool(user.can_manage_groups),
            can_generate=bool(user.can_generate),
            can_vet=bool(user.can_vet),
            approved_at=user.approved_at,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )
        for user in users
    ]


@router.get("/notifications", response_model=AdminNotificationListResponse)
async def list_admin_notifications(
    unread_only: bool = False,
    limit: int = 100,
    current_user: User = Depends(get_current_admin),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    """List notifications for the current admin user."""
    notification_service = AdminNotificationService(auth_db)
    notifications = await notification_service.list_for_admin(
        current_user.id,
        unread_only=unread_only,
        limit=limit,
    )
    unread_count = await notification_service.get_unread_count(current_user.id)
    return AdminNotificationListResponse(
        notifications=[_serialize_admin_notification(notification) for notification in notifications],
        unread_count=unread_count,
    )


@router.post("/notifications/{notification_id}/read", response_model=AdminNotificationSummary)
async def mark_admin_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_admin),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    """Mark a single notification as read for the current admin user."""
    notification_service = AdminNotificationService(auth_db)
    notification = await notification_service.mark_read(current_user.id, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return _serialize_admin_notification(notification)


@router.post("/notifications/read-all", response_model=MessageResponse)
async def mark_all_admin_notifications_read(
    current_user: User = Depends(get_current_admin),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    """Mark all notifications as read for the current admin user."""
    notification_service = AdminNotificationService(auth_db)
    updated = await notification_service.mark_all_read(current_user.id)
    return MessageResponse(message=f"Marked {updated} notification(s) as read")


@router.post("/users", response_model=AdminUserSummary, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    payload: AdminUserCreateRequest,
    current_user: User = Depends(get_current_admin),
):
    """Create a new user with explicit role and action permissions."""
    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters")

    role = _validate_role(payload.role)
    username = _validate_username(payload.username)
    security_question = " ".join((payload.security_question or "").strip().split())
    security_answer = str(payload.security_answer or "").strip()
    if not security_question or not security_answer:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Security question and answer are required",
        )
    permissions = _resolve_permissions(
        role,
        {
            "can_manage_groups": payload.can_manage_groups,
            "can_generate": payload.can_generate,
            "can_vet": payload.can_vet,
        },
    )

    async with AuthSessionLocal() as auth_db:
        existing_email = await auth_db.execute(select(User.id).where(User.email == payload.email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        existing_username = await auth_db.execute(select(User.id).where(User.username == username))
        if existing_username.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

        user = User(
            id=str(uuid.uuid4()),
            email=payload.email,
            username=username,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            security_question=security_question,
            security_answer_hash=hash_security_answer(security_answer),
            role=role,
            is_active=payload.is_active,
            is_approved=True,
            approved_at=datetime.now(timezone.utc),
            approved_by=current_user.id,
            can_manage_groups=permissions["can_manage_groups"],
            can_generate=permissions["can_generate"],
            can_vet=permissions["can_vet"],
        )
        auth_db.add(user)
        await auth_db.commit()
        await auth_db.refresh(user)

    return AdminUserSummary(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=bool(user.is_active),
        is_approved=bool(user.is_approved),
        is_superuser=bool(user.is_superuser),
        can_manage_groups=bool(user.can_manage_groups),
        can_generate=bool(user.can_generate),
        can_vet=bool(user.can_vet),
        approved_at=user.approved_at,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.patch("/users/{user_id}", response_model=AdminUserSummary)
async def update_admin_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    current_user: User = Depends(get_current_admin),
):
    """Update role, account status, and action permissions for a user."""
    async with AuthSessionLocal() as auth_db:
        result = await auth_db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        update_dict = payload.model_dump(exclude_unset=True)

        if "role" in update_dict and update_dict["role"] is not None:
            update_dict["role"] = _validate_role(update_dict["role"])

        if payload.full_name is not None:
            user.full_name = payload.full_name

        if payload.is_active is not None:
            if user.id == current_user.id and not payload.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account")
            user.is_active = payload.is_active

        role_changed = False
        if "role" in update_dict and update_dict["role"] is not None:
            user.role = update_dict["role"]
            role_changed = True

        permissions_payload = {
            "can_manage_groups": payload.can_manage_groups,
            "can_generate": payload.can_generate,
            "can_vet": payload.can_vet,
        }
        explicit_permission_update = any(value is not None for value in permissions_payload.values())

        if role_changed or explicit_permission_update:
            resolved = _resolve_permissions(user.role, permissions_payload)
            user.can_manage_groups = resolved["can_manage_groups"]
            user.can_generate = resolved["can_generate"]
            user.can_vet = resolved["can_vet"]

        user.updated_at = datetime.now(timezone.utc)
        await auth_db.commit()
        await auth_db.refresh(user)

    return AdminUserSummary(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=bool(user.is_active),
        is_approved=bool(user.is_approved),
        is_superuser=bool(user.is_superuser),
        can_manage_groups=bool(user.can_manage_groups),
        can_generate=bool(user.can_generate),
        can_vet=bool(user.can_vet),
        approved_at=user.approved_at,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/users/{user_id}/approve", response_model=AdminUserSummary)
async def approve_admin_user_registration(
    user_id: str,
    request: Request,
    current_user: User = Depends(get_current_admin),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    """Approve a pending user registration so the account can sign in."""
    user_service = UserService(auth_db)
    client_info = get_client_info(request)

    try:
        user = await user_service.approve_user_registration(
            user_id=user_id,
            admin_user_id=current_user.id,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return _serialize_admin_user(user)

@router.post("/users/approve-bulk", response_model=AdminBulkApproveUsersResponse)
async def approve_admin_users_bulk(
    payload: AdminBulkApproveUsersRequest,
    request: Request,
    current_user: User = Depends(get_current_admin),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    """Approve multiple pending user registrations in one request."""
    user_service = UserService(auth_db)
    client_info = get_client_info(request)

    approved_users: List[AdminUserSummary] = []
    seen_ids: set[str] = set()

    for raw_user_id in payload.user_ids:
        user_id = str(raw_user_id or "").strip()
        if not user_id or user_id in seen_ids:
            continue
        seen_ids.add(user_id)

        existing_user = await user_service.get_user_by_id(user_id)
        if not existing_user or existing_user.is_approved:
            continue

        approved_user = await user_service.approve_user_registration(
            user_id=user_id,
            admin_user_id=current_user.id,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
        )
        approved_users.append(_serialize_admin_user(approved_user))

    return AdminBulkApproveUsersResponse(
        approved_users=approved_users,
        approved_count=len(approved_users),
    )


@router.post("/users/{user_id}/reset-password", response_model=MessageResponse)
async def admin_reset_user_password(
    user_id: str,
    payload: AdminUserPasswordResetRequest,
    request: Request,
    current_user: User = Depends(get_current_admin),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    """Allow admins to reset the password for any user account."""
    user_service = UserService(auth_db)
    client_info = get_client_info(request)

    try:
        await user_service.admin_reset_password(
            user_id=user_id,
            new_password=payload.new_password,
            admin_user_id=current_user.id,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return MessageResponse(message="Password reset successfully")


@router.delete("/users/{user_id}", response_model=AdminUserDeleteResponse)
async def delete_admin_user(
    user_id: str,
    payload: AdminUserDeleteRequest,
    request: Request,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    """Delete a user's login and optionally remove related platform data."""
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account")

    user_service = UserService(auth_db)
    target_user = await user_service.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target_user.role == "admin":
        remaining_admins = await auth_db.execute(
            select(func.count())
            .select_from(User)
            .where(User.role == "admin", User.id != user_id)
        )
        if int(remaining_admins.scalar() or 0) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete the last admin account")

    cleanup_counts = await _delete_admin_user_data(
        db,
        user_id=user_id,
        delete_subjects=payload.delete_subjects,
        delete_questions=payload.delete_questions,
        delete_vetting_data=payload.delete_vetting_data,
    )
    await db.commit()

    client_info = get_client_info(request)
    deleted_user = await user_service.delete_user_login(
        user_id,
        admin_user_id=current_user.id,
        ip_address=client_info.get("ip_address"),
        user_agent=client_info.get("user_agent"),
        cleanup_summary={
            "delete_subjects": payload.delete_subjects,
            "delete_questions": payload.delete_questions,
            "delete_vetting_data": payload.delete_vetting_data,
            **cleanup_counts,
        },
    )

    if not any((payload.delete_subjects, payload.delete_questions, payload.delete_vetting_data)):
        message = f"Deleted {deleted_user['username']}'s login. Their subjects, questions, and vetting data were preserved."
    else:
        cleanup_parts: list[str] = []
        if payload.delete_subjects:
            cleanup_parts.append(f"{cleanup_counts['deleted_subjects']} subject(s)")
        if payload.delete_questions:
            cleanup_parts.append(f"{cleanup_counts['deleted_questions']} question(s)")
        if payload.delete_vetting_data:
            cleanup_parts.append(
                f"{cleanup_counts['deleted_vetting_logs']} vetting log(s) and {cleanup_counts['deleted_vetting_progress']} saved progress record(s)"
            )
        message = f"Deleted {deleted_user['username']}'s login and removed " + ", ".join(cleanup_parts) + "."

    return AdminUserDeleteResponse(
        message=message,
        deleted_subjects=cleanup_counts["deleted_subjects"],
        deleted_questions=cleanup_counts["deleted_questions"],
        deleted_vetting_logs=cleanup_counts["deleted_vetting_logs"],
        deleted_vetting_progress=cleanup_counts["deleted_vetting_progress"],
    )


@router.get("/provider-metrics", response_model=ProviderMetricsResponse)
async def get_provider_metrics(
    days: int = 30,
    usage_type: Optional[str] = None,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return provider-level generation and rejection/regeneration metrics.

    Args:
        days: Number of days to look back (1-365)
        usage_type: Filter by usage type - "vquest" for question generation, or None for all
    """
    window_days = max(1, min(days, 365))
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    provider_expr = _provider_key_expr().label("provider_key")

    generated_rows = (
        await db.execute(
            select(
                provider_expr,
                func.count(Question.id).label("generated"),
                func.count(distinct(Question.session_id)).label("api_calls"),
            )
            .where(
                Question.generation_status == "accepted",
                Question.generated_at >= since,
            )
            .group_by(provider_expr)
        )
    ).all()
    generated_map = {
        str(row.provider_key or "unknown"): {
            "generated": int(row.generated or 0),
            "api_calls": int(row.api_calls or 0),
        }
        for row in generated_rows
    }

    # Query provider_usage_logs for non-question-generation usage
    if usage_type != "vquest":
        usage_log_rows = (
            await db.execute(
                select(
                    ProviderUsageLog.provider_key,
                    func.count(ProviderUsageLog.id).label("usage_count"),
                )
                .where(
                    ProviderUsageLog.created_at >= since,
                )
                .group_by(ProviderUsageLog.provider_key)
            )
        ).all()

        for row in usage_log_rows:
            provider_key = str(row.provider_key or "unknown")
            usage_count = int(row.usage_count or 0)
            if provider_key in generated_map:
                generated_map[provider_key]["api_calls"] += usage_count
            else:
                generated_map[provider_key] = {
                    "generated": 0,
                    "api_calls": usage_count,
                }

    rejected_rows = (
        await db.execute(
            select(
                provider_expr,
                func.count(Question.id).label("rejected"),
            )
            .where(
                Question.vetting_status == "rejected",
                Question.generated_at >= since,
            )
            .group_by(provider_expr)
        )
    ).all()
    rejected_map = {
        str(row.provider_key or "unknown"): int(row.rejected or 0)
        for row in rejected_rows
    }

    vetted_rows = (
        await db.execute(
            select(
                provider_expr,
                func.count(Question.id).label("vetted"),
            )
            .where(
                Question.vetting_status == "approved",
                Question.generated_at >= since,
            )
            .group_by(provider_expr)
        )
    ).all()
    vetted_map = {
        str(row.provider_key or "unknown"): int(row.vetted or 0)
        for row in vetted_rows
    }

    regenerated_rows = (
        await db.execute(
            select(
                provider_expr,
                func.count(Question.id).label("regenerated"),
            )
            .where(
                Question.replaces_id.isnot(None),
                Question.generated_at >= since,
            )
            .group_by(provider_expr)
        )
    ).all()
    regenerated_map = {
        str(row.provider_key or "unknown"): int(row.regenerated or 0)
        for row in regenerated_rows
    }

    reason_rows = (
        await db.execute(
            select(
                provider_expr,
                VettingLog.reason_codes,
                VettingLog.rejection_reasons,
            )
            .join(VettingLog, VettingLog.question_id == Question.id)
            .where(
                VettingLog.decision == "reject",
                VettingLog.created_at >= since,
            )
        )
    ).all()

    reason_map: dict[str, Counter] = {}
    for row in reason_rows:
        provider_key = str(row.provider_key or "unknown")
        bucket = reason_map.setdefault(provider_key, Counter())
        codes = row.reason_codes or []
        reasons = row.rejection_reasons or []
        for code in codes:
            if code:
                bucket[str(code)] += 1
        if not codes:
            for reason in reasons:
                if reason:
                    bucket[str(reason)] += 1

    provider_keys = set(generated_map) | set(rejected_map) | set(regenerated_map) | set(vetted_map)
    provider_metrics_list: List[ProviderMetric] = []
    total_generated = 0
    total_rejected = 0
    total_regenerated = 0

    for pk in sorted(provider_keys):
        generated = generated_map.get(pk, {}).get("generated", 0)
        api_calls = generated_map.get(pk, {}).get("api_calls", 0)
        rejected = rejected_map.get(pk, 0)
        regenerated = regenerated_map.get(pk, 0)
        vetted = vetted_map.get(pk, 0)

        total_generated += generated
        total_rejected += rejected
        total_regenerated += regenerated

        rejection_rate = (rejected / generated) if generated else 0.0
        regeneration_rate = (regenerated / rejected) if rejected else 0.0
        if rejection_rate <= 0.2:
            inferred_preference = "preferred"
        elif rejection_rate <= 0.4:
            inferred_preference = "neutral"
        else:
            inferred_preference = "avoid"

        top_reasons = [
            reason for reason, _ in reason_map.get(pk, Counter()).most_common(3)
        ]

        provider_metrics_list.append(
            ProviderMetric(
                provider_key=pk,
                total_generated=generated,
                api_calls=api_calls,
                avg_questions_per_call=round((generated / api_calls) if api_calls else 0.0, 2),
                total_rejected=rejected,
                total_regenerated=regenerated,
                total_vetted=vetted,
                rejection_rate=round(rejection_rate, 4),
                regeneration_rate=round(regeneration_rate, 4),
                inferred_preference=inferred_preference,
                top_rejection_reasons=top_reasons,
            )
        )

    provider_metrics_list.sort(key=lambda item: item.total_generated, reverse=True)

    return ProviderMetricsResponse(
        window_days=window_days,
        total_generated=total_generated,
        total_rejected=total_rejected,
        total_regenerated=total_regenerated,
        providers=provider_metrics_list,
    )
