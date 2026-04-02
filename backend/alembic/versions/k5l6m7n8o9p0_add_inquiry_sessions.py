"""add inquiry sessions

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-04-02 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'k5l6m7n8o9p0'
down_revision = 'j4k5l6m7n8o9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'inquiry_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('subject_id', sa.String(length=36), nullable=False),
        sa.Column('topic_id', sa.String(length=36), nullable=True),
        sa.Column('current_level', sa.String(length=20), nullable=False, server_default='beginner'),
        sa.Column('completed_turns_by_level', sa.JSON(), nullable=True),
        sa.Column('messages', sa.JSON(), nullable=True),
        sa.Column('current_phase', sa.String(length=30), nullable=False, server_default='awaiting-answer'),
        sa.Column('current_question_attempt', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_complete', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inquiry_sessions_user_id', 'inquiry_sessions', ['user_id'])
    op.create_index('ix_inquiry_sessions_subject_id', 'inquiry_sessions', ['subject_id'])
    op.create_index('ix_inquiry_sessions_is_active', 'inquiry_sessions', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_inquiry_sessions_is_active', table_name='inquiry_sessions')
    op.drop_index('ix_inquiry_sessions_subject_id', table_name='inquiry_sessions')
    op.drop_index('ix_inquiry_sessions_user_id', table_name='inquiry_sessions')
    op.drop_table('inquiry_sessions')
