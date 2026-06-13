"""
Connection endpoints.

POST /connections/add   – Store an encrypted connection string, introspect schema.
GET  /connections/{user_id} – List connections for a user.
DELETE /connections/{connection_id} – Soft-delete a connection.
"""
import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.connection import ConnectionAddRequest, ConnectionListResponse, ConnectionResponse
from app.services import connection_service
from app.services.schema_service import introspect_and_cache

router = APIRouter(prefix="/connections", tags=["connections"])
logger = get_logger(__name__)

@router.post("/add", status_code=status.HTTP_201_CREATED)
async def add_connection(
    body: ConnectionAddRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    request_id = getattr(request.state, "request_id", None)

    # Validate reachability (sync, runs in thread pool)
    loop = asyncio.get_event_loop()
    reachable = await loop.run_in_executor(
        None,
        connection_service._validate_connection_reachable,
        body.url,
    )
    if not reachable:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot reach the database with the provided connection string.",
        )

    # Introspect schema to get table count (session_id = user_id for initial connect)
    try:
        schema = await introspect_and_cache(
            session_id=body.user_id,
            connection_string=body.url,
        )
        table_count = len(schema)
    except Exception as exc:
        logger.warning("connections.introspect_failed", error=str(exc))
        table_count = 0

    conn = await connection_service.add_connection(
        session=db,
        user_id=body.user_id,
        connection_string=body.url,
        table_count=table_count,
    )

    return {
        "success": True,
        "data": {
            "connection_id": conn.connection_id,
            "db_name": conn.db_name,
            "db_type": conn.db_type,
            "table_count": conn.table_count,
        },
        "correlation_id": request_id,
    }

@router.get("/{user_id}", response_model=ConnectionListResponse)
@router.get("/list", response_model=ConnectionListResponse)
async def list_connections(
    user_id: str,   
    db: AsyncSession = Depends(get_db),
):    
    connections = await connection_service.get_connections_for_user(db, user_id)
    items = []
    # for c in connections:
    #     item = ConnectionResponse.model_validate(c)
    #     if item.created_at:
    #         item.created_at = item.created_at.isoformat()
    #     items.append(item)
    return ConnectionListResponse(connections=connections, total=len(connections))

@router.delete("/{connection_id}")
async def delete_connection(
    connection_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    deleted = await connection_service.soft_delete_connection(db, connection_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found or already deleted.",
        )
    return {"success": True, "message": "Connection deleted."}

@router.post("/test_connection")
async def test_connection(
    body: ConnectionAddRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        request_id = getattr(request.state, "request_id", None)

        # Validate reachability (sync, runs in thread pool)
        loop = asyncio.get_event_loop()
        reachable = await loop.run_in_executor(
            None,
            connection_service._validate_connection_reachable,
            body.url,
        )
        if not reachable:
            logger.error("Connection test failed: Unreachable")  # Debug print
            return {"success": False, "message": "Cannot reach the database with the provided connection string."}

        return {"success": True, "message": "Connection is reachable."}
    except Exception as exc:
        logger.error("connections.test_connection_failed", error=str(exc))
        return {"success": False, "message": "Error testing connection: " + str(exc)}
        # raise HTTPException(
        #     status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        #     detail="Error testing connection: " + str(exc),
        # )
