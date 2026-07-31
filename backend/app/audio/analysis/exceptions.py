"""Audio analysis foundation exceptions."""

from typing import Any

from app.shared.exceptions.base import AppException, ValidationException


class AnalysisException(AppException):
    """Base exception for audio analysis failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "ANALYSIS_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(
            message,
            code=code,
            details=details,
            status_code=status_code,
        )


class VADException(AnalysisException):
    """Raised when voice activity detection fails."""

    def __init__(
        self,
        message: str = "Voice activity detection failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="VAD_ERROR", details=details, status_code=502)


class FeatureExtractionException(AnalysisException):
    """Raised when signal feature extraction fails."""

    def __init__(
        self,
        message: str = "Feature extraction failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="FEATURE_EXTRACTION_ERROR",
            details=details,
            status_code=502,
        )


class InvalidWaveformException(ValidationException):
    """Raised when the waveform cannot be analyzed."""

    def __init__(
        self,
        message: str = "Invalid waveform",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "INVALID_WAVEFORM"


class AnalysisTimeoutException(AnalysisException):
    """Raised when analysis exceeds the configured timeout."""

    def __init__(
        self,
        message: str = "Audio analysis timed out",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="ANALYSIS_TIMEOUT",
            details=details,
            status_code=504,
        )


class AnalysisNotFoundException(AppException):
    """Raised when analysis artifacts are missing for an asset."""

    def __init__(self, audio_id: object) -> None:
        super().__init__(
            f"Analysis not found for audio: {audio_id}",
            code="ANALYSIS_NOT_FOUND",
            details={"audio_id": str(audio_id)},
            status_code=404,
        )
