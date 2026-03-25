"""
GEL (Graded Error Learning) / GELTrain data models.

Models for student evaluation of AI-generated questions:
- EvaluationItem: A question packaged for student evaluation
- Assignment: A release of evaluation items to students
- StudentAttempt: A student's attempt at evaluating an item
- AttemptIssue: Issues/tags identified by student in an attempt
- AttemptScore: Per-dimension and total scores for an attempt
- AttemptEvent: Audit trail for attempt lifecycle
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Boolean, Integer, Float, DateTime, Text, ForeignKey,
    UniqueConstraint, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
import enum

from app.core.database import Base


class EvaluationItemStatus(str, enum.Enum):
    """Status of an evaluation item."""
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class AssignmentStatus(str, enum.Enum):
    """Status of an assignment/release."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class AttemptStatus(str, enum.Enum):
    """Status of a student attempt."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    SCORED = "scored"
    REVIEWED = "reviewed"  # Teacher/admin reviewed


class IssueSeverity(str, enum.Enum):
    """Severity of an identified issue."""
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class IssueCategory(str, enum.Enum):
    """Category of issue identified in a question."""
    FACTUAL_ERROR = "factual_error"
    AMBIGUOUS = "ambiguous"
    INCOMPLETE = "incomplete"
    MISLEADING = "misleading"
    OFF_TOPIC = "off_topic"
    DIFFICULTY_MISMATCH = "difficulty_mismatch"
    BLOOM_MISMATCH = "bloom_mismatch"
    POOR_DISTRACTOR = "poor_distractor"
    ANSWER_REVEALED = "answer_revealed"
    FORMATTING = "formatting"
    OTHER = "other"


class EvaluationItem(Base):
    """
    A question packaged for student evaluation.
    Links to the original Question and includes metadata for evaluation context.
    """
    __tablename__ = "gel_evaluation_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Link to source question
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    
    # Subject/topic context (denormalized for query efficiency)
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    
    # Evaluation metadata
    status: Mapped[str] = mapped_column(
        String(20), default=EvaluationItemStatus.DRAFT.value, nullable=False
    )
    difficulty_label: Mapped[Optional[str]] = mapped_column(String(20))  # easy/medium/hard
    bloom_level: Mapped[Optional[str]] = mapped_column(String(30))
    
    # Ground truth for scoring (set by teacher/admin)
    known_issues: Mapped[Optional[dict]] = mapped_column(JSONB)  # Pre-identified issues
    expected_detection_count: Mapped[Optional[int]] = mapped_column(Integer)
    is_control_item: Mapped[bool] = mapped_column(Boolean, default=False)  # Known good/bad for calibration
    control_type: Mapped[Optional[str]] = mapped_column(String(20))  # "known_good" or "known_bad"
    
    # Rubric reference
    rubric_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(36))  # User ID who created
    
    # Relationships
    question = relationship("Question", back_populates="evaluation_items")
    subject = relationship("Subject")
    topic = relationship("Topic")
    rubric = relationship("Rubric")
    attempts = relationship("StudentAttempt", back_populates="evaluation_item", cascade="all, delete-orphan")
    assignment_items = relationship("AssignmentItem", back_populates="evaluation_item")

    __table_args__ = (
        Index("ix_gel_eval_items_status", "status"),
        Index("ix_gel_eval_items_subject", "subject_id"),
        Index("ix_gel_eval_items_topic", "topic_id"),
    )


class Assignment(Base):
    """
    A release of evaluation items to students.
    Defines scope (subject/topic), timing, and attempt rules.
    """
    __tablename__ = "gel_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Assignment metadata
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Scope
    subject_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    cohort: Mapped[Optional[str]] = mapped_column(String(100))  # Target cohort
    grade: Mapped[Optional[str]] = mapped_column(String(20))  # Target grade
    
    # Status and timing
    status: Mapped[str] = mapped_column(
        String(20), default=AssignmentStatus.DRAFT.value, nullable=False
    )
    scheduled_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    scheduled_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Attempt rules
    max_attempts_per_item: Mapped[int] = mapped_column(Integer, default=1)
    time_limit_minutes: Mapped[Optional[int]] = mapped_column(Integer)  # Per item
    shuffle_items: Mapped[bool] = mapped_column(Boolean, default=True)
    show_feedback_immediately: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Scoring settings
    rubric_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True
    )
    passing_score: Mapped[Optional[float]] = mapped_column(Float)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(36))
    
    # Relationships
    subject = relationship("Subject")
    topic = relationship("Topic")
    rubric = relationship("Rubric")
    items = relationship("AssignmentItem", back_populates="assignment", cascade="all, delete-orphan")
    attempts = relationship("StudentAttempt", back_populates="assignment")

    __table_args__ = (
        Index("ix_gel_assignments_status", "status"),
        Index("ix_gel_assignments_cohort", "cohort"),
        Index("ix_gel_assignments_dates", "scheduled_start", "scheduled_end"),
    )


class AssignmentItem(Base):
    """
    Junction table linking assignments to evaluation items.
    Allows ordering and item-specific overrides.
    """
    __tablename__ = "gel_assignment_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gel_assignments.id", ondelete="CASCADE"), nullable=False
    )
    evaluation_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gel_evaluation_items.id", ondelete="CASCADE"), nullable=False
    )
    
    # Ordering
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    
    # Item-specific overrides
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    time_limit_override: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="items")
    evaluation_item = relationship("EvaluationItem", back_populates="assignment_items")

    __table_args__ = (
        UniqueConstraint("assignment_id", "evaluation_item_id", name="uq_assignment_item"),
        Index("ix_gel_assignment_items_assignment", "assignment_id"),
    )


class StudentAttempt(Base):
    """
    A student's attempt at evaluating an item.
    Captures detections, reasoning, corrections, and confidence.
    """
    __tablename__ = "gel_student_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Links
    student_id: Mapped[str] = mapped_column(String(36), nullable=False)  # User ID
    evaluation_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gel_evaluation_items.id", ondelete="CASCADE"), nullable=False
    )
    assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gel_assignments.id", ondelete="SET NULL"), nullable=True
    )
    
    # Attempt metadata
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(
        String(20), default=AttemptStatus.NOT_STARTED.value, nullable=False
    )
    
    # Student responses
    has_issues_detected: Mapped[Optional[bool]] = mapped_column(Boolean)  # Did student find any issues?
    reasoning_text: Mapped[Optional[str]] = mapped_column(Text)  # Student's explanation
    correction_text: Mapped[Optional[str]] = mapped_column(Text)  # Student's proposed correction
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)  # 0.0-1.0 student confidence
    
    # Draft support
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    draft_data: Mapped[Optional[dict]] = mapped_column(JSONB)  # Partial responses
    
    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    time_spent_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Scoring (populated after submission)
    total_score: Mapped[Optional[float]] = mapped_column(Float)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB)
    scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    scored_by: Mapped[Optional[str]] = mapped_column(String(50))  # "auto" or user ID
    
    # Review (teacher/admin override)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    score_override: Mapped[Optional[float]] = mapped_column(Float)
    
    # Feedback shown to student
    feedback_text: Mapped[Optional[str]] = mapped_column(Text)
    feedback_shown_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    evaluation_item = relationship("EvaluationItem", back_populates="attempts")
    assignment = relationship("Assignment", back_populates="attempts")
    issues = relationship("AttemptIssue", back_populates="attempt", cascade="all, delete-orphan")
    scores = relationship("AttemptScore", back_populates="attempt", cascade="all, delete-orphan")
    events = relationship("AttemptEvent", back_populates="attempt", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_gel_attempts_student", "student_id"),
        Index("ix_gel_attempts_item", "evaluation_item_id"),
        Index("ix_gel_attempts_assignment", "assignment_id"),
        Index("ix_gel_attempts_status", "status"),
        UniqueConstraint("student_id", "evaluation_item_id", "assignment_id", "attempt_number", 
                        name="uq_student_attempt"),
    )


class AttemptIssue(Base):
    """
    An issue/tag identified by a student in their attempt.
    """
    __tablename__ = "gel_attempt_issues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gel_student_attempts.id", ondelete="CASCADE"), nullable=False
    )
    
    # Issue details
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default=IssueSeverity.MODERATE.value)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Location in question (optional)
    location_start: Mapped[Optional[int]] = mapped_column(Integer)  # Character offset
    location_end: Mapped[Optional[int]] = mapped_column(Integer)
    location_field: Mapped[Optional[str]] = mapped_column(String(50))  # "question", "option_a", etc.
    
    # Validation against ground truth
    is_valid: Mapped[Optional[bool]] = mapped_column(Boolean)  # Set during scoring
    validation_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    attempt = relationship("StudentAttempt", back_populates="issues")

    __table_args__ = (
        Index("ix_gel_issues_attempt", "attempt_id"),
        Index("ix_gel_issues_category", "category"),
    )


class AttemptScore(Base):
    """
    Per-dimension scores for an attempt.
    Supports transparent score breakdowns.
    """
    __tablename__ = "gel_attempt_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gel_student_attempts.id", ondelete="CASCADE"), nullable=False
    )
    
    # Score dimension
    dimension: Mapped[str] = mapped_column(String(50), nullable=False)
    # Dimensions: "detection", "reasoning", "correction", "confidence_calibration"
    
    # Score values
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    weighted_score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    
    # Scoring details
    scoring_notes: Mapped[Optional[str]] = mapped_column(Text)
    scoring_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    attempt = relationship("StudentAttempt", back_populates="scores")

    __table_args__ = (
        UniqueConstraint("attempt_id", "dimension", name="uq_attempt_dimension"),
        Index("ix_gel_scores_attempt", "attempt_id"),
    )


class AttemptEvent(Base):
    """
    Audit trail for attempt lifecycle events.
    """
    __tablename__ = "gel_attempt_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gel_student_attempts.id", ondelete="CASCADE"), nullable=False
    )
    
    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: "started", "saved_draft", "submitted", "scored", "reviewed", "feedback_viewed"
    
    event_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36))  # User who triggered
    actor_type: Mapped[str] = mapped_column(String(20), default="student")  # "student", "teacher", "system"
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    attempt = relationship("StudentAttempt", back_populates="events")

    __table_args__ = (
        Index("ix_gel_events_attempt", "attempt_id"),
        Index("ix_gel_events_type", "event_type"),
        Index("ix_gel_events_created", "created_at"),
    )
