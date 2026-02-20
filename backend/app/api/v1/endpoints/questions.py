"""
Question generation API endpoints.
"""

import json
import os
from typing import Optional, List
import uuid
from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request
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
                generator = question_service.quick_generate(
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
                )
                
                async for progress in generator:
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
    
    # Base query for user's questions (exclude archived)
    base_query = select(Question).join(Document).where(
        Document.user_id == current_user.id,
        Question.is_archived == False,
    )
    
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
        .where(Document.user_id == current_user.id, Question.is_archived == False)
        .group_by(Question.question_type)
    )
    by_type = {row[0]: row[1] for row in type_result.all()}
    
    # Questions by difficulty
    diff_result = await db.execute(
        select(Question.difficulty_level, func.count())
        .join(Document)
        .where(Document.user_id == current_user.id, Question.is_archived == False)
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
        show_archived=False,  # Never show archived in pending vetting
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
    from app.schemas.question import QuestionResponse as QR
    from app.services.question_service import QuestionGenerationService
    
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
    
    if vetting_data.status == "rejected":
        replacement = None
        qsvc = QuestionGenerationService(db)
        
        from loguru import logger
        logger.info(f"Question rejected: {question_id}, document_id={question.document_id}, subject_id={question.subject_id}")
        
        if question.document_id:
            # Document-based question: regenerate using quick_generate
            q_type = question.question_type or "mcq"
            marks_map = {"mcq": 1, "short_answer": 2, "long_answer": 5}
            if question.marks and q_type in marks_map:
                marks_map[q_type] = question.marks
            context = (question.question_text or "")[:500] if question.question_text else "Replacement question"

            # Ensure we regenerate the same question type but prefer a different question text/topic/LO
            subject_for_gen = question.subject_id
            topic_for_gen = None  # explicitly unset so generator can pick other chapters

            bloom_levels_all = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
            bloom_to_use = None
            if question.bloom_taxonomy_level and question.bloom_taxonomy_level in bloom_levels_all:
                bloom_candidates = [b for b in bloom_levels_all if b != question.bloom_taxonomy_level]
                if bloom_candidates:
                    bloom_to_use = bloom_candidates

            logger.info(f"Regenerating via quick_generate for document_id={question.document_id}")
            
            # Generate replacements but accept only those that keep the same type and are sufficiently different
            async for progress in qsvc.quick_generate(
                user_id=current_user.id,
                document_id=question.document_id,
                context=context,
                count=1,
                types=[q_type],
                difficulty=question.difficulty_level or "medium",
                marks_by_type=marks_map,
                subject_id=subject_for_gen,
                topic_id=topic_for_gen,
                bloom_levels=bloom_to_use,
            ):
                if getattr(progress, "question", None):
                    candidate = progress.question
                    # keep same type
                    if (candidate.question_type or q_type) != q_type:
                        logger.info(f"Skipping replacement with different type: {candidate.id} ({candidate.question_type})")
                        continue
                    # ensure text differs
                    if candidate.question_text and question.question_text and candidate.question_text.strip() == question.question_text.strip():
                        logger.info(f"Skipping replacement with identical text: {candidate.id}")
                        continue
                    # prefer different topic if available
                    if candidate.topic_id and question.topic_id and candidate.topic_id == question.topic_id:
                        logger.info(f"Skipping replacement in same topic: {candidate.id}")
                        continue

                    replacement = candidate
                    logger.info(f"Found acceptable replacement question: {replacement.id}")
                    break

            if replacement:
                logger.info(f"Returning replacement question: {replacement.id}")
                return QR.model_validate(replacement)
            else:
                logger.info(f"No replacement generated from quick_generate")
        
        elif question.subject_id:
            # Rubric-based question: regenerate using rubric-style generation from syllabus
            from app.models.subject import Subject, Topic
            from app.services.llm_service import LLMService
            from app.services.embedding_service import EmbeddingService
            import random

            logger.info(f"Regenerating rubric-based question for subject_id={question.subject_id}")
            
            q_type = question.question_type or "mcq"
            marks = question.marks or 2
            
            # Get topics with syllabus content from the same subject
            result = await db.execute(
                select(Topic)
                .where(
                    Topic.subject_id == question.subject_id,
                    Topic.has_syllabus == True,
                )
                .order_by(Topic.order_index)
            )
            topics = result.scalars().all()
            
            if topics:
                # Prepare chunks from topics (excluding the rejected question's topic if possible)
                all_chunks = []
                for t in topics:
                    if t.syllabus_content:
                        # Skip the same topic if there are other options
                        if question.topic_id and t.id == question.topic_id and len(topics) > 1:
                            continue
                        
                        content = t.syllabus_content
                        paragraphs = re.split(r'\n\n+', content)
                        chunk_size = 1500
                        current_chunk = ""
                        
                        for para in paragraphs:
                            if len(current_chunk) + len(para) < chunk_size:
                                current_chunk += "\n\n" + para if current_chunk else para
                            else:
                                if current_chunk:
                                    all_chunks.append({
                                        "topic_id": str(t.id),
                                        "topic_name": t.name,
                                        "content": current_chunk.strip(),
                                    })
                                current_chunk = para
                        
                        if current_chunk:
                            all_chunks.append({
                                "topic_id": str(t.id),
                                "topic_name": t.name,
                                "content": current_chunk.strip(),
                            })
                
                if all_chunks:
                    # Select a random chunk
                    selected_chunk = random.choice(all_chunks)
                    
                    llm_service = LLMService()
                    embedding_service = EmbeddingService()
                    
                    # Build prompt for regeneration
                    system_prompt = _get_rubric_system_prompt(q_type)
                    
                    prompt = f"""Context from "{selected_chunk['topic_name']}":
{selected_chunk['content']}

Generate a {q_type.replace('_', ' ')} question based on this content.
- Marks: {marks}
- The question must start with an interrogative word (What, Which, How, Why, etc.) or a valid imperative (Find, Calculate, Explain, etc.)
- The question should directly test understanding of the material
- IMPORTANT: Generate a DIFFERENT question from: "{question.question_text[:100]}..."

Output valid JSON only."""

                    logger.info(f"Generating replacement question via LLM for topic: {selected_chunk['topic_name']}")
                    
                    try:
                        response = await llm_service.generate_json(
                            prompt=prompt,
                            system_prompt=system_prompt,
                            temperature=0.8,  # Higher for more variety
                        )
                        
                        if response and "question_text" in response:
                            question_text = response["question_text"]

                            # Basic validation
                            if len(question_text) >= 15 and question_text.strip() != question.question_text.strip():
                                # Create embedding
                                question_embedding = await embedding_service.get_embedding(question_text)

                                # --- Determine LO / CO mapping for regenerated question ---
                                assigned_lo = None
                                assigned_co_map = None

                                # Prefer LO from LLM response if present
                                if isinstance(response.get("learning_outcome_id"), str):
                                    assigned_lo = response.get("learning_outcome_id")
                                elif isinstance(response.get("learning_outcome"), str):
                                    assigned_lo = response.get("learning_outcome")

                                # Prefer topic's LO mapping (if topic has explicit mappings)
                                topic_obj = None
                                try:
                                    tres = await db.execute(select(Topic).where(Topic.id == uuid.UUID(selected_chunk["topic_id"])))
                                    topic_obj = tres.scalar_one_or_none()
                                except Exception:
                                    topic_obj = None

                                topic_lo_map = (topic_obj.learning_outcome_mappings if topic_obj and getattr(topic_obj, "learning_outcome_mappings", None) else selected_chunk.get("lo_mappings")) or {}
                                if not assigned_lo and topic_lo_map:
                                    try:
                                        assigned_lo = max((topic_lo_map or {}).items(), key=lambda kv: (kv[1] or 0))[0]
                                    except Exception:
                                        assigned_lo = None

                                # Fallback to rubric LO distribution
                                if not assigned_lo and lo_distribution:
                                    items = [(k, float(v or 0)) for k, v in lo_distribution.items() if (v or 0) > 0]
                                    if items:
                                        total_w = sum(w for _, w in items)
                                        if total_w > 0:
                                            import random as _rand
                                            pick = _rand.random() * total_w
                                            acc = 0.0
                                            for k, w in items:
                                                acc += w
                                                if pick <= acc:
                                                    assigned_lo = k
                                                    break

                                # Derive CO mapping from subject LO mappings if available
                                subject_lo_mappings = getattr(subject, "learning_outcome_mappings", {}) or {}
                                if assigned_lo and subject_lo_mappings and isinstance(subject_lo_mappings.get(assigned_lo), dict):
                                    assigned_co_map = subject_lo_mappings.get(assigned_lo)
                                else:
                                    cos = (subject.course_outcomes or {}).get("outcomes") if subject.course_outcomes else None
                                    if assigned_lo and cos and isinstance(cos, list) and len(cos) > 0:
                                        m = re.search(r"LO(\d+)", str(assigned_lo))
                                        if m:
                                            idx = (int(m.group(1)) - 1) % len(cos)
                                            assigned_co_map = { f"CO{idx+1}": 1 }
                                        else:
                                            assigned_co_map = { cos[0]["id"] if isinstance(cos[0], dict) and "id" in cos[0] else f"CO1": 1 }
                                    else:
                                        assigned_co_map = {}

                                # Create new question (with LO/CO mapping)
                                new_question = Question(
                                    subject_id=question.subject_id,
                                    topic_id=uuid.UUID(selected_chunk["topic_id"]),
                                    question_text=question_text,
                                    question_embedding=question_embedding,
                                    question_type=q_type,
                                    marks=marks,
                                    difficulty_level=question.difficulty_level or "medium",
                                    bloom_taxonomy_level=response.get("bloom_level", "understand"),
                                    correct_answer=response.get("correct_answer") or response.get("expected_answer"),
                                    options=response.get("options"),
                                    explanation=response.get("explanation"),
                                    topic_tags=response.get("topic_tags", [selected_chunk["topic_name"]]),
                                    learning_outcome_id=assigned_lo,
                                    course_outcome_mapping=assigned_co_map,
                                    generation_confidence=0.75,
                                    vetting_status="pending",
                                    generation_metadata={
                                        "regenerated_from": str(question_id),
                                        "topic_name": selected_chunk["topic_name"],
                                        "assigned_learning_outcome": assigned_lo,
                                        "assigned_course_outcome_mapping": assigned_co_map,
                                    },
                                )
                                db.add(new_question)
                                await db.commit()
                                await db.refresh(new_question)

                                replacement = new_question
                                logger.info(f"Created replacement question: {replacement.id}")
                    except Exception as e:
                        logger.error(f"Error generating replacement: {e}")
                        await db.rollback()
            
            if replacement:
                logger.info(f"Returning rubric-based replacement: {replacement.id}")
                return QR.model_validate(replacement)
            else:
                logger.info(f"No replacement generated for rubric-based question")
        
        # No replacement was generated - return the rejected question itself
        # (frontend will remove it from the list, no fake replacement)
        logger.info(f"Returning original rejected question (no replacement available)")
    
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
        ),
        Question.is_archived == False,  # Exclude archived from stats
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
        .outerjoin(Question, (Question.subject_id == Subject.id) & (Question.is_archived == False))
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
    
    base_where = [Document.user_id == current_user.id, Question.is_archived == False]
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
    
    base_where = [Document.user_id == current_user.id, Question.is_archived == False]
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
    topic_id: Optional[uuid.UUID] = None  # If set, restrict generation to this chapter only


@router.post("/generate-from-rubric")
async def generate_from_rubric(
    request: RubricGenerationRequest,
    raw_request: Request,
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
    topic_query = select(Topic).where(
        Topic.subject_id == subject.id,
        Topic.has_syllabus == True,
    )
    # If a specific topic_id was requested, restrict to that chapter only
    if request.topic_id:
        topic_query = topic_query.where(Topic.id == request.topic_id)
    topic_query = topic_query.order_by(Topic.order_index)
    result = await db.execute(topic_query)
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
    
    # Pre-fetch subject attributes that might not be loaded in the new session
    subject_lo_mappings = getattr(subject, "learning_outcome_mappings", {}) or {}
    subject_cos = (subject.course_outcomes or {}).get("outcomes") if subject.course_outcomes else None

    logger.info(f"[{request_id}] Rubric generation starting: {rubric_name}, {total_questions} questions, topic_id={request.topic_id}, topics_found={len(topic_data)}")
    for td in topic_data:
        logger.info(f"[{request_id}]   -> Topic: {td['name']} ({td['id']})")
    
    async def event_generator():
        """Generate SSE events with questions."""
        from app.core.database import AsyncSessionLocal
        db = AsyncSessionLocal()
        
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

            # ── RAG: fetch reference-book chunks ──
            reference_context = ""
            ref_count = 0
            try:
                from app.services.document_service import DocumentService
                doc_service = DocumentService(db, embedding_service)
                # Build a query from the topic names + first few hundred chars of syllabus
                rag_query_parts = [td["name"] + ": " + (td["content"] or "")[:200] for td in topic_data if td["content"]]
                rag_query = " ".join(rag_query_parts)[:1000]
                query_emb = await embedding_service.get_query_embedding(rag_query)
                ref_chunks = await doc_service.get_reference_chunks(
                    user_id=current_user.id,
                    subject_id=uuid.UUID(subject_id_str),
                    index_type="reference_book",
                    query_embedding=query_emb,
                    top_k=5,
                )
                if ref_chunks:
                    reference_context = "\n\n".join(
                        f"[Reference {i+1}]: {c.chunk_text}" for i, c in enumerate(ref_chunks)
                    )
                    ref_count = len(ref_chunks)
                    logger.info(f"[{request_id}] RAG found {ref_count} reference chunks for rubric generation")
            except Exception as e:
                logger.warning(f"[{request_id}] RAG lookup failed ({e}); continuing without reference context")

            # Build LO/CO context strings for prompts
            lo_context = ""
            all_lo_keys = set()
            for td in topic_data:
                if td.get("lo_mappings"):
                    all_lo_keys.update(td["lo_mappings"].keys())
            if all_lo_keys:
                lo_context = f"\nAvailable Learning Outcomes: {', '.join(sorted(all_lo_keys))}"
            co_context = ""
            if subject_cos and isinstance(subject_cos, list):
                co_ids = [co.get('id', f'CO{i+1}') if isinstance(co, dict) else str(co) for i, co in enumerate(subject_cos)]
                co_context = f"\nAvailable Course Outcomes: {', '.join(co_ids)}"
            elif subject_lo_mappings:
                all_cos = set()
                for lo_key, co_map in subject_lo_mappings.items():
                    if isinstance(co_map, dict):
                        all_cos.update(co_map.keys())
                if all_cos:
                    co_context = f"\nAvailable Course Outcomes: {', '.join(sorted(all_cos))}"

            yield f"data: {json.dumps({'status': 'processing', 'progress': 10, 'message': f'Prepared {len(all_chunks)} content sections from {len(topic_data)} topics + {ref_count} reference excerpts'})}\n\n"
            
            questions_generated = 0
            questions_failed = 0
            generated_questions = []  # Track for duplicate detection
            generated_embeddings = []  # Track embeddings for semantic dedupe within this session
            existing_question_embeddings = []  # Preloaded DB embeddings for subject-level dedupe

            # Preload existing question embeddings for this subject to reduce false positives
            try:
                emb_res = await db.execute(
                    select(Question.question_embedding).where(
                        Question.subject_id == uuid.UUID(subject_id_str),
                        Question.is_archived == False,
                        Question.question_embedding.isnot(None),
                    ).limit(2000)
                )
                existing_question_embeddings = [r[0] for r in emb_res.all()]
                logger.info(f"[{request_id}] Preloaded {len(existing_question_embeddings)} existing embeddings for dedupe")
            except Exception as e:
                logger.warning(f"[{request_id}] Could not preload existing embeddings ({e}); continuing without DB dedupe")

            # Type mapping
            type_mapping = {
                "mcq": "mcq",
                "short_notes": "short_answer",
                "short_answer": "short_answer",
                "essay": "long_answer",
                "long_answer": "long_answer",
            }

            RETRY_LIMIT = 5

            cancelled = False
            
            # Generate questions for each type
            for q_type, config in question_distribution.items():
                if cancelled:
                    break
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
                    # Check if client has disconnected (cancelled)
                    if await raw_request.is_disconnected():
                        logger.info(f"[{request_id}] Client disconnected, cancelling generation")
                        cancelled = True
                        break

                    try:
                        # Select chunk (round-robin with some randomization)
                        selected_idx = (chunk_index + random.randint(0, min(2, len(all_chunks)-1))) % len(all_chunks)
                        selected_chunk = all_chunks[selected_idx]
                        chunk_index = (chunk_index + chunks_per_question) % len(all_chunks)
                        
                        # Build enhanced prompt
                        system_prompt = _get_rubric_system_prompt(mapped_type)
                        
                        prompt = f"""Context from "{selected_chunk['topic_name']}":
{selected_chunk['content']}
"""
                        if reference_context:
                            prompt += f"""
Additional reference material (use to enrich the question):
{reference_context}
"""
                        prompt += f"""
Generate a {mapped_type.replace('_', ' ')} question based on this content.
- Marks: {marks}
- The question must start with an interrogative word (What, Which, How, Why, etc.) or a valid imperative (Find, Calculate, Explain, etc.)
- The question should directly test understanding of the material
- Avoid questions that are too similar to: {', '.join([q[:50] for q in generated_questions[-5:]]) if generated_questions else 'None yet'}
{lo_context}
{co_context}
- In your JSON output, include "learning_outcome" (the most relevant LO based on the question content) and "course_outcome" (the most relevant CO based on the question content). Analyze what the question tests and choose accordingly.

Output valid JSON only."""

                        accepted = False
                        response_obj = None

                        for attempt in range(RETRY_LIMIT):
                            try:
                                resp = await llm_service.generate_json(
                                    prompt=prompt,
                                    system_prompt=system_prompt,
                                    temperature=0.75 + (0.05 * attempt),
                                )
                            except Exception as e:
                                resp = None

                            if not resp or "question_text" not in resp:
                                logger.warning(f"[{request_id}] LLM returned invalid response (attempt {attempt+1})")
                                if attempt == RETRY_LIMIT - 1:
                                    questions_failed += 1
                                continue

                            candidate_text = resp["question_text"]
                            if len(candidate_text) < 15:
                                logger.debug(f"[{request_id}] Generated text too short (len={len(candidate_text)})")
                                if attempt == RETRY_LIMIT - 1:
                                    questions_failed += 1
                                continue

                            # Compute embedding for candidate
                            try:
                                candidate_emb = await embedding_service.get_embedding(candidate_text)
                            except Exception:
                                logger.exception(f"[{request_id}] Embedding generation failed on attempt {attempt+1}")
                                if attempt == RETRY_LIMIT - 1:
                                    questions_failed += 1
                                continue

                            # Accepted candidate
                            question_text = candidate_text
                            question_embedding = candidate_emb
                            response_obj = resp
                            accepted = True
                            break

                        if not accepted:
                            # All attempts failed for this slot
                            continue

                        # --- Determine Learning Outcome (LO) and Course Outcome (CO) mapping ---
                        assigned_lo = None
                        assigned_co_map = {}

                        # 1) Prefer explicit LO returned by the LLM
                        if response_obj and isinstance(response_obj.get("learning_outcome_id"), str):
                            assigned_lo = response_obj.get("learning_outcome_id")
                        elif response_obj and isinstance(response_obj.get("learning_outcome"), str):
                            assigned_lo = response_obj.get("learning_outcome")

                        # 2) If no LO from LLM, prefer topic's LO mappings (highest weight)
                        topic_lo_map = selected_chunk.get("lo_mappings") or {}
                        if not assigned_lo and topic_lo_map:
                            try:
                                assigned_lo = max(topic_lo_map.items(), key=lambda kv: (kv[1] or 0))[0]
                            except Exception:
                                assigned_lo = None

                        # 3) If still no LO, fall back to rubric LO distribution (weighted random)
                        if not assigned_lo and lo_distribution:
                            items = [(k, float(v or 0)) for k, v in lo_distribution.items() if (v or 0) > 0]
                            if items:
                                total_w = sum(w for _, w in items)
                                if total_w > 0:
                                    import random as _rand
                                    pick = _rand.random() * total_w
                                    acc = 0.0
                                    for k, w in items:
                                        acc += w
                                        if pick <= acc:
                                            assigned_lo = k
                                            break

                        # 4) CO mapping — prefer LLM's intelligent choice
                        if response_obj and isinstance(response_obj.get("course_outcome"), str):
                            assigned_co_map = {response_obj["course_outcome"]: 1}
                        elif response_obj and isinstance(response_obj.get("course_outcome"), dict):
                            assigned_co_map = response_obj["course_outcome"]
                        elif assigned_lo and subject_lo_mappings and isinstance(subject_lo_mappings.get(assigned_lo), dict):
                            assigned_co_map = subject_lo_mappings.get(assigned_lo)
                        elif assigned_lo and subject_cos and isinstance(subject_cos, list) and len(subject_cos) > 0:
                            m = re.search(r"LO(\d+)", str(assigned_lo))
                            if m:
                                idx = (int(m.group(1)) - 1) % len(subject_cos)
                                co_id = subject_cos[idx].get('id', f'CO{idx+1}') if isinstance(subject_cos[idx], dict) else f'CO{idx+1}'
                                assigned_co_map = {co_id: 1}

                        # Create question (accepted candidate) with LO/CO and metadata
                        question = Question(
                            subject_id=uuid.UUID(subject_id_str),
                            topic_id=uuid.UUID(selected_chunk["topic_id"]),
                            question_text=question_text,
                            question_embedding=question_embedding,
                            question_type=mapped_type,
                            marks=marks,
                            difficulty_level="medium",
                            bloom_taxonomy_level=(response_obj.get("bloom_level") if response_obj else "understand"),
                            correct_answer=(response_obj.get("correct_answer") or (response_obj.get("expected_answer") if response_obj else None)),
                            options=(response_obj.get("options") if response_obj else None),
                            explanation=(response_obj.get("explanation") if response_obj else None),
                            topic_tags=(response_obj.get("topic_tags", [selected_chunk["topic_name"]]) if response_obj else [selected_chunk["topic_name"]]),
                            learning_outcome_id=assigned_lo,
                            course_outcome_mapping=assigned_co_map,
                            generation_confidence=0.75,
                            vetting_status="pending",
                            generation_metadata={
                                "rubric_id": str(rubric_id),
                                "topic_name": selected_chunk["topic_name"],
                                "lo_mappings": selected_chunk["lo_mappings"],
                                "assigned_learning_outcome": assigned_lo,
                                "assigned_course_outcome_mapping": assigned_co_map,
                            },
                        )
                        db.add(question)
                        await db.commit()
                        await db.refresh(question)

                        # Track for duplicate detection
                        generated_questions.append(question_text)
                        generated_embeddings.append(question_embedding)
                        questions_generated += 1

                        # Calculate progress
                        progress = 10 + int((questions_generated / max(total_questions, 1)) * 85)

                        yield f"data: {json.dumps({'status': 'generating', 'progress': min(progress, 95), 'current_question': questions_generated, 'total_questions': total_questions, 'message': f'Generated {questions_generated}/{total_questions} questions', 'question': {'id': str(question.id), 'question_text': question.question_text[:100] + '...' if len(question.question_text) > 100 else question.question_text, 'question_type': question.question_type, 'marks': question.marks, 'learning_outcome_id': question.learning_outcome_id, 'course_outcome_mapping': question.course_outcome_mapping}})}\n\n"
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
        finally:
            try:
                await db.close()
            except Exception:
                pass
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============== Per-Chapter Generation with RAG ==============

class QuestionTypeSpec(BaseModel):
    """Specification for a single question type."""
    count: int
    marks_each: int = 2

class ChapterGenerationRequest(BaseModel):
    """Schema for generating questions from a single chapter."""
    topic_id: uuid.UUID
    question_types: dict  # e.g. {"mcq": {"count": 5, "marks_each": 2}, ...}


@router.post("/generate-chapter")
async def generate_chapter(
    request: ChapterGenerationRequest,
    raw_request: Request,
    current_user: User = Depends(rate_limit(requests=200, window_seconds=86400)),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate questions strictly from a single chapter.
    Uses the chapter's syllabus content + RAG from reference books.
    Streams SSE progress updates.
    """
    from app.models.subject import Subject, Topic
    from app.services.llm_service import LLMService
    from app.services.embedding_service import EmbeddingService
    from app.services.document_service import DocumentService
    from app.models.question import Question
    from app.core.database import AsyncSessionLocal
    from loguru import logger
    import random

    request_id = uuid.uuid4().hex[:8]

    # ── Load the topic ──
    result = await db.execute(
        select(Topic).where(Topic.id == request.topic_id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not topic.has_syllabus or not topic.syllabus_content:
        raise HTTPException(status_code=400, detail="This chapter has no syllabus content. Upload syllabus first.")

    topic_id_str = str(topic.id)
    topic_name = topic.name
    topic_content = topic.syllabus_content
    topic_lo_mappings = topic.learning_outcome_mappings or {}
    subject_id = topic.subject_id

    # ── Load the subject ──
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    subject_id_str = str(subject.id)
    subject_name = subject.name
    subject_lo_mappings_data = getattr(subject, "learning_outcome_mappings", {}) or {}
    subject_cos = (subject.course_outcomes or {}).get("outcomes") if subject.course_outcomes else None
    user_id = current_user.id

    # ── Parse question types ──
    type_mapping = {
        "mcq": "mcq", "short_notes": "short_answer",
        "short_answer": "short_answer", "essay": "long_answer",
        "long_answer": "long_answer",
    }
    generation_plan = []
    total_questions = 0
    for q_type, spec in request.question_types.items():
        count = spec.get("count", 0) if isinstance(spec, dict) else 0
        marks = spec.get("marks_each", 2) if isinstance(spec, dict) else 2
        mapped = type_mapping.get(q_type, q_type)
        if count > 0:
            generation_plan.append({"type": mapped, "count": count, "marks": marks})
            total_questions += count

    if total_questions == 0:
        raise HTTPException(status_code=400, detail="Add at least one question to generate.")

    llm_service = LLMService()
    embedding_service = EmbeddingService()

    logger.info(f"[{request_id}] Chapter gen: topic={topic_name} ({topic_id_str}), {total_questions} questions")

    # ── Chunk the syllabus ──
    paragraphs = re.split(r'\n\n+', topic_content)
    syllabus_chunks = []
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) < 1500:
            current_chunk += "\n\n" + para if current_chunk else para
        else:
            if current_chunk:
                syllabus_chunks.append(current_chunk.strip())
            current_chunk = para
    if current_chunk:
        syllabus_chunks.append(current_chunk.strip())
    if not syllabus_chunks:
        syllabus_chunks = [topic_content]

    async def event_generator():
        db = AsyncSessionLocal()
        try:
            yield f"data: {json.dumps({'status': 'processing', 'progress': 5, 'message': 'Analyzing chapter content...'})}\n\n"

            # ── RAG: fetch reference-book chunks ──
            reference_context = ""
            ref_count = 0
            try:
                doc_service = DocumentService(db, embedding_service)
                rag_query = f"{topic_name}: {topic_content[:500]}"
                query_emb = await embedding_service.get_query_embedding(rag_query)
                ref_chunks = await doc_service.get_reference_chunks(
                    user_id=user_id,
                    subject_id=uuid.UUID(subject_id_str),
                    index_type="reference_book",
                    query_embedding=query_emb,
                    top_k=5,
                )
                if ref_chunks:
                    reference_context = "\n\n".join(
                        f"[Reference {i+1}]: {c.chunk_text}" for i, c in enumerate(ref_chunks)
                    )
                    ref_count = len(ref_chunks)
                    logger.info(f"[{request_id}] RAG found {ref_count} reference chunks")
            except Exception as e:
                logger.warning(f"[{request_id}] RAG lookup failed ({e}); continuing without reference context")

            yield f"data: {json.dumps({'status': 'processing', 'progress': 10, 'message': f'Prepared {len(syllabus_chunks)} content sections + {ref_count} reference excerpts'})}\n\n"

            # ── Preload existing embeddings ──
            existing_embeddings = []
            try:
                emb_res = await db.execute(
                    select(Question.question_embedding).where(
                        Question.subject_id == uuid.UUID(subject_id_str),
                        Question.is_archived == False,
                        Question.question_embedding.isnot(None),
                    ).limit(2000)
                )
                existing_embeddings = [r[0] for r in emb_res.all()]
            except Exception as e:
                logger.warning(f"[{request_id}] Embedding preload failed ({e})")

            questions_generated = 0
            questions_failed = 0
            generated_texts = []
            generated_embeddings = []

            RETRY_LIMIT = 5

            cancelled = False

            for plan in generation_plan:
                if cancelled:
                    break
                q_type = plan["type"]
                count = plan["count"]
                marks = plan["marks"]
                chunk_idx = 0

                for i in range(count):
                    # Check if client has disconnected (cancelled)
                    if await raw_request.is_disconnected():
                        logger.info(f"[{request_id}] Client disconnected, cancelling chapter generation")
                        cancelled = True
                        break

                    try:
                        sel_idx = (chunk_idx + random.randint(0, min(2, len(syllabus_chunks) - 1))) % len(syllabus_chunks)
                        selected_content = syllabus_chunks[sel_idx]
                        chunk_idx = (chunk_idx + max(1, len(syllabus_chunks) // count)) % len(syllabus_chunks)

                        system_prompt = _get_rubric_system_prompt(q_type)

                        prompt = f"""Chapter: "{topic_name}"

Syllabus content:
{selected_content}
"""
                        if reference_context:
                            prompt += f"""
Additional reference material (use to enrich the question):
{reference_context}
"""
                        # Build LO/CO context for the LLM
                        lo_context = ""
                        if topic_lo_mappings:
                            lo_list = ', '.join(topic_lo_mappings.keys())
                            lo_context += f"\nAvailable Learning Outcomes for this chapter: {lo_list}"
                        co_context = ""
                        if subject_cos and isinstance(subject_cos, list):
                            co_ids = [co.get('id', f'CO{i+1}') if isinstance(co, dict) else str(co) for i, co in enumerate(subject_cos)]
                            co_context += f"\nAvailable Course Outcomes for this subject: {', '.join(co_ids)}"
                        elif subject_lo_mappings_data:
                            all_cos = set()
                            for lo_key, co_map in subject_lo_mappings_data.items():
                                if isinstance(co_map, dict):
                                    all_cos.update(co_map.keys())
                            if all_cos:
                                co_context += f"\nAvailable Course Outcomes for this subject: {', '.join(sorted(all_cos))}"

                        prompt += f"""
Generate a {q_type.replace('_', ' ')} question based STRICTLY on the chapter "{topic_name}" content above.
- Marks: {marks}
- The question MUST be about the topic "{topic_name}" — do NOT use content from other chapters
- Start with an interrogative word (What, Which, How, Why, etc.) or imperative (Find, Calculate, Explain, etc.)
- Directly test understanding of the material
- Avoid questions similar to: {', '.join([q[:50] for q in generated_texts[-5:]]) if generated_texts else 'None yet'}
{lo_context}
{co_context}
- In your JSON output, include "learning_outcome" (the most relevant LO for this question based on content) and "course_outcome" (the most relevant CO for this question based on content). Analyze the question content and choose the LO/CO that best matches what the question tests.

Output valid JSON only."""

                        accepted = False
                        for attempt in range(RETRY_LIMIT):
                            try:
                                resp = await llm_service.generate_json(
                                    prompt=prompt,
                                    system_prompt=system_prompt,
                                    temperature=0.75 + (0.05 * attempt),
                                )
                            except Exception:
                                resp = None

                            if not resp or "question_text" not in resp:
                                if attempt == RETRY_LIMIT - 1:
                                    questions_failed += 1
                                continue

                            candidate_text = resp["question_text"]
                            if len(candidate_text) < 15:
                                if attempt == RETRY_LIMIT - 1:
                                    questions_failed += 1
                                continue

                            try:
                                candidate_emb = await embedding_service.get_embedding(candidate_text)
                            except Exception:
                                if attempt == RETRY_LIMIT - 1:
                                    questions_failed += 1
                                continue

                            accepted = True

                            # LO / CO assignment — use LLM response, then fallback to topic data
                            assigned_lo = None
                            if isinstance(resp.get("learning_outcome_id"), str):
                                assigned_lo = resp["learning_outcome_id"]
                            elif isinstance(resp.get("learning_outcome"), str):
                                assigned_lo = resp["learning_outcome"]
                            if not assigned_lo and topic_lo_mappings:
                                try:
                                    assigned_lo = max(topic_lo_mappings.items(), key=lambda kv: (kv[1] or 0))[0]
                                except Exception:
                                    pass

                            # CO — prefer LLM's intelligent choice, then subject mappings
                            assigned_co_map = {}
                            if isinstance(resp.get("course_outcome"), str):
                                # LLM chose a CO — use it
                                assigned_co_map = {resp["course_outcome"]: 1}
                            elif isinstance(resp.get("course_outcome"), dict):
                                assigned_co_map = resp["course_outcome"]
                            elif assigned_lo and subject_lo_mappings_data and isinstance(subject_lo_mappings_data.get(assigned_lo), dict):
                                # Subject has explicit LO→CO mapping
                                assigned_co_map = subject_lo_mappings_data.get(assigned_lo)
                            elif assigned_lo and subject_cos and isinstance(subject_cos, list) and len(subject_cos) > 0:
                                m = re.search(r"LO(\d+)", str(assigned_lo))
                                if m:
                                    idx = (int(m.group(1)) - 1) % len(subject_cos)
                                    co_id = subject_cos[idx].get('id', f'CO{idx+1}') if isinstance(subject_cos[idx], dict) else f'CO{idx+1}'
                                    assigned_co_map = {co_id: 1}

                            question = Question(
                                subject_id=uuid.UUID(subject_id_str),
                                topic_id=uuid.UUID(topic_id_str),
                                question_text=candidate_text,
                                question_embedding=candidate_emb,
                                question_type=q_type,
                                marks=marks,
                                difficulty_level="medium",
                                bloom_taxonomy_level=(resp.get("bloom_level") if resp else "understand"),
                                correct_answer=(resp.get("correct_answer") or resp.get("expected_answer")),
                                options=resp.get("options"),
                                explanation=resp.get("explanation"),
                                topic_tags=resp.get("topic_tags", [topic_name]),
                                learning_outcome_id=assigned_lo,
                                course_outcome_mapping=assigned_co_map,
                                generation_confidence=0.75,
                                vetting_status="pending",
                                generation_metadata={
                                    "source": "chapter_generation",
                                    "topic_name": topic_name,
                                    "has_reference_context": bool(reference_context),
                                },
                            )
                            db.add(question)
                            await db.commit()
                            await db.refresh(question)

                            generated_texts.append(candidate_text)
                            generated_embeddings.append(candidate_emb)
                            questions_generated += 1

                            progress = 10 + int((questions_generated / max(total_questions, 1)) * 85)
                            yield f"data: {json.dumps({'status': 'generating', 'progress': min(progress, 95), 'current_question': questions_generated, 'total_questions': total_questions, 'message': f'Generated {questions_generated}/{total_questions} questions', 'question': {'id': str(question.id), 'question_text': question.question_text[:100] + ('...' if len(question.question_text) > 100 else ''), 'question_type': question.question_type, 'marks': question.marks, 'learning_outcome_id': question.learning_outcome_id, 'course_outcome_mapping': question.course_outcome_mapping}})}\n\n"
                            break

                        if not accepted:
                            continue
                    except Exception as e:
                        logger.error(f"[{request_id}] Error generating question: {e}")
                        questions_failed += 1
                        await db.rollback()
                        continue

            # Update subject stats
            try:
                from app.models.subject import Subject as SubjModel
                result = await db.execute(select(SubjModel).where(SubjModel.id == uuid.UUID(subject_id_str)))
                subj = result.scalar_one_or_none()
                if subj:
                    subj.total_questions = (subj.total_questions or 0) + questions_generated
                    await db.commit()
            except Exception as e:
                logger.error(f"[{request_id}] Error updating subject stats: {e}")

            yield f"data: {json.dumps({'status': 'complete', 'progress': 100, 'current_question': questions_generated, 'total_questions': total_questions, 'message': f'Generated {questions_generated} questions' + (f' ({questions_failed} failed)' if questions_failed > 0 else '')})}\n\n"
            logger.info(f"[{request_id}] Chapter gen complete: {questions_generated} generated, {questions_failed} failed")

        except Exception as e:
            logger.error(f"[{request_id}] Chapter generation failed: {e}")
            yield f"data: {json.dumps({'status': 'error', 'progress': 0, 'message': f'Generation failed: {str(e)}'})}\n\n"
        finally:
            try:
                await db.close()
            except Exception:
                pass
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
    "bloom_level": "understand",
    "learning_outcome": "LO1",
    "course_outcome": "CO1"
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
    "bloom_level": "apply",
    "learning_outcome": "LO1",
    "course_outcome": "CO1"
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
    "bloom_level": "analyze",
    "learning_outcome": "LO1",
    "course_outcome": "CO1"
}"""



