"""Audio read/download application service."""

from __future__ import annotations

import json
from uuid import UUID

from app.audio.analysis.exceptions import AnalysisNotFoundException
from app.audio.preprocessing.exceptions import AudioAssetNotFoundException
from app.audio.repository import AudioRepository
from app.audio.schemas import (
    AudioAnalysisRead,
    AudioAssetRead,
    AudioDownloadData,
    AudioMetadataRead,
    AudioSegmentsRead,
    AudioTechnicalRead,
    AudioAcousticRead,
)
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

    async def get_analysis(self, audio_id: UUID) -> AudioAnalysisRead:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)
        if not asset.analysis_completed and not asset.analysis_json:
            raise AnalysisNotFoundException(audio_id)

        payload = dict(asset.analysis_json or {})
        if not payload and asset.analysis_storage_key:
            raw = await self._storage.download(asset.analysis_storage_key)
            payload = json.loads(raw.decode("utf-8"))

        return AudioAnalysisRead(
            audio_id=asset.id,
            analysis_completed=asset.analysis_completed,
            analysis_version=asset.analysis_version,
            analysis_storage_key=asset.analysis_storage_key,
            analysis=payload,
        )

    async def get_segments(self, audio_id: UUID) -> AudioSegmentsRead:
        analysis = await self.get_analysis(audio_id)
        vad = dict(analysis.analysis.get("vad") or {})
        return AudioSegmentsRead(
            audio_id=audio_id,
            speech_segments=list(vad.get("speech_segments") or []),
            silence_segments=list(vad.get("silence_segments") or []),
            speech_duration=float(vad.get("speech_duration") or 0.0),
            speech_ratio=float(vad.get("speech_ratio") or 0.0),
            largest_silence=float(vad.get("largest_silence") or 0.0),
            speech_start=vad.get("speech_start"),
            speech_end=vad.get("speech_end"),
        )

    async def get_technical(self, audio_id: UUID) -> AudioTechnicalRead:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        payload = dict(asset.technical_json or {})
        return AudioTechnicalRead(
            audio_id=asset.id,
            audio_quality=str(payload.get("audio_quality") or "CLEAR"),
            speaker_overlap_present=bool(payload.get("speaker_overlap_present") or False),
            long_silence_present=bool(payload.get("long_silence_present") or False),
            technical_version=asset.technical_version,
            technical_completed=asset.technical_completed,
        )

    async def get_acoustic(self, audio_id: UUID) -> AudioAcousticRead:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        payload = dict(asset.acoustic_json or {})
        return AudioAcousticRead(
            audio_id=asset.id,
            background_noise_present=bool(payload.get("background_noise_present") or False),
            background_noise_type=str(payload.get("background_noise_type") or "NONE"),
            background_noise_severity=str(payload.get("background_noise_severity") or "NONE"),
            acoustic_version=asset.acoustic_version,
            acoustic_completed=asset.acoustic_completed,
        )
