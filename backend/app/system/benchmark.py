"""Benchmark runner: measure a completed evaluation batch.

Computes latency percentiles, throughput, average confidence, and failure
rate from per-audio timing metadata and predictions.
"""

from __future__ import annotations

from uuid import UUID

from app.audio.models import AudioAsset
from app.audio.repository import AudioBatchRepository, AudioRepository
from app.evaluation.exceptions import BatchNotFoundForEvaluationException
from app.jobs.repository import JobRepository
from app.prediction.models import Prediction
from app.prediction.repository import PredictionRepository
from app.shared.logging.setup import get_logger
from app.system.schemas import BenchmarkRead

logger = get_logger(__name__)


def percentile(sorted_values: list[float], rank: float) -> float | None:
    """Nearest-rank percentile over ascending values."""
    if not sorted_values:
        return None
    index = max(0, min(len(sorted_values) - 1, round(rank * (len(sorted_values) - 1))))
    return round(sorted_values[index], 2)


class BenchmarkRunner:
    """Generate benchmark reports for evaluation batches."""

    def __init__(
        self,
        *,
        batches: AudioBatchRepository,
        assets: AudioRepository,
        predictions: PredictionRepository,
        jobs: JobRepository,
    ) -> None:
        self._batches = batches
        self._assets = assets
        self._predictions = predictions
        self._jobs = jobs

    async def run(self, batch_id: UUID) -> BenchmarkRead:
        batch = await self._batches.find_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundForEvaluationException(batch_id)

        assets = await self._assets.find_by_batch(batch_id)
        predictions = await self._predictions.find_by_batch(batch_id)
        job = await self._jobs.find_by_batch(batch_id)

        latencies = self._latencies_ms(assets, predictions)
        latencies.sort()
        confidences = [float(p.confidence) for p in predictions]

        batch_duration_ms = self._batch_duration_ms(job)
        successful = len(predictions)
        failed = max(0, len(assets) - successful)

        throughput = (
            round(successful / (batch_duration_ms / 60000.0), 2)
            if batch_duration_ms and batch_duration_ms > 0
            else None
        )

        report = BenchmarkRead(
            batch_id=batch_id,
            total_files=len(assets),
            successful_files=successful,
            failed_files=failed,
            average_latency_ms=(
                round(sum(latencies) / len(latencies), 2) if latencies else None
            ),
            p50_latency_ms=percentile(latencies, 0.50),
            p95_latency_ms=percentile(latencies, 0.95),
            p99_latency_ms=percentile(latencies, 0.99),
            batch_duration_ms=batch_duration_ms,
            throughput_files_per_minute=throughput,
            average_confidence=(
                round(sum(confidences) / len(confidences), 4) if confidences else None
            ),
            failure_rate=round(failed / len(assets), 4) if assets else 0.0,
        )
        logger.info(
            "benchmark_generated",
            batch_id=str(batch_id),
            total_files=report.total_files,
            throughput_files_per_minute=report.throughput_files_per_minute,
            failure_rate=report.failure_rate,
            status="ok",
        )
        return report

    @staticmethod
    def _latencies_ms(
        assets: list[AudioAsset],
        predictions: list[Prediction],
    ) -> list[float]:
        """Per-file latency from persisted timing, falling back to wall time."""
        uploaded_by_id = {asset.id: asset.uploaded_at for asset in assets}
        timing_by_id = {asset.id: asset.timing_json or {} for asset in assets}
        latencies: list[float] = []
        for prediction in predictions:
            timing = timing_by_id.get(prediction.audio_asset_id, {})
            value = timing.get("total_pipeline_duration_ms")
            if isinstance(value, int | float) and value >= 0:
                latencies.append(float(value))
                continue
            uploaded = uploaded_by_id.get(prediction.audio_asset_id)
            completed = prediction.prediction_completed_at
            if uploaded is not None and completed is not None:
                delta_ms = (completed - uploaded).total_seconds() * 1000.0
                if delta_ms >= 0:
                    latencies.append(delta_ms)
        return latencies

    @staticmethod
    def _batch_duration_ms(job: object) -> float | None:
        started_at = getattr(job, "started_at", None)
        completed_at = getattr(job, "completed_at", None)
        if started_at is None or completed_at is None:
            return None
        return round((completed_at - started_at).total_seconds() * 1000.0, 2)
