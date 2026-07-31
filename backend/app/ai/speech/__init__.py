"""Speech intelligence engine.

Purpose: Speech emotion recognition (tone + intensity) via pluggable SER models.
Responsibilities: Normalized emotion outputs over normalized waveforms.
Dependencies: audio.analysis waveform utilities, StorageProvider, AudioRepository.
Extension points: SpeechEmotionModel implementations (HuggingFace default).
"""

from app.ai.speech.service import SpeechService

__all__ = ["SpeechService"]
