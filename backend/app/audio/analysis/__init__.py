"""Shared audio analysis foundation.

Purpose: Produce reusable VAD + signal feature artifacts for future AI engines.
Responsibilities: Silero VAD, segmentation, feature extraction, persistence.
Dependencies: StorageProvider, numpy/librosa/torch, AudioRepository.
Extension points: Technical / Acoustic / Speech intelligence consumers.
"""

from app.audio.analysis.service import AnalysisService

__all__ = ["AnalysisService"]
