"""Import all ORM models so Alembic and metadata discover them."""

from app.audio.models import AudioAsset, AudioBatch
from app.audit.models import AuditLog
from app.auth.models import User
from app.jobs.models import Job
from app.prediction.models import Prediction

__all__ = [
    "AudioAsset",
    "AudioBatch",
    "AuditLog",
    "Job",
    "Prediction",
    "User",
]
