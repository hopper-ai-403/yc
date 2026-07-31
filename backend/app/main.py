"""FastAPI application factory, lifespan, and entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import Settings, get_settings
from app.health.router import router as health_router
from app.infrastructure.redis.client import get_redis_client
from app.shared.database.session import get_engine
from app.shared.exceptions.handlers import register_exception_handlers
from app.shared.logging.setup import get_logger, setup_logging
from app.shared.middleware.request_id import RequestIdMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    settings: Settings = app.state.settings
    setup_logging(settings.logging)
    logger.info(
        "application_starting",
        environment=settings.app.environment,
        version=settings.app.version,
    )

    redis_client = get_redis_client()
    await redis_client.connect()
    app.state.redis = redis_client

    yield

    logger.info("application_shutting_down")
    await redis_client.disconnect()
    engine = get_engine()
    await engine.dispose()


def create_application() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        description=(
            "Production-grade Audio Intelligence Platform for batch analysis "
            "of customer call recordings with structured AI predictions."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        contact={
            "name": "Audio Intelligence Platform",
        },
        license_info={
            "name": "Proprietary",
        },
    )

    application.state.settings = settings

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestIdMiddleware)

    register_exception_handlers(application)

    application.include_router(health_router)

    return application


app = create_application()
