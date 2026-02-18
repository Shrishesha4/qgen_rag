"""
Question-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
import uuid


class QuestionGenerationRequest(BaseModel):
    """Schema for question generation request."""
    document_id: uuid.UUID
    count: int = Field(..., ge=1, le=50, description="Number of questions to generate")
    types: Optional[List[Literal["mcq", "short_answer", "long_answer"]]] = Field(
        default=["mcq", "short_answer"],
        description="Types of questions to generate"
    )
    difficulty: Optional[Literal["easy", "medium", "hard"]] = Field(
        default="medium",
        description="Difficulty level of questions"
    )
    marks: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Marks per question"
    )
    focus_topics: Optional[List[str]] = Field(
        default=None,
        description="Specific topics to focus on"
    )
    bloom_levels: Optional[List[Literal[
        "remember", "understand", "apply", "analyze", "evaluate", "create"
    ]]] = Field(
        default=None,
        description="Bloom's taxonomy levels to target"
    )
    exclude_question_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        description="Question IDs to exclude (for manual blacklisting)"
    )


class MCQOption(BaseModel):
    """Schema for MCQ option."""
    label: str  # A, B, C, D
    text: str
    is_correct: bool = False


class QuestionResponse(BaseModel):
    """Schema for generated question response."""
    id: uuid.UUID
    document_id: Optional[uuid.UUID]
    subject_id: Optional[uuid.UUID]
    topic_id: Optional[uuid.UUID]
    session_id: Optional[uuid.UUID]
    
    question_text: str
    question_type: Optional[str]
    marks: Optional[int]
    difficulty_level: Optional[str]
    bloom_taxonomy_level: Optional[str]
    
    # MCQ specific
    options: Optional[List[str]]
    correct_answer: Optional[str]
    explanation: Optional[str] = None
    
    # Context
    topic_tags: Optional[List[str]]
    source_chunk_ids: Optional[List[uuid.UUID]]
    
    # OBE mappings
    course_outcome_mapping: Optional[dict]
    learning_outcome_id: Optional[str]
    
    # Vetting
    vetting_status: str = "pending"
    vetted_at: Optional[datetime]
    vetting_notes: Optional[str]
    
    # Quality
    answerability_score: Optional[float]
    specificity_score: Optional[float]
    generation_confidence: Optional[float]
    
    # Metadata
    generated_at: datetime
    times_shown: int
    user_rating: Optional[int]
    is_archived: bool

    model_config = {"from_attributes": True}


class QuestionListResponse(BaseModel):
    """Schema for question list response."""
    questions: List[QuestionResponse]
    pagination: dict


class QuestionRatingRequest(BaseModel):
    """Schema for rating a question."""
    rating: int = Field(..., ge=1, le=5)
    difficulty_rating: Optional[Literal["too_easy", "just_right", "too_hard"]] = None


class QuestionUpdateRequest(BaseModel):
    """Schema for updating a question's editable fields."""
    marks: Optional[int] = Field(default=None, ge=1, le=100, description="Marks for this question")
    difficulty_level: Optional[Literal["easy", "medium", "hard"]] = None
    bloom_taxonomy_level: Optional[Literal[
        "remember", "understand", "apply", "analyze", "evaluate", "create"
    ]] = None
    subject_id: Optional[uuid.UUID] = Field(default=None, description="Link to a subject")
    topic_id: Optional[uuid.UUID] = Field(default=None, description="Link to a specific topic/chapter")
    learning_outcome_id: Optional[str] = Field(default=None, description="Link to a learning outcome (e.g., LO1)")
    course_outcome_mapping: Optional[dict] = Field(default=None, description="Course outcome mapping")
    question_text: Optional[str] = Field(default=None, min_length=5, description="Updated question text")
    correct_answer: Optional[str] = Field(default=None, description="Updated correct answer")
    options: Optional[List[str]] = Field(default=None, description="Updated MCQ options")


class GenerationProgress(BaseModel):
    """Schema for generation progress SSE event."""
    status: Literal["processing", "generating", "validating", "complete", "error"]
    progress: int = Field(..., ge=0, le=100)
    current_question: Optional[int] = None
    total_questions: Optional[int] = None
    question: Optional[QuestionResponse] = None
    message: Optional[str] = None


class GenerationSessionResponse(BaseModel):
    """Schema for generation session response."""
    id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID
    
    # Request params
    requested_count: int
    requested_types: Optional[List[str]]
    requested_marks: Optional[int]
    requested_difficulty: Optional[str]
    focus_topics: Optional[List[str]]
    
    # Status
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    
    # Results
    questions_generated: int
    questions_failed: int
    questions_duplicate: int
    
    # Performance
    total_duration_seconds: Optional[float]
    llm_calls: Optional[int]
    tokens_used: Optional[int]
    
    # Context
    blacklist_size: Optional[int]
    chunks_used: Optional[int]
    
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class GenerationStatsResponse(BaseModel):
    """Schema for generation statistics."""
    total_questions_generated: int
    total_sessions: int
    average_questions_per_session: float
    questions_by_type: dict
    questions_by_difficulty: dict
    average_generation_time: float


class QuickGenerateRequest(BaseModel):
    """Schema for quick question generation from uploaded PDF with context only."""
    context: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Context or title describing what the PDF is about (e.g., 'Chapter 5: Data Structures')"
    )
    count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of questions to generate"
    )
    types: Optional[List[Literal["mcq", "short_answer", "long_answer"]]] = Field(
        default=["mcq", "short_answer"],
        description="Types of questions to generate"
    )
    difficulty: Optional[Literal["easy", "medium", "hard"]] = Field(
        default="medium",
        description="Difficulty level of questions"
    )
    bloom_levels: Optional[List[Literal[
        "remember", "understand", "apply", "analyze", "evaluate", "create"
    ]]] = Field(
        default=None,
        description="Bloom's taxonomy levels to target"
    )


class QuickGenerateProgress(BaseModel):
    """Schema for quick generation progress SSE event."""
    status: Literal["uploading", "processing", "generating", "complete", "error"]
    progress: int = Field(..., ge=0, le=100)
    current_question: Optional[int] = None
    total_questions: Optional[int] = None
    question: Optional[QuestionResponse] = None
    message: Optional[str] = None
    document_id: Optional[uuid.UUID] = None
