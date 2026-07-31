"""Unit tests for prediction entity business rules."""

from uuid import uuid4

import pytest

from app.prediction.models import Prediction
from app.shared.domain.enums import (
    AudioQuality,
    EmotionIntensity,
    EmotionTone,
    NoiseSeverity,
)
from app.shared.domain.exceptions import ImmutableEntityException
from app.shared.domain.value_objects import (
    ConfidenceScore,
    EmotionResult,
    NoiseResult,
    OverlapResult,
    PredictionResult,
    QualityResult,
    SilenceResult,
)


def _sample_result(*, noise_present: bool = False) -> PredictionResult:
    return PredictionResult(
        emotion=EmotionResult(
            tone=EmotionTone.NEUTRAL,
            intensity=EmotionIntensity.LOW,
        ),
        noise=(
            NoiseResult(
                present=True,
                type="office",
                severity=NoiseSeverity.LOW,
            )
            if noise_present
            else NoiseResult(present=False)
        ),
        quality=QualityResult(quality=AudioQuality.CLEAR),
        overlap=OverlapResult(present=False),
        silence=SilenceResult(present=False),
        confidence=ConfidenceScore(value=0.88),
    )


def test_prediction_from_result() -> None:
    asset_id = uuid4()
    prediction = Prediction.from_result(asset_id, _sample_result())
    assert prediction.audio_asset_id == asset_id
    assert prediction.emotional_tone is EmotionTone.NEUTRAL
    assert prediction.background_noise_present is False
    assert prediction.background_noise_severity is NoiseSeverity.NONE
    assert prediction.confidence == 0.88
    assert prediction.is_persisted is False


def test_prediction_immutable_after_flag() -> None:
    prediction = Prediction.from_result(uuid4(), _sample_result())
    prediction.is_persisted = True
    with pytest.raises(ImmutableEntityException):
        prediction.apply_result(_sample_result(noise_present=True))
