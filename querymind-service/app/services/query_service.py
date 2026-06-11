"""
SQL validation and execution service.

Validates SELECT-only + injection patterns, then executes against user DB with
pagination, returning ONLY metadata (no result rows stored in DB).
"""
import re
import time
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Forbidden SQL statement types
_FORBIDDEN_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bDROP\b",
        r"\bTRUNCATE\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bEXEC(?:UTE)?\b",
    )
]

# SQL injection patterns
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"';\s*DROP",
        r"UNION\s+SELECT",
        r"--\s",
        r"/\*.*?\*/",
        r"\bOR\b\s+['\d]+=\s*['\d]+",
        r"\bxp_\w+",
    )
]


def validate_sql(sql: str, schema: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a SQL query:
      1. Must be SELECT-only
      2. Must not match injection patterns
      3. Referenced tables must exist in schema

    Returns a validation_info dict.
    """
    failed_checks: list[str] = []
    invalid_references: list[str] = []
    injection_detected = False

    # 1. SELECT-only check
    stripped = sql.strip().lstrip("(")
    if not re.match(r"^SELECT\b", stripped, re.IGNORECASE):
        failed_checks.append("must_be_select")

    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(sql):
            failed_checks.append(f"forbidden_statement:{pattern.pattern}")

    # 2. Injection detection
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(sql):
            injection_detected = True
            failed_checks.append(f"injection_pattern:{pattern.pattern}")

    # 3. Table existence check (basic heuristic)
    known_tables = set(schema.keys())
    # Extract table names from FROM and JOIN clauses
    from_matches = re.findall(
        r"\bFROM\s+([a-zA-Z_]\w*)|\bJOIN\s+([a-zA-Z_]\w*)", sql, re.IGNORECASE
    )
    referenced = {m[0] or m[1] for m in from_matches}
    for table in referenced:
        if table.lower() not in {t.lower() for t in known_tables}:
            invalid_references.append(table)
            failed_checks.append(f"unknown_table:{table}")

    passed = not failed_checks
    reason = "OK" if passed else "; ".join(failed_checks)

    return {
        "passed": passed,
        "failed_checks": failed_checks,
        "reason": reason,
        "invalid_references": invalid_references,
        "injection_detected": injection_detected,
    }


def _sync_execute(
    connection_string: str, sql: str, page: int, page_size: int
) -> dict[str, Any]:
    """Synchronous query execution (runs in executor thread)."""
    engine = create_engine(
        connection_string,
        connect_args={"connect_timeout": settings.CONNECTION_TIMEOUT},
        pool_pre_ping=True,
    )

    # Add pagination to the query
    paginated_sql = f"SELECT * FROM ({sql}) _q LIMIT {page_size} OFFSET {(page - 1) * page_size}"

    start = time.monotonic()
    with engine.connect() as conn:
        # Set statement timeout for PostgreSQL
        try:
            conn.execute(text(f"SET statement_timeout = {settings.QUERY_TIMEOUT * 1000}"))
        except Exception:
            pass  # Not PostgreSQL

        result = conn.execute(text(paginated_sql))
        columns = list(result.keys())
        rows = result.fetchall()

    elapsed_ms = int((time.monotonic() - start) * 1000)
    engine.dispose()

    row_count = len(rows)
    truncated = row_count >= settings.MAX_RESULT_ROWS
    truncation_warning = (
        f"Results truncated at {settings.MAX_RESULT_ROWS} rows." if truncated else None
    )

    return {
        "columns": columns,
        "rows": [list(r) for r in rows],
        "row_count": row_count,
        "execution_time_ms": elapsed_ms,
        "pagination": {
            "page": page,
            "page_size": page_size,
        },
        "truncated": truncated,
        "truncation_warning": truncation_warning,
    }


async def execute_query(
    connection_string: str,
    sql: str,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Async wrapper for synchronous query execution."""
    import asyncio

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _sync_execute, connection_string, sql, page, page_size
    )
    return result
