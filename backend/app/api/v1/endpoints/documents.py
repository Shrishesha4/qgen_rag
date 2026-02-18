"""
Document management API endpoints.
"""

import os
from typing import Optional, Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentListItem,
    DocumentUploadResponse,
    PaginationInfo,
)
from app.services.document_service import DocumentService
from app.api.v1.deps import get_current_user, rate_limit
from app.models.user import User


router = APIRouter()


MIME_TYPE_MAPPING = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(rate_limit(requests=10, window_seconds=3600)),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document for processing.
    Supported formats: PDF, DOCX, TXT
    """
    # Validate file extension
    filename = file.filename or "document"
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
    
    # Determine mime type
    mime_type = MIME_TYPE_MAPPING.get(ext, "application/octet-stream")
    
    # Upload document
    document_service = DocumentService(db)
    
    try:
        document = await document_service.upload_document(
            user_id=current_user.id,
            filename=filename,
            file_content=content,
            mime_type=mime_type,
        )
        
        return DocumentUploadResponse(
            document_id=document.id,
            filename=document.filename,
            status=document.processing_status,
            message="Document uploaded successfully. Processing started.",
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all documents for the current user.
    """
    document_service = DocumentService(db)
    
    documents, pagination = await document_service.get_documents(
        user_id=current_user.id,
        page=page,
        limit=limit,
        status=status,
    )
    
    return DocumentListResponse(
        documents=[
            DocumentListItem(
                id=doc.id,
                filename=doc.filename,
                processing_status=doc.processing_status,
                upload_timestamp=doc.upload_timestamp,
                total_chunks=doc.total_chunks,
                questions_generated=getattr(doc, "questions_generated", 0),
            )
            for doc in documents
        ],
        pagination=pagination,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get document details by ID.
    """
    document_service = DocumentService(db)
    
    document = await document_service.get_document(document_id, current_user.id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a document and all associated data.
    """
    document_service = DocumentService(db)
    
    success = await document_service.delete_document(document_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return {"message": "Document deleted successfully"}


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all chunks for a document (for debugging/preview).
    """
    document_service = DocumentService(db)
    
    try:
        chunks = await document_service.get_document_chunks(document_id, current_user.id)
        
        return {
            "document_id": str(document_id),
            "total_chunks": len(chunks),
            "chunks": [
                {
                    "index": chunk.chunk_index,
                    "text": chunk.chunk_text[:500] + "..." if len(chunk.chunk_text) > 500 else chunk.chunk_text,
                    "token_count": chunk.token_count,
                    "page_number": chunk.page_number,
                }
                for chunk in chunks
            ],
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get document processing status.
    """
    document_service = DocumentService(db)
    
    document = await document_service.get_document(document_id, current_user.id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return {
        "document_id": str(document.id),
        "filename": document.filename,
        "status": document.processing_status,
        "total_chunks": document.total_chunks,
        "total_tokens": document.total_tokens,
        "processed_at": document.processed_at,
    }


# ============== Reference Document Management ==============

@router.post("/reference/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_reference_document(
    file: UploadFile = File(..., description="Reference book or template paper PDF"),
    subject_id: str = Form(..., description="Subject ID to associate the document with"),
    index_type: Literal["reference_book", "template_paper"] = Form(..., description="Type of reference material"),
    current_user: User = Depends(rate_limit(requests=20, window_seconds=3600)),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a reference document (book or template paper) for novelty comparison.
    
    Reference documents are indexed separately from teaching materials and are used
    for novelty validation and intelligent regeneration of questions.
    
    - reference_book: Used for conceptual inspiration when regenerating questions
    - template_paper: Used for detecting similarity with existing exam questions
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
    
    # Validate subject_id
    try:
        parsed_subject_id = uuid.UUID(subject_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subject_id format",
        )
    
    # Determine mime type
    mime_type = MIME_TYPE_MAPPING.get(ext, "application/octet-stream")
    
    # Upload reference document
    document_service = DocumentService(db)
    
    try:
        document = await document_service.upload_reference_document(
            user_id=current_user.id,
            filename=filename,
            file_content=content,
            mime_type=mime_type,
            subject_id=parsed_subject_id,
            index_type=index_type,
        )
        
        return DocumentUploadResponse(
            document_id=document.id,
            filename=document.filename,
            status=document.processing_status,
            message=f"{index_type.replace('_', ' ').title()} uploaded successfully. Processing started.",
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("/reference/list")
async def list_reference_documents(
    subject_id: Optional[uuid.UUID] = Query(None, description="Filter by subject"),
    index_type: Optional[str] = Query(None, description="Filter by type: reference_book, template_paper"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List reference documents (books and template papers) for the current user.
    Returns documents split by type for easier UI handling.
    """
    document_service = DocumentService(db)
    
    documents = await document_service.get_reference_documents(
        user_id=current_user.id,
        subject_id=subject_id,
        index_type=index_type,
    )
    
    # Convert documents to response format with all required fields
    doc_responses = [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "file_size_bytes": doc.file_size_bytes,
            "mime_type": doc.mime_type,
            "index_type": doc.index_type,
            "subject_id": str(doc.subject_id) if doc.subject_id else None,
            "processing_status": doc.processing_status,
            "total_chunks": doc.total_chunks,
            "upload_timestamp": doc.upload_timestamp.isoformat() if doc.upload_timestamp else None,
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
        }
        for doc in documents
    ]
    
    # Split by index_type for the response
    reference_books = [d for d in doc_responses if d["index_type"] == "reference_book"]
    template_papers = [d for d in doc_responses if d["index_type"] == "template_paper"]
    
    return {
        "reference_books": reference_books,
        "template_papers": template_papers,
    }
