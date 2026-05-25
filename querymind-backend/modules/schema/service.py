"""
modules/schema/service.py
Public interface of SchemaModule.
Called by AIModule and the API layer.

All SQLAlchemy calls run in thread pool executors — never block the event loop.
"""
from __future__ import annotations

import asyncio
import logging
from functools import partial

from core.config import get_settings
from modules.session.store import session_store
from modules.schema import cache as schema_cache
from modules.schema import introspector
from modules.schema.rag import select_relevant_tables

logger = logging.getLogger(__name__)


async def get_relevant_schema(
    session_id: str,
    question: str,
) -> tuple[dict, dict]:
    """
    Two-step RAG pipeline. Returns (schema_dict, rag_context_dict).

    Step 1 — Get table list (lightweight):
      a. Check Redis index via cache.get_index(session_id).
         If cached: use cached list with row_count 0 (counts not in index).
         If not cached: call introspector.get_table_list_with_estimates(engine)
                        via run_in_executor.

    Step 2 — Score and select.

    Step 3 — Fetch full schema for selected tables:
      a. Try cache.get_cached_tables(session_id, selected_tables).
      b. For any table missing from cache: introspect live via run_in_executor,
         then store in Redis (do not wait for warm_cache).
      c. Merge cached + live results.

    rag_context_dict: {
      total_tables, selected_tables, selection_scores,
      selection_method, tables_from_cache, tables_introspected_live
    }
    """
    settings = get_settings()
    loop = asyncio.get_event_loop()
    engine = session_store.get_engine(session_id)

    # ── Step 1: Get table list ────────────────────────────────────────────
    index = await schema_cache.get_index(session_id)

    if index is not None:
        table_list = [{"table_name": name, "row_count_estimate": 0} for name in index]
        logger.debug(
            "schema:table_list from cache, session=%s tables=%d",
            session_id,
            len(table_list),
        )
    else:
        table_list = await loop.run_in_executor(
            None,
            introspector.get_table_list_with_estimates,
            engine,
        )
        logger.debug(
            "schema:table_list from live introspection, session=%s tables=%d",
            session_id,
            len(table_list),
        )

    # ── Step 2: RAG scoring ───────────────────────────────────────────────
    max_tables = settings.MAX_RELEVANT_TABLES
    selected_tables, scores = select_relevant_tables(question, table_list, max_tables)

    # Determine selection method for context dict
    all_zero = all(s == 0.0 for s in scores.values())
    selection_method = "size_fallback" if all_zero else "keyword_match"

    # ── Step 3: Fetch full schema ─────────────────────────────────────────
    cached_results = await schema_cache.get_cached_tables(session_id, selected_tables)
    tables_from_cache = list(cached_results.keys())

    missing = [t for t in selected_tables if t not in cached_results]
    tables_introspected_live: list[str] = []
    live_results: dict[str, dict] = {}

    for table_name in missing:
        try:
            table_data = await loop.run_in_executor(
                None,
                partial(introspector.introspect_table, engine, table_name),
            )
            live_results[table_name] = table_data
            tables_introspected_live.append(table_name)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Live introspection failed for %s:%s — %s",
                session_id,
                table_name,
                exc,
            )

    # Store newly introspected tables in Redis
    if live_results:
        await schema_cache.store_schema_chunks(
            session_id,
            list(live_results.values()),
            ttl=settings.SCHEMA_CACHE_TTL,
        )

    # Merge
    schema_dict: dict[str, dict] = {**cached_results, **live_results}

    rag_context_dict: dict = {
        "total_tables": len(table_list),
        "selected_tables": selected_tables,
        "selection_scores": {t: round(scores.get(t, 0.0), 4) for t in selected_tables},
        "selection_method": selection_method,
        "tables_from_cache": tables_from_cache,
        "tables_introspected_live": tables_introspected_live,
    }

    return schema_dict, rag_context_dict


async def get_full_schema(session_id: str) -> dict:
    """
    Return full schema for all tables in the session's database.
    Used by GET /api/schema/{session_id}.
    Cache-first, fall back to live introspection.
    """
    loop = asyncio.get_event_loop()
    engine = session_store.get_engine(session_id)

    # Try cache first
    all_tables = await schema_cache.get_cached_tables(session_id, table_names=None)

    if all_tables:
        logger.debug(
            "get_full_schema: fully cached, session=%s tables=%d",
            session_id,
            len(all_tables),
        )
        return all_tables

    # Cache miss — live introspection
    logger.info(
        "get_full_schema: cache miss, introspecting live for session=%s",
        session_id,
    )
    table_names: list[str] = await loop.run_in_executor(
        None,
        introspector.get_all_table_names,
        engine,
    )

    settings = get_settings()
    result: dict[str, dict] = {}
    tables_to_cache: list[dict] = []

    for name in table_names:
        try:
            from functools import partial
            table_data = await loop.run_in_executor(
                None,
                partial(introspector.introspect_table, engine, name),
            )
            result[name] = table_data
            tables_to_cache.append(table_data)
        except Exception as exc:  # noqa: BLE001
            logger.error("Introspection failed for %s:%s — %s", session_id, name, exc)

    if tables_to_cache:
        await schema_cache.store_schema_chunks(
            session_id,
            tables_to_cache,
            ttl=settings.SCHEMA_CACHE_TTL,
        )

    return result


async def refresh_schema(session_id: str) -> dict:
    """
    Invalidate cache and re-introspect all tables.
    Used by POST /api/schema/{session_id}/refresh.
    Returns full schema dict.
    """
    logger.info("refresh_schema: invalidating cache for session=%s", session_id)
    await schema_cache.invalidate_session_cache(session_id)
    return await get_full_schema(session_id)
