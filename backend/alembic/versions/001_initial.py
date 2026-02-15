"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('role', sa.String(50), default='teacher'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Refresh tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('is_revoked', sa.Boolean(), default=False),
    )
    
    # Subjects table
    op.create_table(
        'subjects',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color', sa.String(7), default='#3B82F6'),
        sa.Column('icon', sa.String(50), default='book'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('subject_id', sa.String(36), sa.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=True, index=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('processing_status', sa.String(50), default='pending'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Document chunks table with vector column
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_embedding', Vector(384), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('start_char', sa.Integer(), nullable=True),
        sa.Column('end_char', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Rubric templates table
    op.create_table(
        'rubric_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('question_type', sa.String(50), nullable=True),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Rubric criteria table
    op.create_table(
        'rubric_criteria',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('rubric_id', sa.String(36), sa.ForeignKey('rubric_templates.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('max_score', sa.Float(), nullable=False, default=10.0),
        sa.Column('weight', sa.Float(), nullable=False, default=1.0),
        sa.Column('order_index', sa.Integer(), default=0),
    )
    
    # Generation sessions table
    op.create_table(
        'generation_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('requested_count', sa.Integer(), nullable=False),
        sa.Column('requested_types', sa.JSON(), nullable=True),
        sa.Column('requested_marks', sa.Integer(), nullable=True),
        sa.Column('requested_difficulty', sa.String(50), nullable=True),
        sa.Column('focus_topics', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('questions_generated', sa.Integer(), default=0),
        sa.Column('questions_failed', sa.Integer(), default=0),
        sa.Column('questions_duplicate', sa.Integer(), default=0),
        sa.Column('total_duration_seconds', sa.Float(), nullable=True),
        sa.Column('llm_calls', sa.Integer(), default=0),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('blacklist_size', sa.Integer(), nullable=True),
        sa.Column('chunks_used', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
    )
    
    # Questions table with vector column
    op.create_table(
        'questions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('generation_sessions.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(50), nullable=False),
        sa.Column('marks', sa.Integer(), nullable=True),
        sa.Column('difficulty_level', sa.String(50), nullable=True),
        sa.Column('bloom_taxonomy_level', sa.String(50), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('correct_answer', sa.Text(), nullable=True),
        sa.Column('topic_tags', sa.JSON(), nullable=True),
        sa.Column('source_chunk_ids', sa.JSON(), nullable=True),
        sa.Column('question_embedding', Vector(384), nullable=True),
        sa.Column('answerability_score', sa.Float(), nullable=True),
        sa.Column('specificity_score', sa.Float(), nullable=True),
        sa.Column('generation_confidence', sa.Float(), nullable=True),
        sa.Column('vetting_status', sa.String(50), default='pending', index=True),
        sa.Column('vetting_comments', sa.Text(), nullable=True),
        sa.Column('vetted_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('vetted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('times_shown', sa.Integer(), default=0),
        sa.Column('user_rating', sa.Float(), nullable=True),
        sa.Column('is_archived', sa.Boolean(), default=False),
    )


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('questions')
    op.drop_table('generation_sessions')
    op.drop_table('rubric_criteria')
    op.drop_table('rubric_templates')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('subjects')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
    
    # Don't drop the vector extension as other things might use it
    # op.execute('DROP EXTENSION IF EXISTS vector')
