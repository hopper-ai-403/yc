"""Technical intelligence exceptions."""

from typing import Any
from uuid import UUID

from app.shared.exceptions.base import AppException


class TechnicalAnalysisException(AppException):
    """Base exception for technical analysis failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "TECHNICAL_ANALYSIS_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 502,
    ) -> None:
        super().__init__(
            message,
            code=code,
            details=details,
            status_code=status_code,
        )


class TechnicalArtifactMissingException(TechnicalAnalysisException):
    """Raised when required analysis artifacts are unavailable."""

    def __init__(
        self,
        message: str = "Missing analysis artifacts for technical analysis",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="TECHNICAL_ARTIFACT_MISSING",
            details=details,
            status_code=412,
        )


class QualityScoringException(TechnicalAnalysisException):
    """Raised when audio quality scoring fails."""

    def __init__(
        self,
        message: str = "Audio quality scoring failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="QUALITY_SCORING_ERROR",
            details=details,
            status_code=502,
        )


class OverlapDetectionException(TechnicalAnalysisException):
    """Raised when speaker overlap detection fails."""

    def __init__(
        self,
        message: str = "Speaker overlap detection failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="OVERLAP_DETECTION_ERROR",
            details=details,
            status_code=502,
        )


class TechnicalNotFoundException(AppException):
    """Raised when technical results are not present for an asset."""

    def __init__(self, audio_id: UUID) -> None:
        super().__init__(
            f"Technical results not found for audio: {audio_id}",
            code="TECHNICAL_NOT_FOUND",
            details={"audio_id": str(audio_id)},
            status_code=404,
        )
