"""Job orchestration service.

Purpose: Own the job lifecycle and progress tracking for batch processing.
Responsibilities: create/queue/start/complete/fail/cancel/retry/update_progress.
Dependencies: JobRepository, Audio repositories, JobProgressCache, JobDispatcher.
Extension points: Stage pipelines (preprocess → infer → aggregate).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.audio.repository import AudioBatchRepository, AudioRepository
from app.config.settings import JobSettings
from app.infrastructure.redis.job_progress import JobProgressCache
from app.jobs.dispatcher import JobDispatcher
from app.jobs.exceptions import (
    JobNotFoundException,
    JobRetryExhaustedException,
    JobStateException,
)
from app.jobs.models import Job
from app.jobs.repository import JobRepository
from app.jobs.schemas import JobProgressData, JobRead
from app.jobs.state_machine import (
    is_audio_retriable,
    is_audio_terminal_success,
    validate_audio_transition,
    validate_job_transition,
)
from app.shared.domain.enums import AudioStatus, BatchStatus, JobStatus
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class JobService:
    """Coordinates asynchronous job lifecycle without performing AI work."""

    def __init__(
        self,
        *,
        settings: JobSettings,
        jobs: JobRepository,
        batches: AudioBatchRepository,
        assets: AudioRepository,
        progress_cache: JobProgressCache,
        dispatcher: JobDispatcher,
    ) -> None:
        self._settings = settings
        self._jobs = jobs
        self._batches = batches
        self._assets = assets
        self._progress = progress_cache
        self._dispatcher = dispatcher

    async def create_job(self, batch_id: UUID) -> Job:
        """Create a PENDING job for a batch if one does not already exist."""
        existing = await self._jobs.find_by_batch(batch_id)
        if existing is not None:
            return existing

        batch = await self._batches.find_by_id(batch_id)
        if batch is None:
            raise JobStateException(
                "Cannot create job for missing batch",
                details={"batch_id": str(batch_id)},
            )

        job = await self._jobs.create(
            Job(
                batch_id=batch_id,
                status=JobStatus.PENDING,
                progress=0,
                total_files=batch.total_files,
                processed_files=0,
                failed_files=0,
            )
        )
        await self._sync_cache(job)
        return job

    async def queue_job(self, job_id: UUID, *, countdown: int = 0) -> Job:
        """Transition PENDING/FAILED/CANCELLED → QUEUED and enqueue the worker."""
        job = await self._require_job(job_id)
        if job.status is JobStatus.QUEUED:
            task_id = self._dispatcher.enqueue_batch(job.id, countdown=countdown)
            await self._progress.set_celery_task_id(job.id, task_id)
            logger.info(
                "job_queue_idempotent",
                job_id=str(job.id),
                celery_task_id=task_id,
                status=job.status.value,
            )
            return job

        if job.status is JobStatus.RUNNING:
            raise JobStateException(
                "Job is already running",
                details={"job_id": str(job_id), "status": job.status.value},
            )

        validate_job_transition(job.status, JobStatus.QUEUED)
        job.status = JobStatus.QUEUED
        job.error_message = None
        job.completed_at = None
        await self._jobs.save(job)

        assets = await self._assets.find_by_batch(job.batch_id)
        for asset in assets:
            if is_audio_terminal_success(asset.processing_status):
                continue
            if asset.processing_status is AudioStatus.QUEUED:
                continue
            validate_audio_transition(asset.processing_status, AudioStatus.QUEUED)
            await self._assets.update_status(asset.id, AudioStatus.QUEUED)

        await self._batches.update_status(job.batch_id, BatchStatus.QUEUED)
        await self._sync_cache(job)

        task_id = self._dispatcher.enqueue_batch(job.id, countdown=countdown)
        await self._progress.set_celery_task_id(job.id, task_id)
        logger.info(
            "job_queued",
            job_id=str(job.id),
            celery_task_id=task_id,
            countdown=countdown,
            status=job.status.value,
        )
        return job

    async def start_job(self, job_id: UUID, *, worker_id: str | None = None) -> Job:
        """Transition QUEUED → RUNNING when the worker begins orchestration."""
        job = await self._require_job(job_id)
        if job.status is JobStatus.CANCELLED:
            raise JobStateException(
                "Cancelled job cannot be started",
                details={"job_id": str(job_id)},
            )
        if job.status is JobStatus.RUNNING:
            return job
        if job.status is JobStatus.PENDING:
            validate_job_transition(job.status, JobStatus.QUEUED)
            job.status = JobStatus.QUEUED

        validate_job_transition(job.status, JobStatus.RUNNING)
        job.status = JobStatus.RUNNING
        job.started_at = job.started_at or datetime.now(timezone.utc)
        job.error_message = None

        assets = await self._assets.find_by_batch(job.batch_id)
        job.total_files = len(assets)
        await self._jobs.save(job)
        await self._batches.update_status(job.batch_id, BatchStatus.PROCESSING)
        await self._sync_cache(job, worker_id=worker_id)

        logger.info(
            "job_started",
            job_id=str(job.id),
            worker_id=worker_id,
            total_files=job.total_files,
            status=job.status.value,
        )
        return job

    async def complete_job(self, job_id: UUID, *, worker_id: str | None = None) -> Job:
        """Mark a running job COMPLETED after all assets settle."""
        job = await self._require_job(job_id)
        if job.status is JobStatus.CANCELLED:
            return job
        if job.status is JobStatus.COMPLETED:
            return job

        validate_job_transition(job.status, JobStatus.COMPLETED)
        job = await self.update_progress(job_id)
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = None
        await self._jobs.save(job)
        await self._batches.update_status(job.batch_id, BatchStatus.COMPLETED)
        await self._sync_cache(job, worker_id=worker_id)

        duration_ms = self._elapsed_ms(job)
        logger.info(
            "job_completed",
            job_id=str(job.id),
            worker_id=worker_id,
            duration_ms=duration_ms,
            processed_files=job.processed_files,
            failed_files=job.failed_files,
            status=job.status.value,
        )
        return job

    async def fail_job(
        self,
        job_id: UUID,
        *,
        error_message: str,
        worker_id: str | None = None,
    ) -> Job:
        """Mark a job FAILED (orchestration-level failure)."""
        job = await self._require_job(job_id)
        if job.status is JobStatus.CANCELLED:
            return job
        if job.status is JobStatus.FAILED:
            job.error_message = error_message
            await self._jobs.save(job)
            await self._sync_cache(job, worker_id=worker_id)
            return job

        validate_job_transition(job.status, JobStatus.FAILED)
        job = await self.update_progress(job_id)
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = error_message[:1024]
        await self._jobs.save(job)
        await self._batches.update_status(job.batch_id, BatchStatus.FAILED)
        await self._sync_cache(job, worker_id=worker_id)

        logger.error(
            "job_failed",
            job_id=str(job.id),
            worker_id=worker_id,
            duration_ms=self._elapsed_ms(job),
            error_message=error_message,
            status=job.status.value,
        )
        return job

    async def cancel_job(self, job_id: UUID) -> Job:
        """Cancel a job that has not finished and free its Celery queue slot."""
        job = await self._require_job(job_id)
        if job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED}:
            return job

        validate_job_transition(job.status, JobStatus.CANCELLED)
        celery_task_id = await self._progress.get_celery_task_id(job.id)
        if celery_task_id:
            self._dispatcher.revoke_batch(celery_task_id)

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        await self._jobs.save(job)
        # Batch has no CANCELLED status; FAILED marks the upload as abandoned.
        if job.batch_id is not None:
            await self._batches.update_status(job.batch_id, BatchStatus.FAILED)
        await self._progress.clear_job(job.id)

        logger.info(
            "job_cancelled",
            job_id=str(job.id),
            celery_task_id=celery_task_id,
            status=job.status.value,
        )
        return job

    async def retry_job(self, job_id: UUID) -> Job:
        """Retry failed assets only with exponential backoff; never redo completed."""
        job = await self._require_job(job_id)
        if job.retry_count >= self._settings.max_retries:
            raise JobRetryExhaustedException(
                job.id,
                job.retry_count,
                self._settings.max_retries,
            )
        if job.status is JobStatus.RUNNING:
            raise JobStateException(
                "Cannot retry a running job",
                details={"job_id": str(job_id)},
            )
        if job.status is JobStatus.QUEUED:
            raise JobStateException(
                "Job is already queued",
                details={"job_id": str(job_id)},
            )

        assets = await self._assets.find_by_batch(job.batch_id)
        failed = [a for a in assets if is_audio_retriable(a.processing_status)]
        if not failed:
            raise JobStateException(
                "No failed audio assets to retry",
                details={"job_id": str(job_id)},
            )

        job.retry_count += 1
        job.error_message = None
        job.completed_at = None
        await self._jobs.save(job)

        for asset in failed:
            validate_audio_transition(asset.processing_status, AudioStatus.QUEUED)
            await self._assets.update_status(asset.id, AudioStatus.QUEUED)

        await self.update_progress(job_id)

        countdown = self._settings.retry_backoff_base_seconds * (
            2 ** (job.retry_count - 1)
        )
        logger.info(
            "retry_triggered",
            job_id=str(job.id),
            retry_count=job.retry_count,
            failed_assets=len(failed),
            countdown=countdown,
            status=job.status.value,
        )
        return await self.queue_job(job.id, countdown=countdown)

    async def update_progress(self, job_id: UUID) -> Job:
        """Recompute and persist progress counters from asset statuses."""
        job = await self._require_job(job_id)
        assets = await self._assets.find_by_batch(job.batch_id)
        total = len(assets)
        processed = sum(
            1 for a in assets if is_audio_terminal_success(a.processing_status)
        )
        failed = sum(1 for a in assets if a.processing_status is AudioStatus.FAILED)
        percentage = 0 if total == 0 else round((processed / total) * 100)

        job.total_files = total
        job.processed_files = processed
        job.failed_files = failed
        job.progress = max(0, min(100, percentage))
        await self._jobs.save(job)
        await self._sync_cache(job)
        return job

    async def get_job(self, job_id: UUID) -> JobRead:
        job = await self._require_job(job_id)
        return JobRead.from_entity(job)

    async def get_progress(self, job_id: UUID) -> JobProgressData:
        cached = await self._progress.get_progress(job_id)
        if cached is not None:
            return JobProgressData.model_validate(cached)
        job = await self.update_progress(job_id)
        return JobProgressData.from_entity(job)

    async def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobRead]:
        jobs = await self._jobs.list_jobs(status=status, limit=limit, offset=offset)
        return [JobRead.from_entity(job) for job in jobs]

    async def transition_audio(
        self,
        audio_id: UUID,
        new_status: AudioStatus,
        *,
        job_id: UUID | None = None,
        worker_id: str | None = None,
    ) -> None:
        """Validate and apply an audio status transition, then refresh job progress."""
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise JobStateException(
                "Audio asset not found",
                details={"audio_id": str(audio_id)},
            )
        if asset.processing_status is new_status:
            return
        if is_audio_terminal_success(
            asset.processing_status
        ) and is_audio_terminal_success(new_status):
            return

        validate_audio_transition(asset.processing_status, new_status)
        await self._assets.update_status(audio_id, new_status)

        resolved_job_id = job_id
        if resolved_job_id is None:
            job = await self._jobs.find_by_batch(asset.batch_id)
            resolved_job_id = job.id if job else None
        if resolved_job_id is not None:
            await self.update_progress(resolved_job_id)
            if worker_id:
                await self._progress.set_job_heartbeat(resolved_job_id, worker_id)

    async def is_cancelled(self, job_id: UUID) -> bool:
        job = await self._require_job(job_id)
        return job.status is JobStatus.CANCELLED

    async def get_audio_status(self, audio_id: UUID) -> AudioStatus | None:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            return None
        return asset.processing_status

    async def list_processable_audio_ids(self, job_id: UUID) -> list[UUID]:
        """Return audio ids that still need orchestration work (idempotent filter)."""
        job = await self._require_job(job_id)
        assets = await self._assets.find_by_batch(job.batch_id)
        processable: list[UUID] = []
        for asset in assets:
            if is_audio_terminal_success(asset.processing_status):
                continue
            if asset.processing_status is AudioStatus.FAILED:
                continue
            processable.append(asset.id)
        return processable

    async def recover_stale_processing(self, job_id: UUID) -> int:
        """Reset PROCESSING assets to QUEUED for worker recovery."""
        job = await self._require_job(job_id)
        assets = await self._assets.find_by_batch(job.batch_id)
        recovered = 0
        for asset in assets:
            if asset.processing_status is not AudioStatus.PROCESSING:
                continue
            validate_audio_transition(asset.processing_status, AudioStatus.QUEUED)
            await self._assets.update_status(asset.id, AudioStatus.QUEUED)
            recovered += 1
        if recovered:
            logger.info(
                "worker_recovery",
                job_id=str(job.id),
                recovered_assets=recovered,
            )
            await self.update_progress(job_id)
        return recovered

    async def recover_orphaned_jobs(self, *, threshold_seconds: int = 1800) -> int:
        """Requeue RUNNING jobs whose worker died (no fresh heartbeat).

        Recovery path: fail the orphaned job, reset stale PROCESSING assets,
        then requeue. Returns the number of recovered jobs.
        """
        active = await self._jobs.find_active()
        now = datetime.now(timezone.utc)
        recovered = 0
        for job in active:
            if job.status is not JobStatus.RUNNING:
                continue
            if job.started_at is None:
                continue
            started = job.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if (now - started).total_seconds() < threshold_seconds:
                continue
            try:
                fresh = await self._progress.has_fresh_job_heartbeat(job.id)
            except Exception:
                fresh = True  # Cache unavailable: do not recover blindly.
            if fresh:
                continue

            validate_job_transition(job.status, JobStatus.FAILED)
            job.status = JobStatus.FAILED
            job.error_message = "Orphaned job recovered: worker heartbeat lost"
            await self._jobs.save(job)

            await self.recover_stale_processing(job.id)
            await self.queue_job(job.id)
            recovered += 1
            logger.warning(
                "orphaned_job_recovered",
                job_id=str(job.id),
                started_at=started.isoformat(),
                status="requeued",
            )
        return recovered

    async def _require_job(self, job_id: UUID) -> Job:
        job = await self._jobs.find_by_id(job_id)
        if job is None:
            raise JobNotFoundException(job_id)
        return job

    async def _sync_cache(self, job: Job, *, worker_id: str | None = None) -> None:
        payload = JobProgressData.from_entity(job).model_dump(mode="json")
        await self._progress.set_status(job.id, job.status.value)
        await self._progress.set_progress(job.id, payload)
        if worker_id:
            await self._progress.set_job_heartbeat(job.id, worker_id)

    @staticmethod
    def _elapsed_ms(job: Job) -> int | None:
        if job.started_at is None:
            return None
        end = job.completed_at or datetime.now(timezone.utc)
        return int((end - job.started_at).total_seconds() * 1000)
