"""Prediction engine exceptions."""

from typing import Any
from uuid import UUID

from app.shared.exceptions.base import AppException, ValidationException


class PredictionException(AppException):
    """Base exception for prediction engine failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "PREDICTION_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 502,
    ) -> None:
        super().__init__(
            message,
            code=code,
            details=details,
            status_code=status_code,
        )


class PredictionArtifactMissingException(PredictionException):
    """Raised when an upstream AI engine result is missing."""

    def __init__(
        self,
        message: str = "Missing AI engine results for prediction",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="PREDICTION_ARTIFACT_MISSING",
            details=details,
            status_code=412,
        )


class PredictionAlreadyExistsException(PredictionException):
    """Raised when overwriting an immutable prediction without regeneration."""

    def __init__(self, audio_asset_id: UUID, *, prediction_id: UUID) -> None:
        super().__init__(
            f"Prediction already exists for audio asset: {audio_asset_id}",
            code="PREDICTION_ALREADY_EXISTS",
            details={
                "audio_asset_id": str(audio_asset_id),
                "prediction_id": str(prediction_id),
            },
            status_code=409,
        )


class PredictionNotFoundException(AppException):
    """Raised when no prediction exists for the requested resource."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            code="PREDICTION_NOT_FOUND",
            details=details,
            status_code=404,
        )


class PredictionValidationFailedException(ValidationException):
    """Raised when a prediction violates business rules before persistence."""

    def __init__(
        self,
        message: str = "Prediction validation failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
