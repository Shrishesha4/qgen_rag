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
    count: int = Field(..., ge=1, le=200, description="Number of questions to generate")
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
        le=200,
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


class SourceReference(BaseModel):
    """Schema for source reference information showing where content came from."""
    document_name: Optional[str] = None
    page_number: Optional[int] = None
    page_range: Optional[List[int]] = None  # [start_page, end_page]
    position_in_page: Optional[str] = None  # "top", "middle", "bottom"
    position_percentage: Optional[float] = None  # 0-100
    section_heading: Optional[str] = None
    content_snippet: Optional[str] = None  # Full source passage
    highlighted_phrase: Optional[str] = None  # Most relevant sentence(s) for this question
    relevance_reason: Optional[str] = None  # Why this content was used for the question


class QuestionSourceInfo(BaseModel):
    """Schema for complete source information for a question."""
    sources: List[SourceReference] = []
    generation_reasoning: Optional[str] = None  # Why this question was generated from these sources
    content_coverage: Optional[str] = None  # What aspects of the content are covered


class QuestionResponse(BaseModel):
    """Schema for generated question response."""
    id: uuid.UUID
    document_id: Optional[uuid.UUID]
    subject_id: Optional[uuid.UUID]
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    topic_id: Optional[uuid.UUID]
    topic_name: Optional[str] = None
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
    
    # Source Attribution (new)
    source_info: Optional[QuestionSourceInfo] = None
    
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
    
    # Version control
    replaced_by_id: Optional[uuid.UUID] = None
    replaces_id: Optional[uuid.UUID] = None
    version_number: int = 1
    is_latest: bool = True
    previous_versions: Optional[List["QuestionResponse"]] = None  # For nested version history

    model_config = {"from_attributes": True}
    
    @classmethod
    def from_orm_with_sources(cls, question, source_info: Optional[QuestionSourceInfo] = None):
        """Create response with extracted source info from generation_metadata."""
        data = {
            "id": question.id,
            "document_id": question.document_id,
            "subject_id": question.subject_id,
            "subject_name": getattr(getattr(question, "subject", None), "name", None),
            "subject_code": getattr(getattr(question, "subject", None), "code", None),
            "topic_id": question.topic_id,
            "topic_name": getattr(getattr(question, "topic", None), "name", None),
            "session_id": getattr(question, "session_id", None),
            "question_text": question.question_text,
            "question_type": question.question_type,
            "marks": question.marks,
            "difficulty_level": question.difficulty_level,
            "bloom_taxonomy_level": question.bloom_taxonomy_level,
            "options": question.options,
            "correct_answer": question.correct_answer,
            "explanation": question.explanation,
            "topic_tags": question.topic_tags,
            "source_chunk_ids": question.source_chunk_ids,
            "course_outcome_mapping": question.course_outcome_mapping,
            "learning_outcome_id": question.learning_outcome_id,
            "vetting_status": question.vetting_status,
            "vetted_at": question.vetted_at,
            "vetting_notes": question.vetting_notes,
            "answerability_score": question.answerability_score,
            "specificity_score": question.specificity_score,
            "generation_confidence": question.generation_confidence,
            "generated_at": question.generated_at,
            "times_shown": question.times_shown,
            "user_rating": question.user_rating,
            "is_archived": question.is_archived,
            "replaced_by_id": question.replaced_by_id,
            "replaces_id": question.replaces_id,
            "version_number": getattr(question, "version_number", 1),
            "is_latest": getattr(question, "is_latest", True),
        }
        
        # Extract source info from generation_metadata if available
        if source_info:
            data["source_info"] = source_info
        elif hasattr(question, "generation_metadata") and question.generation_metadata:
            metadata = question.generation_metadata
            if "source_info" in metadata:
                data["source_info"] = QuestionSourceInfo(**metadata["source_info"])
            elif "sources" in metadata:
                data["source_info"] = QuestionSourceInfo(
                    sources=[SourceReference(**s) for s in metadata.get("sources", [])],
                    generation_reasoning=metadata.get("generation_reasoning"),
                    content_coverage=metadata.get("content_coverage"),
                )
        
        return cls(**data)


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
    questions_failed: Optional[int] = None


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
        le=200,
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
    questions_failed: Optional[int] = None
    session_id: Optional[uuid.UUID] = None
    processing_progress: Optional[int] = None
    processing_step: Optional[str] = None
    processing_detail: Optional[str] = None
    processing_document: Optional[str] = None
    processing_documents_total: Optional[int] = None
