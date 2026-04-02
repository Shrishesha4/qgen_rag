"""
VQuest service — query approved questions from the question bank.

Used by course module question attachment and personalized test generation.
"""

from typing import Optional, List

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question


async def get_approved_questions(
    db: AsyncSession,
    subject_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    difficulty: Optional[str] = None,
    bloom_level: Optional[str] = None,
    question_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[Question], int]:
    """
    Fetch approved questions with optional filters.
    Returns (questions, total_count).
    """
    filters = [Question.vetting_status == "approved"]

    if subject_id:
        filters.append(Question.subject_id == subject_id)
    if topic_id:
        filters.append(Question.topic_id == topic_id)
    if difficulty:
        filters.append(Question.difficulty_level == difficulty)
    if bloom_level:
        filters.append(Question.bloom_taxonomy_level == bloom_level)
    if question_type:
        filters.append(Question.question_type == question_type)

    where = and_(*filters)

    count_q = select(func.count()).select_from(Question).where(where)
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(Question)
        .where(where)
        .order_by(Question.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(query)).scalars().all()
    return rows, total


async def search_questions_for_module(
    db: AsyncSession,
    query_text: Optional[str] = None,
    subject_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    difficulty: Optional[str] = None,
    bloom_level: Optional[str] = None,
    limit: int = 20,
) -> List[Question]:
    """
    Search approved questions by text match + filters.
    For full semantic search, use the embedding service separately.
    """
    filters = [Question.vetting_status == "approved"]

    if subject_id:
        filters.append(Question.subject_id == subject_id)
    if topic_id:
        filters.append(Question.topic_id == topic_id)
    if difficulty:
        filters.append(Question.difficulty_level == difficulty)
    if bloom_level:
        filters.append(Question.bloom_taxonomy_level == bloom_level)
    if query_text:
        pattern = f"%{query_text}%"
        filters.append(Question.question_text.ilike(pattern))

    where = and_(*filters)
    query = (
        select(Question)
        .where(where)
        .order_by(Question.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(query)).scalars().all()
    return rows


async def get_questions_by_ids(
    db: AsyncSession,
    question_ids: List[str],
    approved_only: bool = True,
) -> List[Question]:
    """Fetch specific questions by ID list."""
    filters = [Question.id.in_(question_ids)]
    if approved_only:
        filters.append(Question.vetting_status == "approved")

    query = select(Question).where(and_(*filters))
    rows = (await db.execute(query)).scalars().all()
    return rows
