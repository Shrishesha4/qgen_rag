"""add_topic_audit_log

Revision ID: 9aaddae6699d
Revises: h2i3j4k5l6m7
Create Date: 2026-03-27 10:42:18.665537

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9aaddae6699d'
down_revision: Union[str, None] = 'h2i3j4k5l6m7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('topic_audit_log',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('topic_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('user_name', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_topic_audit_log_created_at'), 'topic_audit_log', ['created_at'], unique=False)
    op.create_index(op.f('ix_topic_audit_log_topic_id'), 'topic_audit_log', ['topic_id'], unique=False)
    op.create_index(op.f('ix_topic_audit_log_user_id'), 'topic_audit_log', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_topic_audit_log_user_id'), table_name='topic_audit_log')
    op.drop_index(op.f('ix_topic_audit_log_topic_id'), table_name='topic_audit_log')
    op.drop_index(op.f('ix_topic_audit_log_created_at'), table_name='topic_audit_log')
    op.drop_table('topic_audit_log')
