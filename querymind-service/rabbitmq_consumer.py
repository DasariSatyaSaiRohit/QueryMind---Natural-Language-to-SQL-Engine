"""
Standalone RabbitMQ consumer.

Reads from `history-persist-queue` and `introspection-queue` and fires Celery tasks.
Run as: python rabbitmq_consumer.py
"""
import asyncio
import json

import aio_pika
from aio_pika import IncomingMessage

from app.core.config import settings
from app.core.security import decrypt
from app.services.schema_service import introspect_and_cache
from app.workers.tasks import _async_persist, persist_history, introspect_schema


async def on_message(message: IncomingMessage) -> None:
    async with message.process():
        try:
            data = json.loads(message.body)
            session_id = data["session_id"]
            record = data["record"]
            match message.routing_key:
                case settings.HISTORY_QUEUE:
                    await _async_persist(session_id, record)
                    print(f"[consumer] Received message on {settings.HISTORY_QUEUE}")
                case settings.INTROSPECTION_QUEUE:
                    await introspect_and_cache(session_id, decrypt(record['connection_string']))
                    print(f"[consumer] Received message on {settings.INTROSPECTION_QUEUE}")
                case _:
                    print(f"[consumer] Received message on unknown queue: {message.routing_key}")
            print(f"[consumer] Received message for session={session_id}")
        except Exception as exc:
            print(f"[consumer] Failed to process message: {exc}")


async def main() -> None:
    try:
        print(f"[consumer] Connecting to {settings.RABBITMQ_URL}")
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)

        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)

            history_queue = await channel.declare_queue(settings.HISTORY_QUEUE, durable=True)
            introspection_queue = await channel.declare_queue(settings.INTROSPECTION_QUEUE, durable=True)

            print(f"[consumer] Listening on queue: {history_queue}")
            print(f"[consumer] Listening on queue: {introspection_queue}")

            await history_queue.consume(on_message)
            await introspection_queue.consume(on_message)

            await asyncio.Future()  # run forever
    except Exception as e:
        print("consumer main error", e)


if __name__ == "__main__":
    asyncio.run(main())