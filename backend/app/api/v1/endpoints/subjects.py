"""
Subject and Topic API endpoints.
"""

import os
import io
import logging
import re
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks, Request
from sqlalchemy import select, func, case, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth_database import AuthSessionLocal
from app.core.config import settings
from app.models.subject import Subject, Topic, SubjectGroup
from app.models.question import Question
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.models.topic_audit import TopicAuditLog
from app.schemas.subject import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    SubjectListResponse,
    SubjectDetailResponse,
    TopicCreate,
    TopicUpdate,
    TopicResponse,
    TopicListResponse,
    SubjectGroupCreate,
    SubjectGroupUpdate,
    SubjectGroupResponse,
    SubjectGroupTreeNode,
    SubjectTreeResponse,
)
from app.api.v1.deps import get_current_user, ensure_user_can_generate, ensure_user_can_manage_groups
from app.services.provider_service import (
    create_llm_service_for_active_provider,
    get_provider_service,
)
from app.services.activity_service import safe_record_activity

logger = logging.getLogger(__name__)
router = APIRouter()


class SubjectTopicReviewStats(BaseModel):
    topic_id: str
    generated: int
    approved: int
    rejected: int
    pending: int


class SubjectReviewStatsResponse(BaseModel):
    generated: int
    approved: int
    rejected: int
    pending: int
    topics: List[SubjectTopicReviewStats]


# ============== Subject Endpoints ==============

@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    request: Request,
    subject_data: SubjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new subject."""
    group = None
    if subject_data.group_id:
        group_result = await db.execute(
            select(SubjectGroup).where(SubjectGroup.id == subject_data.group_id)
        )
        group = group_result.scalar_one_or_none()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target group not found",
            )

    subject = Subject(
        user_id=current_user.id,
        group_id=subject_data.group_id,
        name=subject_data.name,
        code=subject_data.code,
        description=subject_data.description,
        learning_outcomes=(
            {"outcomes": [lo.model_dump() for lo in subject_data.learning_outcomes]}
            if subject_data.learning_outcomes else None
        ),
        course_outcomes=(
            {"outcomes": [co.model_dump() for co in subject_data.course_outcomes]}
            if subject_data.course_outcomes else None
        ),
    )
    db.add(subject)
    await db.commit()
    await db.refresh(subject)

    await safe_record_activity(
        user=current_user,
        action_key="subject_created",
        action_label="Created Subject",
        category="subjects",
        source_area="teacher_subjects",
        entity_type="subject",
        entity_id=subject.id,
        entity_name=subject.name,
        subject_id=subject.id,
        subject_name=subject.name,
        group_id=subject.group_id,
        group_name=group.name if group else None,
        details={
            "code": subject.code,
            "has_description": bool(subject.description),
            "has_learning_outcomes": bool(subject.learning_outcomes),
            "has_course_outcomes": bool(subject.course_outcomes),
        },
        request=request,
    )
    return SubjectResponse.model_validate(subject)


@router.get("", response_model=SubjectListResponse)
async def list_subjects(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name or code"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all subjects visible to teachers."""
    query = select(Subject)
    
    if search:
        query = query.where(
            (Subject.name.ilike(f"%{search}%")) | (Subject.code.ilike(f"%{search}%"))
        )
    
    # Count total
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()
    
    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Subject.name)
    
    result = await db.execute(query)
    subjects = result.scalars().all()

    # Compute live question counts per subject (non-archived, latest version only)
    subject_ids = [s.id for s in subjects]
    live_counts: dict = {}
    status_counts_by_subject: dict = {}
    if subject_ids:
        live_counts_result = await db.execute(
            select(Question.subject_id, func.count(Question.id))
            .where(
                Question.subject_id.in_(subject_ids),
                Question.is_archived == False,
                Question.is_latest == True,
            )
            .group_by(Question.subject_id)
        )
        live_counts = dict(live_counts_result.all())

        status_counts_result = await db.execute(
            select(
                Question.subject_id,
                func.count(case((Question.vetting_status == "pending", 1))).label("total_pending"),
                func.count(case((Question.vetting_status == "approved", 1))).label("total_approved"),
                func.count(case((Question.vetting_status == "rejected", 1))).label("total_rejected"),
            )
            .where(
                Question.subject_id.in_(subject_ids),
                Question.is_archived == False,
                Question.is_latest == True,
            )
            .group_by(Question.subject_id)
        )
        for subject_id, total_pending, total_approved, total_rejected in status_counts_result.all():
            status_counts_by_subject[subject_id] = {
                "total_pending": int(total_pending or 0),
                "total_approved": int(total_approved or 0),
                "total_rejected": int(total_rejected or 0),
            }

    subject_responses = []
    for s in subjects:
        sr = SubjectResponse.model_validate(s)
        sr.total_questions = live_counts.get(s.id, 0)
        subject_status_counts = status_counts_by_subject.get(s.id, {})
        sr.total_pending = int(subject_status_counts.get("total_pending", 0))
        sr.total_approved = int(subject_status_counts.get("total_approved", 0))
        sr.total_rejected = int(subject_status_counts.get("total_rejected", 0))
        subject_responses.append(sr)

    return SubjectListResponse(
        subjects=subject_responses,
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        }
    )


# ============== Subject Groups (must be before /{subject_id} routes) ==============

@router.get("/tree", response_model=SubjectTreeResponse)
async def get_subjects_tree(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get hierarchical tree of groups and subjects with aggregated stats."""
    # Fetch all groups
    groups_result = await db.execute(
        select(SubjectGroup).order_by(SubjectGroup.order_index)
    )
    all_groups = groups_result.scalars().all()
    
    # Fetch all subjects with live question counts
    subjects_result = await db.execute(select(Subject).order_by(Subject.name))
    all_subjects = subjects_result.scalars().all()
    
    subject_ids = [s.id for s in all_subjects]
    
    # Compute live question counts
    live_counts: dict = {}
    status_counts_by_subject: dict = {}
    if subject_ids:
        live_counts_result = await db.execute(
            select(Question.subject_id, func.count(Question.id))
            .where(
                Question.subject_id.in_(subject_ids),
                Question.is_archived == False,
                Question.is_latest == True,
            )
            .group_by(Question.subject_id)
        )
        live_counts = dict(live_counts_result.all())

        status_counts_result = await db.execute(
            select(
                Question.subject_id,
                func.count(case((Question.vetting_status == "pending", 1))).label("total_pending"),
                func.count(case((Question.vetting_status == "approved", 1))).label("total_approved"),
                func.count(case((Question.vetting_status == "rejected", 1))).label("total_rejected"),
            )
            .where(
                Question.subject_id.in_(subject_ids),
                Question.is_archived == False,
                Question.is_latest == True,
            )
            .group_by(Question.subject_id)
        )
        for subject_id, total_pending, total_approved, total_rejected in status_counts_result.all():
            status_counts_by_subject[subject_id] = {
                "total_pending": int(total_pending or 0),
                "total_approved": int(total_approved or 0),
                "total_rejected": int(total_rejected or 0),
            }
    
    # Build subject responses with stats
    subject_responses_map: dict = {}
    for s in all_subjects:
        sr = SubjectResponse.model_validate(s)
        sr.total_questions = live_counts.get(s.id, 0)
        subject_status_counts = status_counts_by_subject.get(s.id, {})
        sr.total_pending = int(subject_status_counts.get("total_pending", 0))
        sr.total_approved = int(subject_status_counts.get("total_approved", 0))
        sr.total_rejected = int(subject_status_counts.get("total_rejected", 0))
        subject_responses_map[s.id] = sr
    
    # Group subjects by group_id
    subjects_by_group: dict = {}
    ungrouped_subjects = []
    for s in all_subjects:
        sr = subject_responses_map[s.id]
        if s.group_id:
            subjects_by_group.setdefault(s.group_id, []).append(sr)
        else:
            ungrouped_subjects.append(sr)
    
    # Build group tree with aggregated stats
    groups_by_id = {g.id: g for g in all_groups}
    children_by_parent: dict = {}
    for g in all_groups:
        children_by_parent.setdefault(g.parent_id, []).append(g)
    
    def build_group_node(group: SubjectGroup) -> SubjectGroupTreeNode:
        """Recursively build group tree node with aggregated stats."""
        children = children_by_parent.get(group.id, [])
        child_nodes = [build_group_node(c) for c in sorted(children, key=lambda x: x.order_index)]
        
        group_subjects = subjects_by_group.get(group.id, [])
        
        # Aggregate stats from direct subjects
        total_subjects = len(group_subjects)
        total_questions = sum(s.total_questions for s in group_subjects)
        total_pending = sum(s.total_pending for s in group_subjects)
        total_approved = sum(s.total_approved for s in group_subjects)
        total_rejected = sum(s.total_rejected for s in group_subjects)
        
        # Add stats from child groups
        for child in child_nodes:
            total_subjects += child.total_subjects
            total_questions += child.total_questions
            total_pending += child.total_pending
            total_approved += child.total_approved
            total_rejected += child.total_rejected
        
        return SubjectGroupTreeNode(
            id=group.id,
            name=group.name,
            parent_id=group.parent_id,
            order_index=group.order_index,
            created_at=group.created_at,
            updated_at=group.updated_at,
            total_subjects=total_subjects,
            total_questions=total_questions,
            total_pending=total_pending,
            total_approved=total_approved,
            total_rejected=total_rejected,
            children=child_nodes,
            subjects=group_subjects,
        )
    
    # Build root-level groups
    root_groups = children_by_parent.get(None, [])
    root_group_nodes = [build_group_node(g) for g in sorted(root_groups, key=lambda x: x.order_index)]
    
    # Calculate totals
    all_totals = {
        "total_groups": len(all_groups),
        "total_subjects": len(all_subjects),
        "total_questions": sum(sr.total_questions for sr in subject_responses_map.values()),
        "total_pending": sum(sr.total_pending for sr in subject_responses_map.values()),
        "total_approved": sum(sr.total_approved for sr in subject_responses_map.values()),
        "total_rejected": sum(sr.total_rejected for sr in subject_responses_map.values()),
    }
    
    return SubjectTreeResponse(
        groups=root_group_nodes,
        ungrouped_subjects=ungrouped_subjects,
        totals=all_totals,
    )


@router.post("/groups", response_model=SubjectGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    request: Request,
    group_data: SubjectGroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new subject group/folder."""
    # Validate parent exists if provided
    if group_data.parent_id:
        parent_result = await db.execute(
            select(SubjectGroup).where(SubjectGroup.id == group_data.parent_id)
        )
        if not parent_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent group not found",
            )
    
    # Get max order_index for siblings
    sibling_query = select(func.max(SubjectGroup.order_index)).where(
        SubjectGroup.parent_id == group_data.parent_id
    )
    max_order_result = await db.execute(sibling_query)
    max_order = max_order_result.scalar_one() or -1
    
    group = SubjectGroup(
        name=group_data.name,
        parent_id=group_data.parent_id,
        order_index=max_order + 1,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    parent_name = None
    if group.parent_id:
        parent_result = await db.execute(select(SubjectGroup.name).where(SubjectGroup.id == group.parent_id))
        parent_name = parent_result.scalar_one_or_none()

    await safe_record_activity(
        user=current_user,
        action_key="group_created",
        action_label="Created Group",
        category="subjects",
        source_area="teacher_subjects",
        entity_type="group",
        entity_id=group.id,
        entity_name=group.name,
        group_id=group.id,
        group_name=group.name,
        details={
            "parent_group_id": group.parent_id,
            "parent_group_name": parent_name,
        },
        request=request,
    )
    
    return SubjectGroupResponse.model_validate(group)


@router.get("/groups", response_model=List[SubjectGroupResponse])
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all subject groups (flat list)."""
    result = await db.execute(
        select(SubjectGroup).order_by(SubjectGroup.parent_id.nullsfirst(), SubjectGroup.order_index)
    )
    groups = result.scalars().all()
    return [SubjectGroupResponse.model_validate(g) for g in groups]


@router.get("/groups/{group_id}", response_model=SubjectGroupResponse)
async def get_group(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific subject group."""
    result = await db.execute(
        select(SubjectGroup).where(SubjectGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    
    return SubjectGroupResponse.model_validate(group)


@router.put("/groups/{group_id}", response_model=SubjectGroupResponse)
async def update_group(
    group_id: str,
    request: Request,
    group_data: SubjectGroupUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a subject group."""
    ensure_user_can_manage_groups(current_user)

    result = await db.execute(
        select(SubjectGroup).where(SubjectGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    
    # Validate new parent if provided
    if group_data.parent_id is not None:
        if group_data.parent_id == group_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A group cannot be its own parent",
            )
        if group_data.parent_id:
            # Check for circular reference
            current_parent_id = group_data.parent_id
            while current_parent_id:
                if current_parent_id == group_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Circular parent reference detected",
                    )
                parent_result = await db.execute(
                    select(SubjectGroup.parent_id).where(SubjectGroup.id == current_parent_id)
                )
                current_parent_id = parent_result.scalar_one_or_none()
    
    update_data = group_data.model_dump(exclude_unset=True)
    changed_fields = {}
    previous_name = group.name
    previous_parent_id = group.parent_id
    for field, value in update_data.items():
        old_value = getattr(group, field)
        if old_value != value:
            changed_fields[field] = {"old": old_value, "new": value}
        setattr(group, field, value)
    
    await db.commit()
    await db.refresh(group)

    if changed_fields:
        await safe_record_activity(
            user=current_user,
            action_key="group_updated",
            action_label="Updated Group",
            category="subjects",
            source_area="teacher_subjects",
            entity_type="group",
            entity_id=group.id,
            entity_name=group.name,
            group_id=group.id,
            group_name=group.name,
            details={
                "changes": changed_fields,
                "previous_name": previous_name,
                "previous_parent_id": previous_parent_id,
            },
            request=request,
        )
    return SubjectGroupResponse.model_validate(group)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    request: Request,
    move_subjects_to_root: bool = Query(True, description="Move direct subjects one level up instead of relying on DB nulling"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a subject group and lift direct children and subjects one level up."""
    ensure_user_can_manage_groups(current_user)

    result = await db.execute(
        select(SubjectGroup).where(SubjectGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    
    parent_group_id = group.parent_id
    deleted_group_name = group.name

    # Re-parent direct child groups to the deleted group's parent so hierarchy is lifted by one level.
    children_result = await db.execute(
        select(SubjectGroup)
        .where(SubjectGroup.parent_id == group_id)
        .order_by(SubjectGroup.order_index, SubjectGroup.created_at)
    )
    direct_children = children_result.scalars().all()
    if direct_children:
        max_order_result = await db.execute(
            select(func.max(SubjectGroup.order_index)).where(
                SubjectGroup.parent_id == parent_group_id,
                SubjectGroup.id != group_id,
            )
        )
        max_order = max_order_result.scalar_one()
        next_order = (max_order if max_order is not None else -1) + 1
        for child in direct_children:
            child.parent_id = parent_group_id
            child.order_index = next_order
            next_order += 1

    if move_subjects_to_root:
        # Move subjects from the deleted group to its parent (or root if parent is null).
        await db.execute(
            update(Subject).where(Subject.group_id == group_id).values(group_id=parent_group_id)
        )

    # Persist re-parenting before deleting parent, otherwise DB-level ON DELETE CASCADE
    # can remove children first and cause stale-row updates during commit flush.
    await db.flush()

    # Use SQL delete to avoid ORM relationship cascade deleting re-parented child groups.
    await db.execute(delete(SubjectGroup).where(SubjectGroup.id == group_id))
    await db.commit()

    await safe_record_activity(
        user=current_user,
        action_key="group_deleted",
        action_label="Deleted Group",
        category="subjects",
        source_area="teacher_subjects",
        entity_type="group",
        entity_id=group_id,
        entity_name=deleted_group_name,
        group_id=group_id,
        group_name=deleted_group_name,
        details={
            "move_subjects_to_root": move_subjects_to_root,
            "parent_group_id": parent_group_id,
            "moved_child_groups": len(direct_children),
        },
        request=request,
    )


@router.post("/groups/{group_id}/move", response_model=SubjectGroupResponse)
async def move_group(
    group_id: str,
    request: Request,
    new_parent_id: Optional[str] = Query(None, description="New parent group ID, or null for root"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Move a group to a new parent (or root)."""
    ensure_user_can_manage_groups(current_user)

    result = await db.execute(
        select(SubjectGroup).where(SubjectGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    
    previous_parent_id = group.parent_id
    previous_parent_name = None
    if previous_parent_id:
        previous_parent_result = await db.execute(select(SubjectGroup.name).where(SubjectGroup.id == previous_parent_id))
        previous_parent_name = previous_parent_result.scalar_one_or_none()

    new_parent_name = None

    # Validate new parent
    if new_parent_id:
        if new_parent_id == group_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A group cannot be its own parent",
            )
        
        parent_result = await db.execute(
            select(SubjectGroup).where(SubjectGroup.id == new_parent_id)
        )
        parent_group = parent_result.scalar_one_or_none()
        if not parent_group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="New parent group not found",
            )
        new_parent_name = parent_group.name
        
        # Check for circular reference
        current_parent_id = new_parent_id
        while current_parent_id:
            if current_parent_id == group_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot move group into its own descendant",
                )
            parent_check = await db.execute(
                select(SubjectGroup.parent_id).where(SubjectGroup.id == current_parent_id)
            )
            current_parent_id = parent_check.scalar_one_or_none()
    
    # Get max order_index for new siblings
    sibling_query = select(func.max(SubjectGroup.order_index)).where(
        SubjectGroup.parent_id == new_parent_id
    )
    max_order_result = await db.execute(sibling_query)
    max_order = max_order_result.scalar_one() or -1
    
    group.parent_id = new_parent_id
    group.order_index = max_order + 1
    
    await db.commit()
    await db.refresh(group)

    await safe_record_activity(
        user=current_user,
        action_key="group_moved",
        action_label="Moved Group",
        category="subjects",
        source_area="teacher_subjects",
        entity_type="group",
        entity_id=group.id,
        entity_name=group.name,
        group_id=group.id,
        group_name=group.name,
        details={
            "previous_parent_id": previous_parent_id,
            "previous_parent_name": previous_parent_name,
            "new_parent_id": new_parent_id,
            "new_parent_name": new_parent_name,
        },
        request=request,
    )
    return SubjectGroupResponse.model_validate(group)


# ============== Subject Detail Endpoints ==============

@router.get("/{subject_id}", response_model=SubjectDetailResponse)
async def get_subject(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific subject with its topics."""
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
    
    # Compute live question counts per topic (only non-archived, latest version)
    topic_counts_result = await db.execute(
        select(Question.topic_id, func.count(Question.id))
        .where(
            Question.topic_id.isnot(None),
            Question.is_archived == False,
            Question.is_latest == True,
        )
        .group_by(Question.topic_id)
    )
    topic_counts = dict(topic_counts_result.all())

    # Compute live subject-level total (includes questions without a topic)
    subject_count_result = await db.execute(
        select(func.count(Question.id))
        .where(
            Question.subject_id == subject_id,
            Question.is_archived == False,
            Question.is_latest == True,
        )
    )
    live_subject_total = subject_count_result.scalar_one()

    sorted_topics = sorted(subject.topics, key=lambda x: x.order_index)
    topic_responses = []
    for t in sorted_topics:
        tr = TopicResponse.model_validate(t)
        tr.total_questions = topic_counts.get(t.id, 0)
        topic_responses.append(tr)

    subject_resp = SubjectResponse.model_validate(subject)
    subject_resp.total_questions = live_subject_total
    
    # Fetch creator username from auth database (SQLite)
    creator_username = None
    if subject.user_id:
        async with AuthSessionLocal() as auth_db:
            user_result = await auth_db.execute(
                select(User.username).where(User.id == subject.user_id)
            )
            creator_username = user_result.scalar_one_or_none()
    subject_resp.creator_username = creator_username
    
    return SubjectDetailResponse(
        **subject_resp.model_dump(),
        topics=topic_responses
    )


@router.get("/{subject_id}/review-stats", response_model=SubjectReviewStatsResponse)
async def get_subject_review_stats(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return aggregated review stats for a subject and its topics."""
    subject_result = await db.execute(
        select(Subject.id).where(Subject.id == subject_id)
    )
    if not subject_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )

    topics_result = await db.execute(
        select(Topic.id).where(Topic.subject_id == subject_id).order_by(Topic.order_index)
    )
    ordered_topic_ids = [str(topic_id) for topic_id in topics_result.scalars().all()]

    question_counts_result = await db.execute(
        select(
            Question.topic_id,
            func.count(Question.id).label("generated"),
            func.count(case((Question.vetting_status == "approved", 1))).label("approved"),
            func.count(case((Question.vetting_status == "rejected", 1))).label("rejected"),
            func.count(case((Question.vetting_status == "pending", 1))).label("pending"),
        )
        .where(
            Question.subject_id == subject_id,
            Question.is_archived == False,
            Question.is_latest == True,
        )
        .group_by(Question.topic_id)
    )

    counts_by_topic_id: dict[str, dict[str, int]] = {}
    orphan_counts = {
        "generated": 0,
        "approved": 0,
        "rejected": 0,
        "pending": 0,
    }
    for topic_id, generated, approved, rejected, pending in question_counts_result.all():
        counts = {
            "generated": int(generated or 0),
            "approved": int(approved or 0),
            "rejected": int(rejected or 0),
            "pending": int(pending or 0),
        }
        if topic_id is None:
            orphan_counts = counts
        else:
            counts_by_topic_id[str(topic_id)] = counts

    if len(ordered_topic_ids) == 1:
        only_topic_id = ordered_topic_ids[0]
        base_counts = counts_by_topic_id.get(
            only_topic_id,
            {"generated": 0, "approved": 0, "rejected": 0, "pending": 0},
        )
        counts_by_topic_id[only_topic_id] = {
            key: int(base_counts.get(key, 0) or 0) + int(orphan_counts.get(key, 0) or 0)
            for key in ("generated", "approved", "rejected", "pending")
        }

    topic_stats = [
        SubjectTopicReviewStats(
            topic_id=topic_id,
            generated=int(counts_by_topic_id.get(topic_id, {}).get("generated", 0) or 0),
            approved=int(counts_by_topic_id.get(topic_id, {}).get("approved", 0) or 0),
            rejected=int(counts_by_topic_id.get(topic_id, {}).get("rejected", 0) or 0),
            pending=int(counts_by_topic_id.get(topic_id, {}).get("pending", 0) or 0),
        )
        for topic_id in ordered_topic_ids
    ]

    generated_total = sum(item.generated for item in topic_stats) + (0 if len(ordered_topic_ids) == 1 else orphan_counts["generated"])
    approved_total = sum(item.approved for item in topic_stats) + (0 if len(ordered_topic_ids) == 1 else orphan_counts["approved"])
    rejected_total = sum(item.rejected for item in topic_stats) + (0 if len(ordered_topic_ids) == 1 else orphan_counts["rejected"])
    pending_total = sum(item.pending for item in topic_stats) + (0 if len(ordered_topic_ids) == 1 else orphan_counts["pending"])

    return SubjectReviewStatsResponse(
        generated=generated_total,
        approved=approved_total,
        rejected=rejected_total,
        pending=pending_total,
        topics=topic_stats,
    )


@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    subject_data: SubjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a subject."""
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    update_data = subject_data.model_dump(exclude_unset=True)
    
    if "learning_outcomes" in update_data and update_data["learning_outcomes"]:
        update_data["learning_outcomes"] = {"outcomes": [lo.model_dump() for lo in subject_data.learning_outcomes]}
    if "course_outcomes" in update_data and update_data["course_outcomes"]:
        update_data["course_outcomes"] = {"outcomes": [co.model_dump() for co in subject_data.course_outcomes]}
    
    for field, value in update_data.items():
        setattr(subject, field, value)
    
    await db.commit()
    await db.refresh(subject)
    return SubjectResponse.model_validate(subject)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a subject and all its topics."""
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
        )
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    await db.delete(subject)
    await db.commit()


# ============== Topic Endpoints ==============

@router.post("/{subject_id}/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    subject_id: str,
    request: Request,
    topic_data: TopicCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new topic in a subject."""
    # Verify subject exists (shared across teachers)
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    topic = Topic(
        subject_id=subject_id,
        name=topic_data.name,
        description=topic_data.description,
        order_index=topic_data.order_index,
        syllabus_content=getattr(topic_data, 'syllabus_content', None),
        has_syllabus=bool(getattr(topic_data, 'syllabus_content', None)),
    )
    db.add(topic)
    
    # Update subject topic count
    subject.total_topics += 1
    
    await db.commit()
    await db.refresh(topic)

    # Trigger LO+CO regeneration if syllabus content was provided
    if getattr(topic_data, 'syllabus_content', None):
        background_tasks.add_task(_bg_generate_los, subject_id=subject_id, user_id=current_user.id)
        background_tasks.add_task(_bg_generate_cos, subject_id=subject_id, user_id=current_user.id)

    await safe_record_activity(
        user=current_user,
        action_key="topic_created",
        action_label="Created Topic",
        category="topics",
        source_area="teacher_subjects",
        entity_type="topic",
        entity_id=topic.id,
        entity_name=topic.name,
        subject_id=subject.id,
        subject_name=subject.name,
        topic_id=topic.id,
        topic_name=topic.name,
        details={
            "order_index": topic.order_index,
            "has_syllabus": bool(topic.has_syllabus),
        },
        request=request,
    )

    return TopicResponse.model_validate(topic)


@router.get("/{subject_id}/topics", response_model=TopicListResponse)
async def list_topics(
    subject_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all topics for a subject."""
    # Verify subject exists (shared across teachers)
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    query = select(Topic).where(Topic.subject_id == subject_id)
    
    # Count total
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()
    
    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Topic.order_index)
    
    result = await db.execute(query)
    topics = result.scalars().all()
    
    # Compute live question counts per topic (only non-archived)
    topic_ids = [t.id for t in topics]
    if topic_ids:
        topic_counts_result = await db.execute(
            select(Question.topic_id, func.count(Question.id))
            .where(
                Question.topic_id.in_(topic_ids),
                Question.is_archived == False,
            Question.vetting_status == "approved",
            )
            .group_by(Question.topic_id)
        )
        topic_counts = dict(topic_counts_result.all())
    else:
        topic_counts = {}

    topic_responses = []
    for t in topics:
        tr = TopicResponse.model_validate(t)
        tr.total_questions = topic_counts.get(t.id, 0)
        topic_responses.append(tr)

    return TopicListResponse(
        topics=topic_responses,
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        }
    )


@router.put("/{subject_id}/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    subject_id: str,
    topic_id: str,
    request: Request,
    topic_data: TopicUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a topic."""
    # Verify subject exists (shared across teachers)
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    result = await db.execute(
        select(Topic).where(
            Topic.id == topic_id,
            Topic.subject_id == subject_id,
        )
    )
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    update_data = topic_data.model_dump(exclude_unset=True)
    changed_fields = {}
    
    # Record audit entries for each changed field
    user_name = current_user.full_name or current_user.username or "Unknown"
    audit_field_map = {
        "name": "topic_name",
        "description": "description",
        "syllabus_content": "syllabus_content",
    }
    for field, value in update_data.items():
        audit_field = audit_field_map.get(field)
        if audit_field:
            old_val = getattr(topic, field, None)
            new_val = value
            # Only log if the value actually changed
            if str(old_val or "") != str(new_val or ""):
                changed_fields[field] = {"old": old_val, "new": new_val}
                db.add(TopicAuditLog(
                    topic_id=topic_id,
                    user_id=current_user.id,
                    user_name=user_name,
                    action="update",
                    field_name=audit_field,
                    old_value=str(old_val)[:2000] if old_val else None,
                    new_value=str(new_val)[:2000] if new_val else None,
                ))
        setattr(topic, field, value)
    
    await db.commit()
    await db.refresh(topic)

    if changed_fields:
        await safe_record_activity(
            user=current_user,
            action_key="topic_updated",
            action_label="Updated Topic",
            category="topics",
            source_area="teacher_subjects",
            entity_type="topic",
            entity_id=topic.id,
            entity_name=topic.name,
            subject_id=subject.id,
            subject_name=subject.name,
            topic_id=topic.id,
            topic_name=topic.name,
            details={"changes": changed_fields},
            request=request,
        )
    return TopicResponse.model_validate(topic)


@router.get("/topics/{topic_id}/audit-log")
async def get_topic_audit_log(
    topic_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get audit log entries for a topic (for the History tab)."""
    # Verify topic exists
    result = await db.execute(
        select(Topic).where(Topic.id == topic_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    # Count total entries
    count_result = await db.execute(
        select(func.count()).where(TopicAuditLog.topic_id == topic_id)
    )
    total = count_result.scalar_one()
    
    # Paginate, newest first
    offset = (page - 1) * limit
    result = await db.execute(
        select(TopicAuditLog)
        .where(TopicAuditLog.topic_id == topic_id)
        .order_by(TopicAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    entries = result.scalars().all()
    
    return {
        "entries": [
            {
                "id": e.id,
                "topic_id": e.topic_id,
                "user_name": e.user_name,
                "action": e.action,
                "field_name": e.field_name,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        },
    }


@router.delete("/{subject_id}/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    subject_id: str,
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a topic."""
    # Verify subject exists (shared across teachers)
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    result = await db.execute(
        select(Topic).where(
            Topic.id == topic_id,
            Topic.subject_id == subject_id,
        )
    )
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    await db.delete(topic)
    subject.total_topics = max(0, subject.total_topics - 1)
    await db.commit()


@router.post("/{subject_id}/topics/{topic_id}/upload-syllabus", response_model=TopicResponse)
async def upload_topic_syllabus(
    subject_id: str,
    topic_id: str,
    request: Request,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document (PDF, DOCX, TXT) and extract its content as syllabus for the topic.
    The extracted text will be saved to the topic's syllabus_content field.
    """
    # Verify subject exists (shared across teachers)
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    # Get topic
    result = await db.execute(
        select(Topic).where(
            Topic.id == topic_id,
            Topic.subject_id == subject_id,
        )
    )
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    # Validate file extension
    filename = file.filename or "document"
    ext = os.path.splitext(filename)[1].lower()
    
    allowed_extensions = [".pdf", ".txt", ".docx"]
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size (10MB limit)
    max_size_mb = 10
    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_size_mb}MB",
        )
    
    # Extract text based on file type
    try:
        text_content = await _extract_text_from_file(content, ext)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract text from file: {str(e)}",
        )
    
    if not text_content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text content could be extracted from the file",
        )
    
    # Update topic with extracted content
    topic.syllabus_content = text_content
    topic.has_syllabus = True
    
    # Update subject syllabus coverage
    total_topics_result = await db.execute(
        select(func.count()).where(Topic.subject_id == subject_id)
    )
    total_topics = total_topics_result.scalar_one()
    
    topics_with_syllabus_result = await db.execute(
        select(func.count()).where(
            Topic.subject_id == subject_id,
            Topic.has_syllabus == True,
        )
    )
    topics_with_syllabus = topics_with_syllabus_result.scalar_one()
    
    if total_topics > 0:
        subject.syllabus_coverage = (topics_with_syllabus / total_topics) * 100
    
    await db.commit()
    await db.refresh(topic)

    # Trigger LO and CO generation in the background so upload response is instant
    background_tasks.add_task(_bg_generate_los, subject_id=subject_id, user_id=current_user.id)
    background_tasks.add_task(_bg_generate_cos, subject_id=subject_id, user_id=current_user.id)

    await safe_record_activity(
        user=current_user,
        action_key="topic_syllabus_uploaded",
        action_label="Uploaded Topic Syllabus",
        category="topics",
        source_area="teacher_subjects",
        entity_type="topic",
        entity_id=topic.id,
        entity_name=topic.name,
        subject_id=subject.id,
        subject_name=subject.name,
        topic_id=topic.id,
        topic_name=topic.name,
        details={
            "filename": filename,
            "file_extension": ext,
            "bytes": len(content),
        },
        request=request,
    )

    return TopicResponse.model_validate(topic)


async def _bg_generate_los(subject_id: str, user_id: str) -> None:
    """Background task: regenerate LOs for a subject after new syllabus content is added."""
    from app.core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            subj_result = await db.execute(
                select(Subject).where(Subject.id == subject_id)
            )
            subject = subj_result.scalar_one_or_none()
            if not subject:
                return

            topics_result = await db.execute(
                select(Topic).where(Topic.subject_id == subject_id).order_by(Topic.order_index)
            )
            topics = topics_result.scalars().all()

            parts = []
            for t in topics:
                if t.syllabus_content:
                    parts.append(f"Chapter: {t.name}\n{t.syllabus_content[:1500]}")
                else:
                    parts.append(f"Chapter: {t.name}")
            combined = "\n\n".join(parts).strip()

            if len(combined) > 100:
                los = await _generate_los_with_llm(subject.name, subject.code, combined)
            else:
                los = list(_GENERIC_LOS)

            subject.learning_outcomes = {"outcomes": los}

            # Map LOs to individual topics based on content relevance
            for t in topics:
                topic_text = (t.syllabus_content or t.name or "").lower()
                mapped_los = []
                for lo in los:
                    lo_desc = (lo.get("description") or lo.get("name") or "").lower()
                    # Simple keyword overlap check
                    lo_words = set(lo_desc.split()) - {"the", "a", "an", "and", "or", "of", "to", "in", "for", "is", "are", "be"}
                    topic_words = set(topic_text.split()) - {"the", "a", "an", "and", "or", "of", "to", "in", "for", "is", "are", "be"}
                    overlap = len(lo_words & topic_words)
                    if overlap >= 2 or len(los) <= 3:
                        mapped_los.append({"id": lo.get("id"), "name": lo.get("name"), "level": 2})
                if not mapped_los and los:
                    # At least map the first LO
                    mapped_los.append({"id": los[0].get("id"), "name": los[0].get("name"), "level": 1})
                t.learning_outcome_mappings = {"mapped_outcomes": mapped_los}

            await db.commit()
            logger.info(f"Background LO generation complete for subject {subject_id}")
    except Exception as e:
        logger.error(f"Background LO generation failed for subject {subject_id}: {e}")


async def _bg_generate_cos(subject_id: str, user_id: str) -> None:
    """Background task: regenerate COs for a subject after new syllabus content is added."""
    from app.core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            subj_result = await db.execute(
                select(Subject).where(Subject.id == subject_id)
            )
            subject = subj_result.scalar_one_or_none()
            if not subject:
                return

            topics_result = await db.execute(
                select(Topic).where(Topic.subject_id == subject_id).order_by(Topic.order_index)
            )
            topics = topics_result.scalars().all()

            parts = []
            for t in topics:
                if t.syllabus_content:
                    parts.append(f"Chapter: {t.name}\n{t.syllabus_content[:1500]}")
                else:
                    parts.append(f"Chapter: {t.name}")
            combined = "\n\n".join(parts).strip()

            # Include LOs if already generated
            los_text = ""
            if subject.learning_outcomes and subject.learning_outcomes.get("outcomes"):
                los_text = "\n\nExisting Learning Outcomes:\n" + "\n".join(
                    f"- {lo.get('id', '')}: {lo.get('description', lo.get('name', ''))}"
                    for lo in subject.learning_outcomes["outcomes"]
                )

            if len(combined) > 100:
                cos = await _generate_cos_with_llm(
                    subject.name, 
                    subject.code, 
                    combined + los_text,
                    user_id=subject.user_id,
                    subject_id=subject_id,
                )
            else:
                cos = list(_GENERIC_COS)

            subject.course_outcomes = {"outcomes": cos}
            await db.commit()
            logger.info(f"Background CO generation complete for subject {subject_id}")
    except Exception as e:
        logger.error(f"Background CO generation failed for subject {subject_id}: {e}")


_GENERIC_COS = [
    {"id": "CO1", "name": "Foundational Knowledge",
     "description": "Demonstrate understanding of core concepts, terminology, and principles of the subject."},
    {"id": "CO2", "name": "Problem Solving",
     "description": "Apply subject knowledge to analyse and solve standard and complex problems."},
    {"id": "CO3", "name": "Critical Thinking",
     "description": "Evaluate different approaches, identify limitations, and justify conclusions with evidence."},
    {"id": "CO4", "name": "Design & Implementation",
     "description": "Design solutions or systems by integrating concepts from multiple topics within the subject."},
    {"id": "CO5", "name": "Professional Practice",
     "description": "Communicate technical ideas effectively and apply ethical reasoning in professional contexts."},
]


async def _generate_cos_with_llm(
    subject_name: str, 
    subject_code: str, 
    syllabus_text: str,
    user_id: Optional[str] = None,
    subject_id: Optional[str] = None,
) -> list:
    """Use LLM to derive 4-6 Course Outcomes from aggregated syllabus content; falls back to generic COs."""
    # Use the active AI provider from database instead of environment variable
    provider_svc = get_provider_service()
    try:
        enabled_providers = await provider_svc.get_enabled_providers()
        if not enabled_providers:
            logger.warning("No enabled providers configured, falling back to generic COs")
            return _GENERIC_COS
        llm_service, provider_metadata = provider_svc.create_llm_service(enabled_providers[0])
    except Exception as e:
        logger.error(f"Failed to create LLM service for CO generation: {e}")
        return _GENERIC_COS
    
    truncated = syllabus_text[:12000]

    system_prompt = (
        "You are an expert curriculum designer specialising in Outcome-Based Education (OBE). "
        "Generate 4 to 6 Course Outcomes (COs) for a university subject from its syllabus.\n\n"
        "Course Outcomes are broader than Learning Outcomes — they define what a student should be able to DO "
        "at the end of the entire course. They map to Programme Outcomes (POs) and are used in OBE accreditation.\n\n"
        "Each CO must:\n"
        "- Be specific to this subject's domain\n"
        "- Start with an action verb aligned to Bloom's taxonomy (e.g. Demonstrate, Apply, Analyse, Design, Evaluate)\n"
        "- Be measurable and assessable through exams or assignments\n"
        "- Cover a distinct competency area of the course\n\n"
        "Return ONLY a valid JSON array:\n"
        '[{"id":"CO1","name":"Short 2-5 word label","description":"Full CO statement."},...]\n'
        "No markdown, no extra text."
    )
    prompt = (
        f"Subject: {subject_name} ({subject_code})\n\n"
        f"Syllabus and context:\n{truncated}\n\n"
        "Generate 4-6 specific, measurable Course Outcomes."
    )

    try:
        result = await llm_service.generate_json(prompt=prompt, system_prompt=system_prompt, temperature=0.3)
        
        # Track provider usage (non-blocking)
        if user_id and provider_metadata:
            from app.services.provider_usage_tracking_service import provider_usage_tracker
            provider_usage_tracker.track_usage(
                provider_key=provider_metadata.get("provider_key", "unknown"),
                user_id=user_id,
                usage_type="course_outcomes_generation",
                provider_name=provider_metadata.get("provider"),
                provider_model=provider_metadata.get("llm_model"),
                subject_id=subject_id,
                usage_metadata={"action": "generate_course_outcomes", "subject_name": subject_name},
            )
        
        cos_raw = result if isinstance(result, list) else next(
            (v for v in result.values() if isinstance(v, list)), None
        )
        if not cos_raw:
            return _GENERIC_COS
        validated = []
        for i, co in enumerate(cos_raw[:6], start=1):
            if isinstance(co, dict):
                validated.append({
                    "id": str(co.get("id") or f"CO{i}")[:10],
                    "name": str(co.get("name") or f"CO{i}")[:100],
                    "description": str(co["description"])[:500] if co.get("description") else None,
                })
        return validated or _GENERIC_COS
    except Exception as e:
        logger.error(f"CO generation LLM failed: {e}")
        return _GENERIC_COS


async def _extract_text_from_file(content: bytes, extension: str) -> str:
    """Extract text from file content based on file type.

    For PDFs, native text extraction is attempted first (PyMuPDF).
    If the result is too sparse (scanned/image-based PDF), OCR via
    pytesseract is used as a fallback on a page-by-page basis.
    """

    if extension == ".pdf":
        import fitz  # PyMuPDF
        text_parts = []
        ocr_pages = []  # pages where native extraction yielded nothing

        with fitz.open(stream=content, filetype="pdf") as doc:
            for page_num, page in enumerate(doc):
                native = page.get_text().strip()
                if native:
                    text_parts.append(native)
                else:
                    # Render page to image for OCR
                    ocr_pages.append((page_num, page.get_pixmap(dpi=200)))

        native_text = "\n\n".join(text_parts)

        # If we have OCR pages (scanned PDF or mixed)
        if ocr_pages:
            try:
                import pytesseract
                from PIL import Image
                import io as _io

                ocr_parts = []
                for page_num, pix in ocr_pages:
                    img_bytes = pix.tobytes("png")
                    img = Image.open(_io.BytesIO(img_bytes))
                    ocr_text = pytesseract.image_to_string(img, lang="eng").strip()
                    if ocr_text:
                        ocr_parts.append(ocr_text)

                if ocr_parts:
                    ocr_combined = "\n\n".join(ocr_parts)
                    return (native_text + "\n\n" + ocr_combined).strip() if native_text else ocr_combined
            except Exception as e:
                logger.warning(f"OCR fallback failed for PDF: {e}")

        return native_text

    elif extension == ".txt":
        return content.decode("utf-8", errors="ignore")

    elif extension == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(content))
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        return "\n\n".join(text_parts)

    return ""


async def _extract_chapters_with_llm(text_content: str, subject_name: str, subject_code: str) -> List[dict]:
    """
    Use LLM to intelligently extract chapters/topics from syllabus text.
    Returns a list of dicts with 'name', 'description', and optionally 'syllabus_content'.
    """
    llm_service, _ = await create_llm_service_for_active_provider()
    
    # Truncate text if too long (LLMs have context limits)
    max_chars = 15000
    truncated_text = text_content[:max_chars] if len(text_content) > max_chars else text_content
    
    system_prompt = """You are an expert curriculum analyzer. Your task is to extract chapters/topics/units from a syllabus document.

For each chapter you identify:
1. Extract the chapter/topic/unit name
2. Extract or summarize a brief description
3. Include the relevant syllabus content for that chapter

Return your response as a valid JSON array of objects with the following structure:
[
  {
    "name": "Introduction to Subject",
    "description": "Brief overview of the chapter content",
    "syllabus_content": "Detailed syllabus content for this chapter"
  }
]

Guidelines:
- Extract ALL chapters/units/modules mentioned in the syllabus
- Maintain the original order from the syllabus
- Name field must be ONLY the clean topic title
- DO NOT include numbering/prefixes like "Chapter 1", "CHAPTER II", "Unit 3", "Module 4" in name
- Keep the syllabus_content detailed and accurate
- DO NOT omit chapters even if they seem minor or have sparse content
- DO NOT leave syllabus_content empty, you must add some relevant info related to the subject
- If no clear chapter divisions exist, group related topics logically
- Return ONLY the JSON array, no other text"""

    prompt = f"""Analyze the following syllabus for the subject "{subject_name}" (Code: {subject_code}) and extract all chapters/topics/units:

SYLLABUS CONTENT:
{truncated_text}

Extract all chapters with their names, descriptions, and content.
Important: for each "name", return only the topic title without chapter/unit/module prefixes or numbering.
Return as a JSON array."""

    try:
        result = await llm_service.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,  # Low temperature for more deterministic extraction
        )
        
        # Handle both array and object with 'chapters' key
        if isinstance(result, list):
            chapters = result
        elif isinstance(result, dict) and 'chapters' in result:
            chapters = result['chapters']
        else:
            # Try to find an array in the result
            for key, value in result.items():
                if isinstance(value, list):
                    chapters = value
                    break
            else:
                chapters = []
        
        def normalize_topic_name(raw_name: str) -> str:
            """
            Normalize extracted chapter/topic names by removing leading
            chapter/unit numbering prefixes like:
            - "UNIT 1:"
            - "Unit II -"
            - "CHAPTER 3."
            """
            name = (raw_name or '').strip()

            # Repeatedly remove leading labels such as
            # "UNIT II:", "CHAPTER 1 -", "MODULE 3)"
            prefix_pattern = re.compile(
                r"^\s*(?:unit|chapter|module)\s*(?:\d+|[ivxlcdm]+)\s*[:.\-)\]]*\s*",
                flags=re.IGNORECASE,
            )
            while True:
                next_name = prefix_pattern.sub('', name, count=1).strip()
                if next_name == name:
                    break
                name = next_name

            # Remove any leftover leading numeric outline (e.g., "1. ", "2) ")
            name = re.sub(r"^\s*\d+\s*[:.\-)\]]\s*", '', name).strip()
            return name

        # Validate and clean chapters
        validated_chapters = []
        for chapter in chapters:
            if isinstance(chapter, dict) and 'name' in chapter:
                cleaned_name = normalize_topic_name(str(chapter.get('name', 'Untitled Chapter')))
                if not cleaned_name:
                    continue
                validated_chapters.append({
                    'name': cleaned_name[:255],
                    'description': str(chapter.get('description', ''))[:1000] if chapter.get('description') else None,
                    'syllabus_content': str(chapter.get('syllabus_content', '')) if chapter.get('syllabus_content') else None,
                })
            elif isinstance(chapter, list) and len(chapter) >= 1:
                # LLM returned positional strings instead of a keyed object.
                # Positions: 0 = name, 1 = description, 2 = syllabus_content
                name_val = normalize_topic_name(str(chapter[0]).strip() if chapter[0] else 'Untitled Chapter')
                if not name_val:
                    continue
                validated_chapters.append({
                    'name': name_val[:255],
                    'description': str(chapter[1])[:1000] if len(chapter) > 1 and chapter[1] else None,
                    'syllabus_content': str(chapter[2]) if len(chapter) > 2 and chapter[2] else None,
                })
            elif isinstance(chapter, str) and chapter.strip():
                # Bare string — use as name only
                cleaned_name = normalize_topic_name(chapter.strip())
                if not cleaned_name:
                    continue
                validated_chapters.append({
                    'name': cleaned_name[:255],
                    'description': None,
                    'syllabus_content': None,
                })
        
        return validated_chapters
        
    except Exception as e:
        logger.error(f"LLM chapter extraction failed: {e}")
        raise


@router.post("/{subject_id}/extract-chapters")
async def extract_chapters_from_syllabus(
    subject_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a syllabus PDF/DOCX/TXT and use AI to automatically extract and create chapters.
    
    This endpoint:
    1. Extracts text from the uploaded document
    2. Uses LLM to identify chapters/topics from the syllabus
    3. Creates Topic entries for each identified chapter
    4. Returns the list of created topics
    """
    ensure_user_can_generate(current_user)

    # Verify subject exists (shared across teachers)
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    # Validate file extension
    filename = file.filename or "document"
    ext = os.path.splitext(filename)[1].lower()
    
    allowed_extensions = [".pdf", ".txt", ".docx"]
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size (15MB limit for syllabus)
    max_size_mb = settings.MAX_UPLOAD_SIZE_MB
    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_size_mb}MB",
        )
    
    # Extract text from document
    try:
        text_content = await _extract_text_from_file(content, ext)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract text from file: {str(e)}",
        )
    
    if not text_content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text content could be extracted from the file",
        )
    
    # Use LLM to extract chapters
    try:
        chapters = await _extract_chapters_with_llm(
            text_content=text_content,
            subject_name=subject.name,
            subject_code=subject.code,
        )
    except Exception as e:
        logger.error(f"LLM extraction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI failed to extract chapters: {str(e)}",
        )
    
    if not chapters:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No chapters could be identified in the document. Please ensure the file contains a valid syllabus structure.",
        )
    
    # Get current max order_index for existing topics
    existing_topics_result = await db.execute(
        select(func.max(Topic.order_index)).where(Topic.subject_id == subject_id)
    )
    max_order = existing_topics_result.scalar_one() or -1
    
    # Create topics for each extracted chapter
    created_topics = []
    for idx, chapter in enumerate(chapters):
        topic = Topic(
            subject_id=subject_id,
            name=chapter['name'],
            description=chapter.get('description'),
            order_index=max_order + 1 + idx,
            has_syllabus=bool(chapter.get('syllabus_content')),
            syllabus_content=chapter.get('syllabus_content'),
        )
        db.add(topic)
        created_topics.append(topic)
    
    # Update subject stats
    subject.total_topics += len(created_topics)
    
    # Recalculate syllabus coverage
    total_topics_result = await db.execute(
        select(func.count()).where(Topic.subject_id == subject_id)
    )
    # Add the new topics we just created (they haven't been committed yet)
    total_topics = total_topics_result.scalar_one() + len(created_topics)
    
    topics_with_syllabus_count = sum(1 for t in created_topics if t.has_syllabus)
    existing_with_syllabus_result = await db.execute(
        select(func.count()).where(
            Topic.subject_id == subject_id,
            Topic.has_syllabus == True,
        )
    )
    total_with_syllabus = existing_with_syllabus_result.scalar_one() + topics_with_syllabus_count
    
    if total_topics > 0:
        subject.syllabus_coverage = int((total_with_syllabus / total_topics) * 100)
    
    await db.commit()
    
    # Refresh topics to get their IDs
    for topic in created_topics:
        await db.refresh(topic)
    
    return {
        "message": f"Successfully extracted {len(created_topics)} chapters from syllabus",
        "chapters_created": len(created_topics),
        "topics": [TopicResponse.model_validate(t) for t in created_topics],
    }


# ── Learning Outcomes auto-generation ───────────────────────────────────────

_GENERIC_LOS = [
    {"id": "LO1", "name": "Knowledge & Understanding",
     "description": "Recall and explain fundamental concepts, theories, and principles of the subject."},
    {"id": "LO2", "name": "Application",
     "description": "Apply acquired knowledge and techniques to solve standard problems in the domain."},
    {"id": "LO3", "name": "Analysis & Evaluation",
     "description": "Analyse complex scenarios, interpret data, and critically evaluate proposed solutions."},
    {"id": "LO4", "name": "Synthesis & Design",
     "description": "Design and construct solutions or systems by integrating knowledge from multiple areas."},
    {"id": "LO5", "name": "Communication",
     "description": "Communicate ideas, methods, and findings clearly in written and oral forms."},
]


async def _generate_los_with_llm(subject_name: str, subject_code: str, syllabus_text: str) -> list:
    """Use LLM to derive 5-7 LOs from aggregated syllabus content; falls back to generic LOs."""
    # Use the active AI provider from database instead of environment variable
    provider_svc = get_provider_service()
    try:
        enabled_providers = await provider_svc.get_enabled_providers()
        if not enabled_providers:
            logger.warning("No enabled providers configured, falling back to generic LOs")
            return _GENERIC_LOS
        llm_service, _ = provider_svc.create_llm_service(enabled_providers[0])
    except Exception as e:
        logger.error(f"Failed to create LLM service for LO generation: {e}")
        return _GENERIC_LOS
    
    truncated = syllabus_text[:12000]

    system_prompt = (
        "You are an expert curriculum designer specialising in Outcome-Based Education (OBE). "
        "Generate 5 to 7 Learning Outcomes (LOs) for a university subject from its syllabus.\n\n"
        "Each LO must:\n"
        "- Be specific to this subject's domain\n"
        "- Start with a Bloom's taxonomy action verb (e.g. Understand, Apply, Analyse, Design, Evaluate)\n"
        "- Be measurable and distinct from the others\n\n"
        "Return ONLY a valid JSON array:\n"
        '[{"id":"LO1","name":"Short 2-5 word label","description":"Full LO statement."},...]\n'
        "No markdown, no extra text."
    )
    prompt = (
        f"Subject: {subject_name} ({subject_code})\n\n"
        f"Syllabus content:\n{truncated}\n\n"
        "Generate 5-7 specific, measurable Learning Outcomes."
    )

    try:
        result = await llm_service.generate_json(prompt=prompt, system_prompt=system_prompt, temperature=0.3)
        los_raw = result if isinstance(result, list) else next(
            (v for v in result.values() if isinstance(v, list)), None
        )
        if not los_raw:
            return _GENERIC_LOS
        validated = []
        for i, lo in enumerate(los_raw[:7], start=1):
            if isinstance(lo, dict):
                validated.append({
                    "id": str(lo.get("id") or f"LO{i}")[:10],
                    "name": str(lo.get("name") or f"LO{i}")[:100],
                    "description": str(lo["description"])[:500] if lo.get("description") else None,
                })
        return validated or _GENERIC_LOS
    except Exception as e:
        logger.error(f"LO generation LLM failed: {e}")
        return _GENERIC_LOS


@router.post("/{subject_id}/generate-learning-outcomes", response_model=SubjectResponse)
async def generate_learning_outcomes(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Auto-generate Learning Outcomes for a subject.

    Content priority (highest → lowest):
    1. Topic syllabus_content (all chapters concatenated)
    2. Reference book chunks linked to this subject (up to 30 chunks × 400 chars each)
    3. Generic fallback LOs if nothing meaningful is found or the LLM fails
    """
    ensure_user_can_generate(current_user)

    subj_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = subj_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    # ── 1. Topic syllabus content ────────────────────────────────────────────
    topics_result = await db.execute(
        select(Topic).where(Topic.subject_id == subject_id).order_by(Topic.order_index)
    )
    topics = topics_result.scalars().all()

    topic_parts = []
    for t in topics:
        if t.syllabus_content:
            topic_parts.append(f"Chapter: {t.name}\n{t.syllabus_content[:1500]}")
        else:
            topic_parts.append(f"Chapter: {t.name}")
    syllabus_text = "\n\n".join(topic_parts)
    has_syllabus = any(t.syllabus_content for t in topics)

    # ── 2. Reference book chunks ─────────────────────────────────────────────
    ref_text = ""
    ref_docs_result = await db.execute(
        select(Document.id, Document.filename).where(
            Document.subject_id == subject_id,
            Document.index_type == "reference_book",
            Document.processing_status == "completed",
        )
    )
    ref_docs = ref_docs_result.all()
    if ref_docs:
        doc_ids = [row.id for row in ref_docs]
        # Pull first 30 meaningful chunks (evenly spread across books)
        chunks_result = await db.execute(
            select(DocumentChunk.chunk_text, Document.filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.document_id.in_(doc_ids))
            .order_by(Document.id, DocumentChunk.chunk_index)
            .limit(60)
        )
        chunk_rows = chunks_result.all()
        # Deduplicate by book, take up to 30 chunks total
        seen_docs: dict = {}
        selected = []
        for chunk_text, filename in chunk_rows:
            seen_docs[filename] = seen_docs.get(filename, 0) + 1
            if seen_docs[filename] <= max(1, 30 // len(doc_ids)):
                selected.append(chunk_text[:400])
            if len(selected) >= 30:
                break
        if selected:
            ref_text = "\n\nREFERENCE BOOK EXCERPTS:\n" + "\n---\n".join(selected)

    combined = (syllabus_text + ref_text).strip()
    has_real_content = has_syllabus or bool(ref_text)

    if has_real_content and len(combined) > 100:
        los = await _generate_los_with_llm(subject.name, subject.code, combined)
    else:
        los = list(_GENERIC_LOS)  # generic fallback

    subject.learning_outcomes = {"outcomes": los}
    await db.commit()
    await db.refresh(subject)
    return SubjectResponse.model_validate(subject)


# ============== Subject Move Endpoint ==============

@router.put("/{subject_id}/move", response_model=SubjectResponse)
async def move_subject(
    subject_id: str,
    request: Request,
    group_id: Optional[str] = Query(None, description="Target group ID, or null for root"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Move a subject to a different group (or root)."""
    ensure_user_can_manage_groups(current_user)

    result = await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    previous_group_id = subject.group_id
    previous_group_name = None
    if previous_group_id:
        previous_group_result = await db.execute(select(SubjectGroup.name).where(SubjectGroup.id == previous_group_id))
        previous_group_name = previous_group_result.scalar_one_or_none()

    target_group_name = None

    # Validate target group if provided
    if group_id:
        group_result = await db.execute(
            select(SubjectGroup).where(SubjectGroup.id == group_id)
        )
        target_group = group_result.scalar_one_or_none()
        if not target_group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target group not found",
            )
        target_group_name = target_group.name
    
    subject.group_id = group_id
    await db.commit()
    await db.refresh(subject)

    await safe_record_activity(
        user=current_user,
        action_key="subject_moved",
        action_label="Moved Subject",
        category="subjects",
        source_area="teacher_subjects",
        entity_type="subject",
        entity_id=subject.id,
        entity_name=subject.name,
        subject_id=subject.id,
        subject_name=subject.name,
        group_id=group_id,
        group_name=target_group_name,
        details={
            "previous_group_id": previous_group_id,
            "previous_group_name": previous_group_name,
            "new_group_id": group_id,
            "new_group_name": target_group_name,
        },
        request=request,
    )
    return SubjectResponse.model_validate(subject)