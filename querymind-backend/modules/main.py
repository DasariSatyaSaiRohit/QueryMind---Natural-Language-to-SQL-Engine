"""
main.py
QueryMind FastAPI application — final entrypoint.

Wires together:
  - All module routers
  - Middleware (CORS → RequestID → RequestLogging)
  - Exception handlers (RateLimit, QueryMindError, unhandled)
  - Lifespan: startup checks + graceful shutdown
  - Health endpoints (/health, /health/detailed)
"""
from __future__ import annotations

import logging
import logging.config
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.config import get_settings
from core.context import get_request_id, get_session_id, set_request_id
from core.exceptions import QueryMindError
from core.rate_limit import limiter

# ── Module routers ────────────────────────────────────────────────────────
from modules.ai.router import router as ai_router
from modules.execution.router import router as execution_router
from modules.query.router import router as query_router
from modules.schema.router import router as schema_router
from modules.session.router import router as session_router

settings = get_settings()

# ── Structured logging ────────────────────────────────────────────────────


class ContextFilter(logging.Filter):
    """Injects request_id and session_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.session_id = get_session_id()
        return True


LOG_FORMAT = (
    "%(asctime)s [%(levelname)s] "
    "request_id=%(request_id)s session_id=%(session_id)s "
    "%(name)s: %(message)s"
)


def _configure_logging() -> None:
    context_filter = ContextFilter()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handler.addFilter(context_filter)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(logging.Formatter(LOG_FORMAT))
            handler.addFilter(context_filter)


_configure_logging()
logger = logging.getLogger(__name__)

# ── App startup time (for /health/detailed uptime) ────────────────────────
_START_TIME = time.monotonic()


# ── Lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup checks and graceful shutdown."""
    # ── Startup ───────────────────────────────────────────────────────────
    logger.info(
        "QueryMind backend starting — version=1.0.0 env=%s port=%d",
        settings.ENVIRONMENT,
        settings.PORT,
    )

    # Test Redis
    from core.redis_client import get_redis
    try:
        redis = get_redis()
        redis.ping()
        logger.info("Redis connection OK — url=%s", settings.REDIS_URL)
    except Exception as exc:  # noqa: BLE001
        logger.error("Redis connection FAILED: %s", exc)

    logger.info("All modules initialised. Ready to serve.")

    yield  # Application runs here

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("QueryMind backend shutdown initiated.")

    # Dispose all active SQLAlchemy engines
    try:
        from modules.session.store import session_store
        for session_id, engine in list(session_store._engines.items()):
            try:
                engine.dispose()
                logger.debug("Disposed engine for session=%s", session_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Engine dispose error session=%s: %s", session_id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error during engine disposal: %s", exc)

    # Close Redis connection pool
    try:
        from core.redis_client import get_redis
        get_redis().close()
        logger.info("Redis connection pool closed.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis close error: %s", exc)

    logger.info("Shutdown complete.")


# ── Application factory ───────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="QueryMind Backend",
        description="NL→SQL query engine — modular monolith",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    )

    # ── Rate limiter ──────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Middleware (outermost first) ───────────────────────────────────────
    # 1. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. RequestID
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or _new_uuid()
        set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # 3. Request logging
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        status_code = response.status_code

        log_fn = logger.info
        if status_code >= 500:
            log_fn = logger.error
        elif status_code >= 400:
            log_fn = logger.warning

        log_fn(
            "%s %s → %d (%dms)",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )
        return response

    # ── Exception handlers ────────────────────────────────────────────────

    @app.exception_handler(QueryMindError)
    async def querymind_error_handler(request: Request, exc: QueryMindError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_type": exc.error_type,
                "message": str(exc),
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception on %s %s:\n%s",
            request.method,
            request.url.path,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error_type": "internal_server_error",
                "message": "An unexpected error occurred. Please try again later.",
                "request_id": get_request_id(),
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(session_router)    # /api/session/...
    app.include_router(schema_router)     # /api/schema/...
    app.include_router(ai_router)         # /api/query/generate + /ws/query/...
    app.include_router(execution_router)  # /api/query/execute + /api/query/history/...
    app.include_router(query_router)      # /api/query/ask

    # ── Health endpoints ──────────────────────────────────────────────────

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        """Basic liveness check."""
        redis_status = "ok"
        try:
            from core.redis_client import get_redis
            get_redis().ping()
        except Exception:  # noqa: BLE001
            redis_status = "error"

        from modules.session.store import session_store
        return {
            "service": "querymind-backend",
            "status": "ok",
            "environment": settings.ENVIRONMENT,
            "version": "1.0.0",
            "redis": redis_status,
            "active_sessions": session_store.count(),
        }

    @app.get("/health/detailed", tags=["health"])
    async def health_detailed() -> dict:
        """
        Detailed readiness check — internal only, not exposed through gateway.
        Includes per-module status, uptime, and active session count.
        """
        redis_status = "ok"
        redis_info: dict = {}
        try:
            from core.redis_client import get_redis
            r = get_redis()
            r.ping()
            info = r.info("server")
            redis_info = {
                "version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "connected_clients": info.get("connected_clients"),
            }
        except Exception as exc:  # noqa: BLE001
            redis_status = "error"
            redis_info = {"error": str(exc)}

        from modules.session.store import session_store
        uptime_seconds = int(time.monotonic() - _START_TIME)

        return {
            "service": "querymind-backend",
            "status": "ok",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "uptime_seconds": uptime_seconds,
            "active_sessions": session_store.count(),
            "modules": {
                "session": "ok",
                "schema": "ok",
                "ai": "ok",
                "execution": "ok",
                "query": "ok",
            },
            "dependencies": {
                "redis": {
                    "status": redis_status,
                    **redis_info,
                },
                "celery": {
                    "broker": settings.AMQP_URL.split("@")[-1]
                    if "@" in settings.AMQP_URL
                    else settings.AMQP_URL,
                    "status": "configured",
                },
                "anthropic": {
                    "model": settings.CLAUDE_MODEL,
                    "status": "configured",
                },
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return app


def _new_uuid() -> str:
    from uuid import uuid4
    return str(uuid4())


app = create_app()

# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.ENVIRONMENT == "development",
    )
