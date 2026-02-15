"""
Rubric Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel, Field
import uuid


class QuestionTypeDistribution(BaseModel):
    """Schema for question type distribution in rubric."""
    count: int = Field(..., ge=0, description="Number of questions of this type")
    marks_each: int = Field(..., ge=1, description="Marks per question")


class RubricBase(BaseModel):
    """Base schema for Rubric."""
    name: str = Field(..., min_length=1, max_length=255)
    exam_type: str = Field(..., description="Type of exam: final_exam, mid_term, quiz, assignment")
    duration_minutes: int = Field(180, ge=1, description="Duration in minutes")


class RubricCreate(RubricBase):
    """Schema for creating a Rubric."""
    subject_id: uuid.UUID
    question_type_distribution: Dict[str, QuestionTypeDistribution]  # {"mcq": {...}, "short_notes": {...}}
    learning_outcomes_distribution: Dict[str, int]  # {"LO1": 25, "LO2": 25, ...}


class RubricUpdate(BaseModel):
    """Schema for updating a Rubric."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    exam_type: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1)
    question_type_distribution: Optional[Dict[str, QuestionTypeDistribution]] = None
    learning_outcomes_distribution: Optional[Dict[str, int]] = None


class RubricResponse(RubricBase):
    """Schema for Rubric response."""
    id: uuid.UUID
    user_id: uuid.UUID
    subject_id: uuid.UUID
    question_type_distribution: dict
    learning_outcomes_distribution: dict
    total_questions: int
    total_marks: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RubricListResponse(BaseModel):
    """Schema for rubric list response."""
    rubrics: List[RubricResponse]
    pagination: dict


class RubricDetailResponse(RubricResponse):
    """Schema for detailed Rubric response with subject info."""
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
