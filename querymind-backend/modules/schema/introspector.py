"""
modules/schema/introspector.py
PostgreSQL schema introspection using SQLAlchemy Inspector.
All functions are synchronous — called via run_in_executor from service.py.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Engine, Inspector, inspect, text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type normalisation
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[str, str] = {
    "VARCHAR": "text",
    "CHARACTER VARYING": "text",
    "TEXT": "text",
    "CHAR": "text",
    "CHARACTER": "text",
    "INTEGER": "integer",
    "INT": "integer",
    "INT4": "integer",
    "BIGINT": "bigint",
    "INT8": "bigint",
    "SMALLINT": "smallint",
    "INT2": "smallint",
    "NUMERIC": "numeric",
    "DECIMAL": "numeric",
    "FLOAT": "float",
    "FLOAT4": "float",
    "REAL": "float",
    "DOUBLE PRECISION": "float",
    "FLOAT8": "float",
    "BOOLEAN": "boolean",
    "BOOL": "boolean",
    "DATE": "date",
    "TIMESTAMP": "timestamp",
    "TIMESTAMP WITHOUT TIME ZONE": "timestamp",
    "TIMESTAMP WITH TIME ZONE": "timestamptz",
    "TIMESTAMPTZ": "timestamptz",
    "UUID": "uuid",
    "JSONB": "jsonb",
    "JSON": "json",
    "ARRAY": "array",
}


def _normalise_type(raw: str) -> str:
    upper = raw.upper().split("(")[0].strip()
    return _TYPE_MAP.get(upper, raw.lower())


# ---------------------------------------------------------------------------
# Row count via pg_class.reltuples (never COUNT(*))
# ---------------------------------------------------------------------------

def _get_row_count_estimate(engine: Engine, table_name: str, schema: str = "public") -> int:
    sql = text(
        "SELECT reltuples::bigint AS estimate "
        "FROM pg_class "
        "JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace "
        "WHERE pg_namespace.nspname = :schema "
        "AND pg_class.relname = :table"
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"schema": schema, "table": table_name}).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


# ---------------------------------------------------------------------------
# Table comment via obj_description()
# ---------------------------------------------------------------------------

def _get_table_comment(engine: Engine, table_name: str, schema: str = "public") -> str | None:
    sql = text(
        "SELECT obj_description(c.oid) "
        "FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = :schema AND c.relname = :table AND c.relkind = 'r'"
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"schema": schema, "table": table_name}).fetchone()
    return row[0] if row and row[0] else None


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def introspect_table(engine: Engine, table_name: str, schema: str = "public") -> dict:
    """
    Reflect one table and return a comprehensive dict.

    Returns:
      table_name, schema, columns, primary_keys, foreign_keys,
      indexes, row_count_estimate, comment
    """
    inspector: Inspector = inspect(engine)

    # ── Columns ──────────────────────────────────────────────────────────
    raw_columns = inspector.get_columns(table_name, schema=schema)
    raw_pks = inspector.get_pk_constraint(table_name, schema=schema)
    raw_fks = inspector.get_foreign_keys(table_name, schema=schema)
    raw_indexes = inspector.get_indexes(table_name, schema=schema)

    pk_set: set[str] = set(raw_pks.get("constrained_columns", []))

    # Build FK lookup: column_name → {references_table, references_column}
    fk_by_col: dict[str, dict] = {}
    for fk in raw_fks:
        for local_col, ref_col in zip(
            fk.get("constrained_columns", []),
            fk.get("referred_columns", []),
        ):
            fk_by_col[local_col] = {
                "references_table": fk.get("referred_table"),
                "references_column": ref_col,
            }

    columns: list[dict] = []
    for col in raw_columns:
        col_name = col["name"]
        raw_type = str(col.get("type", "unknown"))
        columns.append(
            {
                "name": col_name,
                "type": _normalise_type(raw_type),
                "nullable": col.get("nullable", True),
                "primary_key": col_name in pk_set,
                "default": str(col["default"]) if col.get("default") is not None else None,
                "comment": col.get("comment"),
                "foreign_key": fk_by_col.get(col_name),
            }
        )

    # ── Foreign keys (table level) ────────────────────────────────────────
    foreign_keys: list[dict] = [
        {
            "constrained_columns": fk.get("constrained_columns", []),
            "referred_table": fk.get("referred_table"),
            "referred_columns": fk.get("referred_columns", []),
        }
        for fk in raw_fks
    ]

    # ── Indexes ───────────────────────────────────────────────────────────
    indexes: list[dict] = [
        {
            "name": idx.get("name"),
            "columns": idx.get("column_names", []),
            "unique": idx.get("unique", False),
        }
        for idx in raw_indexes
    ]

    # ── Estimates + comment ───────────────────────────────────────────────
    try:
        row_count_estimate = _get_row_count_estimate(engine, table_name, schema)
    except Exception as exc:  # noqa: BLE001
        logger.warning("row_count_estimate failed for %s: %s", table_name, exc)
        row_count_estimate = 0

    try:
        comment = _get_table_comment(engine, table_name, schema)
    except Exception as exc:  # noqa: BLE001
        logger.warning("table_comment failed for %s: %s", table_name, exc)
        comment = None

    return {
        "table_name": table_name,
        "schema": schema,
        "columns": columns,
        "primary_keys": list(pk_set),
        "foreign_keys": foreign_keys,
        "indexes": indexes,
        "row_count_estimate": row_count_estimate,
        "comment": comment,
    }


def get_all_table_names(engine: Engine) -> list[str]:
    """Return list of all table names in the public schema."""
    inspector: Inspector = inspect(engine)
    return inspector.get_table_names(schema="public")


def get_table_list_with_estimates(engine: Engine) -> list[dict]:
    """
    Return lightweight list for RAG relevance scoring.
    Each entry: { table_name: str, row_count_estimate: int }
    Does NOT introspect columns — fast path only.
    """
    sql = text(
        "SELECT c.relname AS table_name, c.reltuples::bigint AS row_count_estimate "
        "FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' "
        "ORDER BY c.relname"
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()

    return [
        {"table_name": row[0], "row_count_estimate": max(int(row[1]), 0)}
        for row in rows
    ]
