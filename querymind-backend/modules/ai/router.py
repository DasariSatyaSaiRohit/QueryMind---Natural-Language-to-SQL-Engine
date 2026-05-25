"""
modules/ai/router.py
AI endpoints:
  POST /api/query/generate  — REST SQL generation
  WS   /ws/query/{session_id} — streaming via WebSocket
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core.auth import AuthenticatedUser, require_auth
from core.auth_middleware import verify_session_ownership
from core.config import get_settings
from core.context import set_session_id
from core.exceptions import SQLValidationError
from core.rate_limit import limiter
from modules.ai.generator import make_cache_key, stream_sql_tokens
from modules.ai.service import generate
from modules.schema.service import get_relevant_schema

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    question: str
    session_id: str


# ---------------------------------------------------------------------------
# REST endpoint
# ---------------------------------------------------------------------------

@router.post("/api/query/generate")
@limiter.limit("10/minute")
async def generate_sql_endpoint(
    request: Request,
    body: GenerateRequest,
    user: AuthenticatedUser = Depends(verify_session_ownership),
) -> dict:
    """
    Generate SQL from a natural language question.
    Uses schema RAG + Claude, with Redis query cache.
    """
    result = await generate(
        session_id=body.session_id,
        question=body.question,
    )
    return result


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/query/{session_id}")
async def query_websocket(
    websocket: WebSocket,
    session_id: str,
) -> None:
    """
    Streaming SQL generation over WebSocket.

    Auth: verify JWT from ?token= query param before accepting.

    Protocol:
      Client sends: { "question": "..." }
      Server sends:
        { "type": "rag_context", ... }
        { "type": "token", "content": "..." }  (per chunk)
        { "type": "complete", ...result_dict }
        { "type": "error", "reason": "..." }  (on failure)

    Timeout: WS_GENERATION_TIMEOUT seconds.
    """
    settings = get_settings()

    # ── JWT auth from query param ─────────────────────────────────────────
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="missing_token")
        return

    from core.auth import _decode_token
    from fastapi import HTTPException

    try:
        payload = _decode_token(token)
    except HTTPException as exc:
        error_type = exc.detail.get("error_type", "invalid_token") if isinstance(exc.detail, dict) else "invalid_token"
        await websocket.close(code=4401, reason=error_type)
        return

    jwt_session_id: str | None = payload.get("session_id")
    user_id: str | None = payload.get("sub")

    # Session ownership check
    if jwt_session_id != session_id:
        await websocket.close(code=4403, reason="session_ownership_violation")
        return

    set_session_id(session_id)

    await websocket.accept()
    logger.info("WS connected: user=%s session=%s", user_id, session_id)

    # ── Receive question ──────────────────────────────────────────────────
    try:
        raw_message = await websocket.receive_text()
        message = json.loads(raw_message)
        question: str = message.get("question", "").strip()
    except (WebSocketDisconnect, json.JSONDecodeError, Exception) as exc:
        logger.warning("WS receive error for session=%s: %s", session_id, exc)
        await _ws_safe_send(websocket, {"type": "error", "reason": "invalid_message"})
        await websocket.close()
        return

    if not question:
        await _ws_safe_send(websocket, {"type": "error", "reason": "empty_question"})
        await websocket.close()
        return

    # ── RAG + stream ──────────────────────────────────────────────────────
    try:
        schema, rag_context = await get_relevant_schema(session_id, question)
    except Exception as exc:  # noqa: BLE001
        logger.error("WS schema error session=%s: %s", session_id, exc)
        await _ws_safe_send(websocket, {"type": "error", "reason": str(exc)})
        await websocket.close()
        return

    # Send RAG context immediately
    rag_sent = await _ws_safe_send(
        websocket,
        {"type": "rag_context", **rag_context},
    )
    if not rag_sent:
        return  # Client disconnected

    # ── Streaming callbacks ───────────────────────────────────────────────
    async def on_token(chunk: str) -> None:
        sent = await _ws_safe_send(websocket, {"type": "token", "content": chunk})
        if not sent:
            raise WebSocketDisconnect(code=1001)

    async def on_complete(result: dict) -> None:
        # Fire Celery tasks before closing
        from workers.tasks import cache_query_result, log_usage
        cache_key = make_cache_key(session_id, question)
        import json as _json
        cache_query_result.delay(cache_key=cache_key, result_json=_json.dumps(result))
        log_usage.delay(
            session_id=session_id,
            question=question,
            tokens_used=result.get("tokens_used", 0),
            latency_ms=result.get("latency_ms", 0),
            cache_hit=False,
        )
        await _ws_safe_send(websocket, {"type": "complete", **result})

    async def on_error(reason: str) -> None:
        await _ws_safe_send(websocket, {"type": "error", "reason": reason})

    # ── Run with timeout ──────────────────────────────────────────────────
    try:
        await asyncio.wait_for(
            stream_sql_tokens(
                question=question,
                schema=schema,
                on_token=on_token,
                on_complete=on_complete,
                on_error=on_error,
            ),
            timeout=settings.WS_GENERATION_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "WS generation timeout (%ds) for session=%s",
            settings.WS_GENERATION_TIMEOUT,
            session_id,
        )
        await _ws_safe_send(
            websocket,
            {"type": "error", "reason": "generation_timeout"},
        )
    except WebSocketDisconnect:
        logger.warning("WS client disconnected during generation: session=%s", session_id)
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("WS unhandled error session=%s: %s", session_id, exc)
        await _ws_safe_send(websocket, {"type": "error", "reason": "internal_error"})

    try:
        await websocket.close()
    except Exception:  # noqa: BLE001
        pass

    logger.info("WS closed: session=%s", session_id)


async def _ws_safe_send(websocket: WebSocket, data: dict) -> bool:
    """
    Send JSON data over WebSocket.
    Returns False if the client has disconnected; True on success.
    """
    try:
        await websocket.send_json(data)
        return True
    except WebSocketDisconnect:
        logger.warning("WS send: client already disconnected")
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("WS send error: %s", exc)
        return False
