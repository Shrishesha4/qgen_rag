"""Add role field to users table

Revision ID: 005_add_user_role
Revises: e3871e9f4ef3
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_user_role'
down_revision: Union[str, None] = 'e3871e9f4ef3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add role column with default 'teacher' for existing users
    op.add_column('users', sa.Column('role', sa.String(20), nullable=False, server_default='teacher'))


def downgrade() -> None:
    op.drop_column('users', 'role')
