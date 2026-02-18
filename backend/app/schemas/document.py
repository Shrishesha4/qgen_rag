"""
Document-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
import uuid


class DocumentBase(BaseModel):
    """Base document schema."""
    filename: str


class DocumentCreate(DocumentBase):
    """Schema for document upload."""
    pass


class DocumentChunkResponse(BaseModel):
    """Schema for document chunk response."""
    id: uuid.UUID
    chunk_index: int
    chunk_text: str
    page_number: Optional[int]
    section_heading: Optional[str]
    token_count: Optional[int]

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    """Schema for document response."""
    id: uuid.UUID
    filename: str
    file_size_bytes: int
    mime_type: Optional[str]
    processing_status: str
    total_chunks: Optional[int]
    total_tokens: Optional[int]
    upload_timestamp: datetime
    processed_at: Optional[datetime]
    document_metadata: Optional[dict]
    questions_generated: Optional[int] = 0
    # Index type for novelty system
    index_type: str = "primary"  # primary, reference_book, template_paper
    subject_id: Optional[uuid.UUID] = None

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    """Schema for document in list view."""
    id: uuid.UUID
    filename: str
    processing_status: str
    upload_timestamp: datetime
    total_chunks: Optional[int]
    questions_generated: Optional[int] = 0
    index_type: str = "primary"

    model_config = {"from_attributes": True}


class PaginationInfo(BaseModel):
    """Schema for pagination info."""
    page: int
    limit: int
    total: int
    total_pages: int


class DocumentListResponse(BaseModel):
    """Schema for document list response."""
    documents: List[DocumentListItem]
    pagination: PaginationInfo


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response."""
    document_id: uuid.UUID
    filename: str
    status: str
    message: str


class ReferenceDocumentUploadRequest(BaseModel):
    """Schema for uploading reference documents (books/template papers)."""
    subject_id: uuid.UUID = Field(..., description="Subject to associate the document with")
    index_type: Literal["reference_book", "template_paper"] = Field(
        ..., description="Type of reference material"
    )
