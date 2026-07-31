"""Acoustic intelligence application service.

Purpose: Acoustic-only analysis (background noise present/type/severity).
Responsibilities: Idempotent acoustic_analysis, persist to DB/R2,
    enforce business rule: no noise => NONE type/severity.
Dependencies: AudioRepository, AcousticPipeline, StorageProvider.
Extension points: NoiseDetector / NoiseClassifier / NoiseSeverityEstimator
    implementations swapped via factory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.ai.acoustic.exceptions import (
    AcousticArtifactMissingException,
    AcousticNotFoundException,
)
from app.ai.acoustic.pipeline import AcousticPipeline, acoustic_storage_key
from app.ai.acoustic.schemas import ACOUSTIC_VERSION, AcousticResult
from app.audio.preprocessing.exceptions import AudioAssetNotFoundException
from app.audio.repository import AudioRepository
from app.shared.domain.enums import NoiseSeverity, NoiseType
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class AcousticService:
    """Coordinates acoustic analysis and persistence."""

    def __init__(
        self,
        *,
        assets: AudioRepository,
        pipeline: AcousticPipeline,
    ) -> None:
        self._assets = assets
        self._pipeline = pipeline

    async def analyze_audio(self, audio_id: UUID) -> AcousticResult:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        if asset.acoustic_completed and asset.acoustic_json:
            logger.info(
                "acoustic_skipped_idempotent",
                audio_id=str(audio_id),
                acoustic_version=asset.acoustic_version,
            )
            return AcousticResult.model_validate(asset.acoustic_json)

        if not asset.analysis_completed and not asset.analysis_json:
            raise AcousticArtifactMissingException(
                "Analysis artifacts required before acoustic analysis",
                details={"audio_id": str(audio_id)},
            )

        result = self._enforce_business_rules(
            await self._pipeline.run(asset),
        )
        key = acoustic_storage_key(asset.batch_id, asset.id)
        await self._assets.save_acoustic_result(
            audio_id,
            acoustic_version=ACOUSTIC_VERSION,
            acoustic_json=result.to_storage_dict(),
            acoustic_completed_at=datetime.now(timezone.utc),
        )
        logger.info(
            "acoustic_persisted",
            audio_id=str(audio_id),
            acoustic_version=ACOUSTIC_VERSION,
            storage_key=key,
            status="ok",
        )
        return result

    async def get_acoustic(self, audio_id: UUID) -> AcousticResult:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)
        if asset.acoustic_json:
            return AcousticResult.model_validate(asset.acoustic_json)
        raise AcousticNotFoundException(audio_id)

    @staticmethod
    def _enforce_business_rules(result: AcousticResult) -> AcousticResult:
        if result.background_noise_present:
            return result
        if (
            result.background_noise_type is NoiseType.NONE
            and result.background_noise_severity is NoiseSeverity.NONE
        ):
            return result
        return result.model_copy(
            update={
                "background_noise_type": NoiseType.NONE,
                "background_noise_severity": NoiseSeverity.NONE,
            }
        )
