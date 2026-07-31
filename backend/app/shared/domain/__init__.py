"""Shared domain primitives.

Purpose: Cross-cutting domain enums, value objects, and domain exceptions.
Responsibilities: Encode ubiquitous language and invariants without I/O.
Dependencies: Pydantic, shared exceptions.
Extension points: Add new value objects/enums for future analyzers.
"""

from app.shared.domain.enums import (
    AudioQuality,
    AudioStatus,
    BatchStatus,
    EmotionIntensity,
    EmotionTone,
    JobStatus,
    NoiseSeverity,
    UserRole,
)
from app.shared.domain.exceptions import (
    DomainException,
    ImmutableEntityException,
    InvariantViolationException,
)
from app.shared.domain.value_objects import (
    AudioMetadata,
    ConfidenceScore,
    EmotionResult,
    NoiseResult,
    OverlapResult,
    PredictionResult,
    QualityResult,
    SilenceResult,
)

__all__ = [
    "AudioMetadata",
    "AudioQuality",
    "AudioStatus",
    "BatchStatus",
    "ConfidenceScore",
    "DomainException",
    "EmotionIntensity",
    "EmotionResult",
    "EmotionTone",
    "ImmutableEntityException",
    "InvariantViolationException",
    "JobStatus",
    "NoiseResult",
    "NoiseSeverity",
    "OverlapResult",
    "PredictionResult",
    "QualityResult",
    "SilenceResult",
    "UserRole",
]
