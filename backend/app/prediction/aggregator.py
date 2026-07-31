"""PredictionAggregator: collect independent AI engine outputs.

Responsibilities: load TechnicalResult / AcousticResult / SpeechResult and
build AnalysisResult. Nothing else. No business rules live here — engines
never learn about each other.
"""

from __future__ import annotations

from app.ai.acoustic.schemas import AcousticResult
from app.ai.speech.schemas import SpeechResult
from app.ai.technical.schemas import TechnicalResult
from app.audio.models import AudioAsset
from app.prediction.exceptions import PredictionArtifactMissingException
from app.prediction.schemas import AnalysisResult
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class PredictionAggregator:
    """Build AnalysisResult from persisted per-engine artifacts."""

    def aggregate(self, asset: AudioAsset) -> AnalysisResult:
        logger.info(
            "AggregationStarted",
            audio_id=str(asset.id),
            status="started",
        )
        missing: list[str] = []
        if not asset.technical_json:
            missing.append("technical")
        if not asset.acoustic_json:
            missing.append("acoustic")
        if not asset.speech_json:
            missing.append("speech")
        if missing:
            raise PredictionArtifactMissingException(
                "Engine results required before prediction",
                details={"audio_id": str(asset.id), "missing": missing},
            )

        result = AnalysisResult(
            technical=TechnicalResult.model_validate(asset.technical_json),
            acoustic=AcousticResult.model_validate(asset.acoustic_json),
            speech=SpeechResult.model_validate(asset.speech_json),
        )
        logger.info(
            "AggregationCompleted",
            audio_id=str(asset.id),
            status="ok",
        )
        return result
