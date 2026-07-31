"""Audio analysis application service.

Purpose: Produce reusable VAD + feature artifacts for downstream AI engines.
Responsibilities: Idempotent analyze_audio, persist completion markers, R2 JSON.
Dependencies: AudioRepository, AnalysisPipeline, StorageProvider.
Extension points: Technical / Acoustic / Speech engines consume AnalysisArtifact.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from app.audio.analysis.exceptions import (
    AnalysisNotFoundException,
    InvalidWaveformException,
)
from app.audio.analysis.pipeline import AnalysisPipeline, analysis_storage_key
from app.audio.analysis.schemas import ANALYSIS_VERSION, AnalysisArtifact
from app.audio.preprocessing.exceptions import AudioAssetNotFoundException
from app.audio.repository import AudioRepository
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


class AnalysisService:
    """Coordinates analysis pipeline and persistence."""

    def __init__(
        self,
        *,
        assets: AudioRepository,
        pipeline: AnalysisPipeline,
        storage: StorageProvider,
    ) -> None:
        self._assets = assets
        self._pipeline = pipeline
        self._storage = storage

    async def analyze_audio(self, audio_id: UUID) -> AnalysisArtifact:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        if (
            asset.analysis_completed
            and asset.analysis_storage_key
            and asset.analysis_json
        ):
            logger.info(
                "analysis_skipped_idempotent",
                audio_id=str(audio_id),
                analysis_storage_key=asset.analysis_storage_key,
                analysis_version=asset.analysis_version,
            )
            return AnalysisArtifact.model_validate(asset.analysis_json)

        if not asset.is_preprocessed or not asset.normalized_storage_key:
            raise InvalidWaveformException(
                "Cannot analyze audio before preprocessing completes",
                details={"audio_id": str(audio_id)},
            )

        artifact = await self._pipeline.run(asset)
        key = analysis_storage_key(asset.batch_id, asset.id)
        await self._assets.save_analysis_result(
            audio_id,
            analysis_storage_key=key,
            analysis_version=ANALYSIS_VERSION,
            analysis_json=artifact.to_storage_dict(),
            analysis_completed_at=datetime.now(timezone.utc),
        )
        logger.info(
            "analysis_persisted",
            audio_id=str(audio_id),
            analysis_storage_key=key,
            analysis_version=ANALYSIS_VERSION,
            status="ok",
        )
        return artifact

    async def get_analysis(self, audio_id: UUID) -> AnalysisArtifact:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)
        if asset.analysis_json:
            return AnalysisArtifact.model_validate(asset.analysis_json)
        if asset.analysis_storage_key:
            raw = await self._storage.download(asset.analysis_storage_key)
            return AnalysisArtifact.model_validate(json.loads(raw.decode("utf-8")))
        raise AnalysisNotFoundException(audio_id)
