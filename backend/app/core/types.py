"""Custom SQLAlchemy column types used across the application."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.types import TypeDecorator, String


class UUIDString(TypeDecorator):
    """Store UUID values in VARCHAR(36) columns while accepting UUID objects."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Optional[object], dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value: Optional[str], dialect):
        return value
