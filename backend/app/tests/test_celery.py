"""Tests for Celery task queue configuration."""

from unittest.mock import patch

from celery import Task

from app.core.celery_app import celery_app
from app.tasks.base import BaseTask, MAX_RETRIES, RETRY_BACKOFF, RETRY_BACKOFF_MAX


class TestCeleryAppConfiguration:
    """Tests for Celery application instance configuration."""

    def test_celery_app_name(self):
        assert celery_app.main == "smart_wifi_dashboard"

    def test_broker_url_uses_redis(self):
        assert "redis://" in celery_app.conf.broker_url

    def test_result_backend_uses_redis(self):
        assert "redis://" in celery_app.conf.result_backend

    def test_broker_and_backend_use_different_databases(self):
        # Broker uses db 1, backend uses db 2
        assert celery_app.conf.broker_url != celery_app.conf.result_backend

    def test_task_serializer_is_json(self):
        assert celery_app.conf.task_serializer == "json"

    def test_result_serializer_is_json(self):
        assert celery_app.conf.result_serializer == "json"

    def test_accept_content_is_json_only(self):
        assert celery_app.conf.accept_content == ["json"]

    def test_result_expires_one_hour(self):
        assert celery_app.conf.result_expires == 3600

    def test_default_queue(self):
        assert celery_app.conf.task_default_queue == "default"

    def test_task_routes_reports_queue(self):
        routes = celery_app.conf.task_routes
        assert "reports.*" in routes
        assert routes["reports.*"]["queue"] == "reports"

    def test_task_routes_ai_analysis_queue(self):
        routes = celery_app.conf.task_routes
        assert "ai.*" in routes
        assert routes["ai.*"]["queue"] == "ai_analysis"

    def test_utc_enabled(self):
        assert celery_app.conf.enable_utc is True
        assert celery_app.conf.timezone == "UTC"

    def test_worker_concurrency_set(self):
        assert celery_app.conf.worker_concurrency == 4

    def test_task_acks_late_enabled(self):
        assert celery_app.conf.task_acks_late is True

    def test_task_track_started_enabled(self):
        assert celery_app.conf.task_track_started is True


class TestBaseTask:
    """Tests for the base task class with retry logic."""

    def test_base_task_is_abstract(self):
        assert BaseTask.abstract is True

    def test_base_task_inherits_from_celery_task(self):
        assert issubclass(BaseTask, Task)

    def test_max_retries_is_three(self):
        assert BaseTask.max_retries == MAX_RETRIES
        assert BaseTask.max_retries == 3

    def test_retry_backoff_is_exponential(self):
        assert BaseTask.retry_backoff == RETRY_BACKOFF
        assert BaseTask.retry_backoff == 2

    def test_retry_backoff_max(self):
        assert BaseTask.retry_backoff_max == RETRY_BACKOFF_MAX
        assert BaseTask.retry_backoff_max == 60

    def test_retry_jitter_enabled(self):
        assert BaseTask.retry_jitter is True

    def test_autoretry_for_exceptions(self):
        assert BaseTask.autoretry_for == (Exception,)


class TestBaseTaskLifecycleHooks:
    """Tests for BaseTask lifecycle hook methods."""

    def test_on_retry_logs_warning(self, caplog):
        """Verify on_retry logs a warning with task details."""
        import logging

        task = BaseTask()
        task.name = "test.task"

        # Mock the request object since it's not available outside task execution
        mock_request = type("MockRequest", (), {"retries": 1})()
        with patch.object(type(task), "request", new_callable=lambda: property(lambda self: mock_request)):
            with caplog.at_level(logging.WARNING):
                task.on_retry(
                    exc=ValueError("test error"),
                    task_id="abc-123",
                    args=(),
                    kwargs={},
                    einfo=None,
                )

        assert "test.task" in caplog.text
        assert "abc-123" in caplog.text
        assert "test error" in caplog.text

    def test_on_failure_logs_error(self, caplog):
        """Verify on_failure logs an error with task details."""
        import logging

        task = BaseTask()
        task.name = "test.task"

        with caplog.at_level(logging.ERROR):
            task.on_failure(
                exc=RuntimeError("permanent failure"),
                task_id="def-456",
                args=(),
                kwargs={},
                einfo=None,
            )

        assert "test.task" in caplog.text
        assert "def-456" in caplog.text
        assert "permanent failure" in caplog.text

    def test_on_success_logs_info(self, caplog):
        """Verify on_success logs an info message."""
        import logging

        task = BaseTask()
        task.name = "test.task"

        with caplog.at_level(logging.INFO):
            task.on_success(
                retval={"status": "done"},
                task_id="ghi-789",
                args=(),
                kwargs={},
            )

        assert "test.task" in caplog.text
        assert "ghi-789" in caplog.text
        assert "completed successfully" in caplog.text

    def test_before_start_logs_info(self, caplog):
        """Verify before_start logs an info message."""
        import logging

        task = BaseTask()
        task.name = "test.task"

        with caplog.at_level(logging.INFO):
            task.before_start(
                task_id="jkl-012",
                args=(),
                kwargs={},
            )

        assert "test.task" in caplog.text
        assert "jkl-012" in caplog.text
        assert "starting" in caplog.text


class TestTaskRouting:
    """Tests for task routing to correct queues."""

    def test_report_task_routes_to_reports_queue(self):
        """Tasks named reports.* should route to the reports queue."""
        router = celery_app.amqp.router
        route = router.route({}, "reports.generate_pdf", args=(), kwargs={})
        assert route["queue"].name == "reports"

    def test_ai_task_routes_to_ai_analysis_queue(self):
        """Tasks named ai.* should route to the ai_analysis queue."""
        router = celery_app.amqp.router
        route = router.route({}, "ai.analyze_traffic", args=(), kwargs={})
        assert route["queue"].name == "ai_analysis"

    def test_default_task_routes_to_default_queue(self):
        """Tasks without a matching route should go to the default queue."""
        router = celery_app.amqp.router
        route = router.route({}, "misc.cleanup", args=(), kwargs={})
        assert route["queue"].name == "default"
