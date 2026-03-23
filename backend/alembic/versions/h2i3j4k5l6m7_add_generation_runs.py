"""Add generation_runs table for persistent background generation tracking.

Revision ID: h2i3j4k5l6m7
Revises: f00fd388dd24
Create Date: 2026-03-23 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h2i3j4k5l6m7'
down_revision = 'f00fd388dd24'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'generation_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('subject_id', sa.String(36), sa.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('topic_id', sa.String(36), sa.ForeignKey('topics.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('in_progress', sa.Boolean(), server_default='true', index=True),
        sa.Column('current_question', sa.Integer(), server_default='0'),
        sa.Column('total_questions', sa.Integer(), server_default='0'),
        sa.Column('target_count', sa.Integer(), server_default='30'),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Create index for finding active runs by topic
    op.create_index('ix_generation_runs_topic_in_progress', 'generation_runs', ['topic_id', 'in_progress'])
    # Create index for finding active runs by subject
    op.create_index('ix_generation_runs_subject_in_progress', 'generation_runs', ['subject_id', 'in_progress'])


def downgrade() -> None:
    op.drop_index('ix_generation_runs_subject_in_progress', table_name='generation_runs')
    op.drop_index('ix_generation_runs_topic_in_progress', table_name='generation_runs')
    op.drop_table('generation_runs')
