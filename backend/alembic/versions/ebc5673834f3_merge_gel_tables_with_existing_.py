"""Merge GEL tables with existing migrations

Revision ID: ebc5673834f3
Revises: g1e2l3t4r5a6, i3j4k5l6m7n8
Create Date: 2026-03-25 17:37:59.255631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ebc5673834f3'
down_revision: Union[str, None] = ('g1e2l3t4r5a6', 'i3j4k5l6m7n8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
