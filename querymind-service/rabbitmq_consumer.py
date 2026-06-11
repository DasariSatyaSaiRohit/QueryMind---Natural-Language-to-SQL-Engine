"""
Standalone RabbitMQ consumer.

Reads from `history-persist-queue` and fires Celery `persist_history` tasks.
Run as: python rabbitmq_consumer.py
"""
import asyncio
import json
import os

import aio_pika
from aio_pika import IncomingMessage

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672")
QUEUE_NAME = "history-persist-queue"


async def on_message(message: IncomingMessage) -> None:
    async with message.process():
        try:
            data = json.loads(message.body)
            session_id = data["session_id"]
            record = data["record"]

            # Fire Celery task (non-blocking)
            from app.workers.tasks import persist_history
            persist_history.delay(session_id, record)

            print(f"[consumer] Dispatched persist_history for session={session_id}")
        except Exception as exc:
            print(f"[consumer] Failed to process message: {exc}")


async def main() -> None:
    print(f"[consumer] Connecting to {RABBITMQ_URL}")
    connection = await aio_pika.connect_robust(RABBITMQ_URL)

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        queue = await channel.declare_queue(QUEUE_NAME, durable=True)

        print(f"[consumer] Listening on queue: {QUEUE_NAME}")
        await queue.consume(on_message)
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
