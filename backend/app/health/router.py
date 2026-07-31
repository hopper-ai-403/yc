"""Health check API routes.

Routes only orchestrate dependency-injected health services.
No business logic lives here.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.config.settings import Settings, get_settings
from app.health.schemas import ComponentHealth, HealthData
from app.health.service import HealthService
from app.infrastructure.r2.client import CloudflareR2Storage
from app.infrastructure.redis.client import RedisClient, get_redis_client
from app.shared.database.session import get_engine
from app.shared.response.schemas import SuccessResponse

router = APIRouter(tags=["Health"])


def _status_for(component: ComponentHealth) -> int:
    if component.status == "healthy":
        return status.HTTP_200_OK
    return status.HTTP_503_SERVICE_UNAVAILABLE


def get_health_service(
    request: Request,
    settings: Settings = Depends(get_settings),
    redis_client: RedisClient = Depends(get_redis_client),
) -> HealthService:
    """Construct HealthService via dependency injection."""
    del request
    storage = CloudflareR2Storage(settings.r2)
    return HealthService(
        engine=get_engine(),
        redis_client=redis_client,
        storage=storage,
        celery_broker_url=settings.celery.broker_url,
    )


@router.get(
    "/health",
    response_model=SuccessResponse[HealthData],
    summary="Application liveness probe",
)
async def health(
    settings: Settings = Depends(get_settings),
) -> SuccessResponse[HealthData]:
    """Return overall application liveness."""
    return SuccessResponse(
        message="Service is healthy",
        data=HealthData(
            status="healthy",
            service=settings.logging.service_name,
            version=settings.app.version,
            environment=settings.app.environment,
        ),
    )


@router.get(
    "/health/database",
    response_model=SuccessResponse[ComponentHealth],
    summary="Database health probe",
)
async def health_database(
    service: HealthService = Depends(get_health_service),
) -> JSONResponse:
    """Return database connectivity status."""
    result = await service.check_database()
    payload = SuccessResponse(message="Database health check", data=result)
    return JSONResponse(
        status_code=_status_for(result),
        content=payload.model_dump(),
    )


@router.get(
    "/health/redis",
    response_model=SuccessResponse[ComponentHealth],
    summary="Redis health probe",
)
async def health_redis(
    service: HealthService = Depends(get_health_service),
) -> JSONResponse:
    """Return Redis connectivity status."""
    result = await service.check_redis()
    payload = SuccessResponse(message="Redis health check", data=result)
    return JSONResponse(
        status_code=_status_for(result),
        content=payload.model_dump(),
    )


@router.get(
    "/health/storage",
    response_model=SuccessResponse[ComponentHealth],
    summary="Object storage health probe",
)
async def health_storage(
    service: HealthService = Depends(get_health_service),
) -> JSONResponse:
    """Return object storage configuration/readiness status."""
    result = await service.check_storage()
    payload = SuccessResponse(message="Storage health check", data=result)
    return JSONResponse(
        status_code=_status_for(result),
        content=payload.model_dump(),
    )


@router.get(
    "/health/worker",
    response_model=SuccessResponse[ComponentHealth],
    summary="Celery worker health probe",
)
async def health_worker(
    service: HealthService = Depends(get_health_service),
) -> JSONResponse:
    """Return Celery worker availability status."""
    result = await service.check_worker()
    payload = SuccessResponse(message="Worker health check", data=result)
    return JSONResponse(
        status_code=_status_for(result),
        content=payload.model_dump(),
    )


@router.get(
    "/health/ready",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Readiness probe aggregating all dependencies",
)
async def health_ready(
    service: HealthService = Depends(get_health_service),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Aggregate dependency health for orchestrator readiness checks."""
    report = await service.check_all()
    all_healthy = all(component.status == "healthy" for component in report.values())
    http_status = (
        status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    components = {name: component.model_dump() for name, component in report.items()}
    payload = SuccessResponse(
        message="Readiness check",
        data={
            "status": "healthy" if all_healthy else "unhealthy",
            "service": settings.logging.service_name,
            "components": components,
        },
    )
    return JSONResponse(status_code=http_status, content=payload.model_dump())
