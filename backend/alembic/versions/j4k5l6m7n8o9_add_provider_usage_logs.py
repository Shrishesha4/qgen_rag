"""Add provider_usage_logs table for tracking non-question-generation provider usage.

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-04-03 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j4k5l6m7n8o9'
down_revision = 'i3j4k5l6m7n8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'provider_usage_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('provider_key', sa.String(length=60), nullable=False),
        sa.Column('provider_name', sa.String(length=100), nullable=True),
        sa.Column('provider_model', sa.String(length=100), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('subject_id', sa.String(length=36), nullable=True),
        sa.Column('topic_id', sa.String(length=36), nullable=True),
        sa.Column('usage_type', sa.String(length=50), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=True),
        sa.Column('usage_metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_provider_usage_logs_provider_key'), 'provider_usage_logs', ['provider_key'], unique=False)
    op.create_index(op.f('ix_provider_usage_logs_user_id'), 'provider_usage_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_provider_usage_logs_subject_id'), 'provider_usage_logs', ['subject_id'], unique=False)
    op.create_index(op.f('ix_provider_usage_logs_usage_type'), 'provider_usage_logs', ['usage_type'], unique=False)
    op.create_index(op.f('ix_provider_usage_logs_session_id'), 'provider_usage_logs', ['session_id'], unique=False)
    op.create_index(op.f('ix_provider_usage_logs_created_at'), 'provider_usage_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_provider_usage_logs_created_at'), table_name='provider_usage_logs')
    op.drop_index(op.f('ix_provider_usage_logs_session_id'), table_name='provider_usage_logs')
    op.drop_index(op.f('ix_provider_usage_logs_usage_type'), table_name='provider_usage_logs')
    op.drop_index(op.f('ix_provider_usage_logs_subject_id'), table_name='provider_usage_logs')
    op.drop_index(op.f('ix_provider_usage_logs_user_id'), table_name='provider_usage_logs')
    op.drop_index(op.f('ix_provider_usage_logs_provider_key'), table_name='provider_usage_logs')
    op.drop_table('provider_usage_logs')
