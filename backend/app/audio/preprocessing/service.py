"""Preprocessing service — orchestrates persistence around the pipeline.

Purpose: Standardize AudioAssets for downstream AI.
Responsibilities: Idempotent preprocess, persist metadata, R2 keys.
Dependencies: AudioRepository, StorageProvider, PreprocessingPipeline.
Extension points: Replace stages without changing JobService.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.audio.preprocessing.exceptions import AudioAssetNotFoundException
from app.audio.preprocessing.metadata import AudioTechnicalMetadata
from app.audio.preprocessing.pipeline import (
    PreprocessingPipeline,
    metadata_storage_key,
    normalized_storage_key,
)
from app.audio.repository import AudioRepository
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class PreprocessingService:
    """Application service for audio preprocessing."""

    def __init__(
        self,
        *,
        assets: AudioRepository,
        pipeline: PreprocessingPipeline,
    ) -> None:
        self._assets = assets
        self._pipeline = pipeline

    async def preprocess_audio(self, audio_id: UUID) -> AudioTechnicalMetadata:
        """Run preprocessing for one asset. Idempotent when already preprocessed."""
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        if (
            asset.is_preprocessed
            and asset.normalized_storage_key
            and asset.metadata_json
        ):
            logger.info(
                "preprocessing_skipped_idempotent",
                audio_id=str(audio_id),
                normalized_storage_key=asset.normalized_storage_key,
            )
            return AudioTechnicalMetadata.model_validate(asset.metadata_json)

        metadata = await self._pipeline.run(asset)
        await self._assets.save_preprocessing_result(
            audio_id,
            duration=metadata.duration,
            sample_rate=metadata.sample_rate,
            channels=metadata.channels,
            normalized_storage_key=normalized_storage_key(asset.batch_id, asset.id),
            metadata_json=metadata.to_storage_dict(),
            metadata_storage_key=metadata_storage_key(asset.batch_id, asset.id),
            preprocessed_at=datetime.now(timezone.utc),
        )
        logger.info(
            "metadata_saved",
            audio_id=str(audio_id),
            duration=metadata.duration,
            sample_rate=metadata.sample_rate,
            channels=metadata.channels,
            status="ok",
        )
        return metadata
