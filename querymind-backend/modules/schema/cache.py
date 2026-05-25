"""
modules/schema/cache.py
Redis schema cache — async read/write/invalidate operations.
All functions use the shared redis_client helpers from core.
"""
from __future__ import annotations

import json
import logging

from core.redis_client import (
    cache_delete_pattern,
    cache_get,
    cache_set,
    cache_ttl,
    get_redis,
)
from core.config import get_settings

logger = logging.getLogger(__name__)


def _table_key(session_id: str, table_name: str) -> str:
    return f"schema:{session_id}:{table_name}"


def _index_key(session_id: str) -> str:
    return f"schema:{session_id}:__index__"


async def get_cached_table(session_id: str, table_name: str) -> dict | None:
    """Return cached table dict from Redis or None on miss."""
    raw = await cache_get(_table_key(session_id, table_name))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Corrupt cache entry for %s:%s", session_id, table_name)
        return None


async def get_cached_tables(
    session_id: str,
    table_names: list[str] | None = None,
) -> dict[str, dict]:
    """
    Return dict of { table_name: table_dict } from Redis.
    If table_names is None: fetch all tables using __index__.
    If table_names is provided: fetch only those tables.
    Skip any table not in cache (partial result is acceptable).
    """
    if table_names is None:
        index = await get_index(session_id)
        if not index:
            return {}
        table_names = index

    result: dict[str, dict] = {}
    for name in table_names:
        data = await get_cached_table(session_id, name)
        if data is not None:
            result[name] = data
    return result


async def store_schema_chunks(
    session_id: str,
    tables: list[dict],
    ttl: int,
) -> None:
    """
    Store each table as a separate Redis key plus the index key.
    Uses a pipeline for batch writes (one round trip).
    """
    if not tables:
        return

    settings = get_settings()
    effective_ttl = ttl or settings.SCHEMA_CACHE_TTL

    redis = get_redis()
    pipe = redis.pipeline()

    table_names: list[str] = []
    for table in tables:
        name = table["table_name"]
        table_names.append(name)
        pipe.set(
            _table_key(session_id, name),
            json.dumps(table),
            ex=effective_ttl,
        )

    # Store the index
    pipe.set(
        _index_key(session_id),
        json.dumps(table_names),
        ex=effective_ttl,
    )

    pipe.execute()
    logger.debug(
        "Stored %d schema chunks for session=%s (ttl=%ds)",
        len(tables),
        session_id,
        effective_ttl,
    )


async def get_index(session_id: str) -> list[str] | None:
    """Return list of cached table names from __index__ key, or None."""
    raw = await cache_get(_index_key(session_id))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Corrupt schema index for session=%s", session_id)
        return None


async def invalidate_session_cache(session_id: str) -> None:
    """Delete all schema:{session_id}:* keys using SCAN + DEL."""
    pattern = f"schema:{session_id}:*"
    await cache_delete_pattern(pattern)
    logger.info("Invalidated schema cache for session=%s", session_id)


async def get_cache_ttl(session_id: str) -> int:
    """Return TTL of __index__ key in seconds. -1 if not cached."""
    return await cache_ttl(_index_key(session_id))
