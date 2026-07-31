"""Celery worker lifecycle signals.

worker_ready: warm up singleton models and recover orphaned jobs.
worker_shutdown: graceful shutdown logging and cleanup.
"""

from __future__ import annotations

from celery.signals import worker_ready, worker_shutdown

from app.config.settings import get_settings
from app.infrastructure.warmup import warmup_models
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


@worker_ready.connect
def on_worker_ready(sender: object = None, **kwargs: object) -> None:
    """Warm up singleton models and recover orphaned jobs at worker boot."""
    settings = get_settings()
    try:
        state = warmup_models(settings.speech, settings.performance)
        logger.info(
            "worker_ready_warmup",
            loaded_models=state.loaded_models,
            load_durations_ms=state.load_durations_ms,
            status="ok",
        )
    except Exception as exc:
        # Warmup failure must not prevent worker boot; first task will retry load.
        logger.error(
            "worker_warmup_failed",
            error=str(exc),
            status="degraded",
        )

    try:
        from app.infrastructure.celery.runtime import run_async, with_session
        from app.jobs.factory import build_job_service

        async def _recover() -> int:
            async def handler(session):  # type: ignore[no-untyped-def]
                service = build_job_service(session)
                return await service.recover_orphaned_jobs(
                    threshold_seconds=settings.performance.orphaned_job_threshold_seconds,
                )

            return await with_session(handler)

        recovered = run_async(_recover())
        if recovered:
            logger.warning(
                "orphaned_jobs_recovered",
                recovered_count=recovered,
                status="requeued",
            )
    except Exception as exc:
        logger.error("orphaned_job_recovery_failed", error=str(exc))


@worker_shutdown.connect
def on_worker_shutdown(sender: object = None, **kwargs: object) -> None:
    """Log graceful worker shutdown."""
    logger.info(
        "worker_shutdown_graceful",
        status="stopping",
        service="worker",
    )
