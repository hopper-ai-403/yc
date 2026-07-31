"""Health check response schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthData(BaseModel):
    """Top-level application health payload."""

    status: Literal["healthy", "unhealthy", "degraded"] = "healthy"
    service: str
    version: str
    environment: str


class ComponentHealth(BaseModel):
    """Health status for a single dependency."""

    status: Literal["healthy", "unhealthy", "degraded"]
    component: str
    details: dict[str, object] = Field(default_factory=dict)
