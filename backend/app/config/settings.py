"""Typed application settings using pydantic-settings.

All configuration is loaded from environment variables and optional .env files.
Business logic must never call os.getenv() directly.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Core application settings."""

    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")

    name: str = "Audio Intelligence Platform"
    version: str = "0.1.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


class DatabaseSettings(BaseSettings):
    """PostgreSQL database settings."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="ignore")

    url: str = "postgresql+psycopg://aip:aip@postgres:5432/aip"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800
    echo: bool = False


class RedisSettings(BaseSettings):
    """Redis settings."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    url: str = "redis://redis:6379/0"
    health_check_interval: int = 30


class JWTSettings(BaseSettings):
    """JWT authentication settings (wired in Sprint 1)."""

    model_config = SettingsConfigDict(env_prefix="JWT_", extra="ignore")

    secret_key: str = "change-me-in-production-use-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7


class R2Settings(BaseSettings):
    """Cloudflare R2 object storage settings."""

    model_config = SettingsConfigDict(env_prefix="R2_", extra="ignore")

    account_id: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    bucket_name: str = "audio-intelligence"
    endpoint_url: str = ""
    region: str = "auto"
    signed_url_expiry_seconds: int = 3600


class LoggingSettings(BaseSettings):
    """Structured logging settings."""

    model_config = SettingsConfigDict(env_prefix="LOGGING_", extra="ignore")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = True
    service_name: str = "audio-intelligence-platform"


class AISettings(BaseSettings):
    """AI inference settings (wired in later sprints)."""

    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    enabled: bool = False
    model_cache_dir: str = "/tmp/model_cache"
    inference_timeout_seconds: int = 120
    batch_size: int = 8


class CelerySettings(BaseSettings):
    """Celery worker settings."""

    model_config = SettingsConfigDict(env_prefix="CELERY_", extra="ignore")

    broker_url: str = "redis://redis:6379/1"
    result_backend: str = "redis://redis:6379/2"
    task_always_eager: bool = False
    task_track_started: bool = True
    worker_prefetch_multiplier: int = 1
    task_acks_late: bool = True


class Settings(BaseSettings):
    """Root settings aggregating all configuration domains."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    r2: R2Settings = Field(default_factory=R2Settings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    ai: AISettings = Field(default_factory=AISettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
