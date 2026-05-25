"""
modules/query/service.py
Full NL → SQL → execute pipeline.
The primary gateway entry point: one call returns generated SQL + query results.
"""
from __future__ import annotations

import logging

from core.exceptions import SQLExecutionError, SQLValidationError
from modules.ai.service import generate as ai_generate
from modules.execution.service import execute_query

logger = logging.getLogger(__name__)


async def ask(
    session_id: str,
    question: str,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    Full pipeline: NL → SQL → execute → return merged results.

    Steps:
      1. ai_generate(session_id, question)
         → { sql, rationale, explanation, tables_used,
              tokens_used, latency_ms, cache_hit, rag_context, validation }

      2. execute_query(session_id, sql, page, page_size)
         → ExecutionResult dict

      3. Merge and return a unified response dict.

    Error handling:
      SQLValidationError from step 1:
        Return structured error without attempting execution.
      SQLExecutionError from step 2:
        Return the generated SQL alongside the error so the user can see
        what was generated before the failure.
    """
    # ── Step 1: Generate SQL ──────────────────────────────────────────────
    try:
        generation = await ai_generate(session_id=session_id, question=question)
    except SQLValidationError as exc:
        logger.warning(
            "ask: SQL validation failed session=%s question=%r: %s",
            session_id,
            question[:80],
            exc,
        )
        return {
            "success": False,
            "error_type": "validation_failed",
            "message": str(exc),
            "sql_attempted": None,
            "question": question,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "ask: generation unexpected error session=%s: %s", session_id, exc
        )
        raise

    sql: str = generation["sql"]

    # ── Step 2: Execute ───────────────────────────────────────────────────
    try:
        execution = await execute_query(
            session_id=session_id,
            sql=sql,
            page=page,
            page_size=page_size,
        )
    except SQLExecutionError as exc:
        logger.warning(
            "ask: execution failed session=%s sql_preview=%r: %s",
            session_id,
            sql[:120],
            exc,
        )
        return {
            "success": False,
            "error_type": "execution_failed",
            "message": str(exc),
            "sql": sql,
            "rationale": generation.get("rationale", ""),
            "explanation": generation.get("explanation", ""),
            "tables_used": generation.get("tables_used", []),
            "cache_hit": generation.get("cache_hit", False),
            "rag_context": generation.get("rag_context"),
            "validation": generation.get("validation"),
            "question": question,
        }

    # ── Step 3: Merge ─────────────────────────────────────────────────────
    return {
        "success": True,
        "question": question,
        # Generation fields
        "sql": sql,
        "rationale": generation.get("rationale", ""),
        "explanation": generation.get("explanation", ""),
        "tables_used": generation.get("tables_used", []),
        "cache_hit": generation.get("cache_hit", False),
        "rag_context": generation.get("rag_context"),
        "validation": generation.get("validation"),
        "generation_time_ms": generation.get("latency_ms", 0),
        "tokens_used": generation.get("tokens_used", 0),
        # Execution fields
        "columns": execution["columns"],
        "rows": execution["rows"],
        "row_count": execution["row_count"],
        "execution_time_ms": execution["execution_time_ms"],
        "truncated": execution["truncated"],
        "truncation_warning": execution["truncation_warning"],
        "pagination": execution["pagination"],
    }
