import logging
from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def cache_get(key: str) -> Optional[str]:
    client = get_redis()
    try:
        value = await client.get(key)
        return value
    except Exception as exc:
        logger.warning(f"cache_get failed for key={key!r}: {exc}")
        return None


async def cache_set(key: str, value: str, ttl: int) -> None:
    client = get_redis()
    try:
        await client.setex(key, ttl, value)
    except Exception as exc:
        logger.warning(f"cache_set failed for key={key!r}: {exc}")


async def cache_delete(key: str) -> None:
    client = get_redis()
    try:
        await client.delete(key)
    except Exception as exc:
        logger.warning(f"cache_delete failed for key={key!r}: {exc}")


async def cache_delete_pattern(pattern: str) -> None:
    client = get_redis()
    try:
        cursor = 0
        keys_to_delete: list[str] = []
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
            keys_to_delete.extend(keys)
            if cursor == 0:
                break
        if keys_to_delete:
            await client.delete(*keys_to_delete)
            logger.debug(f"cache_delete_pattern: deleted {len(keys_to_delete)} keys matching {pattern!r}")
    except Exception as exc:
        logger.warning(f"cache_delete_pattern failed for pattern={pattern!r}: {exc}")


async def cache_exists(key: str) -> bool:
    client = get_redis()
    try:
        result = await client.exists(key)
        return bool(result)
    except Exception as exc:
        logger.warning(f"cache_exists failed for key={key!r}: {exc}")
        return False


async def cache_ttl(key: str) -> int:
    client = get_redis()
    try:
        ttl = await client.ttl(key)
        return int(ttl)
    except Exception as exc:
        logger.warning(f"cache_ttl failed for key={key!r}: {exc}")
        return -1


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")
