"""System operations HTTP API."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.shared.response.schemas import SuccessResponse
from app.system.dependencies import get_system_service
from app.system.schemas import BenchmarkRead, SystemMetricsRead, WorkersRead
from app.system.service import SystemService

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get(
    "/metrics",
    response_model=SuccessResponse[SystemMetricsRead],
    summary="Aggregate system operational metrics",
)
async def get_system_metrics(
    service: SystemService = Depends(get_system_service),
) -> SuccessResponse[SystemMetricsRead]:
    data = await service.get_metrics()
    return SuccessResponse(message="System metrics retrieved", data=data)


@router.get(
    "/benchmark",
    response_model=SuccessResponse[BenchmarkRead],
    summary="Benchmark a completed evaluation batch",
)
async def get_system_benchmark(
    batch_id: UUID,
    service: SystemService = Depends(get_system_service),
) -> SuccessResponse[BenchmarkRead]:
    data = await service.run_benchmark(batch_id)
    return SuccessResponse(message="Benchmark generated", data=data)


@router.get(
    "/workers",
    response_model=SuccessResponse[WorkersRead],
    summary="List registered workers with stale detection",
)
async def get_system_workers(
    service: SystemService = Depends(get_system_service),
) -> SuccessResponse[WorkersRead]:
    data = await service.list_workers()
    return SuccessResponse(message="Workers retrieved", data=data)
