"""Acoustic analysis pipeline: load artifact → analyze → upload JSON."""

from __future__ import annotations

import json
import time
from uuid import UUID

from app.ai.acoustic.analyzer import AcousticAnalyzer
from app.ai.acoustic.exceptions import AcousticArtifactMissingException
from app.ai.acoustic.schemas import ACOUSTIC_VERSION, AcousticResult
from app.audio.models import AudioAsset
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


def acoustic_storage_key(batch_id: UUID, audio_id: UUID) -> str:
    return f"uploads/{batch_id}/acoustic/{audio_id}.json"


class AcousticPipeline:
    """Consume analysis artifacts and emit acoustic results."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        analyzer: AcousticAnalyzer,
    ) -> None:
        self._storage = storage
        self._analyzer = analyzer

    async def run(
        self,
        asset: AudioAsset,
        *,
        analysis_json: dict[str, object] | None = None,
    ) -> AcousticResult:
        from app.audio.analysis.pipeline import analysis_storage_key
        from app.audio.analysis.schemas import AnalysisArtifact

        started = time.perf_counter()
        payload: dict[str, object] | None = analysis_json or asset.analysis_json
        if payload is None:
            key = asset.analysis_storage_key or analysis_storage_key(
                asset.batch_id,
                asset.id,
            )
            try:
                raw = await self._storage.download(key)
            except Exception as exc:
                raise AcousticArtifactMissingException(
                    "Unable to load analysis artifact for acoustic analysis",
                    details={"audio_id": str(asset.id), "key": key, "error": str(exc)},
                ) from exc
            payload = json.loads(raw.decode("utf-8"))

        artifact = AnalysisArtifact.model_validate(payload)
        result = self._analyzer.analyze(artifact)

        key = acoustic_storage_key(asset.batch_id, asset.id)
        await self._storage.upload(
            key,
            json.dumps(result.to_storage_dict()).encode("utf-8"),
            content_type="application/json",
            metadata={
                "audio_id": str(asset.id),
                "batch_id": str(asset.batch_id),
                "stage": "acoustic",
                "version": ACOUSTIC_VERSION,
            },
        )
        logger.info(
            "acoustic_uploaded",
            audio_id=str(asset.id),
            storage_key=key,
            duration_ms=int((time.perf_counter() - started) * 1000),
            status="ok",
        )
        return result
