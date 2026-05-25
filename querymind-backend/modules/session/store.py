"""
SessionStore — two-layer session storage.

Layer 1: in-memory dict[session_id -> Engine]   (fast path, lost on restart)
Layer 2: Redis hash session:{session_id}:*       (source of truth)

Redis keys per session:
  session:{session_id}:conn  — encrypted connection string  TTL SESSION_TTL
  session:{session_id}:meta  — JSON metadata dict           TTL SESSION_TTL
"""

import json
import logging
import threading
from datetime import datetime, timezone

import redis as redis_sync
from sqlalchemy import Engine, create_engine, text

from core.config import settings
from core.database import decrypt_connection_string
from core.exceptions import SessionExpiredError, SessionNotFoundError

logger = logging.getLogger(__name__)


def _sync_redis() -> redis_sync.Redis:
    return redis_sync.from_url(settings.REDIS_URL, decode_responses=True)


def _build_engine(conn_str: str) -> Engine:
    """Create a SQLAlchemy engine with pool settings from config."""
    return create_engine(
        conn_str,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,
    )


class SessionStore:
    """
    Thread-safe, Redis-backed session store.

    The in-memory engine dict is a cache only — not the source of truth.
    On process restart, engines are transparently reconstructed from Redis
    so users never need to reconnect.
    """

    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_engine(self, session_id: str) -> Engine:
        """
        Return the SQLAlchemy engine for *session_id*.

        Fast path  → engine already in memory.
        Slow path  → reconstruct from Redis without user interaction.

        Raises:
            SessionNotFoundError: No entry in Redis (session never existed or fully expired).
            SessionExpiredError:  Redis meta entry present but conn string is gone.
            DatabaseConnectionError: Reconstructed engine fails SELECT 1.
        """
        # Fast path
        with self._lock:
            engine = self._engines.get(session_id)
        if engine is not None:
            return engine

        # Slow path — reconstruct from Redis
        r = _sync_redis()
        conn_key = f"session:{session_id}:conn"
        meta_key = f"session:{session_id}:meta"

        encrypted = r.get(conn_key)
        if encrypted is None:
            # Check whether the meta key exists at all to give a better error
            if r.exists(meta_key):
                raise SessionExpiredError(
                    f"Session {session_id!r} exists but the connection string has expired. "
                    "Please reconnect."
                )
            raise SessionNotFoundError(f"Session {session_id!r} not found.")

        try:
            conn_str = decrypt_connection_string(encrypted)
        except ValueError as exc:
            raise SessionExpiredError(
                f"Could not decrypt connection string for session {session_id!r}: {exc}"
            ) from exc

        engine = _build_engine(conn_str)

        # Verify the reconstructed engine is actually reachable
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            engine.dispose()
            from core.exceptions import DatabaseConnectionError
            raise DatabaseConnectionError(
                f"Reconnection attempt for session {session_id!r} failed: {exc}"
            ) from exc

        with self._lock:
            self._engines[session_id] = engine

        logger.info(f"[SessionStore] Reconstructed engine for session_id={session_id} from Redis")
        return engine

    def add(
        self,
        session_id: str,
        engine: Engine,
        database_name: str,
        encrypted_conn_str: str,
        db_type: str = "postgresql",
    ) -> dict:
        """
        Register a newly-created engine and persist session metadata to Redis.

        Returns the metadata dict that was stored.
        """
        connected_at = datetime.now(tz=timezone.utc).isoformat()
        meta = {
            "session_id": session_id,
            "database_name": database_name,
            "connected_at": connected_at,
            "db_type": db_type,
        }

        r = _sync_redis()
        pipe = r.pipeline()
        pipe.setex(f"session:{session_id}:conn", settings.SESSION_TTL, encrypted_conn_str)
        pipe.setex(f"session:{session_id}:meta", settings.SESSION_TTL, json.dumps(meta))
        pipe.execute()

        with self._lock:
            self._engines[session_id] = engine

        logger.info(
            f"[SessionStore] Added session_id={session_id} "
            f"db={database_name} type={db_type}"
        )
        return meta

    def remove(self, session_id: str) -> None:
        """
        Remove engine from memory and delete all Redis keys for the session.
        Idempotent — no error if session does not exist.
        """
        with self._lock:
            engine = self._engines.pop(session_id, None)

        if engine is not None:
            try:
                engine.dispose()
            except Exception as exc:
                logger.warning(f"[SessionStore] Error disposing engine for {session_id}: {exc}")

        r = _sync_redis()

        # Delete all keys associated with this session
        keys_to_delete = [
            f"session:{session_id}:conn",
            f"session:{session_id}:meta",
            f"usage_log:{session_id}",
            f"exec_history:{session_id}",
        ]
        # Also delete schema cache entries via SCAN
        cursor = 0
        while True:
            cursor, schema_keys = r.scan(
                cursor=cursor,
                match=f"schema:{session_id}:*",
                count=100,
            )
            keys_to_delete.extend(schema_keys)
            if cursor == 0:
                break

        if keys_to_delete:
            r.delete(*keys_to_delete)

        logger.info(f"[SessionStore] Removed session_id={session_id}")

    def has(self, session_id: str) -> bool:
        """
        Returns True if the session exists in memory OR in Redis.
        Does not reconstruct the engine.
        """
        with self._lock:
            if session_id in self._engines:
                return True

        r = _sync_redis()
        return bool(r.exists(f"session:{session_id}:conn"))

    def get_meta(self, session_id: str) -> dict | None:
        """
        Return the session metadata dict from Redis without touching the engine.
        Returns None if the session does not exist.
        """
        r = _sync_redis()
        raw = r.get(f"session:{session_id}:meta")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"[SessionStore] Corrupt meta JSON for session_id={session_id}")
            return None

    def count(self) -> int:
        """Return the number of in-memory active engines."""
        with self._lock:
            return len(self._engines)


# Module-level singleton — imported by all other modules
session_store = SessionStore()
