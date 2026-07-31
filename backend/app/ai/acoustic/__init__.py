"""Acoustic intelligence engine.

Purpose: Background noise detection, classification, and severity.
Responsibilities: Deterministic acoustic assessment over Sprint 5 artifacts.
Dependencies: audio.analysis artifacts, StorageProvider, AudioRepository.
Extension points: NoiseDetector / NoiseClassifier / NoiseSeverityEstimator.
"""

from app.ai.acoustic.service import AcousticService

__all__ = ["AcousticService"]
