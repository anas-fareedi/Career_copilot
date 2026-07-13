"""
Celery application instance.

Usage:
  Start worker:   celery -A APP.workers.celery_app worker --loglevel=info
  Start beat:     celery -A APP.workers.celery_app beat --loglevel=info
  Inspect tasks:  celery -A APP.workers.celery_app inspect active
"""

from celery import Celery
from celery.schedules import crontab

from APP.core.config import settings

celery_app = Celery(
    "career_copilot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["APP.workers.tasks"],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Retry / reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_default_retry_delay=60,  # seconds

    # Result expiry — keep results for 24 hours so pipeline status can be polled
    result_expires=86400,

    # Beat schedule
    # Primary: autonomous discovery + tailoring every 6 hours for opted-in users
    # Secondary: lightweight discovery-only sweep (kept for manual trigger compatibility)
    beat_schedule={
        "autonomous-discovery-and-tailor-every-6h": {
            "task": "APP.workers.tasks.run_discovery_and_tailor_for_all_users",
            "schedule": crontab(minute=0, hour="*/6"),
        },
    },
)
