"""relax legacy documents not-null constraints for ORM compatibility

Revision ID: c7a1f6e9a004
Revises: c7a1f6e9a003
Create Date: 2026-03-20
"""

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7a1f6e9a004"
down_revision: Union[str, None] = "c7a1f6e9a003"
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


def upgrade() -> None:
    if not _table_exists("documents"):
        return

    # Backfill legacy columns from canonical/newer columns when possible.
    if _column_exists("documents", "original_filename") and _column_exists("documents", "filename"):
        op.execute(
            "UPDATE documents SET original_filename = filename WHERE original_filename IS NULL"
        )

    if _column_exists("documents", "file_path") and _column_exists("documents", "storage_path"):
        op.execute(
            "UPDATE documents SET file_path = storage_path WHERE file_path IS NULL"
        )

    if _column_exists("documents", "file_type") and _column_exists("documents", "mime_type"):
        op.execute(
            "UPDATE documents SET file_type = mime_type WHERE file_type IS NULL"
        )

    if _column_exists("documents", "file_size") and _column_exists("documents", "file_size_bytes"):
        op.execute(
            "UPDATE documents SET file_size = file_size_bytes WHERE file_size IS NULL"
        )

    # Relax legacy constraints to prevent inserts from failing when ORM omits legacy fields.
    if _column_exists("documents", "original_filename"):
        op.alter_column(
            "documents",
            "original_filename",
            existing_type=sa.String(length=255),
            nullable=True,
        )

    if _column_exists("documents", "file_path"):
        op.alter_column(
            "documents",
            "file_path",
            existing_type=sa.String(length=500),
            nullable=True,
        )

    if _column_exists("documents", "file_type"):
        op.alter_column(
            "documents",
            "file_type",
            existing_type=sa.String(length=100),
            nullable=True,
        )

    if _column_exists("documents", "file_size"):
        op.alter_column(
            "documents",
            "file_size",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    # Repair migration: conservative no-op downgrade.
    pass
