"""Preprocessing-specific exceptions."""

from typing import Any
from uuid import UUID

from app.shared.exceptions.base import (
    AppException,
    StorageException,
    ValidationException,
)


class PreprocessingException(AppException):
    """Base exception for audio preprocessing failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "PREPROCESSING_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(
            message,
            code=code,
            details=details,
            status_code=status_code,
        )


class AudioValidationException(ValidationException):
    """Raised when an audio file fails preprocessing validation."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "AUDIO_VALIDATION_ERROR"


class FFprobeException(PreprocessingException):
    """Raised when ffprobe fails."""

    def __init__(
        self,
        message: str = "ffprobe failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="FFPROBE_ERROR",
            details=details,
            status_code=502,
        )


class FFmpegException(PreprocessingException):
    """Raised when ffmpeg fails."""

    def __init__(
        self,
        message: str = "ffmpeg failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="FFMPEG_ERROR",
            details=details,
            status_code=502,
        )


class PreprocessingTimeoutException(PreprocessingException):
    """Raised when ffmpeg/ffprobe exceeds the configured timeout."""

    def __init__(
        self,
        message: str = "Audio preprocessing timed out",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="PREPROCESSING_TIMEOUT",
            details=details,
            status_code=504,
        )


class AudioDownloadException(StorageException):
    """Raised when downloading original audio from object storage fails."""

    def __init__(
        self,
        message: str = "Failed to download audio from storage",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "AUDIO_DOWNLOAD_ERROR"


class AudioUploadException(StorageException):
    """Raised when uploading normalized audio/metadata fails."""

    def __init__(
        self,
        message: str = "Failed to upload preprocessed audio",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "AUDIO_UPLOAD_ERROR"


class AudioAssetNotFoundException(AppException):
    """Raised when an audio asset cannot be found."""

    def __init__(self, audio_id: UUID) -> None:
        super().__init__(
            f"Audio asset not found: {audio_id}",
            code="AUDIO_NOT_FOUND",
            details={"audio_id": str(audio_id)},
            status_code=404,
        )


class InvalidMetadataException(PreprocessingException):
    """Raised when extracted metadata is incomplete or invalid."""

    def __init__(
        self,
        message: str = "Invalid audio metadata",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="INVALID_METADATA",
            details=details,
            status_code=422,
        )
