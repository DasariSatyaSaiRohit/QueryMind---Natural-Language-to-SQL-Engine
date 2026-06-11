import json
from typing import Any, Optional
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


async def redis_get(key: str) -> Optional[Any]:
    r = await get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def redis_set(key: str, value: Any, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.set(key, json.dumps(value), ex=ttl)


async def redis_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


async def redis_lpush(key: str, *values: str) -> None:
    r = await get_redis()
    await r.lpush(key, *values)


async def redis_lrange(key: str, start: int = 0, end: int = -1) -> list[str]:
    r = await get_redis()
    return await r.lrange(key, start, end)


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
