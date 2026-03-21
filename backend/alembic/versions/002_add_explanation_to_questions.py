"""add_explanation_to_questions

Revision ID: 002_add_explanation
Revises: 001_initial
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_explanation'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def upgrade() -> None:
    # Add explanation column to questions table
    if not _column_exists('questions', 'explanation'):
        op.add_column('questions', sa.Column('explanation', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove explanation column from questions table
    op.drop_column('questions', 'explanation')
