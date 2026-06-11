"""
Health & readiness endpoints.
"""
import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import engine
from app.db.redis import get_redis

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@router.get("/health/ready")
async def readiness():
    """Deep health check: DB + Redis + Ollama."""
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    # Redis
    try:
        r = await get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(settings.OLLAMA_URL.replace("/api/chat", "/api/tags"))
            checks["ollama"] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
    except Exception as exc:
        checks["ollama"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
