"""
Async RabbitMQ client using aio-pika.

Publishes history records to `history-persist-queue`.
Falls back to synchronous DB write if publish fails.
"""
from datetime import timedelta
import json
from typing import Any

import aio_pika
from aio_pika import Connection, Channel, Message

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RabbitMQClient:
    def __init__(self) -> None:
        self._connection: Connection | None = None
        self._channel: Channel | None = None

    async def connect(self) -> None:
        try:
            logger.info("Connecting to RabbitMQ at ...")
            self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self._channel = await self._connection.channel()
            await self._channel.declare_queue(settings.HISTORY_QUEUE, durable=True)
            await self._channel.declare_queue(settings.HISTORY_DLQ, durable=True)
            await self._channel.declare_queue(settings.INTROSPECTION_QUEUE, durable=True)
            logger.info("rabbitmq.connected", Connection=self._connection, Channel=self._channel)
        except Exception as exc:
            logger.warning("rabbitmq.connect_failed", error=str(exc))
            self._connection = None
            self._channel = None

    async def publish(
        self, queue: str, session_id: str, record: dict[str, Any], correlation_id: str | None = None
    ) -> bool:
        if self._channel is None:
            logger.warning("rabbitmq.not_connected, falling back to sync persist")
            await self._fallback_sync_persist(session_id, record)
            return False

        try:
            body = json.dumps({"session_id": session_id, "record": record}).encode()
            headers: dict[str, str] = {}
            if correlation_id:
                headers["x-correlation-id"] = correlation_id

            message = Message(
                body=body,
                content_type="application/json",
                headers=headers,
                expiration=timedelta(milliseconds=settings.MESSAGE_EXPIRATION_MS),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await self._channel.default_exchange.publish(
                message, routing_key=queue
            )
            logger.info("rabbitmq.published", session_id=session_id)
            return True
        except Exception as exc:
            logger.error("rabbitmq.publish_failed", error=str(exc))
            await self._fallback_sync_persist(session_id, record)
            return False

    async def _fallback_sync_persist(
        self, session_id: str, record: dict[str, Any]
    ) -> None:
        """Direct DB write when RabbitMQ is unavailable."""
        import uuid
        from datetime import datetime
        from app.db.session import async_session_maker
        from app.models.query_history import QueryHistory

        try:
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
            logger.info("rabbitmq.fallback_persist_ok", session_id=session_id)
        except Exception as e:
            logger.error("rabbitmq.fallback_persist_failed", error=str(e))

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("rabbitmq.disconnected")


rabbitmq_client = RabbitMQClient()
