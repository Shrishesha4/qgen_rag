"""Add novelty validation fields

Revision ID: 003_add_novelty_fields
Revises: 002_add_explanation
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '003_add_novelty_fields'
down_revision: Union[str, None] = '002_add_explanation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # User model: Add novelty settings
    op.add_column('users', sa.Column('novelty_threshold', sa.Float(), nullable=True, default=1.0))
    op.add_column('users', sa.Column('max_regeneration_attempts', sa.Integer(), nullable=True, default=5))
    op.add_column('users', sa.Column('subject_reference_materials', sa.JSON(), nullable=True))
    
    # Set default values for existing users
    op.execute("UPDATE users SET novelty_threshold = 1.0 WHERE novelty_threshold IS NULL")
    op.execute("UPDATE users SET max_regeneration_attempts = 5 WHERE max_regeneration_attempts IS NULL")
    
    # Document model: Add index_type and subject_id
    op.add_column('documents', sa.Column('index_type', sa.String(50), nullable=True, default='primary'))
    op.add_column('documents', sa.Column(
        'subject_id',
        UUID(as_uuid=True),
        sa.ForeignKey('subjects.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    ))
    
    # Set default index_type for existing documents
    op.execute("UPDATE documents SET index_type = 'primary' WHERE index_type IS NULL")
    
    # Question model: Add novelty validation fields
    op.add_column('questions', sa.Column('novelty_score', sa.Float(), nullable=True))
    op.add_column('questions', sa.Column('max_similarity', sa.Float(), nullable=True))
    op.add_column('questions', sa.Column('similarity_source', sa.String(50), nullable=True))
    op.add_column('questions', sa.Column('generation_attempt_count', sa.Integer(), nullable=True, default=1))
    op.add_column('questions', sa.Column('used_reference_materials', sa.Boolean(), nullable=True, default=False))
    op.add_column('questions', sa.Column('novelty_metadata', sa.JSON(), nullable=True))
    op.add_column('questions', sa.Column('generation_status', sa.String(20), nullable=True, default='accepted'))
    op.add_column('questions', sa.Column('discard_reason', sa.Text(), nullable=True))
    
    # Set default values for existing questions
    op.execute("UPDATE questions SET generation_attempt_count = 1 WHERE generation_attempt_count IS NULL")
    op.execute("UPDATE questions SET used_reference_materials = false WHERE used_reference_materials IS NULL")
    op.execute("UPDATE questions SET generation_status = 'accepted' WHERE generation_status IS NULL")
    
    # Create index for novelty queries
    op.create_index('ix_questions_generation_status', 'questions', ['generation_status'])
    op.create_index('ix_questions_novelty_score', 'questions', ['novelty_score'])
    op.create_index('ix_documents_index_type', 'documents', ['index_type'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_documents_index_type', 'documents')
    op.drop_index('ix_questions_novelty_score', 'questions')
    op.drop_index('ix_questions_generation_status', 'questions')
    
    # Remove question columns
    op.drop_column('questions', 'discard_reason')
    op.drop_column('questions', 'generation_status')
    op.drop_column('questions', 'novelty_metadata')
    op.drop_column('questions', 'used_reference_materials')
    op.drop_column('questions', 'generation_attempt_count')
    op.drop_column('questions', 'similarity_source')
    op.drop_column('questions', 'max_similarity')
    op.drop_column('questions', 'novelty_score')
    
    # Remove document columns
    op.drop_column('documents', 'subject_id')
    op.drop_column('documents', 'index_type')
    
    # Remove user columns
    op.drop_column('users', 'subject_reference_materials')
    op.drop_column('users', 'max_regeneration_attempts')
    op.drop_column('users', 'novelty_threshold')
