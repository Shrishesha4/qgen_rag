"""
Admin Dashboard API endpoints.

Provides aggregate statistics across the entire platform:
subjects, topics, questions generated, vetting stats, per-user breakdowns.
"""

from typing import Optional, List
from datetime import datetime, timezone, timedelta
import re
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, and_, case, distinct, literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth_database import AuthSessionLocal
from app.api.v1.deps import get_current_admin
from app.models.user import User, VALID_ROLES, default_permissions_for_role
from app.models.question import Question, GenerationSession
from app.models.subject import Subject, Topic
from app.models.training import VettingLog
from app.core.security import hash_password


router = APIRouter()


# ============== Schemas ==============


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
    is_superuser: bool
    can_manage_groups: bool
    can_generate: bool
    can_vet: bool
    created_at: Optional[datetime]
    last_login_at: Optional[datetime]


class AdminUserCreateRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None
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

    total_questions_q = select(func.count(Question.id)).where(
        Question.generation_status == "accepted"
    )
    vetted_q = select(func.count(Question.id)).where(
        Question.vetting_status.in_(["approved", "rejected"])
    )
    approved_q = select(func.count(Question.id)).where(
        Question.vetting_status == "approved"
    )
    rejected_q = select(func.count(Question.id)).where(
        Question.vetting_status == "rejected"
    )
    pending_q = select(func.count(Question.id)).where(
        Question.vetting_status == "pending",
        Question.generation_status == "accepted",
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
        .where(Question.vetted_by.isnot(None))
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
        .where(Question.vetted_by.isnot(None))
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
            Question.vetting_status == "pending",
            Question.generation_status == "accepted",
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
                Question.generation_status == "accepted",
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
            Question.generation_status == "accepted",
        )
    )
    subject_stats_row = subject_stats_result.one()

    topic_stats_map = {}
    if topic_ids:
        topic_stats_result = await db.execute(
            select(Question.topic_id, *_question_count_columns())
            .where(
                Question.topic_id.in_(topic_ids),
                Question.generation_status == "accepted",
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
            is_superuser=bool(user.is_superuser),
            can_manage_groups=bool(user.can_manage_groups),
            can_generate=bool(user.can_generate),
            can_vet=bool(user.can_vet),
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )
        for user in users
    ]


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
            role=role,
            is_active=payload.is_active,
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
        is_superuser=bool(user.is_superuser),
        can_manage_groups=bool(user.can_manage_groups),
        can_generate=bool(user.can_generate),
        can_vet=bool(user.can_vet),
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
        is_superuser=bool(user.is_superuser),
        can_manage_groups=bool(user.can_manage_groups),
        can_generate=bool(user.can_generate),
        can_vet=bool(user.can_vet),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("/provider-metrics", response_model=ProviderMetricsResponse)
async def get_provider_metrics(
    days: int = 30,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return provider-level generation and rejection/regeneration metrics."""
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
    provider_metrics: List[ProviderMetric] = []
    total_generated = 0
    total_rejected = 0
    total_regenerated = 0

    for provider_key in sorted(provider_keys):
        generated = generated_map.get(provider_key, {}).get("generated", 0)
        api_calls = generated_map.get(provider_key, {}).get("api_calls", 0)
        rejected = rejected_map.get(provider_key, 0)
        regenerated = regenerated_map.get(provider_key, 0)

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
            reason for reason, _ in reason_map.get(provider_key, Counter()).most_common(3)
        ]

        provider_metrics.append(
            ProviderMetric(
                provider_key=provider_key,
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

    provider_metrics.sort(key=lambda item: item.total_generated, reverse=True)

    return ProviderMetricsResponse(
        window_days=window_days,
        total_generated=total_generated,
        total_rejected=total_rejected,
        total_regenerated=total_regenerated,
        providers=provider_metrics,
    )
