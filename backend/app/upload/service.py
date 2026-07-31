"""Upload service orchestrating validation, R2 storage, and persistence.

Purpose: Accept ZIP/audio uploads and create batch/asset/job records.
Responsibilities: Validate files, store originals in R2, persist domain entities.
Dependencies: repositories, StorageProvider, UploadSettings.
Extension points: Manifest CSV parsing, virus scanning hooks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.audio.models import AudioAsset, AudioBatch
from app.audio.repository import AudioBatchRepository, AudioRepository
from app.auth.models import User
from app.auth.repository import UserRepository
from app.config.settings import UploadSettings
from app.jobs.models import Job
from app.jobs.repository import JobRepository
from app.shared.domain.enums import AudioStatus, BatchStatus, JobStatus, UserRole
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider
from app.upload.exceptions import (
    CorruptedArchiveException,
    EmptyUploadException,
    UploadStorageException,
    UploadValidationException,
)
from app.upload.schemas import RejectedFile, UploadResultData, ValidatedAudioFile
from app.upload.validation import (
    ensure_unique_filenames,
    is_zip_upload,
    sniff_mime_type,
    validate_audio_bytes,
)
from app.upload.zip_extractor import extract_audio_from_zip

logger = get_logger(__name__)


@dataclass(frozen=True)
class IncomingUpload:
    """Raw multipart upload candidate."""

    filename: str
    content: bytes
    content_type: str | None


class UploadService:
    """Coordinates the upload and storage pipeline."""

    def __init__(
        self,
        *,
        settings: UploadSettings,
        storage: StorageProvider,
        users: UserRepository,
        batches: AudioBatchRepository,
        assets: AudioRepository,
        jobs: JobRepository,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._users = users
        self._batches = batches
        self._assets = assets
        self._jobs = jobs

    async def upload(self, uploads: list[IncomingUpload]) -> UploadResultData:
        """Validate, store, and persist an upload batch."""
        if not uploads:
            raise EmptyUploadException("No files were provided")

        accepted: list[ValidatedAudioFile] = []
        rejected: list[RejectedFile] = []
        source_names: list[str] = []

        for item in uploads:
            source_names.append(item.filename)
            mime_type = sniff_mime_type(item.filename, item.content_type)
            try:
                if is_zip_upload(item.filename, mime_type):
                    zip_accepted, zip_rejected = extract_audio_from_zip(
                        filename=item.filename,
                        content=item.content,
                        settings=self._settings,
                    )
                    accepted.extend(zip_accepted)
                    rejected.extend(
                        RejectedFile(filename=row["filename"], reason=row["reason"])
                        for row in zip_rejected
                    )
                else:
                    accepted.append(
                        validate_audio_bytes(
                            filename=item.filename,
                            content=item.content,
                            declared_mime=mime_type,
                            settings=self._settings,
                        )
                    )
            except CorruptedArchiveException:
                raise
            except UploadValidationException as exc:
                rejected.append(
                    RejectedFile(filename=item.filename, reason=exc.message)
                )

        if not accepted:
            raise EmptyUploadException(
                "Upload contained no valid audio files",
            )

        if len(accepted) > self._settings.max_files_per_batch:
            raise UploadValidationException(
                "Too many audio files in batch",
                details={
                    "files_uploaded_candidate": len(accepted),
                    "max_files_per_batch": self._settings.max_files_per_batch,
                },
            )

        ensure_unique_filenames(accepted)

        batch_id = uuid4()
        uploader = await self._ensure_system_uploader()
        uploaded_keys: list[str] = []
        now = datetime.now(timezone.utc)

        try:
            for file in accepted:
                storage_key = f"uploads/{batch_id}/original/{file.filename}"
                await self._storage.upload_file(
                    storage_key,
                    file.content,
                    content_type=file.mime_type,
                    metadata={
                        "checksum_sha256": file.checksum_sha256,
                        "batch_id": str(batch_id),
                    },
                )
                uploaded_keys.append(storage_key)

            batch = await self._batches.create(
                AudioBatch(
                    id=batch_id,
                    original_filename=(
                        source_names[0]
                        if len(source_names) == 1
                        else f"batch-{len(source_names)}-files"
                    ),
                    total_files=len(accepted),
                    uploaded_by=uploader.id,
                    status=BatchStatus.UPLOADED,
                )
            )

            for file, storage_key in zip(accepted, uploaded_keys, strict=True):
                await self._assets.create(
                    AudioAsset(
                        batch_id=batch.id,
                        filename=file.filename,
                        format=file.extension,
                        extension=file.extension,
                        mime_type=file.mime_type,
                        size_bytes=file.size_bytes,
                        checksum_sha256=file.checksum_sha256,
                        uploaded_at=now,
                        storage_key=storage_key,
                        processing_status=AudioStatus.UPLOADED,
                    )
                )

            job = await self._jobs.create(
                Job(
                    batch_id=batch.id,
                    status=JobStatus.PENDING,
                    progress=0,
                    total_files=len(accepted),
                    processed_files=0,
                    failed_files=0,
                )
            )
        except Exception as exc:
            await self._cleanup_keys(uploaded_keys)
            if isinstance(exc, UploadValidationException):
                raise
            logger.exception("upload_pipeline_failed", batch_id=str(batch_id))
            raise UploadStorageException(
                "Failed to store uploaded files",
                details={"batch_id": str(batch_id), "error": str(exc)},
            ) from exc

        logger.info(
            "upload_batch_created",
            batch_id=str(batch.id),
            job_id=str(job.id),
            files_uploaded=len(accepted),
            files_rejected=len(rejected),
            status="ok",
        )
        return UploadResultData(
            batch_id=batch.id,
            job_id=job.id,
            files_uploaded=len(accepted),
            files_rejected=len(rejected),
            rejected_files=rejected,
        )

    async def _ensure_system_uploader(self) -> User:
        existing = await self._users.find_by_email(self._settings.system_uploader_email)
        if existing is not None:
            return existing
        return await self._users.create(
            User(
                email=self._settings.system_uploader_email,
                password_hash="!",  # noqa: S106 - placeholder; auth lands later
                role=UserRole.ADMIN,
                is_active=True,
            )
        )

    async def _cleanup_keys(self, keys: list[str]) -> None:
        for key in keys:
            try:
                await self._storage.delete_file(key)
            except Exception:
                logger.warning("r2_cleanup_failed", key=key)
