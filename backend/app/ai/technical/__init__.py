"""Technical intelligence engine.

Purpose: Technical-only outputs (quality, speaker overlap, long silence).
Responsibilities: Deterministic scoring over Sprint 5 analysis artifacts.
Dependencies: audio.analysis artifacts, StorageProvider, AudioRepository.
Extension points: OverlapDetector implementations (signal / pyannote / neural).
"""

from app.ai.technical.service import TechnicalService

__all__ = ["TechnicalService"]
