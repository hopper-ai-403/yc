"""Safe ZIP extraction for upload batches."""

from __future__ import annotations

import io
import zipfile
from pathlib import PurePosixPath

from app.config.settings import UploadSettings
from app.upload.exceptions import CorruptedArchiveException, UploadValidationException
from app.upload.schemas import ValidatedAudioFile
from app.upload.validation import is_audio_extension, validate_audio_bytes


def _is_safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute():
        return False
    if any(part in {"", ".", ".."} for part in path.parts if part == ".."):
        return False
    if ".." in path.parts:
        return False
    return True


def extract_audio_from_zip(
    *,
    filename: str,
    content: bytes,
    settings: UploadSettings,
) -> tuple[list[ValidatedAudioFile], list[dict[str, str]]]:
    """Extract and validate audio files from a ZIP archive.

    Returns accepted files and rejection records for unsupported members.
    """
    if len(content) > settings.max_zip_size_bytes:
        raise UploadValidationException(
            "ZIP archive exceeds maximum allowed size",
            details={
                "filename": filename,
                "size_bytes": len(content),
                "max_zip_size_bytes": settings.max_zip_size_bytes,
            },
        )

    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise CorruptedArchiveException(
            "Corrupted or unreadable ZIP archive",
            details={"filename": filename, "error": str(exc)},
        ) from exc

    accepted: list[ValidatedAudioFile] = []
    rejected: list[dict[str, str]] = []
    total_uncompressed = 0

    with archive:
        try:
            archive.testzip()
        except Exception as exc:
            raise CorruptedArchiveException(
                "Corrupted ZIP archive member detected",
                details={"filename": filename, "error": str(exc)},
            ) from exc

        members = [info for info in archive.infolist() if not info.is_dir()]
        if len(members) > settings.max_files_per_batch:
            raise UploadValidationException(
                "ZIP contains too many files",
                details={
                    "filename": filename,
                    "file_count": len(members),
                    "max_files_per_batch": settings.max_files_per_batch,
                },
            )

        for info in members:
            member_name = info.filename
            if not _is_safe_member(member_name):
                rejected.append(
                    {
                        "filename": member_name,
                        "reason": "unsafe_path",
                    }
                )
                continue

            # Skip macOS / hidden metadata noise.
            basename = PurePosixPath(member_name).name
            if basename.startswith(".") or member_name.startswith("__MACOSX/"):
                rejected.append(
                    {
                        "filename": member_name,
                        "reason": "ignored_metadata",
                    }
                )
                continue

            extension = PurePosixPath(basename).suffix.lower()
            if not is_audio_extension(extension, settings):
                rejected.append(
                    {
                        "filename": basename,
                        "reason": "unsupported_format",
                    }
                )
                continue

            if info.file_size > settings.max_file_size_bytes:
                rejected.append(
                    {
                        "filename": basename,
                        "reason": "file_too_large",
                    }
                )
                continue

            total_uncompressed += info.file_size
            if total_uncompressed > settings.max_uncompressed_zip_bytes:
                raise UploadValidationException(
                    "Uncompressed ZIP contents exceed safety limit",
                    details={
                        "filename": filename,
                        "max_uncompressed_zip_bytes": (
                            settings.max_uncompressed_zip_bytes
                        ),
                    },
                )

            try:
                raw = archive.read(info)
            except Exception as exc:
                raise CorruptedArchiveException(
                    "Failed to read ZIP member",
                    details={"filename": member_name, "error": str(exc)},
                ) from exc

            try:
                validated = validate_audio_bytes(
                    filename=basename,
                    content=raw,
                    declared_mime=None,
                    settings=settings,
                )
                accepted.append(validated)
            except UploadValidationException as exc:
                rejected.append(
                    {
                        "filename": basename,
                        "reason": exc.message,
                    }
                )

    return accepted, rejected
