"""Global FastAPI exception handlers."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.exceptions.base import AppException
from app.shared.logging.setup import get_logger
from app.shared.response.schemas import ErrorBody, ErrorResponse

logger = get_logger(__name__)


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    logger.warning(
        "app_exception",
        code=exc.code,
        message=exc.message,
        path=request.url.path,
        details=exc.details,
    )
    body = ErrorResponse(
        error=ErrorBody(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=exc.errors(),
    )
    body = ErrorResponse(
        error=ErrorBody(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"errors": exc.errors()},
        )
    )
    return JSONResponse(status_code=422, content=body.model_dump())


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    logger.warning(
        "http_exception",
        path=request.url.path,
        status_code=exc.status_code,
        detail=str(exc.detail),
    )
    body = ErrorResponse(
        error=ErrorBody(
            code="HTTP_ERROR",
            message=str(exc.detail),
            details={},
        )
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
    )
    body = ErrorResponse(
        error=ErrorBody(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details={},
        )
    )
    return JSONResponse(status_code=500, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-wide exception handlers."""
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
