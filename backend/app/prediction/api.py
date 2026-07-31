"""Prediction HTTP API.

Routes orchestrate dependency-injected services only.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.prediction.dependencies import (
    get_prediction_export_service,
    get_prediction_service,
)
from app.prediction.export import PredictionExportService
from app.prediction.schemas import PredictionListRead, PredictionRead
from app.prediction.service import PredictionService
from app.shared.response.schemas import SuccessResponse

router = APIRouter(prefix="/api/v1", tags=["prediction"])


@router.get(
    "/audio/{audio_id}/prediction",
    response_model=SuccessResponse[PredictionRead],
    summary="Get the final prediction for an audio asset",
)
async def get_audio_prediction(
    audio_id: UUID,
    service: PredictionService = Depends(get_prediction_service),
) -> SuccessResponse[PredictionRead]:
    data = await service.get_prediction(audio_id)
    return SuccessResponse(message="Prediction retrieved", data=data)


@router.get(
    "/batches/{batch_id}/predictions",
    response_model=SuccessResponse[PredictionListRead],
    summary="List predictions for a batch",
)
async def get_batch_predictions(
    batch_id: UUID,
    service: PredictionService = Depends(get_prediction_service),
) -> SuccessResponse[PredictionListRead]:
    predictions = await service.list_by_batch(batch_id)
    data = PredictionListRead(count=len(predictions), predictions=predictions)
    return SuccessResponse(message="Batch predictions retrieved", data=data)


@router.get(
    "/jobs/{job_id}/predictions",
    response_model=SuccessResponse[PredictionListRead],
    summary="List predictions for a job",
)
async def get_job_predictions(
    job_id: UUID,
    service: PredictionService = Depends(get_prediction_service),
) -> SuccessResponse[PredictionListRead]:
    predictions = await service.list_by_job(job_id)
    data = PredictionListRead(count=len(predictions), predictions=predictions)
    return SuccessResponse(message="Job predictions retrieved", data=data)


@router.get(
    "/batches/{batch_id}/predictions/export.json",
    response_model=SuccessResponse[dict],
    summary="Export batch predictions as JSON (public fields only)",
)
async def export_batch_predictions_json(
    batch_id: UUID,
    service: PredictionExportService = Depends(get_prediction_export_service),
) -> SuccessResponse[dict]:
    payload = await service.export_json(batch_id)
    return SuccessResponse(
        message="Batch predictions exported",
        data={"batch_id": str(batch_id), "count": len(payload), "results": payload},
    )
