"""
modules/execution/safety.py
Defense-in-depth duplicate of Pass 1 from modules/ai/safety.py.
ExecutionModule never trusts AIModule — it re-validates before touching the DB.
Do NOT import from modules.ai.safety — this copy is intentional.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

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
    Logs a warning with the first 200 chars of SQL on failure.
    """
    match = FORBIDDEN.search(sql)
    if match:
        keyword = match.group(1).upper()
        reason = (
            f"Forbidden SQL operation detected: '{keyword}'. "
            "Only SELECT statements are permitted."
        )
        logger.warning(
            "ExecutionModule safety BLOCKED keyword=%s sql_preview=%r",
            keyword,
            sql[:200],
        )
        return False, reason
    return True, None
