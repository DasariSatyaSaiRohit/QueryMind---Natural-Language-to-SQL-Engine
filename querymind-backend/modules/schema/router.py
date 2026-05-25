"""
modules/schema/router.py
Schema API endpoints.

GET  /api/schema/{session_id}         → get_full_schema
POST /api/schema/{session_id}/refresh → refresh_schema

Both require JWT auth + session ownership verification.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from core.auth import AuthenticatedUser
from core.auth_middleware import verify_session_ownership
from core.rate_limit import limiter
from modules.schema.service import get_full_schema, refresh_schema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schema", tags=["schema"])


@router.get("/{session_id}")
@limiter.limit("60/minute")
async def get_schema(
    request: Request,
    session_id: str,
    user: AuthenticatedUser = Depends(verify_session_ownership),
) -> dict:
    """
    Return the full introspected schema for the session's database.
    Cache-first, falls back to live introspection.
    """
    schema = await get_full_schema(session_id)
    return {
        "session_id": session_id,
        "tables": schema,
        "table_count": len(schema),
    }


@router.post("/{session_id}/refresh")
@limiter.limit("60/minute")
async def refresh_schema_endpoint(
    request: Request,
    session_id: str,
    user: AuthenticatedUser = Depends(verify_session_ownership),
) -> dict:
    """
    Invalidate the schema cache and re-introspect all tables.
    Returns the freshly introspected schema.
    """
    schema = await refresh_schema(session_id)
    return {
        "session_id": session_id,
        "tables": schema,
        "table_count": len(schema),
        "refreshed": True,
    }
