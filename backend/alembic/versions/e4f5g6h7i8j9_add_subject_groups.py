"""add subject groups for hierarchical organization

Revision ID: e4f5g6h7i8j9
Revises: cd754e1f4b40
Create Date: 2026-03-23 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5g6h7i8j9'
down_revision: Union[str, None] = 'cd754e1f4b40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create subject_groups table
    op.create_table(
        'subject_groups',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('parent_id', sa.String(36), sa.ForeignKey('subject_groups.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Add group_id column to subjects table
    op.add_column(
        'subjects',
        sa.Column('group_id', sa.String(36), sa.ForeignKey('subject_groups.id', ondelete='SET NULL'), nullable=True, index=True)
    )


def downgrade() -> None:
    # Remove group_id column from subjects
    op.drop_column('subjects', 'group_id')
    
    # Drop subject_groups table
    op.drop_table('subject_groups')
