"""add topic_id to documents for per-topic reference materials

Revision ID: d4e5f6a7b8c9
Revises: c3ac2378206b
Create Date: 2026-03-21
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c7a1f6e9a006"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Add topic_id column to documents table
    op.add_column(
        "documents",
        sa.Column("topic_id", sa.String(36), nullable=True)
    )
    
    # Create foreign key constraint
    op.create_foreign_key(
        "fk_documents_topic_id",
        "documents",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="SET NULL"
    )
    
    # Create index for efficient topic-based queries
    op.create_index("ix_documents_topic_id", "documents", ["topic_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_topic_id", table_name="documents")
    op.drop_constraint("fk_documents_topic_id", "documents", type_="foreignkey")
    op.drop_column("documents", "topic_id")
