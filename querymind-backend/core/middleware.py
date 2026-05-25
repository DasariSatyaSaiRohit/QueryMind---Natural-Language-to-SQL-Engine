import logging
import time
import traceback
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from core.context import get_request_id, set_request_id
from core.exceptions import QueryMindError

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        set_request_id(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        status_code = response.status_code
        log_line = (
            f"{request.method} {request.url.path} "
            f"status={status_code} duration_ms={duration_ms}"
        )

        if status_code < 400:
            logger.info(log_line)
        elif status_code < 500:
            logger.warning(log_line)
        else:
            logger.error(log_line)

        return response


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id()

    if isinstance(exc, QueryMindError):
        logger.warning(
            f"QueryMindError: {exc.error_type} — {exc.message} (request_id={request_id})"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_type": exc.error_type,
                "message": exc.message,
                "request_id": request_id,
            },
        )

    logger.error(
        f"Unhandled exception (request_id={request_id}): {traceback.format_exc()}"
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_type": "internal_error",
            "message": "An unexpected error occurred. Please try again.",
            "request_id": request_id,
        },
    )
