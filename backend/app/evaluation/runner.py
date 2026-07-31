"""Batch execution runner.

Validates a batch and queues its job for asynchronous processing.
Never blocks on processing; returns immediately.
"""

from __future__ import annotations

from uuid import UUID

from app.audio.repository import AudioBatchRepository
from app.evaluation.exceptions import (
    BatchNotFoundForEvaluationException,
    BatchNotRunnableException,
)
from app.evaluation.schemas import BatchRunRead
from app.jobs.exceptions import JobStateException
from app.jobs.service import JobService
from app.shared.domain.enums import JobStatus
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class BatchRunner:
    """Kick off batch processing via the job orchestration engine."""

    def __init__(
        self,
        *,
        batches: AudioBatchRepository,
        jobs: JobService,
    ) -> None:
        self._batches = batches
        self._jobs = jobs

    async def run(self, batch_id: UUID) -> BatchRunRead:
        batch = await self._batches.find_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundForEvaluationException(batch_id)
        if not batch.assets:
            raise BatchNotRunnableException(batch_id, reason="batch has no audio assets")

        job = await self._jobs.create_job(batch_id)

        if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
            logger.info(
                "batch_run_duplicate_prevented",
                batch_id=str(batch_id),
                job_id=str(job.id),
                status=job.status.value,
            )
            return BatchRunRead(
                batch_id=batch_id,
                job_id=job.id,
                status=job.status.value,
                queued=False,
                already_running=True,
            )

        try:
            job = await self._jobs.queue_job(job.id)
        except JobStateException as exc:
            if "already running" in str(exc):
                return BatchRunRead(
                    batch_id=batch_id,
                    job_id=job.id,
                    status=job.status.value,
                    queued=False,
                    already_running=True,
                )
            raise BatchNotRunnableException(batch_id, reason=str(exc)) from exc

        logger.info(
            "batch_run_queued",
            batch_id=str(batch_id),
            job_id=str(job.id),
            status=job.status.value,
        )
        return BatchRunRead(
            batch_id=batch_id,
            job_id=job.id,
            status=job.status.value,
            queued=True,
            already_running=False,
        )
