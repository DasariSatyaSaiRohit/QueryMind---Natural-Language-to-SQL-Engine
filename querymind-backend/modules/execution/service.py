"""
modules/execution/service.py
Async execution service — wraps the synchronous executor in a thread pool
and dispatches Celery tasks after returning results.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone

from core.redis_client import get_redis
from modules.execution.executor import execute_sync
from modules.session.store import session_store

logger = logging.getLogger(__name__)


async def execute_query(
    session_id: str,
    sql: str,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    1. Resolve SQLAlchemy engine from session store
       (triggers lazy Redis reconstruction if engine evicted from memory).
    2. Run execute_sync in a thread pool executor.
    3. Compute sql_hash for archiving.
    4. Dispatch persist_history and archive_result Celery tasks (fire-and-forget).
    5. Return the ExecutionResult dict.
    """
    from workers.tasks import archive_result, persist_history  # avoid circular at import time

    engine = session_store.get_engine(session_id)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        execute_sync,
        engine,
        sql,
        page,
        page_size,
    )

    # Build history record
    sql_hash = hashlib.sha256(sql.encode()).hexdigest()[:16]
    history_record = {
        "sql": sql,
        "question": None,          # populated by query/service.py when available
        "row_count": result["row_count"],
        "execution_time_ms": result["execution_time_ms"],
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "success": True,
        "truncated": result["truncated"],
    }

    # Fire-and-forget Celery tasks
    persist_history.delay(session_id=session_id, record=history_record)
    archive_result.delay(
        session_id=session_id,
        sql_hash=sql_hash,
        result_json=json.dumps(result),
    )

    return result


async def get_history(session_id: str) -> list[dict]:
    """
    Read exec_history:{session_id} from Redis.
    Returns up to 20 most recent records (LRANGE 0 19).
    Returns empty list if key does not exist.
    """
    redis = get_redis()
    key = f"exec_history:{session_id}"

    try:
        raw_entries = redis.lrange(key, 0, 19)
    except Exception as exc:  # noqa: BLE001
        logger.error("get_history Redis error for session=%s: %s", session_id, exc)
        return []

    records: list[dict] = []
    for raw in raw_entries:
        try:
            records.append(json.loads(raw))
        except json.JSONDecodeError:
            logger.warning("Corrupt history entry for session=%s — skipping", session_id)

    return records
