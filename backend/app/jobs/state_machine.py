"""Job and audio lifecycle state machines with transition validation."""

from app.shared.domain.enums import AudioStatus, JobStatus
from app.shared.domain.exceptions import InvariantViolationException

JOB_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.QUEUED, JobStatus.CANCELLED},
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.PENDING},
    JobStatus.RUNNING: {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.FAILED: {JobStatus.QUEUED, JobStatus.PENDING, JobStatus.CANCELLED},
    JobStatus.COMPLETED: {JobStatus.QUEUED},
    JobStatus.CANCELLED: {JobStatus.QUEUED, JobStatus.PENDING},
}

AUDIO_TRANSITIONS: dict[AudioStatus, set[AudioStatus]] = {
    AudioStatus.UPLOADED: {
        AudioStatus.VALIDATED,
        AudioStatus.QUEUED,
        AudioStatus.FAILED,
    },
    AudioStatus.VALIDATED: {AudioStatus.QUEUED, AudioStatus.FAILED},
    AudioStatus.QUEUED: {AudioStatus.PROCESSING, AudioStatus.FAILED},
    AudioStatus.PROCESSING: {
        AudioStatus.COMPLETED,
        AudioStatus.PROCESSED,
        AudioStatus.FAILED,
        AudioStatus.QUEUED,
    },
    AudioStatus.PROCESSED: {AudioStatus.COMPLETED},
    AudioStatus.COMPLETED: set(),
    AudioStatus.FAILED: {AudioStatus.QUEUED},
}


def validate_job_transition(current: JobStatus, new: JobStatus) -> None:
    """Raise if a job status transition is illegal."""
    allowed = JOB_TRANSITIONS.get(current, set())
    if new not in allowed and new is not current:
        raise InvariantViolationException(
            f"Invalid job transition: {current.value} → {new.value}",
            details={"from": current.value, "to": new.value},
        )


def validate_audio_transition(current: AudioStatus, new: AudioStatus) -> None:
    """Raise if an audio status transition is illegal."""
    allowed = AUDIO_TRANSITIONS.get(current, set())
    if new not in allowed and new is not current:
        raise InvariantViolationException(
            f"Invalid audio transition: {current.value} → {new.value}",
            details={"from": current.value, "to": new.value},
        )


def is_audio_terminal_success(status: AudioStatus) -> bool:
    """Return True when audio has finished successfully."""
    return status in {AudioStatus.COMPLETED, AudioStatus.PROCESSED}


def is_audio_retriable(status: AudioStatus) -> bool:
    """Return True when audio may be retried."""
    return status is AudioStatus.FAILED
