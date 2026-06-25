"""Base task class with error handling and retry logic.

Provides a reusable base for all Celery tasks with:
- Exponential backoff retry (max 3 retries)
- Structured error handling and logging
- Task lifecycle hooks for monitoring
"""

import logging
from typing import Any

from celery import Task

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # Exponential backoff base in seconds
RETRY_BACKOFF_MAX = 60  # Maximum backoff delay in seconds


class BaseTask(Task):
    """Base task class with built-in error handling and exponential backoff retry.

    All application tasks should inherit from this class to get consistent
    retry behavior and error logging.

    Usage:
        @celery_app.task(base=BaseTask, bind=True, name="reports.generate_pdf")
        def generate_pdf_report(self, tenant_id: str, params: dict) -> dict:
            ...
    """

    abstract = True
    autoretry_for = (Exception,)
    max_retries = MAX_RETRIES
    retry_backoff = RETRY_BACKOFF
    retry_backoff_max = RETRY_BACKOFF_MAX
    retry_jitter = True

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Called when the task is retried."""
        logger.warning(
            "Task %s[%s] retrying (attempt %d/%d): %s",
            self.name,
            task_id,
            self.request.retries + 1,
            self.max_retries,
            str(exc),
        )

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Called when the task fails after all retries are exhausted."""
        logger.error(
            "Task %s[%s] failed permanently after %d retries: %s",
            self.name,
            task_id,
            self.max_retries,
            str(exc),
            exc_info=True,
        )

    def on_success(
        self,
        retval: Any,
        task_id: str,
        args: tuple,
        kwargs: dict[str, Any],
    ) -> None:
        """Called when the task completes successfully."""
        logger.info(
            "Task %s[%s] completed successfully.",
            self.name,
            task_id,
        )

    def before_start(
        self,
        task_id: str,
        args: tuple,
        kwargs: dict[str, Any],
    ) -> None:
        """Called before the task starts executing."""
        logger.info(
            "Task %s[%s] starting.",
            self.name,
            task_id,
        )
