"""Redis-backed job progress and worker heartbeat cache.

Purpose: Cache live job orchestration state for fast progress reads.
Responsibilities: status/progress/heartbeat key management with TTLs.
Dependencies: RedisClient, JobSettings.
Extension points: Pub/sub progress push, multi-worker lease keys.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
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

    async def has_fresh_job_heartbeat(self, job_id: UUID) -> bool:
        """Return True if a worker heartbeat exists for the job."""
        client = await self._ensure_client()
        return bool(await client.exists(self.heartbeat_key(job_id)))

    async def list_workers(self) -> list[dict[str, Any]]:
        """Return live worker heartbeat payloads (TTL-scoped keys)."""
        client = await self._ensure_client()
        workers: list[dict[str, Any]] = []
        cursor: int = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match="worker:*", count=100)
            for key in keys:
                raw = await client.get(key)
                if raw is None:
                    continue
                try:
                    payload = json.loads(str(raw))
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    payload.setdefault("worker_id", str(key).split(":", 1)[1])
                    workers.append(payload)
            if int(cursor) == 0:
                break
        return workers

    def is_worker_stale(self, payload: dict[str, Any]) -> bool:
        """Detect a stale worker from its heartbeat timestamp and TTL budget."""
        raw = payload.get("timestamp")
        if not isinstance(raw, str) or not raw:
            return True
        try:
            timestamp = datetime.fromisoformat(raw)
        except ValueError:
            return True
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - timestamp).total_seconds()
        return age_seconds > self._settings.heartbeat_ttl_seconds

    async def set_worker_heartbeat(
        self, hostname: str, payload: dict[str, Any]
    ) -> None:
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
        if self._redis._client is None:
            await self._redis.connect()
        return self._redis.client
