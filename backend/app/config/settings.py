"""Typed application settings using pydantic-settings.

All configuration is loaded from environment variables and optional .env files.
Business logic must never call os.getenv() directly.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv(Path.cwd() / ".env", override=False)


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
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


class DatabaseSettings(BaseSettings):
    """Neon PostgreSQL database settings.

    Use the Neon pooled connection string for the application (`url`) and the
    direct (non-pooler) connection string for Alembic migrations (`direct_url`).
    """

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="ignore")

    url: str = (
        "postgresql+psycopg://user:password@ep-xxx.region.aws.neon.tech/"
        "neondb?sslmode=require"
    )
    direct_url: str = ""
    pool_size: int = 5
    max_overflow: int = 5
    pool_timeout: int = 30
    pool_recycle: int = 300
    echo: bool = False

    @field_validator("url", "direct_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if not isinstance(value, str) or not value:
            return value
        normalized = value
        if normalized.startswith("postgres://"):
            normalized = "postgresql+psycopg://" + normalized.removeprefix(
                "postgres://"
            )
        elif normalized.startswith("postgresql://"):
            normalized = "postgresql+psycopg://" + normalized.removeprefix(
                "postgresql://"
            )
        if "neon.tech" in normalized and "sslmode=" not in normalized:
            separator = "&" if "?" in normalized else "?"
            normalized = f"{normalized}{separator}sslmode=require"
        return normalized

    @property
    def migration_url(self) -> str:
        """Prefer the direct Neon endpoint for migrations when configured."""
        return self.direct_url or self.url


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


class UploadSettings(BaseSettings):
    """Upload pipeline validation and safety limits."""

    model_config = SettingsConfigDict(env_prefix="UPLOAD_", extra="ignore")

    max_file_size_bytes: int = 100 * 1024 * 1024
    max_zip_size_bytes: int = 500 * 1024 * 1024
    max_files_per_batch: int = 500
    max_uncompressed_zip_bytes: int = 1024 * 1024 * 1024
    allowed_extensions: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [".wav", ".mp3", ".ogg"]
    )
    allowed_mime_types: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "audio/wav",
            "audio/x-wav",
            "audio/wave",
            "audio/mpeg",
            "audio/mp3",
            "audio/ogg",
            "application/ogg",
            "application/zip",
            "application/x-zip-compressed",
            "multipart/x-zip",
        ]
    )
    system_uploader_email: str = "system.upload@audio-intelligence.local"

    @field_validator("allowed_extensions", "allowed_mime_types", mode="before")
    @classmethod
    def parse_csv_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


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


class JobSettings(BaseSettings):
    """Job orchestration settings."""

    model_config = SettingsConfigDict(env_prefix="JOB_", extra="ignore")

    max_retries: int = 3
    retry_backoff_base_seconds: int = 2
    simulate_processing_ms: int = 100
    heartbeat_ttl_seconds: int = 60
    progress_ttl_seconds: int = 86_400


class PreprocessingSettings(BaseSettings):
    """Audio preprocessing / ffmpeg settings."""

    model_config = SettingsConfigDict(env_prefix="PREPROCESS_", extra="ignore")

    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    ffmpeg_timeout_seconds: int = 120
    ffprobe_timeout_seconds: int = 30
    target_sample_rate: int = 16_000
    target_channels: int = 1
    target_lufs: float = -23.0
    target_true_peak_db: float = -1.5
    loudness_range: float = 11.0
    trim_silence: bool = True
    silence_threshold_db: float = -50.0
    silence_min_duration_seconds: float = 0.1
    allowed_codecs: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "pcm_s16le",
            "pcm_s24le",
            "pcm_s32le",
            "pcm_f32le",
            "pcm_u8",
            "pcm_mulaw",
            "pcm_alaw",
            "flac",
            "mp3",
            "aac",
            "vorbis",
            "opus",
        ]
    )

    @field_validator("allowed_codecs", mode="before")
    @classmethod
    def parse_allowed_codecs(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class AnalysisSettings(BaseSettings):
    """Shared audio analysis foundation settings."""

    model_config = SettingsConfigDict(env_prefix="ANALYSIS_", extra="ignore")

    vad_backend: Literal["silero", "energy"] = "silero"
    expected_sample_rate: int = 16_000
    timeout_seconds: int = 120
    vad_threshold: float = 0.5
    vad_min_speech_ms: int = 250
    vad_min_silence_ms: int = 100
    vad_window_samples: int = 512


class TechnicalSettings(BaseSettings):
    """Technical intelligence engine settings (deterministic rules)."""

    model_config = SettingsConfigDict(env_prefix="TECHNICAL_", extra="ignore")

    # Long silence rules.
    long_silence_seconds: float = 6.0
    total_silence_ratio: float = 0.55
    min_speech_ratio: float = 0.35

    # Quality scoring thresholds.
    clear_threshold: float = 85.0
    slightly_impaired_threshold: float = 65.0

    # Quality penalties (weights sum to 100 max).
    snr_penalty_weight: float = 30.0
    missing_snr_penalty: float = 12.0
    clipping_penalty_weight: float = 25.0
    dynamic_range_penalty_weight: float = 20.0
    silence_penalty_weight: float = 15.0
    speech_presence_penalty_weight: float = 10.0

    # Quality input thresholds.
    snr_good_db: float = 25.0
    snr_ok_db: float = 12.0
    dynamic_range_good_db: float = 18.0
    dynamic_range_bad_db: float = 6.0
    silence_ratio_warn: float = 0.35
    silence_ratio_bad: float = 0.75
    speech_ratio_good: float = 0.6
    speech_ratio_bad: float = 0.15

    # Overlap heuristics (signal-based detector).
    overlap_threshold: float = 0.6
    overlap_density_weight: float = 0.35
    overlap_zcr_weight: float = 0.2
    overlap_bandwidth_weight: float = 0.25
    overlap_spread_weight: float = 0.2
    overlap_density_full_at: float = 0.6
    overlap_zcr_min: float = 0.02
    overlap_zcr_max: float = 0.2
    overlap_bandwidth_min_hz: float = 1500.0
    overlap_bandwidth_max_hz: float = 5000.0
    overlap_spread_min: float = 0.4
    overlap_spread_max: float = 1.4


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
    upload: UploadSettings = Field(default_factory=UploadSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    ai: AISettings = Field(default_factory=AISettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    jobs: JobSettings = Field(default_factory=JobSettings)
    preprocessing: PreprocessingSettings = Field(default_factory=PreprocessingSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    technical: TechnicalSettings = Field(default_factory=TechnicalSettings)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
