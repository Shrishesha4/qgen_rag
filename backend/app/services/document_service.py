"""
Document service for file upload and processing.
"""

import os
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, BinaryIO
from pathlib import Path
import uuid
import aiofiles

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentChunk
from app.models.question import Question
from app.schemas.document import DocumentResponse, DocumentListItem, PaginationInfo
from app.core.config import settings
from app.services.embedding_service import EmbeddingService


class DocumentService:
    """Service for document management and processing."""

    def __init__(self, db: AsyncSession, embedding_service: Optional[EmbeddingService] = None):
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()

    async def upload_document(
        self,
        user_id: uuid.UUID,
        filename: str,
        file_content: bytes,
        mime_type: str,
        index_type: str = "primary",
        subject_id: Optional[uuid.UUID] = None,
    ) -> Document:
        """Upload and process a document."""
        # Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)

        # Check for duplicate (same user, same file)
        existing = await self.db.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.file_hash == file_hash,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Document already uploaded")

        # Create storage path
        storage_dir = Path(settings.UPLOAD_DIR) / str(user_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        unique_filename = f"{uuid.uuid4()}_{filename}"
        storage_path = storage_dir / unique_filename

        # Save file
        async with aiofiles.open(storage_path, "wb") as f:
            await f.write(file_content)

        # Create document record
        document = Document(
            user_id=user_id,
            filename=filename,
            file_hash=file_hash,
            file_size_bytes=file_size,
            mime_type=mime_type,
            storage_path=str(storage_path),
            processing_status="pending",
            index_type=index_type,
            subject_id=subject_id,
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        # Start async processing
        asyncio.create_task(self._process_document(document.id))

        return document

    async def upload_reference_document(
        self,
        user_id: uuid.UUID,
        filename: str,
        file_content: bytes,
        mime_type: str,
        subject_id: uuid.UUID,
        index_type: str,  # reference_book or template_paper
    ) -> Document:
        """
        Upload a reference document (book or template paper).
        These are stored in a separate index for novelty comparison.
        """
        if index_type not in ("reference_book", "template_paper", "reference_questions"):
            raise ValueError("index_type must be 'reference_book', 'template_paper', or 'reference_questions'")
        
        return await self.upload_document(
            user_id=user_id,
            filename=filename,
            file_content=file_content,
            mime_type=mime_type,
            index_type=index_type,
            subject_id=subject_id,
        )

    async def upload_and_process_document(
        self,
        user_id: uuid.UUID,
        filename: str,
        file_content: bytes,
        mime_type: str,
        context: Optional[str] = None,
    ) -> Document:
        """
        Upload and synchronously process a document.
        Used for quick generation where we need the document ready immediately.
        """
        # Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)

        # Check for duplicate (same user, same file)
        existing = await self.db.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.file_hash == file_hash,
            )
        )
        existing_doc = existing.scalar_one_or_none()
        if existing_doc:
            # If already processed, return it
            if existing_doc.processing_status == "completed":
                return existing_doc
            raise ValueError("Document already uploaded and is processing")

        # Create storage path
        storage_dir = Path(settings.UPLOAD_DIR) / str(user_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        unique_filename = f"{uuid.uuid4()}_{filename}"
        storage_path = storage_dir / unique_filename

        # Save file
        async with aiofiles.open(storage_path, "wb") as f:
            await f.write(file_content)

        # Create document record with context
        document = Document(
            user_id=user_id,
            filename=filename,
            file_hash=file_hash,
            file_size_bytes=file_size,
            mime_type=mime_type,
            storage_path=str(storage_path),
            processing_status="processing",
            document_metadata={"context": context} if context else {},
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        try:
            # Extract text based on file type
            text_content = await self._extract_text(str(storage_path), mime_type)

            # Chunk the document
            chunks = self._chunk_text(text_content)

            # Create embeddings and store chunks
            total_tokens = 0
            for idx, chunk_data in enumerate(chunks):
                embedding = await self.embedding_service.get_embedding(chunk_data["text"])
                
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    chunk_text=chunk_data["text"],
                    chunk_embedding=embedding,
                    token_count=chunk_data["token_count"],
                    page_number=chunk_data.get("page_number"),
                    section_heading=chunk_data.get("section_heading"),
                    chunk_metadata=chunk_data.get("metadata", {}),
                )
                self.db.add(chunk)
                total_tokens += chunk_data["token_count"]

            # Update document
            document.total_chunks = len(chunks)
            document.total_tokens = total_tokens
            document.processing_status = "completed"
            document.processed_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(document)
            
            return document

        except Exception as e:
            document.processing_status = "failed"
            document.document_metadata = {"error": str(e), "context": context}
            await self.db.commit()
            raise ValueError(f"Document processing failed: {str(e)}")

    async def _process_document(self, document_id: uuid.UUID):
        """Process document: extract text, chunk, and create embeddings."""
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()
                if not document:
                    return

                # Update status
                document.processing_status = "processing"
                await db.commit()

                # Extract text based on file type
                text_content = await self._extract_text(document.storage_path, document.mime_type)

                # Chunk the document
                chunks = self._chunk_text(text_content)

                # Create embeddings and store chunks
                total_tokens = 0
                for idx, chunk_data in enumerate(chunks):
                    embedding = await self.embedding_service.get_embedding(chunk_data["text"])
                    
                    chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_index=idx,
                        chunk_text=chunk_data["text"],
                        chunk_embedding=embedding,
                        token_count=chunk_data["token_count"],
                        page_number=chunk_data.get("page_number"),
                        section_heading=chunk_data.get("section_heading"),
                        chunk_metadata=chunk_data.get("metadata", {}),
                    )
                    db.add(chunk)
                    total_tokens += chunk_data["token_count"]

                # Update document
                document.total_chunks = len(chunks)
                document.total_tokens = total_tokens
                document.processing_status = "completed"
                document.processed_at = datetime.now(timezone.utc)
                await db.commit()

            except Exception as e:
                document.processing_status = "failed"
                document.document_metadata = {"error": str(e)}
                await db.commit()

    async def _extract_text(self, file_path: str, mime_type: str) -> str:
        """Extract text from document based on file type."""
        import fitz  # PyMuPDF

        if mime_type == "application/pdf":
            text_parts = []
            with fitz.open(file_path) as doc:
                for page in doc:
                    text_parts.append(page.get_text())
            return "\n\n".join(text_parts)
        
        elif mime_type == "text/plain":
            async with aiofiles.open(file_path, "r") as f:
                return await f.read()
        
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            from docx import Document as DocxDocument
            doc = DocxDocument(file_path)
            return "\n\n".join([para.text for para in doc.paragraphs])
        
        else:
            raise ValueError(f"Unsupported file type: {mime_type}")

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ) -> List[dict]:
        """
        Chunk text into smaller pieces for embedding using semantic-aware splitting.
        Uses RecursiveCharacterTextSplitter for better context preservation.
        """
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        import re
        
        chunk_size = chunk_size or settings.CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

        # Use RecursiveCharacterTextSplitter for semantic-aware chunking
        # It tries to split on these separators in order, preferring larger semantic units
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n\n",      # Major section breaks
                "\n\n",        # Paragraph breaks
                "\n",          # Line breaks
                ". ",          # Sentence endings
                "? ",          # Question endings
                "! ",          # Exclamation endings
                "; ",          # Semicolon breaks
                ", ",          # Comma breaks
                " ",           # Word breaks
                ""             # Character-level fallback
            ],
            length_function=len,
            is_separator_regex=False,
        )
        
        # Split the text
        raw_chunks = splitter.split_text(text)
        
        # Build chunk metadata
        chunks = []
        for idx, chunk_text in enumerate(raw_chunks):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue
            
            # Extract metadata from chunk content
            metadata = self._extract_chunk_metadata(chunk_text)
            
            chunks.append({
                "text": chunk_text,
                "token_count": len(chunk_text.split()),
                "metadata": metadata,
            })

        return chunks

    def _extract_chunk_metadata(self, text: str) -> dict:
        """Extract metadata from chunk content for filtering."""
        import re
        
        metadata = {}
        
        # Check for code blocks
        metadata["has_code"] = bool(re.search(
            r'```|def\s+\w+|class\s+\w+|function\s+\w+|import\s+\w+|from\s+\w+|const\s+\w+|let\s+\w+|var\s+\w+',
            text
        ))
        
        # Check for mathematical content
        metadata["has_math"] = bool(re.search(
            r'\$.*\$|\d+\s*[+\-*/=<>≤≥]\s*\d+|√|∑|∏|∫|∂|∞|π|θ|α|β|γ|equation|formula|theorem',
            text,
            re.IGNORECASE
        ))
        
        # Check for lists
        metadata["has_list"] = bool(re.search(
            r'^\s*[-•*]\s+|^\s*\d+\.\s+|^\s*[a-z]\)\s+|^\s*[ivxlcdm]+\.\s+',
            text,
            re.MULTILINE | re.IGNORECASE
        ))
        
        # Check for tables
        metadata["has_table"] = bool(re.search(
            r'\|.*\|.*\||^\s*\+[-+]+\+\s*$',
            text,
            re.MULTILINE
        ))
        
        # Check for definitions/key terms
        metadata["has_definition"] = bool(re.search(
            r':\s*definition|defined\s+as|refers\s+to|means\s+that|is\s+known\s+as',
            text,
            re.IGNORECASE
        ))
        
        # Estimate complexity/difficulty based on various heuristics
        metadata["estimated_complexity"] = self._estimate_complexity(text)
        
        return metadata

    def _estimate_complexity(self, text: str) -> str:
        """Estimate the complexity of text content."""
        import re
        
        # Count complexity indicators
        complexity_score = 0
        
        # Long words (likely technical terms)
        long_words = len([w for w in text.split() if len(w) > 10])
        complexity_score += min(long_words / 5, 2)
        
        # Sentences per 100 words (lower = more complex)
        words = len(text.split())
        sentences = len(re.findall(r'[.!?]+', text))
        if words > 0 and sentences > 0:
            avg_sentence_length = words / sentences
            if avg_sentence_length > 25:
                complexity_score += 1
            if avg_sentence_length > 35:
                complexity_score += 1
        
        # Technical patterns
        if re.search(r'theorem|proof|lemma|corollary|hypothesis', text, re.IGNORECASE):
            complexity_score += 2
        if re.search(r'algorithm|complexity|optimization', text, re.IGNORECASE):
            complexity_score += 1
        
        # Classify
        if complexity_score >= 4:
            return "high"
        elif complexity_score >= 2:
            return "medium"
        else:
            return "low"

    async def get_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Document]:
        """Get document by ID (user-scoped)."""
        result = await self.db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_documents(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[Document], PaginationInfo]:
        """Get paginated documents for a user."""
        query = select(Document).where(Document.user_id == user_id)
        
        if status:
            query = query.where(Document.processing_status == status)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Get page
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Document.upload_timestamp.desc())
        result = await self.db.execute(query)
        documents = result.scalars().all()

        # Get question counts
        for doc in documents:
            q_result = await self.db.execute(
                select(func.count()).where(Question.document_id == doc.id)
            )
            doc.questions_generated = q_result.scalar_one()

        pagination = PaginationInfo(
            page=page,
            limit=limit,
            total=total,
            total_pages=(total + limit - 1) // limit,
        )

        return documents, pagination

    async def delete_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a document and all related data."""
        document = await self.get_document(document_id, user_id)
        if not document:
            return False

        # Delete file
        if os.path.exists(document.storage_path):
            os.remove(document.storage_path)

        # Delete from database (cascades to chunks and questions)
        await self.db.delete(document)
        await self.db.commit()
        return True

    async def get_document_chunks(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[DocumentChunk]:
        """Get all chunks for a document."""
        # Verify ownership
        document = await self.get_document(document_id, user_id)
        if not document:
            raise ValueError("Document not found")

        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return result.scalars().all()

    async def search_chunks(
        self,
        document_id: uuid.UUID,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[DocumentChunk]:
        """Search chunks by semantic similarity."""
        from pgvector.sqlalchemy import Vector
        
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        return result.scalars().all()

    async def hybrid_search(
        self,
        document_id: uuid.UUID,
        query: str,
        query_embedding: List[float],
        top_k: int = 5,
        alpha: float = 0.5,
    ) -> List[DocumentChunk]:
        """
        Hybrid search combining vector similarity and BM25 keyword matching.
        
        Args:
            document_id: Document to search within
            query: The text query for BM25 scoring
            query_embedding: Pre-computed embedding for semantic search
            top_k: Number of results to return
            alpha: Balance between semantic (1.0) and keyword (0.0) search
        
        Returns:
            Top-k chunks ranked by combined score
        """
        from rank_bm25 import BM25Okapi
        
        # Get all chunks for this document
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = list(result.scalars().all())
        
        if not chunks:
            return []
        
        # BM25 scoring
        tokenized_chunks = [c.chunk_text.lower().split() for c in chunks]
        bm25 = BM25Okapi(tokenized_chunks)
        bm25_scores = bm25.get_scores(query.lower().split())
        
        # Normalize BM25 scores to [0, 1]
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
        bm25_scores_normalized = [s / max_bm25 for s in bm25_scores]
        
        # Vector similarity scores
        vector_scores = []
        for chunk in chunks:
            # Check if embedding exists (handle numpy array truth value issue)
            if chunk.chunk_embedding is not None and len(chunk.chunk_embedding) > 0:
                sim = self.embedding_service.compute_similarity(
                    query_embedding, chunk.chunk_embedding
                )
                # Convert to [0, 1] range (cosine similarity is already [-1, 1])
                vector_scores.append((sim + 1) / 2)
            else:
                vector_scores.append(0)
        
        # Combine scores using weighted sum
        combined_scores = [
            alpha * vector_scores[i] + (1 - alpha) * bm25_scores_normalized[i]
            for i in range(len(chunks))
        ]
        
        # Sort by combined score and return top-k
        ranked = sorted(
            zip(chunks, combined_scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [chunk for chunk, _ in ranked[:top_k]]

    async def get_reference_documents(
        self,
        user_id: uuid.UUID,
        subject_id: Optional[uuid.UUID] = None,
        index_type: Optional[str] = None,
    ) -> List[Document]:
        """
        Get reference documents (books, template papers, and reference questions) for a user.
        Includes all processing statuses so users can see pending/processing uploads.
        """
        query = select(Document).where(
            Document.user_id == user_id,
            Document.index_type.in_(["reference_book", "template_paper", "reference_questions"]),
        )
        
        if subject_id:
            query = query.where(Document.subject_id == subject_id)
        
        if index_type:
            query = query.where(Document.index_type == index_type)
        
        query = query.order_by(Document.upload_timestamp.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_reference_chunks(
        self,
        user_id: uuid.UUID,
        subject_id: Optional[uuid.UUID] = None,
        index_type: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 10,
    ) -> List[DocumentChunk]:
        """
        Get chunks from reference documents.
        If query_embedding is provided, returns the most relevant chunks.
        Otherwise returns all chunks.
        """
        # Get reference documents
        docs = await self.get_reference_documents(user_id, subject_id, index_type)
        
        if not docs:
            return []
        
        doc_ids = [doc.id for doc in docs]
        
        # Get all chunks
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id.in_(doc_ids))
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = result.scalars().all()
        
        if not chunks:
            return []
        
        # If no query embedding, return all chunks
        if query_embedding is None:
            return chunks
        
        # Score and rank by similarity
        scored_chunks = []
        for chunk in chunks:
            if chunk.chunk_embedding is not None and len(chunk.chunk_embedding) > 0:
                similarity = self.embedding_service.compute_similarity(
                    query_embedding, chunk.chunk_embedding
                )
                scored_chunks.append((chunk, similarity))
        
        # Sort by similarity
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        return [c for c, _ in scored_chunks[:top_k]]

    async def get_primary_chunks_excluding_used(
        self,
        document_id: uuid.UUID,
        used_chunk_ids: List[uuid.UUID],
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
    ) -> List[DocumentChunk]:
        """
        Get primary document chunks excluding already-used ones.
        Useful for intelligent regeneration with alternative chunks.
        """
        # Get all chunks for the document
        result = await self.db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                ~DocumentChunk.id.in_(used_chunk_ids) if used_chunk_ids else True,
            )
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = result.scalars().all()
        
        if not chunks:
            return []
        
        # If no query embedding, return random selection
        if query_embedding is None:
            import random
            return random.sample(chunks, min(top_k, len(chunks)))
        
        # Score and rank by similarity
        scored_chunks = []
        for chunk in chunks:
            if chunk.chunk_embedding is not None and len(chunk.chunk_embedding) > 0:
                similarity = self.embedding_service.compute_similarity(
                    query_embedding, chunk.chunk_embedding
                )
                scored_chunks.append((chunk, similarity))
        
        # Sort by similarity
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        return [c for c, _ in scored_chunks[:top_k]]
