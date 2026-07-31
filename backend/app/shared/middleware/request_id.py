"""Request ID middleware for correlating logs across a request."""

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.shared.logging.setup import bind_context, clear_context, get_logger

logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request_id to every request and response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        bind_context(request_id=request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request_failed",
                path=request.url.path,
                method=request.method,
                latency=latency_ms,
                status="error",
            )
            clear_context()
            raise

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            latency=latency_ms,
            status="ok" if response.status_code < 500 else "error",
        )
        clear_context()
        return response
