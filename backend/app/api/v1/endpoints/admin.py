"""
Admin Dashboard API endpoints.

Provides aggregate statistics across the entire platform:
subjects, topics, questions generated, vetting stats, per-user breakdowns.
"""

from typing import Optional, List, Any, Dict
from collections import Counter
from datetime import datetime, timezone, timedelta
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, func, and_, case, distinct, delete, or_, literal
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
from app.services.user_service import UserService


router = APIRouter()


# ============== Schemas ==============


class ProviderMetric(BaseModel):
    provider_key: str
    total_generated: int
    api_calls: int
    avg_questions_per_call: float
    total_rejected: int
    total_regenerated: int
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


@router.get("/subjects", response_model=List[AdminSubjectSummary])
async def list_admin_subjects(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subject).order_by(Subject.name.asc()))
    subjects = result.scalars().all()
    users_map = await _get_all_users()

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

    provider_keys = set(generated_map) | set(rejected_map) | set(regenerated_map)
    provider_metrics_list: List[ProviderMetric] = []
    total_generated = 0
    total_rejected = 0
    total_regenerated = 0

    for pk in sorted(provider_keys):
        generated = generated_map.get(pk, {}).get("generated", 0)
        api_calls = generated_map.get(pk, {}).get("api_calls", 0)
        rejected = rejected_map.get(pk, 0)
        regenerated = regenerated_map.get(pk, 0)

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
