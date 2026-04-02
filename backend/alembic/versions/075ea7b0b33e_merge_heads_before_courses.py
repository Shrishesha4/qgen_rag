"""merge_heads_before_courses

Revision ID: 075ea7b0b33e
Revises: 9aaddae6699d, k5l6m7n8o9p0
Create Date: 2026-04-02 15:43:54.674958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '075ea7b0b33e'
down_revision: Union[str, None] = ('9aaddae6699d', 'k5l6m7n8o9p0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
