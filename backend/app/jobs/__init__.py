"""Job processing feature module.

Purpose: Asynchronous job persistence.
Responsibilities: Job model and repository.
Dependencies: audio, shared.database, shared.domain.
Extension points: Celery orchestration, progress computation.
"""

from app.jobs.models import Job
from app.jobs.repository import JobRepository, SqlAlchemyJobRepository

__all__ = ["Job", "JobRepository", "SqlAlchemyJobRepository"]
