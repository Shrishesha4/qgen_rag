#!/usr/bin/env python
import argparse
import asyncio
import hashlib
import logging
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.endpoints.vetter import _reconstruct_prompt
from app.core.auth_database import AuthSessionLocal
from app.core.database import AsyncSessionLocal
from app.models.document import Document, DocumentChunk
from app.models.question import GenerationSession, Question
from app.models.training import TrainingPair, VettingLog
from app.models.user import ROLE_ADMIN, ROLE_TEACHER, ROLE_VETTER, User
from app.services.embedding_service import EmbeddingService
from app.services.question_service import QuestionGenerationService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("simulate_vetting_for_training")

DIFFICULTIES = ["easy", "medium", "hard"]
REJECTION_REASON_CODES = [
    "poor_grammar",
    "ambiguous_question",
    "poor_distractors",
    "too_easy",
    "too_hard",
    "formatting_issue",
    "explanation_missing",
    "not_standalone",
]
REJECTION_FEEDBACK = [
    "The question needs clearer wording and stronger pedagogical quality.",
    "The distractors are weak and the item feels too predictable.",
    "The question should be rewritten to improve clarity and assessment value.",
    "The question quality is acceptable for regeneration but not for direct approval.",
]
APPROVAL_NOTE = "Bulk simulation approval for training bootstrap"
REGEN_APPROVAL_NOTE = "Bulk simulation approval of first regenerated replacement"


async def resolve_vetter_id(explicit_vetter_id: str | None) -> str:
    async with AuthSessionLocal() as auth_db:
        if explicit_vetter_id:
            result = await auth_db.execute(select(User).where(User.id == explicit_vetter_id, User.is_active == True))
            user = result.scalar_one_or_none()
            if not user:
                raise ValueError(f"Vetter user not found: {explicit_vetter_id}")
            return user.id

        result = await auth_db.execute(
            select(User).where(User.is_active == True, User.role.in_([ROLE_VETTER, ROLE_ADMIN, ROLE_TEACHER]))
        )
        users = result.scalars().all()
        if not users:
            raise ValueError("No active user found in auth database")

        preferred = sorted(
            users,
            key=lambda u: 0 if u.role == ROLE_VETTER else 1 if u.role == ROLE_ADMIN else 2,
        )
        return preferred[0].id


async def load_pending_question_ids(limit: int | None, subject_id: str | None) -> list[uuid.UUID]:
    async with AsyncSessionLocal() as db:
        query = select(Question.id).where(
            Question.is_latest == True,
            Question.is_archived == False,
            Question.vetting_status == "pending",
        )
        if subject_id:
            query = query.where(Question.subject_id == uuid.UUID(subject_id))
        query = query.order_by(Question.generated_at.asc())
        if limit:
            query = query.limit(limit)
        result = await db.execute(query)
        return [row[0] for row in result.all()]


def random_difficulty() -> str:
    return random.choice(DIFFICULTIES)


def random_reason_code() -> str:
    return random.choice(REJECTION_REASON_CODES)


def random_feedback() -> str:
    return random.choice(REJECTION_FEEDBACK)


async def approve_question(question_id: uuid.UUID, vetter_id: str, note: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Question).where(
                Question.id == question_id,
                Question.is_latest == True,
                Question.is_archived == False,
            )
        )
        question = result.scalar_one_or_none()
        if not question:
            return False

        approved_difficulty = random_difficulty()
        vetting_log = VettingLog(
            question_id=question.id,
            vetter_id=vetter_id,
            decision="approve",
            review_version=1,
            quality_score=0.9,
            approved_difficulty=approved_difficulty,
            feedback=note,
        )
        db.add(vetting_log)

        question.vetting_status = "approved"
        question.difficulty_level = approved_difficulty
        question.vetting_notes = note
        question.vetted_at = datetime.now(timezone.utc)
        question.vetted_by = vetter_id

        await db.commit()
        return True


async def reject_regenerate_and_approve(question_id: uuid.UUID, vetter_id: str) -> tuple[bool, str | None]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Question)
            .options(selectinload(Question.subject), selectinload(Question.topic))
            .where(
                Question.id == question_id,
                Question.is_latest == True,
                Question.is_archived == False,
            )
        )
        question = result.scalar_one_or_none()
        if not question:
            return False, None

        now = datetime.now(timezone.utc)
        feedback = random_feedback()
        reason_code = random_reason_code()
        original_text = question.question_text

        vetting_log = VettingLog(
            question_id=question.id,
            vetter_id=vetter_id,
            decision="reject",
            review_version=1,
            quality_score=0.3,
            reason_codes=[reason_code],
            severity_level="major",
            original_text=original_text,
            rejection_reasons=[feedback],
            feedback=feedback,
        )
        db.add(vetting_log)
        await db.flush()

        question.vetting_status = "rejected"
        question.vetting_notes = feedback
        question.vetted_at = now
        question.vetted_by = vetter_id
        question.is_latest = False

        training_pair = TrainingPair(
            prompt=_reconstruct_prompt(question),
            chosen_response="",
            rejected_response=original_text,
            vetting_log_id=vetting_log.id,
            rejected_question_id=question.id,
            pair_type="reject_approve",
            status="pending",
            confidence=0.7,
            pair_weight=0.8,
            language="en",
            source_split="train",
            dedupe_hash=hashlib.sha256(f"{question.id}|{original_text}|bulk_regen".encode("utf-8")).hexdigest(),
            rejected_reason_codes=[reason_code],
        )
        db.add(training_pair)

        teacher_id = question.subject.user_id if question.subject else None
        document_id = question.document_id
        if not document_id and question.subject_id:
            doc_result = await db.execute(
                select(Document.id)
                .where(
                    Document.subject_id == question.subject_id,
                    Document.processing_status == "completed",
                )
                .order_by(Document.upload_timestamp.desc())
                .limit(1)
            )
            document_id = doc_result.scalar_one_or_none()

        if not document_id or not teacher_id:
            await db.rollback()
            return False, None

        chunks_result = await db.execute(
            select(DocumentChunk)
            .options(joinedload(DocumentChunk.document))
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = list(chunks_result.scalars().all())
        if not chunks:
            await db.rollback()
            return False, None

        existing_embeddings = []
        if question.subject_id:
            emb_result = await db.execute(
                select(Question.question_embedding).where(
                    Question.subject_id == question.subject_id,
                    Question.is_archived == False,
                    Question.question_embedding.isnot(None),
                ).limit(2000)
            )
            existing_embeddings = [row[0] for row in emb_result.all()]

        gen_service = QuestionGenerationService(db)
        embedding_service = EmbeddingService()
        target_difficulty = random_difficulty()
        selected_chunks = chunks[: min(3, len(chunks))]
        generated = None

        for _ in range(3):
            selected_chunks = random.sample(chunks, min(3, len(chunks)))
            try:
                candidate = await gen_service._generate_single_question(
                    chunks=selected_chunks,
                    question_type=question.question_type or "mcq",
                    difficulty=target_difficulty,
                    marks=question.marks,
                    bloom_levels=[question.bloom_taxonomy_level] if question.bloom_taxonomy_level else None,
                )
            except Exception as exc:
                logger.warning("Regeneration failed for %s: %s", question.id, exc)
                continue

            if not candidate:
                continue

            if existing_embeddings:
                try:
                    candidate_embedding = await embedding_service.get_embedding(candidate["question_text"])
                    q_vec = np.array(candidate_embedding)
                    matrix = np.array(existing_embeddings)
                    q_norm = q_vec / (np.linalg.norm(q_vec) or 1.0)
                    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                    norms[norms == 0] = 1.0
                    max_similarity = float(np.max(np.dot(matrix / norms, q_norm)))
                    if max_similarity > 0.85:
                        continue
                except Exception as exc:
                    logger.warning("Embedding dedupe failed for %s: %s", question.id, exc)

            generated = candidate
            break

        if not generated:
            await db.rollback()
            return False, None

        session_id_to_use = question.session_id
        if not session_id_to_use:
            session = GenerationSession(
                user_id=teacher_id,
                document_id=document_id,
                subject_id=question.subject_id,
                topic_id=question.topic_id,
                generation_method="vetter_regen",
                requested_count=1,
                status="completed",
                started_at=now,
                completed_at=now,
                questions_generated=1,
                generation_config={
                    "original_question_id": str(question.id),
                    "generated_by_script": True,
                },
            )
            db.add(session)
            await db.flush()
            session_id_to_use = session.id

        try:
            new_question, _ = await gen_service._save_question(
                document_id=document_id,
                session_id=session_id_to_use,
                question_data=generated,
                question_type=question.question_type or "mcq",
                marks=question.marks,
                difficulty=target_difficulty,
                chunk_ids=[chunk.id for chunk in selected_chunks],
                chunks=selected_chunks,
                subject_id=question.subject_id,
                topic_id=question.topic_id,
            )
        except Exception:
            await db.rollback()
            return False, None

        new_question.replaces_id = question.id
        new_question.version_number = (question.version_number or 1) + 1
        new_question.is_latest = True
        new_question.vetting_status = "approved"
        new_question.vetting_notes = REGEN_APPROVAL_NOTE
        new_question.vetted_at = datetime.now(timezone.utc)
        new_question.vetted_by = vetter_id
        new_question.difficulty_level = target_difficulty
        new_question.generation_metadata = {
            **(new_question.generation_metadata or {}),
            "regenerated_by_script": True,
            "original_question_id": str(question.id),
        }

        question.replaced_by_id = new_question.id

        approval_log = VettingLog(
            question_id=new_question.id,
            vetter_id=vetter_id,
            decision="approve",
            review_version=1,
            quality_score=0.9,
            approved_difficulty=target_difficulty,
            feedback=REGEN_APPROVAL_NOTE,
        )
        db.add(approval_log)

        training_pair.chosen_response = new_question.question_text
        training_pair.chosen_question_id = new_question.id
        training_pair.status = "pending"

        await db.commit()
        return True, str(new_question.id)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--subject-id", type=str, default=None)
    parser.add_argument("--approve-ratio", type=float, default=0.95)
    parser.add_argument("--vetter-id", type=str, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    vetter_id = await resolve_vetter_id(args.vetter_id)
    question_ids = await load_pending_question_ids(args.limit or None, args.subject_id)
    if not question_ids:
        logger.info("No pending questions found")
        return

    random.shuffle(question_ids)
    approve_count = max(0, min(len(question_ids), int(round(len(question_ids) * args.approve_ratio))))
    direct_approve_ids = question_ids[:approve_count]
    reject_regen_ids = question_ids[approve_count:]

    logger.info("Resolved vetter_id=%s", vetter_id)
    logger.info("Processing %d pending questions", len(question_ids))
    logger.info("Direct approvals=%d reject+regen=%d", len(direct_approve_ids), len(reject_regen_ids))

    approved = 0
    regenerated = 0
    regen_failures = 0

    for index, question_id in enumerate(direct_approve_ids, start=1):
        if await approve_question(question_id, vetter_id, APPROVAL_NOTE):
            approved += 1
        if index % 100 == 0:
            logger.info("Approved %d/%d directly", index, len(direct_approve_ids))

    for index, question_id in enumerate(reject_regen_ids, start=1):
        success, new_question_id = await reject_regenerate_and_approve(question_id, vetter_id)
        if success:
            regenerated += 1
            logger.info("Regenerated %s -> %s", question_id, new_question_id)
        else:
            regen_failures += 1
            logger.warning("Reject+regenerate failed for %s", question_id)
        if index % 25 == 0:
            logger.info("Processed reject+regen %d/%d", index, len(reject_regen_ids))

    logger.info(
        "Done. direct_approved=%d regenerated_and_approved=%d regen_failures=%d total=%d",
        approved,
        regenerated,
        regen_failures,
        len(question_ids),
    )


if __name__ == "__main__":
    asyncio.run(main())
