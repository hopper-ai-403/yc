"""Specific application exceptions.

Never raise generic Exception from application code unless unavoidable.
"""

from typing import Any


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "APP_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code


class ValidationException(AppException):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            details=details,
            status_code=422,
        )


class StorageException(AppException):
    """Raised when object storage operations fail."""

    def __init__(
        self,
        message: str = "Storage operation failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="STORAGE_ERROR",
            details=details,
            status_code=502,
        )


class AuthenticationException(AppException):
    """Raised when authentication or authorization fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="AUTHENTICATION_ERROR",
            details=details,
            status_code=401,
        )


class InferenceException(AppException):
    """Raised when AI inference fails."""

    def __init__(
        self,
        message: str = "Inference failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="INFERENCE_ERROR",
            details=details,
            status_code=502,
        )


class QueueException(AppException):
    """Raised when queue / worker operations fail."""

    def __init__(
        self,
        message: str = "Queue operation failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="QUEUE_ERROR",
            details=details,
            status_code=502,
        )
