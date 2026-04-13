"""Three-state circuit breaker.

Wraps outbound calls (typically httpx to external APIs — SAM, OIG,
payment rails, insurance APIs) so that a failing upstream doesn't
consume worker threads or pile up timeouts while the downstream is
obviously dead.

States::

    CLOSED      — normal operation. Calls pass through. Consecutive
                  failures are counted; once failure_threshold is hit
                  the breaker transitions to OPEN.
    OPEN        — every call raises CircuitOpenError *immediately*
                  (zero network round-trip) until recovery_timeout has
                  elapsed, at which point we transition to HALF_OPEN.
    HALF_OPEN   — exactly one call is admitted as a probe. On success
                  the breaker goes CLOSED and the failure count resets.
                  On failure the breaker returns to OPEN and the
                  recovery timer restarts.

Fail-fast behavior is the point — better to return 503 to one client in
50ms than queue 100 clients waiting 30s each for a socket timeout.

Thread safety: a single ``threading.Lock`` protects state transitions
and counters. The call itself happens OUTSIDE the lock so a slow
upstream doesn't block the breaker for other threads.

This is sync-only by design (covers httpx.Client). An async variant
would clone the class with ``asyncio.Lock`` and ``await func(...)``;
we'll add it when the first async caller needs it (YAGNI).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypeVar

__all__ = ["CircuitBreaker", "CircuitOpenError", "CircuitState"]

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised immediately when the breaker is OPEN.

    Carries ``service`` (the breaker's name) and ``retry_after`` (seconds
    until the next HALF_OPEN probe). Middleware/handlers can translate
    this into a 503 with a ``Retry-After`` header.
    """

    def __init__(self, service: str, retry_after: float) -> None:
        super().__init__(f"circuit '{service}' is open; retry_after={retry_after:.2f}s")
        self.service = service
        self.retry_after = retry_after


@dataclass
class _Stats:
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    opened_at: float | None = None
    total_calls: int = 0
    total_failures: int = 0
    total_short_circuits: int = 0


class CircuitBreaker:
    """Three-state breaker around a sync callable.

    Args:
        name: Human-readable identifier for logs / errors (e.g., "oig-api").
        failure_threshold: How many consecutive failures trip CLOSED→OPEN.
        recovery_timeout: Seconds to wait before OPEN→HALF_OPEN probe.
        expected_exceptions: Exception types that count as a failure.
            Defaults to any ``Exception`` — tune this to avoid treating
            e.g. ``ValidationError`` (a 4xx-equivalent caller bug) as a
            breaker failure.
    """

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be > 0")
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        self._state = CircuitState.CLOSED
        self._stats = _Stats()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        # Read under lock to get a consistent snapshot after any lazy
        # transition triggered by time.
        with self._lock:
            self._maybe_transition_open_to_half_open()
            return self._state

    @property
    def stats(self) -> _Stats:
        with self._lock:
            # Return a copy so callers can't mutate internals.
            return _Stats(**self._stats.__dict__)

    # ------------------------------------------------------------------
    # Core call path
    # ------------------------------------------------------------------

    def call(self, func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        """Invoke *func(\\*args, \\*\\*kwargs)* through the breaker.

        Raises:
            CircuitOpenError: If the breaker is OPEN (and hasn't yet
                elapsed into HALF_OPEN).
            Any exception raised by *func* (re-raised after counting).
        """
        with self._lock:
            self._stats.total_calls += 1
            self._maybe_transition_open_to_half_open()
            if self._state is CircuitState.OPEN:
                self._stats.total_short_circuits += 1
                retry_after = self._retry_after_seconds_locked()
                raise CircuitOpenError(self.name, retry_after)

        # Execute OUTSIDE the lock so slow calls don't block other
        # threads from seeing state.
        try:
            result = func(*args, **kwargs)
        except self.expected_exceptions as exc:
            self._record_failure()
            raise
        else:
            self._record_success()
            return result

    # Convenience: call as `breaker(func, *args, **kwargs)`
    __call__ = call

    # ------------------------------------------------------------------
    # Test / operational hooks
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Force state back to CLOSED with fresh counters."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._stats = _Stats()

    # ------------------------------------------------------------------
    # Internals — all callers must hold the lock when invoking these
    # ------------------------------------------------------------------

    def _maybe_transition_open_to_half_open(self) -> None:
        if self._state is not CircuitState.OPEN:
            return
        opened_at = self._stats.opened_at
        if opened_at is None:
            return
        if time.monotonic() - opened_at >= self.recovery_timeout:
            self._state = CircuitState.HALF_OPEN

    def _retry_after_seconds_locked(self) -> float:
        opened_at = self._stats.opened_at
        if opened_at is None:
            return 0.0
        remaining = self.recovery_timeout - (time.monotonic() - opened_at)
        return max(remaining, 0.0)

    def _record_failure(self) -> None:
        with self._lock:
            self._stats.total_failures += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            if self._state is CircuitState.HALF_OPEN:
                # Probe failed → back to OPEN, reset the timer.
                self._state = CircuitState.OPEN
                self._stats.opened_at = time.monotonic()
            elif (
                self._state is CircuitState.CLOSED
                and self._stats.consecutive_failures >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                self._stats.opened_at = time.monotonic()

    def _record_success(self) -> None:
        with self._lock:
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            if self._state is CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._stats.opened_at = None
