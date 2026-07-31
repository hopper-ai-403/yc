"""Speech intelligence application service.

Purpose: Speech-only analysis (emotional tone + intensity via SER).
Responsibilities: Idempotent speech_analysis, persist normalized values to DB/R2.
Dependencies: AudioRepository, SpeechPipeline, SpeechEmotionModel (via analyzer).
Extension points: SpeechEmotionModel implementations swapped via factory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.ai.speech.exceptions import (
    SpeechArtifactMissingException,
    SpeechNotFoundException,
)
from app.ai.speech.pipeline import SpeechPipeline, speech_storage_key
from app.ai.speech.schemas import SPEECH_VERSION, SpeechResult
from app.audio.preprocessing.exceptions import AudioAssetNotFoundException
from app.audio.repository import AudioRepository
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class SpeechService:
    """Coordinates speech emotion analysis and persistence."""

    def __init__(
        self,
        *,
        assets: AudioRepository,
        pipeline: SpeechPipeline,
    ) -> None:
        self._assets = assets
        self._pipeline = pipeline

    async def analyze_audio(self, audio_id: UUID) -> SpeechResult:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        if asset.speech_completed and asset.speech_json:
            logger.info(
                "speech_skipped_idempotent",
                audio_id=str(audio_id),
                speech_version=asset.speech_version,
            )
            return SpeechResult.model_validate(asset.speech_json)

        if not asset.is_preprocessed or not asset.normalized_storage_key:
            raise SpeechArtifactMissingException(
                "Preprocessing required before speech analysis",
                details={"audio_id": str(audio_id)},
            )

        result = await self._pipeline.run(asset)
        key = speech_storage_key(asset.batch_id, asset.id)
        await self._assets.save_speech_result(
            audio_id,
            speech_version=SPEECH_VERSION,
            speech_json=result.to_storage_dict(),
            speech_completed_at=datetime.now(timezone.utc),
        )
        logger.info(
            "speech_persisted",
            audio_id=str(audio_id),
            speech_version=SPEECH_VERSION,
            storage_key=key,
            status="ok",
        )
        return result

    async def get_speech(self, audio_id: UUID) -> SpeechResult:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)
        if asset.speech_json:
            return SpeechResult.model_validate(asset.speech_json)
        raise SpeechNotFoundException(audio_id)
