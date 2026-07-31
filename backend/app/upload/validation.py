"""Upload validation helpers (MIME, extension, size, checksum)."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import PurePosixPath

from app.config.settings import UploadSettings
from app.upload.exceptions import (
    DuplicateFilenameException,
    UnsupportedFormatException,
    UploadValidationException,
)
from app.upload.schemas import ValidatedAudioFile

AUDIO_EXTENSION_MIME: dict[str, str] = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
}


def normalize_extension(filename: str) -> str:
    """Return lowercase file extension including the leading dot."""
    suffix = PurePosixPath(filename).suffix.lower()
    return suffix


def sniff_mime_type(filename: str, declared_mime: str | None) -> str:
    """Resolve MIME type from declaration or filename extension."""
    extension = normalize_extension(filename)
    if declared_mime and declared_mime != "application/octet-stream":
        return declared_mime.lower()
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed.lower()
    return AUDIO_EXTENSION_MIME.get(extension, "application/octet-stream")


def is_zip_upload(filename: str, mime_type: str) -> bool:
    """Return True when the upload is a ZIP archive."""
    extension = normalize_extension(filename)
    return extension == ".zip" or mime_type in {
        "application/zip",
        "application/x-zip-compressed",
        "multipart/x-zip",
    }


def is_audio_extension(extension: str, settings: UploadSettings) -> bool:
    """Return True when extension is an allowed audio type."""
    return extension in {ext.lower() for ext in settings.allowed_extensions}


def validate_audio_bytes(
    *,
    filename: str,
    content: bytes,
    declared_mime: str | None,
    settings: UploadSettings,
) -> ValidatedAudioFile:
    """Validate a single audio file and return a structured candidate."""
    safe_name = PurePosixPath(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise UploadValidationException(
            "Invalid filename",
            details={"filename": filename},
        )

    extension = normalize_extension(safe_name)
    if not is_audio_extension(extension, settings):
        raise UnsupportedFormatException(
            f"Unsupported file extension: {extension or '(none)'}",
            details={"filename": safe_name, "extension": extension},
        )

    size_bytes = len(content)
    if size_bytes == 0:
        raise UploadValidationException(
            "Empty audio file",
            details={"filename": safe_name},
        )
    if size_bytes > settings.max_file_size_bytes:
        raise UploadValidationException(
            "Audio file exceeds maximum allowed size",
            details={
                "filename": safe_name,
                "size_bytes": size_bytes,
                "max_file_size_bytes": settings.max_file_size_bytes,
            },
        )

    mime_type = sniff_mime_type(safe_name, declared_mime)
    allowed_audio_mimes = {
        mime.lower()
        for mime in settings.allowed_mime_types
        if mime.lower().startswith("audio/")
    }
    # Allow extension-based acceptance when browsers send octet-stream.
    if mime_type not in allowed_audio_mimes and mime_type != "application/octet-stream":
        if mime_type not in AUDIO_EXTENSION_MIME.values():
            raise UnsupportedFormatException(
                f"Unsupported MIME type: {mime_type}",
                details={"filename": safe_name, "mime_type": mime_type},
            )

    if mime_type == "application/octet-stream":
        mime_type = AUDIO_EXTENSION_MIME[extension]

    checksum = hashlib.sha256(content).hexdigest()
    return ValidatedAudioFile(
        filename=safe_name,
        extension=extension.lstrip("."),
        mime_type=mime_type,
        size_bytes=size_bytes,
        checksum_sha256=checksum,
        content=content,
    )


def ensure_unique_filenames(files: list[ValidatedAudioFile]) -> None:
    """Reject batches that contain duplicate filenames (case-insensitive)."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in files:
        key = item.filename.lower()
        if key in seen:
            duplicates.append(item.filename)
        seen.add(key)
    if duplicates:
        raise DuplicateFilenameException(
            "Duplicate filenames in upload",
            details={"duplicates": sorted(set(duplicates))},
        )
