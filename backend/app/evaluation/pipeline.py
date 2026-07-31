"""Evaluation pipeline: metrics computation + export generation."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.audio.repository import AudioRepository
from app.evaluation.exporter import BatchExporter
from app.evaluation.metrics import BatchMetricsCalculator
from app.evaluation.models import BatchMetrics
from app.evaluation.repository import BatchMetricsRepository
from app.prediction.repository import PredictionRepository
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class EvaluationPipeline:
    """Finalize a completed batch: persist metrics and upload exports."""

    def __init__(
        self,
        *,
        assets: AudioRepository,
        predictions: PredictionRepository,
        metrics_repo: BatchMetricsRepository,
        calculator: BatchMetricsCalculator,
        exporter: BatchExporter,
    ) -> None:
        self._assets = assets
        self._predictions = predictions
        self._metrics = metrics_repo
        self._calculator = calculator
        self._exporter = exporter

    async def finalize_batch(
        self,
        batch_id: UUID,
        *,
        regenerate_exports: bool = False,
    ) -> BatchMetrics:
        """Compute + persist metrics, then generate + upload exports."""
        assets = await self._assets.find_by_batch(batch_id)
        predictions = await self._predictions.find_by_batch(batch_id)

        computed = self._calculator.calculate(assets=assets, predictions=predictions)
        metrics = await self._metrics.upsert(
            batch_id,
            total_audio=computed.total_audio,
            successful_predictions=computed.successful_predictions,
            failed_predictions=computed.failed_predictions,
            success_rate=computed.success_rate,
            average_processing_time_ms=computed.average_processing_time_ms,
            min_processing_time_ms=computed.min_processing_time_ms,
            max_processing_time_ms=computed.max_processing_time_ms,
            average_confidence=computed.average_confidence,
            computed_at=datetime.now(timezone.utc),
        )
        logger.info(
            "evaluation_metrics_persisted",
            batch_id=str(batch_id),
            total_audio=metrics.total_audio,
            successful_predictions=metrics.successful_predictions,
            status="ok",
        )

        await self._exporter.generate_and_upload(
            batch_id,
            regenerate=regenerate_exports,
        )
        return metrics
