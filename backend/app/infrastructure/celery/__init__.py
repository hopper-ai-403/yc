"""Celery application infrastructure."""

from app.infrastructure.celery.app import celery_app, create_celery_app

__all__ = ["celery_app", "create_celery_app"]
