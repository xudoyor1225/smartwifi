"""Task discovery and registration for Celery workers.

This package contains all async task definitions for the Smart WiFi Dashboard.
Tasks are auto-discovered by the Celery app and routed to appropriate queues:

- reports.* → 'reports' queue (PDF/Excel report generation)
- ai.* → 'ai_analysis' queue (traffic analysis, anomaly detection)
- default → 'default' queue (general background tasks)

Import the celery app and base task for use in task modules:

    from app.core.celery_app import celery_app
    from app.tasks.base import BaseTask

    @celery_app.task(base=BaseTask, bind=True, name="reports.generate_pdf")
    def generate_pdf_report(self, tenant_id: str, params: dict) -> dict:
        ...
"""

from app.core.celery_app import celery_app
from app.tasks.base import BaseTask

__all__ = ["celery_app", "BaseTask"]
