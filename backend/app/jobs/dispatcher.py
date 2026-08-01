"""Job orchestration dispatcher abstraction."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class JobDispatcher(Protocol):
    """Dispatches batch orchestration work to the worker fleet."""

    def enqueue_batch(self, job_id: UUID, *, countdown: int = 0) -> str:
        """Queue process_batch for a job. Returns Celery task id."""
        ...

    def revoke_batch(self, celery_task_id: str) -> None:
        """Remove a queued/running Celery task so it no longer occupies workers."""
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

    def revoke_batch(self, celery_task_id: str) -> None:
        if not celery_task_id.strip():
            return
        from app.infrastructure.celery.app import celery_app

        try:
            celery_app.control.revoke(celery_task_id, terminate=True)
            logger.info(
                "celery_task_revoked",
                celery_task_id=celery_task_id,
                status="ok",
            )
        except Exception as exc:
            logger.warning(
                "celery_task_revoke_failed",
                celery_task_id=celery_task_id,
                error=str(exc),
                status="error",
            )
