"""add training quality registry and promotion tables

Revision ID: f1a2b3c4d5e6
Revises: 8f1b6e4c2a10
Create Date: 2026-03-13
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "8f1b6e4c2a10"
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

    def check_exists(table_name: str, check_name: str) -> bool:
        if not table_exists(table_name):
            return False
        return any(chk["name"] == check_name for chk in inspector.get_check_constraints(table_name))

    if not column_exists("vetting_logs", "review_version"):
        op.add_column(
            "vetting_logs",
            sa.Column("review_version", sa.Integer(), server_default="1", nullable=False),
        )
    if not column_exists("vetting_logs", "quality_score"):
        op.add_column("vetting_logs", sa.Column("quality_score", sa.Float(), nullable=True))
    if not column_exists("vetting_logs", "rubric_snapshot"):
        op.add_column("vetting_logs", sa.Column("rubric_snapshot", JSONB(), nullable=True))
    if not column_exists("vetting_logs", "reason_codes"):
        op.add_column("vetting_logs", sa.Column("reason_codes", ARRAY(sa.Text()), nullable=True))
    if not column_exists("vetting_logs", "severity_level"):
        op.add_column("vetting_logs", sa.Column("severity_level", sa.String(length=20), nullable=True))

    if not check_exists("vetting_logs", "ck_vetting_logs_quality_score_range"):
        op.create_check_constraint(
            "ck_vetting_logs_quality_score_range",
            "vetting_logs",
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)",
        )
    if not check_exists("vetting_logs", "ck_vetting_logs_severity_level_values"):
        op.create_check_constraint(
            "ck_vetting_logs_severity_level_values",
            "vetting_logs",
            "severity_level IS NULL OR severity_level IN ('minor', 'major', 'critical')",
        )

    if not column_exists("training_pairs", "dedupe_hash"):
        op.add_column("training_pairs", sa.Column("dedupe_hash", sa.String(length=64), nullable=True))
    if not column_exists("training_pairs", "pair_weight"):
        op.add_column(
            "training_pairs",
            sa.Column("pair_weight", sa.Float(), server_default="1.0", nullable=False),
        )
    if not column_exists("training_pairs", "language"):
        op.add_column(
            "training_pairs",
            sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
        )
    if not column_exists("training_pairs", "source_split"):
        op.add_column("training_pairs", sa.Column("source_split", sa.String(length=10), nullable=True))
    if not column_exists("training_pairs", "rejected_reason_codes"):
        op.add_column(
            "training_pairs",
            sa.Column("rejected_reason_codes", ARRAY(sa.Text()), nullable=True),
        )

    if not index_exists("training_pairs", "ix_training_pairs_dedupe_hash"):
        op.create_index(
            "ix_training_pairs_dedupe_hash",
            "training_pairs",
            ["dedupe_hash"],
            unique=True,
        )
    if not check_exists("training_pairs", "ck_training_pairs_source_split_values"):
        op.create_check_constraint(
            "ck_training_pairs_source_split_values",
            "training_pairs",
            "source_split IS NULL OR source_split IN ('train', 'val', 'test')",
        )

    if not table_exists("vetting_reason_codes"):
        op.create_table(
            "vetting_reason_codes",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("severity_default", sa.String(length=20), server_default="minor", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("code", name="uq_vetting_reason_codes_code"),
        )
        inspector = sa.inspect(bind)
    if not index_exists("vetting_reason_codes", "ix_vetting_reason_codes_code"):
        op.create_index("ix_vetting_reason_codes_code", "vetting_reason_codes", ["code"], unique=False)
    if not index_exists("vetting_reason_codes", "ix_vetting_reason_codes_created_at"):
        op.create_index("ix_vetting_reason_codes_created_at", "vetting_reason_codes", ["created_at"], unique=False)

    if not table_exists("training_datasets"):
        op.create_table(
            "training_datasets",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("dataset_tag", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("snapshot_filter", JSONB(), nullable=True),
            sa.Column("sample_counts", JSONB(), nullable=True),
            sa.Column("manifest_path", sa.String(length=500), nullable=True),
            sa.Column("checksum", sa.String(length=128), nullable=True),
            sa.UniqueConstraint("dataset_tag", name="uq_training_datasets_dataset_tag"),
        )
        inspector = sa.inspect(bind)
    if not index_exists("training_datasets", "ix_training_datasets_dataset_tag"):
        op.create_index("ix_training_datasets_dataset_tag", "training_datasets", ["dataset_tag"], unique=False)

    if not table_exists("model_evaluations"):
        op.create_table(
            "model_evaluations",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("model_version_id", UUID(as_uuid=True), sa.ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("dataset_tag", sa.String(length=100), nullable=False),
            sa.Column("eval_type", sa.String(length=50), nullable=False),
            sa.Column("metrics", JSONB(), nullable=True),
            sa.Column("pass_fail", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        inspector = sa.inspect(bind)
    if not index_exists("model_evaluations", "ix_model_evaluations_model_version_id"):
        op.create_index("ix_model_evaluations_model_version_id", "model_evaluations", ["model_version_id"], unique=False)
    if not index_exists("model_evaluations", "ix_model_evaluations_dataset_tag"):
        op.create_index("ix_model_evaluations_dataset_tag", "model_evaluations", ["dataset_tag"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_model_evaluations_dataset_tag", table_name="model_evaluations")
    op.drop_index("ix_model_evaluations_model_version_id", table_name="model_evaluations")
    op.drop_table("model_evaluations")

    op.drop_index("ix_training_datasets_dataset_tag", table_name="training_datasets")
    op.drop_table("training_datasets")

    op.drop_index("ix_vetting_reason_codes_created_at", table_name="vetting_reason_codes")
    op.drop_index("ix_vetting_reason_codes_code", table_name="vetting_reason_codes")
    op.drop_table("vetting_reason_codes")

    op.drop_constraint("ck_training_pairs_source_split_values", "training_pairs", type_="check")
    op.drop_index("ix_training_pairs_dedupe_hash", table_name="training_pairs")
    op.drop_column("training_pairs", "rejected_reason_codes")
    op.drop_column("training_pairs", "source_split")
    op.drop_column("training_pairs", "language")
    op.drop_column("training_pairs", "pair_weight")
    op.drop_column("training_pairs", "dedupe_hash")

    op.drop_constraint("ck_vetting_logs_severity_level_values", "vetting_logs", type_="check")
    op.drop_constraint("ck_vetting_logs_quality_score_range", "vetting_logs", type_="check")
    op.drop_column("vetting_logs", "severity_level")
    op.drop_column("vetting_logs", "reason_codes")
    op.drop_column("vetting_logs", "rubric_snapshot")
    op.drop_column("vetting_logs", "quality_score")
    op.drop_column("vetting_logs", "review_version")
