"""add teacher vetting progress snapshots

Revision ID: c9f2e1a4b7d8
Revises: b3e8f7a2c519
Create Date: 2026-03-21
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "c9f2e1a4b7d8"
down_revision: Union[str, None] = "b3e8f7a2c519"
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return any(c["name"] == constraint_name for c in inspector.get_unique_constraints(table_name))


def foreign_key_exists(table_name: str, constrained_columns: list[str], referred_table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    normalized = sorted(constrained_columns)
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("referred_table") != referred_table:
            continue
        if sorted(fk.get("constrained_columns") or []) == normalized:
            return True
    return False


def upgrade() -> None:
    if not table_exists("teacher_vetting_progress"):
        op.create_table(
            "teacher_vetting_progress",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("progress_key", sa.String(length=255), nullable=False),
            sa.Column("subject_id", sa.String(length=36), nullable=False),
            sa.Column("topic_id", sa.String(length=36), nullable=True),
            sa.Column("mixed_topics_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("selected_mixed_topic_ids", JSONB(), nullable=True),
            sa.Column("generation_batch_size", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("allow_no_pdf_generation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("questions_snapshot", JSONB(), nullable=False),
            sa.Column("current_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("approved_question_ids", JSONB(), nullable=True),
            sa.Column("rejected_question_ids", JSONB(), nullable=True),
            sa.Column("batch_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not unique_constraint_exists("teacher_vetting_progress", "uq_teacher_vetting_progress_user_key"):
        op.create_unique_constraint(
            "uq_teacher_vetting_progress_user_key",
            "teacher_vetting_progress",
            ["user_id", "progress_key"],
        )

    if not index_exists("teacher_vetting_progress", "ix_teacher_vetting_progress_user_id"):
        op.create_index(
            "ix_teacher_vetting_progress_user_id",
            "teacher_vetting_progress",
            ["user_id"],
            unique=False,
        )

    if not index_exists("teacher_vetting_progress", "ix_teacher_vetting_progress_subject_id"):
        op.create_index(
            "ix_teacher_vetting_progress_subject_id",
            "teacher_vetting_progress",
            ["subject_id"],
            unique=False,
        )

    if not index_exists("teacher_vetting_progress", "ix_teacher_vetting_progress_topic_id"):
        op.create_index(
            "ix_teacher_vetting_progress_topic_id",
            "teacher_vetting_progress",
            ["topic_id"],
            unique=False,
        )

    if not index_exists("teacher_vetting_progress", "ix_teacher_vetting_progress_updated_at"):
        op.create_index(
            "ix_teacher_vetting_progress_updated_at",
            "teacher_vetting_progress",
            ["updated_at"],
            unique=False,
        )

    if not foreign_key_exists("teacher_vetting_progress", ["subject_id"], "subjects"):
        op.create_foreign_key(
            "fk_teacher_vetting_progress_subject_id",
            "teacher_vetting_progress",
            "subjects",
            ["subject_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if not foreign_key_exists("teacher_vetting_progress", ["topic_id"], "topics"):
        op.create_foreign_key(
            "fk_teacher_vetting_progress_topic_id",
            "teacher_vetting_progress",
            "topics",
            ["topic_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if table_exists("teacher_vetting_progress"):
        op.drop_table("teacher_vetting_progress")
