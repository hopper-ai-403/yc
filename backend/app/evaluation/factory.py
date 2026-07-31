"""Factory for EvaluationService outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.repository import (
    SqlAlchemyAudioBatchRepository,
    SqlAlchemyAudioRepository,
)
from app.config.settings import get_settings
from app.evaluation.exporter import BatchExporter
from app.evaluation.metrics import BatchMetricsCalculator
from app.evaluation.pipeline import EvaluationPipeline
from app.evaluation.repository import (
    BatchMetricsRepository,
    SqlAlchemyBatchMetricsRepository,
)
from app.evaluation.runner import BatchRunner
from app.evaluation.service import EvaluationService
from app.infrastructure.r2.client import CloudflareR2Storage
from app.jobs.factory import build_job_service
from app.jobs.repository import SqlAlchemyJobRepository
from app.jobs.service import JobService
from app.prediction.export import PredictionExportService
from app.prediction.repository import SqlAlchemyPredictionRepository
from app.shared.storage.provider import StorageProvider


def build_evaluation_service(
    session: AsyncSession,
    *,
    storage: StorageProvider | None = None,
    job_service: JobService | None = None,
    predictions_export: PredictionExportService | None = None,
) -> EvaluationService:
    """Construct EvaluationService with concrete collaborators."""
    settings = get_settings()
    storage_provider = storage or CloudflareR2Storage(settings.r2)
    prediction_repo = SqlAlchemyPredictionRepository(session)
    export_service = predictions_export or PredictionExportService(
        predictions=prediction_repo,
    )
    exporter = BatchExporter(
        storage=storage_provider,
        predictions_export=export_service,
        signed_url_expiry_seconds=settings.r2.signed_url_expiry_seconds,
    )
    metrics_repo: BatchMetricsRepository = SqlAlchemyBatchMetricsRepository(session)
    return EvaluationService(
        batches=SqlAlchemyAudioBatchRepository(session),
        jobs=SqlAlchemyJobRepository(session),
        runner=BatchRunner(
            batches=SqlAlchemyAudioBatchRepository(session),
            jobs=job_service or build_job_service(session),
        ),
        pipeline=EvaluationPipeline(
            assets=SqlAlchemyAudioRepository(session),
            predictions=prediction_repo,
            metrics_repo=metrics_repo,
            calculator=BatchMetricsCalculator(),
            exporter=exporter,
        ),
        exporter=exporter,
        metrics_repo=metrics_repo,
        predictions_export=export_service,
    )
