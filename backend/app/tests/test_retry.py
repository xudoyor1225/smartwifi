"""Tests for the retry utility with exponential backoff.

Covers:
- Successful execution on first try (no retries)
- Success after 1 retry
- Success after 2 retries
- Failure after all 3 retries (raises RetryExhaustedError)
- Correct backoff timing (1s, 2s, 4s)
- Logging of retry attempts
- Failure callback invocation
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.retry import (
    RetryAttempt,
    RetryConfig,
    RetryExhaustedError,
    with_retry,
)


class TestSuccessfulExecution:
    """Tests for functions that succeed without needing retries."""

    async def test_success_on_first_try(self):
        """Function that succeeds immediately should return without retries."""
        call_count = 0

        @with_retry(max_retries=3)
        async def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await succeed()
        assert result == "ok"
        assert call_count == 1

    async def test_returns_correct_value(self):
        """Decorated function should return the original return value."""

        @with_retry(max_retries=3)
        async def compute(x: int, y: int):
            return x + y

        result = await compute(3, 7)
        assert result == 10

    async def test_passes_args_and_kwargs(self):
        """Decorator should forward all positional and keyword arguments."""
        received_args = []
        received_kwargs = {}

        @with_retry(max_retries=3)
        async def capture(*args, **kwargs):
            received_args.extend(args)
            received_kwargs.update(kwargs)
            return "done"

        await capture("a", "b", key="value")
        assert received_args == ["a", "b"]
        assert received_kwargs == {"key": "value"}


class TestRetryOnFailure:
    """Tests for functions that fail then succeed."""

    async def test_success_after_1_retry(self):
        """Function that fails once then succeeds should return on second attempt."""
        call_count = 0

        @with_retry(max_retries=3, backoff_base=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("connection refused")
            return "recovered"

        result = await flaky()
        assert result == "recovered"
        assert call_count == 2

    async def test_success_after_2_retries(self):
        """Function that fails twice then succeeds should return on third attempt."""
        call_count = 0

        @with_retry(max_retries=3, backoff_base=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timed out")
            return "recovered"

        result = await flaky()
        assert result == "recovered"
        assert call_count == 3

    async def test_success_after_3_retries(self):
        """Function that fails 3 times then succeeds on the 4th attempt."""
        call_count = 0

        @with_retry(max_retries=3, backoff_base=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ConnectionError("refused")
            return "finally"

        result = await flaky()
        assert result == "finally"
        assert call_count == 4


class TestRetryExhausted:
    """Tests for functions that fail after all retry attempts."""

    async def test_raises_retry_exhausted_error(self):
        """Should raise RetryExhaustedError after all retries are exhausted."""

        @with_retry(max_retries=3, backoff_base=0.01)
        async def always_fail():
            raise ConnectionError("connection refused")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await always_fail()

        err = exc_info.value
        assert isinstance(err.original_error, ConnectionError)
        assert "connection refused" in str(err.original_error)
        assert err.function_name == "always_fail"

    async def test_retry_history_has_correct_count(self):
        """Retry history should contain one entry per attempt (initial + retries)."""

        @with_retry(max_retries=3, backoff_base=0.01)
        async def always_fail():
            raise ValueError("bad value")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await always_fail()

        err = exc_info.value
        # 1 initial attempt + 3 retries = 4 total attempts
        assert len(err.retry_history) == 4

    async def test_retry_history_records_details(self):
        """Each retry attempt should record attempt number, timestamp, and error info."""

        @with_retry(max_retries=2, backoff_base=0.01)
        async def always_fail():
            raise RuntimeError("something broke")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await always_fail()

        err = exc_info.value
        for i, attempt in enumerate(err.retry_history):
            assert attempt.attempt_number == i + 1
            assert attempt.timestamp > 0
            assert attempt.error_message == "something broke"
            assert attempt.error_type == "RuntimeError"

    async def test_only_catches_specified_exceptions(self):
        """Should not retry on exceptions not in retryable_exceptions."""

        @with_retry(
            max_retries=3,
            backoff_base=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def raise_value_error():
            raise ValueError("not retryable")

        # ValueError should propagate immediately, not wrapped in RetryExhaustedError
        with pytest.raises(ValueError, match="not retryable"):
            await raise_value_error()


class TestBackoffTiming:
    """Tests for correct exponential backoff delays."""

    async def test_backoff_delays_are_correct(self):
        """Backoff should follow pattern: base * multiplier^attempt (1s, 2s, 4s)."""

        @with_retry(max_retries=3, backoff_base=1.0, backoff_multiplier=2.0)
        async def always_fail():
            raise ConnectionError("refused")

        with patch("app.services.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RetryExhaustedError):
                await always_fail()

            # Should have slept 3 times (after attempts 1, 2, 3 — not after the last)
            assert mock_sleep.call_count == 3
            delays = [call.args[0] for call in mock_sleep.call_args_list]
            assert delays == [1.0, 2.0, 4.0]

    async def test_custom_backoff_parameters(self):
        """Custom base and multiplier should produce correct delays."""

        @with_retry(max_retries=3, backoff_base=0.5, backoff_multiplier=3.0)
        async def always_fail():
            raise ConnectionError("refused")

        with patch("app.services.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RetryExhaustedError):
                await always_fail()

            delays = [call.args[0] for call in mock_sleep.call_args_list]
            # 0.5 * 3^0 = 0.5, 0.5 * 3^1 = 1.5, 0.5 * 3^2 = 4.5
            assert delays == [0.5, 1.5, 4.5]

    async def test_no_sleep_on_immediate_success(self):
        """No sleep should occur when the function succeeds on first try."""

        @with_retry(max_retries=3, backoff_base=1.0)
        async def succeed():
            return "ok"

        with patch("app.services.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await succeed()
            mock_sleep.assert_not_called()


class TestLogging:
    """Tests for retry attempt logging."""

    async def test_logs_each_retry_attempt(self):
        """Each retry attempt should be logged with function name, attempt number, and error."""
        call_count = 0

        @with_retry(max_retries=3, backoff_base=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("connection refused")
            return "ok"

        with patch("app.services.retry.logger") as mock_logger:
            await flaky()

            # Should have logged 2 retry warnings (attempts 1 and 2 failed)
            assert mock_logger.warning.call_count == 2

            # Verify first log message contains expected info
            first_call_args = mock_logger.warning.call_args_list[0]
            log_msg = first_call_args[0][0] % first_call_args[0][1:]
            assert "flaky" in log_msg
            assert "1/3" in log_msg
            assert "connection refused" in log_msg

    async def test_logs_all_attempts_on_exhaustion(self):
        """All retry attempts should be logged when retries are exhausted."""

        @with_retry(max_retries=3, backoff_base=0.01)
        async def always_fail():
            raise TimeoutError("timed out")

        with patch("app.services.retry.logger") as mock_logger:
            with pytest.raises(RetryExhaustedError):
                await always_fail()

            # 3 warnings for the first 3 failures (the 4th failure doesn't log
            # because it raises immediately)
            assert mock_logger.warning.call_count == 3


class TestFailureCallback:
    """Tests for the on_failure callback (circuit breaker integration)."""

    async def test_callback_invoked_on_each_failure(self):
        """Failure callback should be called once per failed attempt."""
        callback = MagicMock()
        call_count = 0

        @with_retry(max_retries=3, backoff_base=0.01, on_failure=callback)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("refused")
            return "ok"

        await flaky()

        # Callback should have been called for each of the 2 failures
        assert callback.call_count == 2
        # Each call should receive the exception instance
        for call in callback.call_args_list:
            assert isinstance(call[0][0], ConnectionError)

    async def test_callback_invoked_on_all_failures_when_exhausted(self):
        """Callback should be called for every failure including the final one."""
        callback = MagicMock()

        @with_retry(max_retries=3, backoff_base=0.01, on_failure=callback)
        async def always_fail():
            raise TimeoutError("timed out")

        with pytest.raises(RetryExhaustedError):
            await always_fail()

        # 1 initial + 3 retries = 4 total failures
        assert callback.call_count == 4
        for call in callback.call_args_list:
            assert isinstance(call[0][0], TimeoutError)

    async def test_no_callback_on_success(self):
        """Callback should not be called when the function succeeds."""
        callback = MagicMock()

        @with_retry(max_retries=3, backoff_base=0.01, on_failure=callback)
        async def succeed():
            return "ok"

        await succeed()
        callback.assert_not_called()

    async def test_callback_receives_correct_exception_type(self):
        """Callback should receive the actual exception that was raised."""
        received_errors = []

        def track_error(exc):
            received_errors.append(exc)

        call_count = 0

        @with_retry(
            max_retries=3,
            backoff_base=0.01,
            retryable_exceptions=(ConnectionError, TimeoutError),
            on_failure=track_error,
        )
        async def mixed_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("conn error")
            if call_count == 2:
                raise TimeoutError("timeout")
            return "ok"

        await mixed_errors()

        assert len(received_errors) == 2
        assert isinstance(received_errors[0], ConnectionError)
        assert isinstance(received_errors[1], TimeoutError)


class TestRetryConfig:
    """Tests for the RetryConfig dataclass."""

    def test_default_values(self):
        """RetryConfig should have sensible defaults."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.backoff_base == 1.0
        assert config.backoff_multiplier == 2.0
        assert config.retryable_exceptions == (Exception,)
        assert config.on_failure is None

    def test_custom_values(self):
        """RetryConfig should accept custom values."""
        callback = MagicMock()
        config = RetryConfig(
            max_retries=5,
            backoff_base=2.0,
            backoff_multiplier=3.0,
            retryable_exceptions=(ConnectionError, TimeoutError),
            on_failure=callback,
        )
        assert config.max_retries == 5
        assert config.backoff_base == 2.0
        assert config.backoff_multiplier == 3.0
        assert config.retryable_exceptions == (ConnectionError, TimeoutError)
        assert config.on_failure is callback


class TestRetryExhaustedErrorDetails:
    """Tests for RetryExhaustedError attributes and message."""

    def test_error_message_format(self):
        """Error message should include function name and attempt count."""
        history = [
            RetryAttempt(1, time.time(), "err1", "ConnectionError"),
            RetryAttempt(2, time.time(), "err2", "ConnectionError"),
        ]
        original = ConnectionError("final error")
        err = RetryExhaustedError(original, history, "my_function")

        assert "my_function" in str(err)
        assert "2 retry attempt(s)" in str(err)
        assert "final error" in str(err)

    def test_preserves_original_error(self):
        """Should preserve the original exception for re-raising or inspection."""
        original = TimeoutError("timed out")
        err = RetryExhaustedError(original, [], "func")
        assert err.original_error is original

    def test_preserves_retry_history(self):
        """Should preserve the full retry history."""
        history = [
            RetryAttempt(1, 1000.0, "err1", "ConnectionError"),
            RetryAttempt(2, 1001.0, "err2", "TimeoutError"),
        ]
        err = RetryExhaustedError(ConnectionError("x"), history, "func")
        assert err.retry_history == history
        assert len(err.retry_history) == 2
