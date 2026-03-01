"""
Test service for teacher-created assessments.
Handles test creation, question generation from approved pool, publishing, and performance analytics.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.test import Test, TestQuestion, TestSubmission
from app.models.question import Question
from app.models.subject import Subject, Topic
from app.models.user import User
from app.core.logging import logger


class TestService:
    """Service for managing teacher tests."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========================
    # Test CRUD
    # ========================

    async def create_test(self, teacher_id: UUID, data: dict) -> Test:
        """Create a new test (draft)."""
        test = Test(
            teacher_id=teacher_id,
            subject_id=data["subject_id"],
            title=data["title"],
            description=data.get("description"),
            instructions=data.get("instructions"),
            generation_type=data.get("generation_type", "subject_wise"),
            difficulty_config=data.get("difficulty_config"),
            topic_config=data.get("topic_config"),
            duration_minutes=data.get("duration_minutes"),
            status="draft",
        )
        self.db.add(test)
        await self.db.commit()
        await self.db.refresh(test)
        return test

    async def get_test(self, test_id: UUID, teacher_id: Optional[UUID] = None) -> Optional[Test]:
        """Get a test by ID, optionally filtered by teacher."""
        query = select(Test).where(Test.id == test_id)
        if teacher_id:
            query = query.where(Test.teacher_id == teacher_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_tests(self, teacher_id: UUID, status: Optional[str] = None) -> List[dict]:
        """List tests for a teacher with summary info."""
        query = (
            select(
                Test,
                Subject.name.label("subject_name"),
                Subject.code.label("subject_code"),
                func.count(TestSubmission.id).label("submissions_count"),
                func.avg(TestSubmission.percentage).label("average_score"),
            )
            .join(Subject, Test.subject_id == Subject.id)
            .outerjoin(TestSubmission, and_(
                TestSubmission.test_id == Test.id,
                TestSubmission.status == "submitted",
            ))
            .where(Test.teacher_id == teacher_id)
            .group_by(Test.id, Subject.name, Subject.code)
            .order_by(desc(Test.updated_at))
        )
        if status:
            query = query.where(Test.status == status)

        result = await self.db.execute(query)
        rows = result.all()

        tests = []
        for row in rows:
            test = row[0]
            tests.append({
                "id": test.id,
                "teacher_id": test.teacher_id,
                "subject_id": test.subject_id,
                "title": test.title,
                "description": test.description,
                "instructions": test.instructions,
                "generation_type": test.generation_type,
                "difficulty_config": test.difficulty_config,
                "topic_config": test.topic_config,
                "total_questions": test.total_questions,
                "total_marks": test.total_marks,
                "duration_minutes": test.duration_minutes,
                "status": test.status,
                "published_at": test.published_at,
                "unpublished_at": test.unpublished_at,
                "created_at": test.created_at,
                "updated_at": test.updated_at,
                "subject_name": row[1],
                "subject_code": row[2],
                "submissions_count": row[3] or 0,
                "average_score": round(float(row[4]), 1) if row[4] else None,
            })
        return tests

    async def update_test(self, test_id: UUID, teacher_id: UUID, data: dict) -> Optional[Test]:
        """Update test details."""
        test = await self.get_test(test_id, teacher_id)
        if not test:
            return None

        for key, value in data.items():
            if value is not None and hasattr(test, key):
                setattr(test, key, value)

        await self.db.commit()
        await self.db.refresh(test)
        return test

    async def delete_test(self, test_id: UUID, teacher_id: UUID) -> bool:
        """Delete a test (only draft/unpublished)."""
        test = await self.get_test(test_id, teacher_id)
        if not test:
            return False
        if test.status == "published":
            return False
        await self.db.delete(test)
        await self.db.commit()
        return True

    # ========================
    # Generate Questions for Test
    # ========================

    async def generate_test_questions(self, test_id: UUID, teacher_id: UUID) -> dict:
        """
        Generate questions for a test from the approved questions pool.
        Uses the test's difficulty_config and topic_config to select questions.
        """
        test = await self.get_test(test_id, teacher_id)
        if not test:
            raise ValueError("Test not found")
        if test.status == "published":
            raise ValueError("Cannot regenerate questions for a published test")

        # Clear existing test questions
        existing = await self.db.execute(
            select(TestQuestion).where(TestQuestion.test_id == test_id)
        )
        for tq in existing.scalars().all():
            await self.db.delete(tq)

        selected_questions = []
        difficulty_config = test.difficulty_config or {}
        topic_config = test.topic_config or []

        if test.generation_type == "topic_wise" and topic_config:
            # Topic-wise generation: select questions per topic
            for topic_entry in topic_config:
                topic_id = topic_entry.get("topic_id")
                count = topic_entry.get("count", 5)
                questions = await self._select_questions(
                    subject_id=test.subject_id,
                    topic_id=UUID(topic_id) if isinstance(topic_id, str) else topic_id,
                    difficulty_config=difficulty_config,
                    count=count,
                )
                selected_questions.extend(questions)

        elif test.generation_type == "multi_topic" and topic_config:
            # Multi-topic: select from multiple topics with individual configs
            for topic_entry in topic_config:
                topic_id = topic_entry.get("topic_id")
                count = topic_entry.get("count", 5)
                questions = await self._select_questions(
                    subject_id=test.subject_id,
                    topic_id=UUID(topic_id) if isinstance(topic_id, str) else topic_id,
                    difficulty_config=difficulty_config,
                    count=count,
                )
                selected_questions.extend(questions)

        else:
            # Subject-wise: select from whole subject
            total_count = sum(
                cfg.get("count", 0) if isinstance(cfg, dict) else 0
                for cfg in difficulty_config.values()
            ) if difficulty_config else 10
            selected_questions = await self._select_questions(
                subject_id=test.subject_id,
                difficulty_config=difficulty_config,
                count=total_count,
            )

        # Create TestQuestion entries
        total_marks = 0
        for idx, q in enumerate(selected_questions):
            marks = self._get_marks_for_difficulty(q.difficulty_level)
            tq = TestQuestion(
                test_id=test_id,
                question_id=q.id,
                order_index=idx,
                marks=marks,
            )
            self.db.add(tq)
            total_marks += marks

        # Update test totals
        test.total_questions = len(selected_questions)
        test.total_marks = total_marks

        await self.db.commit()
        await self.db.refresh(test)

        return {
            "test_id": test.id,
            "questions_added": len(selected_questions),
            "total_marks": total_marks,
        }

    async def _select_questions(
        self,
        subject_id: UUID,
        topic_id: Optional[UUID] = None,
        difficulty_config: Optional[dict] = None,
        count: int = 10,
    ) -> List[Question]:
        """Select approved questions from the pool based on criteria."""
        all_questions = []

        if difficulty_config:
            for difficulty, config in difficulty_config.items():
                if not isinstance(config, dict):
                    continue
                diff_count = config.get("count", 0)
                if diff_count <= 0:
                    continue

                query = (
                    select(Question)
                    .where(
                        and_(
                            Question.subject_id == subject_id,
                            Question.vetting_status == "approved",
                            Question.is_archived == False,
                            Question.difficulty_level == difficulty,
                        )
                    )
                )
                if topic_id:
                    query = query.where(Question.topic_id == topic_id)
                
                # Filter by LO mapping if specified
                lo_mapping = config.get("lo_mapping", [])
                if lo_mapping:
                    query = query.where(Question.learning_outcome_id.in_(lo_mapping))

                query = query.order_by(func.random()).limit(diff_count)
                result = await self.db.execute(query)
                all_questions.extend(result.scalars().all())
        else:
            # No difficulty config, just select randomly
            query = (
                select(Question)
                .where(
                    and_(
                        Question.subject_id == subject_id,
                        Question.vetting_status == "approved",
                        Question.is_archived == False,
                    )
                )
            )
            if topic_id:
                query = query.where(Question.topic_id == topic_id)
            query = query.order_by(func.random()).limit(count)
            result = await self.db.execute(query)
            all_questions.extend(result.scalars().all())

        return all_questions

    def _get_marks_for_difficulty(self, difficulty: Optional[str]) -> int:
        """Assign default marks based on difficulty."""
        return {"easy": 1, "medium": 2, "hard": 3}.get(difficulty or "easy", 1)

    # ========================
    # Publishing
    # ========================

    async def publish_test(self, test_id: UUID, teacher_id: UUID) -> Optional[Test]:
        """Publish a test, making it available to students."""
        test = await self.get_test(test_id, teacher_id)
        if not test:
            return None
        if test.total_questions == 0:
            raise ValueError("Cannot publish a test with no questions. Generate questions first.")

        test.status = "published"
        test.published_at = datetime.now(timezone.utc)
        test.unpublished_at = None
        await self.db.commit()
        await self.db.refresh(test)
        return test

    async def unpublish_test(self, test_id: UUID, teacher_id: UUID) -> Optional[Test]:
        """Unpublish a test."""
        test = await self.get_test(test_id, teacher_id)
        if not test:
            return None

        test.status = "unpublished"
        test.unpublished_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(test)
        return test

    # ========================
    # Test Questions Management
    # ========================

    async def get_test_questions(self, test_id: UUID) -> List[dict]:
        """Get all questions for a test with details."""
        query = (
            select(TestQuestion, Question, Topic.name.label("topic_name"))
            .join(Question, TestQuestion.question_id == Question.id)
            .outerjoin(Topic, Question.topic_id == Topic.id)
            .where(TestQuestion.test_id == test_id)
            .order_by(TestQuestion.order_index)
        )
        result = await self.db.execute(query)
        rows = result.all()

        questions = []
        for row in rows:
            tq = row[0]
            q = row[1]
            topic_name = row[2]
            questions.append({
                "id": tq.id,
                "test_id": tq.test_id,
                "question_id": q.id,
                "order_index": tq.order_index,
                "marks": tq.marks,
                "question_text_override": tq.question_text_override,
                "options_override": tq.options_override,
                "correct_answer_override": tq.correct_answer_override,
                "question_text": tq.question_text_override or q.question_text,
                "question_type": q.question_type,
                "options": tq.options_override or q.options,
                "correct_answer": tq.correct_answer_override or q.correct_answer,
                "explanation": q.explanation,
                "difficulty_level": q.difficulty_level,
                "bloom_taxonomy_level": q.bloom_taxonomy_level,
                "topic_name": topic_name,
                "learning_outcome_id": q.learning_outcome_id,
            })
        return questions

    async def update_test_question(
        self, test_id: UUID, test_question_id: UUID, teacher_id: UUID, data: dict
    ) -> Optional[dict]:
        """Update a question within a test (override text, marks, etc.)."""
        # Verify teacher owns the test
        test = await self.get_test(test_id, teacher_id)
        if not test:
            return None

        result = await self.db.execute(
            select(TestQuestion).where(
                and_(TestQuestion.id == test_question_id, TestQuestion.test_id == test_id)
            )
        )
        tq = result.scalar_one_or_none()
        if not tq:
            return None

        old_marks = tq.marks
        for key, value in data.items():
            if value is not None and hasattr(tq, key):
                setattr(tq, key, value)

        # Update total marks if marks changed
        if "marks" in data and data["marks"] is not None and data["marks"] != old_marks:
            test.total_marks = test.total_marks - old_marks + data["marks"]

        await self.db.commit()
        return {"status": "updated"}

    async def remove_test_question(
        self, test_id: UUID, test_question_id: UUID, teacher_id: UUID
    ) -> bool:
        """Remove a question from a test."""
        test = await self.get_test(test_id, teacher_id)
        if not test:
            return False

        result = await self.db.execute(
            select(TestQuestion).where(
                and_(TestQuestion.id == test_question_id, TestQuestion.test_id == test_id)
            )
        )
        tq = result.scalar_one_or_none()
        if not tq:
            return False

        test.total_questions -= 1
        test.total_marks -= tq.marks
        await self.db.delete(tq)
        await self.db.commit()
        return True

    # ========================
    # Student-facing
    # ========================

    async def get_published_tests_for_student(self, student_id: UUID) -> List[dict]:
        """Get published tests for subjects the student is enrolled in."""
        from app.models.gamification import Enrollment

        query = (
            select(
                Test,
                Subject.name.label("subject_name"),
                Subject.code.label("subject_code"),
                TestSubmission.id.label("submission_id"),
                TestSubmission.percentage.label("submission_percentage"),
                TestSubmission.status.label("submission_status"),
            )
            .join(Subject, Test.subject_id == Subject.id)
            .join(
                Enrollment,
                and_(
                    Enrollment.subject_id == Test.subject_id,
                    Enrollment.student_id == student_id,
                    Enrollment.is_active == True,
                ),
            )
            .outerjoin(
                TestSubmission,
                and_(
                    TestSubmission.test_id == Test.id,
                    TestSubmission.student_id == student_id,
                ),
            )
            .where(Test.status == "published")
            .order_by(desc(Test.published_at))
        )
        result = await self.db.execute(query)
        rows = result.all()

        tests = []
        for row in rows:
            test = row[0]
            tests.append({
                "id": test.id,
                "title": test.title,
                "description": test.description,
                "instructions": test.instructions,
                "subject_name": row[1],
                "subject_code": row[2],
                "total_questions": test.total_questions,
                "total_marks": test.total_marks,
                "duration_minutes": test.duration_minutes,
                "published_at": test.published_at,
                "has_submitted": row[3] is not None,
                "submission_percentage": float(row[4]) if row[4] else None,
                "submission_status": row[5],
            })
        return tests

    async def get_test_for_student(self, test_id: UUID, student_id: UUID) -> Optional[dict]:
        """Get test details and questions for a student to take."""
        test = await self.get_test(test_id)
        if not test or test.status != "published":
            return None

        # Check if already submitted
        result = await self.db.execute(
            select(TestSubmission).where(
                and_(
                    TestSubmission.test_id == test_id,
                    TestSubmission.student_id == student_id,
                    TestSubmission.status == "submitted",
                )
            )
        )
        if result.scalar_one_or_none():
            return {"already_submitted": True, "test_id": test_id}

        # Get questions (without correct answers)
        questions = await self.get_test_questions(test_id)
        for q in questions:
            q.pop("correct_answer", None)
            q.pop("correct_answer_override", None)
            q.pop("explanation", None)

        return {
            "id": test.id,
            "title": test.title,
            "description": test.description,
            "instructions": test.instructions,
            "total_questions": test.total_questions,
            "total_marks": test.total_marks,
            "duration_minutes": test.duration_minutes,
            "questions": questions,
        }

    async def submit_test(self, test_id: UUID, student_id: UUID, data: dict) -> dict:
        """Submit student answers for a test and calculate score."""
        test = await self.get_test(test_id)
        if not test or test.status != "published":
            raise ValueError("Test not available")

        # Check if already submitted
        result = await self.db.execute(
            select(TestSubmission).where(
                and_(
                    TestSubmission.test_id == test_id,
                    TestSubmission.student_id == student_id,
                    TestSubmission.status == "submitted",
                )
            )
        )
        if result.scalar_one_or_none():
            raise ValueError("Already submitted this test")

        # Get questions with answers
        questions = await self.get_test_questions(test_id)
        question_map = {str(q["question_id"]): q for q in questions}

        answers = data.get("answers", [])
        score = 0
        total_marks = test.total_marks
        answer_results = []

        for ans in answers:
            q_id = str(ans["question_id"])
            q = question_map.get(q_id)
            if not q:
                continue

            correct = q.get("correct_answer", "")
            selected = ans.get("selected_answer", "")
            is_correct = self._check_answer(selected, correct)
            marks_obtained = q["marks"] if is_correct else 0
            score += marks_obtained

            answer_results.append({
                "question_id": q_id,
                "selected_answer": selected,
                "is_correct": is_correct,
                "marks_obtained": marks_obtained,
                "correct_answer": correct,
                "explanation": q.get("explanation"),
                "time_taken_seconds": ans.get("time_taken_seconds"),
            })

        percentage = round((score / total_marks * 100), 1) if total_marks > 0 else 0.0

        submission = TestSubmission(
            test_id=test_id,
            student_id=student_id,
            score=score,
            total_marks=total_marks,
            percentage=percentage,
            answers=answer_results,
            time_taken_seconds=data.get("total_time_seconds"),
            status="submitted",
            submitted_at=datetime.now(timezone.utc),
        )
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)

        return {
            "id": submission.id,
            "test_id": test_id,
            "student_id": student_id,
            "score": score,
            "total_marks": total_marks,
            "percentage": percentage,
            "status": "submitted",
            "time_taken_seconds": submission.time_taken_seconds,
            "started_at": submission.started_at,
            "submitted_at": submission.submitted_at,
            "results": answer_results,
        }

    def _check_answer(self, selected: str, correct: str) -> bool:
        """Check if selected answer matches correct answer."""
        if not selected or not correct:
            return False
        # Normalize: strip whitespace, compare case-insensitively
        return selected.strip().upper() == correct.strip().upper()

    # ========================
    # Performance Analytics
    # ========================

    async def get_test_performance(self, test_id: UUID, teacher_id: UUID) -> dict:
        """Get performance analytics for a specific test."""
        test = await self.get_test(test_id, teacher_id)
        if not test:
            raise ValueError("Test not found")

        # Get all submissions
        result = await self.db.execute(
            select(TestSubmission, User.full_name, User.username)
            .join(User, TestSubmission.student_id == User.id)
            .where(
                and_(
                    TestSubmission.test_id == test_id,
                    TestSubmission.status == "submitted",
                )
            )
            .order_by(desc(TestSubmission.percentage))
        )
        rows = result.all()

        submissions = []
        scores = []
        for row in rows:
            sub = row[0]
            submissions.append({
                "id": sub.id,
                "test_id": sub.test_id,
                "student_id": sub.student_id,
                "score": sub.score,
                "total_marks": sub.total_marks,
                "percentage": sub.percentage,
                "status": sub.status,
                "time_taken_seconds": sub.time_taken_seconds,
                "started_at": sub.started_at,
                "submitted_at": sub.submitted_at,
                "student_name": row[1] or row[2],
                "student_username": row[2],
                "answers": sub.answers,
            })
            scores.append(sub.score)

        # Question-level performance
        questions = await self.get_test_questions(test_id)
        question_perf = []
        for q in questions:
            q_id = str(q["question_id"])
            correct_count = 0
            total_attempts = 0
            time_sum = 0
            time_count = 0

            for sub_data in submissions:
                sub_answers = sub_data.get("answers") or []
                for ans in sub_answers:
                    if str(ans.get("question_id")) == q_id:
                        total_attempts += 1
                        if ans.get("is_correct"):
                            correct_count += 1
                        t = ans.get("time_taken_seconds")
                        if t:
                            time_sum += t
                            time_count += 1

            question_perf.append({
                "question_id": q["question_id"],
                "question_text": q["question_text"],
                "correct_count": correct_count,
                "total_attempts": total_attempts,
                "accuracy": round(correct_count / total_attempts * 100, 1) if total_attempts > 0 else 0.0,
                "average_time_seconds": round(time_sum / time_count, 1) if time_count > 0 else None,
            })

        return {
            "test_id": test.id,
            "test_title": test.title,
            "total_submissions": len(submissions),
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "average_percentage": round(
                sum(s["percentage"] for s in submissions) / len(submissions), 1
            ) if submissions else 0.0,
            "highest_score": max(scores) if scores else 0,
            "lowest_score": min(scores) if scores else 0,
            "submissions": submissions,
            "question_performance": question_perf,
        }
