"""add model evaluation lifecycle and spot-check fields

Revision ID: b3e8f7a2c519
Revises: 9c7d4e2f1a11
Create Date: 2026-03-21
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "b3e8f7a2c519"
down_revision: Union[str, None] = "9c7d4e2f1a11"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    from sqlalchemy import inspect as sa_inspect

    bind = op.get_bind()
    inspector = sa_inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Evaluation lifecycle
    if not column_exists("model_evaluations", "eval_status"):
        op.add_column(
            "model_evaluations",
            sa.Column(
                "eval_status",
                sa.String(length=30),
                nullable=True,
                server_default="pending",
                comment="pending | running | completed | failed",
            ),
        )
    if not column_exists("model_evaluations", "completed_at"):
        op.add_column(
            "model_evaluations",
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not column_exists("model_evaluations", "error_message"):
        op.add_column(
            "model_evaluations",
            sa.Column("error_message", sa.Text(), nullable=True),
        )

    # Quality gate details
    if not column_exists("model_evaluations", "gate_checks"):
        op.add_column(
            "model_evaluations",
            sa.Column(
                "gate_checks",
                JSONB(),
                nullable=True,
                comment="Per-gate pass/fail breakdown",
            ),
        )

    # Spot-check workflow
    if not column_exists("model_evaluations", "spot_check_status"):
        op.add_column(
            "model_evaluations",
            sa.Column(
                "spot_check_status",
                sa.String(length=30),
                nullable=True,
                server_default="not_required",
                comment="not_required | pending | approved | rejected",
            ),
        )
    if not column_exists("model_evaluations", "spot_check_samples"):
        op.add_column(
            "model_evaluations",
            sa.Column(
                "spot_check_samples",
                JSONB(),
                nullable=True,
                comment="Sample question IDs selected for human review",
            ),
        )
    if not column_exists("model_evaluations", "spot_check_reviewed_by"):
        op.add_column(
            "model_evaluations",
            sa.Column("spot_check_reviewed_by", sa.String(length=36), nullable=True),
        )
    if not column_exists("model_evaluations", "spot_check_reviewed_at"):
        op.add_column(
            "model_evaluations",
            sa.Column("spot_check_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not column_exists("model_evaluations", "spot_check_notes"):
        op.add_column(
            "model_evaluations",
            sa.Column("spot_check_notes", sa.Text(), nullable=True),
        )

    # Lineage
    if not column_exists("model_evaluations", "evaluated_by"):
        op.add_column(
            "model_evaluations",
            sa.Column(
                "evaluated_by",
                sa.String(length=36),
                nullable=True,
                comment="User ID or 'system' for automated evaluations",
            ),
        )


def downgrade() -> None:
    for col in [
        "evaluated_by",
        "spot_check_notes",
        "spot_check_reviewed_at",
        "spot_check_reviewed_by",
        "spot_check_samples",
        "spot_check_status",
        "gate_checks",
        "error_message",
        "completed_at",
        "eval_status",
    ]:
        if column_exists("model_evaluations", col):
            op.drop_column("model_evaluations", col)
