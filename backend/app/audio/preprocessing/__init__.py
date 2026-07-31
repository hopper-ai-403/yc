"""Audio preprocessing package.

Purpose: Standardize uploaded audio before AI inference.
Responsibilities: Download, validate, probe, normalize, upload, persist.
Dependencies: StorageProvider, ffmpeg/ffprobe, AudioRepository.
Extension points: Swap normalizer/loudness strategy without touching jobs.
"""

from app.audio.preprocessing.service import PreprocessingService

__all__ = ["PreprocessingService"]
