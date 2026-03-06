"""Update embedding dimension from 384 to 768

Switching from all-MiniLM-L6-v2 (384-dim) to BAAI/bge-base-en-v1.5 (768-dim).
Existing embeddings are incompatible across models — they are NULLed out here
so the re-embedding script can repopulate them with the correct model.

Revision ID: 006_update_embedding_dimension
Revises: 005_add_user_role
Create Date: 2026-03-06 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = '006_update_embedding_dimension'
down_revision: Union[str, None] = '005_add_user_role'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_DIM = 768
OLD_DIM = 384


def upgrade() -> None:
    # Drop vector indexes — they bind to the current dimension and cannot be
    # reused after the column type changes.
    op.execute("DROP INDEX IF EXISTS idx_chunk_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS idx_question_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS idx_chunk_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_question_embedding_hnsw")

    # NULL out stale 384-dim embeddings.  pgvector does not allow an implicit
    # cast between differently-dimensioned vector types, so we clear first.
    op.execute("UPDATE document_chunks SET chunk_embedding = NULL")
    op.execute("UPDATE questions      SET question_embedding = NULL")

    # Alter column types to the new dimension.
    op.execute(
        f"ALTER TABLE document_chunks "
        f"ALTER COLUMN chunk_embedding TYPE vector({NEW_DIM})"
    )
    op.execute(
        f"ALTER TABLE questions "
        f"ALTER COLUMN question_embedding TYPE vector({NEW_DIM})"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunk_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS idx_question_embedding_ivfflat")

    op.execute("UPDATE document_chunks SET chunk_embedding = NULL")
    op.execute("UPDATE questions      SET question_embedding = NULL")

    op.execute(
        f"ALTER TABLE document_chunks "
        f"ALTER COLUMN chunk_embedding TYPE vector({OLD_DIM})"
    )
    op.execute(
        f"ALTER TABLE questions "
        f"ALTER COLUMN question_embedding TYPE vector({OLD_DIM})"
    )
