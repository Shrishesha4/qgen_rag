#!/usr/bin/env python
"""
Data Collection Initialization Script

This script helps initialize the system with sample data and
sets up the initial training pipeline for the SLM/LLM system.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.models.topic import Topic
from app.models.document import Document
from app.models.training import VettingReasonCode
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCollectionInitializer:
    """
    Initialize the system with sample data for training pipeline.
    
    This creates:
    - Sample subjects and topics
    - Initial vetting reason codes
    - Sample documents (if provided)
    - System configuration for training
    """
    
    def __init__(self):
        self.sample_subjects = [
            {
                "name": "Biology",
                "description": "Study of living organisms and life processes",
                "topics": [
                    {"name": "Cell Biology", "description": "Structure and function of cells"},
                    {"name": "Genetics", "description": "Heredity and variation in organisms"},
                    {"name": "Evolution", "description": "Change in species over time"},
                    {"name": "Ecology", "description": "Interactions between organisms and environment"},
                    {"name": "Human Anatomy", "description": "Structure of human body"},
                ]
            },
            {
                "name": "Computer Science",
                "description": "Study of computation and information processing",
                "topics": [
                    {"name": "Data Structures", "description": "Organization and storage of data"},
                    {"name": "Algorithms", "description": "Problem-solving procedures"},
                    {"name": "Machine Learning", "description": "Systems that learn from data"},
                    {"name": "Database Systems", "description": "Data management and retrieval"},
                    {"name": "Computer Networks", "description": "Communication between computers"},
                ]
            },
            {
                "name": "Physics",
                "description": "Study of matter, energy, and their interactions",
                "topics": [
                    {"name": "Mechanics", "description": "Motion and forces"},
                    {"name": "Thermodynamics", "description": "Heat and energy transfer"},
                    {"name": "Electromagnetism", "description": "Electric and magnetic phenomena"},
                    {"name": "Quantum Physics", "description": "Behavior at atomic scale"},
                    {"name": "Relativity", "description": "Space, time, and gravity"},
                ]
            },
            {
                "name": "Mathematics",
                "description": "Study of numbers, quantities, and shapes",
                "topics": [
                    {"name": "Calculus", "description": "Continuous change and limits"},
                    {"name": "Linear Algebra", "description": "Vector spaces and linear mappings"},
                    {"name": "Probability", "description": "Study of uncertainty"},
                    {"name": "Statistics", "description": "Data analysis and interpretation"},
                    {"name": "Discrete Mathematics", "description": "Mathematical structures"},
                ]
            },
            {
                "name": "Chemistry",
                "description": "Study of matter and its properties",
                "topics": [
                    {"name": "Organic Chemistry", "description": "Carbon-based compounds"},
                    {"name": "Inorganic Chemistry", "description": "Non-organic compounds"},
                    {"name": "Physical Chemistry", "description": "Physical properties of molecules"},
                    {"name": "Analytical Chemistry", "description": "Composition analysis"},
                    {"name": "Biochemistry", "description": "Chemical processes in living organisms"},
                ]
            }
        ]
        
        self.vetting_reasons = [
            # Content quality issues
            {"code": "unclear_question", "label": "Unclear Question", "severity": "major"},
            {"code": "ambiguous_answer", "label": "Ambiguous Answer", "severity": "major"},
            {"code": "incorrect_answer", "label": "Incorrect Answer", "severity": "critical"},
            {"code": "incomplete_question", "label": "Incomplete Question", "severity": "major"},
            {"code": "multiple_questions", "label": "Multiple Questions", "severity": "minor"},
            
            # Difficulty issues
            {"code": "wrong_difficulty", "label": "Wrong Difficulty Level", "severity": "minor"},
            {"code": "too_easy", "label": "Too Easy for Level", "severity": "minor"},
            {"code": "too_hard", "label": "Too Hard for Level", "severity": "minor"},
            
            # Educational value
            {"code": "not_educational", "label": "Not Educational", "severity": "major"},
            {"code": "trivial_content", "label": "Trivial Content", "severity": "minor"},
            {"code": "off_topic", "label": "Off Topic", "severity": "major"},
            
            # Formatting issues
            {"code": "grammar_error", "label": "Grammar Error", "severity": "minor"},
            {"code": "spelling_error", "label": "Spelling Error", "severity": "minor"},
            {"code": "poor_formatting", "label": "Poor Formatting", "severity": "minor"},
            {"code": "mcq_options_invalid", "label": "Invalid MCQ Options", "severity": "major"},
            
            # Technical issues
            {"code": "reference_missing", "label": "Reference Material Missing", "severity": "major"},
            {"code": "context_insufficient", "label": "Insufficient Context", "severity": "major"},
            {"code": "answer_mismatch", "label": "Answer Doesn't Match Question", "severity": "critical"},
        ]
    
    async def initialize(self):
        """Initialize the system with sample data."""
        logger.info("Starting data collection initialization...")
        
        async with AsyncSessionLocal() as db:
            # Create vetting reason codes
            await self._create_vetting_reason_codes(db)
            
            # Create sample subjects and topics
            await self._create_subjects_and_topics(db)
            
            # Create initial system configuration
            await self._create_system_config(db)
            
            await db.commit()
        
        logger.info("Data collection initialization completed!")
    
    async def _create_vetting_reason_codes(self, db: AsyncSession):
        """Create initial vetting reason codes."""
        logger.info("Creating vetting reason codes...")
        
        for reason_data in self.vetting_reasons:
            # Check if already exists
            existing = await db.execute(
                select(VettingReasonCode).where(VettingReasonCode.code == reason_data["code"])
            )
            if existing.scalar_one_or_none():
                continue
            
            reason = VettingReasonCode(
                code=reason_data["code"],
                label=reason_data["label"],
                description=reason_data["label"],
                severity_default=reason_data["severity"],
                created_by="system"
            )
            db.add(reason)
        
        logger.info(f"Created {len(self.vetting_reasons)} vetting reason codes")
    
    async def _create_subjects_and_topics(self, db: AsyncSession):
        """Create sample subjects and topics."""
        logger.info("Creating subjects and topics...")
        
        for subject_data in self.sample_subjects:
            # Check if subject already exists
            existing = await db.execute(
                select(Subject).where(Subject.name == subject_data["name"])
            )
            if existing.scalar_one_or_none():
                continue
            
            # Create subject
            subject = Subject(
                name=subject_data["name"],
                description=subject_data["description"],
                created_by="system"
            )
            db.add(subject)
            await db.flush()  # Get the ID
            
            # Create topics
            for topic_data in subject_data["topics"]:
                topic = Topic(
                    name=topic_data["name"],
                    description=topic_data["description"],
                    subject_id=subject.id,
                    created_by="system"
                )
                db.add(topic)
        
        logger.info(f"Created {len(self.sample_subjects)} subjects with topics")
    
    async def _create_system_config(self, db: AsyncSession):
        """Create initial system configuration."""
        logger.info("Creating system configuration...")
        
        # This would create any initial configuration records
        # For now, we'll just log that this step was completed
        logger.info("System configuration completed")

class DataCollectionGuide:
    """
    Guide for ongoing data collection and training pipeline setup.
    """
    
    @staticmethod
    def get_data_collection_plan() -> Dict[str, Any]:
        """Get comprehensive data collection plan."""
        return {
            "phase_1": {
                "name": "Baseline Data Collection",
                "duration": "2-4 weeks",
                "targets": {
                    "total_questions": 5000,
                    "approved_questions": 2000,
                    "subjects_covered": 5,
                    "difficulty_levels": ["easy", "medium", "hard"],
                    "question_types": ["mcq", "short_answer", "long_answer"]
                },
                "daily_targets": {
                    "new_questions": 250,
                    "vetted_questions": 100,
                    "approved_questions": 50
                },
                "quality_metrics": {
                    "approval_rate_target": 0.4,  # 40% initial approval rate
                    "diversity_target": 0.8,      # 80% topic diversity
                    "difficulty_distribution": {
                        "easy": 0.33,
                        "medium": 0.34,
                        "hard": 0.33
                    }
                }
            },
            "phase_2": {
                "name": "Model Training Pipeline",
                "duration": "1-2 weeks",
                "activities": [
                    "SFT training on approved questions",
                    "DPO training on preference pairs",
                    "Model evaluation and validation",
                    "Model activation and deployment"
                ],
                "requirements": {
                    "min_approved_questions": 1000,
                    "min_preference_pairs": 500,
                    "diverse_subjects": 3
                }
            },
            "phase_3": {
                "name": "Continuous Improvement",
                "duration": "Ongoing",
                "activities": [
                    "Daily data collection",
                    "Weekly model updates",
                    "Monthly evaluation",
                    "Quarterly model promotion"
                ],
                "targets": {
                    "daily_vetting": 100,
                    "weekly_training": 1,
                    "monthly_improvement": "5% approval rate increase"
                }
            }
        }
    
    @staticmethod
    def get_training_workflow() -> Dict[str, Any]:
        """Get detailed training workflow."""
        return {
            "data_flow": {
                "generation": "Teachers generate questions using API",
                "vetting": "Students/experts review and provide feedback",
                "collection": "System collects all feedback data",
                "preparation": "Data is prepared for training",
                "training": "Models are fine-tuned on collected data",
                "deployment": "Improved models are deployed",
                "repeat": "Cycle continues with better generation"
            },
            "quality_gates": {
                "critique_filter": {
                    "threshold": 4.0,
                    "auto_reject_below": 2.0,
                    "description": "Constitutional AI filter before human vetting"
                },
                "human_vetting": {
                    "target_approval_rate": 0.8,
                    "min_vetters_per_question": 2,
                    "description": "Human quality control"
                },
                "training_readiness": {
                    "min_samples": 1000,
                    "min_diversity": 0.7,
                    "description": "Minimum data quality for training"
                }
            },
            "adaptive_learning": {
                "difficulty_calibration": {
                    "mechanism": "Learn from vetter difficulty ratings",
                    "update_frequency": "daily",
                    "target_accuracy": 0.85
                },
                "subject_specialization": {
                    "mechanism": "Per-subject pattern learning",
                    "update_frequency": "weekly",
                    "target_improvement": "10% approval rate increase"
                },
                "feedback_integration": {
                    "mechanism": "Real-time pattern extraction",
                    "update_frequency": "continuous",
                    "target_response": "next generation cycle"
                }
            }
        }
    
    @staticmethod
    def get_monitoring_metrics() -> Dict[str, Any]:
        """Get monitoring metrics and targets."""
        return {
            "generation_metrics": {
                "questions_generated_per_day": {"target": 250, "warning": 100},
                "generation_success_rate": {"target": 0.95, "warning": 0.9},
                "average_generation_time": {"target": 2.0, "warning": 5.0},  # seconds
                "critique_pass_rate": {"target": 0.7, "warning": 0.5}
            },
            "vetting_metrics": {
                "questions_vetted_per_day": {"target": 100, "warning": 50},
                "approval_rate": {"target": 0.8, "warning": 0.6},
                "average_vetting_time": {"target": 30, "warning": 60},  # seconds
                "vetter_participation": {"target": 10, "warning": 5}  # active vetters
            },
            "training_metrics": {
                "training_job_success_rate": {"target": 0.95, "warning": 0.8},
                "average_training_time": {"target": 4, "warning": 8},  # hours
                "model_improvement_rate": {"target": 0.05, "warning": 0.02},
                "gpu_utilization": {"target": 0.8, "warning": 0.5}
            },
            "quality_metrics": {
                "question_diversity_score": {"target": 0.8, "warning": 0.6},
                "difficulty_accuracy": {"target": 0.85, "warning": 0.7},
                "educational_value_score": {"target": 0.9, "warning": 0.7},
                "user_satisfaction": {"target": 4.0, "warning": 3.0}  # 1-5 scale
            }
        }

async def main():
    """Main initialization function."""
    print("🚀 QGen RAG Data Collection Initialization")
    print("=" * 50)
    
    # Initialize sample data
    initializer = DataCollectionInitializer()
    await initializer.initialize()
    
    # Get data collection plan
    guide = DataCollectionGuide()
    plan = guide.get_data_collection_plan()
    workflow = guide.get_training_workflow()
    metrics = guide.get_monitoring_metrics()
    
    print("\n📋 Data Collection Plan:")
    for phase_name, phase_data in plan.items():
        print(f"\n  {phase_name.replace('_', ' ').title()}:")
        print(f"    Name: {phase_data['name']}")
        print(f"    Duration: {phase_data['duration']}")
        if 'targets' in phase_data:
            print(f"    Targets: {phase_data['targets']}")
    
    print("\n🔄 Training Workflow:")
    print("  Data Flow:")
    for step, description in workflow['data_flow'].items():
        print(f"    {step.title()}: {description}")
    
    print("\n📊 Key Metrics to Monitor:")
    for category, metric_data in metrics.items():
        print(f"\n  {category.title()}:")
        for metric, targets in metric_data.items():
            print(f"    {metric}: {targets}")
    
    print("\n✅ Initialization Complete!")
    print("\n🎯 Next Steps:")
    print("1. Start the system: docker-compose -f docker-compose.dgx.yml up -d")
    print("2. Access the frontend: http://your-dgx-ip:5173")
    print("3. Create teacher and vetter accounts")
    print("4. Upload reference documents")
    print("5. Begin generating and vetting questions")
    print("6. Monitor progress in Grafana: http://your-dgx-ip:3000")
    
    print("\n📚 For detailed guidance, see: docs/DGX_SPARK_DEPLOYMENT.md")

if __name__ == "__main__":
    asyncio.run(main())
