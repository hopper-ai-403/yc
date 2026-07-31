"""Authentication domain models.

Purpose: Persist platform users.
Responsibilities: User entity mapping.
Dependencies: shared.database, shared.domain.enums.
Extension points: Profile fields, organization membership.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.shared.database.enums import pg_enum
from app.shared.domain.enums import UserRole

if TYPE_CHECKING:
    from app.audio.models import AudioBatch
    from app.audit.models import AuditLog


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Platform user entity."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.EVALUATOR,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    batches: Mapped[list[AudioBatch]] = relationship(
        back_populates="uploader",
        lazy="selectin",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="actor",
        lazy="selectin",
    )
