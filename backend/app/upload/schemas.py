"""Upload API and service schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class RejectedFile(BaseModel):
    """Description of a rejected upload candidate."""

    filename: str
    reason: str


class UploadResultData(BaseModel):
    """Successful upload response payload."""

    batch_id: UUID
    job_id: UUID
    files_uploaded: int
    files_rejected: int
    rejected_files: list[RejectedFile] = Field(default_factory=list)


class ValidatedAudioFile(BaseModel):
    """In-memory representation of a validated audio candidate."""

    model_config = {"arbitrary_types_allowed": True}

    filename: str
    extension: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    content: bytes
