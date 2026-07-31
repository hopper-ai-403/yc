"""Acoustic intelligence exceptions."""

from typing import Any
from uuid import UUID

from app.shared.exceptions.base import AppException


class AcousticAnalysisException(AppException):
    """Base exception for acoustic analysis failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "ACOUSTIC_ANALYSIS_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 502,
    ) -> None:
        super().__init__(
            message,
            code=code,
            details=details,
            status_code=status_code,
        )


class AcousticArtifactMissingException(AcousticAnalysisException):
    """Raised when required analysis artifacts are unavailable."""

    def __init__(
        self,
        message: str = "Missing analysis artifacts for acoustic analysis",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="ACOUSTIC_ARTIFACT_MISSING",
            details=details,
            status_code=412,
        )


class NoiseClassificationException(AcousticAnalysisException):
    """Raised when noise classification fails."""

    def __init__(
        self,
        message: str = "Noise classification failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="NOISE_CLASSIFICATION_ERROR",
            details=details,
        )


class NoiseDetectionException(AcousticAnalysisException):
    """Raised when noise detection fails."""

    def __init__(
        self,
        message: str = "Noise detection failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="NOISE_DETECTION_ERROR",
            details=details,
        )


class AcousticNotFoundException(AppException):
    """Raised when acoustic results are not present for an asset."""

    def __init__(self, audio_id: UUID) -> None:
        super().__init__(
            f"Acoustic results not found for audio: {audio_id}",
            code="ACOUSTIC_NOT_FOUND",
            details={"audio_id": str(audio_id)},
            status_code=404,
        )
