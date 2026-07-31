"""System operations service: metrics, workers, benchmark."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from app.config.settings import Settings
from app.infrastructure.database.health import check_database_connection
from app.infrastructure.redis.client import RedisClient
from app.infrastructure.redis.job_progress import JobProgressCache
from app.infrastructure.warmup import get_warmup_state, is_model_loaded
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider
from app.system.benchmark import BenchmarkRunner
from app.system.schemas import BenchmarkRead, SystemMetricsRead, WorkerRead, WorkersRead

logger = get_logger(__name__)


class SystemService:
    """Operational readiness and benchmarking queries."""

    def __init__(
        self,
        *,
        settings: Settings,
        engine: AsyncEngine,
        redis_client: RedisClient,
        storage: StorageProvider,
        progress_cache: JobProgressCache,
        benchmark: BenchmarkRunner,
    ) -> None:
        self._settings = settings
        self._engine = engine
        self._redis = redis_client
        self._storage = storage
        self._cache = progress_cache
        self._benchmark = benchmark

    async def get_metrics(self) -> SystemMetricsRead:
        database = await check_database_connection(self._engine)
        redis_ok = await self._redis_ok()
        r2_ok = await self._r2_ok()
        celery_ok = self._celery_ok()
        workers = await self._safe_workers()
        model_loaded = is_model_loaded(self._settings.speech.model_name)
        if not get_warmup_state().warmup_enabled:
            model_loaded = True

        return SystemMetricsRead(
            database=database,
            redis=redis_ok,
            r2=r2_ok,
            celery=celery_ok,
            model_loaded=model_loaded,
            worker_count=len(workers),
            system_version=self._settings.app.version,
            checked_at=datetime.now(timezone.utc),
        )

    async def list_workers(self) -> WorkersRead:
        payloads = await self._safe_workers()
        workers: list[WorkerRead] = []
        for payload in payloads:
            stale = self._cache.is_worker_stale(payload)
            timestamp = payload.get("timestamp")
            last_heartbeat: datetime | None = None
            if isinstance(timestamp, str) and timestamp:
                try:
                    last_heartbeat = datetime.fromisoformat(timestamp)
                except ValueError:
                    last_heartbeat = None
            workers.append(
                WorkerRead(
                    worker_id=str(payload.get("worker_id", "unknown")),
                    status=str(payload.get("status", "unknown")),
                    last_heartbeat=last_heartbeat,
                    stale=stale,
                )
            )
        stale_count = sum(1 for worker in workers if worker.stale)
        return WorkersRead(
            worker_count=len(workers),
            stale_count=stale_count,
            workers=workers,
        )

    async def run_benchmark(self, batch_id: UUID) -> BenchmarkRead:
        return await self._benchmark.run(batch_id)

    async def _redis_ok(self) -> bool:
        try:
            return bool(await self._redis.health_check())
        except Exception:
            return False

    async def _r2_ok(self) -> bool:
        try:
            return bool(await self._storage.health_check())
        except Exception:
            return False

    def _celery_ok(self) -> bool:
        try:
            from app.infrastructure.celery.app import celery_app

            with celery_app.connection() as connection:
                connection.ensure_connection(max_retries=1)
            return True
        except Exception:
            logger.warning("celery_broker_ping_failed")
            return False

    async def _safe_workers(self) -> list[dict]:
        try:
            return await self._cache.list_workers()
        except Exception:
            logger.warning("worker_listing_failed")
            return []
