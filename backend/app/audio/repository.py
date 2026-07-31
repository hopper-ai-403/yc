"""Audio batch and asset repository contracts and SQLAlchemy implementations."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audio.models import AudioAsset, AudioBatch
from app.shared.domain.enums import AudioStatus, BatchStatus


class AudioBatchRepository(ABC):
    """Persistence contract for AudioBatch aggregates."""

    @abstractmethod
    async def create(self, batch: AudioBatch) -> AudioBatch:
        """Persist a new batch."""

    @abstractmethod
    async def find_by_id(self, batch_id: UUID) -> AudioBatch | None:
        """Find a batch by id, including assets and job."""

    @abstractmethod
    async def update_status(
        self, batch_id: UUID, status: BatchStatus
    ) -> AudioBatch | None:
        """Update batch status."""

    @abstractmethod
    async def list_by_uploader(self, uploader_id: UUID) -> list[AudioBatch]:
        """List batches uploaded by a user."""


class AudioRepository(ABC):
    """Persistence contract for AudioAsset entities."""

    @abstractmethod
    async def create(self, asset: AudioAsset) -> AudioAsset:
        """Persist a new audio asset."""

    @abstractmethod
    async def find_by_id(self, asset_id: UUID) -> AudioAsset | None:
        """Find an audio asset by id."""

    @abstractmethod
    async def find_by_batch(self, batch_id: UUID) -> list[AudioAsset]:
        """List assets belonging to a batch."""

    @abstractmethod
    async def update_status(
        self,
        asset_id: UUID,
        status: AudioStatus,
    ) -> AudioAsset | None:
        """Update processing status for an asset."""

    @abstractmethod
    async def save_preprocessing_result(
        self,
        asset_id: UUID,
        *,
        duration: float,
        sample_rate: int,
        channels: int,
        normalized_storage_key: str,
        metadata_json: dict[str, Any],
        metadata_storage_key: str,
        preprocessed_at: datetime,
    ) -> AudioAsset | None:
        """Persist preprocessing outputs onto the asset."""

    @abstractmethod
    async def save_analysis_result(
        self,
        asset_id: UUID,
        *,
        analysis_storage_key: str,
        analysis_version: str,
        analysis_json: dict[str, Any],
        analysis_completed_at: datetime,
    ) -> AudioAsset | None:
        """Persist analysis completion markers and artifact JSON."""

    @abstractmethod
    async def save_technical_result(
        self,
        asset_id: UUID,
        *,
        technical_version: str,
        technical_json: dict[str, Any],
        technical_completed_at: datetime,
    ) -> AudioAsset | None:
        """Persist technical intelligence outputs onto the asset."""

    @abstractmethod
    async def save_acoustic_result(
        self,
        asset_id: UUID,
        *,
        acoustic_version: str,
        acoustic_json: dict[str, Any],
        acoustic_completed_at: datetime,
    ) -> AudioAsset | None:
        """Persist acoustic intelligence outputs onto the asset."""

    @abstractmethod
    async def save_speech_result(
        self,
        asset_id: UUID,
        *,
        speech_version: str,
        speech_json: dict[str, Any],
        speech_completed_at: datetime,
    ) -> AudioAsset | None:
        """Persist speech intelligence outputs onto the asset."""

    @abstractmethod
    async def save_timing(
        self,
        asset_id: UUID,
        *,
        timing_json: dict[str, Any],
    ) -> AudioAsset | None:
        """Persist per-stage pipeline timing metadata onto the asset."""


class SqlAlchemyAudioBatchRepository(AudioBatchRepository):
    """SQLAlchemy-backed AudioBatchRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, batch: AudioBatch) -> AudioBatch:
        self._session.add(batch)
        await self._session.flush()
        await self._session.refresh(batch)
        return batch

    async def find_by_id(self, batch_id: UUID) -> AudioBatch | None:
        statement = (
            select(AudioBatch)
            .where(AudioBatch.id == batch_id)
            .options(
                selectinload(AudioBatch.assets),
                selectinload(AudioBatch.job),
            )
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        batch_id: UUID,
        status: BatchStatus,
    ) -> AudioBatch | None:
        batch = await self.find_by_id(batch_id)
        if batch is None:
            return None
        batch.status = status
        await self._session.flush()
        await self._session.refresh(batch)
        return batch

    async def list_by_uploader(self, uploader_id: UUID) -> list[AudioBatch]:
        statement = (
            select(AudioBatch)
            .where(AudioBatch.uploaded_by == uploader_id)
            .order_by(AudioBatch.created_at.desc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())


class SqlAlchemyAudioRepository(AudioRepository):
    """SQLAlchemy-backed AudioRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, asset: AudioAsset) -> AudioAsset:
        self._session.add(asset)
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def find_by_id(self, asset_id: UUID) -> AudioAsset | None:
        return await self._session.get(AudioAsset, asset_id)

    async def find_by_batch(self, batch_id: UUID) -> list[AudioAsset]:
        statement = (
            select(AudioAsset)
            .where(AudioAsset.batch_id == batch_id)
            .order_by(AudioAsset.created_at.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def update_status(
        self,
        asset_id: UUID,
        status: AudioStatus,
    ) -> AudioAsset | None:
        asset = await self.find_by_id(asset_id)
        if asset is None:
            return None
        asset.processing_status = status
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def save_preprocessing_result(
        self,
        asset_id: UUID,
        *,
        duration: float,
        sample_rate: int,
        channels: int,
        normalized_storage_key: str,
        metadata_json: dict[str, Any],
        metadata_storage_key: str,
        preprocessed_at: datetime,
    ) -> AudioAsset | None:
        asset = await self.find_by_id(asset_id)
        if asset is None:
            return None
        payload = dict(metadata_json)
        payload["metadata_storage_key"] = metadata_storage_key
        asset.duration = duration
        asset.sample_rate = sample_rate
        asset.channels = channels
        asset.normalized_storage_key = normalized_storage_key
        asset.metadata_json = payload
        asset.is_preprocessed = True
        asset.preprocessed_at = preprocessed_at
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def save_analysis_result(
        self,
        asset_id: UUID,
        *,
        analysis_storage_key: str,
        analysis_version: str,
        analysis_json: dict[str, Any],
        analysis_completed_at: datetime,
    ) -> AudioAsset | None:
        asset = await self.find_by_id(asset_id)
        if asset is None:
            return None
        asset.analysis_storage_key = analysis_storage_key
        asset.analysis_version = analysis_version
        asset.analysis_json = dict(analysis_json)
        asset.analysis_completed = True
        asset.analysis_completed_at = analysis_completed_at
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def save_technical_result(
        self,
        asset_id: UUID,
        *,
        technical_version: str,
        technical_json: dict[str, Any],
        technical_completed_at: datetime,
    ) -> AudioAsset | None:
        asset = await self.find_by_id(asset_id)
        if asset is None:
            return None
        asset.technical_version = technical_version
        asset.technical_json = dict(technical_json)
        asset.technical_completed = True
        asset.technical_completed_at = technical_completed_at
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def save_acoustic_result(
        self,
        asset_id: UUID,
        *,
        acoustic_version: str,
        acoustic_json: dict[str, Any],
        acoustic_completed_at: datetime,
    ) -> AudioAsset | None:
        asset = await self.find_by_id(asset_id)
        if asset is None:
            return None
        asset.acoustic_version = acoustic_version
        asset.acoustic_json = dict(acoustic_json)
        asset.acoustic_completed = True
        asset.acoustic_completed_at = acoustic_completed_at
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def save_speech_result(
        self,
        asset_id: UUID,
        *,
        speech_version: str,
        speech_json: dict[str, Any],
        speech_completed_at: datetime,
    ) -> AudioAsset | None:
        asset = await self.find_by_id(asset_id)
        if asset is None:
            return None
        asset.speech_version = speech_version
        asset.speech_json = dict(speech_json)
        asset.speech_completed = True
        asset.speech_completed_at = speech_completed_at
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def save_timing(
        self,
        asset_id: UUID,
        *,
        timing_json: dict[str, Any],
    ) -> AudioAsset | None:
        asset = await self.find_by_id(asset_id)
        if asset is None:
            return None
        asset.timing_json = dict(timing_json)
        await self._session.flush()
        await self._session.refresh(asset)
        return asset
