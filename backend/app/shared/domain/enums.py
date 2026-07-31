"""Domain enumerations (ubiquitous language)."""

from enum import Enum


class UserRole(str, Enum):
    """Platform user roles."""

    ADMIN = "ADMIN"
    EVALUATOR = "EVALUATOR"


class BatchStatus(str, Enum):
    """Lifecycle status for an audio batch."""

    UPLOADED = "UPLOADED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AudioStatus(str, Enum):
    """Lifecycle status for a single audio asset."""

    UPLOADED = "UPLOADED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobStatus(str, Enum):
    """Lifecycle status for an asynchronous processing job."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EmotionTone(str, Enum):
    """Predicted emotional tone."""

    NEUTRAL = "NEUTRAL"
    SATISFIED = "SATISFIED"
    FRUSTRATED = "FRUSTRATED"
    UPSET = "UPSET"
    DISTRESSED = "DISTRESSED"


class EmotionIntensity(str, Enum):
    """Predicted emotional intensity."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class NoiseSeverity(str, Enum):
    """Background noise severity."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AudioQuality(str, Enum):
    """Perceived audio quality class."""

    CLEAR = "CLEAR"
    SLIGHTLY_IMPAIRED = "SLIGHTLY_IMPAIRED"
    SEVERELY_IMPAIRED = "SEVERELY_IMPAIRED"
