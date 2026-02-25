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
            # Extract text with page-level information
            pages_data = await self._extract_text_with_pages(str(storage_path), mime_type)
            
            # Update document metadata with page info
            document.document_metadata = {
                **(document.document_metadata or {}),
                "total_pages": len(pages_data),
                "document_name": pages_data[0].get("document_name") if pages_data else filename,
            }

            # Chunk the document with page tracking
            chunks = self._chunk_text_with_pages(pages_data)

            # Create embeddings and store chunks
            total_tokens = 0
            for idx, chunk_data in enumerate(chunks):
                embedding = await self.embedding_service.get_embedding(chunk_data["text"])
                
                # Build comprehensive chunk metadata
                chunk_metadata = chunk_data.get("metadata", {})
                chunk_metadata["source_info"] = {
                    "document_name": chunk_data.get("document_name", filename),
                    "page_number": chunk_data.get("page_number"),
                    "page_range": chunk_data.get("page_range"),
                    "position_in_page": chunk_data.get("position_in_page"),
                    "position_percentage": chunk_data.get("position_percentage"),
                }
                
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    chunk_text=chunk_data["text"],
                    chunk_embedding=embedding,
                    token_count=chunk_data["token_count"],
                    page_number=chunk_data.get("page_number"),
                    section_heading=chunk_data.get("section_heading"),
                    chunk_metadata=chunk_metadata,
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
        """Process document: extract text with page info, chunk, and create embeddings."""
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

                # Extract text with page-level information
                pages_data = await self._extract_text_with_pages(document.storage_path, document.mime_type)
                
                # Store document metadata including page count
                document.document_metadata = {
                    **(document.document_metadata or {}),
                    "total_pages": len(pages_data),
                    "document_name": pages_data[0].get("document_name") if pages_data else document.filename,
                }

                # Chunk the document with page tracking
                chunks = self._chunk_text_with_pages(pages_data)

                # Create embeddings and store chunks
                total_tokens = 0
                for idx, chunk_data in enumerate(chunks):
                    embedding = await self.embedding_service.get_embedding(chunk_data["text"])
                    
                    # Build comprehensive chunk metadata
                    chunk_metadata = chunk_data.get("metadata", {})
                    chunk_metadata["source_info"] = {
                        "document_name": chunk_data.get("document_name", document.filename),
                        "page_number": chunk_data.get("page_number"),
                        "page_range": chunk_data.get("page_range"),
                        "position_in_page": chunk_data.get("position_in_page"),
                        "position_percentage": chunk_data.get("position_percentage"),
                    }
                    
                    chunk = DocumentChunk(
                        document_id=document_id,
                        chunk_index=idx,
                        chunk_text=chunk_data["text"],
                        chunk_embedding=embedding,
                        token_count=chunk_data["token_count"],
                        page_number=chunk_data.get("page_number"),
                        section_heading=chunk_data.get("section_heading"),
                        chunk_metadata=chunk_metadata,
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
        """Extract text from document based on file type (legacy method for compatibility)."""
        pages = await self._extract_text_with_pages(file_path, mime_type)
        return "\n\n".join([p["text"] for p in pages])
    
    async def _extract_text_with_pages(self, file_path: str, mime_type: str) -> List[dict]:
        """
        Extract text from document with page-level metadata.
        
        Returns a list of dicts with structure:
        {
            "page_number": int,
            "text": str,
            "blocks": [{"text": str, "position": {"top": float, "left": float, "bottom": float, "right": float}}]
        }
        """
        import fitz  # PyMuPDF
        from pathlib import Path

        document_name = Path(file_path).stem

        if mime_type == "application/pdf":
            pages_data = []
            with fitz.open(file_path) as doc:
                for page_num, page in enumerate(doc, start=1):
                    # Extract text blocks with position info
                    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
                    text_blocks = []
                    
                    for block in blocks:
                        if block.get("type") == 0:  # Text block
                            block_text = ""
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    block_text += span.get("text", "")
                                block_text += "\n"
                            
                            if block_text.strip():
                                text_blocks.append({
                                    "text": block_text.strip(),
                                    "position": {
                                        "top": block.get("bbox", [0, 0, 0, 0])[1],
                                        "left": block.get("bbox", [0, 0, 0, 0])[0],
                                        "bottom": block.get("bbox", [0, 0, 0, 0])[3],
                                        "right": block.get("bbox", [0, 0, 0, 0])[2],
                                    }
                                })
                    
                    page_height = page.rect.height
                    full_text = page.get_text()
                    
                    pages_data.append({
                        "page_number": page_num,
                        "text": full_text,
                        "page_height": page_height,
                        "blocks": text_blocks,
                        "document_name": document_name,
                    })
            
            return pages_data
        
        elif mime_type == "text/plain":
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
            # Treat entire text file as one page
            return [{
                "page_number": 1,
                "text": content,
                "page_height": None,
                "blocks": [{"text": content, "position": {"top": 0, "left": 0, "bottom": 100, "right": 100}}],
                "document_name": document_name,
            }]
        
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            from docx import Document as DocxDocument
            doc = DocxDocument(file_path)
            # DOCX doesn't have clear page breaks, treat paragraphs with estimated page grouping
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            
            # Estimate ~40 lines per page for DOCX
            lines_per_page = 40
            pages_data = []
            current_page = 1
            current_blocks = []
            current_line_count = 0
            
            for para in paragraphs:
                para_lines = para.count('\n') + 1
                if current_line_count + para_lines > lines_per_page and current_blocks:
                    pages_data.append({
                        "page_number": current_page,
                        "text": "\n\n".join([b["text"] for b in current_blocks]),
                        "page_height": None,
                        "blocks": current_blocks,
                        "document_name": document_name,
                    })
                    current_page += 1
                    current_blocks = []
                    current_line_count = 0
                
                current_blocks.append({
                    "text": para,
                    "position": {"top": current_line_count * 2.5, "left": 0, "bottom": (current_line_count + para_lines) * 2.5, "right": 100}
                })
                current_line_count += para_lines
            
            # Add remaining content
            if current_blocks:
                pages_data.append({
                    "page_number": current_page,
                    "text": "\n\n".join([b["text"] for b in current_blocks]),
                    "page_height": None,
                    "blocks": current_blocks,
                    "document_name": document_name,
                })
            
            return pages_data if pages_data else [{"page_number": 1, "text": "", "page_height": None, "blocks": [], "document_name": document_name}]
        
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

    def _chunk_text_with_pages(
        self,
        pages_data: List[dict],
        chunk_size: int = None,
        chunk_overlap: int = None,
    ) -> List[dict]:
        """
        Chunk text with page-level tracking for source attribution.
        
        Each chunk contains:
        - text: The chunk content
        - token_count: Number of tokens
        - page_number: Primary page the chunk is from
        - page_range: [start_page, end_page] if chunk spans pages
        - position_in_page: "top", "middle", or "bottom" based on vertical position
        - section_heading: Detected section heading if any
        - document_name: Name of the source document
        - source_blocks: List of block positions this chunk came from
        - metadata: Additional metadata (has_code, has_math, etc.)
        """
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        import re
        
        chunk_size = chunk_size or settings.CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n\n", "\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
            length_function=len,
            is_separator_regex=False,
        )
        
        chunks = []
        
        # Build a mapping of character positions to page/block info
        full_text = ""
        char_to_page = []  # List of (char_index, page_num, block_info)
        
        for page in pages_data:
            page_num = page["page_number"]
            page_text = page["text"]
            page_height = page.get("page_height", 100) or 100
            document_name = page.get("document_name", "Unknown")
            
            start_idx = len(full_text)
            full_text += page_text + "\n\n"
            
            # Track position within page
            for i, char in enumerate(page_text):
                char_to_page.append({
                    "page_number": page_num,
                    "document_name": document_name,
                    "page_height": page_height,
                    "char_pos_in_page": i,
                    "page_text_length": len(page_text),
                })
            # Add separators
            for _ in range(2):
                char_to_page.append({
                    "page_number": page_num,
                    "document_name": document_name,
                    "page_height": page_height,
                    "char_pos_in_page": len(page_text),
                    "page_text_length": len(page_text),
                })
        
        # Split the combined text
        raw_chunks = splitter.split_text(full_text)
        
        # Map each chunk back to its source pages
        current_pos = 0
        for chunk_text in raw_chunks:
            chunk_text_stripped = chunk_text.strip()
            if not chunk_text_stripped:
                continue
            
            # Find where this chunk starts in the full text
            chunk_start = full_text.find(chunk_text, current_pos)
            if chunk_start == -1:
                chunk_start = current_pos
            chunk_end = chunk_start + len(chunk_text)
            current_pos = chunk_start + 1
            
            # Determine page range and position
            pages_in_chunk = set()
            positions_in_page = []
            document_names = set()
            
            for i in range(chunk_start, min(chunk_end, len(char_to_page))):
                info = char_to_page[i]
                pages_in_chunk.add(info["page_number"])
                document_names.add(info["document_name"])
                
                # Calculate vertical position (0-100%)
                if info["page_text_length"] > 0:
                    pos_pct = (info["char_pos_in_page"] / info["page_text_length"]) * 100
                    positions_in_page.append(pos_pct)
            
            page_list = sorted(pages_in_chunk)
            primary_page = page_list[0] if page_list else 1
            page_range = [page_list[0], page_list[-1]] if page_list else [1, 1]
            
            # Determine position in page (top/middle/bottom)
            avg_position = sum(positions_in_page) / len(positions_in_page) if positions_in_page else 50
            if avg_position < 33:
                position_label = "top"
            elif avg_position < 66:
                position_label = "middle"
            else:
                position_label = "bottom"
            
            # Extract section heading if present
            section_heading = self._extract_section_heading(chunk_text_stripped)
            
            # Extract metadata
            metadata = self._extract_chunk_metadata(chunk_text_stripped)
            metadata["source_info"] = {
                "page_number": primary_page,
                "page_range": page_range,
                "position_in_page": position_label,
                "position_percentage": round(avg_position, 1),
                "document_name": list(document_names)[0] if document_names else "Unknown",
            }
            
            chunks.append({
                "text": chunk_text_stripped,
                "token_count": len(chunk_text_stripped.split()),
                "page_number": primary_page,
                "page_range": page_range,
                "position_in_page": position_label,
                "position_percentage": round(avg_position, 1),
                "section_heading": section_heading,
                "document_name": list(document_names)[0] if document_names else "Unknown",
                "metadata": metadata,
            })
        
        return chunks
    
    def _extract_section_heading(self, text: str) -> Optional[str]:
        """Extract section heading from chunk if present at the beginning."""
        import re
        
        lines = text.strip().split('\n')
        if not lines:
            return None
        
        first_line = lines[0].strip()
        
        # Common heading patterns
        heading_patterns = [
            r'^(?:Chapter|Section|Part|Unit)\s+\d+[.:]?\s*(.+)$',
            r'^(\d+\.)+\s*(.+)$',  # Numbered headings like "1.2.3 Title"
            r'^([A-Z][A-Za-z\s]+):$',  # "Title:" format
            r'^([A-Z][A-Z\s]+)$',  # ALL CAPS headings
        ]
        
        for pattern in heading_patterns:
            match = re.match(pattern, first_line, re.IGNORECASE)
            if match:
                # Return the heading (last group usually contains the title)
                return match.group(match.lastindex) if match.lastindex else first_line
        
        # If first line is short and looks like a title (< 80 chars, no sentence-ending punctuation)
        if len(first_line) < 80 and not re.search(r'[.!?]$', first_line):
            return first_line
        
        return None

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
        
        # Get all chunks with document relationship for filename access
        result = await self.db.execute(
            select(DocumentChunk)
            .options(selectinload(DocumentChunk.document))
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
