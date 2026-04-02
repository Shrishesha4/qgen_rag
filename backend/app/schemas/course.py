"""
Pydantic schemas for the course marketplace.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# ── Course ────────────────────────────────────────────────────────────────────

class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    subject_id: Optional[str] = None
    price_cents: int = Field(0, ge=0)
    currency: str = Field("INR", max_length=3)
    cover_image_url: Optional[str] = None
    preview_video_url: Optional[str] = None
    learning_outcomes: Optional[dict] = None


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    subject_id: Optional[str] = None
    price_cents: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    cover_image_url: Optional[str] = None
    preview_video_url: Optional[str] = None
    learning_outcomes: Optional[dict] = None
    is_featured: Optional[bool] = None


class CourseModuleResponse(BaseModel):
    id: str
    course_id: str
    title: str
    description: Optional[str] = None
    order_index: int
    module_type: str
    content_data: Optional[dict] = None
    duration_minutes: Optional[int] = None
    is_preview: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CourseResponse(BaseModel):
    id: str
    teacher_id: str
    subject_id: Optional[str] = None
    title: str
    slug: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    preview_video_url: Optional[str] = None
    price_cents: int
    currency: str
    status: str
    is_featured: bool
    learning_outcomes: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    modules: List[CourseModuleResponse] = []

    class Config:
        from_attributes = True


class CourseSummary(BaseModel):
    """Lightweight course card for catalog listings."""
    id: str
    teacher_id: str
    teacher_name: Optional[str] = None
    title: str
    slug: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    price_cents: int
    currency: str
    status: str
    is_featured: bool
    module_count: int = 0
    enrolled_count: int = 0
    created_at: datetime


class CourseListResponse(BaseModel):
    items: List[CourseSummary]
    total: int
    page: int
    page_size: int


# ── Module ────────────────────────────────────────────────────────────────────

class ModuleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    module_type: str = Field("content", pattern=r"^(content|quiz|assignment)$")
    content_data: Optional[dict] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    is_preview: bool = False


class ModuleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    module_type: Optional[str] = Field(None, pattern=r"^(content|quiz|assignment)$")
    content_data: Optional[dict] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    is_preview: Optional[bool] = None


class ModuleContentGenerateRequest(BaseModel):
    topic_id: Optional[str] = None
    focus: Optional[str] = None


class ModuleContentStreamEvent(BaseModel):
    """SSE event payload for streamed module draft generation."""

    type: Literal["meta", "field_start", "field_delta", "field_complete", "complete", "error"]
    field: Optional[Literal[
        "summary",
        "learning_objectives",
        "body_markdown",
        "assignment_prompt",
        "video_url",
        "suggested_duration_minutes",
    ]] = None
    delta: Optional[str] = None
    message: Optional[str] = None
    module: Optional[CourseModuleResponse] = None
    provider_key: Optional[str] = None
    provider_name: Optional[str] = None
    provider_model: Optional[str] = None


class ModuleReorder(BaseModel):
    module_ids: List[str] = Field(..., min_length=1)


class ModuleQuestionAdd(BaseModel):
    question_ids: List[str] = Field(..., min_length=1)


class ModuleQuestionResponse(BaseModel):
    id: str
    module_id: str
    question_id: str
    sequence: int
    weight: float

    class Config:
        from_attributes = True


# ── Enrollment ────────────────────────────────────────────────────────────────

class EnrollmentCreate(BaseModel):
    payment_provider: str = Field("mock", pattern=r"^(mock|razorpay)$")
    mock: bool = False


class EnrollmentProgressUpdate(BaseModel):
    completed_module_ids: Optional[List[str]] = None
    quiz_scores: Optional[dict] = None


class EnrollmentResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    status: str
    progress_data: Optional[dict] = None
    enrolled_at: datetime
    completed_at: Optional[datetime] = None
    course: Optional[CourseResponse] = None

    class Config:
        from_attributes = True


class EnrollmentListResponse(BaseModel):
    items: List[EnrollmentResponse]
    total: int


# ── Payment ───────────────────────────────────────────────────────────────────

class PaymentResponse(BaseModel):
    id: str
    enrollment_id: str
    student_id: str
    amount_cents: int
    currency: str
    status: str
    provider: str
    provider_ref: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── PersonalizedItem ──────────────────────────────────────────────────────────

class PersonalizedTestRequest(BaseModel):
    course_id: Optional[str] = None
    topic_focus: Optional[List[str]] = None
    question_count: int = Field(10, ge=3, le=30)
    difficulty_bias: str = Field("auto", pattern=r"^(auto|easy|hard)$")


class PersonalizedModuleRequest(BaseModel):
    course_id: Optional[str] = None
    topic_id: str
    focus_areas: Optional[List[str]] = None


class PersonalizedItemResponse(BaseModel):
    id: str
    student_id: str
    course_id: Optional[str] = None
    topic_id: Optional[str] = None
    item_type: str
    template_id: Optional[str] = None
    generated_content: Optional[dict] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── LearningProfile ──────────────────────────────────────────────────────────

class WeakTopic(BaseModel):
    topic_id: str
    topic_name: str
    avg_score: float
    fail_count: int


class MasteredTopic(BaseModel):
    topic_id: str
    topic_name: str
    avg_score: float


class LearningProfile(BaseModel):
    weak_topics: List[WeakTopic] = []
    mastered_topics: List[MasteredTopic] = []
    reasoning_gaps: List[str] = []
    total_questions_seen: int = 0
    overall_level: str = "beginner"
