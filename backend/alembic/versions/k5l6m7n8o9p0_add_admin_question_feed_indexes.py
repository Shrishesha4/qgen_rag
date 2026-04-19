"""Add indexes for the admin questions feed.

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-04-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k5l6m7n8o9p0'
down_revision = 'j4k5l6m7n8o9'
branch_labels = None
depends_on = None


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)


def upgrade() -> None:
    if not _index_exists('questions', 'ix_questions_admin_feed_generated_at'):
        op.create_index(
            'ix_questions_admin_feed_generated_at',
            'questions',
            ['generated_at', 'id'],
            unique=False,
        )

    if not _index_exists('questions', 'ix_questions_admin_feed_subject_topic_generated_at'):
        op.create_index(
            'ix_questions_admin_feed_subject_topic_generated_at',
            'questions',
            ['subject_id', 'topic_id', 'generated_at', 'id'],
            unique=False,
        )

    if not _index_exists('questions', 'ix_questions_admin_feed_status_generated_at'):
        op.create_index(
            'ix_questions_admin_feed_status_generated_at',
            'questions',
            ['vetting_status', 'generated_at', 'id'],
            unique=False,
        )


def downgrade() -> None:
    if _index_exists('questions', 'ix_questions_admin_feed_status_generated_at'):
        op.drop_index('ix_questions_admin_feed_status_generated_at', table_name='questions')
    if _index_exists('questions', 'ix_questions_admin_feed_subject_topic_generated_at'):
        op.drop_index('ix_questions_admin_feed_subject_topic_generated_at', table_name='questions')
    if _index_exists('questions', 'ix_questions_admin_feed_generated_at'):
        op.drop_index('ix_questions_admin_feed_generated_at', table_name='questions')
