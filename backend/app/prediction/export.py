"""Prediction export service.

Exports ONLY the public assessment fields. Internal metadata, provenance,
and engine breakdowns never leave the platform through exports.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any
from uuid import UUID

from app.prediction.models import Prediction
from app.prediction.repository import PredictionRepository
from app.prediction.schemas import ASSESSMENT_FIELDS
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_CSV_HEADER = ("filename", "result_json")


class PredictionExportService:
    """Export batch predictions in public assessment shape."""

    def __init__(self, *, predictions: PredictionRepository) -> None:
        self._predictions = predictions

    async def export_csv(self, batch_id: UUID) -> str:
        """Return CSV text: filename,result_json (public fields only)."""
        predictions = await self._predictions.find_by_batch(batch_id)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(_CSV_HEADER)
        for prediction in predictions:
            writer.writerow(
                [
                    self._filename(prediction),
                    json.dumps(self._public_result(prediction)),
                ]
            )
        logger.info(
            "PredictionExported",
            batch_id=str(batch_id),
            format="csv",
            count=len(predictions),
            status="ok",
        )
        return buffer.getvalue()

    async def export_json(self, batch_id: UUID) -> list[dict[str, Any]]:
        """Return JSON-serializable list: filename + public result only."""
        predictions = await self._predictions.find_by_batch(batch_id)
        payload = [
            {
                "filename": self._filename(prediction),
                "result": self._public_result(prediction),
            }
            for prediction in predictions
        ]
        logger.info(
            "PredictionExported",
            batch_id=str(batch_id),
            format="json",
            count=len(payload),
            status="ok",
        )
        return payload

    def _public_result(self, prediction: Prediction) -> dict[str, Any]:
        source = (
            dict(prediction.prediction_json)
            if prediction.prediction_json
            else {
                "emotional_tone": prediction.emotional_tone.value,
                "emotional_intensity": prediction.emotional_intensity.value,
                "background_noise_present": prediction.background_noise_present,
                "background_noise_type": prediction.background_noise_type,
                "background_noise_severity": prediction.background_noise_severity.value,
                "audio_quality": prediction.audio_quality.value,
                "speaker_overlap_present": prediction.speaker_overlap,
                "long_silence_present": prediction.long_silence,
                "confidence": prediction.confidence,
            }
        )
        return {field: source[field] for field in ASSESSMENT_FIELDS}

    @staticmethod
    def _filename(prediction: Prediction) -> str:
        asset = prediction.audio_asset
        return asset.filename if asset is not None else str(prediction.audio_asset_id)
