"""Audit repository contract and SQLAlchemy implementation."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog


class AuditRepository(ABC):
    """Persistence contract for AuditLog entities."""

    @abstractmethod
    async def append(self, entry: AuditLog) -> AuditLog:
        """Append a new audit log entry."""

    @abstractmethod
    async def find_by_id(self, entry_id: UUID) -> AuditLog | None:
        """Find an audit entry by id."""

    @abstractmethod
    async def find_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
    ) -> list[AuditLog]:
        """Find audit entries for a resource."""

    @abstractmethod
    async def find_by_actor(self, actor_id: UUID) -> list[AuditLog]:
        """Find audit entries for an actor."""


class SqlAlchemyAuditRepository(AuditRepository):
    """SQLAlchemy-backed AuditRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: AuditLog) -> AuditLog:
        self._session.add(entry)
        await self._session.flush()
        await self._session.refresh(entry)
        return entry

    async def find_by_id(self, entry_id: UUID) -> AuditLog | None:
        return await self._session.get(AuditLog, entry_id)

    async def find_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
    ) -> list[AuditLog]:
        statement = (
            select(AuditLog)
            .where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(AuditLog.created_at.desc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_actor(self, actor_id: UUID) -> list[AuditLog]:
        statement = (
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .order_by(AuditLog.created_at.desc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
