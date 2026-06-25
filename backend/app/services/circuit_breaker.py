"""Circuit breaker pattern for MikroTik router communication.

Implements a state machine (Closed, Open, Half-Open) that protects the system
from cascade failures when the MikroTik router becomes unresponsive. Tracks
consecutive failures within a sliding window and transitions states accordingly.

State transitions:
- CLOSED → OPEN: 5 consecutive failures within 60 seconds
- OPEN → HALF_OPEN: After 30-second recovery timeout
- HALF_OPEN → CLOSED: Probe command succeeds
- HALF_OPEN → OPEN: Probe command fails

Emits state change events for WebSocket broadcasting via optional callback.

Requirements: 12.4, 12.7, 12.8
"""

import logging
import time
from enum import Enum
from typing import Any, Callable

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker with failure counting and automatic recovery.

    Tracks consecutive failures within a sliding time window. When the failure
    threshold is reached, the circuit opens and rejects all requests. After a
    recovery timeout, the circuit transitions to half-open and allows a single
    probe command to test connectivity.

    Attributes:
        state: Current circuit breaker state.
        failure_threshold: Number of failures to trigger open state.
        failure_window: Time window in seconds for counting failures.
        recovery_timeout: Seconds to wait before transitioning to half-open.
    """

    def __init__(
        self,
        failure_threshold: int | None = None,
        failure_window: int | None = None,
        recovery_timeout: int | None = None,
        on_state_change: Callable[[CircuitBreakerState, CircuitBreakerState, float | None], Any] | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures to open circuit.
                Defaults to settings.circuit_breaker_failure_threshold (5).
            failure_window: Time window in seconds for failure counting.
                Defaults to settings.circuit_breaker_failure_window (60).
            recovery_timeout: Seconds before transitioning from OPEN to HALF_OPEN.
                Defaults to settings.circuit_breaker_recovery_timeout (30).
            on_state_change: Optional callback invoked on state transitions.
                Called with (old_state, new_state, estimated_recovery_seconds).
        """
        settings = get_settings()
        self._failure_threshold = failure_threshold or settings.circuit_breaker_failure_threshold
        self._failure_window = failure_window or settings.circuit_breaker_failure_window
        self._recovery_timeout = recovery_timeout or settings.circuit_breaker_recovery_timeout
        self._on_state_change = on_state_change

        self._state = CircuitBreakerState.CLOSED
        self._failure_timestamps: list[float] = []
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitBreakerState:
        """Current circuit breaker state.

        Automatically transitions from OPEN to HALF_OPEN when the recovery
        timeout has elapsed.
        """
        if self._state == CircuitBreakerState.OPEN:
            if self._opened_at is not None:
                elapsed = time.time() - self._opened_at
                if elapsed >= self._recovery_timeout:
                    self._transition_to(CircuitBreakerState.HALF_OPEN)
        return self._state

    @property
    def failure_threshold(self) -> int:
        """Number of failures required to open the circuit."""
        return self._failure_threshold

    @property
    def failure_window(self) -> int:
        """Time window in seconds for counting failures."""
        return self._failure_window

    @property
    def recovery_timeout(self) -> int:
        """Seconds to wait before transitioning from OPEN to HALF_OPEN."""
        return self._recovery_timeout

    @property
    def failure_count(self) -> int:
        """Current number of failures within the sliding window."""
        self._prune_expired_failures()
        return len(self._failure_timestamps)

    def record_failure(self) -> None:
        """Record a failure and potentially transition to OPEN state.

        Adds the current timestamp to the failure window. If the number of
        failures within the window reaches the threshold, transitions to OPEN.
        If already in HALF_OPEN state, transitions back to OPEN (probe failed).
        """
        now = time.time()

        if self._state == CircuitBreakerState.HALF_OPEN:
            # Probe failed — re-open the circuit
            logger.warning(
                "Circuit breaker probe failed. Re-opening circuit. "
                "Next probe in %ds.",
                self._recovery_timeout,
            )
            self._failure_timestamps = [now]
            self._transition_to(CircuitBreakerState.OPEN)
            self._opened_at = now
            return

        if self._state == CircuitBreakerState.CLOSED:
            self._failure_timestamps.append(now)
            self._prune_expired_failures()

            if len(self._failure_timestamps) >= self._failure_threshold:
                logger.warning(
                    "Circuit breaker threshold reached (%d failures in %ds). "
                    "Opening circuit. Recovery in %ds.",
                    self._failure_threshold,
                    self._failure_window,
                    self._recovery_timeout,
                )
                self._transition_to(CircuitBreakerState.OPEN)
                self._opened_at = now

    def record_success(self) -> None:
        """Record a success and potentially transition to CLOSED state.

        If in HALF_OPEN state, the probe succeeded — close the circuit.
        If in CLOSED state, resets the failure counter.
        """
        if self._state == CircuitBreakerState.HALF_OPEN:
            logger.info("Circuit breaker probe succeeded. Closing circuit.")
            self._failure_timestamps.clear()
            self._opened_at = None
            self._transition_to(CircuitBreakerState.CLOSED)
        elif self._state == CircuitBreakerState.CLOSED:
            # Success in closed state resets failure counter
            self._failure_timestamps.clear()

    def can_execute(self) -> bool:
        """Check if a command can be executed.

        Returns True if the circuit is CLOSED or HALF_OPEN (allowing a probe).
        Returns False if the circuit is OPEN (rejecting all commands).

        Note: Accessing this property may trigger OPEN → HALF_OPEN transition
        if the recovery timeout has elapsed.
        """
        current_state = self.state  # triggers auto-transition check
        return current_state in (CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN)

    def get_estimated_recovery_time(self) -> float:
        """Get estimated seconds until the next probe attempt.

        Returns:
            Seconds remaining until HALF_OPEN transition if OPEN.
            0.0 if already CLOSED or HALF_OPEN.
        """
        if self._state == CircuitBreakerState.OPEN and self._opened_at is not None:
            elapsed = time.time() - self._opened_at
            remaining = self._recovery_timeout - elapsed
            return max(0.0, remaining)
        return 0.0

    def reset(self) -> None:
        """Reset the circuit breaker to CLOSED state.

        Clears all failure history and timers. Useful for manual recovery
        or testing.
        """
        old_state = self._state
        self._state = CircuitBreakerState.CLOSED
        self._failure_timestamps.clear()
        self._opened_at = None
        if old_state != CircuitBreakerState.CLOSED:
            self._emit_state_change(old_state, CircuitBreakerState.CLOSED)

    def _transition_to(self, new_state: CircuitBreakerState) -> None:
        """Transition to a new state and emit change event."""
        old_state = self._state
        if old_state == new_state:
            return
        self._state = new_state
        self._emit_state_change(old_state, new_state)

    def _emit_state_change(
        self, old_state: CircuitBreakerState, new_state: CircuitBreakerState
    ) -> None:
        """Emit state change event for WebSocket broadcasting."""
        estimated_recovery = self.get_estimated_recovery_time()
        logger.info(
            "Circuit breaker state change: %s → %s (recovery in %.1fs)",
            old_state.value,
            new_state.value,
            estimated_recovery,
        )
        if self._on_state_change is not None:
            try:
                self._on_state_change(old_state, new_state, estimated_recovery)
            except Exception as exc:
                logger.error(
                    "Error in circuit breaker state change callback: %s", exc
                )

    def _prune_expired_failures(self) -> None:
        """Remove failure timestamps outside the sliding window."""
        cutoff = time.time() - self._failure_window
        self._failure_timestamps = [
            ts for ts in self._failure_timestamps if ts > cutoff
        ]


class TenantCircuitBreaker:
    """Manages per-tenant circuit breakers.

    Each tenant has an independent circuit breaker instance that tracks
    failures for their specific MikroTik router connection.
    """

    def __init__(
        self,
        failure_threshold: int | None = None,
        failure_window: int | None = None,
        recovery_timeout: int | None = None,
        on_state_change: Callable[[str, CircuitBreakerState, CircuitBreakerState, float | None], Any] | None = None,
    ) -> None:
        """Initialize tenant circuit breaker manager.

        Args:
            failure_threshold: Number of consecutive failures to open circuit.
            failure_window: Time window in seconds for failure counting.
            recovery_timeout: Seconds before transitioning from OPEN to HALF_OPEN.
            on_state_change: Optional callback invoked on state transitions.
                Called with (tenant_id, old_state, new_state, estimated_recovery_seconds).
        """
        self._failure_threshold = failure_threshold
        self._failure_window = failure_window
        self._recovery_timeout = recovery_timeout
        self._on_state_change = on_state_change
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_breaker(self, tenant_id: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            The circuit breaker instance for the specified tenant.
        """
        if tenant_id not in self._breakers:
            # Create a tenant-scoped callback wrapper
            tenant_callback = None
            if self._on_state_change is not None:
                def tenant_callback(
                    old_state: CircuitBreakerState,
                    new_state: CircuitBreakerState,
                    estimated_recovery: float | None,
                    _tenant_id: str = tenant_id,
                ) -> None:
                    self._on_state_change(_tenant_id, old_state, new_state, estimated_recovery)

            self._breakers[tenant_id] = CircuitBreaker(
                failure_threshold=self._failure_threshold,
                failure_window=self._failure_window,
                recovery_timeout=self._recovery_timeout,
                on_state_change=tenant_callback,
            )
        return self._breakers[tenant_id]

    def record_failure(self, tenant_id: str) -> None:
        """Record a failure for a tenant's circuit breaker."""
        self.get_breaker(tenant_id).record_failure()

    def record_success(self, tenant_id: str) -> None:
        """Record a success for a tenant's circuit breaker."""
        self.get_breaker(tenant_id).record_success()

    def can_execute(self, tenant_id: str) -> bool:
        """Check if a command can be executed for a tenant."""
        return self.get_breaker(tenant_id).can_execute()

    def get_state(self, tenant_id: str) -> CircuitBreakerState:
        """Get the current state of a tenant's circuit breaker."""
        return self.get_breaker(tenant_id).state

    def get_estimated_recovery_time(self, tenant_id: str) -> float:
        """Get estimated recovery time for a tenant's circuit breaker."""
        return self.get_breaker(tenant_id).get_estimated_recovery_time()

    def reset(self, tenant_id: str) -> None:
        """Reset a tenant's circuit breaker to CLOSED state."""
        if tenant_id in self._breakers:
            self._breakers[tenant_id].reset()

    def reset_all(self) -> None:
        """Reset all tenant circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()
        self._breakers.clear()

    @property
    def active_tenants(self) -> list[str]:
        """List of tenant IDs with active circuit breakers."""
        return list(self._breakers.keys())
