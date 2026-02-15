"""
Subject and Topic API endpoints.
"""

import os
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.config import settings
from app.models.subject import Subject, Topic
from app.models.user import User
from app.schemas.subject import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    SubjectListResponse,
    SubjectDetailResponse,
    TopicCreate,
    TopicUpdate,
    TopicResponse,
    TopicListResponse,
)
from app.api.v1.deps import get_current_user


router = APIRouter()


# ============== Subject Endpoints ==============

@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_data: SubjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new subject."""
    subject = Subject(
        user_id=current_user.id,
        name=subject_data.name,
        code=subject_data.code,
        description=subject_data.description,
        learning_outcomes=(
            {"outcomes": [lo.model_dump() for lo in subject_data.learning_outcomes]}
            if subject_data.learning_outcomes else None
        ),
        course_outcomes=(
            {"outcomes": [co.model_dump() for co in subject_data.course_outcomes]}
            if subject_data.course_outcomes else None
        ),
    )
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return SubjectResponse.model_validate(subject)


@router.get("", response_model=SubjectListResponse)
async def list_subjects(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name or code"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all subjects for the current user."""
    query = select(Subject).where(Subject.user_id == current_user.id)
    
    if search:
        query = query.where(
            (Subject.name.ilike(f"%{search}%")) | (Subject.code.ilike(f"%{search}%"))
        )
    
    # Count total
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()
    
    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Subject.name)
    
    result = await db.execute(query)
    subjects = result.scalars().all()
    
    return SubjectListResponse(
        subjects=[SubjectResponse.model_validate(s) for s in subjects],
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        }
    )


@router.get("/{subject_id}", response_model=SubjectDetailResponse)
async def get_subject(
    subject_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific subject with its topics."""
    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.topics))
        .where(
            Subject.id == subject_id,
            Subject.user_id == current_user.id,
        )
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    return SubjectDetailResponse(
        **SubjectResponse.model_validate(subject).model_dump(),
        topics=[TopicResponse.model_validate(t) for t in sorted(subject.topics, key=lambda x: x.order_index)]
    )


@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: uuid.UUID,
    subject_data: SubjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a subject."""
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.user_id == current_user.id,
        )
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    update_data = subject_data.model_dump(exclude_unset=True)
    
    if "learning_outcomes" in update_data and update_data["learning_outcomes"]:
        update_data["learning_outcomes"] = {"outcomes": [lo.model_dump() for lo in subject_data.learning_outcomes]}
    if "course_outcomes" in update_data and update_data["course_outcomes"]:
        update_data["course_outcomes"] = {"outcomes": [co.model_dump() for co in subject_data.course_outcomes]}
    
    for field, value in update_data.items():
        setattr(subject, field, value)
    
    await db.commit()
    await db.refresh(subject)
    return SubjectResponse.model_validate(subject)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a subject and all its topics."""
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.user_id == current_user.id,
        )
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    await db.delete(subject)
    await db.commit()


# ============== Topic Endpoints ==============

@router.post("/{subject_id}/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    subject_id: uuid.UUID,
    topic_data: TopicCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new topic in a subject."""
    # Verify subject ownership
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.user_id == current_user.id,
        )
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    topic = Topic(
        subject_id=subject_id,
        name=topic_data.name,
        description=topic_data.description,
        order_index=topic_data.order_index,
    )
    db.add(topic)
    
    # Update subject topic count
    subject.total_topics += 1
    
    await db.commit()
    await db.refresh(topic)
    return TopicResponse.model_validate(topic)


@router.get("/{subject_id}/topics", response_model=TopicListResponse)
async def list_topics(
    subject_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all topics for a subject."""
    # Verify subject ownership
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    query = select(Topic).where(Topic.subject_id == subject_id)
    
    # Count total
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()
    
    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Topic.order_index)
    
    result = await db.execute(query)
    topics = result.scalars().all()
    
    return TopicListResponse(
        topics=[TopicResponse.model_validate(t) for t in topics],
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        }
    )


@router.put("/{subject_id}/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    subject_id: uuid.UUID,
    topic_id: uuid.UUID,
    topic_data: TopicUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a topic."""
    # Verify subject ownership
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    result = await db.execute(
        select(Topic).where(
            Topic.id == topic_id,
            Topic.subject_id == subject_id,
        )
    )
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    update_data = topic_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(topic, field, value)
    
    await db.commit()
    await db.refresh(topic)
    return TopicResponse.model_validate(topic)


@router.delete("/{subject_id}/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    subject_id: uuid.UUID,
    topic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a topic."""
    # Verify subject ownership
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.user_id == current_user.id,
        )
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    result = await db.execute(
        select(Topic).where(
            Topic.id == topic_id,
            Topic.subject_id == subject_id,
        )
    )
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    await db.delete(topic)
    subject.total_topics = max(0, subject.total_topics - 1)
    await db.commit()


@router.post("/{subject_id}/topics/{topic_id}/upload-syllabus", response_model=TopicResponse)
async def upload_topic_syllabus(
    subject_id: uuid.UUID,
    topic_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document (PDF, DOCX, TXT) and extract its content as syllabus for the topic.
    The extracted text will be saved to the topic's syllabus_content field.
    """
    # Verify subject ownership
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.user_id == current_user.id,
        )
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    # Get topic
    result = await db.execute(
        select(Topic).where(
            Topic.id == topic_id,
            Topic.subject_id == subject_id,
        )
    )
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    # Validate file extension
    filename = file.filename or "document"
    ext = os.path.splitext(filename)[1].lower()
    
    allowed_extensions = [".pdf", ".txt", ".docx"]
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size (10MB limit)
    max_size_mb = 10
    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_size_mb}MB",
        )
    
    # Extract text based on file type
    try:
        text_content = await _extract_text_from_file(content, ext)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract text from file: {str(e)}",
        )
    
    if not text_content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text content could be extracted from the file",
        )
    
    # Update topic with extracted content
    topic.syllabus_content = text_content
    topic.has_syllabus = True
    
    # Update subject syllabus coverage
    total_topics_result = await db.execute(
        select(func.count()).where(Topic.subject_id == subject_id)
    )
    total_topics = total_topics_result.scalar_one()
    
    topics_with_syllabus_result = await db.execute(
        select(func.count()).where(
            Topic.subject_id == subject_id,
            Topic.has_syllabus == True,
        )
    )
    topics_with_syllabus = topics_with_syllabus_result.scalar_one()
    
    if total_topics > 0:
        subject.syllabus_coverage = (topics_with_syllabus / total_topics) * 100
    
    await db.commit()
    await db.refresh(topic)
    
    return TopicResponse.model_validate(topic)


async def _extract_text_from_file(content: bytes, extension: str) -> str:
    """Extract text from file content based on file type."""
    import io
    
    if extension == ".pdf":
        import fitz  # PyMuPDF
        text_parts = []
        with fitz.open(stream=content, filetype="pdf") as doc:
            for page in doc:
                text_parts.append(page.get_text())
        return "\n\n".join(text_parts)
    
    elif extension == ".txt":
        return content.decode("utf-8", errors="ignore")
    
    elif extension == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(content))
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        return "\n\n".join(text_parts)
    
    return ""