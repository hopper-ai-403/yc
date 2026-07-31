"""Celery tasks for job orchestration and audio preprocessing (no AI inference).

Purpose: Drive asynchronous batch lifecycle and preprocessing pipeline.
Responsibilities: process_batch, process_audio (→ preprocess), finalize, heartbeat.
Dependencies: JobService, PreprocessingService, Redis progress cache, async DB session.
Extension points: Replace preprocess with preprocess → infer → aggregate.
"""

from __future__ import annotations

import socket
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from celery import chord, group

from app.config.settings import get_settings
from app.infrastructure.celery.app import celery_app
from app.infrastructure.celery.runtime import run_async, with_session
from app.infrastructure.redis.client import get_redis_client
from app.infrastructure.redis.job_progress import JobProgressCache
from app.jobs.factory import build_job_service
from app.shared.domain.enums import AudioStatus, JobStatus
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


def _worker_id(task: Any) -> str:
    hostname = getattr(task.request, "hostname", None)
    return str(hostname or socket.gethostname())


@celery_app.task(name="app.infrastructure.celery.tasks.heartbeat", bind=True)
def heartbeat(self: Any) -> dict[str, str]:
    """Return a heartbeat payload and refresh worker:{hostname} in Redis."""
    worker = _worker_id(self)
    payload = {
        "status": "ok",
        "task_id": self.request.id or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "worker",
        "worker_id": worker,
    }

    async def _cache() -> None:
        settings = get_settings().jobs
        cache = JobProgressCache(get_redis_client(), settings)
        await cache.set_worker_heartbeat(worker, payload)
        logger.info(
            "worker_heartbeat",
            worker_id=worker,
            status="ok",
        )

    try:
        run_async(_cache())
    except Exception:
        logger.exception("worker_heartbeat_cache_failed", worker_id=worker)
    return payload


@celery_app.task(name="app.infrastructure.celery.tasks.process_batch", bind=True)
def process_batch(self: Any, job_id: str) -> dict[str, Any]:
    """Orchestrate a job: recover stale work, start job, fan out audio tasks."""
    worker = _worker_id(self)
    job_uuid = UUID(job_id)

    async def _prepare() -> list[str]:
        async def handler(session):  # type: ignore[no-untyped-def]
            service = build_job_service(session)
            if await service.is_cancelled(job_uuid):
                logger.info("job_skipped_cancelled", job_id=job_id, worker_id=worker)
                return []
            await service.recover_stale_processing(job_uuid)
            job = await service.start_job(job_uuid, worker_id=worker)
            if job.status is JobStatus.CANCELLED:
                return []
            audio_ids = await service.list_processable_audio_ids(job_uuid)
            return [str(audio_id) for audio_id in audio_ids]

        return await with_session(handler)

    audio_ids = run_async(_prepare())
    if not audio_ids:
        run_async(_finalize_job(job_uuid, worker))
        return {"job_id": job_id, "audio_count": 0, "status": "empty_or_cancelled"}

    header = group(process_audio.s(audio_id, job_id) for audio_id in audio_ids)
    async_result = chord(header)(finalize_job.s(job_id))
    return {
        "job_id": job_id,
        "audio_count": len(audio_ids),
        "chord_id": str(async_result.id),
        "worker_id": worker,
    }


@celery_app.task(
    name="app.infrastructure.celery.tasks.process_audio",
    bind=True,
    max_retries=3,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def process_audio(self: Any, audio_id: str, job_id: str) -> dict[str, Any]:
    """Process a single audio asset via the preprocessing pipeline (no AI)."""
    worker = _worker_id(self)
    return run_async(_process_audio(UUID(audio_id), UUID(job_id), worker))


@celery_app.task(name="app.infrastructure.celery.tasks.finalize_job")
def finalize_job(results: list[Any] | None, job_id: str) -> dict[str, Any]:
    """Aggregate per-audio results and complete or fail the parent job."""
    worker = socket.gethostname()
    return run_async(_finalize_job(UUID(job_id), worker, results=results))


async def _process_audio(
    audio_id: UUID,
    job_id: UUID,
    worker_id: str,
) -> dict[str, Any]:
    started = time.perf_counter()

    async def begin(session):  # type: ignore[no-untyped-def]
        service = build_job_service(session)
        if await service.is_cancelled(job_id):
            return {"done": True, "payload": {
                "audio_id": str(audio_id),
                "status": "skipped_cancelled",
                "worker_id": worker_id,
            }}

        status = await service.get_audio_status(audio_id)
        if status is None:
            return {"done": True, "payload": {
                "audio_id": str(audio_id),
                "status": "missing",
                "worker_id": worker_id,
            }}

        from app.jobs.state_machine import is_audio_terminal_success

        if is_audio_terminal_success(status):
            logger.info(
                "audio_skipped_idempotent",
                job_id=str(job_id),
                audio_id=str(audio_id),
                worker_id=worker_id,
                status=status.value,
            )
            return {"done": True, "payload": {
                "audio_id": str(audio_id),
                "status": "already_completed",
                "worker_id": worker_id,
            }}

        if status is AudioStatus.FAILED:
            return {"done": True, "payload": {
                "audio_id": str(audio_id),
                "status": "failed_skip",
                "worker_id": worker_id,
            }}

        if status in {AudioStatus.UPLOADED, AudioStatus.VALIDATED}:
            await service.transition_audio(
                audio_id,
                AudioStatus.QUEUED,
                job_id=job_id,
                worker_id=worker_id,
            )
            status = AudioStatus.QUEUED

        if status is AudioStatus.QUEUED:
            logger.info(
                "audio_started",
                job_id=str(job_id),
                audio_id=str(audio_id),
                worker_id=worker_id,
            )
            await service.transition_audio(
                audio_id,
                AudioStatus.PROCESSING,
                job_id=job_id,
                worker_id=worker_id,
            )
        elif status is AudioStatus.PROCESSING:
            logger.info(
                "audio_resumed",
                job_id=str(job_id),
                audio_id=str(audio_id),
                worker_id=worker_id,
            )
        else:
            return {"done": True, "payload": {
                "audio_id": str(audio_id),
                "status": f"unexpected_{status.value}",
                "worker_id": worker_id,
            }}
        return {"done": False, "payload": None}

    begin_result = await with_session(begin)
    if begin_result["done"]:
        return begin_result["payload"]

    # Preprocessing stage (no AI). Transient errors re-raised for Celery retry.
    from app.audio.preprocessing.exceptions import (
        AudioValidationException,
        InvalidMetadataException,
        PreprocessingException,
        PreprocessingTimeoutException,
    )
    from app.audio.preprocessing.factory import build_preprocessing_service

    try:
        async def preprocess(session):  # type: ignore[no-untyped-def]
            service = build_preprocessing_service(session)
            return await service.preprocess_audio(audio_id)

        await with_session(preprocess)
    except PreprocessingTimeoutException:
        raise TimeoutError("preprocessing timed out") from None
    except (AudioValidationException, InvalidMetadataException) as exc:
        await with_session(_mark_audio_failed(audio_id, job_id, worker_id, str(exc)))
        return {
            "audio_id": str(audio_id),
            "status": "FAILED",
            "error": str(exc),
            "worker_id": worker_id,
        }
    except PreprocessingException as exc:
        # Storage / ffmpeg failures: mark failed for this attempt; Celery may retry
        # ConnectionError/TimeoutError only. Non-transient preprocessing errors fail asset.
        await with_session(_mark_audio_failed(audio_id, job_id, worker_id, str(exc)))
        return {
            "audio_id": str(audio_id),
            "status": "FAILED",
            "error": str(exc),
            "code": getattr(exc, "code", "PREPROCESSING_ERROR"),
            "worker_id": worker_id,
        }

    async def finish(session):  # type: ignore[no-untyped-def]
        service = build_job_service(session)
        if await service.is_cancelled(job_id):
            return {
                "audio_id": str(audio_id),
                "status": "cancelled_midflight",
                "worker_id": worker_id,
            }

        status = await service.get_audio_status(audio_id)
        from app.jobs.state_machine import is_audio_terminal_success

        if status is not None and is_audio_terminal_success(status):
            return {
                "audio_id": str(audio_id),
                "status": "already_completed",
                "worker_id": worker_id,
            }

        await service.transition_audio(
            audio_id,
            AudioStatus.COMPLETED,
            job_id=job_id,
            worker_id=worker_id,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "audio_completed",
            job_id=str(job_id),
            audio_id=str(audio_id),
            worker_id=worker_id,
            duration_ms=duration_ms,
            status="COMPLETED",
        )
        return {
            "audio_id": str(audio_id),
            "status": "COMPLETED",
            "duration_ms": duration_ms,
            "worker_id": worker_id,
        }

    return await with_session(finish)


def _mark_audio_failed(
    audio_id: UUID,
    job_id: UUID,
    worker_id: str,
    error_message: str,
):  # type: ignore[no-untyped-def]
    async def handler(session):  # type: ignore[no-untyped-def]
        service = build_job_service(session)
        status = await service.get_audio_status(audio_id)
        if status is not None and status is not AudioStatus.FAILED:
            try:
                await service.transition_audio(
                    audio_id,
                    AudioStatus.FAILED,
                    job_id=job_id,
                    worker_id=worker_id,
                )
            except Exception:
                logger.exception(
                    "audio_fail_transition_error",
                    audio_id=str(audio_id),
                    job_id=str(job_id),
                )
        logger.error(
            "audio_preprocessing_failed",
            audio_id=str(audio_id),
            job_id=str(job_id),
            worker_id=worker_id,
            error=error_message,
            status="FAILED",
        )
        return None

    return handler


async def _finalize_job(
    job_id: UUID,
    worker_id: str,
    *,
    results: list[Any] | None = None,
) -> dict[str, Any]:
    async def handler(session):  # type: ignore[no-untyped-def]
        service = build_job_service(session)
        if await service.is_cancelled(job_id):
            job = await service.get_job(job_id)
            return {"job_id": str(job_id), "status": job.status.value}

        job_entity = await service.update_progress(job_id)
        unfinished = await service.list_processable_audio_ids(job_id)
        if unfinished:
            await service.fail_job(
                job_id,
                error_message=f"Unresolved audio assets remain: {len(unfinished)}",
                worker_id=worker_id,
            )
            status = JobStatus.FAILED.value
        else:
            await service.complete_job(job_id, worker_id=worker_id)
            status = JobStatus.COMPLETED.value

        return {
            "job_id": str(job_id),
            "status": status,
            "processed_files": job_entity.processed_files,
            "failed_files": job_entity.failed_files,
            "results_count": len(results or []),
            "worker_id": worker_id,
        }

    return await with_session(handler)
