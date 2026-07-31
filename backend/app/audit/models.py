"""Audit domain models.

Purpose: Persist immutable-ish records of important system actions.
Responsibilities: Audit log entity mapping.
Dependencies: auth.models, shared.database.
Extension points: Structured action catalogs, retention policies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.auth.models import User


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Record of a significant platform action."""

    __tablename__ = "audit_logs"

    actor_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    actor: Mapped[User | None] = relationship(
        back_populates="audit_logs", lazy="joined"
    )
