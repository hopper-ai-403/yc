"""Unit tests for domain value objects and business rules."""

import pytest
from pydantic import ValidationError

from app.shared.domain.enums import (
    AudioQuality,
    EmotionIntensity,
    EmotionTone,
    NoiseSeverity,
)
from app.shared.domain.exceptions import InvariantViolationException
from app.shared.domain.value_objects import (
    AudioMetadata,
    ConfidenceScore,
    EmotionResult,
    NoiseResult,
    OverlapResult,
    PredictionResult,
    QualityResult,
    SilenceResult,
)


def test_emotion_result_immutable() -> None:
    result = EmotionResult(tone=EmotionTone.NEUTRAL, intensity=EmotionIntensity.LOW)
    with pytest.raises(ValidationError):
        result.tone = EmotionTone.UPSET  # type: ignore[misc]


def test_confidence_score_valid_bounds() -> None:
    assert ConfidenceScore(value=0.0).value == 0.0
    assert ConfidenceScore(value=1.0).value == 1.0
    assert ConfidenceScore(value=0.73).value == 0.73


def test_confidence_score_rejects_out_of_range() -> None:
    with pytest.raises((InvariantViolationException, ValidationError)):
        ConfidenceScore(value=1.01)
    with pytest.raises((InvariantViolationException, ValidationError)):
        ConfidenceScore(value=-0.1)


def test_noise_result_allows_present_with_type() -> None:
    result = NoiseResult(
        present=True,
        type="traffic",
        severity=NoiseSeverity.MEDIUM,
    )
    assert result.present is True
    assert result.type == "traffic"


def test_noise_type_must_be_empty_when_absent() -> None:
    with pytest.raises((InvariantViolationException, ValidationError)):
        NoiseResult(present=False, type="hum", severity=NoiseSeverity.NONE)


def test_noise_severity_must_be_none_when_absent() -> None:
    with pytest.raises((InvariantViolationException, ValidationError)):
        NoiseResult(present=False, type="", severity=NoiseSeverity.LOW)


def test_noise_absent_defaults() -> None:
    result = NoiseResult(present=False)
    assert result.type == ""
    assert result.severity is NoiseSeverity.NONE


def test_audio_metadata_validation() -> None:
    meta = AudioMetadata(
        duration=12.5,
        sample_rate=16000,
        channels=1,
        bitrate=128000,
    )
    assert meta.sample_rate == 16000
    with pytest.raises(ValidationError):
        AudioMetadata(duration=-1, sample_rate=16000, channels=1)


def test_prediction_result_aggregates_analyzers() -> None:
    payload = PredictionResult(
        emotion=EmotionResult(
            tone=EmotionTone.SATISFIED,
            intensity=EmotionIntensity.MEDIUM,
        ),
        noise=NoiseResult(present=False),
        quality=QualityResult(quality=AudioQuality.CLEAR),
        overlap=OverlapResult(present=False),
        silence=SilenceResult(present=True),
        confidence=ConfidenceScore(value=0.91),
    )
    assert payload.confidence.value == 0.91
    assert payload.noise.severity is NoiseSeverity.NONE
