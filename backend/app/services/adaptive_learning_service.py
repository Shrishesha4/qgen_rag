#!/usr/bin/env python
"""
Adaptive Learning Service

Implements adaptive difficulty and multi-subject learning mechanisms.
Analyzes vetting patterns to understand what makes questions good/bad for different subjects and difficulty levels.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.question import Question
from app.models.training import VettingLog, VettingReasonCode, TrainingPair
from app.models.subject import Subject
from app.models.topic import Topic

logger = logging.getLogger(__name__)

class DifficultyProfile:
    """Profile for what constitutes difficulty levels in different subjects."""
    
    def __init__(self, subject_id: str):
        self.subject_id = subject_id
        self.easy_patterns: List[str] = []
        self.medium_patterns: List[str] = []
        self.hard_patterns: List[str] = []
        self.indicator_weights: Dict[str, float] = {}
        self.success_rates: Dict[str, float] = {}
        
    def add_pattern(self, difficulty: str, pattern: str, success_rate: float):
        """Add a pattern for a difficulty level with its success rate."""
        if difficulty == "easy":
            self.easy_patterns.append((pattern, success_rate))
        elif difficulty == "medium":
            self.medium_patterns.append((pattern, success_rate))
        elif difficulty == "hard":
            self.hard_patterns.append((pattern, success_rate))
    
    def predict_difficulty(self, question_text: str) -> Tuple[str, float]:
        """Predict difficulty of a question based on learned patterns."""
        scores = {"easy": 0.0, "medium": 0.0, "hard": 0.0}
        
        # Check against patterns
        for pattern, weight in self.easy_patterns:
            if pattern.lower() in question_text.lower():
                scores["easy"] += weight
                
        for pattern, weight in self.medium_patterns:
            if pattern.lower() in question_text.lower():
                scores["medium"] += weight
                
        for pattern, weight in self.hard_patterns:
            if pattern.lower() in question_text.lower():
                scores["hard"] += weight
        
        # Normalize scores
        total = sum(scores.values())
        if total > 0:
            scores = {k: v/total for k, v in scores.items()}
        
        predicted = max(scores, key=scores.get)
        confidence = scores[predicted]
        
        return predicted, confidence

class SubjectProfile:
    """Profile for learning patterns specific to a subject."""
    
    def __init__(self, subject_id: str, subject_name: str):
        self.subject_id = subject_id
        self.subject_name = subject_name
        self.approval_patterns: List[str] = []
        self.rejection_patterns: List[str] = []
        self.topic_difficulty_map: Dict[str, str] = {}
        self.optimal_question_types: Dict[str, float] = {}
        self.common_mistakes: List[str] = []
        
    def add_approval_pattern(self, pattern: str):
        """Add a pattern that leads to approval."""
        if pattern not in self.approval_patterns:
            self.approval_patterns.append(pattern)
    
    def add_rejection_pattern(self, pattern: str):
        """Add a pattern that leads to rejection."""
        if pattern not in self.rejection_patterns:
            self.rejection_patterns.append(pattern)

class AdaptiveLearningService:
    """
    Service that learns from vetting data to improve question generation.
    
    Key capabilities:
    1. Understands what makes questions "easy", "medium", or "hard" for each subject
    2. Learns subject-specific patterns that lead to approval/rejection
    3. Adapts to multi-subject contexts
    4. Provides feedback to improve generation quality
    """
    
    def __init__(self):
        self.subject_profiles: Dict[str, SubjectProfile] = {}
        self.difficulty_profiles: Dict[str, DifficultyProfile] = {}
        self.global_patterns: Dict[str, float] = {}
        self.last_update: Optional[datetime] = None
        
        # Load existing profiles
        asyncio.create_task(self._load_profiles())
    
    async def _load_profiles(self):
        """Load learning profiles from database."""
        async with AsyncSessionLocal() as db:
            await self._analyze_subject_patterns(db)
            await self._analyze_difficulty_patterns(db)
            await self._analyze_global_patterns(db)
            
        self.last_update = datetime.utcnow()
        logger.info(f"Loaded profiles for {len(self.subject_profiles)} subjects")
    
    async def _analyze_subject_patterns(self, db: AsyncSession):
        """Analyze approval/rejection patterns per subject."""
        # Get all subjects
        subjects_result = await db.execute(select(Subject))
        subjects = subjects_result.scalars().all()
        
        for subject in subjects:
            profile = SubjectProfile(str(subject.id), subject.name)
            
            # Analyze recent vetting for this subject
            recent_date = datetime.utcnow() - timedelta(days=30)
            
            # Get approved questions
            approved_result = await db.execute(
                select(Question)
                .join(VettingLog, Question.id == VettingLog.question_id)
                .where(
                    and_(
                        Question.subject_id == subject.id,
                        VettingLog.decision == "approve",
                        VettingLog.created_at >= recent_date
                    )
                )
                .limit(100)
            )
            approved_questions = approved_result.scalars().all()
            
            # Get rejected questions
            rejected_result = await db.execute(
                select(Question)
                .join(VettingLog, Question.id == VettingLog.question_id)
                .where(
                    and_(
                        Question.subject_id == subject.id,
                        VettingLog.decision == "reject",
                        VettingLog.created_at >= recent_date
                    )
                )
                .limit(100)
            )
            rejected_questions = rejected_result.scalars().all()
            
            # Extract patterns from approved questions
            for q in approved_questions:
                # Add question starters
                words = q.question_text.split()[:3]  # First 3 words
                pattern = " ".join(words)
                profile.add_approval_pattern(pattern)
                
                # Add question type success
                q_type = q.question_type or "unknown"
                profile.optimal_question_types[q_type] = profile.optimal_question_types.get(q_type, 0) + 1
            
            # Extract patterns from rejected questions
            for q in rejected_questions:
                words = q.question_text.split()[:3]
                pattern = " ".join(words)
                profile.add_rejection_pattern(pattern)
            
            self.subject_profiles[str(subject.id)] = profile
    
    async def _analyze_difficulty_patterns(self, db: AsyncSession):
        """Analyze what makes questions easy/medium/hard in each subject."""
        subjects_result = await db.execute(select(Subject))
        subjects = subjects_result.scalars().all()
        
        for subject in subjects:
            profile = DifficultyProfile(str(subject.id))
            
            recent_date = datetime.utcnow() - timedelta(days=60)
            
            # Get questions with difficulty labels and approval status
            questions_result = await db.execute(
                select(Question, VettingLog)
                .join(VettingLog, Question.id == VettingLog.question_id)
                .where(
                    and_(
                        Question.subject_id == subject.id,
                        Question.difficulty_level.in_(["easy", "medium", "hard"]),
                        VettingLog.created_at >= recent_date
                    )
                )
            )
            results = questions_result.all()
            
            # Analyze patterns by difficulty
            difficulty_patterns = {"easy": [], "medium": [], "hard": []}
            
            for question, vetting in results:
                difficulty = question.difficulty_level
                success = vetting.decision == "approve"
                
                # Extract key phrases and indicators
                text = question.question_text.lower()
                
                # Question starters
                starters = ["what is", "name", "identify", "list", "explain", "describe", 
                           "compare", "analyze", "evaluate", "design", "synthesize"]
                
                for starter in starters:
                    if starter in text:
                        success_rate = 1.0 if success else 0.0
                        difficulty_patterns[difficulty].append((starter, success_rate))
                
                # Complexity indicators
                complexity_words = ["because", "since", "therefore", "however", "although", 
                                  "analyze", "evaluate", "synthesize", "create"]
                
                for word in complexity_words:
                    if word in text:
                        success_rate = 1.0 if success else 0.0
                        difficulty_patterns[difficulty].append((word, success_rate))
            
            # Add patterns to profile
            for difficulty, patterns in difficulty_patterns.items():
                # Group by pattern and calculate average success rate
                pattern_groups = defaultdict(list)
                for pattern, success_rate in patterns:
                    pattern_groups[pattern].append(success_rate)
                
                for pattern, rates in pattern_groups.items():
                    avg_success = sum(rates) / len(rates)
                    profile.add_pattern(difficulty, pattern, avg_success)
            
            self.difficulty_profiles[str(subject.id)] = profile
    
    async def _analyze_global_patterns(self, db: AsyncSession):
        """Analyze global patterns across all subjects."""
        recent_date = datetime.utcnow() - timedelta(days=30)
        
        # Get rejection reasons globally
        rejection_result = await db.execute(
            select(VettingLog.rejection_reasons)
            .where(VettingLog.decision == "reject")
            .where(VettingLog.created_at >= recent_date)
        )
        rejections = rejection_result.scalars().all()
        
        # Count rejection reasons
        reason_counter = Counter()
        for reasons in rejections:
            if reasons:
                for reason in reasons:
                    reason_counter[reason] += 1
        
        total_rejections = sum(reason_counter.values())
        self.global_patterns = {
            reason: count / total_rejections 
            for reason, count in reason_counter.items()
        }
    
    async def get_difficulty_guidance(
        self, 
        subject_id: str, 
        target_difficulty: str,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get guidance for generating questions at a specific difficulty level.
        
        Returns:
            {
                "recommended_starters": List[str],
                "avoid_patterns": List[str],
                "complexity_indicators": List[str],
                "topic_specific_tips": List[str],
                "confidence": float
            }
        """
        profile = self.difficulty_profiles.get(subject_id)
        if not profile:
            return {"confidence": 0.0, "message": "No profile available for subject"}
        
        # Get patterns for target difficulty
        target_patterns = getattr(profile, f"{target_difficulty}_patterns", [])
        
        # Sort by success rate
        target_patterns.sort(key=lambda x: x[1], reverse=True)
        
        # Get patterns that work well for this difficulty
        recommended_starters = [pattern for pattern, rate in target_patterns[:10] if rate > 0.7]
        
        # Get patterns to avoid (low success rates)
        avoid_patterns = [pattern for pattern, rate in target_patterns if rate < 0.3]
        
        # Complexity indicators based on difficulty
        complexity_indicators = []
        if target_difficulty == "easy":
            complexity_indicators = ["what is", "name", "identify", "list"]
        elif target_difficulty == "medium":
            complexity_indicators = ["explain", "describe", "compare", "analyze"]
        elif target_difficulty == "hard":
            complexity_indicators = ["evaluate", "synthesize", "design", "critique"]
        
        return {
            "recommended_starters": recommended_starters,
            "avoid_patterns": avoid_patterns,
            "complexity_indicators": complexity_indicators,
            "topic_specific_tips": [],  # Could be enhanced with topic analysis
            "confidence": len(target_patterns) / 50.0  # Simple confidence metric
        }
    
    async def validate_difficulty(
        self, 
        subject_id: str, 
        question_text: str, 
        intended_difficulty: str
    ) -> Dict[str, Any]:
        """
        Validate if a question matches its intended difficulty.
        
        Returns:
            {
                "predicted_difficulty": str,
                "confidence": float,
                "matches_intended": bool,
                "recommendations": List[str]
            }
        """
        profile = self.difficulty_profiles.get(subject_id)
        if not profile:
            return {"confidence": 0.0, "message": "No profile available"}
        
        predicted, confidence = profile.predict_difficulty(question_text)
        matches = predicted == intended_difficulty
        
        recommendations = []
        if not matches:
            recommendations.append(f"Question appears to be {predicted}, not {intended_difficulty}")
            
            # Suggest improvements
            if intended_difficulty == "easy" and predicted == "hard":
                recommendations.append("Consider using simpler question starters like 'What is' or 'Name'")
            elif intended_difficulty == "hard" and predicted == "easy":
                recommendations.append("Consider using analysis/evaluation starters like 'Analyze' or 'Evaluate'")
        
        return {
            "predicted_difficulty": predicted,
            "confidence": confidence,
            "matches_intended": matches,
            "recommendations": recommendations
        }
    
    async def get_subject_guidance(self, subject_id: str) -> Dict[str, Any]:
        """
        Get guidance for generating questions in a specific subject.
        
        Returns:
            {
                "successful_patterns": List[str],
                "patterns_to_avoid": List[str],
                "optimal_question_types": Dict[str, int],
                "common_mistakes": List[str],
                "topic_difficulty_mapping": Dict[str, str]
            }
        """
        profile = self.subject_profiles.get(subject_id)
        if not profile:
            return {"message": "No profile available for subject"}
        
        return {
            "successful_patterns": profile.approval_patterns[:20],
            "patterns_to_avoid": profile.rejection_patterns[:20],
            "optimal_question_types": profile.optimal_question_types,
            "common_mistakes": profile.common_mistakes,
            "topic_difficulty_mapping": profile.topic_difficulty_map
        }
    
    async def learn_from_vetting(self, question_id: uuid.UUID, vetting_log: VettingLog):
        """
        Update learning profiles based on new vetting feedback.
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get the question
                question_result = await db.execute(
                    select(Question).where(Question.id == question_id)
                )
                question = question_result.scalar_one_or_none()
                
                if not question:
                    return
                
                subject_id = str(question.subject_id)
                
                # Update subject profile
                if subject_id not in self.subject_profiles:
                    subject_result = await db.execute(
                        select(Subject).where(Subject.id == question.subject_id)
                    )
                    subject = subject_result.scalar_one_or_none()
                    if subject:
                        self.subject_profiles[subject_id] = SubjectProfile(subject_id, subject.name)
                
                subject_profile = self.subject_profiles[subject_id]
                
                # Add patterns based on outcome
                words = question.question_text.split()[:3]
                pattern = " ".join(words)
                
                if vetting_log.decision == "approve":
                    subject_profile.add_approval_pattern(pattern)
                    
                    # Update optimal question types
                    q_type = question.question_type or "unknown"
                    subject_profile.optimal_question_types[q_type] = \
                        subject_profile.optimal_question_types.get(q_type, 0) + 1
                        
                elif vetting_log.decision == "reject":
                    subject_profile.add_rejection_pattern(pattern)
                    
                    # Add to common mistakes if reasons provided
                    if vetting_log.rejection_reasons:
                        subject_profile.common_mistakes.extend(vetting_log.rejection_reasons)
                
                # Periodically re-analyze patterns
                if datetime.utcnow() - (self.last_update or datetime.utcnow()) > timedelta(hours=6):
                    await self._load_profiles()
                    
        except Exception as e:
            logger.error(f"Failed to learn from vetting: {e}")
    
    async def get_generation_prompt_enhancement(
        self, 
        subject_id: str, 
        difficulty: str, 
        topic: Optional[str] = None
    ) -> str:
        """
        Get prompt enhancements based on learned patterns.
        
        Returns additional context to add to generation prompts.
        """
        subject_guidance = await self.get_subject_guidance(subject_id)
        difficulty_guidance = await self.get_difficulty_guidance(subject_id, difficulty, topic)
        
        enhancements = []
        
        # Add subject-specific guidance
        if subject_guidance.get("successful_patterns"):
            patterns = ", ".join(subject_guidance["successful_patterns"][:5])
            enhancements.append(f"Questions that start with: {patterns}")
        
        # Add difficulty-specific guidance
        if difficulty_guidance.get("recommended_starters"):
            starters = ", ".join(difficulty_guidance["recommended_starters"][:3])
            enhancements.append(f"Use question starters like: {starters}")
        
        # Add things to avoid
        avoid_patterns = []
        if subject_guidance.get("patterns_to_avoid"):
            avoid_patterns.extend(subject_guidance["patterns_to_avoid"][:3])
        if difficulty_guidance.get("avoid_patterns"):
            avoid_patterns.extend(difficulty_guidance["avoid_patterns"][:3])
        
        if avoid_patterns:
            avoid_text = ", ".join(avoid_patterns)
            enhancements.append(f"Avoid patterns like: {avoid_text}")
        
        if enhancements:
            return "\n\nLearned Guidelines:\n" + "\n".join(f"- {e}" for e in enhancements)
        else:
            return ""

# Global instance
adaptive_learning_service = AdaptiveLearningService()
