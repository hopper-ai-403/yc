"""Job orchestration dispatcher abstraction."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class JobDispatcher(Protocol):
    """Dispatches batch orchestration work to the worker fleet."""

    def enqueue_batch(self, job_id: UUID, *, countdown: int = 0) -> str:
        """Queue process_batch for a job. Returns Celery task id."""
        ...


class CeleryJobDispatcher:
    """Celery-backed JobDispatcher."""

    def enqueue_batch(self, job_id: UUID, *, countdown: int = 0) -> str:
        from app.infrastructure.celery.tasks import process_batch

        async_result = process_batch.apply_async(  # type: ignore[attr-defined]
            args=[str(job_id)],
            countdown=max(0, countdown),
        )
        return str(async_result.id)
