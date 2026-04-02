"""
Learning History Service — aggregates student learning data into a LearningProfile.

Pulls from StudentAttempt, InquirySession, and Enrollment.progress_data to
build a per-student picture of weak/mastered topics and reasoning gaps.
"""

import logging
from typing import Optional, List

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gel import StudentAttempt, EvaluationItem
from app.models.inquiry_session import InquirySession
from app.models.course import Enrollment
from app.models.subject import Topic
from app.schemas.course import LearningProfile, WeakTopic, MasteredTopic

logger = logging.getLogger(__name__)

WEAK_THRESHOLD = 0.6
MASTERED_THRESHOLD = 0.8


async def build_learning_profile(
    db: AsyncSession,
    student_id: str,
    course_id: Optional[str] = None,
) -> LearningProfile:
    """
    Build a learning profile for a student by aggregating their history.

    Returns weak topics, mastered topics, reasoning gaps, question count, and level.
    """
    topic_stats = await _aggregate_attempt_scores(db, student_id)
    session_data = await _aggregate_sessions(db, student_id)
    enrollment_data = await _aggregate_enrollment_progress(db, student_id, course_id)

    # Merge session data into topic stats
    for tid, sinfo in session_data.items():
        if tid not in topic_stats:
            topic_stats[tid] = {"total_score": 0, "count": 0, "fail_count": 0, "topic_name": sinfo["topic_name"]}
        topic_stats[tid]["session_stalls"] = sinfo.get("stall_count", 0)

    # Classify topics
    weak_topics: List[WeakTopic] = []
    mastered_topics: List[MasteredTopic] = []
    total_seen = 0

    for tid, stats in topic_stats.items():
        count = stats["count"]
        total_seen += count
        if count == 0:
            continue
        avg = stats["total_score"] / count
        name = stats.get("topic_name", tid)
        fail_count = stats.get("fail_count", 0) + stats.get("session_stalls", 0)

        if avg < WEAK_THRESHOLD:
            weak_topics.append(WeakTopic(topic_id=tid, topic_name=name, avg_score=round(avg, 2), fail_count=fail_count))
        elif avg >= MASTERED_THRESHOLD:
            mastered_topics.append(MasteredTopic(topic_id=tid, topic_name=name, avg_score=round(avg, 2)))

    # Sort weak by score ascending (worst first)
    weak_topics.sort(key=lambda w: w.avg_score)
    mastered_topics.sort(key=lambda m: -m.avg_score)

    # Infer reasoning gaps from low-scoring attempts with reasoning text
    reasoning_gaps = await _extract_reasoning_gaps(db, student_id)

    # Determine overall level
    if not topic_stats:
        overall_level = "beginner"
    else:
        avg_all = sum(s["total_score"] for s in topic_stats.values()) / max(sum(s["count"] for s in topic_stats.values()), 1)
        if avg_all >= 0.85:
            overall_level = "pro"
        elif avg_all >= 0.65:
            overall_level = "advanced"
        else:
            overall_level = "beginner"

    total_seen += enrollment_data.get("completed_quizzes", 0)

    return LearningProfile(
        weak_topics=weak_topics,
        mastered_topics=mastered_topics,
        reasoning_gaps=reasoning_gaps,
        total_questions_seen=total_seen,
        overall_level=overall_level,
    )


async def _aggregate_attempt_scores(db: AsyncSession, student_id: str) -> dict:
    """Group StudentAttempt scores by topic_id via EvaluationItem."""
    query = (
        select(
            EvaluationItem.topic_id,
            func.avg(StudentAttempt.total_score).label("avg_score"),
            func.count(StudentAttempt.id).label("cnt"),
            func.sum(case((StudentAttempt.total_score < WEAK_THRESHOLD, 1), else_=0)).label("fail_cnt"),
        )
        .join(EvaluationItem, StudentAttempt.evaluation_item_id == EvaluationItem.id)
        .where(
            and_(
                StudentAttempt.student_id == student_id,
                StudentAttempt.total_score.isnot(None),
                EvaluationItem.topic_id.isnot(None),
            )
        )
        .group_by(EvaluationItem.topic_id)
    )
    rows = (await db.execute(query)).all()

    # Fetch topic names
    topic_ids = [r[0] for r in rows if r[0]]
    topic_names = {}
    if topic_ids:
        tq = select(Topic.id, Topic.name).where(Topic.id.in_(topic_ids))
        for tid, tname in (await db.execute(tq)).all():
            topic_names[tid] = tname

    stats = {}
    for row in rows:
        tid = row[0]
        if not tid:
            continue
        stats[tid] = {
            "total_score": float(row[1] or 0) * int(row[2] or 0),
            "count": int(row[2] or 0),
            "fail_count": int(row[3] or 0),
            "topic_name": topic_names.get(tid, tid),
        }
    return stats


async def _aggregate_sessions(db: AsyncSession, student_id: str) -> dict:
    """Aggregate InquirySession data — track topics where student stalled."""
    query = (
        select(InquirySession.topic_id, InquirySession.current_level, InquirySession.completed_turns_by_level)
        .where(and_(InquirySession.user_id == student_id, InquirySession.topic_id.isnot(None)))
    )
    rows = (await db.execute(query)).all()

    # Fetch topic names
    topic_ids = list({r[0] for r in rows if r[0]})
    topic_names = {}
    if topic_ids:
        tq = select(Topic.id, Topic.name).where(Topic.id.in_(topic_ids))
        for tid, tname in (await db.execute(tq)).all():
            topic_names[tid] = tname

    session_data: dict = {}
    for row in rows:
        tid = row[0]
        if not tid:
            continue
        turns = row[2] or {}
        # Count sessions where student didn't advance past beginner
        stalled = 1 if row[1] == "beginner" and turns.get("beginner", 0) >= 2 else 0

        if tid not in session_data:
            session_data[tid] = {"stall_count": 0, "topic_name": topic_names.get(tid, tid)}
        session_data[tid]["stall_count"] += stalled

    return session_data


async def _aggregate_enrollment_progress(
    db: AsyncSession, student_id: str, course_id: Optional[str]
) -> dict:
    """Pull quiz scores from enrollment progress_data."""
    filters = [Enrollment.student_id == student_id]
    if course_id:
        filters.append(Enrollment.course_id == course_id)

    query = select(Enrollment.progress_data).where(and_(*filters))
    rows = (await db.execute(query)).scalars().all()

    completed_quizzes = 0
    for data in rows:
        if not data:
            continue
        # progress_data format: {"completed_modules": ["id1", ...], "quiz_scores": {"mod_id": 85}}
        scores = data.get("quiz_scores", {})
        completed_quizzes += len(scores)

    return {"completed_quizzes": completed_quizzes}


async def _extract_reasoning_gaps(db: AsyncSession, student_id: str, limit: int = 5) -> List[str]:
    """
    Extract reasoning gap patterns from low-scoring attempts that have reasoning text.
    Returns a list of short gap descriptions.
    """
    query = (
        select(StudentAttempt.reasoning_text, StudentAttempt.feedback_text)
        .where(
            and_(
                StudentAttempt.student_id == student_id,
                StudentAttempt.total_score.isnot(None),
                StudentAttempt.total_score < WEAK_THRESHOLD,
                StudentAttempt.reasoning_text.isnot(None),
            )
        )
        .order_by(StudentAttempt.created_at.desc())
        .limit(20)
    )
    rows = (await db.execute(query)).all()

    gaps = []
    for reasoning, feedback in rows:
        if feedback and len(feedback) > 10:
            # Use feedback as the gap description (truncated)
            gap = feedback[:120].strip()
            if gap and gap not in gaps:
                gaps.append(gap)
        if len(gaps) >= limit:
            break

    return gaps
