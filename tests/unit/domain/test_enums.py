"""Unit tests for domain enums."""

import pytest

from app.shared.domain.enums import (
    AudioQuality,
    AudioStatus,
    BatchStatus,
    EmotionIntensity,
    EmotionTone,
    JobStatus,
    NoiseSeverity,
    UserRole,
)


def test_user_role_values() -> None:
    assert UserRole.ADMIN.value == "ADMIN"
    assert UserRole.EVALUATOR.value == "EVALUATOR"


def test_batch_status_values() -> None:
    assert {status.value for status in BatchStatus} == {
        "UPLOADED",
        "VALIDATED",
        "QUEUED",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
    }


def test_audio_status_values() -> None:
    assert {status.value for status in AudioStatus} == {
        "UPLOADED",
        "VALIDATED",
        "QUEUED",
        "PROCESSING",
        "PROCESSED",
        "COMPLETED",
        "FAILED",
    }


def test_job_status_values() -> None:
    assert JobStatus.CANCELLED.value == "CANCELLED"
    assert JobStatus.RUNNING.value == "RUNNING"


def test_emotion_and_quality_enums() -> None:
    assert EmotionTone.DISTRESSED.value == "DISTRESSED"
    assert EmotionIntensity.MEDIUM.value == "MEDIUM"
    assert NoiseSeverity.NONE.value == "NONE"
    assert AudioQuality.CLEAR.value == "CLEAR"


def test_invalid_enum_rejected() -> None:
    with pytest.raises(ValueError):
        UserRole("SUPERUSER")
