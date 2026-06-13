"""
Celery tasks – run in the celery-worker container.

NOTE: Celery tasks are synchronous by default.  We use asyncio.run() to bridge
the sync Celery world to our async SQLAlchemy session maker.
"""
import asyncio
import uuid
from datetime import datetime

from app.services.schema_service import introspect_and_cache
from app.workers.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="persist_history",
    max_retries=3,
    acks_late=True,
)
def persist_history(self, session_id: str, record: dict):
    """Persist a query history record to PostgreSQL."""
    try:
        asyncio.run(_async_persist(session_id, record))
    except Exception as exc:
        logger.error(
            "persist_history.failed",
            session_id=session_id,
            attempt=self.request.retries,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, name="introspect_schema", max_retries=3, acks_late=True)
def introspect_schema(self, session_id: str, connection_string: str):
    """Introspect DB schema and cache it in Redis."""
    try:
        asyncio.run(introspect_and_cache(session_id, connection_string))
    except Exception as exc:
        logger.error(
            "introspect_schema.failed",
            session_id=session_id,
            attempt=self.request.retries,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _async_persist(session_id: str, record: dict) -> None:
    from app.db.session import async_session_maker
    from app.models.query_history import QueryHistory

    async with async_session_maker() as db:
        history = QueryHistory(
            history_id=uuid.uuid4().hex,
            session_id=session_id,
            user_input=record.get("user_input", ""),
            sql_query=record.get("sql_query", ""),
            chain_of_thought=record.get("chain_of_thought"),
            execution_time_ms=record.get("execution_time_ms"),
            cache_hit=record.get("cache_hit", False),
            correlation_id=record.get("correlation_id"),
            created_at=datetime.utcnow(),
        )
        db.add(history)
        await db.commit()
    logger.info(
        "persist_history.ok",
        history_id=history.history_id,
        session_id=session_id,
    )