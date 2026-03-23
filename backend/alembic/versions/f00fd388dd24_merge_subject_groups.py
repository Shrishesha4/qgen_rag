"""merge_subject_groups

Revision ID: f00fd388dd24
Revises: a1c2d3e4f5a6, e4f5g6h7i8j9
Create Date: 2026-03-23 16:14:20.388089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f00fd388dd24'
down_revision: Union[str, None] = ('a1c2d3e4f5a6', 'e4f5g6h7i8j9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
