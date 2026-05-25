"""
QueryMind background tasks.

All tasks are fire-and-forget — dispatched after the HTTP response is sent.
They MUST NOT block the request path.

Redis key schema used here:
  schema:{session_id}:{table_name}  — per-table metadata JSON
  schema:{session_id}:__index__     — JSON list of table names
  session:{session_id}:conn         — encrypted connection string
  session:{session_id}:meta         — session metadata JSON
  usage_log:{session_id}            — LPUSH list of usage records (capped 100)
  exec_history:{session_id}         — LPUSH list of execution records (capped 100)
  query_cache:{cache_key}           — cached SQL generation result
  exec_result:{session_id}:{hash}   — full execution result (5 min TTL)
"""

import json
import logging
import time
from datetime import datetime, timezone

import redis as redis_sync

from core.config import settings
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sync_redis() -> redis_sync.Redis:
    """Return a synchronous Redis client for use inside Celery worker processes."""
    return redis_sync.from_url(settings.REDIS_URL, decode_responses=True)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Task 1 — warm_cache
# ---------------------------------------------------------------------------

@celery_app.task(
    name="querymind.tasks.warm_cache",
    bind=True,
    max_retries=2,
)
def warm_cache(self, session_id: str, encrypted_conn_str: str) -> None:
    """
    Introspect the full DB schema for a session and populate Redis.
    Triggered after a successful session connect.
    Retries up to 2 times with exponential back-off (1 s, 2 s).
    """
    attempt = self.request.retries
    start = time.monotonic()

    try:
        from sqlalchemy import create_engine, inspect, text
        from sqlalchemy.pool import NullPool
        from core.database import decrypt_connection_string

        conn_str = decrypt_connection_string(encrypted_conn_str)

        # Temporary single-use engine — disposed after introspection
        engine = create_engine(
            conn_str,
            poolclass=NullPool,
        )

        r = _sync_redis()
        table_names: list[str] = []

        try:
            inspector = inspect(engine)
            raw_tables = inspector.get_table_names()

            for table_name in raw_tables:
                # Columns
                columns = []
                for col in inspector.get_columns(table_name):
                    columns.append({
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                        "primary_key": col.get("primary_key", False),
                        "default": str(col["default"]) if col.get("default") is not None else None,
                    })

                # Primary key
                pk_info = inspector.get_pk_constraint(table_name)
                pk_columns = pk_info.get("constrained_columns", []) if pk_info else []

                # Foreign keys
                fk_list = []
                for fk in inspector.get_foreign_keys(table_name):
                    fk_list.append({
                        "constrained_columns": fk.get("constrained_columns", []),
                        "referred_table": fk.get("referred_table", ""),
                        "referred_columns": fk.get("referred_columns", []),
                    })

                # Indexes
                idx_list = []
                for idx in inspector.get_indexes(table_name):
                    idx_list.append({
                        "name": idx.get("name", ""),
                        "columns": idx.get("column_names", []),
                        "unique": idx.get("unique", False),
                    })

                # Row count estimate (PostgreSQL-specific; falls back to 0)
                row_count_estimate = 0
                try:
                    with engine.connect() as conn:
                        result = conn.execute(
                            text(
                                "SELECT reltuples::bigint FROM pg_class "
                                "WHERE relname = :tname"
                            ),
                            {"tname": table_name},
                        )
                        row = result.fetchone()
                        if row:
                            row_count_estimate = int(row[0])
                except Exception:
                    pass  # non-PostgreSQL or permission denied — not fatal

                table_meta = {
                    "table_name": table_name,
                    "columns": columns,
                    "primary_key": pk_columns,
                    "foreign_keys": fk_list,
                    "indexes": idx_list,
                    "row_count_estimate": row_count_estimate,
                }

                cache_key = f"schema:{session_id}:{table_name}"
                r.setex(cache_key, settings.SCHEMA_CACHE_TTL, json.dumps(table_meta))
                table_names.append(table_name)

            # Store the table-name index
            index_key = f"schema:{session_id}:__index__"
            r.setex(index_key, settings.SCHEMA_CACHE_TTL, json.dumps(table_names))

        finally:
            engine.dispose()

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            f"[warm_cache] session_id={session_id} "
            f"table_count={len(table_names)} duration_ms={duration_ms}"
        )

    except Exception as exc:
        countdown = 2 ** attempt  # 1 s, 2 s
        logger.warning(
            f"[warm_cache] attempt={attempt} session_id={session_id} "
            f"error={exc!r} retrying in {countdown}s"
        )
        raise self.retry(exc=exc, countdown=countdown)


# ---------------------------------------------------------------------------
# Task 2 — refresh_expiring_caches
# ---------------------------------------------------------------------------

@celery_app.task(name="querymind.tasks.refresh_expiring_caches")
def refresh_expiring_caches() -> None:
    """
    Periodic task (every 55 min via Celery beat).
    Finds schema index keys with TTL < 300 s and re-dispatches warm_cache.
    """
    r = _sync_redis()
    refreshed = 0
    cursor = 0

    while True:
        cursor, keys = r.scan(cursor=cursor, match="schema:*:__index__", count=200)
        for key in keys:
            ttl = r.ttl(key)
            if 0 < ttl < 300:
                # key format: schema:{session_id}:__index__
                parts = key.split(":")
                if len(parts) >= 3:
                    session_id = parts[1]
                    conn_key = f"session:{session_id}:conn"
                    encrypted_conn_str = r.get(conn_key)
                    if encrypted_conn_str:
                        warm_cache.delay(session_id, encrypted_conn_str)
                        refreshed += 1
                    else:
                        logger.debug(
                            f"[refresh_expiring_caches] "
                            f"session={session_id} conn expired — skipping"
                        )
        if cursor == 0:
            break

    logger.info(f"[refresh_expiring_caches] refreshed={refreshed} sessions")


# ---------------------------------------------------------------------------
# Task 3 — log_usage
# ---------------------------------------------------------------------------

@celery_app.task(name="querymind.tasks.log_usage")
def log_usage(
    session_id: str,
    question: str,
    tokens_used: int,
    latency_ms: int,
    cache_hit: bool,
) -> None:
    """
    Appends a usage record to Redis list for the session.
    Capped at 100 entries. 24 h TTL.
    """
    r = _sync_redis()
    key = f"usage_log:{session_id}"
    record = json.dumps({
        "question": question,
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
        "cache_hit": cache_hit,
        "timestamp_iso": _now_iso(),
    })
    pipe = r.pipeline()
    pipe.lpush(key, record)
    pipe.ltrim(key, 0, 99)
    pipe.expire(key, 86400)
    pipe.execute()
    logger.debug(f"[log_usage] session_id={session_id} tokens={tokens_used} cache_hit={cache_hit}")


# ---------------------------------------------------------------------------
# Task 4 — cache_query_result
# ---------------------------------------------------------------------------

@celery_app.task(name="querymind.tasks.cache_query_result")
def cache_query_result(cache_key: str, result_json: str) -> None:
    """
    Stores a generated SQL result in the Redis query cache.
    TTL: settings.QUERY_CACHE_TTL (default 24 h).
    """
    r = _sync_redis()
    full_key = f"query_cache:{cache_key}"
    r.setex(full_key, settings.QUERY_CACHE_TTL, result_json)
    logger.debug(f"[cache_query_result] key={full_key} ttl={settings.QUERY_CACHE_TTL}s")


# ---------------------------------------------------------------------------
# Task 5 — persist_history
# ---------------------------------------------------------------------------

@celery_app.task(name="querymind.tasks.persist_history")
def persist_history(session_id: str, record: dict) -> None:
    """
    Appends an execution record to the session's query history in Redis.
    Capped at 100 entries. 24 h TTL.

    Expected record fields:
      sql, question, row_count, execution_time_ms, timestamp_iso, success
    """
    r = _sync_redis()
    key = f"exec_history:{session_id}"
    payload = json.dumps(record, default=str)
    pipe = r.pipeline()
    pipe.lpush(key, payload)
    pipe.ltrim(key, 0, 99)
    pipe.expire(key, 86400)
    pipe.execute()
    logger.debug(f"[persist_history] session_id={session_id} success={record.get('success')}")


# ---------------------------------------------------------------------------
# Task 6 — archive_result
# ---------------------------------------------------------------------------

@celery_app.task(name="querymind.tasks.archive_result")
def archive_result(session_id: str, sql_hash: str, result_json: str) -> None:
    """
    Stores the full execution result in Redis for 5 minutes.
    Allows re-pagination without re-executing the SQL.
    """
    r = _sync_redis()
    key = f"exec_result:{session_id}:{sql_hash}"
    r.setex(key, 300, result_json)
    logger.debug(f"[archive_result] session_id={session_id} hash={sql_hash} ttl=300s")
