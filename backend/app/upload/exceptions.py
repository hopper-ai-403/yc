"""Upload-specific exceptions."""

from typing import Any

from app.shared.exceptions.base import StorageException, ValidationException


class UploadValidationException(ValidationException):
    """Raised when uploaded content fails validation."""

    def __init__(
        self,
        message: str = "Upload validation failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "UPLOAD_VALIDATION_ERROR"


class EmptyUploadException(UploadValidationException):
    """Raised when no acceptable audio files are present."""

    def __init__(self, message: str = "Upload contained no audio files") -> None:
        super().__init__(message, details={"reason": "empty_upload"})


class CorruptedArchiveException(UploadValidationException):
    """Raised when a ZIP archive cannot be read."""

    def __init__(
        self,
        message: str = "Corrupted or unreadable ZIP archive",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details or {"reason": "corrupted_zip"})


class UnsupportedFormatException(UploadValidationException):
    """Raised when a file format is not supported."""

    def __init__(
        self,
        message: str = "Unsupported file format",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details or {"reason": "unsupported_format"})


class DuplicateFilenameException(UploadValidationException):
    """Raised when duplicate filenames appear in one batch."""

    def __init__(
        self,
        message: str = "Duplicate filenames in upload",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details or {"reason": "duplicate_filename"})


class UploadStorageException(StorageException):
    """Raised when R2 persistence fails during upload."""

    def __init__(
        self,
        message: str = "Failed to store uploaded file",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.code = "UPLOAD_STORAGE_ERROR"
