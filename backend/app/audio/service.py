"""Audio read/download application service."""

from __future__ import annotations

from uuid import UUID

from app.audio.preprocessing.exceptions import AudioAssetNotFoundException
from app.audio.repository import AudioRepository
from app.audio.schemas import AudioAssetRead, AudioDownloadData, AudioMetadataRead
from app.config.settings import R2Settings
from app.shared.storage.provider import StorageProvider


class AudioQueryService:
    """Read-side service for audio assets (no business mutation)."""

    def __init__(
        self,
        *,
        assets: AudioRepository,
        storage: StorageProvider,
        r2_settings: R2Settings,
    ) -> None:
        self._assets = assets
        self._storage = storage
        self._r2 = r2_settings

    async def get_audio(self, audio_id: UUID) -> AudioAssetRead:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)
        return AudioAssetRead.from_entity(asset)

    async def get_metadata(self, audio_id: UUID) -> AudioMetadataRead:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)
        return AudioMetadataRead(
            audio_id=asset.id,
            metadata=dict(asset.metadata_json or {}),
            is_preprocessed=asset.is_preprocessed,
        )

    async def get_download_url(self, audio_id: UUID) -> AudioDownloadData:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        if asset.normalized_storage_key:
            key = asset.normalized_storage_key
            variant = "normalized"
        else:
            key = asset.storage_key
            variant = "original"

        expires_in = self._r2.signed_url_expiry_seconds
        url = await self._storage.generate_signed_url(key, expires_in=expires_in)
        return AudioDownloadData(
            audio_id=asset.id,
            url=url,
            storage_key=key,
            content_variant=variant,
            expires_in=expires_in,
        )
