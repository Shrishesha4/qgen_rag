"""
GEL Service.

Service for managing GEL (Graded Error Learning) operations:
- Evaluation items management
- Assignment management
- Student attempt lifecycle
- Dashboard data
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.orm import selectinload
import logging
import uuid

from app.models.gel import (
    EvaluationItem, Assignment, AssignmentItem, StudentAttempt,
    AttemptIssue, AttemptScore, AttemptEvent,
    EvaluationItemStatus, AssignmentStatus, AttemptStatus,
)
from app.models.question import Question
from app.models.subject import Subject, Topic
from app.schemas.gel import (
    EvaluationItemCreate, EvaluationItemUpdate,
    AssignmentCreate, AssignmentUpdate,
    StudentAttemptCreate, StudentAttemptSubmit, StudentAttemptDraft,
    AttemptIssueCreate,
)
from app.services.gel_scoring_service import GELScoringService

logger = logging.getLogger(__name__)


class GELService:
    """Service for GEL operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.scoring_service = GELScoringService(db)
    @staticmethod
    def _sid(value: Optional[object]) -> Optional[str]:
        """Normalize UUID/str inputs to plain strings for varchar PK/FK columns."""
        return str(value) if value is not None else None

    # ==================== Evaluation Items ====================

    async def create_evaluation_item(
        self,
        data: EvaluationItemCreate,
        created_by: str,
    ) -> EvaluationItem:
        """Create a new evaluation item from a question."""
        # Verify question exists
        question = await self.db.get(Question, str(data.question_id))
        if not question:
            raise ValueError(f"Question {data.question_id} not found")
        
        item = EvaluationItem(
            question_id=str(data.question_id),
            subject_id=str(data.subject_id) if data.subject_id else (str(question.subject_id) if question.subject_id else None),
            topic_id=str(data.topic_id) if data.topic_id else (str(question.topic_id) if question.topic_id else None),
            difficulty_label=data.difficulty_label or question.difficulty_level,
            bloom_level=data.bloom_level or question.bloom_taxonomy_level,
            known_issues=data.known_issues,
            expected_detection_count=data.expected_detection_count,
            is_control_item=data.is_control_item,
            control_type=data.control_type,
            rubric_id=str(data.rubric_id) if data.rubric_id else None,
            status=EvaluationItemStatus.DRAFT.value,
            created_by=created_by,
        )
        
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        
        logger.info(f"Created evaluation item {item.id} from question {data.question_id}")
        return item

    async def bulk_create_evaluation_items(
        self,
        question_ids: List[uuid.UUID],
        created_by: str,
        status: str = "draft",
        rubric_id: Optional[uuid.UUID] = None,
    ) -> List[EvaluationItem]:
        """Bulk create evaluation items from questions."""
        items = []
        for qid in question_ids:
            question = await self.db.get(Question, str(qid))
            if not question:
                logger.warning(f"Question {qid} not found, skipping")
                continue

            item = EvaluationItem(
                question_id=str(qid),
                subject_id=str(question.subject_id) if question.subject_id else None,
                topic_id=str(question.topic_id) if question.topic_id else None,
                difficulty_label=question.difficulty_level,
                bloom_level=question.bloom_taxonomy_level,
                rubric_id=rubric_id,
                status=status,
                created_by=created_by,
            )
            self.db.add(item)
            items.append(item)
        
        await self.db.commit()
        for item in items:
            await self.db.refresh(item)
        
        logger.info(f"Bulk created {len(items)} evaluation items")
        return items

    async def get_evaluation_item(self, item_id: uuid.UUID) -> Optional[EvaluationItem]:
        """Get an evaluation item by ID."""
        return await self.db.get(EvaluationItem, self._sid(item_id))

    async def list_evaluation_items(
        self,
        status: Optional[str] = None,
        subject_id: Optional[uuid.UUID] = None,
        topic_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[EvaluationItem], int]:
        """List evaluation items with filters."""
        query = select(EvaluationItem)
        
        if status:
            query = query.where(EvaluationItem.status == status)
        if subject_id:
            query = query.where(EvaluationItem.subject_id == self._sid(subject_id))
        if topic_id:
            query = query.where(EvaluationItem.topic_id == self._sid(topic_id))
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(EvaluationItem.created_at.desc())
        
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return list(items), total

    async def update_evaluation_item(
        self,
        item_id: uuid.UUID,
        data: EvaluationItemUpdate,
    ) -> Optional[EvaluationItem]:
        """Update an evaluation item."""
        item = await self.db.get(EvaluationItem, self._sid(item_id))
        if not item:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        
        item.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(item)
        
        return item

    async def delete_evaluation_item(self, item_id: uuid.UUID) -> bool:
        """Delete an evaluation item."""
        item = await self.db.get(EvaluationItem, self._sid(item_id))
        if not item:
            return False
        
        await self.db.delete(item)
        await self.db.commit()
        return True

    # ==================== Assignments ====================

    async def create_assignment(
        self,
        data: AssignmentCreate,
        created_by: str,
    ) -> Assignment:
        """Create a new assignment."""
        assignment = Assignment(
            id=str(uuid.uuid4()),
            title=data.title,
            description=data.description,
            subject_id=str(data.subject_id) if data.subject_id else None,
            topic_id=str(data.topic_id) if data.topic_id else None,
            cohort=data.cohort,
            grade=data.grade,
            scheduled_start=data.scheduled_start,
            scheduled_end=data.scheduled_end,
            max_attempts_per_item=data.max_attempts_per_item,
            time_limit_minutes=data.time_limit_minutes,
            shuffle_items=data.shuffle_items,
            show_feedback_immediately=data.show_feedback_immediately,
            rubric_id=str(data.rubric_id) if data.rubric_id else None,
            passing_score=data.passing_score,
            status=AssignmentStatus.DRAFT.value,
            created_by=created_by,
        )
        
        self.db.add(assignment)
        await self.db.flush()
        
        # Add evaluation items if provided
        if data.evaluation_item_ids:
            for seq, item_id in enumerate(data.evaluation_item_ids):
                assignment_item = AssignmentItem(
                    assignment_id=assignment.id,
                    evaluation_item_id=str(item_id),
                    sequence_number=seq,
                )
                self.db.add(assignment_item)
        
        await self.db.commit()
        await self.db.refresh(assignment)
        
        logger.info(f"Created assignment {assignment.id}: {assignment.title}")
        return assignment

    async def get_assignment(self, assignment_id: uuid.UUID) -> Optional[Assignment]:
        """Get an assignment by ID."""
        query = select(Assignment).where(Assignment.id == self._sid(assignment_id))
        query = query.options(selectinload(Assignment.items))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_assignments(
        self,
        status: Optional[str] = None,
        cohort: Optional[str] = None,
        grade: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Assignment], int]:
        """List assignments with filters."""
        query = select(Assignment)
        
        if status:
            query = query.where(Assignment.status == status)
        if cohort:
            query = query.where(Assignment.cohort == cohort)
        if grade:
            query = query.where(Assignment.grade == grade)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Assignment.created_at.desc())
        
        result = await self.db.execute(query)
        assignments = result.scalars().all()
        
        return list(assignments), total

    async def update_assignment(
        self,
        assignment_id: uuid.UUID,
        data: AssignmentUpdate,
    ) -> Optional[Assignment]:
        """Update an assignment."""
        assignment = await self.db.get(Assignment, self._sid(assignment_id))
        if not assignment:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(assignment, key, value)
        
        assignment.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(assignment)
        
        return assignment

    async def activate_assignment(self, assignment_id: uuid.UUID) -> Optional[Assignment]:
        """Activate an assignment (make it available to students)."""
        assignment = await self.db.get(Assignment, self._sid(assignment_id))
        if not assignment:
            return None
        
        assignment.status = AssignmentStatus.ACTIVE.value
        assignment.actual_start = datetime.utcnow()
        assignment.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(assignment)
        
        logger.info(f"Activated assignment {assignment_id}")
        return assignment

    async def close_assignment(self, assignment_id: uuid.UUID) -> Optional[Assignment]:
        """Close an assignment."""
        assignment = await self.db.get(Assignment, self._sid(assignment_id))
        if not assignment:
            return None
        
        assignment.status = AssignmentStatus.CLOSED.value
        assignment.actual_end = datetime.utcnow()
        assignment.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(assignment)
        
        logger.info(f"Closed assignment {assignment_id}")
        return assignment

    async def add_items_to_assignment(
        self,
        assignment_id: uuid.UUID,
        evaluation_item_ids: List[uuid.UUID],
        starting_sequence: int = 0,
    ) -> int:
        """Add evaluation items to an assignment."""
        assignment = await self.db.get(Assignment, self._sid(assignment_id))
        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")
        
        added = 0
        for seq, item_id in enumerate(evaluation_item_ids):
            # Check if already exists
            existing = await self.db.execute(
                select(AssignmentItem).where(
                    and_(
                        AssignmentItem.assignment_id == assignment.id,
                        AssignmentItem.evaluation_item_id == self._sid(item_id),
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            assignment_item = AssignmentItem(
                assignment_id=assignment.id,
                evaluation_item_id=self._sid(item_id),
                sequence_number=starting_sequence + seq,
            )
            self.db.add(assignment_item)
            added += 1
        
        await self.db.commit()
        return added

    # ==================== Student Attempts ====================

    async def get_student_assignments(
        self,
        student_id: str,
        cohort: Optional[str] = None,
        grade: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get assignments available to a student."""
        query = select(Assignment).where(
            Assignment.status == AssignmentStatus.ACTIVE.value
        )
        
        if cohort:
            query = query.where(
                or_(Assignment.cohort == cohort, Assignment.cohort.is_(None))
            )
        if grade:
            query = query.where(
                or_(Assignment.grade == grade, Assignment.grade.is_(None))
            )
        
        query = query.options(selectinload(Assignment.items))
        result = await self.db.execute(query)
        assignments = result.scalars().all()
        
        # Enrich with attempt data
        enriched = []
        for assignment in assignments:
            item_count = len(assignment.items) if assignment.items else 0
            
            # Get attempt counts
            attempts_query = select(func.count()).select_from(StudentAttempt).where(
                and_(
                    StudentAttempt.assignment_id == assignment.id,
                    StudentAttempt.student_id == student_id,
                )
            )
            attempt_count = (await self.db.execute(attempts_query)).scalar() or 0
            
            enriched.append({
                "assignment": assignment,
                "item_count": item_count,
                "attempts_made": attempt_count,
            })
        
        return enriched

    async def get_assigned_items(
        self,
        student_id: str,
        assignment_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Get items assigned to a student in an assignment."""
        assignment_id_str = self._sid(assignment_id)
        # Get assignment items
        query = select(AssignmentItem).where(
            AssignmentItem.assignment_id == assignment_id_str
        ).order_by(AssignmentItem.sequence_number)
        
        result = await self.db.execute(query)
        assignment_items = result.scalars().all()
        
        items = []
        for ai in assignment_items:
            eval_item = await self.db.get(EvaluationItem, ai.evaluation_item_id)
            if not eval_item:
                continue
            
            question = await self.db.get(Question, str(eval_item.question_id))
            
            # Get student's attempts for this item
            attempts_query = select(StudentAttempt).where(
                and_(
                    StudentAttempt.evaluation_item_id == ai.evaluation_item_id,
                    StudentAttempt.assignment_id == assignment_id_str,
                    StudentAttempt.student_id == student_id,
                )
            ).order_by(StudentAttempt.attempt_number.desc())
            
            attempts_result = await self.db.execute(attempts_query)
            attempts = attempts_result.scalars().all()
            
            items.append({
                "evaluation_item": eval_item,
                "question": question,
                "sequence_number": ai.sequence_number,
                "weight": ai.weight,
                "time_limit_override": ai.time_limit_override,
                "attempts": list(attempts),
                "attempts_used": len(attempts),
            })
        
        return items

    async def start_attempt(
        self,
        student_id: str,
        data: StudentAttemptCreate,
    ) -> StudentAttempt:
        """Start a new attempt on an evaluation item."""
        eval_item_id = self._sid(data.evaluation_item_id)
        assignment_id = self._sid(data.assignment_id)
        # Verify evaluation item exists
        eval_item = await self.db.get(EvaluationItem, eval_item_id)
        if not eval_item:
            raise ValueError(f"Evaluation item {data.evaluation_item_id} not found")
        
        # Check assignment constraints if provided
        assignment = None
        max_attempts = 1
        if assignment_id:
            assignment = await self.db.get(Assignment, assignment_id)
            if not assignment:
                raise ValueError(f"Assignment {data.assignment_id} not found")
            if assignment.status != AssignmentStatus.ACTIVE.value:
                raise ValueError("Assignment is not active")
            max_attempts = assignment.max_attempts_per_item
        
        # Count existing attempts
        existing_query = select(func.count()).select_from(StudentAttempt).where(
            and_(
                StudentAttempt.student_id == student_id,
                StudentAttempt.evaluation_item_id == eval_item_id,
                StudentAttempt.assignment_id == assignment_id if assignment_id else True,
            )
        )
        existing_count = (await self.db.execute(existing_query)).scalar() or 0
        
        if existing_count >= max_attempts:
            raise ValueError(f"Maximum attempts ({max_attempts}) reached for this item")
        
        # Check for in-progress attempt
        in_progress_query = select(StudentAttempt).where(
            and_(
                StudentAttempt.student_id == student_id,
                StudentAttempt.evaluation_item_id == eval_item_id,
                StudentAttempt.assignment_id == assignment_id if assignment_id else True,
                StudentAttempt.status == AttemptStatus.IN_PROGRESS.value,
            )
        )
        in_progress = (await self.db.execute(in_progress_query)).scalar_one_or_none()
        if in_progress:
            # Return existing in-progress attempt
            return in_progress
        
        # Create new attempt
        attempt = StudentAttempt(
            student_id=student_id,
            evaluation_item_id=eval_item_id,
            assignment_id=assignment_id,
            attempt_number=existing_count + 1,
            status=AttemptStatus.IN_PROGRESS.value,
            started_at=datetime.utcnow(),
            is_draft=True,
        )
        
        self.db.add(attempt)
        await self.db.commit()
        await self.db.refresh(attempt)
        
        # Log event
        event = AttemptEvent(
            attempt_id=attempt.id,
            event_type="started",
            actor_id=student_id,
            actor_type="student",
        )
        self.db.add(event)
        await self.db.commit()
        
        logger.info(f"Started attempt {attempt.id} for student {student_id}")
        return attempt

    async def save_draft(
        self,
        attempt_id: uuid.UUID,
        student_id: str,
        data: StudentAttemptDraft,
    ) -> StudentAttempt:
        """Save a draft of an attempt."""
        attempt = await self.db.get(StudentAttempt, self._sid(attempt_id))
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found")
        if attempt.student_id != student_id:
            raise ValueError("Not authorized to modify this attempt")
        if attempt.status not in [AttemptStatus.NOT_STARTED.value, AttemptStatus.IN_PROGRESS.value]:
            raise ValueError("Cannot modify a submitted attempt")
        
        # Update fields
        if data.has_issues_detected is not None:
            attempt.has_issues_detected = data.has_issues_detected
        if data.reasoning_text is not None:
            attempt.reasoning_text = data.reasoning_text
        if data.correction_text is not None:
            attempt.correction_text = data.correction_text
        if data.confidence_score is not None:
            attempt.confidence_score = data.confidence_score
        if data.draft_data is not None:
            attempt.draft_data = data.draft_data
        
        attempt.is_draft = True
        attempt.updated_at = datetime.utcnow()
        
        # Handle issues
        if data.issues:
            # Clear existing issues
            await self.db.execute(
                select(AttemptIssue).where(AttemptIssue.attempt_id == self._sid(attempt_id))
            )
            for issue_data in data.issues:
                issue = AttemptIssue(
                    attempt_id=attempt.id,
                    category=issue_data.category,
                    severity=issue_data.severity,
                    description=issue_data.description,
                    location_start=issue_data.location_start,
                    location_end=issue_data.location_end,
                    location_field=issue_data.location_field,
                )
                self.db.add(issue)
        
        await self.db.commit()
        await self.db.refresh(attempt)
        
        # Log event
        event = AttemptEvent(
            attempt_id=attempt.id,
            event_type="saved_draft",
            actor_id=student_id,
            actor_type="student",
        )
        self.db.add(event)
        await self.db.commit()
        
        return attempt

    async def submit_attempt(
        self,
        attempt_id: uuid.UUID,
        student_id: str,
        data: StudentAttemptSubmit,
    ) -> Dict[str, Any]:
        """Submit an attempt for scoring."""
        attempt = await self.db.get(StudentAttempt, self._sid(attempt_id))
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found")
        if attempt.student_id != student_id:
            raise ValueError("Not authorized to submit this attempt")
        if attempt.status not in [AttemptStatus.NOT_STARTED.value, AttemptStatus.IN_PROGRESS.value]:
            raise ValueError("Attempt already submitted")
        
        # Update attempt with submission data
        attempt.has_issues_detected = data.has_issues_detected
        attempt.reasoning_text = data.reasoning_text
        attempt.correction_text = data.correction_text
        attempt.confidence_score = data.confidence_score
        attempt.is_draft = False
        attempt.submitted_at = datetime.utcnow()
        attempt.status = AttemptStatus.SUBMITTED.value
        
        # Calculate time spent
        if attempt.started_at:
            delta = attempt.submitted_at - attempt.started_at
            attempt.time_spent_seconds = int(delta.total_seconds())
        
        # Clear and add issues
        await self.db.execute(
            select(AttemptIssue).where(AttemptIssue.attempt_id == self._sid(attempt_id))
        )
        for issue_data in data.issues:
            issue = AttemptIssue(
                attempt_id=attempt.id,
                category=issue_data.category,
                severity=issue_data.severity,
                description=issue_data.description,
                location_start=issue_data.location_start,
                location_end=issue_data.location_end,
                location_field=issue_data.location_field,
            )
            self.db.add(issue)
        
        await self.db.commit()
        
        # Log submission event
        event = AttemptEvent(
            attempt_id=attempt.id,
            event_type="submitted",
            actor_id=student_id,
            actor_type="student",
            event_data={"issues_count": len(data.issues)},
        )
        self.db.add(event)
        await self.db.commit()
        
        # Score the attempt
        scoring_result = await self.scoring_service.score_attempt(str(attempt.id))
        
        # Check if feedback should be shown immediately
        show_feedback = False
        if attempt.assignment_id:
            assignment = await self.db.get(Assignment, self._sid(attempt.assignment_id))
            if assignment and assignment.show_feedback_immediately:
                show_feedback = True
                attempt.feedback_shown_at = datetime.utcnow()
                await self.db.commit()
        
        return {
            "attempt_id": str(attempt.id),
            "status": attempt.status,
            "total_score": scoring_result["total_score"],
            "show_feedback": show_feedback,
            "feedback": scoring_result["feedback"] if show_feedback else None,
            "score_breakdown": scoring_result["score_breakdown"] if show_feedback else None,
        }

    async def get_attempt(
        self,
        attempt_id: uuid.UUID,
        student_id: Optional[str] = None,
    ) -> Optional[StudentAttempt]:
        """Get an attempt by ID."""
        query = select(StudentAttempt).where(StudentAttempt.id == self._sid(attempt_id))
        query = query.options(
            selectinload(StudentAttempt.issues),
            selectinload(StudentAttempt.scores),
        )
        
        if student_id:
            query = query.where(StudentAttempt.student_id == student_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_attempt_feedback(
        self,
        attempt_id: uuid.UUID,
        student_id: str,
    ) -> Dict[str, Any]:
        """Get feedback for an attempt."""
        attempt = await self.get_attempt(attempt_id, student_id)
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found")
        
        if attempt.status not in [AttemptStatus.SCORED.value, AttemptStatus.REVIEWED.value]:
            raise ValueError("Attempt has not been scored yet")
        
        # Mark feedback as shown
        if not attempt.feedback_shown_at:
            attempt.feedback_shown_at = datetime.utcnow()
            await self.db.commit()
            
            # Log event
            event = AttemptEvent(
                attempt_id=attempt.id,
                event_type="feedback_viewed",
                actor_id=student_id,
                actor_type="student",
            )
            self.db.add(event)
            await self.db.commit()
        
        # Get evaluation item for ground truth
        eval_item = await self.db.get(EvaluationItem, attempt.evaluation_item_id)
        
        final_score = attempt.score_override if attempt.score_override is not None else attempt.total_score
        
        return {
            "attempt_id": str(attempt.id),
            "total_score": final_score,
            "max_possible_score": 100.0,
            "percentage": final_score,
            "passed": final_score >= 60 if final_score else False,
            "score_breakdown": attempt.score_breakdown,
            "feedback_text": attempt.feedback_text,
            "known_issues": eval_item.known_issues if eval_item else None,
            "expected_detection_count": eval_item.expected_detection_count if eval_item else None,
            "issues": [
                {
                    "category": i.category,
                    "severity": i.severity,
                    "description": i.description,
                    "is_valid": i.is_valid,
                    "validation_notes": i.validation_notes,
                }
                for i in attempt.issues
            ],
        }

    async def list_student_attempts(
        self,
        student_id: str,
        assignment_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[StudentAttempt], int]:
        """List attempts for a student."""
        query = select(StudentAttempt).where(StudentAttempt.student_id == student_id)
        
        if assignment_id:
            query = query.where(StudentAttempt.assignment_id == self._sid(assignment_id))
        if status:
            query = query.where(StudentAttempt.status == status)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(StudentAttempt.created_at.desc())
        query = query.options(selectinload(StudentAttempt.issues))
        
        result = await self.db.execute(query)
        attempts = result.scalars().all()
        
        return list(attempts), total

    # ==================== Dashboard ====================

    async def get_student_dashboard(
        self,
        student_id: str,
        cohort: Optional[str] = None,
        grade: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get dashboard data for a student."""
        # Get active assignments
        assignments = await self.get_student_assignments(student_id, cohort, grade)
        
        # Count attempts by status
        in_progress_query = select(func.count()).select_from(StudentAttempt).where(
            and_(
                StudentAttempt.student_id == student_id,
                StudentAttempt.status == AttemptStatus.IN_PROGRESS.value,
            )
        )
        in_progress = (await self.db.execute(in_progress_query)).scalar() or 0
        
        completed_query = select(func.count()).select_from(StudentAttempt).where(
            and_(
                StudentAttempt.student_id == student_id,
                StudentAttempt.status.in_([AttemptStatus.SCORED.value, AttemptStatus.REVIEWED.value]),
            )
        )
        completed = (await self.db.execute(completed_query)).scalar() or 0
        
        # Calculate average score
        avg_query = select(func.avg(StudentAttempt.total_score)).where(
            and_(
                StudentAttempt.student_id == student_id,
                StudentAttempt.total_score.isnot(None),
            )
        )
        avg_score = (await self.db.execute(avg_query)).scalar()
        
        # Count due soon (within 24 hours)
        due_soon = 0
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        for a in assignments:
            assignment = a["assignment"]
            if assignment.scheduled_end and now < assignment.scheduled_end < tomorrow:
                due_soon += a["item_count"] - a["attempts_made"]
        
        return {
            "assignments": assignments,
            "in_progress_count": in_progress,
            "completed_count": completed,
            "due_soon_count": due_soon,
            "average_score": round(avg_score, 2) if avg_score else None,
        }

    # ==================== Statistics ====================

    async def get_statistics(
        self,
        subject_id: Optional[uuid.UUID] = None,
        cohort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get GEL statistics."""
        # Evaluation items
        items_query = select(func.count()).select_from(EvaluationItem)
        if subject_id:
            items_query = items_query.where(EvaluationItem.subject_id == subject_id)
        total_items = (await self.db.execute(items_query)).scalar() or 0
        
        active_items_query = items_query.where(EvaluationItem.status == EvaluationItemStatus.ACTIVE.value)
        active_items = (await self.db.execute(active_items_query)).scalar() or 0
        
        # Assignments
        assignments_query = select(func.count()).select_from(Assignment)
        total_assignments = (await self.db.execute(assignments_query)).scalar() or 0
        
        active_assignments_query = assignments_query.where(Assignment.status == AssignmentStatus.ACTIVE.value)
        active_assignments = (await self.db.execute(active_assignments_query)).scalar() or 0
        
        # Attempts
        attempts_query = select(func.count()).select_from(StudentAttempt)
        total_attempts = (await self.db.execute(attempts_query)).scalar() or 0
        
        completed_attempts_query = attempts_query.where(
            StudentAttempt.status.in_([AttemptStatus.SCORED.value, AttemptStatus.REVIEWED.value])
        )
        completed_attempts = (await self.db.execute(completed_attempts_query)).scalar() or 0
        
        # Average score
        avg_query = select(func.avg(StudentAttempt.total_score)).where(
            StudentAttempt.total_score.isnot(None)
        )
        avg_score = (await self.db.execute(avg_query)).scalar()
        
        # Score distribution
        score_dist = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        scores_query = select(StudentAttempt.total_score).where(
            StudentAttempt.total_score.isnot(None)
        )
        scores_result = await self.db.execute(scores_query)
        for (score,) in scores_result:
            if score <= 20:
                score_dist["0-20"] += 1
            elif score <= 40:
                score_dist["21-40"] += 1
            elif score <= 60:
                score_dist["41-60"] += 1
            elif score <= 80:
                score_dist["61-80"] += 1
            else:
                score_dist["81-100"] += 1
        
        # Common issues
        issues_query = select(
            AttemptIssue.category,
            func.count(AttemptIssue.id).label("count")
        ).group_by(AttemptIssue.category).order_by(func.count(AttemptIssue.id).desc()).limit(10)
        issues_result = await self.db.execute(issues_query)
        common_issues = [{"category": cat, "count": cnt} for cat, cnt in issues_result]

        # Confidence calibration placeholder until detailed calibration metrics are stored
        confidence_calibration = {
            "overconfident": 0,
            "underconfident": 0,
            "calibrated": 0,
        }
        
        return {
            "total_evaluation_items": total_items,
            "active_evaluation_items": active_items,
            "total_assignments": total_assignments,
            "active_assignments": active_assignments,
            "total_attempts": total_attempts,
            "completed_attempts": completed_attempts,
            "average_score": round(avg_score, 2) if avg_score else None,
            "score_distribution": score_dist,
            "common_issues": common_issues,
            "confidence_calibration": confidence_calibration,
        }
