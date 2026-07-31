"""Health check service layer."""

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncEngine

from app.health.schemas import ComponentHealth
from app.infrastructure.database.health import check_database_connection
from app.infrastructure.redis.client import RedisClient
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


class HealthService:
    """Coordinates dependency health probes."""

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        redis_client: RedisClient,
        storage: StorageProvider,
        celery_broker_url: str,
    ) -> None:
        self._engine = engine
        self._redis_client = redis_client
        self._storage = storage
        self._celery_broker_url = celery_broker_url

    async def check_database(self) -> ComponentHealth:
        """Probe Neon PostgreSQL connectivity."""
        healthy = await check_database_connection(self._engine)
        logger.info(
            "health_check",
            component="database",
            status="healthy" if healthy else "unhealthy",
        )
        return ComponentHealth(
            status="healthy" if healthy else "unhealthy",
            component="database",
            details={"reachable": healthy},
        )

    async def check_redis(self) -> ComponentHealth:
        """Probe Redis connectivity."""
        healthy = await self._redis_client.health_check()
        logger.info(
            "health_check",
            component="redis",
            status="healthy" if healthy else "unhealthy",
        )
        return ComponentHealth(
            status="healthy" if healthy else "unhealthy",
            component="redis",
            details={"reachable": healthy},
        )

    async def check_storage(self) -> ComponentHealth:
        """Probe object storage readiness."""
        healthy = await self._storage.health_check()
        logger.info(
            "health_check",
            component="storage",
            status="healthy" if healthy else "unhealthy",
        )
        return ComponentHealth(
            status="healthy" if healthy else "unhealthy",
            component="storage",
            details={"configured": healthy},
        )

    async def check_worker(self) -> ComponentHealth:
        """Probe Celery worker availability via broker inspect."""
        try:
            probe = Celery(broker=self._celery_broker_url)
            inspector = probe.control.inspect(timeout=2.0)
            ping_result = inspector.ping() if inspector is not None else None
            healthy = bool(ping_result)
            details: dict[str, object] = {
                "workers": list(ping_result.keys()) if ping_result else [],
            }
        except Exception as exc:
            healthy = False
            details = {"error": str(exc)}

        logger.info(
            "health_check",
            component="worker",
            status="healthy" if healthy else "unhealthy",
        )
        return ComponentHealth(
            status="healthy" if healthy else "unhealthy",
            component="worker",
            details=details,
        )

    async def check_all(self) -> dict[str, ComponentHealth]:
        """Run all dependency health probes."""
        return {
            "database": await self.check_database(),
            "redis": await self.check_redis(),
            "storage": await self.check_storage(),
            "worker": await self.check_worker(),
        }
