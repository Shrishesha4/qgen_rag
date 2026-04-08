"""Favorites and structured activity log endpoints."""

from typing import Optional, Literal, List, Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_admin, get_current_user
from app.core.auth_database import get_auth_db
from app.models.auth import UserFavorite, ActivityLog
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.services.activity_service import safe_record_activity


router = APIRouter()


class FavoriteToggleRequest(BaseModel):
    entity_type: Literal["subject", "group"]
    entity_id: str = Field(..., min_length=1, max_length=36)
    entity_name: Optional[str] = Field(default=None, max_length=255)
    source_area: Optional[str] = Field(default=None, max_length=50)


class FavoriteSummary(BaseModel):
    entity_type: str
    entity_id: str
    created_at: Optional[str]


class FavoritesResponse(BaseModel):
    favorites: List[FavoriteSummary]


class ActivityEventRequest(BaseModel):
    action_key: str = Field(..., min_length=1, max_length=80)
    action_label: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=50)
    source_area: Optional[str] = Field(default=None, max_length=50)
    entity_type: Optional[str] = Field(default=None, max_length=20)
    entity_id: Optional[str] = Field(default=None, max_length=36)
    entity_name: Optional[str] = Field(default=None, max_length=255)
    subject_id: Optional[str] = Field(default=None, max_length=36)
    subject_name: Optional[str] = Field(default=None, max_length=255)
    topic_id: Optional[str] = Field(default=None, max_length=36)
    topic_name: Optional[str] = Field(default=None, max_length=255)
    group_id: Optional[str] = Field(default=None, max_length=36)
    group_name: Optional[str] = Field(default=None, max_length=255)
    details: Optional[dict[str, Any]] = None


class ActivityLogSummary(BaseModel):
    id: str
    actor_user_id: Optional[str]
    actor_role: Optional[str]
    actor_name: Optional[str]
    actor_email: Optional[str]
    action_key: str
    action_label: str
    category: Optional[str]
    source_area: Optional[str]
    entity_type: Optional[str]
    entity_id: Optional[str]
    entity_name: Optional[str]
    subject_id: Optional[str]
    subject_name: Optional[str]
    topic_id: Optional[str]
    topic_name: Optional[str]
    group_id: Optional[str]
    group_name: Optional[str]
    endpoint: Optional[str]
    http_method: Optional[str]
    ip_address: Optional[str]
    success: bool
    error_message: Optional[str]
    details: Optional[dict[str, Any]]
    created_at: Optional[str]


class ActivityLogListResponse(BaseModel):
    items: List[ActivityLogSummary]
    pagination: dict


class ActivityFilterOption(BaseModel):
    key: str
    label: str


class ActivityLogFilterOptionsResponse(BaseModel):
    actions: List[ActivityFilterOption]
    source_areas: List[str]
    actor_roles: List[str]
    entity_types: List[str]
    categories: List[str]


def _serialize_favorite(favorite: UserFavorite) -> FavoriteSummary:
    return FavoriteSummary(
        entity_type=favorite.entity_type,
        entity_id=favorite.entity_id,
        created_at=favorite.created_at.isoformat() if favorite.created_at else None,
    )


def _serialize_activity_log(log: ActivityLog) -> ActivityLogSummary:
    return ActivityLogSummary(
        id=log.id,
        actor_user_id=log.actor_user_id,
        actor_role=log.actor_role,
        actor_name=log.actor_name,
        actor_email=log.actor_email,
        action_key=log.action_key,
        action_label=log.action_label,
        category=log.category,
        source_area=log.source_area,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        entity_name=log.entity_name,
        subject_id=log.subject_id,
        subject_name=log.subject_name,
        topic_id=log.topic_id,
        topic_name=log.topic_name,
        group_id=log.group_id,
        group_name=log.group_name,
        endpoint=log.endpoint,
        http_method=log.http_method,
        ip_address=log.ip_address,
        success=bool(log.success),
        error_message=log.error_message,
        details=log.details,
        created_at=log.created_at.isoformat() if log.created_at else None,
    )


@router.get("/favorites", response_model=FavoritesResponse)
async def list_current_user_favorites(
    current_user: User = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    result = await auth_db.execute(
        select(UserFavorite)
        .where(UserFavorite.user_id == current_user.id)
        .order_by(UserFavorite.created_at.asc())
    )
    favorites = result.scalars().all()
    return FavoritesResponse(favorites=[_serialize_favorite(favorite) for favorite in favorites])


@router.put("/favorites", response_model=FavoriteSummary)
async def add_current_user_favorite(
    payload: FavoriteToggleRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    result = await auth_db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.entity_type == payload.entity_type,
            UserFavorite.entity_id == payload.entity_id,
        )
    )
    favorite = result.scalar_one_or_none()

    if favorite is None:
        favorite = UserFavorite(
            user_id=current_user.id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
        )
        auth_db.add(favorite)
        await auth_db.commit()
        await auth_db.refresh(favorite)

    await safe_record_activity(
        user=current_user,
        action_key="favorite_added",
        action_label="Pinned Favorite",
        category="favorites",
        source_area=payload.source_area,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        entity_name=payload.entity_name,
        request=request,
    )
    return _serialize_favorite(favorite)


@router.delete("/favorites", response_model=MessageResponse)
async def remove_current_user_favorite(
    payload: FavoriteToggleRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    result = await auth_db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.entity_type == payload.entity_type,
            UserFavorite.entity_id == payload.entity_id,
        )
    )
    favorite = result.scalar_one_or_none()
    if favorite is not None:
        await auth_db.delete(favorite)
        await auth_db.commit()

    await safe_record_activity(
        user=current_user,
        action_key="favorite_removed",
        action_label="Unpinned Favorite",
        category="favorites",
        source_area=payload.source_area,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        entity_name=payload.entity_name,
        request=request,
    )
    return MessageResponse(message="Favorite removed")


@router.post("/events", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def record_client_activity_event(
    payload: ActivityEventRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    await safe_record_activity(
        user=current_user,
        action_key=payload.action_key,
        action_label=payload.action_label,
        category=payload.category,
        source_area=payload.source_area,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        entity_name=payload.entity_name,
        subject_id=payload.subject_id,
        subject_name=payload.subject_name,
        topic_id=payload.topic_id,
        topic_name=payload.topic_name,
        group_id=payload.group_id,
        group_name=payload.group_name,
        details=payload.details,
        request=request,
    )
    return MessageResponse(message="Activity recorded")


@router.get("/logs/options", response_model=ActivityLogFilterOptionsResponse)
async def get_activity_log_filter_options(
    current_user: User = Depends(get_current_admin),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    action_rows = await auth_db.execute(
        select(ActivityLog.action_key, ActivityLog.action_label)
        .distinct()
        .order_by(ActivityLog.action_label.asc(), ActivityLog.action_key.asc())
    )
    source_rows = await auth_db.execute(
        select(ActivityLog.source_area)
        .where(ActivityLog.source_area.is_not(None))
        .distinct()
        .order_by(ActivityLog.source_area.asc())
    )
    role_rows = await auth_db.execute(
        select(ActivityLog.actor_role)
        .where(ActivityLog.actor_role.is_not(None))
        .distinct()
        .order_by(ActivityLog.actor_role.asc())
    )
    entity_rows = await auth_db.execute(
        select(ActivityLog.entity_type)
        .where(ActivityLog.entity_type.is_not(None))
        .distinct()
        .order_by(ActivityLog.entity_type.asc())
    )
    category_rows = await auth_db.execute(
        select(ActivityLog.category)
        .where(ActivityLog.category.is_not(None))
        .distinct()
        .order_by(ActivityLog.category.asc())
    )

    return ActivityLogFilterOptionsResponse(
        actions=[ActivityFilterOption(key=key, label=label) for key, label in action_rows.all() if key and label],
        source_areas=[value for value in source_rows.scalars().all() if value],
        actor_roles=[value for value in role_rows.scalars().all() if value],
        entity_types=[value for value in entity_rows.scalars().all() if value],
        categories=[value for value in category_rows.scalars().all() if value],
    )


@router.get("/logs", response_model=ActivityLogListResponse)
async def list_activity_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    q: Optional[str] = Query(None),
    action_key: Optional[str] = Query(None),
    actor_role: Optional[str] = Query(None),
    source_area: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_admin),
    auth_db: AsyncSession = Depends(get_auth_db),
):
    query = select(ActivityLog)

    if action_key:
        query = query.where(ActivityLog.action_key == action_key)
    if actor_role:
        query = query.where(ActivityLog.actor_role == actor_role)
    if source_area:
        query = query.where(ActivityLog.source_area == source_area)
    if entity_type:
        query = query.where(ActivityLog.entity_type == entity_type)
    if category:
        query = query.where(ActivityLog.category == category)
    if success is not None:
        query = query.where(ActivityLog.success == success)
    if q:
        search = f"%{q.strip()}%"
        query = query.where(
            or_(
                ActivityLog.actor_name.ilike(search),
                ActivityLog.actor_email.ilike(search),
                ActivityLog.action_label.ilike(search),
                ActivityLog.action_key.ilike(search),
                ActivityLog.entity_name.ilike(search),
                ActivityLog.subject_name.ilike(search),
                ActivityLog.topic_name.ilike(search),
                ActivityLog.group_name.ilike(search),
                ActivityLog.error_message.ilike(search),
            )
        )

    total_result = await auth_db.execute(select(func.count()).select_from(query.subquery()))
    total = int(total_result.scalar() or 0)

    offset = (page - 1) * limit
    result = await auth_db.execute(
        query.order_by(ActivityLog.created_at.desc()).offset(offset).limit(limit)
    )
    items = result.scalars().all()

    return ActivityLogListResponse(
        items=[_serialize_activity_log(item) for item in items],
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        },
    )