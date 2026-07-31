"""Authentication feature module.

Purpose: User identity persistence for future auth sprints.
Responsibilities: User model and repository.
Dependencies: shared.database, shared.domain.
Extension points: JWT, password hashing (Sprint auth).
"""

from app.auth.models import User
from app.auth.repository import SqlAlchemyUserRepository, UserRepository

__all__ = ["SqlAlchemyUserRepository", "User", "UserRepository"]
