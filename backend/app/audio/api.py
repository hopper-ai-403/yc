"""Audio HTTP API.

Routes orchestrate dependency-injected services only.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.audio.dependencies import get_audio_query_service
from app.audio.schemas import AudioAssetRead, AudioDownloadData, AudioMetadataRead
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
