"""
Subject and Topic Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List, ForwardRef
from pydantic import BaseModel, Field


# Learning Outcome schemas
class LearningOutcomeBase(BaseModel):
    """Base schema for Learning Outcome."""
    id: str  # LO1, LO2, etc.
    name: str
    description: Optional[str] = None


class LearningOutcomeCreate(LearningOutcomeBase):
    """Schema for creating a Learning Outcome."""
    pass


class LearningOutcomeResponse(LearningOutcomeBase):
    """Schema for Learning Outcome response."""
    pass


# Course Outcome schemas
class CourseOutcomeBase(BaseModel):
    """Base schema for Course Outcome."""
    id: str  # CO1, CO2, etc.
    name: str
    description: Optional[str] = None


class CourseOutcomeCreate(CourseOutcomeBase):
    """Schema for creating a Course Outcome."""
    pass


class CourseOutcomeResponse(CourseOutcomeBase):
    """Schema for Course Outcome response."""
    pass


# Topic schemas
class TopicBase(BaseModel):
    """Base schema for Topic."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    order_index: int = 0


class TopicCreate(TopicBase):
    """Schema for creating a Topic."""
    subject_id: str
    syllabus_content: Optional[str] = None


class TopicUpdate(BaseModel):
    """Schema for updating a Topic."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    order_index: Optional[int] = None
    has_syllabus: Optional[bool] = None
    syllabus_content: Optional[str] = None
    learning_outcome_mappings: Optional[dict] = None


class TopicResponse(TopicBase):
    """Schema for Topic response."""
    id: str
    subject_id: str
    has_syllabus: bool
    syllabus_content: Optional[str]
    learning_outcome_mappings: Optional[dict]
    total_questions: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TopicListResponse(BaseModel):
    """Schema for topic list response."""
    topics: List[TopicResponse]
    pagination: dict


# Subject schemas
class SubjectBase(BaseModel):
    """Base schema for Subject."""
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


class SubjectCreate(SubjectBase):
    """Schema for creating a Subject."""
    learning_outcomes: Optional[List[LearningOutcomeCreate]] = None
    course_outcomes: Optional[List[CourseOutcomeCreate]] = None


class SubjectUpdate(BaseModel):
    """Schema for updating a Subject."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    learning_outcomes: Optional[List[LearningOutcomeCreate]] = None
    course_outcomes: Optional[List[CourseOutcomeCreate]] = None


class SubjectResponse(SubjectBase):
    """Schema for Subject response."""
    id: str
    user_id: Optional[str] = None
    creator_username: Optional[str] = None
    group_id: Optional[str] = None
    learning_outcomes: Optional[dict]
    course_outcomes: Optional[dict]
    total_questions: int
    total_topics: int
    total_pending: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    syllabus_coverage: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubjectListResponse(BaseModel):
    """Schema for subject list response."""
    subjects: List[SubjectResponse]
    pagination: dict


class SubjectDetailResponse(SubjectResponse):
    """Schema for detailed Subject response with topics."""
    topics: List[TopicResponse] = []


# Subject Group schemas
class SubjectGroupBase(BaseModel):
    """Base schema for Subject Group."""
    name: str = Field(..., min_length=1, max_length=255)


class SubjectGroupCreate(SubjectGroupBase):
    """Schema for creating a Subject Group."""
    parent_id: Optional[str] = None


class SubjectGroupUpdate(BaseModel):
    """Schema for updating a Subject Group."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[str] = None
    order_index: Optional[int] = None


class SubjectGroupResponse(SubjectGroupBase):
    """Schema for Subject Group response."""
    id: str
    parent_id: Optional[str] = None
    order_index: int = 0
    created_at: datetime
    updated_at: datetime
    # Aggregated stats (computed at query time)
    total_subjects: int = 0
    total_questions: int = 0
    total_pending: int = 0
    total_approved: int = 0
    total_rejected: int = 0

    model_config = {"from_attributes": True}


class SubjectGroupTreeNode(SubjectGroupResponse):
    """Recursive schema for Subject Group tree with children."""
    children: List["SubjectGroupTreeNode"] = []
    subjects: List["SubjectResponse"] = []


class SubjectTreeResponse(BaseModel):
    """Schema for hierarchical subjects response with groups."""
    groups: List[SubjectGroupTreeNode] = []
    ungrouped_subjects: List[SubjectResponse] = []
    totals: dict = {}


# Update forward references
SubjectGroupTreeNode.model_rebuild()
