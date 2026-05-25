"""
modules/ai/safety.py
Three-pass SQL validation pipeline.
All functions are synchronous.

Pass 1: Operation safety (forbidden keywords)
Pass 2: Schema cross-reference (sqlglot parse)
Pass 3: Injection guard (pattern matching on question)
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pass 1 — Operation safety
# ---------------------------------------------------------------------------

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|MERGE"
    r"|GRANT|REVOKE|EXEC|EXECUTE|CALL|COPY|VACUUM|ANALYZE|REINDEX"
    r"|LOCK|CLUSTER|COMMENT|SECURITY|OWNER|RENAME)\b",
    re.IGNORECASE,
)


def check_operation_safety(sql: str) -> tuple[bool, str | None]:
    """
    Scan SQL for forbidden write/DDL keywords.
    Return (True, None) if safe.
    Return (False, reason) if blocked.
    """
    match = FORBIDDEN.search(sql)
    if match:
        keyword = match.group(1).upper()
        reason = f"Forbidden SQL operation detected: '{keyword}'. Only SELECT statements are permitted."
        logger.warning(
            "Pass 1 BLOCKED keyword=%s sql_preview=%r", keyword, sql[:200]
        )
        return False, reason
    return True, None


# ---------------------------------------------------------------------------
# Pass 2 — Schema cross-reference
# ---------------------------------------------------------------------------

def validate_against_schema(
    sql: str,
    schema: dict,
) -> tuple[bool, str | None, list[str]]:
    """
    Parse SQL using sqlglot (postgres dialect).
    Extract all table and column references.
    Cross-reference against schema dict from SchemaModule.

    Returns: (passed, reason, invalid_references)
    invalid_references: list of "table:name" or "column:table.name" strings

    If sqlglot is not installed or parse fails: return (True, None, []).
    Never block a query due to a parser error — only block on confirmed mismatches.
    """
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError:
        logger.warning("Pass 2: sqlglot not installed — skipping schema cross-reference")
        return True, None, []

    try:
        parsed = sqlglot.parse_one(sql, dialect="postgres")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pass 2: sqlglot parse error — falling through: %s", exc)
        return True, None, []

    # Known table names (lowercase for case-insensitive comparison)
    known_tables: set[str] = {name.lower() for name in schema.keys()}

    # Collect all referenced table names from the AST
    referenced_tables: set[str] = set()
    for table_node in parsed.find_all(exp.Table):
        if table_node.name:
            referenced_tables.add(table_node.name.lower())

    invalid_references: list[str] = []

    # Check tables
    for ref_table in referenced_tables:
        if ref_table not in known_tables:
            invalid_references.append(f"table:{ref_table}")

    # Check columns (only for tables we know about)
    for col_node in parsed.find_all(exp.Column):
        col_name = col_node.name
        if col_node.table:
            tbl = col_node.table.lower()
            if tbl in known_tables and tbl in schema:
                known_col_names = {
                    c["name"].lower() for c in schema[tbl].get("columns", [])
                }
                if col_name.lower() not in known_col_names:
                    invalid_references.append(f"column:{tbl}.{col_name}")

    if invalid_references:
        reason = (
            f"SQL references {len(invalid_references)} unknown schema element(s): "
            + ", ".join(invalid_references[:5])
        )
        logger.warning(
            "Pass 2 BLOCKED invalid_refs=%s", invalid_references
        )
        return False, reason, invalid_references

    return True, None, []


# ---------------------------------------------------------------------------
# Pass 3 — Injection guard
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r";\s*(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE)", re.IGNORECASE),
    re.compile(r"UNION\s+SELECT", re.IGNORECASE),
    re.compile(r"--\s*$", re.MULTILINE),
    re.compile(r"/\*.*?\*/", re.DOTALL),
    re.compile(r"'\s*OR\s*'?\d*\s*'?\s*=\s*'?\d", re.IGNORECASE),
    re.compile(r"xp_cmdshell", re.IGNORECASE),
    re.compile(r"EXEC\s*\(", re.IGNORECASE),
    re.compile(r"WAITFOR\s+DELAY", re.IGNORECASE),
    re.compile(r"BENCHMARK\s*\(", re.IGNORECASE),
    re.compile(r"SLEEP\s*\(", re.IGNORECASE),
]

_PATTERN_NAMES = [
    "stacked_statements",
    "union_select",
    "sql_comment_eol",
    "block_comment",
    "or_equals_injection",
    "xp_cmdshell",
    "exec_injection",
    "waitfor_delay",
    "benchmark_injection",
    "sleep_injection",
]


def check_injection_patterns(question: str) -> tuple[bool, str | None]:
    """
    Scan the original user question (not the SQL) for injection patterns.
    Return (True, None) if clean.
    Return (False, reason) if suspicious.
    """
    for pattern, name in zip(INJECTION_PATTERNS, _PATTERN_NAMES):
        if pattern.search(question):
            reason = f"Potential SQL injection pattern detected in question: '{name}'."
            logger.warning(
                "Pass 3 BLOCKED pattern=%s question_preview=%r",
                name,
                question[:200],
            )
            return False, reason
    return True, None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_validation(
    sql: str,
    question: str,
    schema: dict,
) -> dict:
    """
    Run all three passes in order. Fail-fast.
    Return validation result dict:
    {
      passed: bool,
      failed_pass: int | None,
      reason: str | None,
      invalid_references: list[str]
    }
    """
    # Pass 3 runs first on the question (fastest, no parse needed)
    ok, reason = check_injection_patterns(question)
    if not ok:
        return {
            "passed": False,
            "failed_pass": 3,
            "reason": reason,
            "invalid_references": [],
        }

    # Pass 1: forbidden operations
    ok, reason = check_operation_safety(sql)
    if not ok:
        return {
            "passed": False,
            "failed_pass": 1,
            "reason": reason,
            "invalid_references": [],
        }

    # Pass 2: schema cross-reference
    ok, reason, invalid_refs = validate_against_schema(sql, schema)
    if not ok:
        return {
            "passed": False,
            "failed_pass": 2,
            "reason": reason,
            "invalid_references": invalid_refs,
        }

    return {
        "passed": True,
        "failed_pass": None,
        "reason": None,
        "invalid_references": [],
    }
