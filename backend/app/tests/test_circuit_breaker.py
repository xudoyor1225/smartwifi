"""Tests for the circuit breaker pattern implementation.

Covers:
- State transitions: CLOSED → OPEN → HALF_OPEN → CLOSED
- Failure counting within sliding window
- Automatic recovery after timeout
- Probe success/failure behavior
- State change event emission
- Tenant circuit breaker management
- Sliding window expiry (failures outside window are pruned)

Requirements: 12.4, 12.7, 12.8
"""

import time
from unittest.mock import MagicMock


from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    TenantCircuitBreaker,
)


class TestCircuitBreakerInitialState:
    """Tests for circuit breaker initial state."""

    def test_starts_in_closed_state(self):
        """Circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)
        assert cb.state == CircuitBreakerState.CLOSED

    def test_can_execute_when_closed(self):
        """Should allow execution when in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)
        assert cb.can_execute() is True

    def test_initial_failure_count_is_zero(self):
        """Failure count should be zero initially."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)
        assert cb.failure_count == 0

    def test_initial_recovery_time_is_zero(self):
        """Estimated recovery time should be 0 when CLOSED."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)
        assert cb.get_estimated_recovery_time() == 0.0


class TestClosedToOpenTransition:
    """Tests for CLOSED → OPEN state transition."""

    def test_opens_after_threshold_failures(self):
        """Circuit should open after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(5):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN

    def test_stays_closed_below_threshold(self):
        """Circuit should remain closed below failure threshold."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(4):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.CLOSED

    def test_cannot_execute_when_open(self):
        """Should reject execution when in OPEN state."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(5):
            cb.record_failure()

        assert cb.can_execute() is False

    def test_recovery_time_after_opening(self):
        """Should report recovery time after opening."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(5):
            cb.record_failure()

        recovery = cb.get_estimated_recovery_time()
        assert 29.0 <= recovery <= 30.0


class TestSlidingWindowExpiry:
    """Tests for failure counter sliding window behavior."""

    def test_failures_outside_window_are_pruned(self):
        """Failures older than the window should not count toward threshold."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        # Simulate 4 failures that are old (outside the window)
        old_time = time.time() - 61  # 61 seconds ago
        cb._failure_timestamps = [old_time] * 4

        # Add 1 new failure — total within window should be 1, not 5
        cb.record_failure()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 1

    def test_failures_within_window_count(self):
        """All failures within the window should count toward threshold."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        # All failures are recent
        for _ in range(5):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN

    def test_mixed_old_and_new_failures(self):
        """Only recent failures should count; old ones are pruned."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        # 3 old failures
        old_time = time.time() - 61
        cb._failure_timestamps = [old_time] * 3

        # 4 new failures — only these count
        for _ in range(4):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 4


class TestOpenToHalfOpenTransition:
    """Tests for OPEN → HALF_OPEN state transition."""

    def test_transitions_to_half_open_after_timeout(self):
        """Circuit should transition to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(5):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN

        # Simulate time passing beyond recovery timeout
        cb._opened_at = time.time() - 31

        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_can_execute_when_half_open(self):
        """Should allow execution (probe) when in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(5):
            cb.record_failure()

        # Simulate timeout elapsed
        cb._opened_at = time.time() - 31

        assert cb.can_execute() is True

    def test_stays_open_before_timeout(self):
        """Circuit should remain OPEN before recovery timeout elapses."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(5):
            cb.record_failure()

        # Only 10 seconds have passed
        cb._opened_at = time.time() - 10

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False


class TestHalfOpenToClosedTransition:
    """Tests for HALF_OPEN → CLOSED state transition (probe success)."""

    def test_closes_on_probe_success(self):
        """Circuit should close when probe succeeds in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        # Open the circuit
        for _ in range(5):
            cb.record_failure()

        # Transition to HALF_OPEN
        cb._opened_at = time.time() - 31
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Probe succeeds
        cb.record_success()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.can_execute() is True

    def test_failure_count_resets_on_close(self):
        """Failure count should reset to 0 when circuit closes."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(5):
            cb.record_failure()

        cb._opened_at = time.time() - 31
        _ = cb.state  # trigger transition to HALF_OPEN

        cb.record_success()

        assert cb.failure_count == 0


class TestHalfOpenToOpenTransition:
    """Tests for HALF_OPEN → OPEN state transition (probe failure)."""

    def test_reopens_on_probe_failure(self):
        """Circuit should re-open when probe fails in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        # Open the circuit
        for _ in range(5):
            cb.record_failure()

        # Transition to HALF_OPEN
        cb._opened_at = time.time() - 31
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Probe fails
        cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False

    def test_recovery_time_resets_on_reopen(self):
        """Recovery timer should reset when circuit re-opens from HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(5):
            cb.record_failure()

        cb._opened_at = time.time() - 31
        _ = cb.state  # trigger HALF_OPEN

        cb.record_failure()  # probe fails, re-opens

        recovery = cb.get_estimated_recovery_time()
        assert 29.0 <= recovery <= 30.0


class TestSuccessInClosedState:
    """Tests for success recording in CLOSED state."""

    def test_success_resets_failure_counter(self):
        """Recording success in CLOSED state should reset failure counter."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        # Record some failures (below threshold)
        for _ in range(3):
            cb.record_failure()

        assert cb.failure_count == 3

        # Success resets the counter
        cb.record_success()

        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED


class TestStateChangeCallback:
    """Tests for state change event emission."""

    def test_callback_on_open(self):
        """Callback should be invoked when circuit opens."""
        callback = MagicMock()
        cb = CircuitBreaker(
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30,
            on_state_change=callback,
        )

        for _ in range(5):
            cb.record_failure()

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == CircuitBreakerState.CLOSED
        assert args[1] == CircuitBreakerState.OPEN

    def test_callback_on_half_open(self):
        """Callback should be invoked when circuit transitions to HALF_OPEN."""
        callback = MagicMock()
        cb = CircuitBreaker(
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30,
            on_state_change=callback,
        )

        for _ in range(5):
            cb.record_failure()

        callback.reset_mock()

        # Trigger HALF_OPEN transition
        cb._opened_at = time.time() - 31
        _ = cb.state

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == CircuitBreakerState.OPEN
        assert args[1] == CircuitBreakerState.HALF_OPEN

    def test_callback_on_close(self):
        """Callback should be invoked when circuit closes."""
        callback = MagicMock()
        cb = CircuitBreaker(
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30,
            on_state_change=callback,
        )

        for _ in range(5):
            cb.record_failure()

        cb._opened_at = time.time() - 31
        _ = cb.state  # HALF_OPEN

        callback.reset_mock()
        cb.record_success()

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == CircuitBreakerState.HALF_OPEN
        assert args[1] == CircuitBreakerState.CLOSED

    def test_callback_on_reopen(self):
        """Callback should be invoked when circuit re-opens from HALF_OPEN."""
        callback = MagicMock()
        cb = CircuitBreaker(
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30,
            on_state_change=callback,
        )

        for _ in range(5):
            cb.record_failure()

        cb._opened_at = time.time() - 31
        _ = cb.state  # HALF_OPEN

        callback.reset_mock()
        cb.record_failure()  # probe fails

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == CircuitBreakerState.HALF_OPEN
        assert args[1] == CircuitBreakerState.OPEN

    def test_callback_exception_does_not_break_state(self):
        """Callback exceptions should not prevent state transitions."""
        callback = MagicMock(side_effect=RuntimeError("callback error"))
        cb = CircuitBreaker(
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30,
            on_state_change=callback,
        )

        for _ in range(5):
            cb.record_failure()

        # State should still transition despite callback error
        assert cb.state == CircuitBreakerState.OPEN

    def test_no_callback_when_none(self):
        """No error should occur when callback is None."""
        cb = CircuitBreaker(
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30,
            on_state_change=None,
        )

        for _ in range(5):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN


class TestReset:
    """Tests for manual circuit breaker reset."""

    def test_reset_from_open(self):
        """Reset should return circuit to CLOSED from OPEN."""
        cb = CircuitBreaker(failure_threshold=5, failure_window=60, recovery_timeout=30)

        for _ in range(5):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN

        cb.reset()

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.can_execute() is True

    def test_reset_emits_state_change(self):
        """Reset should emit state change event."""
        callback = MagicMock()
        cb = CircuitBreaker(
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30,
            on_state_change=callback,
        )

        for _ in range(5):
            cb.record_failure()

        callback.reset_mock()
        cb.reset()

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == CircuitBreakerState.OPEN
        assert args[1] == CircuitBreakerState.CLOSED


class TestTenantCircuitBreaker:
    """Tests for per-tenant circuit breaker management."""

    def test_creates_breaker_per_tenant(self):
        """Each tenant should get an independent circuit breaker."""
        tcb = TenantCircuitBreaker(
            failure_threshold=5, failure_window=60, recovery_timeout=30
        )

        breaker_a = tcb.get_breaker("tenant-a")
        breaker_b = tcb.get_breaker("tenant-b")

        assert breaker_a is not breaker_b

    def test_returns_same_breaker_for_same_tenant(self):
        """Same tenant should always get the same circuit breaker instance."""
        tcb = TenantCircuitBreaker(
            failure_threshold=5, failure_window=60, recovery_timeout=30
        )

        breaker1 = tcb.get_breaker("tenant-a")
        breaker2 = tcb.get_breaker("tenant-a")

        assert breaker1 is breaker2

    def test_tenant_isolation(self):
        """Failures in one tenant should not affect another."""
        tcb = TenantCircuitBreaker(
            failure_threshold=5, failure_window=60, recovery_timeout=30
        )

        # Open circuit for tenant-a
        for _ in range(5):
            tcb.record_failure("tenant-a")

        assert tcb.can_execute("tenant-a") is False
        assert tcb.can_execute("tenant-b") is True

    def test_record_success_for_tenant(self):
        """Recording success should only affect the specified tenant."""
        tcb = TenantCircuitBreaker(
            failure_threshold=5, failure_window=60, recovery_timeout=30
        )

        # Add failures to both tenants
        for _ in range(3):
            tcb.record_failure("tenant-a")
            tcb.record_failure("tenant-b")

        tcb.record_success("tenant-a")

        assert tcb.get_breaker("tenant-a").failure_count == 0
        assert tcb.get_breaker("tenant-b").failure_count == 3

    def test_get_state_for_tenant(self):
        """Should return correct state for each tenant."""
        tcb = TenantCircuitBreaker(
            failure_threshold=5, failure_window=60, recovery_timeout=30
        )

        for _ in range(5):
            tcb.record_failure("tenant-a")

        assert tcb.get_state("tenant-a") == CircuitBreakerState.OPEN
        assert tcb.get_state("tenant-b") == CircuitBreakerState.CLOSED

    def test_get_estimated_recovery_time(self):
        """Should return recovery time for the specified tenant."""
        tcb = TenantCircuitBreaker(
            failure_threshold=5, failure_window=60, recovery_timeout=30
        )

        for _ in range(5):
            tcb.record_failure("tenant-a")

        recovery = tcb.get_estimated_recovery_time("tenant-a")
        assert 29.0 <= recovery <= 30.0
        assert tcb.get_estimated_recovery_time("tenant-b") == 0.0

    def test_reset_tenant(self):
        """Should reset only the specified tenant's circuit breaker."""
        tcb = TenantCircuitBreaker(
            failure_threshold=5, failure_window=60, recovery_timeout=30
        )

        for _ in range(5):
            tcb.record_failure("tenant-a")
            tcb.record_failure("tenant-b")

        tcb.reset("tenant-a")

        assert tcb.get_state("tenant-a") == CircuitBreakerState.CLOSED
        assert tcb.get_state("tenant-b") == CircuitBreakerState.OPEN

    def test_reset_all(self):
        """Should reset all tenant circuit breakers."""
        tcb = TenantCircuitBreaker(
            failure_threshold=5, failure_window=60, recovery_timeout=30
        )

        for _ in range(5):
            tcb.record_failure("tenant-a")
            tcb.record_failure("tenant-b")

        tcb.reset_all()

        assert tcb.active_tenants == []

    def test_active_tenants(self):
        """Should list all tenants with active circuit breakers."""
        tcb = TenantCircuitBreaker(
            failure_threshold=5, failure_window=60, recovery_timeout=30
        )

        tcb.get_breaker("tenant-a")
        tcb.get_breaker("tenant-b")
        tcb.get_breaker("tenant-c")

        assert sorted(tcb.active_tenants) == ["tenant-a", "tenant-b", "tenant-c"]

    def test_tenant_state_change_callback(self):
        """Tenant callback should include tenant_id."""
        callback = MagicMock()
        tcb = TenantCircuitBreaker(
            failure_threshold=5,
            failure_window=60,
            recovery_timeout=30,
            on_state_change=callback,
        )

        for _ in range(5):
            tcb.record_failure("tenant-x")

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == "tenant-x"
        assert args[1] == CircuitBreakerState.CLOSED
        assert args[2] == CircuitBreakerState.OPEN
