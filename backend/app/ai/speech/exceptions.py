"""Speech intelligence exceptions."""

from typing import Any
from uuid import UUID

from app.shared.exceptions.base import AppException


class SpeechAnalysisException(AppException):
    """Base exception for speech analysis failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SPEECH_ANALYSIS_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 502,
    ) -> None:
        super().__init__(
            message,
            code=code,
            details=details,
            status_code=status_code,
        )


class SpeechArtifactMissingException(SpeechAnalysisException):
    """Raised when required artifacts or waveform are unavailable."""

    def __init__(
        self,
        message: str = "Missing artifacts for speech analysis",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="SPEECH_ARTIFACT_MISSING",
            details=details,
            status_code=412,
        )


class SpeechModelException(SpeechAnalysisException):
    """Raised when the SER model fails to load."""

    def __init__(
        self,
        message: str = "Speech emotion model failed to load",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="SPEECH_MODEL_ERROR",
            details=details,
        )


class SpeechInferenceException(SpeechAnalysisException):
    """Raised when SER inference fails."""

    def __init__(
        self,
        message: str = "Speech emotion inference failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="SPEECH_INFERENCE_ERROR",
            details=details,
        )


class SpeechNotFoundException(AppException):
    """Raised when speech results are not present for an asset."""

    def __init__(self, audio_id: UUID) -> None:
        super().__init__(
            f"Speech results not found for audio: {audio_id}",
            code="SPEECH_NOT_FOUND",
            details={"audio_id": str(audio_id)},
            status_code=404,
        )
