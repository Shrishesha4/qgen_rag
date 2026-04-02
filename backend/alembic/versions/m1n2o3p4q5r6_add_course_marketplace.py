"""add course marketplace tables

Revision ID: m1n2o3p4q5r6
Revises: 075ea7b0b33e
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "m1n2o3p4q5r6"
down_revision = "075ea7b0b33e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── courses ──
    op.create_table(
        "courses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("teacher_id", sa.String(36), nullable=False, index=True),
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(280), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("cover_image_url", sa.String(512), nullable=True),
        sa.Column("preview_video_url", sa.String(512), nullable=True),
        sa.Column("price_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("is_featured", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("learning_outcomes", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── course_modules ──
    op.create_table(
        "course_modules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("module_type", sa.String(20), nullable=False, server_default="content"),
        sa.Column("content_data", JSONB, nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        sa.Column("is_preview", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── module_questions ──
    op.create_table(
        "module_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("module_id", sa.String(36), sa.ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
        sa.UniqueConstraint("module_id", "question_id", name="uq_module_question"),
    )

    # ── enrollments ──
    op.create_table(
        "enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), nullable=False, index=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("progress_data", JSONB, nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("student_id", "course_id", name="uq_student_course"),
    )

    # ── payments ──
    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("student_id", sa.String(36), nullable=False, index=True),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(20), nullable=False, server_default="mock"),
        sa.Column("provider_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── personalized_items ──
    op.create_table(
        "personalized_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), nullable=False, index=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("topic_id", sa.String(36), sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("template_id", sa.String(100), nullable=True),
        sa.Column("generated_content", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("personalized_items")
    op.drop_table("payments")
    op.drop_table("enrollments")
    op.drop_table("module_questions")
    op.drop_table("course_modules")
    op.drop_table("courses")
