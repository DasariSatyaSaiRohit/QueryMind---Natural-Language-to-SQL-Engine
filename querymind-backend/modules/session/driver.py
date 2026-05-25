"""
DatabaseDriver protocol and concrete implementations.

Only PostgreSQL is fully implemented.
MySQL and MongoDB are declared stubs that raise NotImplementedError.
"""

import logging
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

from sqlalchemy import Engine, create_engine, text

from core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class DatabaseDriver(Protocol):
    db_type: str
    url_prefix: str

    def create_engine(self, connection_string: str, pool_config: dict) -> Engine:
        """Create and return a SQLAlchemy engine for this database type."""
        ...

    def test_connection(self, engine: Engine) -> str:
        """
        Test connectivity.
        Return the active database name.
        Raise on any failure.
        """
        ...

    def get_connection_info(self, connection_string: str) -> dict:
        """Extract host, port, database name, and username from connection string."""
        ...


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

class PostgreSQLDriver:
    db_type = "postgresql"
    url_prefix = "postgresql"

    def create_engine(self, connection_string: str, pool_config: dict) -> Engine:
        """
        Create a SQLAlchemy engine for PostgreSQL.

        pool_pre_ping=True is always enabled so stale connections are detected.
        connect_timeout is taken from pool_config (default 10 s).
        """
        connect_timeout = pool_config.get("pool_timeout", settings.DB_POOL_TIMEOUT)
        return create_engine(
            connection_string,
            pool_size=pool_config.get("pool_size", settings.DB_POOL_SIZE),
            max_overflow=pool_config.get("max_overflow", settings.DB_MAX_OVERFLOW),
            pool_timeout=connect_timeout,
            pool_recycle=pool_config.get("pool_recycle", settings.DB_POOL_RECYCLE),
            pool_pre_ping=True,
            connect_args={"connect_timeout": connect_timeout},
        )

    def test_connection(self, engine: Engine) -> str:
        """
        Execute SELECT current_database() and return the database name.
        Raises any SQLAlchemy / DBAPI exception on failure.
        """
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database()"))
            row = result.fetchone()
            if row is None:
                raise RuntimeError("SELECT current_database() returned no rows")
            return str(row[0])

    def get_connection_info(self, connection_string: str) -> dict:
        """
        Parse a PostgreSQL DSN and return { host, port, database, username }.

        Handles both postgresql:// and postgresql+psycopg2:// schemes.
        """
        parsed = urlparse(connection_string)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": (parsed.path or "").lstrip("/") or "postgres",
            "username": parsed.username or "",
        }


# ---------------------------------------------------------------------------
# MySQL (stub)
# ---------------------------------------------------------------------------

class MySQLDriver:
    db_type = "mysql"
    url_prefix = "mysql"

    def create_engine(self, connection_string: str, pool_config: dict) -> Engine:
        raise NotImplementedError("MySQL support is not yet implemented.")

    def test_connection(self, engine: Engine) -> str:
        raise NotImplementedError("MySQL support is not yet implemented.")

    def get_connection_info(self, connection_string: str) -> dict:
        raise NotImplementedError("MySQL support is not yet implemented.")


# ---------------------------------------------------------------------------
# MongoDB (stub)
# ---------------------------------------------------------------------------

class MongoDBDriver:
    db_type = "mongodb"
    url_prefix = "mongodb"

    def create_engine(self, connection_string: str, pool_config: dict) -> Engine:
        raise NotImplementedError("MongoDB support is not yet implemented.")

    def test_connection(self, engine: Engine) -> str:
        raise NotImplementedError("MongoDB support is not yet implemented.")

    def get_connection_info(self, connection_string: str) -> dict:
        raise NotImplementedError("MongoDB support is not yet implemented.")


# ---------------------------------------------------------------------------
# Driver registry
# ---------------------------------------------------------------------------

DRIVERS: dict[str, DatabaseDriver] = {
    "postgresql": PostgreSQLDriver(),
    "postgres":   PostgreSQLDriver(),
    "mysql":      MySQLDriver(),
    "mongodb":    MongoDBDriver(),
}


def get_driver(connection_string: str) -> DatabaseDriver:
    """
    Detect the database type from the connection string prefix (scheme).
    Returns the appropriate driver instance.

    Raises:
        ValueError: If the scheme is unrecognised or the string is malformed.
    """
    if not connection_string or "://" not in connection_string:
        raise ValueError(
            f"Invalid connection string: expected 'scheme://...' but got: {connection_string!r}"
        )

    scheme = connection_string.split("://")[0].lower()
    # Strip SQLAlchemy dialect suffix (e.g. postgresql+psycopg2 → postgresql)
    base_scheme = scheme.split("+")[0]

    driver = DRIVERS.get(base_scheme)
    if driver is None:
        supported = ", ".join(sorted(set(DRIVERS.keys())))
        raise ValueError(
            f"Unsupported database type {base_scheme!r}. "
            f"Supported schemes: {supported}"
        )
    return driver
