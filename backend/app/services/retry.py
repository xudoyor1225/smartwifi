"""Retry utility with exponential backoff for MikroTik router operations.

Provides an async retry decorator that catches specified exceptions and retries
with exponential backoff (1s, 2s, 4s by default). Integrates with the circuit
breaker failure counter and logs each retry attempt with timestamp and error details.

Requirements: 12.2, 12.3
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class RetryAttempt:
    """Record of a single retry attempt."""

    attempt_number: int
    timestamp: float
    error_message: str
    error_type: str


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts (default 3).
        backoff_base: Base delay in seconds for the first retry (default 1).
        backoff_multiplier: Multiplier applied to the delay for each subsequent retry (default 2).
        retryable_exceptions: Tuple of exception types to catch and retry on.
            Defaults to (Exception,) which catches all exceptions.
        on_failure: Optional callback invoked on each failure for circuit breaker integration.
            Called with the exception instance as its argument.
    """

    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_multiplier: float = 2.0
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,)
    on_failure: Callable[[BaseException], Any] | None = None


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted.

    Wraps the original exception and provides a history of all retry attempts
    for debugging and audit logging purposes.

    Attributes:
        original_error: The last exception that caused the final retry failure.
        retry_history: List of RetryAttempt records documenting each failed attempt.
        function_name: Name of the function that exhausted retries.
    """

    def __init__(
        self,
        original_error: BaseException,
        retry_history: list[RetryAttempt],
        function_name: str,
    ) -> None:
        self.original_error = original_error
        self.retry_history = retry_history
        self.function_name = function_name
        attempts = len(retry_history)
        super().__init__(
            f"Function '{function_name}' failed after {attempts} retry attempt(s). "
            f"Last error: {original_error}"
        )


def with_retry(
    max_retries: int = 3,
    backoff_base: float = 1.0,
    backoff_multiplier: float = 2.0,
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_failure: Callable[[BaseException], Any] | None = None,
) -> Callable:
    """Async retry decorator with exponential backoff.

    Retries the decorated async function on specified exceptions with
    exponential backoff delays: backoff_base * (backoff_multiplier ** attempt_index).

    Default timing: 1s after first failure, 2s after second, 4s after third.

    Args:
        max_retries: Maximum number of retry attempts (default 3).
        backoff_base: Base delay in seconds (default 1).
        backoff_multiplier: Multiplier for each subsequent delay (default 2).
        retryable_exceptions: Exception types to catch and retry on.
        on_failure: Optional callback for circuit breaker integration,
            called with the exception on each failure.

    Returns:
        Decorator that wraps an async function with retry logic.

    Example:
        @with_retry(max_retries=3, retryable_exceptions=(ConnectionError, TimeoutError))
        async def connect_to_router(ip: str):
            ...
    """

    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retry_history: list[RetryAttempt] = []
            last_error: BaseException | None = None

            # First attempt (attempt 0) + max_retries retries
            total_attempts = 1 + max_retries

            for attempt in range(total_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_error = exc
                    attempt_record = RetryAttempt(
                        attempt_number=attempt + 1,
                        timestamp=time.time(),
                        error_message=str(exc),
                        error_type=type(exc).__name__,
                    )
                    retry_history.append(attempt_record)

                    # Invoke failure callback for circuit breaker integration
                    if on_failure is not None:
                        on_failure(exc)

                    # If this was the last attempt, don't wait — raise immediately
                    if attempt >= max_retries:
                        break

                    # Calculate backoff delay: base * multiplier^attempt
                    delay = backoff_base * (backoff_multiplier ** attempt)

                    logger.warning(
                        "Retry attempt %d/%d for '%s': %s (%s). "
                        "Waiting %.1fs before next attempt. Timestamp: %s",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        str(exc),
                        type(exc).__name__,
                        delay,
                        time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(attempt_record.timestamp)),
                    )

                    await asyncio.sleep(delay)

            # All retries exhausted
            assert last_error is not None
            raise RetryExhaustedError(
                original_error=last_error,
                retry_history=retry_history,
                function_name=func.__name__,
            )

        return wrapper

    return decorator
