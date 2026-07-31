"""Upload HTTP API.

Routes orchestrate dependency-injected services only.
"""

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.shared.response.schemas import SuccessResponse
from app.upload.dependencies import get_upload_service
from app.upload.exceptions import EmptyUploadException
from app.upload.schemas import UploadResultData
from app.upload.service import IncomingUpload, UploadService

router = APIRouter(prefix="/api/v1", tags=["Uploads"])


@router.post(
    "/uploads",
    response_model=SuccessResponse[UploadResultData],
    status_code=status.HTTP_201_CREATED,
    summary="Upload ZIP or audio files",
)
async def create_upload(
    files: list[UploadFile] = File(..., description="ZIP and/or audio files"),
    service: UploadService = Depends(get_upload_service),
) -> SuccessResponse[UploadResultData]:
    """Accept ZIP archives and individual .wav/.mp3/.ogg files."""
    if not files:
        raise EmptyUploadException("No files were provided")

    incoming: list[IncomingUpload] = []
    for upload in files:
        filename = upload.filename or "unnamed"
        content = await upload.read()
        incoming.append(
            IncomingUpload(
                filename=filename,
                content=content,
                content_type=upload.content_type,
            )
        )

    result = await service.upload(incoming)
    return SuccessResponse(
        message="Upload accepted",
        data=result,
    )
