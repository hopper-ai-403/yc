"""Audio HTTP API.

Routes orchestrate dependency-injected services only.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.audio.dependencies import get_audio_query_service
from app.audio.schemas import (
    AudioAnalysisRead,
    AudioAssetRead,
    AudioDownloadData,
    AudioMetadataRead,
    AudioSegmentsRead,
    AudioTechnicalRead,
)
from app.audio.service import AudioQueryService
from app.shared.response.schemas import SuccessResponse

router = APIRouter(prefix="/api/v1", tags=["Audio"])


@router.get(
    "/audio/{audio_id}",
    response_model=SuccessResponse[AudioAssetRead],
    summary="Get audio asset details",
)
async def get_audio(
    audio_id: UUID,
    service: AudioQueryService = Depends(get_audio_query_service),
) -> SuccessResponse[AudioAssetRead]:
    data = await service.get_audio(audio_id)
    return SuccessResponse(message="Audio asset retrieved", data=data)


@router.get(
    "/audio/{audio_id}/metadata",
    response_model=SuccessResponse[AudioMetadataRead],
    summary="Get preprocessing metadata for an audio asset",
)
async def get_audio_metadata(
    audio_id: UUID,
    service: AudioQueryService = Depends(get_audio_query_service),
) -> SuccessResponse[AudioMetadataRead]:
    data = await service.get_metadata(audio_id)
    return SuccessResponse(message="Audio metadata retrieved", data=data)


@router.get(
    "/audio/{audio_id}/download",
    response_model=SuccessResponse[AudioDownloadData],
    summary="Get a signed download URL (normalized preferred)",
)
async def download_audio(
    audio_id: UUID,
    service: AudioQueryService = Depends(get_audio_query_service),
) -> SuccessResponse[AudioDownloadData]:
    data = await service.get_download_url(audio_id)
    return SuccessResponse(message="Download URL generated", data=data)


@router.get(
    "/audio/{audio_id}/analysis",
    response_model=SuccessResponse[AudioAnalysisRead],
    summary="Get shared analysis artifacts for an audio asset",
)
async def get_audio_analysis(
    audio_id: UUID,
    service: AudioQueryService = Depends(get_audio_query_service),
) -> SuccessResponse[AudioAnalysisRead]:
    data = await service.get_analysis(audio_id)
    return SuccessResponse(message="Audio analysis retrieved", data=data)


@router.get(
    "/audio/{audio_id}/segments",
    response_model=SuccessResponse[AudioSegmentsRead],
    summary="Get speech and silence segments",
)
async def get_audio_segments(
    audio_id: UUID,
    service: AudioQueryService = Depends(get_audio_query_service),
) -> SuccessResponse[AudioSegmentsRead]:
    data = await service.get_segments(audio_id)
    return SuccessResponse(message="Audio segments retrieved", data=data)


@router.get(
    "/audio/{audio_id}/technical",
    response_model=SuccessResponse[AudioTechnicalRead],
    summary="Get technical intelligence results for an audio asset",
)
async def get_audio_technical(
    audio_id: UUID,
    service: AudioQueryService = Depends(get_audio_query_service),
) -> SuccessResponse[AudioTechnicalRead]:
    data = await service.get_technical(audio_id)
    return SuccessResponse(message="Audio technical results retrieved", data=data)
