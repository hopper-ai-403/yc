"""Job-specific exceptions."""

from typing import Any
from uuid import UUID

from app.shared.exceptions.base import AppException, ValidationException


class JobNotFoundException(AppException):
    """Raised when a job cannot be located."""

    def __init__(self, job_id: UUID) -> None:
        super().__init__(
            f"Job not found: {job_id}",
            code="JOB_NOT_FOUND",
            details={"job_id": str(job_id)},
            status_code=404,
        )


class JobStateException(ValidationException):
    """Raised when a job operation is illegal for the current state."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "JOB_STATE_ERROR"


class JobRetryExhaustedException(JobStateException):
    """Raised when retry_count exceeds the configured maximum."""

    def __init__(self, job_id: UUID, retry_count: int, max_retries: int) -> None:
        super().__init__(
            "Maximum job retries exceeded",
            details={
                "job_id": str(job_id),
                "retry_count": retry_count,
                "max_retries": max_retries,
            },
        )
        self.code = "JOB_RETRY_EXHAUSTED"
