"""
Question generation API endpoints.
"""

import json
import os
from typing import Optional, List
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.schemas.question import (
    QuestionGenerationRequest,
    QuestionResponse,
    QuestionListResponse,
    QuestionRatingRequest,
    GenerationProgress,
    GenerationSessionResponse,
    QuickGenerateProgress,
)
from app.services.question_service import QuestionGenerationService
from app.services.document_service import DocumentService
from app.api.v1.deps import get_current_user, rate_limit
from app.models.user import User
from app.models.question import Question, GenerationSession
from app.models.document import Document


# MIME type mapping for allowed extensions
MIME_TYPE_MAPPING = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


router = APIRouter()


@router.post("/generate")
async def generate_questions(
    request: QuestionGenerationRequest,
    current_user: User = Depends(rate_limit(requests=100, window_seconds=86400)),  # 100/day
    db: AsyncSession = Depends(get_db),
):
    """
    Generate questions from a document using RAG.
    Returns Server-Sent Events (SSE) stream with progress updates.
    
    The system automatically:
    1. Retrieves relevant document chunks
    2. Blacklists previously generated questions
    3. Generates unique questions avoiding duplicates
    4. Validates quality and stores results
    """
    question_service = QuestionGenerationService(db)
    
    async def event_generator():
        """Generate SSE events."""
        async for progress in question_service.generate_questions(
            user_id=current_user.id,
            request=request,
        ):
            yield f"data: {progress.model_dump_json()}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/quick-generate")
async def quick_generate_questions(
    file: UploadFile = File(..., description="PDF file to generate questions from"),
    context: str = Form(..., min_length=3, max_length=500, description="Context or title (e.g., 'Chapter 5: Data Structures')"),
    count: int = Form(default=5, ge=1, le=20, description="Number of questions to generate"),
    types: Optional[str] = Form(default="mcq,short_answer", description="Comma-separated question types: mcq, short_answer, long_answer"),
    difficulty: str = Form(default="medium", description="Difficulty level: easy, medium, hard"),
    bloom_levels: Optional[str] = Form(default=None, description="Comma-separated Bloom levels: remember, understand, apply, analyze, evaluate, create"),
    marks_mcq: Optional[int] = Form(default=1, ge=1, le=100, description="Marks for MCQ questions"),
    marks_short: Optional[int] = Form(default=2, ge=1, le=100, description="Marks for short answer questions"),
    marks_long: Optional[int] = Form(default=5, ge=1, le=100, description="Marks for long answer/essay questions"),
    subject_id: Optional[str] = Form(default=None, description="Subject ID to link questions to"),
    topic_id: Optional[str] = Form(default=None, description="Topic/Chapter ID to link questions to"),
    current_user: User = Depends(rate_limit(requests=50, window_seconds=86400)),  # 50/day for quick generate
    db: AsyncSession = Depends(get_db),
):
    """
    Quick question generation from a PDF upload with just context/title.
    
    This simplified endpoint allows you to:
    1. Upload any PDF document
    2. Provide a brief context/title describing the content
    3. Get questions generated automatically using RAG + LLM
    
    No rubrics, subjects, or detailed configuration required.
    Returns Server-Sent Events (SSE) stream with progress updates.
    
    Example:
    - Upload: "chapter5_datastructures.pdf"
    - Context: "Binary Trees and Tree Traversal Algorithms"
    - Get: 5 questions about binary trees
    """
    # Validate file extension
    filename = file.filename or "document.pdf"
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB",
        )
    
    # Parse types and bloom_levels from comma-separated strings
    type_list = [t.strip() for t in types.split(",")] if types else ["mcq", "short_answer"]
    bloom_list = [b.strip() for b in bloom_levels.split(",")] if bloom_levels else None
    
    # Validate types
    valid_types = {"mcq", "short_answer", "long_answer"}
    for t in type_list:
        if t not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid question type: {t}. Valid types: {', '.join(valid_types)}",
            )
    
    # Validate difficulty
    if difficulty not in {"easy", "medium", "hard"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid difficulty. Must be: easy, medium, or hard",
        )
    
    # Validate bloom levels if provided
    if bloom_list:
        valid_blooms = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
        for b in bloom_list:
            if b not in valid_blooms:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid bloom level: {b}. Valid levels: {', '.join(valid_blooms)}",
                )
    
    mime_type = MIME_TYPE_MAPPING.get(ext, "application/octet-stream")
    
    async def event_generator():
        """Generate SSE events for quick generation."""
        import logging
        logger = logging.getLogger(__name__)
        
        document_service = DocumentService(db)
        question_service = QuestionGenerationService(db)
        
        # Step 1: Upload and process document
        logger.info(f"Quick generate: Starting for user {current_user.id}, context: {context}")
        yield f"data: {QuickGenerateProgress(status='uploading', progress=5, message='Uploading document...').model_dump_json()}\n\n"
        
        try:
            yield f"data: {QuickGenerateProgress(status='processing', progress=10, message='Processing document content...').model_dump_json()}\n\n"
            
            # Upload and process synchronously
            logger.info(f"Quick generate: Processing document {filename}")
            document = await document_service.upload_and_process_document(
                user_id=current_user.id,
                filename=filename,
                file_content=content,
                mime_type=mime_type,
                context=context,
            )
            
            # Extract document_id immediately to avoid session issues
            doc_id = document.id
            doc_chunks = document.total_chunks
            
            logger.info(f"Quick generate: Document processed, {doc_chunks} chunks")
            yield f"data: {QuickGenerateProgress(status='processing', progress=20, message=f'Document processed: {doc_chunks} sections extracted', document_id=doc_id).model_dump_json()}\n\n"
            
            # Step 2: Generate questions
            logger.info(f"Quick generate: Starting question generation, count={count}, types={type_list}")
            generation_started = False
            
            # Build marks by type dictionary
            marks_by_type = {
                "mcq": marks_mcq,
                "short_answer": marks_short,
                "long_answer": marks_long,
            }
            
            # Parse subject_id and topic_id
            parsed_subject_id = uuid.UUID(subject_id) if subject_id else None
            parsed_topic_id = uuid.UUID(topic_id) if topic_id else None
            
            try:
                async for progress in question_service.quick_generate(
                    user_id=current_user.id,
                    document_id=doc_id,
                    context=context,
                    count=count,
                    types=type_list,
                    difficulty=difficulty,
                    bloom_levels=bloom_list,
                    marks_by_type=marks_by_type,
                    subject_id=parsed_subject_id,
                    topic_id=parsed_topic_id,
                ):
                    generation_started = True
                    # Adjust progress to account for document processing phase
                    if progress.status == "generating":
                        adjusted_progress = 20 + int(progress.progress * 0.8)
                        progress.progress = min(adjusted_progress, 100)
                    logger.info(f"Quick generate: Progress {progress.status} - {progress.message}")
                    yield f"data: {progress.model_dump_json()}\n\n"
                
                logger.info("Quick generate: Complete")
            except GeneratorExit:
                # Client disconnected during generation
                logger.warning(f"Quick generate: Client disconnected, cleaning up locks")
                if generation_started:
                    # Force cleanup the lock if generation was in progress
                    try:
                        redis_svc = question_service.redis_service
                        await redis_svc.release_generation_lock(str(current_user.id), str(doc_id))
                        logger.info(f"Quick generate: Force released lock for document {doc_id}")
                    except Exception as e:
                        logger.error(f"Quick generate: Failed to release lock on disconnect: {e}")
                raise
                
        except ValueError as e:
            logger.error(f"Quick generate: ValueError - {e}")
            yield f"data: {QuickGenerateProgress(status='error', progress=0, message=str(e)).model_dump_json()}\n\n"
        except GeneratorExit:
            # Re-raise to let FastAPI handle it
            raise
        except Exception as e:
            logger.exception(f"Quick generate: Exception - {e}")
            yield f"data: {QuickGenerateProgress(status='error', progress=0, message=f'An error occurred: {str(e)}').model_dump_json()}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=QuestionListResponse)
async def list_questions(
    document_id: Optional[uuid.UUID] = Query(None, description="Document ID to get questions for"),
    subject_id: Optional[uuid.UUID] = Query(None, description="Subject ID to filter by"),
    topic_id: Optional[uuid.UUID] = Query(None, description="Topic ID to filter by"),
    vetting_status: Optional[str] = Query(None, description="Filter by vetting status (pending, approved, rejected)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    question_type: Optional[str] = Query(None, description="Filter by question type"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    show_archived: bool = Query(False, description="Show only archived questions when true"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List questions with pagination and filtering.
    Can filter by document, subject, topic, or vetting status.
    Set show_archived=true to view archived questions only.
    """
    question_service = QuestionGenerationService(db)
    
    try:
        questions, pagination = await question_service.get_questions(
            user_id=current_user.id,
            document_id=document_id,
            subject_id=subject_id,
            topic_id=topic_id,
            vetting_status=vetting_status,
            page=page,
            limit=limit,
            question_type=question_type,
            difficulty=difficulty,
            show_archived=show_archived,
        )
        
        return QuestionListResponse(
            questions=[QuestionResponse.model_validate(q) for q in questions],
            pagination=pagination,
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific question by ID.
    """
    from sqlalchemy import select, or_
    from app.models.question import Question
    from app.models.document import Document
    from app.models.subject import Subject
    
    result = await db.execute(
        select(Question)
        .outerjoin(Document, Question.document_id == Document.id)
        .outerjoin(Subject, Question.subject_id == Subject.id)
        .where(
            Question.id == question_id,
            or_(
                Document.user_id == current_user.id,
                Subject.user_id == current_user.id,
            )
        )
    )
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
    
    return QuestionResponse.model_validate(question)


@router.post("/{question_id}/rate", response_model=QuestionResponse)
async def rate_question(
    question_id: uuid.UUID,
    rating_data: QuestionRatingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Rate a question for quality feedback.
    """
    question_service = QuestionGenerationService(db)
    
    try:
        question = await question_service.rate_question(
            question_id=question_id,
            user_id=current_user.id,
            rating=rating_data.rating,
            difficulty_rating=rating_data.difficulty_rating,
        )
        
        return QuestionResponse.model_validate(question)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/{question_id}")
async def archive_question(
    question_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Archive a question (soft delete).
    Archived questions remain in blacklist but won't be shown.
    """
    question_service = QuestionGenerationService(db)
    
    success = await question_service.archive_question(
        question_id=question_id,
        user_id=current_user.id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
    
    return {"message": "Question archived successfully"}


@router.post("/{question_id}/unarchive")
async def unarchive_question(
    question_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unarchive a question (restore it).
    Restores an archived question to make it visible again.
    """
    question_service = QuestionGenerationService(db)
    
    success = await question_service.unarchive_question(
        question_id=question_id,
        user_id=current_user.id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived question not found",
        )
    
    return {"message": "Question unarchived successfully"}


@router.get("/sessions/list")
async def list_generation_sessions(
    document_id: Optional[uuid.UUID] = Query(None, description="Filter by document"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List question generation sessions.
    """
    question_service = QuestionGenerationService(db)
    
    sessions, pagination = await question_service.get_generation_sessions(
        user_id=current_user.id,
        document_id=document_id,
        page=page,
        limit=limit,
    )
    
    return {
        "sessions": [GenerationSessionResponse.model_validate(s) for s in sessions],
        "pagination": pagination,
    }


@router.get("/sessions/{session_id}", response_model=GenerationSessionResponse)
async def get_generation_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details of a specific generation session.
    """
    from sqlalchemy import select
    from app.models.question import GenerationSession
    
    result = await db.execute(
        select(GenerationSession).where(
            GenerationSession.id == session_id,
            GenerationSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    
    return GenerationSessionResponse.model_validate(session)


@router.get("/stats/summary")
async def get_question_stats(
    document_id: Optional[uuid.UUID] = Query(None, description="Filter by document"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get question generation statistics.
    """
    from sqlalchemy import select, func
    from app.models.question import Question, GenerationSession
    from app.models.document import Document
    
    # Base query for user's questions
    base_query = select(Question).join(Document).where(Document.user_id == current_user.id)
    
    if document_id:
        base_query = base_query.where(Question.document_id == document_id)
    
    # Total questions
    total_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total_questions = total_result.scalar_one()
    
    # Questions by type
    type_result = await db.execute(
        select(Question.question_type, func.count())
        .join(Document)
        .where(Document.user_id == current_user.id)
        .group_by(Question.question_type)
    )
    by_type = {row[0]: row[1] for row in type_result.all()}
    
    # Questions by difficulty
    diff_result = await db.execute(
        select(Question.difficulty_level, func.count())
        .join(Document)
        .where(Document.user_id == current_user.id)
        .group_by(Question.difficulty_level)
    )
    by_difficulty = {row[0] or "unspecified": row[1] for row in diff_result.all()}
    
    # Total sessions
    session_result = await db.execute(
        select(func.count()).where(GenerationSession.user_id == current_user.id)
    )
    total_sessions = session_result.scalar_one()
    
    # Average generation time
    avg_time_result = await db.execute(
        select(func.avg(GenerationSession.total_duration_seconds))
        .where(GenerationSession.user_id == current_user.id)
    )
    avg_time = avg_time_result.scalar_one() or 0
    
    return {
        "total_questions_generated": total_questions,
        "total_sessions": total_sessions,
        "average_questions_per_session": total_questions / max(total_sessions, 1),
        "questions_by_type": by_type,
        "questions_by_difficulty": by_difficulty,
        "average_generation_time_seconds": round(avg_time, 2),
    }


# ============== Vetting Endpoints ==============

class VettingRequest(BaseModel):
    """Schema for vetting a question."""
    status: str  # approved, rejected
    course_outcome_mapping: Optional[dict] = None  # {"CO1": 2, "CO3": 1}
    notes: Optional[str] = None


class VettingStatsResponse(BaseModel):
    """Schema for vetting statistics."""
    total_generated: int
    total_approved: int
    total_rejected: int
    pending_review: int
    approval_rate: float
    change_from_last_month: float = 0.0


@router.get("/vetting/pending", response_model=QuestionListResponse)
async def get_pending_questions(
    subject_id: Optional[uuid.UUID] = Query(None, description="Filter by subject"),
    topic_id: Optional[uuid.UUID] = Query(None, description="Filter by topic"),
    question_type: Optional[str] = Query(None, description="Filter by question type"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get questions pending vetting/review.
    """
    question_service = QuestionGenerationService(db)
    
    questions, pagination = await question_service.get_questions(
        user_id=current_user.id,
        subject_id=subject_id,
        topic_id=topic_id,
        vetting_status="pending",
        page=page,
        limit=limit,
        question_type=question_type,
    )
    
    return QuestionListResponse(
        questions=[QuestionResponse.model_validate(q) for q in questions],
        pagination=pagination,
    )


@router.post("/{question_id}/vet", response_model=QuestionResponse)
async def vet_question(
    question_id: uuid.UUID,
    vetting_data: VettingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve or reject a question.
    """
    from datetime import datetime, timezone
    from sqlalchemy import or_
    from app.models.question import Question
    from app.models.document import Document
    from app.models.subject import Subject
    
    # Support both document-based and rubric-based questions
    result = await db.execute(
        select(Question)
        .outerjoin(Document, Question.document_id == Document.id)
        .outerjoin(Subject, Question.subject_id == Subject.id)
        .where(
            Question.id == question_id,
            or_(
                Document.user_id == current_user.id,
                Subject.user_id == current_user.id,
            )
        )
    )
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
    
    if vetting_data.status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be 'approved' or 'rejected'",
        )
    
    question.vetting_status = vetting_data.status
    question.vetted_by = current_user.id
    question.vetted_at = datetime.now(timezone.utc)
    question.vetting_notes = vetting_data.notes
    
    if vetting_data.course_outcome_mapping:
        question.course_outcome_mapping = vetting_data.course_outcome_mapping
    
    await db.commit()
    await db.refresh(question)
    
    return QuestionResponse.model_validate(question)


@router.put("/{question_id}/co-mapping", response_model=QuestionResponse)
async def update_co_mapping(
    question_id: uuid.UUID,
    mapping: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update Course Outcome mapping for a question.
    """
    from sqlalchemy import or_
    from app.models.question import Question
    from app.models.document import Document
    from app.models.subject import Subject
    
    result = await db.execute(
        select(Question)
        .outerjoin(Document, Question.document_id == Document.id)
        .outerjoin(Subject, Question.subject_id == Subject.id)
        .where(
            Question.id == question_id,
            or_(
                Document.user_id == current_user.id,
                Subject.user_id == current_user.id,
            )
        )
    )
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
    
    question.course_outcome_mapping = mapping
    await db.commit()
    await db.refresh(question)
    
    return QuestionResponse.model_validate(question)


@router.put("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: uuid.UUID,
    update_data: dict,  # Using dict to accept partial updates
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a question's editable fields including marks, subject, topic, etc.
    
    Updateable fields:
    - marks: int (1-100)
    - difficulty_level: easy/medium/hard
    - bloom_taxonomy_level: remember/understand/apply/analyze/evaluate/create
    - subject_id: UUID - link to a subject
    - topic_id: UUID - link to a specific chapter/topic
    - learning_outcome_id: string (e.g., LO1, LO2)
    - course_outcome_mapping: dict (e.g., {"CO1": 2, "CO3": 1})
    - question_text: string
    - correct_answer: string
    - options: list of strings (for MCQ)
    """
    from sqlalchemy import or_
    from app.models.question import Question
    from app.models.document import Document
    from app.models.subject import Subject, Topic
    
    # Find the question with ownership check
    result = await db.execute(
        select(Question)
        .outerjoin(Document, Question.document_id == Document.id)
        .outerjoin(Subject, Question.subject_id == Subject.id)
        .where(
            Question.id == question_id,
            or_(
                Document.user_id == current_user.id,
                Subject.user_id == current_user.id,
                # Also allow if no document/subject (orphaned questions)
                Question.document_id.is_(None) & Question.subject_id.is_(None),
            )
        )
    )
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
    
    # Validate subject_id if provided
    if 'subject_id' in update_data and update_data['subject_id']:
        subject_result = await db.execute(
            select(Subject).where(
                Subject.id == update_data['subject_id'],
                Subject.user_id == current_user.id
            )
        )
        if not subject_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subject not found or doesn't belong to you",
            )
    
    # Validate topic_id if provided
    if 'topic_id' in update_data and update_data['topic_id']:
        topic_result = await db.execute(
            select(Topic)
            .join(Subject, Topic.subject_id == Subject.id)
            .where(
                Topic.id == update_data['topic_id'],
                Subject.user_id == current_user.id
            )
        )
        topic = topic_result.scalar_one_or_none()
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Topic not found or doesn't belong to you",
            )
        # If topic is provided but subject isn't, auto-set the subject
        if 'subject_id' not in update_data or not update_data['subject_id']:
            update_data['subject_id'] = topic.subject_id
    
    # Allowed fields to update
    allowed_fields = {
        'marks', 'difficulty_level', 'bloom_taxonomy_level', 
        'subject_id', 'topic_id', 'learning_outcome_id',
        'course_outcome_mapping', 'question_text', 'correct_answer', 'options'
    }
    
    # Apply updates
    for field, value in update_data.items():
        if field in allowed_fields:
            setattr(question, field, value)
    
    await db.commit()
    await db.refresh(question)
    
    return QuestionResponse.model_validate(question)


@router.get("/vetting/stats")
async def get_vetting_stats(
    subject_id: Optional[uuid.UUID] = Query(None, description="Filter by subject"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get vetting/review statistics.
    """
    from sqlalchemy import or_
    from app.models.question import Question
    from app.models.document import Document
    from app.models.subject import Subject
    
    # Base query - support both document-based and subject-based questions
    base_where = [
        or_(
            Document.user_id == current_user.id,
            Subject.user_id == current_user.id,
        )
    ]
    if subject_id:
        base_where.append(Question.subject_id == subject_id)
    
    # Total generated
    total_result = await db.execute(
        select(func.count())
        .select_from(Question)
        .outerjoin(Document, Question.document_id == Document.id)
        .outerjoin(Subject, Question.subject_id == Subject.id)
        .where(*base_where)
    )
    total_generated = total_result.scalar_one()
    
    # By status
    status_result = await db.execute(
        select(Question.vetting_status, func.count())
        .outerjoin(Document, Question.document_id == Document.id)
        .outerjoin(Subject, Question.subject_id == Subject.id)
        .where(*base_where)
        .group_by(Question.vetting_status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}
    
    total_approved = by_status.get("approved", 0)
    total_rejected = by_status.get("rejected", 0)
    pending_review = by_status.get("pending", 0)
    
    # Approval rate (out of reviewed questions)
    reviewed = total_approved + total_rejected
    approval_rate = (total_approved / reviewed * 100) if reviewed > 0 else 0.0
    
    return {
        "total_generated": total_generated,
        "total_approved": total_approved,
        "total_rejected": total_rejected,
        "pending_review": pending_review,
        "approval_rate": round(approval_rate, 1),
        "change_from_last_month": 5.2,  # Placeholder - would need historical data
    }


@router.get("/analytics/by-subject")
async def get_analytics_by_subject(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get question analytics grouped by subject.
    """
    from app.models.question import Question
    from app.models.document import Document
    from app.models.subject import Subject
    from sqlalchemy import case
    
    result = await db.execute(
        select(
            Subject.id,
            Subject.name,
            Subject.code,
            func.count(Question.id).label("total_questions"),
            func.sum(case((Question.vetting_status == "approved", 1), else_=0)).label("approved"),
            func.sum(case((Question.vetting_status == "rejected", 1), else_=0)).label("rejected"),
            func.sum(case((Question.vetting_status == "pending", 1), else_=0)).label("pending"),
        )
        .outerjoin(Question, Question.subject_id == Subject.id)
        .where(Subject.user_id == current_user.id)
        .group_by(Subject.id, Subject.name, Subject.code)
    )
    
    subjects = []
    for row in result.all():
        subjects.append({
            "id": str(row.id),
            "name": row.name,
            "code": row.code,
            "total_questions": row.total_questions or 0,
            "approved": row.approved or 0,
            "rejected": row.rejected or 0,
            "pending": row.pending or 0,
        })
    
    return {"subjects": subjects}


@router.get("/analytics/by-learning-outcome")
async def get_analytics_by_lo(
    subject_id: Optional[uuid.UUID] = Query(None, description="Filter by subject"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get question distribution by Learning Outcome.
    """
    from app.models.question import Question
    from app.models.document import Document
    
    base_where = [Document.user_id == current_user.id]
    if subject_id:
        base_where.append(Question.subject_id == subject_id)
    
    result = await db.execute(
        select(Question.learning_outcome_id, func.count())
        .join(Document)
        .where(*base_where)
        .group_by(Question.learning_outcome_id)
    )
    
    distribution = {}
    for row in result.all():
        lo_id = row[0] or "Unassigned"
        distribution[lo_id] = row[1]
    
    return {"learning_outcomes": distribution}


@router.get("/analytics/by-bloom")
async def get_analytics_by_bloom(
    subject_id: Optional[uuid.UUID] = Query(None, description="Filter by subject"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get question distribution by Bloom's Taxonomy level.
    """
    from app.models.question import Question
    from app.models.document import Document
    
    base_where = [Document.user_id == current_user.id]
    if subject_id:
        base_where.append(Question.subject_id == subject_id)
    
    result = await db.execute(
        select(Question.bloom_taxonomy_level, func.count())
        .join(Document)
        .where(*base_where)
        .group_by(Question.bloom_taxonomy_level)
    )
    
    distribution = {}
    for row in result.all():
        level = row[0] or "unspecified"
        distribution[level] = row[1]
    
    return {"bloom_levels": distribution}


# ============== Rubric-Based Generation ==============

class RubricGenerationRequest(BaseModel):
    """Schema for generating questions from a rubric."""
    rubric_id: uuid.UUID


@router.post("/generate-from-rubric")
async def generate_from_rubric(
    request: RubricGenerationRequest,
    current_user: User = Depends(rate_limit(requests=50, window_seconds=86400)),  # 50/day
    db: AsyncSession = Depends(get_db),
):
    """
    Generate questions based on a rubric configuration.
    Uses topics' syllabus content from the rubric's subject.
    
    Flow:
    1. Load rubric with question type & LO distribution
    2. Collect all topics with syllabus content
    3. Chunk syllabus content for better RAG
    4. Generate questions distributed across topics/LOs
    5. Validate & save questions with duplicate detection
    
    Returns Server-Sent Events (SSE) stream with progress updates.
    """
    from app.models.rubric import Rubric
    from app.models.subject import Subject, Topic
    from app.services.llm_service import LLMService
    from app.services.embedding_service import EmbeddingService
    from app.models.question import Question
    from loguru import logger
    import random
    import re
    import math
    
    request_id = uuid.uuid4().hex[:8]
    
    # Get rubric
    result = await db.execute(
        select(Rubric).where(
            Rubric.id == request.rubric_id,
            Rubric.user_id == current_user.id,
        )
    )
    rubric = result.scalar_one_or_none()
    
    if not rubric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rubric not found",
        )
    
    # Extract IDs early to avoid SQLAlchemy lazy loading issues
    rubric_id = rubric.id
    rubric_name = rubric.name
    subject_id = rubric.subject_id
    question_distribution = rubric.question_type_distribution or {}
    lo_distribution = rubric.learning_outcomes_distribution or {}
    total_questions = rubric.total_questions or 0
    
    # Get subject
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id)
    )
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )
    
    subject_id_str = str(subject.id)
    subject_name = subject.name
    
    # Get topics with syllabus content
    result = await db.execute(
        select(Topic)
        .where(
            Topic.subject_id == subject.id,
            Topic.has_syllabus == True,
        )
        .order_by(Topic.order_index)
    )
    topics = result.scalars().all()
    
    if not topics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No topics with syllabus content found. Please add content to topics first.",
        )
    
    # Extract topic data early
    topic_data = []
    for t in topics:
        topic_data.append({
            "id": str(t.id),
            "name": t.name,
            "content": t.syllabus_content or "",
            "lo_mappings": t.learning_outcome_mappings or {},
        })
    
    llm_service = LLMService()
    embedding_service = EmbeddingService()
    
    logger.info(f"[{request_id}] Rubric generation starting: {rubric_name}, {total_questions} questions")
    
    async def event_generator():
        """Generate SSE events with questions."""
        nonlocal db
        
        try:
            yield f"data: {json.dumps({'status': 'processing', 'progress': 5, 'message': 'Analyzing syllabus content...'})}\n\n"
            
            # Prepare chunked content for all topics
            all_chunks = []
            for topic in topic_data:
                if topic["content"]:
                    # Simple chunking by paragraphs
                    content = topic["content"]
                    paragraphs = re.split(r'\n\n+', content)
                    chunk_size = 1500
                    current_chunk = ""
                    
                    for para in paragraphs:
                        if len(current_chunk) + len(para) < chunk_size:
                            current_chunk += "\n\n" + para if current_chunk else para
                        else:
                            if current_chunk:
                                all_chunks.append({
                                    "topic_id": topic["id"],
                                    "topic_name": topic["name"],
                                    "content": current_chunk.strip(),
                                    "lo_mappings": topic["lo_mappings"],
                                })
                            current_chunk = para
                    
                    if current_chunk:
                        all_chunks.append({
                            "topic_id": topic["id"],
                            "topic_name": topic["name"],
                            "content": current_chunk.strip(),
                            "lo_mappings": topic["lo_mappings"],
                        })
            
            if not all_chunks:
                yield f"data: {json.dumps({'status': 'error', 'progress': 0, 'message': 'No syllabus content found in topics'})}\n\n"
                return
            
            yield f"data: {json.dumps({'status': 'processing', 'progress': 10, 'message': f'Prepared {len(all_chunks)} content sections from {len(topic_data)} topics'})}\n\n"
            
            questions_generated = 0
            questions_failed = 0
            generated_questions = []  # Track for duplicate detection
            
            # Type mapping
            type_mapping = {
                "mcq": "mcq",
                "short_notes": "short_answer",
                "short_answer": "short_answer",
                "essay": "long_answer",
                "long_answer": "long_answer",
            }
            
            # Generate questions for each type
            for q_type, config in question_distribution.items():
                count = config.get("count", 0)
                marks = config.get("marks_each", 2)
                mapped_type = type_mapping.get(q_type, "mcq")
                
                if count == 0:
                    continue
                
                logger.info(f"[{request_id}] Generating {count} {mapped_type} questions")
                
                # Distribute across chunks evenly
                chunks_per_question = max(1, len(all_chunks) // count)
                chunk_index = 0
                
                for i in range(count):
                    # Get a fresh session connection for each question
                    try:
                        # Select chunk (round-robin with some randomization)
                        selected_idx = (chunk_index + random.randint(0, min(2, len(all_chunks)-1))) % len(all_chunks)
                        selected_chunk = all_chunks[selected_idx]
                        chunk_index = (chunk_index + chunks_per_question) % len(all_chunks)
                        
                        # Build enhanced prompt
                        system_prompt = _get_rubric_system_prompt(mapped_type)
                        
                        prompt = f"""Context from "{selected_chunk['topic_name']}":
{selected_chunk['content']}

Generate a {mapped_type.replace('_', ' ')} question based on this content.
- Marks: {marks}
- The question must start with an interrogative word (What, Which, How, Why, etc.) or a valid imperative (Find, Calculate, Explain, etc.)
- The question should directly test understanding of the material
- Avoid questions that are too similar to: {', '.join([q[:50] for q in generated_questions[-5:]]) if generated_questions else 'None yet'}

Output valid JSON only."""

                        # Generate question
                        response = await llm_service.generate_json(
                            prompt=prompt,
                            system_prompt=system_prompt,
                            temperature=0.75,  # Slightly higher for variety
                        )
                        
                        if response and "question_text" in response:
                            question_text = response["question_text"]
                            
                            # Basic validation
                            if len(question_text) < 15:
                                questions_failed += 1
                                continue
                            
                            # Check for duplicates (simple similarity check)
                            is_duplicate = False
                            for existing_q in generated_questions:
                                # Simple word overlap check
                                q_words = set(question_text.lower().split())
                                e_words = set(existing_q.lower().split())
                                overlap = len(q_words & e_words) / max(len(q_words), 1)
                                if overlap > 0.7:
                                    is_duplicate = True
                                    break
                            
                            if is_duplicate:
                                logger.warning(f"[{request_id}] Skipping duplicate question")
                                questions_failed += 1
                                continue
                            
                            # Create embedding
                            question_embedding = await embedding_service.get_embedding(question_text)
                            
                            # Create question
                            question = Question(
                                subject_id=uuid.UUID(subject_id_str),
                                topic_id=uuid.UUID(selected_chunk["topic_id"]),
                                question_text=question_text,
                                question_embedding=question_embedding,
                                question_type=mapped_type,
                                marks=marks,
                                difficulty_level="medium",
                                bloom_taxonomy_level=response.get("bloom_level", "understand"),
                                correct_answer=response.get("correct_answer") or response.get("expected_answer"),
                                options=response.get("options"),
                                explanation=response.get("explanation"),
                                topic_tags=response.get("topic_tags", [selected_chunk["topic_name"]]),
                                generation_confidence=0.75,
                                vetting_status="pending",
                                generation_metadata={
                                    "rubric_id": str(rubric_id),
                                    "topic_name": selected_chunk["topic_name"],
                                    "lo_mappings": selected_chunk["lo_mappings"],
                                },
                            )
                            db.add(question)
                            await db.commit()
                            await db.refresh(question)
                            
                            # Track for duplicate detection
                            generated_questions.append(question_text)
                            questions_generated += 1
                            
                            # Calculate progress
                            progress = 10 + int((questions_generated / max(total_questions, 1)) * 85)
                            
                            yield f"data: {json.dumps({'status': 'generating', 'progress': min(progress, 95), 'current_question': questions_generated, 'total_questions': total_questions, 'message': f'Generated {questions_generated}/{total_questions} questions', 'question': {'id': str(question.id), 'question_text': question.question_text[:100] + '...' if len(question.question_text) > 100 else question.question_text, 'question_type': question.question_type, 'marks': question.marks}})}\n\n"
                        else:
                            questions_failed += 1
                            logger.warning(f"[{request_id}] LLM returned invalid response for {mapped_type}")
                            
                    except Exception as e:
                        logger.error(f"[{request_id}] Error generating question: {e}")
                        questions_failed += 1
                        await db.rollback()
                        continue
            
            # Update subject stats
            try:
                result = await db.execute(
                    select(Subject).where(Subject.id == uuid.UUID(subject_id_str))
                )
                subj = result.scalar_one_or_none()
                if subj:
                    subj.total_questions = (subj.total_questions or 0) + questions_generated
                    await db.commit()
            except Exception as e:
                logger.error(f"[{request_id}] Error updating subject stats: {e}")
            
            yield f"data: {json.dumps({'status': 'complete', 'progress': 100, 'current_question': questions_generated, 'total_questions': total_questions, 'message': f'Generated {questions_generated} questions' + (f' ({questions_failed} failed)' if questions_failed > 0 else '')})}\n\n"
            
            logger.info(f"[{request_id}] Rubric generation complete: {questions_generated} generated, {questions_failed} failed")
            
        except Exception as e:
            logger.error(f"[{request_id}] Rubric generation failed: {e}")
            yield f"data: {json.dumps({'status': 'error', 'progress': 0, 'message': f'Generation failed: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _get_rubric_system_prompt(question_type: str) -> str:
    """Get system prompt for rubric-based question generation."""
    if question_type == "mcq":
        return """You are an expert educator creating examination questions.
Generate a high-quality multiple-choice question (MCQ) based on the given context.

Guidelines:
- The question must be clear, specific, and test understanding of the material
- Start with an interrogative word (What, Which, How, When, etc.) or imperative (Calculate, Find, Determine)
- All options should be plausible but only one correct
- Avoid "all of the above" or "none of the above"

Output format (JSON):
{
    "question_text": "The question text ending with ?",
    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
    "correct_answer": "A",
    "explanation": "Brief explanation of why A is correct",
    "topic_tags": ["topic1"],
    "bloom_level": "understand"
}"""
    elif question_type == "short_answer":
        return """You are an expert educator creating examination questions.
Generate a short-answer question requiring a 2-4 sentence response.

Guidelines:
- The question should require application or analysis of concepts
- Start with action verbs like Explain, Describe, Compare, Define
- Be specific about what is expected in the answer

Output format (JSON):
{
    "question_text": "The question text",
    "expected_answer": "Model answer (2-4 sentences)",
    "key_points": ["point1", "point2"],
    "topic_tags": ["topic1"],
    "bloom_level": "apply"
}"""
    else:
        return """You are an expert educator creating examination questions.
Generate an long-answer question requiring a detailed response.

Guidelines:
- The question should require analysis, evaluation, or synthesis
- Start with higher-order verbs like Analyze, Evaluate, Discuss, Compare and contrast
- Clearly state what aspects should be covered

Output format (JSON):
{
    "question_text": "The question text",
    "expected_answer": "Model answer outline with key points",
    "topic_tags": ["topic1"],
    "bloom_level": "analyze"
}"""
