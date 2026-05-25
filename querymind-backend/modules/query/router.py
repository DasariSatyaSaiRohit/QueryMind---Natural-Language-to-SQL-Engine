"""
modules/query/router.py
Primary gateway endpoint — NL → SQL → execute in one HTTP call.

POST /api/query/ask
  Rate:  10/minute (same tier as generation — Claude is called)
  Auth:  require_auth + verify_session_ownership

Error responses:
  422 validation_failed  — SQL generated but failed validation
  422 execution_failed   — SQL valid but DB rejected it
  404 session_not_found  — session does not exist
  502 external_api_error — Claude API unreachable
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from core.auth import AuthenticatedUser
from core.auth_middleware import verify_session_ownership
from core.context import get_request_id
from core.exceptions import (
    ExternalAPIError,
    SessionNotFoundError,
    SQLExecutionError,
    SQLValidationError,
)
from core.rate_limit import limiter
from modules.query.service import ask

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    session_id: str
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/api/query/ask")
@limiter.limit("10/minute")
async def ask_endpoint(
    request: Request,
    body: AskRequest,
    user: AuthenticatedUser = Depends(verify_session_ownership),
) -> dict:
    """
    Primary orchestration endpoint.
    Runs the full NL → SQL → execute pipeline and returns merged results.
    """
    request_id = get_request_id()

    try:
        result = await ask(
            session_id=body.session_id,
            question=body.question,
            page=body.page,
            page_size=body.page_size,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_type": "session_not_found",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc
    except SQLValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_type": "validation_failed",
                "message": str(exc),
                "sql_attempted": None,
                "request_id": request_id,
            },
        ) from exc
    except SQLExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_type": "execution_failed",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc
    except ExternalAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_type": "external_api_error",
                "message": str(exc),
                "request_id": request_id,
            },
        ) from exc

    # ask() may return inline error dicts for validation / execution failures
    # (when the error carries useful context like the generated SQL)
    if not result.get("success", True):
        error_type = result.get("error_type", "unknown_error")

        # Determine HTTP status
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        if error_type == "execution_failed":
            detail = {
                "error_type": error_type,
                "message": result.get("message", "Execution failed."),
                "sql": result.get("sql"),
                "rationale": result.get("rationale"),
                "request_id": request_id,
            }
        else:
            detail = {
                "error_type": error_type,
                "message": result.get("message", "Validation failed."),
                "sql_attempted": result.get("sql_attempted"),
                "request_id": request_id,
            }

        raise HTTPException(status_code=status_code, detail=detail)

    return result
