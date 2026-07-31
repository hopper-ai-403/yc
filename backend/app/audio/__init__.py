"""Audio management feature module.

Purpose: Audio batch/asset persistence, query API, and preprocessing.
Responsibilities: Models, repositories, read API, preprocessing pipeline.
Dependencies: auth, shared.database, shared.domain, storage, ffmpeg.
Extension points: AI inference stages after preprocessing.
"""

from app.audio.models import AudioAsset, AudioBatch
from app.audio.repository import (
    AudioBatchRepository,
    AudioRepository,
    SqlAlchemyAudioBatchRepository,
    SqlAlchemyAudioRepository,
)

__all__ = [
    "AudioAsset",
    "AudioBatch",
    "AudioBatchRepository",
    "AudioRepository",
    "SqlAlchemyAudioBatchRepository",
    "SqlAlchemyAudioRepository",
]
