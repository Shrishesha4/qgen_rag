"""
Re-embed all document chunks and questions with the currently configured model.

Run this after switching embedding models (e.g. all-MiniLM-L6-v2 → BAAI/bge-base-en-v1.5)
to repopulate the NULLed-out vector columns produced by migration 006.

Usage (from backend/):
    python -m scripts.reembed_all

Or directly:
    python scripts/reembed_all.py
"""

import asyncio
import sys
import os

# Allow running as a script from the backend/ directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.document import DocumentChunk
from app.models.question import Question
from app.services.embedding_service import EmbeddingService

BATCH = 64  # chunks per embedding batch


async def reembed_chunks(svc: EmbeddingService) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DocumentChunk.id, DocumentChunk.chunk_text)
            .where(DocumentChunk.chunk_embedding.is_(None))
            .order_by(DocumentChunk.id)
        )
        rows = result.all()

    if not rows:
        print("  No document chunks need re-embedding.")
        return

    print(f"  Re-embedding {len(rows)} document chunks …")
    for start in range(0, len(rows), BATCH):
        batch = rows[start : start + BATCH]
        ids   = [r.id for r in batch]
        texts = [r.chunk_text for r in batch]

        embeddings = await svc.get_embeddings(texts, is_query=False)

        async with AsyncSessionLocal() as db:
            for chunk_id, emb in zip(ids, embeddings):
                await db.execute(
                    update(DocumentChunk)
                    .where(DocumentChunk.id == chunk_id)
                    .values(chunk_embedding=emb)
                )
            await db.commit()

        done = min(start + BATCH, len(rows))
        print(f"    {done}/{len(rows)} chunks done", end="\r", flush=True)

    print(f"\n  ✓ Document chunks complete.")


async def reembed_questions(svc: EmbeddingService) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Question.id, Question.question_text)
            .where(Question.question_embedding.is_(None))
            .order_by(Question.id)
        )
        rows = result.all()

    if not rows:
        print("  No questions need re-embedding.")
        return

    print(f"  Re-embedding {len(rows)} questions …")
    for start in range(0, len(rows), BATCH):
        batch = rows[start : start + BATCH]
        ids   = [r.id for r in batch]
        texts = [r.question_text for r in batch]

        embeddings = await svc.get_embeddings(texts, is_query=False)

        async with AsyncSessionLocal() as db:
            for q_id, emb in zip(ids, embeddings):
                await db.execute(
                    update(Question)
                    .where(Question.id == q_id)
                    .values(question_embedding=emb)
                )
            await db.commit()

        done = min(start + BATCH, len(rows))
        print(f"    {done}/{len(rows)} questions done", end="\r", flush=True)

    print(f"\n  ✓ Questions complete.")


async def main() -> None:
    from app.core.config import settings
    print(f"Model  : {settings.EMBEDDING_MODEL}")
    print(f"Dim    : {settings.EMBEDDING_DIMENSION}")
    print()

    svc = EmbeddingService()

    print("=== Document chunks ===")
    await reembed_chunks(svc)

    print()
    print("=== Questions ===")
    await reembed_questions(svc)

    print()
    print("Done. All embeddings updated to the current model.")


if __name__ == "__main__":
    asyncio.run(main())
