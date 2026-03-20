"""reconcile documents and document_chunks schema with ORM models

Revision ID: c7a1f6e9a003
Revises: c7a1f6e9a002
Create Date: 2026-03-20
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "c7a1f6e9a003"
down_revision: Union[str, None] = "c7a1f6e9a002"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    uniques = inspector.get_unique_constraints(table_name)
    return any(cons.get("name") == constraint_name for cons in uniques)


def upgrade() -> None:
    if _table_exists("documents"):
        if not _column_exists("documents", "file_size_bytes"):
            op.add_column("documents", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
            if _column_exists("documents", "file_size"):
                op.execute("UPDATE documents SET file_size_bytes = file_size WHERE file_size_bytes IS NULL")
            op.execute("UPDATE documents SET file_size_bytes = 0 WHERE file_size_bytes IS NULL")
            op.alter_column("documents", "file_size_bytes", nullable=False)

        if not _column_exists("documents", "mime_type"):
            op.add_column("documents", sa.Column("mime_type", sa.String(length=100), nullable=True))
            if _column_exists("documents", "file_type"):
                op.execute("UPDATE documents SET mime_type = file_type WHERE mime_type IS NULL")

        if not _column_exists("documents", "storage_path"):
            op.add_column("documents", sa.Column("storage_path", sa.String(length=500), nullable=True))
            if _column_exists("documents", "file_path"):
                op.execute("UPDATE documents SET storage_path = file_path WHERE storage_path IS NULL")

        if not _column_exists("documents", "total_chunks"):
            op.add_column("documents", sa.Column("total_chunks", sa.Integer(), nullable=True))

        if not _column_exists("documents", "total_tokens"):
            op.add_column("documents", sa.Column("total_tokens", sa.Integer(), nullable=True))

        if not _column_exists("documents", "upload_timestamp"):
            op.add_column(
                "documents",
                sa.Column("upload_timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            )
            if _column_exists("documents", "created_at"):
                op.execute(
                    "UPDATE documents SET upload_timestamp = created_at WHERE upload_timestamp IS NULL"
                )
            op.alter_column("documents", "upload_timestamp", nullable=False)

        if not _column_exists("documents", "processed_at"):
            op.add_column("documents", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
            if _column_exists("documents", "updated_at"):
                op.execute(
                    """
                    UPDATE documents
                    SET processed_at = updated_at
                    WHERE processed_at IS NULL
                      AND processing_status = 'completed'
                    """
                )

        if not _column_exists("documents", "document_metadata"):
            op.add_column("documents", sa.Column("document_metadata", JSONB(), nullable=True))

        if not _column_exists("documents", "is_public"):
            op.add_column(
                "documents",
                sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            )

        if not _column_exists("documents", "share_token"):
            op.add_column("documents", sa.Column("share_token", sa.String(length=100), nullable=True))

        if _column_exists("documents", "share_token") and not _constraint_exists("documents", "uq_documents_share_token"):
            op.create_unique_constraint("uq_documents_share_token", "documents", ["share_token"])

    if _table_exists("document_chunks"):
        if not _column_exists("document_chunks", "token_count"):
            op.add_column("document_chunks", sa.Column("token_count", sa.Integer(), nullable=True))

        if not _column_exists("document_chunks", "section_heading"):
            op.add_column("document_chunks", sa.Column("section_heading", sa.String(length=500), nullable=True))

        if not _column_exists("document_chunks", "chunk_metadata"):
            op.add_column("document_chunks", sa.Column("chunk_metadata", JSONB(), nullable=True))
            if _column_exists("document_chunks", "metadata"):
                op.execute(
                    "UPDATE document_chunks SET chunk_metadata = metadata::jsonb WHERE chunk_metadata IS NULL"
                )

        if not _index_exists("document_chunks", "ix_document_chunks_document_id"):
            op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"], unique=False)


def downgrade() -> None:
    # Repair migration: keep conservative downgrade behavior.
    pass
