"""Audio management feature module.

Purpose: Audio batch/asset persistence, query API, preprocessing, and analysis.
Responsibilities: Models, repositories, read API, preprocess + analysis pipelines.
Dependencies: auth, shared.database, shared.domain, storage, ffmpeg, Silero/librosa.
Extension points: AI inference engines consuming analysis artifacts.
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
