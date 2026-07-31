"""Redis-backed job progress and worker heartbeat cache.

Purpose: Cache live job orchestration state for fast progress reads.
Responsibilities: status/progress/heartbeat key management with TTLs.
Dependencies: RedisClient, JobSettings.
Extension points: Pub/sub progress push, multi-worker lease keys.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.config.settings import JobSettings
from app.infrastructure.redis.client import RedisClient


class JobProgressCache:
    """Caches job status, progress payloads, and worker heartbeats in Redis."""

    def __init__(self, redis: RedisClient, settings: JobSettings) -> None:
        self._redis = redis
        self._settings = settings

    @staticmethod
    def status_key(job_id: UUID) -> str:
        return f"job:{job_id}:status"

    @staticmethod
    def progress_key(job_id: UUID) -> str:
        return f"job:{job_id}:progress"

    @staticmethod
    def heartbeat_key(job_id: UUID) -> str:
        return f"job:{job_id}:heartbeat"

    @staticmethod
    def worker_key(hostname: str) -> str:
        return f"worker:{hostname}"

    async def set_status(self, job_id: UUID, status: str) -> None:
        client = await self._ensure_client()
        await client.set(
            self.status_key(job_id),
            status,
            ex=self._settings.progress_ttl_seconds,
        )

    async def get_status(self, job_id: UUID) -> str | None:
        client = await self._ensure_client()
        value = await client.get(self.status_key(job_id))
        return str(value) if value is not None else None

    async def set_progress(self, job_id: UUID, payload: dict[str, Any]) -> None:
        client = await self._ensure_client()
        await client.set(
            self.progress_key(job_id),
            json.dumps(payload),
            ex=self._settings.progress_ttl_seconds,
        )

    async def get_progress(self, job_id: UUID) -> dict[str, Any] | None:
        client = await self._ensure_client()
        raw = await client.get(self.progress_key(job_id))
        if raw is None:
            return None
        loaded = json.loads(str(raw))
        if not isinstance(loaded, dict):
            return None
        return loaded

    async def set_job_heartbeat(self, job_id: UUID, worker_id: str) -> None:
        client = await self._ensure_client()
        await client.set(
            self.heartbeat_key(job_id),
            worker_id,
            ex=self._settings.heartbeat_ttl_seconds,
        )

    async def set_worker_heartbeat(self, hostname: str, payload: dict[str, Any]) -> None:
        client = await self._ensure_client()
        await client.set(
            self.worker_key(hostname),
            json.dumps(payload),
            ex=self._settings.heartbeat_ttl_seconds,
        )

    async def clear_job(self, job_id: UUID) -> None:
        client = await self._ensure_client()
        await client.delete(
            self.status_key(job_id),
            self.progress_key(job_id),
            self.heartbeat_key(job_id),
        )

    async def _ensure_client(self):  # type: ignore[no-untyped-def]
        if self._redis._client is None:  # noqa: SLF001
            await self._redis.connect()
        return self._redis.client
