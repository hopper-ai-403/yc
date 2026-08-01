"""Evaluation HTTP API.

Routes orchestrate dependency-injected services only.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.evaluation.dependencies import get_evaluation_service
from app.evaluation.schemas import (
    BatchDeleteRead,
    BatchExportJsonRead,
    BatchExportsRead,
    BatchMetricsRead,
    BatchRunRead,
    BatchStatusRead,
)
from app.evaluation.service import EvaluationService
from app.shared.response.schemas import SuccessResponse

router = APIRouter(prefix="/api/v1", tags=["evaluation"])


@router.post(
    "/batches/{batch_id}/run",
    response_model=SuccessResponse[BatchRunRead],
    summary="Execute a batch asynchronously",
)
async def run_batch(
    batch_id: UUID,
    service: EvaluationService = Depends(get_evaluation_service),
) -> SuccessResponse[BatchRunRead]:
    data = await service.run_batch(batch_id)
    message = (
        "Batch execution already in progress"
        if data.already_running
        else "Batch execution queued"
    )
    return SuccessResponse(message=message, data=data)


@router.delete(
    "/batches/{batch_id}",
    response_model=SuccessResponse[BatchDeleteRead],
    summary="Delete a batch, cancel its job, and free queue capacity",
)
async def delete_batch(
    batch_id: UUID,
    service: EvaluationService = Depends(get_evaluation_service),
) -> SuccessResponse[BatchDeleteRead]:
    data = await service.delete_batch(batch_id)
    return SuccessResponse(
        message="Batch deleted",
        data=data,
    )


@router.get(
    "/batches/{batch_id}/status",
    response_model=SuccessResponse[BatchStatusRead],
    summary="Monitor batch execution progress",
)
async def get_batch_status(
    batch_id: UUID,
    service: EvaluationService = Depends(get_evaluation_service),
) -> SuccessResponse[BatchStatusRead]:
    data = await service.get_status(batch_id)
    return SuccessResponse(message="Batch status retrieved", data=data)


@router.get(
    "/batches/{batch_id}/export/csv",
    summary="Download assessment CSV (filename,result_json)",
)
async def export_batch_csv(
    batch_id: UUID,
    service: EvaluationService = Depends(get_evaluation_service),
) -> Response:
    csv_text = await service.export_csv(batch_id)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="results-{batch_id}.csv"',
        },
    )


@router.get(
    "/batches/{batch_id}/export/json",
    response_model=SuccessResponse[BatchExportJsonRead],
    summary="Download assessment JSON (public fields only)",
)
async def export_batch_json(
    batch_id: UUID,
    service: EvaluationService = Depends(get_evaluation_service),
) -> SuccessResponse[BatchExportJsonRead]:
    results = await service.export_json(batch_id)
    data = BatchExportJsonRead(batch_id=batch_id, count=len(results), results=results)
    return SuccessResponse(message="Batch export retrieved", data=data)


@router.get(
    "/batches/{batch_id}/metrics",
    response_model=SuccessResponse[BatchMetricsRead],
    summary="Get batch evaluation metrics",
)
async def get_batch_metrics(
    batch_id: UUID,
    service: EvaluationService = Depends(get_evaluation_service),
) -> SuccessResponse[BatchMetricsRead]:
    data = await service.get_metrics(batch_id)
    return SuccessResponse(message="Batch metrics retrieved", data=data)


@router.get(
    "/batches/{batch_id}/exports",
    response_model=SuccessResponse[BatchExportsRead],
    summary="Get signed URLs for batch export artifacts",
)
async def get_batch_exports(
    batch_id: UUID,
    service: EvaluationService = Depends(get_evaluation_service),
) -> SuccessResponse[BatchExportsRead]:
    data = await service.get_exports(batch_id)
    return SuccessResponse(message="Batch exports retrieved", data=data)
