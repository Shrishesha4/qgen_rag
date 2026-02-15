"""
Rubric API endpoints.
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.rubric import Rubric
from app.models.subject import Subject
from app.models.user import User
from app.schemas.rubric import (
    RubricCreate,
    RubricUpdate,
    RubricResponse,
    RubricListResponse,
    RubricDetailResponse,
)
from app.api.v1.deps import get_current_user


router = APIRouter()


@router.post("", response_model=RubricResponse, status_code=status.HTTP_201_CREATED)
async def create_rubric(
    rubric_data: RubricCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new rubric."""
    # Verify subject ownership
    result = await db.execute(
        select(Subject).where(
            Subject.id == rubric_data.subject_id,
            Subject.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    # Calculate totals
    total_questions = 0
    total_marks = 0
    distribution = {}
    for q_type, config in rubric_data.question_type_distribution.items():
        distribution[q_type] = config.model_dump()
        total_questions += config.count
        total_marks += config.count * config.marks_each
    
    rubric = Rubric(
        user_id=current_user.id,
        subject_id=rubric_data.subject_id,
        name=rubric_data.name,
        exam_type=rubric_data.exam_type,
        duration_minutes=rubric_data.duration_minutes,
        question_type_distribution=distribution,
        learning_outcomes_distribution=rubric_data.learning_outcomes_distribution,
        total_questions=total_questions,
        total_marks=total_marks,
    )
    db.add(rubric)
    await db.commit()
    await db.refresh(rubric)
    return RubricResponse.model_validate(rubric)


@router.get("", response_model=RubricListResponse)
async def list_rubrics(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    subject_id: Optional[uuid.UUID] = Query(None, description="Filter by subject"),
    exam_type: Optional[str] = Query(None, description="Filter by exam type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all rubrics for the current user."""
    query = select(Rubric).where(Rubric.user_id == current_user.id)
    
    if subject_id:
        query = query.where(Rubric.subject_id == subject_id)
    if exam_type:
        query = query.where(Rubric.exam_type == exam_type)
    
    # Count total
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()
    
    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Rubric.created_at.desc())
    
    result = await db.execute(query)
    rubrics = result.scalars().all()
    
    return RubricListResponse(
        rubrics=[RubricResponse.model_validate(r) for r in rubrics],
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        }
    )


@router.get("/{rubric_id}", response_model=RubricDetailResponse)
async def get_rubric(
    rubric_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific rubric."""
    result = await db.execute(
        select(Rubric)
        .options(selectinload(Rubric.subject))
        .where(
            Rubric.id == rubric_id,
            Rubric.user_id == current_user.id,
        )
    )
    rubric = result.scalar_one_or_none()
    
    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rubric not found",
        )
    
    return RubricDetailResponse(
        **RubricResponse.model_validate(rubric).model_dump(),
        subject_name=rubric.subject.name if rubric.subject else None,
        subject_code=rubric.subject.code if rubric.subject else None,
    )


@router.put("/{rubric_id}", response_model=RubricResponse)
async def update_rubric(
    rubric_id: uuid.UUID,
    rubric_data: RubricUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a rubric."""
    result = await db.execute(
        select(Rubric).where(
            Rubric.id == rubric_id,
            Rubric.user_id == current_user.id,
        )
    )
    rubric = result.scalar_one_or_none()
    
    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rubric not found",
        )
    
    update_data = rubric_data.model_dump(exclude_unset=True)
    
    # Recalculate totals if distribution changed
    if "question_type_distribution" in update_data and update_data["question_type_distribution"]:
        total_questions = 0
        total_marks = 0
        distribution = {}
        for q_type, config in rubric_data.question_type_distribution.items():
            distribution[q_type] = config.model_dump()
            total_questions += config.count
            total_marks += config.count * config.marks_each
        update_data["question_type_distribution"] = distribution
        update_data["total_questions"] = total_questions
        update_data["total_marks"] = total_marks
    
    for field, value in update_data.items():
        setattr(rubric, field, value)
    
    await db.commit()
    await db.refresh(rubric)
    return RubricResponse.model_validate(rubric)


@router.delete("/{rubric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rubric(
    rubric_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a rubric."""
    result = await db.execute(
        select(Rubric).where(
            Rubric.id == rubric_id,
            Rubric.user_id == current_user.id,
        )
    )
    rubric = result.scalar_one_or_none()
    
    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rubric not found",
        )
    
    await db.delete(rubric)
    await db.commit()
