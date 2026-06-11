"""
Schema introspection service.

Connects to user databases (PostgreSQL/MySQL/SQLite) via SQLAlchemy Inspector,
extracts table metadata and caches it in Redis.
"""
import json
from typing import Any
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.db.redis import redis_get, redis_set, redis_lrange, redis_lpush, redis_delete

logger = get_logger(__name__)

# Cache key templates
_SCHEMA_KEY = "schema:{session_id}:{table_name}"
_INDEX_KEY = "schema:{session_id}:__index__"


def _sync_introspect(connection_string: str) -> dict[str, Any]:
    """Synchronous introspection (runs in executor)."""
    engine = create_engine(
        connection_string,
        connect_args={"connect_timeout": settings.CONNECTION_TIMEOUT},
        pool_pre_ping=True,
    )

    inspector = inspect(engine)
    tables: dict[str, Any] = {}

    with engine.connect() as conn:
        for table_name in inspector.get_table_names():
            columns = []
            for col in inspector.get_columns(table_name):
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "primary_key": col.get("primary_key", False),
                    "default": str(col.get("default")) if col.get("default") is not None else None,
                })

            pk_cols = inspector.get_pk_constraint(table_name).get("constrained_columns", [])

            fks = []
            for fk in inspector.get_foreign_keys(table_name):
                fks.append({
                    "constrained_columns": fk.get("constrained_columns"),
                    "referred_table": fk.get("referred_table"),
                    "referred_columns": fk.get("referred_columns"),
                })

            indexes = []
            for idx in inspector.get_indexes(table_name):
                indexes.append({
                    "name": idx.get("name"),
                    "columns": idx.get("column_names", []),
                    "unique": idx.get("unique", False),
                })

            # Estimate row count from pg_class for PostgreSQL, otherwise COUNT(*)
            row_count_estimate: int | None = None
            try:
                if connection_string.startswith(("postgresql", "postgres")):
                    result = conn.execute(
                        text(
                            "SELECT reltuples::BIGINT FROM pg_class WHERE relname = :t"
                        ),
                        {"t": table_name},
                    ).scalar()
                    row_count_estimate = int(result or 0)
                else:
                    result = conn.execute(
                        text(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608
                    ).scalar()
                    row_count_estimate = int(result or 0)
            except Exception:
                pass

            tables[table_name] = {
                "table_name": table_name,
                "columns": columns,
                "primary_key_columns": pk_cols,
                "foreign_keys": fks,
                "indexes": indexes,
                "row_count_estimate": row_count_estimate,
            }

    engine.dispose()
    return tables


async def introspect_and_cache(
    session_id: str,
    connection_string: str,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Return cached schema or introspect and cache it.
    Always uses sync SQLAlchemy Inspector inside an asyncio executor.
    """
    import asyncio

    index_key = _INDEX_KEY.format(session_id=session_id)

    if not force_refresh:
        cached_index = await redis_get(index_key)
        if cached_index:
            schema: dict[str, Any] = {}
            for table_name in cached_index:
                key = _SCHEMA_KEY.format(session_id=session_id, table_name=table_name)
                table_data = await redis_get(key)
                if table_data:
                    schema[table_name] = table_data
            if schema:
                logger.info("schema.cache_hit", session_id=session_id, tables=len(schema))
                return schema

    loop = asyncio.get_event_loop()
    tables = await loop.run_in_executor(None, _sync_introspect, connection_string)

    # Cache each table independently
    for table_name, table_data in tables.items():
        key = _SCHEMA_KEY.format(session_id=session_id, table_name=table_name)
        await redis_set(key, table_data, ttl=settings.SCHEMA_CACHE_TTL)

    await redis_set(index_key, list(tables.keys()), ttl=settings.SCHEMA_CACHE_TTL)
    logger.info("schema.introspected", session_id=session_id, tables=len(tables))
    return tables


async def get_cached_schema(session_id: str) -> dict[str, Any] | None:
    index_key = _INDEX_KEY.format(session_id=session_id)
    cached_index = await redis_get(index_key)
    if not cached_index:
        return None

    schema: dict[str, Any] = {}
    for table_name in cached_index:
        key = _SCHEMA_KEY.format(session_id=session_id, table_name=table_name)
        table_data = await redis_get(key)
        if table_data:
            schema[table_name] = table_data
    return schema or None


def build_rag_schema_context(schema: dict[str, Any], question: str) -> str:
    """Select relevant tables via keyword matching and format as a RAG context string."""
    q_lower = question.lower()
    relevant: list[str] = []

    for table_name, table_data in schema.items():
        score = 0
        if table_name.lower() in q_lower:
            score += 10
        for col in table_data.get("columns", []):
            if col["name"].lower() in q_lower:
                score += 2
        if score > 0:
            relevant.append((score, table_name))

    # Fallback: use all tables if no keyword match
    if not relevant:
        relevant = [(0, t) for t in schema]

    relevant.sort(key=lambda x: -x[0])
    selected = [t for _, t in relevant[:8]]  # cap at 8 tables

    lines: list[str] = ["DATABASE SCHEMA:"]
    for table_name in selected:
        td = schema[table_name]
        lines.append(f"\nTable: {table_name} (~{td.get('row_count_estimate', '?')} rows)")
        lines.append("Columns:")
        for col in td["columns"]:
            pk = " [PK]" if col.get("primary_key") else ""
            nullable = "" if col.get("nullable", True) else " NOT NULL"
            lines.append(f"  - {col['name']}: {col['type']}{pk}{nullable}")
        if td.get("foreign_keys"):
            for fk in td["foreign_keys"]:
                lines.append(
                    f"  FK: {fk['constrained_columns']} → {fk['referred_table']}.{fk['referred_columns']}"
                )

    return "\n".join(lines)
