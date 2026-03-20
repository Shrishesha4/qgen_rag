"""reconcile questions and generation_sessions schema drift

Revision ID: c7a1f6e9a005
Revises: c7a1f6e9a004
Create Date: 2026-03-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c7a1f6e9a005"
down_revision: Union[str, None] = "c7a1f6e9a004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def upgrade() -> None:
    # questions table: bring live schema in sync with ORM fields used by API responses.
    if not _column_exists("questions", "course_outcome_mapping"):
        op.add_column("questions", sa.Column("course_outcome_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    if not _column_exists("questions", "learning_outcome_id"):
        op.add_column("questions", sa.Column("learning_outcome_id", sa.String(length=50), nullable=True))

    if not _column_exists("questions", "vetting_notes"):
        op.add_column("questions", sa.Column("vetting_notes", sa.Text(), nullable=True))
        # Backfill from legacy column name used in older migrations.
        op.execute("UPDATE questions SET vetting_notes = vetting_comments WHERE vetting_notes IS NULL")

    if not _column_exists("questions", "user_difficulty_rating"):
        op.add_column("questions", sa.Column("user_difficulty_rating", sa.String(length=20), nullable=True))

    if not _column_exists("questions", "user_answer"):
        op.add_column("questions", sa.Column("user_answer", sa.Text(), nullable=True))

    if not _column_exists("questions", "answer_correctness"):
        op.add_column("questions", sa.Column("answer_correctness", sa.Boolean(), nullable=True))

    if not _column_exists("questions", "last_shown_at"):
        op.add_column("questions", sa.Column("last_shown_at", sa.DateTime(timezone=True), nullable=True))

    if not _column_exists("questions", "generation_metadata"):
        op.add_column("questions", sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # generation_sessions table has this ORM field but older DBs may miss it.
    if not _column_exists("generation_sessions", "generation_config"):
        op.add_column("generation_sessions", sa.Column("generation_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Keep downgrade conservative and reversible for drift-only columns.
    if _column_exists("generation_sessions", "generation_config"):
        op.drop_column("generation_sessions", "generation_config")

    if _column_exists("questions", "generation_metadata"):
        op.drop_column("questions", "generation_metadata")

    if _column_exists("questions", "last_shown_at"):
        op.drop_column("questions", "last_shown_at")

    if _column_exists("questions", "answer_correctness"):
        op.drop_column("questions", "answer_correctness")

    if _column_exists("questions", "user_answer"):
        op.drop_column("questions", "user_answer")

    if _column_exists("questions", "user_difficulty_rating"):
        op.drop_column("questions", "user_difficulty_rating")

    if _column_exists("questions", "vetting_notes"):
        op.drop_column("questions", "vetting_notes")

    if _column_exists("questions", "learning_outcome_id"):
        op.drop_column("questions", "learning_outcome_id")

    if _column_exists("questions", "course_outcome_mapping"):
        op.drop_column("questions", "course_outcome_mapping")
