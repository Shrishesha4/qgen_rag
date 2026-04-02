"""
GEL Scoring Service.

Implements scoring for student evaluation attempts:
- Detection accuracy (did student find the right issues?)
- Reasoning quality (is the explanation sound?)
- Correction quality (is the proposed fix appropriate?)
- Confidence calibration (with overconfidence penalty)
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
import math

from app.models.gel import (
    StudentAttempt, AttemptIssue, AttemptScore, AttemptEvent,
    EvaluationItem, AttemptStatus
)
from app.models.rubric import Rubric

logger = logging.getLogger(__name__)


# Default scoring weights
DEFAULT_WEIGHTS = {
    "detection": 0.35,
    "reasoning": 0.25,
    "correction": 0.20,
    "confidence_calibration": 0.20,
}

# Default max scores per dimension
DEFAULT_MAX_SCORES = {
    "detection": 100.0,
    "reasoning": 100.0,
    "correction": 100.0,
    "confidence_calibration": 100.0,
}

# Confidence calibration parameters
OVERCONFIDENCE_PENALTY_FACTOR = 1.5  # Penalty multiplier for overconfidence
UNDERCONFIDENCE_BONUS_FACTOR = 0.5  # Smaller bonus for underconfidence


class GELScoringService:
    """Service for scoring student evaluation attempts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def score_attempt(
        self,
        attempt_id: str,
        rubric_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Score a student attempt.
        
        Returns:
            Dict with total_score, score_breakdown, and per-dimension scores
        """
        # Fetch attempt with issues
        attempt = await self.db.get(StudentAttempt, attempt_id)
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found")
        
        if attempt.status not in [AttemptStatus.SUBMITTED.value, AttemptStatus.IN_PROGRESS.value]:
            raise ValueError(f"Attempt {attempt_id} is not in a scorable state")
        
        # Fetch evaluation item for ground truth
        eval_item = await self.db.get(EvaluationItem, str(attempt.evaluation_item_id))
        if not eval_item:
            raise ValueError(f"Evaluation item not found for attempt {attempt_id}")
        
        # Fetch rubric if specified
        rubric = None
        rubric_config = {}
        if rubric_id:
            rubric = await self.db.get(Rubric, rubric_id)
            if rubric and rubric.config:
                rubric_config = rubric.config
        elif eval_item.rubric_id:
            rubric = await self.db.get(Rubric, str(eval_item.rubric_id))
            if rubric and rubric.config:
                rubric_config = rubric.config
        
        # Get weights from rubric or use defaults
        weights = rubric_config.get("weights", DEFAULT_WEIGHTS)
        max_scores = rubric_config.get("max_scores", DEFAULT_MAX_SCORES)
        
        # Fetch student's identified issues
        issues_result = await self.db.execute(
            select(AttemptIssue).where(AttemptIssue.attempt_id == attempt.id)
        )
        student_issues = issues_result.scalars().all()
        
        # Score each dimension
        detection_result = await self._score_detection(
            attempt, eval_item, student_issues, max_scores["detection"]
        )
        reasoning_result = await self._score_reasoning(
            attempt, eval_item, student_issues, max_scores["reasoning"]
        )
        correction_result = await self._score_correction(
            attempt, eval_item, max_scores["correction"]
        )
        calibration_result = await self._score_confidence_calibration(
            attempt, detection_result["accuracy"], max_scores["confidence_calibration"]
        )
        
        # Calculate weighted total
        dimension_scores = {
            "detection": detection_result,
            "reasoning": reasoning_result,
            "correction": correction_result,
            "confidence_calibration": calibration_result,
        }
        
        total_weighted = 0.0
        total_max_weighted = 0.0
        
        for dim, result in dimension_scores.items():
            weight = weights.get(dim, DEFAULT_WEIGHTS.get(dim, 0.25))
            weighted = result["raw_score"] * weight
            max_weighted = result["max_score"] * weight
            result["weight"] = weight
            result["weighted_score"] = weighted
            total_weighted += weighted
            total_max_weighted += max_weighted
        
        # Normalize to 0-100 scale
        total_score = (total_weighted / total_max_weighted * 100) if total_max_weighted > 0 else 0
        
        # Save scores to database
        await self._save_scores(attempt, dimension_scores)
        
        # Update attempt with total score
        attempt.total_score = total_score
        attempt.score_breakdown = {
            dim: {
                "raw": r["raw_score"],
                "max": r["max_score"],
                "weighted": r["weighted_score"],
                "weight": r["weight"],
            }
            for dim, r in dimension_scores.items()
        }
        attempt.scored_at = datetime.utcnow()
        attempt.scored_by = "auto"
        attempt.status = AttemptStatus.SCORED.value
        
        # Generate feedback
        feedback = self._generate_feedback(attempt, dimension_scores, eval_item)
        attempt.feedback_text = feedback
        
        await self.db.commit()
        
        # Log scoring event
        await self._log_event(attempt.id, "scored", {
            "total_score": total_score,
            "dimensions": {d: r["raw_score"] for d, r in dimension_scores.items()},
        })
        
        return {
            "total_score": total_score,
            "max_possible_score": 100.0,
            "percentage": total_score,
            "score_breakdown": dimension_scores,
            "feedback": feedback,
        }

    async def _score_detection(
        self,
        attempt: StudentAttempt,
        eval_item: EvaluationItem,
        student_issues: List[AttemptIssue],
        max_score: float,
    ) -> Dict[str, Any]:
        """
        Score detection accuracy.
        
        Compares student-identified issues against known issues (ground truth).
        """
        known_issues = eval_item.known_issues or {}
        expected_count = eval_item.expected_detection_count or 0
        is_control = eval_item.is_control_item
        control_type = eval_item.control_type
        
        # For control items with known good questions (no issues)
        if is_control and control_type == "known_good":
            # Student should NOT find issues
            if attempt.has_issues_detected is False or len(student_issues) == 0:
                return {
                    "raw_score": max_score,
                    "max_score": max_score,
                    "accuracy": 1.0,
                    "notes": "Correctly identified question as having no issues",
                }
            else:
                # Penalize false positives
                false_positive_penalty = min(len(student_issues) * 20, max_score)
                return {
                    "raw_score": max(0, max_score - false_positive_penalty),
                    "max_score": max_score,
                    "accuracy": 0.0,
                    "notes": f"False positives: found {len(student_issues)} issues in a good question",
                }
        
        # For control items with known bad questions
        if is_control and control_type == "known_bad":
            if attempt.has_issues_detected is True and len(student_issues) > 0:
                # Check if they found the right issues
                matched = self._match_issues(student_issues, known_issues)
                accuracy = matched / max(expected_count, 1) if expected_count > 0 else (1.0 if matched > 0 else 0.0)
                return {
                    "raw_score": accuracy * max_score,
                    "max_score": max_score,
                    "accuracy": accuracy,
                    "notes": f"Found {matched}/{expected_count} known issues",
                }
            else:
                return {
                    "raw_score": 0,
                    "max_score": max_score,
                    "accuracy": 0.0,
                    "notes": "Failed to detect issues in a known problematic question",
                }
        
        # For regular items (non-control)
        if not known_issues and expected_count == 0:
            # No ground truth available - use heuristic scoring
            # Give partial credit for reasonable detection
            if attempt.has_issues_detected is not None:
                return {
                    "raw_score": max_score * 0.7,  # Partial credit for attempting
                    "max_score": max_score,
                    "accuracy": 0.7,
                    "notes": "No ground truth available; partial credit awarded",
                }
            return {
                "raw_score": 0,
                "max_score": max_score,
                "accuracy": 0.0,
                "notes": "No detection response provided",
            }
        
        # Standard scoring with ground truth
        matched = self._match_issues(student_issues, known_issues)
        false_positives = max(0, len(student_issues) - matched)
        false_negatives = max(0, expected_count - matched)
        
        # Calculate precision and recall
        precision = matched / len(student_issues) if student_issues else 0
        recall = matched / expected_count if expected_count > 0 else (1.0 if not student_issues else 0)
        
        # F1-like score
        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0
        
        return {
            "raw_score": f1 * max_score,
            "max_score": max_score,
            "accuracy": f1,
            "precision": precision,
            "recall": recall,
            "matched_issues": matched,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "notes": f"Precision: {precision:.2f}, Recall: {recall:.2f}, F1: {f1:.2f}",
        }

    def _match_issues(
        self,
        student_issues: List[AttemptIssue],
        known_issues: Dict[str, Any],
    ) -> int:
        """
        Match student issues against known issues.
        
        Returns count of correctly identified issues.
        """
        if not known_issues:
            return 0
        
        known_categories = set()
        if isinstance(known_issues, dict):
            # Format: {"issues": [{"category": "factual_error", ...}, ...]}
            for issue in known_issues.get("issues", []):
                if isinstance(issue, dict):
                    known_categories.add(issue.get("category", "").lower())
                elif isinstance(issue, str):
                    known_categories.add(issue.lower())
        elif isinstance(known_issues, list):
            for issue in known_issues:
                if isinstance(issue, dict):
                    known_categories.add(issue.get("category", "").lower())
                elif isinstance(issue, str):
                    known_categories.add(issue.lower())
        
        matched = 0
        for student_issue in student_issues:
            if student_issue.category.lower() in known_categories:
                matched += 1
                # Mark as valid
                student_issue.is_valid = True
            else:
                student_issue.is_valid = False
        
        return matched

    async def _score_reasoning(
        self,
        attempt: StudentAttempt,
        eval_item: EvaluationItem,
        student_issues: List[AttemptIssue],
        max_score: float,
    ) -> Dict[str, Any]:
        """
        Score reasoning quality.
        
        Evaluates the explanation provided by the student.
        """
        reasoning = attempt.reasoning_text or ""
        
        if not reasoning.strip():
            return {
                "raw_score": 0,
                "max_score": max_score,
                "notes": "No reasoning provided",
            }
        
        # Basic heuristics for reasoning quality
        word_count = len(reasoning.split())
        has_specific_references = any(
            keyword in reasoning.lower()
            for keyword in ["because", "therefore", "since", "due to", "as a result", "specifically"]
        )
        
        # Length-based scoring (minimum 20 words for full credit)
        length_score = min(word_count / 20, 1.0)
        
        # Specificity bonus
        specificity_bonus = 0.2 if has_specific_references else 0
        
        # Issue alignment - reasoning should reference identified issues
        issue_alignment = 0.0
        if student_issues:
            issue_categories = [i.category.lower().replace("_", " ") for i in student_issues]
            aligned = sum(1 for cat in issue_categories if cat in reasoning.lower())
            issue_alignment = aligned / len(student_issues) if student_issues else 0
        
        # Combined score
        raw_score = (length_score * 0.4 + specificity_bonus + issue_alignment * 0.4) * max_score
        raw_score = min(raw_score, max_score)
        
        return {
            "raw_score": raw_score,
            "max_score": max_score,
            "word_count": word_count,
            "has_specificity": has_specific_references,
            "issue_alignment": issue_alignment,
            "notes": f"Word count: {word_count}, Specificity: {has_specific_references}, Alignment: {issue_alignment:.2f}",
        }

    async def _score_correction(
        self,
        attempt: StudentAttempt,
        eval_item: EvaluationItem,
        max_score: float,
    ) -> Dict[str, Any]:
        """
        Score correction quality.
        
        Evaluates the proposed fix/correction.
        """
        correction = attempt.correction_text or ""
        has_issues = attempt.has_issues_detected
        
        # If no issues detected, correction is not expected
        if has_issues is False:
            return {
                "raw_score": max_score,  # Full credit for not providing unnecessary correction
                "max_score": max_score,
                "notes": "No correction needed (no issues detected)",
            }
        
        if not correction.strip():
            # Issues detected but no correction provided
            return {
                "raw_score": max_score * 0.3,  # Partial credit
                "max_score": max_score,
                "notes": "Issues detected but no correction provided",
            }
        
        # Basic heuristics for correction quality
        word_count = len(correction.split())
        
        # Length-based scoring
        length_score = min(word_count / 15, 1.0)
        
        # Check for actionable language
        actionable_keywords = ["should", "could", "change", "replace", "remove", "add", "modify", "correct", "fix"]
        has_actionable = any(kw in correction.lower() for kw in actionable_keywords)
        actionable_bonus = 0.2 if has_actionable else 0
        
        raw_score = (length_score * 0.8 + actionable_bonus) * max_score
        raw_score = min(raw_score, max_score)
        
        return {
            "raw_score": raw_score,
            "max_score": max_score,
            "word_count": word_count,
            "has_actionable": has_actionable,
            "notes": f"Word count: {word_count}, Actionable: {has_actionable}",
        }

    async def _score_confidence_calibration(
        self,
        attempt: StudentAttempt,
        actual_accuracy: float,
        max_score: float,
    ) -> Dict[str, Any]:
        """
        Score confidence calibration.
        
        Compares student's confidence against their actual accuracy.
        Penalizes overconfidence more than underconfidence.
        """
        confidence = attempt.confidence_score
        
        if confidence is None:
            return {
                "raw_score": 0,
                "max_score": max_score,
                "notes": "No confidence score provided",
            }
        
        # Calculate calibration error
        calibration_error = abs(confidence - actual_accuracy)
        
        # Determine if overconfident or underconfident
        is_overconfident = confidence > actual_accuracy
        
        # Apply asymmetric penalty
        if is_overconfident:
            # Stronger penalty for overconfidence
            penalty = calibration_error * OVERCONFIDENCE_PENALTY_FACTOR
        else:
            # Smaller penalty for underconfidence
            penalty = calibration_error * UNDERCONFIDENCE_BONUS_FACTOR
        
        # Calculate score (1 - penalty, clamped to [0, 1])
        calibration_score = max(0, 1 - penalty)
        raw_score = calibration_score * max_score
        
        return {
            "raw_score": raw_score,
            "max_score": max_score,
            "confidence": confidence,
            "actual_accuracy": actual_accuracy,
            "calibration_error": calibration_error,
            "is_overconfident": is_overconfident,
            "notes": f"Confidence: {confidence:.2f}, Accuracy: {actual_accuracy:.2f}, Error: {calibration_error:.2f}",
        }

    async def _save_scores(
        self,
        attempt: StudentAttempt,
        dimension_scores: Dict[str, Dict[str, Any]],
    ) -> None:
        """Save per-dimension scores to database."""
        for dimension, result in dimension_scores.items():
            score = AttemptScore(
                attempt_id=attempt.id,
                dimension=dimension,
                raw_score=result["raw_score"],
                max_score=result["max_score"],
                weighted_score=result.get("weighted_score", result["raw_score"]),
                weight=result.get("weight", 1.0),
                scoring_notes=result.get("notes"),
                scoring_metadata={k: v for k, v in result.items() if k not in ["raw_score", "max_score", "weighted_score", "weight", "notes"]},
            )
            self.db.add(score)

    def _generate_feedback(
        self,
        attempt: StudentAttempt,
        dimension_scores: Dict[str, Dict[str, Any]],
        eval_item: EvaluationItem,
    ) -> str:
        """Generate human-readable feedback for the student."""
        feedback_parts = []
        total = attempt.total_score or 0
        
        # Overall assessment
        if total >= 80:
            feedback_parts.append("Excellent work! You demonstrated strong evaluation skills.")
        elif total >= 60:
            feedback_parts.append("Good effort! There's room for improvement in some areas.")
        elif total >= 40:
            feedback_parts.append("Fair attempt. Review the feedback below to improve.")
        else:
            feedback_parts.append("This attempt needs significant improvement. Please review carefully.")
        
        feedback_parts.append("")
        
        # Per-dimension feedback
        detection = dimension_scores.get("detection", {})
        if detection.get("accuracy", 0) < 0.5:
            feedback_parts.append("**Detection**: Work on identifying issues more accurately. Look for factual errors, ambiguities, and formatting problems.")
        elif detection.get("false_positives", 0) > 0:
            feedback_parts.append(f"**Detection**: You identified some issues correctly but also flagged {detection.get('false_positives', 0)} items that weren't actual problems.")
        else:
            feedback_parts.append("**Detection**: Good job identifying the issues!")
        
        reasoning = dimension_scores.get("reasoning", {})
        if reasoning.get("word_count", 0) < 10:
            feedback_parts.append("**Reasoning**: Provide more detailed explanations for your findings.")
        elif not reasoning.get("has_specificity", False):
            feedback_parts.append("**Reasoning**: Use more specific language (e.g., 'because', 'therefore') to strengthen your reasoning.")
        else:
            feedback_parts.append("**Reasoning**: Your explanations were clear and specific.")
        
        correction = dimension_scores.get("correction", {})
        if attempt.has_issues_detected and not attempt.correction_text:
            feedback_parts.append("**Correction**: When you identify issues, always suggest how to fix them.")
        elif correction.get("has_actionable", False):
            feedback_parts.append("**Correction**: Good actionable suggestions for improvement.")
        
        calibration = dimension_scores.get("confidence_calibration", {})
        if calibration.get("is_overconfident", False):
            feedback_parts.append("**Confidence**: Your confidence was higher than your accuracy. Try to be more realistic about your certainty.")
        elif calibration.get("calibration_error", 0) < 0.2:
            feedback_parts.append("**Confidence**: Well-calibrated confidence level!")
        
        return "\n".join(feedback_parts)

    async def _log_event(
        self,
        attempt_id: str,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> None:
        """Log an attempt event."""
        event = AttemptEvent(
            attempt_id=attempt_id,
            event_type=event_type,
            event_data=event_data,
            actor_type="system",
        )
        self.db.add(event)
        await self.db.commit()

    async def get_rubric_config(self, rubric_id: str) -> Dict[str, Any]:
        """Get rubric configuration for scoring."""
        rubric = await self.db.get(Rubric, rubric_id)
        if not rubric:
            return {
                "weights": DEFAULT_WEIGHTS,
                "max_scores": DEFAULT_MAX_SCORES,
            }
        
        config = rubric.config or {}
        return {
            "weights": config.get("weights", DEFAULT_WEIGHTS),
            "max_scores": config.get("max_scores", DEFAULT_MAX_SCORES),
            "descriptors": config.get("descriptors", {}),
        }

    async def override_score(
        self,
        attempt_id: str,
        new_score: float,
        reviewer_id: str,
        review_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Override the automated score with a manual score.
        """
        attempt = await self.db.get(StudentAttempt, attempt_id)
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found")
        
        original_score = attempt.total_score
        attempt.score_override = new_score
        attempt.reviewed_at = datetime.utcnow()
        attempt.reviewed_by = reviewer_id
        attempt.review_notes = review_notes
        attempt.status = AttemptStatus.REVIEWED.value
        
        await self.db.commit()
        
        # Log review event
        await self._log_event(attempt.id, "reviewed", {
            "original_score": original_score,
            "override_score": new_score,
            "reviewer_id": reviewer_id,
        })
        
        return {
            "attempt_id": str(attempt.id),
            "original_score": original_score,
            "override_score": new_score,
            "final_score": new_score,
            "reviewed_by": reviewer_id,
            "reviewed_at": attempt.reviewed_at.isoformat(),
        }
