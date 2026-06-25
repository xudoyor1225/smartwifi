"""Celery application configuration with Redis broker and result backend.

Configures task routing, serialization, result expiry, and worker concurrency
settings for the Smart WiFi Dashboard async task processing.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "smart_wifi_dashboard",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Serialization settings
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Result expiry: 1 hour
    result_expires=3600,
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Worker concurrency settings
    worker_concurrency=4,
    worker_prefetch_multiplier=2,
    worker_max_tasks_per_child=1000,
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit
)

# Task routing: direct tasks to specific queues
celery_app.conf.task_routes = {
    "reports.*": {"queue": "reports"},
    "ai.*": {"queue": "ai_analysis"},
}

# Default queue for tasks that don't match any route
celery_app.conf.task_default_queue = "default"

# Queue definitions for worker startup
celery_app.conf.task_queues_from_config = {
    "default": {"exchange": "default", "routing_key": "default"},
    "reports": {"exchange": "reports", "routing_key": "reports"},
    "ai_analysis": {"exchange": "ai_analysis", "routing_key": "ai_analysis"},
}

# Auto-discover tasks from the app.tasks package
celery_app.autodiscover_tasks(["app.tasks"])
