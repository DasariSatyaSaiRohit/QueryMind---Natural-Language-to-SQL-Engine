# service/routes/session.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from datetime import datetime, timedelta
import json
import redis.asyncio as redis

from app.core.security import decrypt, encrypt
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.connection import Connection
from app.services.schema_service import _sync_introspect

router = APIRouter(prefix="/session", tags=["session"])

# Pydantic Models
class SessionConnectRequest(BaseModel):
    connection_id: str
    user_id: str

class SessionConnectResponse(BaseModel):
    success: bool
    data: dict

@router.post("/connect", response_model=SessionConnectResponse)
async def connect_session(
    request: SessionConnectRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis)
):
    """
    Create new database session for a connection
    
    Business Logic (Service owns):
    1. Validate connection exists
    2. Create ephemeral database connection
    3. Cache session in Redis (TTL: 1 hour)
    4. Return session_id for subsequent queries
    """
    try:
        # 1. Validate connection exists
        connection = await db.get(Connection, request.connection_id)
        if not connection or connection.user_id != request.user_id:
            raise HTTPException(
                status_code=404,
                detail={'success': False, 'message': 'Connection not found'}
            )
        
        # 2. Create session
        session_id = uuid4().hex
        
        # 3. Cache session in Redis (ephemeral DB connection)
        cache_key = f"session:{session_id}"
        session_data = {
            'session_id': session_id,
            'connection_id': request.connection_id,
            'connection_string': connection.connection_string_encrypted,
            'user_id': request.user_id,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
        
        await redis_client.setex(
            cache_key,
            3600,  # 1 hour TTL
            json.dumps(session_data)
        )
        
        # 4. Update last_accessed
        connection.last_accessed = datetime.utcnow()
        await db.commit()
        
        return SessionConnectResponse(
            success=True,
            data={
                'session_id': session_id,
                'connection_id': request.connection_id,
                'expires_at': session_data['expires_at']
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={'success': False, 'message': f'Failed to create session: {str(e)}'}
        )


@router.get("/ {session_id}/schema")
async def get_session_schema(
    session_id: str,
    user_id: str,
    redis_client: Redis = Depends(get_redis)
):
    """
    Get database schema for session
    
    Business Logic (Service owns):
    1. Validate session exists
    2. Get cached schema from Redis
    3. If not cached, introspect schema from database
    4. Cache schema for 7 days
    """
    try:
        # 1. Validate session
        cache_key = f"session:{session_id}"
        session_data = await redis_client.get(cache_key)
        
        if not session_data:
            raise HTTPException(
                status_code=404,
                detail={'success': False, 'message': 'Session not found or expired'}
            )
        
        session = json.loads(session_data)
        if session['user_id'] != user_id:
            raise HTTPException(
                status_code=403,
                detail={'success': False, 'message': 'Unauthorized'}
            )
        
        # 2. Check cached schema
        schema_key = f"schema:{session_id}"
        cached_schema = await redis_client.get(schema_key)
        
        if cached_schema:
            return {
                'success': True,
                'data': json.loads(cached_schema),
                'cache_hit': True
            }
        
        # 3. Introspect schema from database
        connection_string = session['connection_string']
        schema = await _sync_introspect(connection_string)
        
        # 4. Cache schema (7 days)
        await redis_client.setex(
            schema_key,
            604800,  # 7 days
            json.dumps(schema)
        )
        
        return {
            'success': True,
            'data': schema,
            'cache_hit': False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={'success': False, 'message': f'Failed to get schema: {str(e)}'}
        )


@router.get("/{session_id}/tables")
async def get_session_tables(
    session_id: str,
    user_id: str,
    redis_client: Redis = Depends(get_redis)
):
    """
    Get tables list for session
    
    Business Logic (Service owns):
    1. Validate session
    2. Get schema from cache (already cached by /schema endpoint)
    3. Return only tables
    """
    try:
        # Validate session
        cache_key = f"session:{session_id}"
        session_data = await redis_client.get(cache_key)
        
        if not session_data:
            raise HTTPException(
                status_code=404,
                detail={'success': False, 'message': 'Session not found'}
            )
        
        # Get cached schema
        schema_key = f"schema:{session_id}"
        cached_schema = await redis_client.get(schema_key)
        
        if not cached_schema:
            raise HTTPException(
                status_code=404,
                detail={'success': False, 'message': 'Schema not introspected'}
            )
        
        schema = json.loads(cached_schema)
        
        # Return only tables
        return {
            'success': True,
            'data': {
                'tables': schema['tables']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={'success': False, 'message': f'Failed to get tables: {str(e)}'}
        )


@router.get("/{session_id}/tables/{table_id}/schema")
async def get_table_schema(
    session_id: str,
    table_id: str,
    user_id: str,
    redis_client: Redis = Depends(get_redis)
):
    """
    Get table schema details
    
    Business Logic (Service owns):
    1. Validate session
    2. Get cached schema
    3. Filter for specific table
    """
    try:
        # Validate session
        cache_key = f"session:{session_id}"
        session_data = await redis_client.get(cache_key)
        
        if not session_data:
            raise HTTPException(
                status_code=404,
                detail={'success': False, 'message': 'Session not found'}
            )
        
        # Get cached schema
        schema_key = f"schema:{session_id}"
        cached_schema = await redis_client.get(schema_key)
        
        if not cached_schema:
            raise HTTPException(
                status_code=404,
                detail={'success': False, 'message': 'Schema not introspected'}
            )
        
        schema = json.loads(cached_schema)
        
        # Filter for specific table
        table = next(
            (t for t in schema['tables'] if t['table_id'] == table_id),
            None
        )
        
        if not table:
            raise HTTPException(
                status_code=404,
                detail={'success': False, 'message': 'Table not found'}
            )
        
        return {
            'success': True,
            'data': {
                'table_id': table['table_id'],
                'table_name': table['table_name'],
                'columns': table['columns']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={'success': False, 'message': f'Failed to get table schema: {str(e)}'}
        )


@router.get("/{session_id}/columns/{table_id}")
async def get_table_columns(
    session_id: str,
    table_id: str,
    user_id: str,
    redis_client: Redis = Depends(get_redis)
):
    """
    Get columns for specific table
    
    Business Logic (Service owns):
    1. Validate session
    2. Get table schema
    3. Return only columns
    """
    try:
        # Get table schema (calls previous endpoint logic)
        table_schema_response = await get_table_schema(
            session_id, table_id, user_id, redis_client
        )
        
        # Return only columns
        return {
            'success': True,
            'data': {
                'table_id': table_schema_response['data']['table_id'],
                'table_name': table_schema_response['data']['table_name'],
                'columns': table_schema_response['data']['columns']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={'success': False, 'message': f'Failed to get columns: {str(e)}'}
        )


@router.delete("/{session_id}")
async def close_session(
    session_id: str,
    user_id: str,
    redis_client: Redis = Depends(get_redis)
):
    """
    Close database session (cleanup ephemeral connection)
    
    Business Logic (Service owns):
    1. Validate session
    2. Delete from Redis (cleanup)
    3. Return success
    """
    try:
        # Validate session
        cache_key = f"session:{session_id}"
        session_data = await redis_client.get(cache_key)
        
        if not session_data:
            raise HTTPException(
                status_code=404,
                detail={'success': False, 'message': 'Session not found'}
            )
        
        session = json.loads(session_data)
        if session['user_id'] != user_id:
            raise HTTPException(
                status_code=403,
                detail={'success': False, 'message': 'Unauthorized'}
            )
        
        # Delete session from Redis
        await redis_client.delete(cache_key)
        
        # Delete cached schema
        schema_key = f"schema:{session_id}"
        await redis_client.delete(schema_key)
        
        return {
            'success': True,
            'message': 'Session closed'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={'success': False, 'message': f'Failed to close session: {str(e)}'}
        )