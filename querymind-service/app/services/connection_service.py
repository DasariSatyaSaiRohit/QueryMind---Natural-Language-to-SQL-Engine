"""
Connection management service.

Handles CRUD for the connections table, encrypting connection strings at rest,
and caching per-user connection lists in Redis.
"""
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import encrypt, decrypt
from app.db.redis import redis_get, redis_set, redis_delete
from app.models.connection import Connection
from app.schemas.connection import ConnectionResponse

logger = get_logger(__name__)

_USER_CONN_CACHE_KEY = "user_connections:{user_id}"
_USER_CONN_CACHE_TTL = 300  # 5 minutes


def _extract_db_name(connection_string: str) -> str:
    match = re.search(r"/([^/?]+)(\?|$)", connection_string)
    return match.group(1) if match else "unknown"


def _detect_db_type(connection_string: str) -> str:
    if connection_string.startswith(("postgresql", "postgres")):
        return "postgresql"
    if connection_string.startswith("mysql"):
        return "mysql"
    if connection_string.startswith("sqlite"):
        return "sqlite"
    return "unknown"

import socket

def _validate_connection_reachable(connection_string: str) -> bool:
    """Quick sync check using psycopg2 directly — never asyncpg."""
    if connection_string.startswith("sqlite"):
        return True

    orig_getaddrinfo = socket.getaddrinfo
    def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
        return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = getaddrinfo_ipv4

    try:
        import psycopg2
        # Strip params asyncpg/psycopg2 choke on, force psycopg2 scheme
        clean = (
            connection_string
            .replace("postgresql+asyncpg://", "postgresql://")
            .replace("postgresql+psycopg2://", "postgresql://")
            .replace("&channel_binding=require", "")
            .replace("?channel_binding=require&", "?")
            .replace("channel_binding=require", "")
        )
        conn = psycopg2.connect(clean, connect_timeout=5)
        conn.close()
        return True
    except Exception as e:
        logger.warning("connection.validation_failed", error=str(e))
        return False
    finally:
        socket.getaddrinfo = orig_getaddrinfo


# Function returns Pydantic
async def get_connections_for_user(
    session: AsyncSession, user_id: str
) -> list[ConnectionResponse]:  # ✅ Return Pydantic
    cache_key = _USER_CONN_CACHE_KEY.format(user_id=user_id)
    
    # Try cache
    cached = await redis_get(cache_key)
    if cached:
        # Convert cached dict to Pydantic
        return [ConnectionResponse.model_validate(c) for c in cached]
        
    # Query DB
    result = await session.execute(
        select(Connection).where(
            Connection.user_id == user_id,
            Connection.deleted_at.is_(None),
        )
    )
    
    connections = result.scalars().all()
    
    # Create Pydantic objects
    connections_response = [
        ConnectionResponse.model_validate(c)
        for c in connections
    ]
    
    # Cache as dict (serialize)
    await redis_set(
        cache_key,
        [c.model_dump() for c in connections_response],
        ttl=_USER_CONN_CACHE_TTL,
    )
    print(connections_response, "Caching connections for user", user_id)
    return connections_response  # ✅ Return Pydantic


async def get_connection_by_id(
    session: AsyncSession, connection_id: str
) -> Connection | None:
    result = await session.execute(
        select(Connection).where(
            Connection.connection_id == connection_id,
            Connection.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_decrypted_connection_string(
    session: AsyncSession, connection_id: str
) -> str | None:
    conn = await get_connection_by_id(session, connection_id)
    if conn is None:
        return None
    return decrypt(conn.connection_string_encrypted)


async def soft_delete_connection(
    session: AsyncSession, connection_id: str, user_id: str
) -> bool:
    result = await session.execute(
        select(Connection).where(
            Connection.connection_id == connection_id,
            Connection.user_id == user_id,
            Connection.deleted_at.is_(None),
        )
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        return False
    conn.deleted_at = datetime.utcnow()
    await redis_delete(_USER_CONN_CACHE_KEY.format(user_id=user_id))
    return True

async def add_connection(
    session: AsyncSession,
    user_id: str,
    connection_string: str,
    table_count: int = 0,
) -> Connection:
    encrypted = encrypt(connection_string)
    db_name = _extract_db_name(connection_string)
    db_type = _detect_db_type(connection_string)

    connection = Connection(
        connection_id=uuid.uuid4().hex,
        user_id=user_id,
        connection_string_encrypted=encrypted,
        db_name=db_name,
        db_type=db_type,
        table_count=table_count,
        created_at=datetime.utcnow(),
    )
    session.add(connection)
    await session.flush()
    await session.commit()       # ← was missing
    await session.refresh(connection)
    await redis_delete(_USER_CONN_CACHE_KEY.format(user_id=user_id))
    logger.info("connection.added", connection_id=connection.connection_id, user_id=user_id)
    return connection