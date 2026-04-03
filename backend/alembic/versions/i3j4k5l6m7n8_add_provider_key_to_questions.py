"""Add provider_key column to questions table for tracking which provider generated each question.

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-04-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i3j4k5l6m7n8'
down_revision = '9aaddae6699d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add provider_key column to track which LLM provider generated the question
    from sqlalchemy import inspect
    from alembic import op as alembic_op
    bind = alembic_op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('questions')]

    if 'provider_key' not in columns:
        op.add_column(
            'questions',
            sa.Column('provider_key', sa.String(60), nullable=True)
        )

    # Create index for provider-based queries
    indexes = [idx['name'] for idx in inspector.get_indexes('questions')]
    if 'ix_questions_provider_key' not in indexes:
        op.create_index('ix_questions_provider_key', 'questions', ['provider_key'])


def downgrade() -> None:
    op.drop_index('ix_questions_provider_key', table_name='questions')
    op.drop_column('questions', 'provider_key')
