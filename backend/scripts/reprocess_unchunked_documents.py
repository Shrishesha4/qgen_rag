#!/usr/bin/env python3
"""
Reprocess documents that have 0 chunks.

These are typically scanned PDFs that failed native text extraction
and didn't have OCR available at the time of processing.

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/reprocess_unchunked_documents.py [--dry-run] [--limit N]
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, "/home/admin/serv/vquest/backend")

from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def find_unchunked_documents(limit: int = None) -> list[Document]:
    """Find all completed documents that have 0 chunks."""
    async with AsyncSessionLocal() as db:
        # Subquery to count chunks per document
        chunk_counts = (
            select(
                DocumentChunk.document_id,
                func.count(DocumentChunk.id).label("chunk_count"),
            )
            .group_by(DocumentChunk.document_id)
            .subquery()
        )

        # Find completed documents with 0 chunks or no chunks at all
        query = (
            select(Document)
            .outerjoin(chunk_counts, Document.id == chunk_counts.c.document_id)
            .where(
                and_(
                    Document.processing_status == "completed",
                    # Either no chunks exist (NULL) or count is 0
                    (chunk_counts.c.chunk_count == None) | (chunk_counts.c.chunk_count == 0),
                )
            )
            .order_by(Document.upload_timestamp.desc())
        )

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        docs = result.scalars().all()
        
        # Detach from session before returning
        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "storage_path": doc.storage_path,
                "mime_type": doc.mime_type,
                "index_type": doc.index_type,
                "subject_id": doc.subject_id,
                "upload_timestamp": doc.upload_timestamp,
                "metadata": doc.document_metadata,
            }
            for doc in docs
        ]


async def reprocess_document(doc_info: dict) -> dict:
    """Reprocess a single document with OCR support."""
    doc_id = doc_info["id"]
    filename = doc_info["filename"]
    
    logger.info(f"Processing: {filename} ({doc_id[:8]}...)")
    
    try:
        async with AsyncSessionLocal() as db:
            # Fetch fresh document
            result = await db.execute(
                select(Document).where(Document.id == doc_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                return {"id": doc_id, "status": "error", "message": "Document not found"}
            
            # Reset status to processing
            document.processing_status = "processing"
            document.document_metadata = {
                **(document.document_metadata or {}),
                "reprocess_started_at": datetime.now(timezone.utc).isoformat(),
                "processing_step": "reprocessing",
                "processing_progress": 0,
            }
            await db.commit()
        
        # Create embedding service
        embedding_service = EmbeddingService()
        
        # Create document service and run processing
        async with AsyncSessionLocal() as db:
            doc_service = DocumentService(db, embedding_service)
            
            # Call the internal processing method
            await doc_service._process_document(doc_id)
        
        # Check result
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Document).where(Document.id == doc_id)
            )
            document = result.scalar_one_or_none()
            
            chunk_result = await db.execute(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.document_id == doc_id
                )
            )
            chunk_count = chunk_result.scalar()
            
            metadata = document.document_metadata or {}
            used_ocr = metadata.get("used_ocr", False)
            
            return {
                "id": doc_id,
                "filename": filename,
                "status": document.processing_status,
                "chunks": chunk_count,
                "tokens": document.total_tokens,
                "used_ocr": used_ocr,
                "message": f"Processed with {'OCR' if used_ocr else 'native extraction'}",
            }
            
    except Exception as e:
        logger.error(f"Failed to process {filename}: {e}")
        return {
            "id": doc_id,
            "filename": filename,
            "status": "error",
            "message": str(e),
        }


async def main():
    parser = argparse.ArgumentParser(
        description="Reprocess documents that have 0 chunks"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list documents, don't reprocess",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of documents to process",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check OCR availability
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        logger.info(f"✅ Tesseract OCR available: {pytesseract.get_tesseract_version()}")
    except Exception as e:
        logger.warning(f"⚠️  Tesseract OCR not available: {e}")
        logger.warning("   Scanned PDFs may still fail to extract text")

    logger.info(f"OCR_ENABLED={settings.OCR_ENABLED}")
    logger.info(f"OCR_MIN_TEXT_PER_PAGE={settings.OCR_MIN_TEXT_PER_PAGE}")
    logger.info(f"OCR_SPARSE_THRESHOLD={settings.OCR_SPARSE_THRESHOLD}")
    logger.info("")

    # Find unchunked documents
    logger.info("Finding documents with 0 chunks...")
    documents = await find_unchunked_documents(limit=args.limit)

    if not documents:
        logger.info("✅ No unchunked documents found!")
        return

    logger.info(f"Found {len(documents)} documents with 0 chunks:")
    print()
    
    for doc in documents:
        metadata = doc.get("metadata") or {}
        detail = metadata.get("processing_detail", "")
        print(f"  {doc['id'][:8]}... | {doc['index_type']:15} | {doc['filename'][:45]}")
        if detail:
            print(f"           └─ {detail}")
    
    print()

    if args.dry_run:
        logger.info("Dry run mode - not processing any documents")
        return

    # Confirm before processing
    confirm = input(f"Reprocess {len(documents)} documents? [y/N]: ")
    if confirm.lower() != "y":
        logger.info("Aborted")
        return

    # Process documents
    results = {"success": 0, "failed": 0, "total_chunks": 0, "ocr_used": 0}
    
    for i, doc in enumerate(documents, 1):
        logger.info(f"\n[{i}/{len(documents)}] Processing {doc['filename']}")
        
        result = await reprocess_document(doc)
        
        if result["status"] == "completed":
            results["success"] += 1
            results["total_chunks"] += result.get("chunks", 0)
            if result.get("used_ocr"):
                results["ocr_used"] += 1
            logger.info(f"  ✅ {result['chunks']} chunks, {result.get('tokens', 0)} tokens")
        else:
            results["failed"] += 1
            logger.error(f"  ❌ {result.get('message', 'Unknown error')}")

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Processed: {results['success'] + results['failed']}")
    print(f"  Success:   {results['success']}")
    print(f"  Failed:    {results['failed']}")
    print(f"  OCR used:  {results['ocr_used']}")
    print(f"  Total new chunks: {results['total_chunks']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
