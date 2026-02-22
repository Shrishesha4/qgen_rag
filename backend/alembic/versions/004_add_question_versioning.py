"""Add question versioning fields for regeneration tracking

Revision ID: 004_versioning
Revises: e3871e9f4ef3
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '004_versioning'
down_revision = 'e3871e9f4ef3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add replaced_by_id - points to the question that replaced this one
    op.add_column('questions', sa.Column(
        'replaced_by_id',
        UUID(as_uuid=True),
        sa.ForeignKey('questions.id', ondelete='SET NULL'),
        nullable=True,
    ))
    
    # Add replaces_id - points to the question this one replaced
    op.add_column('questions', sa.Column(
        'replaces_id',
        UUID(as_uuid=True),
        sa.ForeignKey('questions.id', ondelete='SET NULL'),
        nullable=True,
    ))
    
    # Add version_number - starts at 1, increments with each regeneration
    op.add_column('questions', sa.Column(
        'version_number',
        sa.Integer(),
        nullable=False,
        server_default='1'
    ))
    
    # Add is_latest - true only for the most recent version
    op.add_column('questions', sa.Column(
        'is_latest',
        sa.Boolean(),
        nullable=False,
        server_default='true'
    ))
    
    # Create index for efficient version chain queries
    op.create_index('ix_questions_replaced_by_id', 'questions', ['replaced_by_id'])
    op.create_index('ix_questions_replaces_id', 'questions', ['replaces_id'])
    op.create_index('ix_questions_is_latest', 'questions', ['is_latest'])


def downgrade() -> None:
    op.drop_index('ix_questions_is_latest', table_name='questions')
    op.drop_index('ix_questions_replaces_id', table_name='questions')
    op.drop_index('ix_questions_replaced_by_id', table_name='questions')
    op.drop_column('questions', 'is_latest')
    op.drop_column('questions', 'version_number')
    op.drop_column('questions', 'replaces_id')
    op.drop_column('questions', 'replaced_by_id')
