"""Health check endpoints.

Purpose: Verify platform component readiness.
Responsibilities: Liveness and dependency health probes.
Dependencies: Database, Redis, Storage, Celery worker.
Extension points: Add new dependency probes as services are introduced.
"""

from app.health.router import router

__all__ = ["router"]
