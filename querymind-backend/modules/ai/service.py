"""
modules/ai/service.py
Public interface of AIModule.

Full pipeline: cache check → schema RAG → Claude generation → Celery dispatch.
"""
from __future__ import annotations

import json
import logging

from core.config import get_settings
from core.redis_client import cache_get
from modules.ai.generator import generate_sql, make_cache_key
from modules.schema.service import get_relevant_schema

logger = logging.getLogger(__name__)


async def generate(
    session_id: str,
    question: str,
) -> dict:
    """
    Full pipeline for REST endpoint.

    1. Check query cache: query_cache:{make_cache_key(session_id, question)}
       Cache hit → dispatch log_usage Celery task → return cached result immediately.

    2. Cache miss:
       a. Call schema_service.get_relevant_schema(session_id, question)
       b. Call generate_sql(question, schema)
       c. Dispatch cache_query_result Celery task (fire-and-forget)
       d. Dispatch log_usage Celery task (fire-and-forget)
       e. Return result

    Result shape:
    {
      sql, rationale, explanation, tables_used,
      tokens_used, latency_ms, cache_hit, rag_context, validation
    }
    """
    # Import Celery tasks here to avoid circular imports at module load time
    from workers.tasks import cache_query_result, log_usage

    import time
    start = time.monotonic()

    cache_key = make_cache_key(session_id, question)
    cache_entry = await cache_get(f"query_cache:{cache_key}")

    if cache_entry is not None:
        logger.info(
            "AI cache hit: session=%s key=%s", session_id, cache_key[:16]
        )
        try:
            result = json.loads(cache_entry)
        except json.JSONDecodeError:
            logger.warning("Corrupt query cache entry for key=%s — regenerating", cache_key)
            result = None

        if result is not None:
            result["cache_hit"] = True
            latency_ms = int((time.monotonic() - start) * 1000)
            log_usage.delay(
                session_id=session_id,
                question=question,
                tokens_used=result.get("tokens_used", 0),
                latency_ms=latency_ms,
                cache_hit=True,
            )
            return result

    # Cache miss — full pipeline
    logger.info("AI cache miss: session=%s — running RAG + Claude", session_id)

    schema, rag_context = await get_relevant_schema(session_id, question)

    result = await generate_sql(question, schema)
    result["cache_hit"] = False
    result["rag_context"] = rag_context

    # Fire-and-forget Celery tasks
    settings = get_settings()
    cache_query_result.delay(
        cache_key=cache_key,
        result_json=json.dumps(result),
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    log_usage.delay(
        session_id=session_id,
        question=question,
        tokens_used=result.get("tokens_used", 0),
        latency_ms=latency_ms,
        cache_hit=False,
    )

    return result
