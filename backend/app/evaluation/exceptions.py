"""Evaluation exceptions."""

from typing import Any
from uuid import UUID

from app.shared.exceptions.base import AppException


class EvaluationException(AppException):
    """Base exception for evaluation workflow failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "EVALUATION_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 502,
    ) -> None:
        super().__init__(
            message,
            code=code,
            details=details,
            status_code=status_code,
        )


class BatchNotRunnableException(EvaluationException):
    """Raised when a batch cannot be executed."""

    def __init__(self, batch_id: UUID, *, reason: str) -> None:
        super().__init__(
            f"Batch cannot be executed: {reason}",
            code="BATCH_NOT_RUNNABLE",
            details={"batch_id": str(batch_id), "reason": reason},
            status_code=409,
        )


class BatchNotFoundForEvaluationException(AppException):
    """Raised when the requested batch does not exist."""

    def __init__(self, batch_id: UUID) -> None:
        super().__init__(
            f"Batch not found: {batch_id}",
            code="BATCH_NOT_FOUND",
            details={"batch_id": str(batch_id)},
            status_code=404,
        )


class ExportNotFoundException(AppException):
    """Raised when batch exports have not been generated yet."""

    def __init__(self, batch_id: UUID) -> None:
        super().__init__(
            f"Exports not found for batch: {batch_id}",
            code="EXPORT_NOT_FOUND",
            details={"batch_id": str(batch_id)},
            status_code=404,
        )
