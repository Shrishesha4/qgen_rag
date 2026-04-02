"""
Enrollment API endpoints.

Endpoints for:
- Enrolling in a course (free or mock-paid)
- Listing student enrollments
- Updating enrollment progress
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.v1.deps import get_current_user, get_current_student
from app.models.user import User
from app.models.course import (
    Course, Enrollment, Payment,
    CourseStatus, EnrollmentStatus, PaymentStatus,
)
from app.schemas.course import (
    EnrollmentCreate, EnrollmentProgressUpdate,
    EnrollmentResponse, EnrollmentListResponse,
)

router = APIRouter()


def _course_response_load_options():
    return selectinload(Enrollment.course).selectinload(Course.modules)


# ==================== Enrollment ====================


@router.post(
    "/courses/{course_id}/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_in_course(
    course_id: str,
    data: EnrollmentCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Enroll current student in a course. Supports free and mock-payment flows."""
    student_id = str(current_user.id)

    # Verify course exists and is published
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.status != CourseStatus.PUBLISHED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course is not available for enrollment")

    # Check for existing enrollment
    exists = await db.execute(
        select(Enrollment)
        .where(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id,
        )
        .options(_course_response_load_options())
    )
    existing_enrollment = exists.scalar_one_or_none()
    if existing_enrollment:
        response.status_code = status.HTTP_200_OK
        return existing_enrollment

    # Create enrollment
    enrollment = Enrollment(
        student_id=student_id,
        course_id=course_id,
        status=EnrollmentStatus.ACTIVE.value,
        progress_data={"completed_module_ids": [], "quiz_scores": {}},
    )
    db.add(enrollment)
    await db.flush()  # get enrollment.id

    # Create payment record
    if data.payment_provider == "mock" or course.price_cents == 0:
        payment = Payment(
            enrollment_id=enrollment.id,
            student_id=student_id,
            amount_cents=course.price_cents,
            currency=course.currency,
            status=PaymentStatus.COMPLETED.value,
            provider="mock",
            provider_ref=None,
        )
    else:
        # Future: real Razorpay — for now, reject non-mock for paid courses
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only mock payment is supported currently",
        )

    db.add(payment)
    await db.commit()
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.id == enrollment.id)
        .options(_course_response_load_options())
    )
    return result.scalar_one()


@router.get("", response_model=EnrollmentListResponse)
async def list_enrollments(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """List the current student's enrollments."""
    student_id = str(current_user.id)
    filters = [Enrollment.student_id == student_id]
    if status_filter:
        filters.append(Enrollment.status == status_filter)

    where = and_(*filters)
    count_q = select(func.count()).select_from(Enrollment).where(where)
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = (
        select(Enrollment)
        .where(where)
        .order_by(Enrollment.enrolled_at.desc())
        .offset(offset)
        .limit(page_size)
        .options(_course_response_load_options())
    )
    rows = (await db.execute(query)).scalars().all()

    return EnrollmentListResponse(items=rows, total=total)


@router.get("/{enrollment_id}", response_model=EnrollmentResponse)
async def get_enrollment(
    enrollment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get enrollment detail with progress."""
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.id == enrollment_id)
        .options(_course_response_load_options())
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    # Only the enrolled student or admin can view
    if enrollment.student_id != str(current_user.id) and current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return enrollment


@router.patch("/{enrollment_id}/progress", response_model=EnrollmentResponse)
async def update_progress(
    enrollment_id: str,
    data: EnrollmentProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Update enrollment progress (mark modules complete, store quiz scores)."""
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.id == enrollment_id)
        .options(_course_response_load_options())
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    if enrollment.student_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your enrollment")

    progress = enrollment.progress_data or {"completed_module_ids": [], "quiz_scores": {}}

    if data.completed_module_ids is not None:
        existing = set(progress.get("completed_module_ids", []))
        existing.update(data.completed_module_ids)
        progress["completed_module_ids"] = list(existing)

    if data.quiz_scores is not None:
        scores = progress.get("quiz_scores", {})
        scores.update(data.quiz_scores)
        progress["quiz_scores"] = scores

    enrollment.progress_data = progress

    # Auto-complete if all modules done
    if enrollment.course:
        all_module_ids = {m.id for m in enrollment.course.modules}
        completed_ids = set(progress.get("completed_module_ids", []))
        if all_module_ids and all_module_ids <= completed_ids:
            enrollment.status = EnrollmentStatus.COMPLETED.value
            enrollment.completed_at = datetime.now(timezone.utc)

    await db.commit()
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.id == enrollment_id)
        .options(_course_response_load_options())
    )
    return result.scalar_one()
