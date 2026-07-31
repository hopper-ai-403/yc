"""User repository contract and SQLAlchemy implementation."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User


class UserRepository(ABC):
    """Persistence contract for User entities."""

    @abstractmethod
    async def create(self, user: User) -> User:
        """Persist a new user."""

    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> User | None:
        """Find a user by primary key."""

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None:
        """Find a user by unique email."""

    @abstractmethod
    async def update(self, user: User) -> User:
        """Persist changes to an existing user."""


class SqlAlchemyUserRepository(UserRepository):
    """SQLAlchemy-backed UserRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def find_by_id(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def find_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def update(self, user: User) -> User:
        await self._session.flush()
        await self._session.refresh(user)
        return user
