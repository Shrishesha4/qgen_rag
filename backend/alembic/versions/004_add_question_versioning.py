"""Add question versioning fields for regeneration tracking

Revision ID: 004_versioning
Revises: e3871e9f4ef3
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_versioning'
down_revision = 'e3871e9f4ef3'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(idx["name"] == index_name for idx in indexes)


def upgrade() -> None:
    # Add replaced_by_id - points to the question that replaced this one
    if not _column_exists('questions', 'replaced_by_id'):
        op.add_column('questions', sa.Column(
            'replaced_by_id',
            sa.String(length=36),
            sa.ForeignKey('questions.id', ondelete='SET NULL'),
            nullable=True,
        ))
    
    # Add replaces_id - points to the question this one replaced
    if not _column_exists('questions', 'replaces_id'):
        op.add_column('questions', sa.Column(
            'replaces_id',
            sa.String(length=36),
            sa.ForeignKey('questions.id', ondelete='SET NULL'),
            nullable=True,
        ))
    
    # Add version_number - starts at 1, increments with each regeneration
    if not _column_exists('questions', 'version_number'):
        op.add_column('questions', sa.Column(
            'version_number',
            sa.Integer(),
            nullable=False,
            server_default='1'
        ))
    
    # Add is_latest - true only for the most recent version
    if not _column_exists('questions', 'is_latest'):
        op.add_column('questions', sa.Column(
            'is_latest',
            sa.Boolean(),
            nullable=False,
            server_default='true'
        ))
    
    # Create index for efficient version chain queries
    if not _index_exists('questions', 'ix_questions_replaced_by_id'):
        op.create_index('ix_questions_replaced_by_id', 'questions', ['replaced_by_id'])
    if not _index_exists('questions', 'ix_questions_replaces_id'):
        op.create_index('ix_questions_replaces_id', 'questions', ['replaces_id'])
    if not _index_exists('questions', 'ix_questions_is_latest'):
        op.create_index('ix_questions_is_latest', 'questions', ['is_latest'])


def downgrade() -> None:
    op.drop_index('ix_questions_is_latest', table_name='questions')
    op.drop_index('ix_questions_replaces_id', table_name='questions')
    op.drop_index('ix_questions_replaced_by_id', table_name='questions')
    op.drop_column('questions', 'is_latest')
    op.drop_column('questions', 'version_number')
    op.drop_column('questions', 'replaces_id')
    op.drop_column('questions', 'replaced_by_id')
