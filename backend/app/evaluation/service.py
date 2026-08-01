"""Evaluation application service.

Purpose: Reviewer-facing batch execution workflow (run → status → export).
Responsibilities: Batch run, status monitoring, metrics reads, export access,
batch deletion (frees queue + storage).
Dependencies: BatchRunner, EvaluationPipeline, BatchExporter, repositories,
JobService, StorageProvider.
Extension points: Additional export formats via BatchExporter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.audio.repository import AudioBatchRepository
from app.evaluation.exceptions import BatchNotFoundForEvaluationException
from app.evaluation.exporter import BatchExporter
from app.evaluation.models import BatchMetrics
from app.evaluation.pipeline import EvaluationPipeline
from app.evaluation.repository import BatchMetricsRepository
from app.evaluation.runner import BatchRunner
from app.evaluation.schemas import (
    BatchDeleteRead,
    BatchExportItem,
    BatchExportsRead,
    BatchMetricsRead,
    BatchRunRead,
    BatchStatusRead,
)
from app.jobs.repository import JobRepository
from app.jobs.service import JobService
from app.prediction.export import PredictionExportService
from app.shared.domain.enums import JobStatus
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


class EvaluationService:
    """Coordinates the end-to-end batch evaluation workflow."""

    def __init__(
        self,
        *,
        batches: AudioBatchRepository,
        jobs: JobRepository,
        runner: BatchRunner,
        pipeline: EvaluationPipeline,
        exporter: BatchExporter,
        metrics_repo: BatchMetricsRepository,
        predictions_export: PredictionExportService,
        job_service: JobService,
        storage: StorageProvider,
    ) -> None:
        self._batches = batches
        self._jobs = jobs
        self._runner = runner
        self._pipeline = pipeline
        self._exporter = exporter
        self._metrics_repo = metrics_repo
        self._predictions_export = predictions_export
        self._job_service = job_service
        self._storage = storage

    async def run_batch(self, batch_id: UUID) -> BatchRunRead:
        return await self._runner.run(batch_id)

    async def get_status(self, batch_id: UUID) -> BatchStatusRead:
        batch = await self._batches.find_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundForEvaluationException(batch_id)

        job = await self._jobs.find_by_batch(batch_id)
        if job is None:
            return BatchStatusRead(
                batch_id=batch_id,
                job_id=None,
                status=batch.status.value,
                progress=0,
                total_files=batch.total_files,
                processed_files=0,
                failed_files=0,
                estimated_remaining_seconds=None,
            )

        return BatchStatusRead(
            batch_id=batch_id,
            job_id=job.id,
            status=job.status.value,
            progress=job.progress,
            total_files=job.total_files,
            processed_files=job.processed_files,
            failed_files=job.failed_files,
            started_at=job.started_at,
            completed_at=job.completed_at,
            estimated_remaining_seconds=self._estimate_remaining(
                job.status,
                job.started_at,
                job.total_files,
                job.processed_files,
            ),
        )

    async def delete_batch(self, batch_id: UUID) -> BatchDeleteRead:
        """Cancel any active job, remove storage objects, and delete the batch.

        Frees Celery queue capacity for stuck PENDING/QUEUED batches and
        removes orphaned upload artifacts from object storage.
        """
        batch = await self._batches.find_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundForEvaluationException(batch_id)

        job = await self._jobs.find_by_batch(batch_id)
        job_cancelled = False
        if job is not None and job.status not in {
            JobStatus.COMPLETED,
            JobStatus.CANCELLED,
        }:
            await self._job_service.cancel_job(job.id)
            job_cancelled = True

        deleted_objects = await self._delete_storage_prefix(batch_id)
        deleted = await self._batches.delete(batch_id)
        if not deleted:
            raise BatchNotFoundForEvaluationException(batch_id)

        logger.info(
            "batch_deleted",
            batch_id=str(batch_id),
            job_cancelled=job_cancelled,
            deleted_objects=deleted_objects,
            status="ok",
        )
        return BatchDeleteRead(
            batch_id=batch_id,
            job_cancelled=job_cancelled,
            deleted_objects=deleted_objects,
        )

    async def _delete_storage_prefix(self, batch_id: UUID) -> int:
        prefix = f"uploads/{batch_id}/"
        deleted = 0
        try:
            keys = await self._storage.list(prefix, max_keys=1000)
        except Exception as exc:
            logger.warning(
                "batch_storage_list_failed",
                batch_id=str(batch_id),
                error=str(exc),
                status="error",
            )
            return 0
        for key in keys:
            try:
                await self._storage.delete(key)
                deleted += 1
            except Exception as exc:
                logger.warning(
                    "batch_storage_delete_failed",
                    batch_id=str(batch_id),
                    storage_key=key,
                    error=str(exc),
                    status="error",
                )
        return deleted

    async def get_metrics(self, batch_id: UUID) -> BatchMetricsRead:
        batch = await self._batches.find_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundForEvaluationException(batch_id)

        metrics = await self._metrics_repo.find_by_batch(batch_id)
        if metrics is None:
            metrics = await self._pipeline.finalize_batch(batch_id)
        return self._to_metrics_read(metrics)

    async def finalize_batch(self, batch_id: UUID) -> BatchMetrics:
        """Worker hook: persist metrics and generate exports (idempotent)."""
        return await self._pipeline.finalize_batch(batch_id)

    async def export_csv(self, batch_id: UUID) -> str:
        batch = await self._batches.find_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundForEvaluationException(batch_id)
        return await self._predictions_export.export_csv(batch_id)

    async def export_json(self, batch_id: UUID) -> list[dict]:
        batch = await self._batches.find_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundForEvaluationException(batch_id)
        return await self._predictions_export.export_json(batch_id)

    async def get_exports(self, batch_id: UUID) -> BatchExportsRead:
        batch = await self._batches.find_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundForEvaluationException(batch_id)
        items = await self._exporter.get_signed_exports(batch_id)
        return BatchExportsRead(
            batch_id=batch_id,
            exports=[BatchExportItem.model_validate(item) for item in items],
        )

    @staticmethod
    def _estimate_remaining(
        status: JobStatus,
        started_at: datetime | None,
        total_files: int,
        processed_files: int,
    ) -> float | None:
        if status is not JobStatus.RUNNING or started_at is None:
            return None
        if processed_files <= 0 or total_files <= processed_files:
            return 0.0 if total_files <= processed_files else None
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        per_file = elapsed / processed_files
        remaining = total_files - processed_files
        return round(per_file * remaining, 2)

    @staticmethod
    def _to_metrics_read(metrics: BatchMetrics) -> BatchMetricsRead:
        return BatchMetricsRead(
            batch_id=metrics.batch_id,
            total_audio=metrics.total_audio,
            successful_predictions=metrics.successful_predictions,
            failed_predictions=metrics.failed_predictions,
            success_rate=metrics.success_rate,
            average_processing_time_ms=metrics.average_processing_time_ms,
            min_processing_time_ms=metrics.min_processing_time_ms,
            max_processing_time_ms=metrics.max_processing_time_ms,
            average_confidence=metrics.average_confidence,
            batch_duration_ms=metrics.batch_duration_ms,
            computed_at=metrics.computed_at,
        )
