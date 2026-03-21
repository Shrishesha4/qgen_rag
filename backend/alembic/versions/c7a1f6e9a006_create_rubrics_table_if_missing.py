"""create rubrics table if missing

Revision ID: c7a1f6e9a006
Revises: c7a1f6e9a005
Create Date: 2026-03-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "c7a1f6e9a006"
down_revision: Union[str, None] = "c7a1f6e9a005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _fk_exists(table_name: str, constrained_columns: list[str], referred_table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("referred_table") == referred_table and fk.get("constrained_columns") == constrained_columns:
            return True
    return False


def upgrade() -> None:
    if not _table_exists("rubrics"):
        op.create_table(
            "rubrics",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("subject_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("exam_type", sa.String(length=50), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="180"),
            sa.Column("question_type_distribution", JSONB(), nullable=False),
            sa.Column("learning_outcomes_distribution", JSONB(), nullable=False),
            sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_marks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _fk_exists("rubrics", ["subject_id"], "subjects"):
        op.create_foreign_key(
            "fk_rubrics_subject_id_subjects",
            "rubrics",
            "subjects",
            ["subject_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if not _index_exists("rubrics", "ix_rubrics_user_id"):
        op.create_index("ix_rubrics_user_id", "rubrics", ["user_id"], unique=False)

    if not _index_exists("rubrics", "ix_rubrics_subject_id"):
        op.create_index("ix_rubrics_subject_id", "rubrics", ["subject_id"], unique=False)


def downgrade() -> None:
    # Repair migration: conservative no-op downgrade.
    pass
