"""Preprocessing service — orchestrates persistence around the pipeline.

Purpose: Standardize AudioAssets for downstream AI.
Responsibilities: Idempotent preprocess, stale-artifact invalidation,
    persist metadata, R2 keys.
Dependencies: AudioRepository, StorageProvider, PreprocessingPipeline,
    PreprocessingSettings.
Extension points: Replace stages without changing JobService.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.audio.preprocessing.exceptions import AudioAssetNotFoundException
from app.audio.preprocessing.metadata import AudioTechnicalMetadata
from app.audio.preprocessing.pipeline import (
    PreprocessingPipeline,
    metadata_storage_key,
    normalized_storage_key,
)
from app.audio.preprocessing.policy import is_preprocessing_stale
from app.audio.repository import AudioRepository
from app.config.settings import PreprocessingSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class PreprocessingService:
    """Application service for audio preprocessing."""

    def __init__(
        self,
        *,
        assets: AudioRepository,
        pipeline: PreprocessingPipeline,
        settings: PreprocessingSettings,
    ) -> None:
        self._assets = assets
        self._pipeline = pipeline
        self._settings = settings

    def needs_reprocess(
        self,
        *,
        is_preprocessed: bool,
        normalized_storage_key: str | None,
        metadata_json: dict[str, Any] | None,
        force: bool = False,
    ) -> bool:
        """Return True when preprocess must run (bypass idempotent reuse)."""
        if force:
            return True
        if not is_preprocessed or not normalized_storage_key or not metadata_json:
            return True
        return is_preprocessing_stale(metadata_json, self._settings)

    async def preprocess_audio(
        self,
        audio_id: UUID,
        *,
        force: bool = False,
    ) -> AudioTechnicalMetadata:
        """Run preprocessing for one asset.

        Idempotent when already preprocessed with a current, non-stale policy.
        Stale normalized audio invalidates downstream artifacts so analysis /
        technical / acoustic / speech / prediction regenerate.
        """
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        if not self.needs_reprocess(
            is_preprocessed=asset.is_preprocessed,
            normalized_storage_key=asset.normalized_storage_key,
            metadata_json=asset.metadata_json,
            force=force,
        ):
            logger.info(
                "preprocessing_skipped_idempotent",
                audio_id=str(audio_id),
                normalized_storage_key=asset.normalized_storage_key,
            )
            return AudioTechnicalMetadata.model_validate(asset.metadata_json)

        if asset.is_preprocessed or asset.analysis_completed or asset.prediction:
            await self._assets.invalidate_downstream_artifacts(audio_id)
            logger.info(
                "preprocessing_stale_artifacts_invalidated",
                audio_id=str(audio_id),
                force=force,
            )

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
            normalized_duration=metadata.normalized_duration,
            sample_rate=metadata.sample_rate,
            channels=metadata.channels,
            trim_mode=metadata.trim_mode,
            status="ok",
        )
        return metadata
