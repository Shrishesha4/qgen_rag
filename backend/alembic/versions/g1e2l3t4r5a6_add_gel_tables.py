"""Add GEL (Graded Error Learning) tables

Revision ID: g1e2l3t4r5a6
Revises: cd754e1f4b40
Create Date: 2026-03-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.core.types import UUIDString

# revision identifiers, used by Alembic.
revision: str = 'g1e2l3t4r5a6'
down_revision: Union[str, None] = 'cd754e1f4b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create gel_evaluation_items table
    op.create_table(
        'gel_evaluation_items',
        sa.Column('id', UUIDString(), primary_key=True),
        sa.Column('question_id', UUIDString(), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subject_id', UUIDString(), sa.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('topic_id', UUIDString(), sa.ForeignKey('topics.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='draft'),
        sa.Column('difficulty_label', sa.String(20), nullable=True),
        sa.Column('bloom_level', sa.String(30), nullable=True),
        sa.Column('known_issues', postgresql.JSONB, nullable=True),
        sa.Column('expected_detection_count', sa.Integer, nullable=True),
        sa.Column('is_control_item', sa.Boolean, default=False),
        sa.Column('control_type', sa.String(20), nullable=True),
        sa.Column('rubric_id', UUIDString(), sa.ForeignKey('rubrics.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(36), nullable=True),
    )
    op.create_index('ix_gel_eval_items_status', 'gel_evaluation_items', ['status'])
    op.create_index('ix_gel_eval_items_subject', 'gel_evaluation_items', ['subject_id'])
    op.create_index('ix_gel_eval_items_topic', 'gel_evaluation_items', ['topic_id'])

    # Create gel_assignments table
    op.create_table(
        'gel_assignments',
        sa.Column('id', UUIDString(), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('subject_id', UUIDString(), sa.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('topic_id', UUIDString(), sa.ForeignKey('topics.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cohort', sa.String(100), nullable=True),
        sa.Column('grade', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='draft'),
        sa.Column('scheduled_start', sa.DateTime, nullable=True),
        sa.Column('scheduled_end', sa.DateTime, nullable=True),
        sa.Column('actual_start', sa.DateTime, nullable=True),
        sa.Column('actual_end', sa.DateTime, nullable=True),
        sa.Column('max_attempts_per_item', sa.Integer, default=1),
        sa.Column('time_limit_minutes', sa.Integer, nullable=True),
        sa.Column('shuffle_items', sa.Boolean, default=True),
        sa.Column('show_feedback_immediately', sa.Boolean, default=False),
        sa.Column('rubric_id', UUIDString(), sa.ForeignKey('rubrics.id', ondelete='SET NULL'), nullable=True),
        sa.Column('passing_score', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(36), nullable=True),
    )
    op.create_index('ix_gel_assignments_status', 'gel_assignments', ['status'])
    op.create_index('ix_gel_assignments_cohort', 'gel_assignments', ['cohort'])
    op.create_index('ix_gel_assignments_dates', 'gel_assignments', ['scheduled_start', 'scheduled_end'])

    # Create gel_assignment_items junction table
    op.create_table(
        'gel_assignment_items',
        sa.Column('id', UUIDString(), primary_key=True),
        sa.Column('assignment_id', UUIDString(), sa.ForeignKey('gel_assignments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evaluation_item_id', UUIDString(), sa.ForeignKey('gel_evaluation_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sequence_number', sa.Integer, default=0),
        sa.Column('weight', sa.Float, default=1.0),
        sa.Column('time_limit_override', sa.Integer, nullable=True),
    )
    op.create_index('ix_gel_assignment_items_assignment', 'gel_assignment_items', ['assignment_id'])
    op.create_unique_constraint('uq_assignment_item', 'gel_assignment_items', ['assignment_id', 'evaluation_item_id'])

    # Create gel_student_attempts table
    op.create_table(
        'gel_student_attempts',
        sa.Column('id', UUIDString(), primary_key=True),
        sa.Column('student_id', sa.String(36), nullable=False),
        sa.Column('evaluation_item_id', UUIDString(), sa.ForeignKey('gel_evaluation_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assignment_id', UUIDString(), sa.ForeignKey('gel_assignments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('attempt_number', sa.Integer, default=1),
        sa.Column('status', sa.String(20), nullable=False, default='not_started'),
        sa.Column('has_issues_detected', sa.Boolean, nullable=True),
        sa.Column('reasoning_text', sa.Text, nullable=True),
        sa.Column('correction_text', sa.Text, nullable=True),
        sa.Column('confidence_score', sa.Float, nullable=True),
        sa.Column('is_draft', sa.Boolean, default=True),
        sa.Column('draft_data', postgresql.JSONB, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('submitted_at', sa.DateTime, nullable=True),
        sa.Column('time_spent_seconds', sa.Integer, nullable=True),
        sa.Column('total_score', sa.Float, nullable=True),
        sa.Column('score_breakdown', postgresql.JSONB, nullable=True),
        sa.Column('scored_at', sa.DateTime, nullable=True),
        sa.Column('scored_by', sa.String(50), nullable=True),
        sa.Column('reviewed_at', sa.DateTime, nullable=True),
        sa.Column('reviewed_by', sa.String(36), nullable=True),
        sa.Column('review_notes', sa.Text, nullable=True),
        sa.Column('score_override', sa.Float, nullable=True),
        sa.Column('feedback_text', sa.Text, nullable=True),
        sa.Column('feedback_shown_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_gel_attempts_student', 'gel_student_attempts', ['student_id'])
    op.create_index('ix_gel_attempts_item', 'gel_student_attempts', ['evaluation_item_id'])
    op.create_index('ix_gel_attempts_assignment', 'gel_student_attempts', ['assignment_id'])
    op.create_index('ix_gel_attempts_status', 'gel_student_attempts', ['status'])
    op.create_unique_constraint('uq_student_attempt', 'gel_student_attempts', 
                                ['student_id', 'evaluation_item_id', 'assignment_id', 'attempt_number'])

    # Create gel_attempt_issues table
    op.create_table(
        'gel_attempt_issues',
        sa.Column('id', UUIDString(), primary_key=True),
        sa.Column('attempt_id', UUIDString(), sa.ForeignKey('gel_student_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), default='moderate'),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('location_start', sa.Integer, nullable=True),
        sa.Column('location_end', sa.Integer, nullable=True),
        sa.Column('location_field', sa.String(50), nullable=True),
        sa.Column('is_valid', sa.Boolean, nullable=True),
        sa.Column('validation_notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('ix_gel_issues_attempt', 'gel_attempt_issues', ['attempt_id'])
    op.create_index('ix_gel_issues_category', 'gel_attempt_issues', ['category'])

    # Create gel_attempt_scores table
    op.create_table(
        'gel_attempt_scores',
        sa.Column('id', UUIDString(), primary_key=True),
        sa.Column('attempt_id', UUIDString(), sa.ForeignKey('gel_student_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dimension', sa.String(50), nullable=False),
        sa.Column('raw_score', sa.Float, nullable=False),
        sa.Column('max_score', sa.Float, nullable=False),
        sa.Column('weighted_score', sa.Float, nullable=False),
        sa.Column('weight', sa.Float, default=1.0),
        sa.Column('scoring_notes', sa.Text, nullable=True),
        sa.Column('scoring_metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('ix_gel_scores_attempt', 'gel_attempt_scores', ['attempt_id'])
    op.create_unique_constraint('uq_attempt_dimension', 'gel_attempt_scores', ['attempt_id', 'dimension'])

    # Create gel_attempt_events table
    op.create_table(
        'gel_attempt_events',
        sa.Column('id', UUIDString(), primary_key=True),
        sa.Column('attempt_id', UUIDString(), sa.ForeignKey('gel_student_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', postgresql.JSONB, nullable=True),
        sa.Column('actor_id', sa.String(36), nullable=True),
        sa.Column('actor_type', sa.String(20), default='student'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )
    op.create_index('ix_gel_events_attempt', 'gel_attempt_events', ['attempt_id'])
    op.create_index('ix_gel_events_type', 'gel_attempt_events', ['event_type'])
    op.create_index('ix_gel_events_created', 'gel_attempt_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('gel_attempt_events')
    op.drop_table('gel_attempt_scores')
    op.drop_table('gel_attempt_issues')
    op.drop_table('gel_student_attempts')
    op.drop_table('gel_assignment_items')
    op.drop_table('gel_assignments')
    op.drop_table('gel_evaluation_items')
