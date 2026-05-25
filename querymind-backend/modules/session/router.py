"""
Session API router.

POST   /api/session/connect
DELETE /api/session/{session_id}/disconnect
GET    /api/session/{session_id}/info

All endpoints require JWT auth.
session_id_var is set on every request so downstream logs carry it.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, field_validator

from core.auth import require_auth
from core.context import set_session_id
from modules.session.service import connect, disconnect, get_session_info

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    session_id: str
    connection_string: str

    @field_validator("session_id")
    @classmethod
    def session_id_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("session_id must not be empty")
        return v

    @field_validator("connection_string")
    @classmethod
    def conn_str_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("connection_string must not be empty")
        return v


class ConnectResponse(BaseModel):
    session_id: str
    database_name: str
    connected_at: str
    db_type: str
    status: str


class DisconnectResponse(BaseModel):
    session_id: str
    status: str


class SessionInfoResponse(BaseModel):
    session_id: str
    database_name: str
    connected_at: str
    db_type: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/connect",
    response_model=ConnectResponse,
    summary="Connect to a database",
    status_code=200,
)
async def connect_endpoint(
    body: ConnectRequest,
    _token: Annotated[dict, Depends(require_auth)],
) -> ConnectResponse:
    """
    Establish a new database session.

    - Validates the connection string.
    - Creates a SQLAlchemy engine and tests connectivity.
    - Persists the encrypted connection string to Redis.
    - Dispatches schema warm-up in the background.
    """
    set_session_id(body.session_id)
    result = await connect(body.session_id, body.connection_string)
    return ConnectResponse(**result)


@router.delete(
    "/{session_id}/disconnect",
    response_model=DisconnectResponse,
    summary="Disconnect a database session",
    status_code=200,
)
async def disconnect_endpoint(
    session_id: Annotated[str, Path(description="The session to disconnect")],
    _token: Annotated[dict, Depends(require_auth)],
) -> DisconnectResponse:
    """
    Tear down an active session, dispose the engine, and remove all cached data.
    """
    set_session_id(session_id)
    result = await disconnect(session_id)
    return DisconnectResponse(**result)


@router.get(
    "/{session_id}/info",
    response_model=SessionInfoResponse,
    summary="Get session metadata",
    status_code=200,
)
async def session_info_endpoint(
    session_id: Annotated[str, Path(description="The session to inspect")],
    _token: Annotated[dict, Depends(require_auth)],
) -> SessionInfoResponse:
    """
    Return metadata for an active session (database name, type, connected_at).
    Does not touch the engine or run any SQL.
    """
    set_session_id(session_id)
    result = await get_session_info(session_id)
    return SessionInfoResponse(**result)
