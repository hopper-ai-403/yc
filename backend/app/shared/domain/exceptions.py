"""Domain-layer exceptions for invariant and immutability violations."""

from typing import Any

from app.shared.exceptions.base import AppException, ValidationException


class DomainException(AppException):
    """Base exception for domain-layer failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "DOMAIN_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(
            message,
            code=code,
            details=details,
            status_code=status_code,
        )


class InvariantViolationException(ValidationException):
    """Raised when a domain invariant is violated."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "INVARIANT_VIOLATION"


class ImmutableEntityException(DomainException):
    """Raised when an immutable entity is modified after persistence."""

    def __init__(
        self,
        message: str = "Entity is immutable after persistence",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="IMMUTABLE_ENTITY",
            details=details,
            status_code=409,
        )
