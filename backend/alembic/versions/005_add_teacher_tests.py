"""Add teacher tests tables

Revision ID: 005_add_teacher_tests
Revises: e3871e9f4ef3
Create Date: 2026-03-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_teacher_tests'
down_revision = 'e3871e9f4ef3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tests table
    op.create_table(
        'tests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subject_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('instructions', sa.Text, nullable=True),
        sa.Column('generation_type', sa.String(30), server_default='subject_wise'),
        sa.Column('difficulty_config', postgresql.JSONB, nullable=True),
        sa.Column('topic_config', postgresql.JSONB, nullable=True),
        sa.Column('total_questions', sa.Integer, server_default='0'),
        sa.Column('total_marks', sa.Integer, server_default='0'),
        sa.Column('duration_minutes', sa.Integer, nullable=True),
        sa.Column('status', sa.String(20), server_default='draft'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unpublished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_tests_teacher_id', 'tests', ['teacher_id'])
    op.create_index('ix_tests_subject_id', 'tests', ['subject_id'])
    op.create_index('ix_tests_status', 'tests', ['status'])

    # Test Questions table
    op.create_table(
        'test_questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('test_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('order_index', sa.Integer, server_default='0'),
        sa.Column('marks', sa.Integer, server_default='1'),
        sa.Column('question_text_override', sa.Text, nullable=True),
        sa.Column('options_override', postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column('correct_answer_override', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('test_id', 'question_id', name='uq_test_question'),
    )
    op.create_index('ix_test_questions_test_id', 'test_questions', ['test_id'])

    # Test Submissions table
    op.create_table(
        'test_submissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('test_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score', sa.Integer, server_default='0'),
        sa.Column('total_marks', sa.Integer, server_default='0'),
        sa.Column('percentage', sa.Float, server_default='0.0'),
        sa.Column('answers', postgresql.JSONB, nullable=True),
        sa.Column('time_taken_seconds', sa.Integer, nullable=True),
        sa.Column('status', sa.String(20), server_default='in_progress'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('test_id', 'student_id', name='uq_test_student_submission'),
    )
    op.create_index('ix_test_submissions_test_id', 'test_submissions', ['test_id'])
    op.create_index('ix_test_submissions_student_id', 'test_submissions', ['student_id'])


def downgrade() -> None:
    op.drop_table('test_submissions')
    op.drop_table('test_questions')
    op.drop_table('tests')
