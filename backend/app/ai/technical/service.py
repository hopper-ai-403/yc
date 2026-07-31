"""Technical intelligence application service.

Purpose: Technical-only analysis (quality, overlap, long silence).
Responsibilities: Idempotent technical_analysis, persist to DB/R2.
Dependencies: AudioRepository, TechnicalPipeline, StorageProvider.
Extension points: Swap OverlapDetector implementations via DI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.ai.technical.exceptions import (
    TechnicalArtifactMissingException,
    TechnicalNotFoundException,
)
from app.ai.technical.pipeline import TechnicalPipeline, technical_storage_key
from app.ai.technical.schemas import TECHNICAL_VERSION, TechnicalResult
from app.audio.preprocessing.exceptions import AudioAssetNotFoundException
from app.audio.repository import AudioRepository
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class TechnicalService:
    """Coordinates technical analysis and persistence."""

    def __init__(
        self,
        *,
        assets: AudioRepository,
        pipeline: TechnicalPipeline,
    ) -> None:
        self._assets = assets
        self._pipeline = pipeline

    async def analyze_audio(self, audio_id: UUID) -> TechnicalResult:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        if asset.technical_completed and asset.technical_json:
            logger.info(
                "technical_skipped_idempotent",
                audio_id=str(audio_id),
                technical_version=asset.technical_version,
            )
            return TechnicalResult.model_validate(asset.technical_json)

        if not asset.analysis_completed and not asset.analysis_json:
            raise TechnicalArtifactMissingException(
                "Analysis artifacts required before technical analysis",
                details={"audio_id": str(audio_id)},
            )

        result = await self._pipeline.run(asset)
        key = technical_storage_key(asset.batch_id, asset.id)
        await self._assets.save_technical_result(
            audio_id,
            technical_version=TECHNICAL_VERSION,
            technical_json=result.to_storage_dict(),
            technical_completed_at=datetime.now(timezone.utc),
        )
        logger.info(
            "technical_persisted",
            audio_id=str(audio_id),
            technical_version=TECHNICAL_VERSION,
            storage_key=key,
            status="ok",
        )
        return result

    async def get_technical(self, audio_id: UUID) -> TechnicalResult:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)
        if asset.technical_json:
            return TechnicalResult.model_validate(asset.technical_json)
        raise TechnicalNotFoundException(audio_id)
