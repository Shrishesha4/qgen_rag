"""
GEL (Graded Error Learning) API endpoints.

Endpoints for:
- Evaluation item management (teacher/admin)
- Assignment management (teacher/admin)
- Student attempt lifecycle
- Dashboard and statistics
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import get_db
from app.api.v1.deps import (
    get_current_user,
    get_current_student,
    get_current_teacher_or_admin,
    get_current_admin,
    get_current_student_or_teacher,
)
from app.models.user import User
from app.services.gel_service import GELService
from app.services.gel_scoring_service import GELScoringService
from app.schemas.gel import (
    EvaluationItemCreate,
    EvaluationItemUpdate,
    EvaluationItemResponse,
    EvaluationItemListResponse,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentResponse,
    AssignmentListResponse,
    StudentAttemptCreate,
    StudentAttemptSubmit,
    StudentAttemptDraft,
    StudentAttemptResponse,
    StudentAttemptListResponse,
    AttemptFeedbackResponse,
    AttemptReviewRequest,
    AttemptReviewResponse,
    StudentDashboardResponse,
    StudentHistoryResponse,
    StudentProgressResponse,
    StudentProfileResponse,
    GELStatisticsResponse,
    BulkEvaluationItemCreate,
    BulkAssignmentItemAdd,
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/gel", tags=["GEL"])


# ==================== Evaluation Items ====================

@router.post("/evaluation-items", response_model=EvaluationItemResponse)
async def create_evaluation_item(
    data: EvaluationItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Create a new evaluation item from a question."""
    service = GELService(db)
    try:
        item = await service.create_evaluation_item(data, str(current_user.id))
        return item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluation-items/bulk", response_model=List[EvaluationItemResponse])
async def bulk_create_evaluation_items(
    data: BulkEvaluationItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Bulk create evaluation items from questions."""
    service = GELService(db)
    items = await service.bulk_create_evaluation_items(
        data.question_ids,
        str(current_user.id),
        data.status,
        data.rubric_id,
    )
    return items


@router.get("/evaluation-items", response_model=EvaluationItemListResponse)
async def list_evaluation_items(
    status: Optional[str] = Query(None),
    subject_id: Optional[uuid.UUID] = Query(None),
    topic_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """List evaluation items with filters."""
    service = GELService(db)
    items, total = await service.list_evaluation_items(
        status=status,
        subject_id=subject_id,
        topic_id=topic_id,
        page=page,
        page_size=page_size,
    )
    return EvaluationItemListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/evaluation-items/{item_id}", response_model=EvaluationItemResponse)
async def get_evaluation_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an evaluation item by ID."""
    service = GELService(db)
    item = await service.get_evaluation_item(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation item not found")
    return item


@router.patch("/evaluation-items/{item_id}", response_model=EvaluationItemResponse)
async def update_evaluation_item(
    item_id: uuid.UUID,
    data: EvaluationItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Update an evaluation item."""
    service = GELService(db)
    item = await service.update_evaluation_item(item_id, data)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation item not found")
    return item


@router.delete("/evaluation-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Delete an evaluation item."""
    service = GELService(db)
    deleted = await service.delete_evaluation_item(item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation item not found")


# ==================== Assignments ====================

@router.post("/assignments", response_model=AssignmentResponse)
async def create_assignment(
    data: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Create a new assignment."""
    service = GELService(db)
    assignment = await service.create_assignment(data, str(current_user.id))
    return assignment


@router.get("/assignments", response_model=AssignmentListResponse)
async def list_assignments(
    status: Optional[str] = Query(None),
    cohort: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """List assignments with filters."""
    service = GELService(db)
    assignments, total = await service.list_assignments(
        status=status,
        cohort=cohort,
        grade=grade,
        page=page,
        page_size=page_size,
    )
    return AssignmentListResponse(
        items=assignments,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an assignment by ID."""
    service = GELService(db)
    assignment = await service.get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


@router.patch("/assignments/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: uuid.UUID,
    data: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Update an assignment."""
    service = GELService(db)
    assignment = await service.update_assignment(assignment_id, data)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


@router.post("/assignments/{assignment_id}/activate", response_model=AssignmentResponse)
async def activate_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Activate an assignment."""
    service = GELService(db)
    assignment = await service.activate_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


@router.post("/assignments/{assignment_id}/close", response_model=AssignmentResponse)
async def close_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Close an assignment."""
    service = GELService(db)
    assignment = await service.close_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


@router.post("/assignments/{assignment_id}/items")
async def add_items_to_assignment(
    assignment_id: uuid.UUID,
    data: BulkAssignmentItemAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Add evaluation items to an assignment."""
    service = GELService(db)
    try:
        added = await service.add_items_to_assignment(
            assignment_id,
            data.evaluation_item_ids,
            data.starting_sequence,
        )
        return {"added": added}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Student Endpoints ====================

@router.get("/student/dashboard", response_model=StudentDashboardResponse)
async def get_student_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Get dashboard data for the current student."""
    service = GELService(db)
    dashboard = await service.get_student_dashboard(
        str(current_user.id),
        cohort=getattr(current_user, 'cohort', None),
        grade=getattr(current_user, 'grade', None),
    )
    
    # Transform for response
    assigned_items = []
    for a in dashboard["assignments"]:
        assignment = a["assignment"]
        # Get items for this assignment
        items = await service.get_assigned_items(str(current_user.id), assignment.id)
        for item in items:
            eval_item = item["evaluation_item"]
            question = item["question"]
            last_attempt = item["attempts"][0] if item["attempts"] else None
            
            assigned_items.append({
                "evaluation_item_id": eval_item.id,
                "assignment_id": assignment.id,
                "assignment_title": assignment.title,
                "question_text": question.question_text if question else "",
                "question_type": question.question_type if question else None,
                "difficulty_label": eval_item.difficulty_label,
                "bloom_level": eval_item.bloom_level,
                "subject_name": None,  # Would need to join
                "topic_name": None,
                "due_date": assignment.scheduled_end,
                "time_limit_minutes": item["time_limit_override"] or assignment.time_limit_minutes,
                "attempts_used": item["attempts_used"],
                "max_attempts": assignment.max_attempts_per_item,
                "last_attempt_status": last_attempt.status if last_attempt else None,
                "last_attempt_score": last_attempt.total_score if last_attempt else None,
            })
    
    return StudentDashboardResponse(
        assigned_items=assigned_items,
        in_progress_count=dashboard["in_progress_count"],
        completed_count=dashboard["completed_count"],
        due_soon_count=dashboard["due_soon_count"],
        average_score=dashboard["average_score"],
    )


@router.get("/student/history", response_model=StudentHistoryResponse)
async def get_student_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """List the student's recent attempts for history view."""
    service = GELService(db)
    history = await service.get_student_history(
        str(current_user.id),
        page=page,
        page_size=page_size,
    )
    return StudentHistoryResponse(**history)


@router.get("/student/progress", response_model=StudentProgressResponse)
async def get_student_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Return aggregated progress metrics for the current student."""
    service = GELService(db)
    return await service.get_student_progress(
        str(current_user.id),
        cohort=getattr(current_user, 'cohort', None),
        grade=getattr(current_user, 'grade', None),
    )


@router.get("/student/profile", response_model=StudentProfileResponse)
async def get_student_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Return student profile with lightweight progress stats."""
    service = GELService(db)
    progress = await service.get_student_progress(
        str(current_user.id),
        cohort=getattr(current_user, 'cohort', None),
        grade=getattr(current_user, 'grade', None),
    )
    return StudentProfileResponse(
        user=UserResponse.model_validate(current_user),
        total_assignments=progress.get("total_assignments", 0),
        completed_attempts=progress.get("completed_attempts", 0),
        average_score=progress.get("average_score"),
        streak_days=progress.get("streak_days", 0),
    )


@router.get("/student/assignments")
async def get_student_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Get assignments available to the current student."""
    service = GELService(db)
    assignments = await service.get_student_assignments(
        str(current_user.id),
        cohort=getattr(current_user, 'cohort', None),
        grade=getattr(current_user, 'grade', None),
    )
    return [
        {
            "id": a["assignment"].id,
            "title": a["assignment"].title,
            "description": a["assignment"].description,
            "scheduled_end": a["assignment"].scheduled_end,
            "item_count": a["item_count"],
            "attempts_made": a["attempts_made"],
        }
        for a in assignments
    ]


@router.get("/student/assignments/{assignment_id}/items")
async def get_assignment_items_for_student(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Get items in an assignment for the current student."""
    service = GELService(db)
    items = await service.get_assigned_items(str(current_user.id), assignment_id)
    return [
        {
            "evaluation_item_id": item["evaluation_item"].id,
            "sequence_number": item["sequence_number"],
            "question_text": item["question"].question_text if item["question"] else "",
            "question_type": item["question"].question_type if item["question"] else None,
            "options": item["question"].options if item["question"] else None,
            "difficulty_label": item["evaluation_item"].difficulty_label,
            "bloom_level": item["evaluation_item"].bloom_level,
            "attempts_used": item["attempts_used"],
            "last_attempt_status": item["attempts"][0].status if item["attempts"] else None,
        }
        for item in items
    ]


# ==================== Attempts ====================

@router.post("/attempts", response_model=StudentAttemptResponse)
async def start_attempt(
    data: StudentAttemptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Start a new attempt on an evaluation item."""
    service = GELService(db)
    try:
        attempt = await service.start_attempt(str(current_user.id), data)
        return attempt
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/attempts/{attempt_id}/draft", response_model=StudentAttemptResponse)
async def save_attempt_draft(
    attempt_id: uuid.UUID,
    data: StudentAttemptDraft,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Save a draft of an attempt."""
    service = GELService(db)
    try:
        attempt = await service.save_draft(attempt_id, str(current_user.id), data)
        return attempt
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/attempts/{attempt_id}/submit")
async def submit_attempt(
    attempt_id: uuid.UUID,
    data: StudentAttemptSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Submit an attempt for scoring."""
    service = GELService(db)
    try:
        result = await service.submit_attempt(attempt_id, str(current_user.id), data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/attempts/{attempt_id}", response_model=StudentAttemptResponse)
async def get_attempt(
    attempt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an attempt by ID."""
    service = GELService(db)
    
    # Students can only see their own attempts
    student_id = str(current_user.id) if current_user.role == "student" else None
    attempt = await service.get_attempt(attempt_id, student_id)
    
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return attempt


@router.get("/attempts/{attempt_id}/feedback", response_model=AttemptFeedbackResponse)
async def get_attempt_feedback(
    attempt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """Get feedback for an attempt."""
    service = GELService(db)
    try:
        feedback = await service.get_attempt_feedback(attempt_id, str(current_user.id))
        return feedback
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/student/attempts", response_model=StudentAttemptListResponse)
async def list_student_attempts(
    assignment_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_student),
):
    """List attempts for the current student."""
    service = GELService(db)
    attempts, total = await service.list_student_attempts(
        str(current_user.id),
        assignment_id=assignment_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return StudentAttemptListResponse(
        items=attempts,
        total=total,
        page=page,
        page_size=page_size,
    )


# ==================== Teacher/Admin Review ====================

@router.post("/attempts/{attempt_id}/review", response_model=AttemptReviewResponse)
async def review_attempt(
    attempt_id: uuid.UUID,
    data: AttemptReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Review and optionally override score for an attempt."""
    scoring_service = GELScoringService(db)
    try:
        result = await scoring_service.override_score(
            str(attempt_id),
            data.score_override,
            str(current_user.id),
            data.review_notes,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/admin/attempts", response_model=StudentAttemptListResponse)
async def list_all_attempts(
    student_id: Optional[str] = Query(None),
    assignment_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """List all attempts (admin view)."""
    service = GELService(db)
    
    if student_id:
        attempts, total = await service.list_student_attempts(
            student_id,
            assignment_id=assignment_id,
            status=status,
            page=page,
            page_size=page_size,
        )
    else:
        # List all attempts - need to implement this in service
        # For now, return empty
        attempts, total = [], 0
    
    return StudentAttemptListResponse(
        items=attempts,
        total=total,
        page=page,
        page_size=page_size,
    )


# ==================== Statistics ====================

@router.get("/statistics", response_model=GELStatisticsResponse)
async def get_gel_statistics(
    subject_id: Optional[uuid.UUID] = Query(None),
    cohort: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_teacher_or_admin),
):
    """Get GEL statistics."""
    service = GELService(db)
    stats = await service.get_statistics(subject_id=subject_id, cohort=cohort)
    return stats
