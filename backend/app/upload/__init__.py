"""Upload feature module.

Purpose: Accept ZIP/audio uploads, validate, store in R2, create batch/job.
Responsibilities: Upload API, validation, storage orchestration.
Dependencies: audio/auth/jobs repositories, StorageProvider.
Extension points: Auth-bound uploader identity, virus scanning.
"""

from app.upload.api import router

__all__ = ["router"]
