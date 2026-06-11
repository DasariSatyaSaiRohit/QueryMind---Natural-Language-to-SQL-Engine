import signal
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.v1.router import api_router
from app.middleware.sanitization import SanitizationMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.workers.rabbitmq_client import rabbitmq_client
from app.services.ai_service import warmup_ollama
from app.db.redis import close_redis
from app.db.session import engine, Base

# Must import all models so Base registers them
from app.models.connection import Connection
from app.models.query_history import QueryHistory

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (like TypeORM synchronize: true)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    # Startup
    try:
        await rabbitmq_client.connect()
    except Exception as exc:
        logger.warning("service.rabbitmq_unavailable", error=str(exc))

    await warmup_ollama()
    logger.info("service.ready")

    yield

    # Shutdown
    await rabbitmq_client.close()
    await engine.dispose()
    await close_redis()
    logger.info("service.shutdown_complete")


# ── Single app instance ───────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,  # ← pass lifespan here
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# app.add_middleware(RequestIDMiddleware)
# app.add_middleware(SanitizationMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(api_router)

# ── SIGTERM ───────────────────────────────────────────────────────────────────
_shutdown_event = asyncio.Event()

def _handle_sigterm(signum, frame):
    _shutdown_event.set()

signal.signal(signal.SIGTERM, _handle_sigterm)

# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "correlation_id": request_id,
        },
    )