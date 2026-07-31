"""Unit tests for configuration and shared primitives."""

from app.config.settings import Settings, get_settings
from app.shared.exceptions import ValidationException
from app.shared.response.schemas import ErrorResponse, SuccessResponse


def test_settings_loads_defaults() -> None:
    settings = Settings()
    assert settings.app.name == "Audio Intelligence Platform"
    assert settings.app.version == "0.1.0"
    assert settings.database.pool_size >= 1


def test_neon_url_normalization() -> None:
    from app.config.settings import DatabaseSettings

    settings = DatabaseSettings(
        url=("postgresql://user:pass@ep-xxx-pooler.us-east-2.aws.neon.tech/neondb"),
        direct_url=("postgres://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb"),
    )
    assert settings.url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in settings.url
    assert settings.direct_url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in settings.direct_url
    assert settings.migration_url == settings.direct_url


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()


def test_success_response_envelope() -> None:
    payload = SuccessResponse(message="ok", data={"status": "healthy"})
    dumped = payload.model_dump()
    assert dumped["success"] is True
    assert dumped["message"] == "ok"
    assert dumped["data"]["status"] == "healthy"


def test_error_response_envelope() -> None:
    payload = ErrorResponse(
        error={
            "code": "VALIDATION_ERROR",
            "message": "Invalid",
            "details": {},
        }
    )
    dumped = payload.model_dump()
    assert dumped["success"] is False
    assert dumped["error"]["code"] == "VALIDATION_ERROR"


def test_validation_exception_defaults() -> None:
    exc = ValidationException("bad input")
    assert exc.code == "VALIDATION_ERROR"
    assert exc.status_code == 422
    assert exc.message == "bad input"
