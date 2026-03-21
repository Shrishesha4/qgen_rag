"""reconcile subject/topic schema with ORM models

Revision ID: c7a1f6e9a001
Revises: b3e8f7a2c519
Create Date: 2026-03-20
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "c7a1f6e9a001"
down_revision: Union[str, None] = "b3e8f7a2c519"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    fks = inspector.get_foreign_keys(table_name)
    return any(fk.get("name") == constraint_name for fk in fks)


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    # ---- subjects table reconciliation ----
    if _table_exists("subjects"):
        if not _column_exists("subjects", "code"):
            op.add_column("subjects", sa.Column("code", sa.String(length=50), nullable=True))
            # Backfill for existing rows.
            op.execute(
                """
                UPDATE subjects
                SET code = COALESCE(
                    NULLIF(SUBSTRING(REGEXP_REPLACE(UPPER(name), '[^A-Z0-9]+', '', 'g') FROM 1 FOR 50), ''),
                    'SUBJ-' || SUBSTRING(id FROM 1 FOR 8)
                )
                WHERE code IS NULL
                """
            )
            op.alter_column("subjects", "code", existing_type=sa.String(length=50), nullable=False)

        if not _column_exists("subjects", "learning_outcomes"):
            op.add_column("subjects", sa.Column("learning_outcomes", JSONB(), nullable=True))

        if not _column_exists("subjects", "course_outcomes"):
            op.add_column("subjects", sa.Column("course_outcomes", JSONB(), nullable=True))

        if not _column_exists("subjects", "total_questions"):
            op.add_column(
                "subjects",
                sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
            )

        if not _column_exists("subjects", "total_topics"):
            op.add_column(
                "subjects",
                sa.Column("total_topics", sa.Integer(), nullable=False, server_default="0"),
            )

        if not _column_exists("subjects", "syllabus_coverage"):
            op.add_column(
                "subjects",
                sa.Column("syllabus_coverage", sa.Integer(), nullable=False, server_default="0"),
            )

    # ---- topics table (missing in older baselines) ----
    if not _table_exists("topics"):
        op.create_table(
            "topics",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("subject_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("has_syllabus", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("syllabus_content", sa.Text(), nullable=True),
            sa.Column("syllabus_file_path", sa.String(length=500), nullable=True),
            sa.Column("learning_outcome_mappings", JSONB(), nullable=True),
            sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _constraint_exists("topics", "topics_subject_id_fkey"):
        op.create_foreign_key(
            "topics_subject_id_fkey",
            "topics",
            "subjects",
            ["subject_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if not _index_exists("topics", "ix_topics_subject_id"):
        op.create_index("ix_topics_subject_id", "topics", ["subject_id"], unique=False)

    # ---- questions table reconciliation for subject/topic-aware flows ----
    if _table_exists("questions"):
        if not _column_exists("questions", "subject_id"):
            op.add_column("questions", sa.Column("subject_id", sa.String(length=36), nullable=True))
        if not _column_exists("questions", "topic_id"):
            op.add_column("questions", sa.Column("topic_id", sa.String(length=36), nullable=True))

        if not _constraint_exists("questions", "questions_subject_id_fkey"):
            op.create_foreign_key(
                "questions_subject_id_fkey",
                "questions",
                "subjects",
                ["subject_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if _table_exists("topics") and not _constraint_exists("questions", "questions_topic_id_fkey"):
            op.create_foreign_key(
                "questions_topic_id_fkey",
                "questions",
                "topics",
                ["topic_id"],
                ["id"],
                ondelete="SET NULL",
            )

        if not _index_exists("questions", "ix_questions_subject_id"):
            op.create_index("ix_questions_subject_id", "questions", ["subject_id"], unique=False)
        if not _index_exists("questions", "ix_questions_topic_id"):
            op.create_index("ix_questions_topic_id", "questions", ["topic_id"], unique=False)


def downgrade() -> None:
    # Intentionally conservative: do not drop reconciled columns/tables automatically.
    # This migration is a repair bridge for schema drift across environments.
    pass
