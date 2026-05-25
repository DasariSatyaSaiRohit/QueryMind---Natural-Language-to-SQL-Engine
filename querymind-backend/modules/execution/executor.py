"""
modules/execution/executor.py
Core SQL execution. Synchronous — called via run_in_executor from service.py.

Safety layers applied in execute_sync (defense-in-depth):
  1. Re-run check_operation_safety
  2. SET TRANSACTION READ ONLY
  3. SET LOCAL statement_timeout
"""
from __future__ import annotations

import logging
import time
from math import ceil

import sqlalchemy.exc
from sqlalchemy import Engine, text

from core.config import get_settings
from core.exceptions import SQLExecutionError, SQLValidationError
from modules.execution.safety import check_operation_safety
from modules.execution.serializer import serialise_rows

logger = logging.getLogger(__name__)


def execute_sync(
    engine: Engine,
    sql: str,
    page: int,
    page_size: int,
) -> dict:
    """
    Execute validated SQL safely inside a read-only transaction.

    Safety layers (in order):
      1. Re-run check_operation_safety(sql) — defense-in-depth.
      2. SET TRANSACTION READ ONLY on the open connection.
      3. SET LOCAL statement_timeout = STATEMENT_TIMEOUT_MS.
      4. Execute SQL, fetch MAX_RESULT_ROWS + 1 rows (truncation sentinel).
      5. Paginate in-memory result.
      6. Serialise to JSON-safe types.
      7. Return ExecutionResult dict.

    Raises:
      SQLValidationError  — forbidden keyword detected (Pass 1).
      SQLExecutionError   — DB operational / programming error.
    """
    settings = get_settings()

    # ── Layer 1: re-validate ──────────────────────────────────────────────
    ok, reason = check_operation_safety(sql)
    if not ok:
        raise SQLValidationError(reason or "Forbidden SQL operation.")

    # ── Clamp pagination params ───────────────────────────────────────────
    page = max(page, 1)
    page_size = min(max(page_size, 1), 500)

    start = time.monotonic()

    try:
        with engine.connect() as conn:
            # ── Layer 2 & 3: read-only + timeout ─────────────────────────
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(
                text(f"SET LOCAL statement_timeout = '{settings.STATEMENT_TIMEOUT_MS}'")
            )

            # ── Execute ───────────────────────────────────────────────────
            result_proxy = conn.execute(text(sql))
            column_names: list[str] = list(result_proxy.keys())

            # Fetch one extra row to detect truncation without a full scan
            max_fetch = settings.MAX_RESULT_ROWS + 1
            raw_rows = result_proxy.fetchmany(max_fetch)

    except sqlalchemy.exc.OperationalError as exc:
        logger.error("SQL execution OperationalError: %s", exc)
        raise SQLExecutionError(
            f"Database operational error: {exc.orig or exc}"
        ) from exc
    except sqlalchemy.exc.ProgrammingError as exc:
        logger.error("SQL execution ProgrammingError: %s", exc)
        raise SQLExecutionError(
            f"SQL programming error: {exc.orig or exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("SQL execution unexpected error: %s", exc)
        raise SQLExecutionError(f"Unexpected execution error: {exc}") from exc

    execution_time_ms = int((time.monotonic() - start) * 1000)

    # ── Truncation detection ──────────────────────────────────────────────
    truncated = len(raw_rows) > settings.MAX_RESULT_ROWS
    if truncated:
        raw_rows = raw_rows[: settings.MAX_RESULT_ROWS]
        truncation_warning = (
            f"Result set exceeded {settings.MAX_RESULT_ROWS} rows and was truncated. "
            "Refine your query with a more specific WHERE clause or explicit LIMIT."
        )
    else:
        truncation_warning = None

    # ── Pagination ────────────────────────────────────────────────────────
    total_rows = len(raw_rows)
    total_pages = max(ceil(total_rows / page_size), 1) if total_rows > 0 else 1
    offset = (page - 1) * page_size
    page_rows = raw_rows[offset: offset + page_size]

    # ── Serialise ─────────────────────────────────────────────────────────
    columns, rows = serialise_rows(list(page_rows), column_names)

    logger.info(
        "execute_sync: rows_total=%d page=%d/%d time_ms=%d truncated=%s",
        total_rows,
        page,
        total_pages,
        execution_time_ms,
        truncated,
    )

    return {
        "sql_executed": sql,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "execution_time_ms": execution_time_ms,
        "truncated": truncated,
        "truncation_warning": truncation_warning,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }
