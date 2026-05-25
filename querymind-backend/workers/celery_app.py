import logging
from celery import Celery
from core.config import settings

logger = logging.getLogger(__name__)


def create_celery() -> Celery:
    app = Celery("querymind")
    app.conf.update(
        broker_url=settings.AMQP_URL,
        result_backend=None,              # fire-and-forget, no result storage
        task_serializer="json",
        accept_content=["json"],
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_routes={
            "querymind.tasks.warm_cache":              {"queue": "schema-tasks"},
            "querymind.tasks.refresh_expiring_caches": {"queue": "schema-tasks"},
            "querymind.tasks.log_usage":               {"queue": "ai-tasks"},
            "querymind.tasks.cache_query_result":      {"queue": "ai-tasks"},
            "querymind.tasks.persist_history":         {"queue": "exec-tasks"},
            "querymind.tasks.archive_result":          {"queue": "exec-tasks"},
        },
        beat_schedule={
            "refresh-expiring-caches": {
                "task": "querymind.tasks.refresh_expiring_caches",
                "schedule": 3300.0,           # every 55 minutes
            }
        },
    )
    return app


celery_app = create_celery()
