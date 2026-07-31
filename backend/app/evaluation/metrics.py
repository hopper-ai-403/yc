"""Batch evaluation metrics calculator."""

from __future__ import annotations

from app.audio.models import AudioAsset
from app.evaluation.schemas import EvaluationMetricsData
from app.prediction.models import Prediction
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class BatchMetricsCalculator:
    """Compute deterministic per-batch metrics from assets and predictions."""

    def calculate(
        self,
        *,
        assets: list[AudioAsset],
        predictions: list[Prediction],
    ) -> EvaluationMetricsData:
        total_audio = len(assets)
        successful = len(predictions)
        failed = max(0, total_audio - successful)
        success_rate = (successful / total_audio) if total_audio > 0 else 0.0

        processing_times = self._processing_times_ms(assets, predictions)
        confidences = [float(p.confidence) for p in predictions]

        metrics = EvaluationMetricsData(
            total_audio=total_audio,
            successful_predictions=successful,
            failed_predictions=failed,
            success_rate=round(success_rate, 4),
            average_processing_time_ms=(
                round(sum(processing_times) / len(processing_times), 2)
                if processing_times
                else None
            ),
            min_processing_time_ms=(
                round(min(processing_times), 2) if processing_times else None
            ),
            max_processing_time_ms=(
                round(max(processing_times), 2) if processing_times else None
            ),
            average_confidence=(
                round(sum(confidences) / len(confidences), 4) if confidences else None
            ),
        )
        logger.info(
            "evaluation_metrics_computed",
            total_audio=metrics.total_audio,
            successful_predictions=metrics.successful_predictions,
            failed_predictions=metrics.failed_predictions,
            success_rate=metrics.success_rate,
            status="ok",
        )
        return metrics

    @staticmethod
    def _processing_times_ms(
        assets: list[AudioAsset],
        predictions: list[Prediction],
    ) -> list[float]:
        """Per-asset wall time from upload to prediction completion."""
        uploaded_by_id = {asset.id: asset.uploaded_at for asset in assets}
        times: list[float] = []
        for prediction in predictions:
            uploaded = uploaded_by_id.get(prediction.audio_asset_id)
            completed = prediction.prediction_completed_at
            if uploaded is None or completed is None:
                continue
            delta_ms = (completed - uploaded).total_seconds() * 1000.0
            if delta_ms >= 0:
                times.append(delta_ms)
        return times
