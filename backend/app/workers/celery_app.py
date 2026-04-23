from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "firemanager",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.health_check",
        "app.workers.execute_operation",
        "app.workers.generate_documents",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "health-check-all-devices": {
            "task": "app.workers.health_check.run_health_checks",
            "schedule": crontab(minute="*/5"),  # every 5 minutes
        },
    },
)
