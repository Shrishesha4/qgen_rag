"""
Subject and Topic database models.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
import uuid

from app.core.database import Base


class Subject(Base):
    """Subject/Course model."""
    
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    
    # Subject info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., CS301, MATH101
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Learning Outcomes
    learning_outcomes: Mapped[Optional[dict]] = mapped_column(JSONB)  # List of LOs with descriptions
    
    # Course Outcomes for OBE mapping
    course_outcomes: Mapped[Optional[dict]] = mapped_column(JSONB)  # CO1-CO5 definitions
    
    # Stats (denormalized for performance)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    total_topics: Mapped[int] = mapped_column(Integer, default=0)
    syllabus_coverage: Mapped[int] = mapped_column(Integer, default=0)  # percentage
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships (user is cross-database, no ORM relationship)
    topics = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")
    rubrics = relationship("Rubric", back_populates="subject", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="subject")
    
    def __repr__(self) -> str:
        return f"<Subject {self.code}: {self.name}>"


class Topic(Base):
    """Topic/Chapter model within a Subject."""
    
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    
    # Topic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    
    # Syllabus
    has_syllabus: Mapped[bool] = mapped_column(Boolean, default=False)
    syllabus_content: Mapped[Optional[str]] = mapped_column(Text)
    syllabus_file_path: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Learning Outcomes mapping for this topic
    learning_outcome_mappings: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Stats
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    subject = relationship("Subject", back_populates="topics")
    questions = relationship("Question", back_populates="topic")
    
    def __repr__(self) -> str:
        return f"<Topic {self.name}>"
