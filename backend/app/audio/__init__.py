"""Audio management feature module.

Purpose: Audio batch and asset persistence.
Responsibilities: Batch/asset models and repositories.
Dependencies: auth, shared.database, shared.domain.
Extension points: Upload pipeline, validation services.
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
