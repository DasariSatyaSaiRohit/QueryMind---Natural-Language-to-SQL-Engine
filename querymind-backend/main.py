import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core.config import settings
from core.context import get_request_id, get_session_id
from core.exceptions import QueryMindError, RateLimitError
from core.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    global_exception_handler,
)
from core.rate_limit import limiter
from core.redis_client import close_redis


# ── Structured logging ────────────────────────────────────────────────────────

class _ContextFilter(logging.Filter):
    """Inject request_id and session_id from ContextVars into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()  # type: ignore[attr-defined]
        record.session_id = get_session_id()  # type: ignore[attr-defined]
        return True


def _configure_logging() -> None:
    log_format = (
        "%(asctime)s [%(levelname)s] "
        "request_id=%(request_id)s session_id=%(session_id)s "
        "%(name)s: %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(log_format))
    handler.addFilter(_ContextFilter())

    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    root.handlers = [handler]

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"QueryMind backend starting (env={settings.ENVIRONMENT})")
    yield
    logger.info("QueryMind backend shutting down — closing connections")
    await close_redis()


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="QueryMind Backend",
        description="AI-powered natural-language-to-SQL query engine",
        version="1.0.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # ── Slowapi state (must come before SlowAPIMiddleware) ────────────────────
    app.state.limiter = limiter

    # ── Middleware stack (registered bottom-up; executes top-down) ───────────
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────
    app.add_exception_handler(QueryMindError, global_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, global_exception_handler)  # type: ignore[arg-type]

    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return await global_exception_handler(
            request,
            RateLimitError("Too many requests — please slow down and try again."),
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]

    # ── Routers ───────────────────────────────────────────────────────────────
    # Routers are registered lazily so module stubs can be built one at a time.
    # Each import is guarded so missing modules don't crash the app during
    # incremental development.

    try:
        from modules.session.router import router as session_router
        app.include_router(session_router, prefix="/api/session", tags=["session"])
    except ImportError:
        logger.warning("modules.session.router not yet implemented — skipping")

    try:
        from modules.schema.router import router as schema_router
        app.include_router(schema_router, prefix="/api/schema", tags=["schema"])
    except ImportError:
        logger.warning("modules.schema.router not yet implemented — skipping")

    try:
        from modules.ai.router import router as ai_router
        app.include_router(ai_router, prefix="/api/query", tags=["ai"])
    except ImportError:
        logger.warning("modules.ai.router not yet implemented — skipping")

    try:
        from modules.execution.router import router as execution_router
        app.include_router(execution_router, prefix="/api/query", tags=["execution"])
    except ImportError:
        logger.warning("modules.execution.router not yet implemented — skipping")

    try:
        from modules.query.router import router as query_router
        app.include_router(query_router, prefix="/api/query", tags=["query"])
    except ImportError:
        logger.warning("modules.query.router not yet implemented — skipping")

    # ── Health endpoints ──────────────────────────────────────────────────────

    @app.get("/health", tags=["health"])
    async def health():
        return {
            "service": "querymind-backend",
            "status": "ok",
            "environment": settings.ENVIRONMENT,
            "version": "1.0.0",
        }

    @app.get("/health/detailed", tags=["health"])
    async def health_detailed():
        from core.redis_client import get_redis

        redis_status = "ok"
        try:
            await get_redis().ping()
        except Exception as exc:
            redis_status = f"error: {exc}"

        return {
            "service": "querymind-backend",
            "status": "ok",
            "environment": settings.ENVIRONMENT,
            "version": "1.0.0",
            "dependencies": {
                "redis": redis_status,
            },
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )
