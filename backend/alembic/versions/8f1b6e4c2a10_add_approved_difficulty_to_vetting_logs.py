"""add approved difficulty to vetting logs

Revision ID: 8f1b6e4c2a10
Revises: 007_add_training_pipeline
Create Date: 2026-03-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f1b6e4c2a10"
down_revision: Union[str, None] = "007_add_training_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("vetting_logs", "approved_difficulty"):
        op.add_column(
            "vetting_logs",
            sa.Column("approved_difficulty", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("vetting_logs", "approved_difficulty")