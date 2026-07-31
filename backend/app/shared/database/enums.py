"""SQLAlchemy helpers for PostgreSQL enum columns."""

from enum import Enum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum

E = TypeVar("E", bound=Enum)


def pg_enum(enum_cls: type[E], *, name: str) -> SAEnum:
    """Create a PostgreSQL-native SQLAlchemy Enum column type."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )
