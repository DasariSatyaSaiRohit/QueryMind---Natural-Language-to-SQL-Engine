"""
modules/execution/router.py
Execution API endpoints.

POST /api/query/execute         — execute provided SQL
GET  /api/query/history/{id}   — fetch session query history
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from core.auth import AuthenticatedUser
from core.auth_middleware import verify_session_ownership
from core.rate_limit import limiter
from modules.execution.service import execute_query, get_history

logger = logging.getLogger(__name__)

router = APIRouter(tags=["execution"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ExecuteRequest(BaseModel):
    sql: str
    session_id: str
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/query/execute")
@limiter.limit("60/minute")
async def execute_sql_endpoint(
    request: Request,
    body: ExecuteRequest,
    user: AuthenticatedUser = Depends(verify_session_ownership),
) -> dict:
    """
    Execute a pre-validated SQL query against the session's database.
    Returns paginated, serialised results.
    """
    result = await execute_query(
        session_id=body.session_id,
        sql=body.sql,
        page=body.page,
        page_size=body.page_size,
    )
    return result


@router.get("/api/query/history/{session_id}")
@limiter.limit("60/minute")
async def get_query_history(
    request: Request,
    session_id: str,
    user: AuthenticatedUser = Depends(verify_session_ownership),
) -> dict:
    """
    Return the 20 most recent execution records for the session.
    """
    history = await get_history(session_id)
    return {
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }
