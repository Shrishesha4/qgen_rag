"""
Personalized Generation Service — generate one-time tests and learning modules
tailored to a student's learning history.
"""

import logging
import random
import uuid
from typing import Optional, List, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import PersonalizedItem, PersonalizedItemType, PersonalizedItemStatus
from app.models.question import Question
from app.models.subject import Topic
from app.schemas.course import LearningProfile
from app.services.learning_history_service import build_learning_profile
from app.services.vquest_service import get_approved_questions
from app.services.provider_service import get_provider_service

logger = logging.getLogger(__name__)


async def generate_personalized_test(
    db: AsyncSession,
    student_id: str,
    course_id: Optional[str] = None,
    topic_focus: Optional[List[str]] = None,
    question_count: int = 10,
    difficulty_bias: str = "auto",
) -> PersonalizedItem:
    """
    Generate a one-time personalized test weighted toward student's weak topics.

    1. Build learning profile
    2. Select questions: 70% from weak topics, 30% from rest
    3. LLM-fill gaps if insufficient approved questions
    4. Persist as PersonalizedItem
    """
    profile = await build_learning_profile(db, student_id, course_id)

    # Determine target topics
    weak_topic_ids = topic_focus or [w.topic_id for w in profile.weak_topics]
    all_topic_ids = [w.topic_id for w in profile.weak_topics] + [m.topic_id for m in profile.mastered_topics]

    weak_target = int(question_count * 0.7)
    rest_target = question_count - weak_target

    # Determine difficulty filter
    difficulty = None
    if difficulty_bias == "easy":
        difficulty = "easy"
    elif difficulty_bias == "hard":
        difficulty = "hard"

    # Fetch questions from weak topics
    weak_questions: List[Question] = []
    for tid in weak_topic_ids:
        if len(weak_questions) >= weak_target:
            break
        qs, _ = await get_approved_questions(
            db, topic_id=tid, difficulty=difficulty, limit=weak_target - len(weak_questions)
        )
        weak_questions.extend(qs)

    # Fetch questions from other topics
    rest_questions: List[Question] = []
    used_ids = {q.id for q in weak_questions}
    other_topics = [t for t in all_topic_ids if t not in set(weak_topic_ids)]
    for tid in other_topics:
        if len(rest_questions) >= rest_target:
            break
        qs, _ = await get_approved_questions(
            db, topic_id=tid, difficulty=difficulty, limit=rest_target - len(rest_questions)
        )
        rest_questions.extend([q for q in qs if q.id not in used_ids])

    # Combine and shuffle
    all_questions = weak_questions[:weak_target] + rest_questions[:rest_target]
    random.shuffle(all_questions)

    # Build question content
    question_data = []
    for q in all_questions:
        question_data.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "difficulty_level": q.difficulty_level,
            "topic_id": q.topic_id,
        })

    # If we don't have enough questions, try to LLM-generate gap-fills
    if len(question_data) < question_count and weak_topic_ids:
        gap_count = question_count - len(question_data)
        generated = await _llm_generate_questions(db, weak_topic_ids[:3], gap_count, difficulty_bias, profile)
        question_data.extend(generated)

    generated_content = {
        "questions": question_data[:question_count],
        "profile_snapshot": {
            "weak_topics": [w.model_dump() for w in profile.weak_topics[:5]],
            "overall_level": profile.overall_level,
        },
        "difficulty_bias": difficulty_bias,
    }

    item = PersonalizedItem(
        id=str(uuid.uuid4()),
        student_id=student_id,
        course_id=course_id,
        item_type=PersonalizedItemType.TEST.value,
        generated_content=generated_content,
        status=PersonalizedItemStatus.ACTIVE.value,
    )
    db.add(item)
    await db.flush()
    return item


async def generate_personalized_module(
    db: AsyncSession,
    student_id: str,
    topic_id: str,
    course_id: Optional[str] = None,
    focus_areas: Optional[List[str]] = None,
) -> PersonalizedItem:
    """
    Generate a bespoke learning module addressing a student's gaps on a topic.

    Sections: concept_recap, misconception_correction, worked_examples,
    practice_problems, recap_summary.
    """
    profile = await build_learning_profile(db, student_id, course_id)

    # Get topic info
    topic = (await db.execute(select(Topic).where(Topic.id == topic_id))).scalar_one_or_none()
    topic_name = topic.name if topic else "Unknown Topic"
    topic_desc = topic.description if topic else ""
    syllabus = topic.syllabus_content if topic else ""

    # Get sample approved questions for RAG context
    sample_qs, _ = await get_approved_questions(db, topic_id=topic_id, limit=5)
    sample_q_texts = [q.question_text for q in sample_qs]

    # Find student's specific weak points on this topic
    weak_info = next((w for w in profile.weak_topics if w.topic_id == topic_id), None)
    reasoning_gaps = profile.reasoning_gaps[:3]

    # Build LLM prompt
    prompt = _build_module_generation_prompt(
        topic_name=topic_name,
        topic_desc=topic_desc,
        syllabus=syllabus,
        sample_questions=sample_q_texts,
        weak_info=weak_info,
        reasoning_gaps=reasoning_gaps,
        focus_areas=focus_areas,
        student_level=profile.overall_level,
    )

    system_prompt = (
        "You are an expert educational content designer. Generate a structured learning module "
        "in JSON format. The module must be tailored to this specific student's weaknesses. "
        "Output valid JSON only."
    )

    # Call LLM
    generated_content = await _call_llm_json(prompt, system_prompt)

    if not generated_content or not isinstance(generated_content, dict):
        # Fallback structure
        generated_content = {
            "concept_recap": f"Review of {topic_name}",
            "misconception_correction": "No specific misconceptions identified.",
            "worked_examples": [],
            "practice_problems": [],
            "recap_summary": [f"Review {topic_name} fundamentals."],
        }

    generated_content["topic_id"] = topic_id
    generated_content["topic_name"] = topic_name
    generated_content["student_level"] = profile.overall_level

    item = PersonalizedItem(
        id=str(uuid.uuid4()),
        student_id=student_id,
        course_id=course_id,
        topic_id=topic_id,
        item_type=PersonalizedItemType.LEARNING_MODULE.value,
        generated_content=generated_content,
        status=PersonalizedItemStatus.ACTIVE.value,
    )
    db.add(item)
    await db.flush()
    return item


def _build_module_generation_prompt(
    topic_name: str,
    topic_desc: str,
    syllabus: str,
    sample_questions: List[str],
    weak_info,
    reasoning_gaps: List[str],
    focus_areas: Optional[List[str]],
    student_level: str,
) -> str:
    parts = [
        f"Generate a personalized learning module for topic: {topic_name}",
        f"Student level: {student_level}",
    ]
    if topic_desc:
        parts.append(f"Topic description: {topic_desc[:500]}")
    if syllabus:
        parts.append(f"Syllabus excerpt: {syllabus[:1500]}")
    if sample_questions:
        parts.append("Sample questions from this topic:")
        for i, q in enumerate(sample_questions[:3], 1):
            parts.append(f"  {i}. {q[:200]}")
    if weak_info:
        parts.append(f"Student's average score on this topic: {weak_info.avg_score}")
        parts.append(f"Number of failures: {weak_info.fail_count}")
    if reasoning_gaps:
        parts.append("Student's reasoning gaps:")
        for gap in reasoning_gaps:
            parts.append(f"  - {gap[:150]}")
    if focus_areas:
        parts.append(f"Requested focus areas: {', '.join(focus_areas[:5])}")

    parts.append("""
Output a JSON object with these keys:
{
  "concept_recap": "A clear, concise explanation of the key concept (2-4 paragraphs, at the student's level)",
  "misconception_correction": "Directly address the specific errors/misconceptions from the student's history (1-2 paragraphs)",
  "worked_examples": [
    {"problem": "...", "solution": "step-by-step solution", "key_insight": "..."}
  ],
  "practice_problems": [
    {"question_text": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct_answer": "A", "explanation": "..."}
  ],
  "recap_summary": ["bullet 1", "bullet 2", "bullet 3"]
}

Generate 2-3 worked examples and 3-5 practice problems. Tailor content to the student's level and weaknesses.""")

    return "\n".join(parts)


async def _llm_generate_questions(
    db: AsyncSession,
    topic_ids: List[str],
    count: int,
    difficulty_bias: str,
    profile: LearningProfile,
) -> List[Dict[str, Any]]:
    """LLM-generate gap-fill questions when approved bank is insufficient."""
    # Get topic names
    topics = (await db.execute(select(Topic.id, Topic.name).where(Topic.id.in_(topic_ids)))).all()
    topic_names = {tid: name for tid, name in topics}

    difficulty = difficulty_bias if difficulty_bias != "auto" else "medium"
    topic_list = ", ".join(topic_names.values()) or "general"

    prompt = f"""Generate {count} multiple-choice questions for these topics: {topic_list}
Difficulty: {difficulty}
Student level: {profile.overall_level}

Output a JSON array where each item has:
{{"question_text": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct_answer": "A", "explanation": "...", "difficulty_level": "{difficulty}"}}

Generate educational, accurate questions. Output JSON only."""

    system_prompt = "You are an expert question generator for educational assessments. Output valid JSON only."

    result = await _call_llm_json(prompt, system_prompt)

    generated = []
    if isinstance(result, list):
        for item in result[:count]:
            if isinstance(item, dict) and "question_text" in item:
                item["question_id"] = f"gen_{uuid.uuid4().hex[:8]}"
                item["question_type"] = "mcq"
                generated.append(item)
    return generated


async def _call_llm_json(prompt: str, system_prompt: str) -> Any:
    """Call an LLM provider's generate_json method."""
    try:
        provider_svc = get_provider_service()
        providers = await provider_svc.get_enabled_providers()
        if not providers:
            logger.warning("No enabled LLM providers for personalized generation")
            return None

        provider = providers[0]
        llm_service, _ = provider_svc.create_llm_service(provider)
        result = await llm_service.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=4096,
        )
        return result
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return None
