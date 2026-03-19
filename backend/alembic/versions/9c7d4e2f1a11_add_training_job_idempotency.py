"""add training job idempotency and replay lineage

Revision ID: 9c7d4e2f1a11
Revises: f1a2b3c4d5e6
Create Date: 2026-03-20
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "9c7d4e2f1a11"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def table_exists(table_name: str) -> bool:
        return table_name in inspector.get_table_names()

    def column_exists(table_name: str, column_name: str) -> bool:
        if not table_exists(table_name):
            return False
        return any(c["name"] == column_name for c in inspector.get_columns(table_name))

    def index_exists(table_name: str, index_name: str) -> bool:
        if not table_exists(table_name):
            return False
        return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))

    def foreign_key_exists(table_name: str, constrained_columns: list[str]) -> bool:
        if not table_exists(table_name):
            return False
        normalized = sorted(constrained_columns)
        return any(
            sorted(fk.get("constrained_columns") or []) == normalized
            for fk in inspector.get_foreign_keys(table_name)
        )

    if not column_exists("training_jobs", "idempotency_key"):
        op.add_column(
            "training_jobs",
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        )
    if not column_exists("training_jobs", "replayed_from_job_id"):
        op.add_column(
            "training_jobs",
            sa.Column("replayed_from_job_id", UUID(as_uuid=True), nullable=True),
        )
        inspector = sa.inspect(bind)

    if not foreign_key_exists("training_jobs", ["replayed_from_job_id"]):
        op.create_foreign_key(
            "fk_training_jobs_replayed_from_job_id_training_jobs",
            "training_jobs",
            "training_jobs",
            ["replayed_from_job_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not index_exists("training_jobs", "ix_training_jobs_idempotency_key"):
        op.create_index(
            "ix_training_jobs_idempotency_key",
            "training_jobs",
            ["idempotency_key"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_training_jobs_idempotency_key", table_name="training_jobs")
    op.drop_constraint(
        "fk_training_jobs_replayed_from_job_id_training_jobs",
        "training_jobs",
        type_="foreignkey",
    )
    op.drop_column("training_jobs", "replayed_from_job_id")
    op.drop_column("training_jobs", "idempotency_key")
