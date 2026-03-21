"""merge vetting progress and eval migrations

Revision ID: cd754e1f4b40
Revises: c9f2e1a4b7d8, d4e5f6a7b8c9
Create Date: 2026-03-21 17:23:52.466594

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd754e1f4b40'
down_revision: Union[str, None] = ('c9f2e1a4b7d8', 'd4e5f6a7b8c9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
