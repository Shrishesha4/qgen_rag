"""
Course marketplace models.

Models for the independent GEL course platform:
- Course: Teacher-authored course package
- CourseModule: Ordered unit within a course (content/quiz/assignment)
- ModuleQuestion: Links approved vquest questions to quiz modules
- Enrollment: Student enrollment in a course
- Payment: Payment record for paid courses
- PersonalizedItem: AI-generated one-time tests/modules for a student
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Boolean, Integer, Float, DateTime, Text, ForeignKey,
    UniqueConstraint, Index, Enum as SQLEnum, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
import enum

from app.core.database import Base
from app.core.types import UUIDString


# ── Enums ─────────────────────────────────────────────────────────────────────

class CourseStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ModuleType(str, enum.Enum):
    CONTENT = "content"
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"


class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    REFUNDED = "refunded"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PersonalizedItemType(str, enum.Enum):
    TEST = "test"
    LEARNING_MODULE = "learning_module"


class PersonalizedItemStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"


# ── Models ────────────────────────────────────────────────────────────────────

class Course(Base):
    """Teacher-authored course package."""

    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    teacher_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subject_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(280), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    preview_video_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CourseStatus.DRAFT.value
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    learning_outcomes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    modules: Mapped[List["CourseModule"]] = relationship(
        back_populates="course", cascade="all, delete-orphan",
        order_by="CourseModule.order_index",
    )
    enrollments: Mapped[List["Enrollment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Course {self.slug} teacher={self.teacher_id}>"


class CourseModule(Base):
    """Ordered unit within a course."""

    __tablename__ = "course_modules"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    course_id: Mapped[str] = mapped_column(
        UUIDString(), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    module_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ModuleType.CONTENT.value
    )
    content_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_preview: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="modules")
    module_questions: Mapped[List["ModuleQuestion"]] = relationship(
        back_populates="module", cascade="all, delete-orphan",
        order_by="ModuleQuestion.sequence",
    )

    def __repr__(self) -> str:
        return f"<CourseModule {self.title} course={self.course_id}>"


class ModuleQuestion(Base):
    """Links approved vquest questions to quiz modules."""

    __tablename__ = "module_questions"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    module_id: Mapped[str] = mapped_column(
        UUIDString(), ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(
        UUIDString(), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Relationships
    module: Mapped["CourseModule"] = relationship(back_populates="module_questions")

    __table_args__ = (
        UniqueConstraint("module_id", "question_id", name="uq_module_question"),
    )


class Enrollment(Base):
    """Student enrollment in a course."""

    __tablename__ = "enrollments"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    student_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    course_id: Mapped[str] = mapped_column(
        UUIDString(), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EnrollmentStatus.ACTIVE.value
    )
    progress_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="enrollments")
    payment: Mapped[Optional["Payment"]] = relationship(
        back_populates="enrollment", uselist=False,
    )

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_student_course"),
    )

    def __repr__(self) -> str:
        return f"<Enrollment student={self.student_id} course={self.course_id}>"


class Payment(Base):
    """Payment record for a course enrollment."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    enrollment_id: Mapped[str] = mapped_column(
        UUIDString(), ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    student_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PaymentStatus.PENDING.value
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="mock")
    provider_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    enrollment: Mapped["Enrollment"] = relationship(back_populates="payment")

    def __repr__(self) -> str:
        return f"<Payment {self.id} {self.status} {self.provider}>"


class PersonalizedItem(Base):
    """AI-generated one-time test or learning module for a student."""

    __tablename__ = "personalized_items"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    student_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    course_id: Mapped[Optional[str]] = mapped_column(
        UUIDString(), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    topic_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )

    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    generated_content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PersonalizedItemStatus.DRAFT.value
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PersonalizedItem {self.item_type} student={self.student_id}>"
