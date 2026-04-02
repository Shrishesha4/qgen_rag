"""
GEL (Graded Error Learning) / GELTrain Pydantic schemas.

Schemas for student evaluation of AI-generated questions.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
import uuid
from app.schemas.user import UserResponse


# Enums as Literals for Pydantic
EvaluationItemStatusType = Literal["draft", "active", "retired"]
AssignmentStatusType = Literal["draft", "scheduled", "active", "closed", "archived"]
AttemptStatusType = Literal["not_started", "in_progress", "submitted", "scored", "reviewed"]
IssueSeverityType = Literal["minor", "moderate", "major", "critical"]
IssueCategoryType = Literal[
    "factual_error", "ambiguous", "incomplete", "misleading", "off_topic",
    "difficulty_mismatch", "bloom_mismatch", "poor_distractor", "answer_revealed",
    "formatting", "other"
]


# ============== Evaluation Item Schemas ==============

class EvaluationItemBase(BaseModel):
    """Base schema for evaluation items."""
    difficulty_label: Optional[str] = Field(None, max_length=20)
    bloom_level: Optional[str] = Field(None, max_length=30)
    known_issues: Optional[dict] = None
    expected_detection_count: Optional[int] = None
    is_control_item: bool = False
    control_type: Optional[str] = None


class EvaluationItemCreate(EvaluationItemBase):
    """Schema for creating an evaluation item."""
    question_id: uuid.UUID
    subject_id: Optional[uuid.UUID] = None
    topic_id: Optional[uuid.UUID] = None
    rubric_id: Optional[uuid.UUID] = None


class EvaluationItemUpdate(BaseModel):
    """Schema for updating an evaluation item."""
    status: Optional[EvaluationItemStatusType] = None
    difficulty_label: Optional[str] = None
    bloom_level: Optional[str] = None
    known_issues: Optional[dict] = None
    expected_detection_count: Optional[int] = None
    is_control_item: Optional[bool] = None
    control_type: Optional[str] = None
    rubric_id: Optional[uuid.UUID] = None


class EvaluationItemResponse(EvaluationItemBase):
    """Schema for evaluation item response."""
    id: uuid.UUID
    question_id: uuid.UUID
    subject_id: Optional[uuid.UUID]
    topic_id: Optional[uuid.UUID]
    rubric_id: Optional[uuid.UUID]
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    
    # Nested question data (optional, for detail views)
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None

    model_config = {"from_attributes": True}


class EvaluationItemListResponse(BaseModel):
    """Schema for paginated evaluation item list."""
    items: List[EvaluationItemResponse]
    total: int
    page: int
    page_size: int


# ============== Assignment Schemas ==============

class AssignmentBase(BaseModel):
    """Base schema for assignments."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    cohort: Optional[str] = Field(None, max_length=100)
    grade: Optional[str] = Field(None, max_length=20)
    max_attempts_per_item: int = Field(default=1, ge=1, le=10)
    time_limit_minutes: Optional[int] = Field(None, ge=1)
    shuffle_items: bool = True
    show_feedback_immediately: bool = False
    passing_score: Optional[float] = Field(None, ge=0, le=100)


class AssignmentCreate(AssignmentBase):
    """Schema for creating an assignment."""
    subject_id: Optional[uuid.UUID] = None
    topic_id: Optional[uuid.UUID] = None
    rubric_id: Optional[uuid.UUID] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    evaluation_item_ids: Optional[List[uuid.UUID]] = None  # Items to include


class AssignmentUpdate(BaseModel):
    """Schema for updating an assignment."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[AssignmentStatusType] = None
    cohort: Optional[str] = None
    grade: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    max_attempts_per_item: Optional[int] = Field(None, ge=1, le=10)
    time_limit_minutes: Optional[int] = None
    shuffle_items: Optional[bool] = None
    show_feedback_immediately: Optional[bool] = None
    rubric_id: Optional[uuid.UUID] = None
    passing_score: Optional[float] = None


class AssignmentResponse(AssignmentBase):
    """Schema for assignment response."""
    id: uuid.UUID
    subject_id: Optional[uuid.UUID]
    topic_id: Optional[uuid.UUID]
    rubric_id: Optional[uuid.UUID]
    status: str
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    
    # Computed fields
    item_count: int = 0
    attempt_count: int = 0

    model_config = {"from_attributes": True}


class AssignmentListResponse(BaseModel):
    """Schema for paginated assignment list."""
    items: List[AssignmentResponse]
    total: int
    page: int
    page_size: int


class AssignmentItemCreate(BaseModel):
    """Schema for adding items to an assignment."""
    evaluation_item_id: uuid.UUID
    sequence_number: int = 0
    weight: float = 1.0
    time_limit_override: Optional[int] = None


# ============== Student Attempt Schemas ==============

class AttemptIssueCreate(BaseModel):
    """Schema for creating an issue in an attempt."""
    category: IssueCategoryType
    severity: IssueSeverityType = "moderate"
    description: Optional[str] = None
    location_start: Optional[int] = None
    location_end: Optional[int] = None
    location_field: Optional[str] = None  # "question", "option_a", etc.


class AttemptIssueResponse(BaseModel):
    """Schema for issue response."""
    id: uuid.UUID
    category: str
    severity: str
    description: Optional[str]
    location_start: Optional[int]
    location_end: Optional[int]
    location_field: Optional[str]
    is_valid: Optional[bool]
    validation_notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AttemptScoreResponse(BaseModel):
    """Schema for score dimension response."""
    id: uuid.UUID
    dimension: str
    raw_score: float
    max_score: float
    weighted_score: float
    weight: float
    scoring_notes: Optional[str]

    model_config = {"from_attributes": True}


class StudentAttemptCreate(BaseModel):
    """Schema for starting a new attempt."""
    evaluation_item_id: uuid.UUID
    assignment_id: Optional[uuid.UUID] = None


class StudentAttemptSubmit(BaseModel):
    """Schema for submitting an attempt."""
    has_issues_detected: bool
    issues: List[AttemptIssueCreate] = []
    reasoning_text: Optional[str] = Field(None, max_length=5000)
    correction_text: Optional[str] = Field(None, max_length=5000)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    is_draft: bool = False


class StudentAttemptDraft(BaseModel):
    """Schema for saving a draft."""
    has_issues_detected: Optional[bool] = None
    issues: List[AttemptIssueCreate] = []
    reasoning_text: Optional[str] = None
    correction_text: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    draft_data: Optional[dict] = None  # Additional partial data


class StudentAttemptResponse(BaseModel):
    """Schema for attempt response."""
    id: uuid.UUID
    student_id: str
    evaluation_item_id: uuid.UUID
    assignment_id: Optional[uuid.UUID]
    attempt_number: int
    status: str
    has_issues_detected: Optional[bool]
    reasoning_text: Optional[str]
    correction_text: Optional[str]
    confidence_score: Optional[float]
    is_draft: bool
    started_at: Optional[datetime]
    submitted_at: Optional[datetime]
    time_spent_seconds: Optional[int]
    total_score: Optional[float]
    score_breakdown: Optional[dict]
    scored_at: Optional[datetime]
    feedback_text: Optional[str]
    feedback_shown_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Nested data
    issues: List[AttemptIssueResponse] = []
    scores: List[AttemptScoreResponse] = []

    model_config = {"from_attributes": True}


class StudentAttemptListResponse(BaseModel):
    """Schema for paginated attempt list."""
    items: List[StudentAttemptResponse]
    total: int
    page: int
    page_size: int


# ============== Student Dashboard Schemas ==============

class AssignedItemResponse(BaseModel):
    """Schema for an item assigned to a student."""
    evaluation_item_id: uuid.UUID
    assignment_id: uuid.UUID
    assignment_title: str
    question_text: str
    question_type: Optional[str]
    difficulty_label: Optional[str]
    bloom_level: Optional[str]
    subject_name: Optional[str]
    topic_name: Optional[str]
    due_date: Optional[datetime]
    time_limit_minutes: Optional[int]
    attempts_used: int
    max_attempts: int
    last_attempt_status: Optional[str]
    last_attempt_score: Optional[float]


class StudentDashboardResponse(BaseModel):
    """Schema for student dashboard data."""
    assigned_items: List[AssignedItemResponse]
    in_progress_count: int
    completed_count: int
    due_soon_count: int
    average_score: Optional[float]


class StudentHistoryItemResponse(BaseModel):
    """Schema for a student's past attempt entry."""
    attempt_id: uuid.UUID
    evaluation_item_id: uuid.UUID
    assignment_id: Optional[uuid.UUID]
    assignment_title: Optional[str]
    question_text: str
    question_type: Optional[str]
    difficulty_label: Optional[str]
    bloom_level: Optional[str]
    status: str
    score: Optional[float]
    submitted_at: Optional[datetime]
    updated_at: Optional[datetime]
    attempt_number: int


class StudentHistoryResponse(BaseModel):
    """Schema for student attempt history."""
    items: List[StudentHistoryItemResponse]
    total: int


class StudentProgressAttempt(BaseModel):
    """Recent attempt summary for progress view."""
    attempt_id: uuid.UUID
    assignment_title: Optional[str]
    question_text: str
    status: str
    score: Optional[float]
    submitted_at: Optional[datetime]


class StudentProgressResponse(BaseModel):
    """Aggregated progress metrics for a student."""
    total_assignments: int
    total_items_assigned: int
    attempted_items: int
    in_progress_attempts: int
    completed_attempts: int
    average_score: Optional[float]
    best_score: Optional[float]
    completion_rate: Optional[float]
    streak_days: int
    last_activity_at: Optional[datetime]
    recent_attempts: List[StudentProgressAttempt]


class StudentProfileResponse(BaseModel):
    """Profile detail plus quick stats for a student."""
    user: UserResponse
    total_assignments: int
    completed_attempts: int
    average_score: Optional[float]
    streak_days: int


# ============== Feedback Schemas ==============

class AttemptFeedbackResponse(BaseModel):
    """Schema for feedback on an attempt."""
    attempt_id: uuid.UUID
    total_score: float
    max_possible_score: float
    percentage: float
    passed: bool
    
    # Score breakdown by dimension
    detection_score: Optional[float]
    detection_max: Optional[float]
    reasoning_score: Optional[float]
    reasoning_max: Optional[float]
    correction_score: Optional[float]
    correction_max: Optional[float]
    confidence_calibration_score: Optional[float]
    confidence_calibration_max: Optional[float]
    
    # Detailed feedback
    feedback_text: str
    issues_feedback: List[dict]  # Per-issue feedback
    improvement_suggestions: List[str]
    
    # Ground truth (if revealed)
    known_issues: Optional[dict] = None
    expected_detection_count: Optional[int] = None


# ============== Teacher/Admin Review Schemas ==============

class AttemptReviewRequest(BaseModel):
    """Schema for teacher/admin review of an attempt."""
    score_override: Optional[float] = Field(None, ge=0)
    review_notes: Optional[str] = Field(None, max_length=2000)
    issue_validations: Optional[List[dict]] = None  # [{"issue_id": "...", "is_valid": true, "notes": "..."}]


class AttemptReviewResponse(BaseModel):
    """Schema for review response."""
    attempt_id: uuid.UUID
    reviewed_at: datetime
    reviewed_by: str
    review_notes: Optional[str]
    score_override: Optional[float]
    original_score: Optional[float]
    final_score: float


# ============== Bulk Operations ==============

class BulkEvaluationItemCreate(BaseModel):
    """Schema for bulk creating evaluation items from questions."""
    question_ids: List[uuid.UUID]
    status: EvaluationItemStatusType = "draft"
    rubric_id: Optional[uuid.UUID] = None


class BulkAssignmentItemAdd(BaseModel):
    """Schema for bulk adding items to an assignment."""
    evaluation_item_ids: List[uuid.UUID]
    starting_sequence: int = 0


# ============== Statistics Schemas ==============

class GELStatisticsResponse(BaseModel):
    """Schema for GEL statistics."""
    total_evaluation_items: int
    active_evaluation_items: int
    total_assignments: int
    active_assignments: int
    total_attempts: int
    completed_attempts: int
    average_score: Optional[float]
    score_distribution: dict  # {"0-20": 5, "21-40": 10, ...}
    common_issues: List[dict]  # [{"category": "factual_error", "count": 50}, ...]
    confidence_calibration: dict  # {"overconfident": 30, "underconfident": 20, "calibrated": 50}
