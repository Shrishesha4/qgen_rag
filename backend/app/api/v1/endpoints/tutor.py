"""
Tutor API — personalized test generation, learning module generation,
and learning profile retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_student
from app.models.user import User
from app.models.course import PersonalizedItem, PersonalizedItemStatus
from app.schemas.course import (
    PersonalizedTestRequest,
    PersonalizedModuleRequest,
    PersonalizedItemResponse,
    LearningProfile,
)
from app.services.learning_history_service import build_learning_profile
from app.services.personalized_generation_service import (
    generate_personalized_test,
    generate_personalized_module,
)

router = APIRouter()


@router.get("/learning-profile", response_model=LearningProfile)
async def get_learning_profile(
    course_id: str | None = None,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Get the student's learning profile aggregated from all history."""
    return await build_learning_profile(db, current_user.id, course_id)


@router.post("/generate-test", response_model=PersonalizedItemResponse)
async def create_personalized_test(
    body: PersonalizedTestRequest,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Generate a one-time personalized test weighted toward weak topics."""
    item = await generate_personalized_test(
        db=db,
        student_id=current_user.id,
        course_id=body.course_id,
        topic_focus=body.topic_focus,
        question_count=body.question_count,
        difficulty_bias=body.difficulty_bias,
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/generate-module", response_model=PersonalizedItemResponse)
async def create_personalized_module(
    body: PersonalizedModuleRequest,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Generate a bespoke learning module targeting a specific topic gap."""
    item = await generate_personalized_module(
        db=db,
        student_id=current_user.id,
        topic_id=body.topic_id,
        course_id=body.course_id,
        focus_areas=body.focus_areas,
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/items", response_model=list[PersonalizedItemResponse])
async def list_personalized_items(
    item_type: str | None = None,
    course_id: str | None = None,
    limit: int = 20,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """List student's personalized items (tests and modules)."""
    from sqlalchemy import select, and_

    filters = [PersonalizedItem.student_id == current_user.id]
    if item_type:
        filters.append(PersonalizedItem.item_type == item_type)
    if course_id:
        filters.append(PersonalizedItem.course_id == course_id)

    query = (
        select(PersonalizedItem)
        .where(and_(*filters))
        .order_by(PersonalizedItem.created_at.desc())
        .limit(min(limit, 50))
    )
    rows = (await db.execute(query)).scalars().all()
    return rows


@router.get("/items/{item_id}", response_model=PersonalizedItemResponse)
async def get_personalized_item(
    item_id: str,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific personalized item."""
    from sqlalchemy import select, and_

    item = (
        await db.execute(
            select(PersonalizedItem).where(
                and_(
                    PersonalizedItem.id == item_id,
                    PersonalizedItem.student_id == current_user.id,
                )
            )
        )
    ).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/items/{item_id}/complete", response_model=PersonalizedItemResponse)
async def complete_personalized_item(
    item_id: str,
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Mark a personalized test or module as completed."""
    from sqlalchemy import select, and_

    item = (
        await db.execute(
            select(PersonalizedItem).where(
                and_(
                    PersonalizedItem.id == item_id,
                    PersonalizedItem.student_id == current_user.id,
                )
            )
        )
    ).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.status = PersonalizedItemStatus.COMPLETED.value
    await db.commit()
    await db.refresh(item)
    return item
