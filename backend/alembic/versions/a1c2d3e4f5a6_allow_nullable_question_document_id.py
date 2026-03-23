"""allow questions.document_id to be nullable for no-PDF persistence

Revision ID: a1c2d3e4f5a6
Revises: cd754e1f4b40
Create Date: 2026-03-23
"""

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c2d3e4f5a6"
down_revision: Union[str, None] = "cd754e1f4b40"
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
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _column_is_nullable(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for col in inspector.get_columns(table_name):
        if col["name"] == column_name:
            return bool(col.get("nullable", True))
    return True


def _find_document_fk_names(table_name: str) -> list[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    names: list[str] = []
    for fk in inspector.get_foreign_keys(table_name):
        constrained = fk.get("constrained_columns") or []
        referred_table = fk.get("referred_table")
        if constrained == ["document_id"] and referred_table == "documents":
            if fk.get("name"):
                names.append(fk["name"])
    return names


def upgrade() -> None:
    if not _table_exists("questions") or not _column_exists("questions", "document_id"):
        return

    if not _column_is_nullable("questions", "document_id"):
        op.alter_column(
            "questions",
            "document_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )

    existing_fk_names = _find_document_fk_names("questions")
    for fk_name in existing_fk_names:
        op.drop_constraint(fk_name, "questions", type_="foreignkey")

    op.create_foreign_key(
        "questions_document_id_fkey",
        "questions",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    if not _table_exists("questions") or not _column_exists("questions", "document_id"):
        return

    bind = op.get_bind()
    null_count = bind.execute(sa.text("SELECT COUNT(*) FROM questions WHERE document_id IS NULL")).scalar() or 0
    if null_count > 0:
        raise RuntimeError(
            "Cannot downgrade a1c2d3e4f5a6: questions.document_id has NULL values. "
            "Backfill document_id values before downgrading."
        )

    existing_fk_names = _find_document_fk_names("questions")
    for fk_name in existing_fk_names:
        op.drop_constraint(fk_name, "questions", type_="foreignkey")

    op.create_foreign_key(
        "questions_document_id_fkey",
        "questions",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )

    if _column_is_nullable("questions", "document_id"):
        op.alter_column(
            "questions",
            "document_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
