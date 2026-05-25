"""
Session service — high-level operations called by the API layer.

connect()          → validate + create engine + persist to Redis + warm cache
disconnect()       → dispose engine + wipe all Redis keys
get_session_info() → return metadata from Redis
"""

import logging
from datetime import datetime, timezone

from core.config import settings
from core.database import encrypt_connection_string
from core.exceptions import DatabaseConnectionError, SessionNotFoundError

from modules.session.driver import get_driver
from modules.session.store import session_store

logger = logging.getLogger(__name__)


async def connect(session_id: str, connection_string: str) -> dict:
    """
    Establish a new database session.

    Steps:
      1. Validate the connection string is non-empty.
      2. Detect the appropriate driver from the scheme.
      3. If the session already exists, disconnect it first (idempotent reconnect).
      4. Encrypt the connection string.
      5. Create the engine via the driver.
      6. Test the connection; raise DatabaseConnectionError on failure.
      7. Store the session in the SessionStore (in-memory + Redis).
      8. Dispatch warm_cache Celery task (fire-and-forget).
      9. Return session metadata.

    Returns:
        dict with keys: session_id, database_name, connected_at, db_type, status
    """
    connection_string = (connection_string or "").strip()
    if not connection_string:
        raise DatabaseConnectionError("Connection string must not be empty.")

    driver = get_driver(connection_string)

    # Idempotent reconnect — clean up any existing session first
    if session_store.has(session_id):
        logger.info(f"[connect] Re-connecting existing session_id={session_id}")
        session_store.remove(session_id)

    pool_config = {
        "pool_size":    settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    }

    # Create engine
    try:
        engine = driver.create_engine(connection_string, pool_config)
    except Exception as exc:
        raise DatabaseConnectionError(
            f"Failed to initialise connection for session {session_id!r}: {exc}"
        ) from exc

    # Test reachability
    try:
        database_name = driver.test_connection(engine)
    except Exception as exc:
        engine.dispose()
        raise DatabaseConnectionError(
            f"Could not connect to the database: {exc}"
        ) from exc

    encrypted_conn_str = encrypt_connection_string(connection_string)
    meta = session_store.add(
        session_id=session_id,
        engine=engine,
        database_name=database_name,
        encrypted_conn_str=encrypted_conn_str,
        db_type=driver.db_type,
    )

    # Fire-and-forget: warm the schema cache in the background
    try:
        from workers.tasks import warm_cache
        warm_cache.delay(session_id, encrypted_conn_str)
        logger.info(f"[connect] Dispatched warm_cache for session_id={session_id}")
    except Exception as exc:
        # Celery broker unavailable should NOT fail the connect response
        logger.warning(
            f"[connect] Could not dispatch warm_cache for session_id={session_id}: {exc}"
        )

    logger.info(
        f"[connect] session_id={session_id} db={database_name} type={driver.db_type}"
    )
    return {**meta, "status": "connected"}


async def disconnect(session_id: str) -> dict:
    """
    Tear down an active database session.

    Raises:
        SessionNotFoundError: If the session does not exist.

    Returns:
        dict with keys: session_id, status
    """
    if not session_store.has(session_id):
        raise SessionNotFoundError(f"Session {session_id!r} not found.")

    # get_engine may reconstruct the engine from Redis; that's fine — we
    # just need to dispose it cleanly.
    try:
        engine = session_store.get_engine(session_id)
        engine.dispose()
    except (SessionNotFoundError, Exception) as exc:
        logger.warning(
            f"[disconnect] Could not dispose engine for session_id={session_id}: {exc}"
        )

    session_store.remove(session_id)
    logger.info(f"[disconnect] session_id={session_id} disconnected")
    return {"session_id": session_id, "status": "disconnected"}


async def get_session_info(session_id: str) -> dict:
    """
    Return metadata for an active session without touching the engine.

    Raises:
        SessionNotFoundError: If the session does not exist in Redis.

    Returns:
        dict with keys: session_id, database_name, connected_at, db_type
    """
    meta = session_store.get_meta(session_id)
    if meta is None:
        raise SessionNotFoundError(f"Session {session_id!r} not found.")
    return meta
