"""Common reusable type aliases."""

from typing import TypeAlias
from uuid import UUID

JSONDict: TypeAlias = dict[str, object]
EntityId: TypeAlias = UUID
