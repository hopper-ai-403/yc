"""PredictionValidator: enforce all business rules before persistence."""

from __future__ import annotations

from app.prediction.exceptions import PredictionValidationFailedException
from app.prediction.schemas import AssessmentPrediction
from app.shared.domain.enums import NoiseSeverity, NoiseType
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class PredictionValidator:
    """Validate a built prediction against domain business rules."""

    def __init__(self, *, confidence_rounding: int = 2) -> None:
        self._rounding = confidence_rounding

    def validate(self, prediction: AssessmentPrediction) -> AssessmentPrediction:
        """Return the normalized prediction or raise ValidationException."""
        errors: list[str] = []

        if prediction.emotional_tone is None:  # pragma: no cover - type guard
            errors.append("emotional_tone must never be null")
        if prediction.emotional_intensity is None:  # pragma: no cover
            errors.append("emotional_intensity must never be null")

        normalized = prediction
        if not prediction.background_noise_present:
            if (
                prediction.background_noise_type is not NoiseType.NONE
                or prediction.background_noise_severity is not NoiseSeverity.NONE
            ):
                normalized = prediction.model_copy(
                    update={
                        "background_noise_type": NoiseType.NONE,
                        "background_noise_severity": NoiseSeverity.NONE,
                    }
                )

        confidence = normalized.confidence
        if confidence < 0.0 or confidence > 1.0:
            errors.append(f"confidence out of bounds: {confidence}")

        rounded = round(confidence, self._rounding)
        if rounded != confidence:
            normalized = normalized.model_copy(update={"confidence": rounded})

        if errors:
            raise PredictionValidationFailedException(
                "Prediction validation failed",
                details={"errors": errors},
            )

        logger.info(
            "PredictionValidated",
            confidence=normalized.confidence,
            status="ok",
        )
        return normalized
