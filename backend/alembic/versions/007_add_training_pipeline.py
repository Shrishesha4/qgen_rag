"""add training pipeline tables

Revision ID: 007_add_training_pipeline
Revises: 006_update_embedding_dimension
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from pgvector.sqlalchemy import Vector

# revision identifiers
revision = "007_add_training_pipeline"
down_revision = "006_update_embedding_dimension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── vetting_logs ──
    op.create_table(
        "vetting_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("question_id", UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("vetter_id", sa.String(36), nullable=False, index=True),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("original_text", sa.Text),
        sa.Column("edited_text", sa.Text),
        sa.Column("edit_diff", JSONB),
        sa.Column("rejection_reasons", ARRAY(sa.Text)),
        sa.Column("rejection_reason_embedding", Vector(768)),
        sa.Column("feedback", sa.Text),
        sa.Column("auto_critique_score", sa.Float),
        sa.Column("auto_critique_reasons", JSONB),
        sa.Column("time_spent_seconds", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )

    # ── training_pairs ──
    op.create_table(
        "training_pairs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("chosen_response", sa.Text, nullable=False),
        sa.Column("rejected_response", sa.Text, nullable=False),
        sa.Column("vetting_log_id", UUID(as_uuid=True), sa.ForeignKey("vetting_logs.id", ondelete="SET NULL")),
        sa.Column("chosen_question_id", UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="SET NULL")),
        sa.Column("rejected_question_id", UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="SET NULL")),
        sa.Column("pair_type", sa.String(20), server_default="edit"),
        sa.Column("status", sa.String(10), server_default="pending"),
        sa.Column("used_in_version", sa.String(50)),
        sa.Column("confidence", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )

    # ── model_versions ──
    op.create_table(
        "model_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("version_tag", sa.String(50), unique=True, nullable=False),
        sa.Column("base_model", sa.String(100), nullable=False),
        sa.Column("lora_adapter_path", sa.String(500)),
        sa.Column("training_method", sa.String(20), server_default="sft"),
        sa.Column("training_pairs_count", sa.Integer, server_default="0"),
        sa.Column("sft_samples_count", sa.Integer, server_default="0"),
        sa.Column("hyperparameters", JSONB),
        sa.Column("eval_metrics", JSONB),
        sa.Column("is_active", sa.Boolean, server_default="false"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("error_message", sa.Text),
        sa.Column("parent_version_id", UUID(as_uuid=True), sa.ForeignKey("model_versions.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("training_started_at", sa.DateTime(timezone=True)),
        sa.Column("training_completed_at", sa.DateTime(timezone=True)),
    )

    # ── training_jobs ──
    op.create_table(
        "training_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("model_version_id", UUID(as_uuid=True), sa.ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("training_data_path", sa.String(500)),
        sa.Column("training_samples", sa.Integer, server_default="0"),
        sa.Column("validation_samples", sa.Integer, server_default="0"),
        sa.Column("current_epoch", sa.Integer, server_default="0"),
        sa.Column("total_epochs", sa.Integer, server_default="3"),
        sa.Column("current_step", sa.Integer, server_default="0"),
        sa.Column("total_steps", sa.Integer, server_default="0"),
        sa.Column("current_loss", sa.Float),
        sa.Column("final_loss", sa.Float),
        sa.Column("eval_metrics", JSONB),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("triggered_by", sa.String(36)),
    )


def downgrade() -> None:
    op.drop_table("training_jobs")
    op.drop_table("model_versions")
    op.drop_table("training_pairs")
    op.drop_table("vetting_logs")
