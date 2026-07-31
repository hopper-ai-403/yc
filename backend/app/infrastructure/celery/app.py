"""Celery application factory and registered instance."""

from celery import Celery

from app.config.settings import get_settings


def create_celery_app() -> Celery:
    """Create and configure the Celery application."""
    settings = get_settings()

    app = Celery(
        "audio_intelligence",
        broker=settings.celery.broker_url,
        backend=settings.celery.result_backend,
        include=["app.infrastructure.celery.tasks"],
    )

    app.conf.update(
        task_track_started=settings.celery.task_track_started,
        task_always_eager=settings.celery.task_always_eager,
        worker_prefetch_multiplier=settings.celery.worker_prefetch_multiplier,
        task_acks_late=settings.celery.task_acks_late,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_default_queue="default",
        task_routes={
            "app.infrastructure.celery.tasks.heartbeat": {"queue": "default"},
            "app.infrastructure.celery.tasks.process_batch": {"queue": "default"},
            "app.infrastructure.celery.tasks.process_audio": {"queue": "default"},
            "app.infrastructure.celery.tasks.finalize_job": {"queue": "default"},
        },
    )

    return app


celery_app: Celery = create_celery_app()
