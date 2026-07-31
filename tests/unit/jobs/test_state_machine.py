"""Unit tests for job and audio state machines."""

import pytest

from app.jobs.state_machine import (
    is_audio_retriable,
    is_audio_terminal_success,
    validate_audio_transition,
    validate_job_transition,
)
from app.shared.domain.enums import AudioStatus, JobStatus
from app.shared.domain.exceptions import InvariantViolationException


def test_job_happy_path_transitions() -> None:
    validate_job_transition(JobStatus.PENDING, JobStatus.QUEUED)
    validate_job_transition(JobStatus.QUEUED, JobStatus.RUNNING)
    validate_job_transition(JobStatus.RUNNING, JobStatus.COMPLETED)


def test_job_invalid_transition_rejected() -> None:
    with pytest.raises(InvariantViolationException):
        validate_job_transition(JobStatus.PENDING, JobStatus.RUNNING)


def test_audio_orchestration_transitions() -> None:
    validate_audio_transition(AudioStatus.UPLOADED, AudioStatus.QUEUED)
    validate_audio_transition(AudioStatus.QUEUED, AudioStatus.PROCESSING)
    validate_audio_transition(AudioStatus.PROCESSING, AudioStatus.COMPLETED)
    validate_audio_transition(AudioStatus.FAILED, AudioStatus.QUEUED)


def test_audio_helpers() -> None:
    assert is_audio_terminal_success(AudioStatus.COMPLETED)
    assert is_audio_terminal_success(AudioStatus.PROCESSED)
    assert is_audio_retriable(AudioStatus.FAILED)
    assert not is_audio_retriable(AudioStatus.COMPLETED)
