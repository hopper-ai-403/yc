"""Celery tasks.

Sprint 0 includes only a heartbeat task for worker health verification.
Business tasks are deferred to later sprints.
"""

from datetime import datetime, timezone
from typing import Any

from app.infrastructure.celery.app import celery_app


@celery_app.task(name="app.infrastructure.celery.tasks.heartbeat", bind=True)
def heartbeat(self: Any) -> dict[str, str]:
    """Return a heartbeat payload confirming the worker is alive."""
    return {
        "status": "ok",
        "task_id": self.request.id or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "worker",
    }
