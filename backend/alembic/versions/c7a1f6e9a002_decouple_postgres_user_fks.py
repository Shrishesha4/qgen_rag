"""decouple postgres user foreign keys from auth flow

Revision ID: c7a1f6e9a002
Revises: c7a1f6e9a001
Create Date: 2026-03-20
"""

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7a1f6e9a002"
down_revision: Union[str, None] = "c7a1f6e9a001"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    fks = inspector.get_foreign_keys(table_name)
    return any(fk.get("name") == constraint_name for fk in fks)


def upgrade() -> None:
    # User identities are stored in SQLite auth DB. In PostgreSQL, keep user_id/vetted_by
    # as plain string references enforced at application level.
    fk_targets = [
        ("subjects", "subjects_user_id_fkey"),
        ("documents", "documents_user_id_fkey"),
        ("generation_sessions", "generation_sessions_user_id_fkey"),
        ("questions", "questions_vetted_by_fkey"),
    ]

    for table_name, constraint_name in fk_targets:
        if _table_exists(table_name) and _constraint_exists(table_name, constraint_name):
            op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def downgrade() -> None:
    # Conservative: do not recreate deprecated cross-database FKs.
    pass
