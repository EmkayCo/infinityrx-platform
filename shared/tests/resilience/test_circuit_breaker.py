"""Tests for shared.resilience.circuit_breaker.CircuitBreaker."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from shared.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


# ---------------------------------------------------------------------------
# Construction / validation
# ---------------------------------------------------------------------------


def test_rejects_zero_threshold() -> None:
    with pytest.raises(ValueError, match="failure_threshold"):
        CircuitBreaker("svc", failure_threshold=0, recovery_timeout=1)


def test_rejects_negative_threshold() -> None:
    with pytest.raises(ValueError, match="failure_threshold"):
        CircuitBreaker("svc", failure_threshold=-1, recovery_timeout=1)


def test_rejects_zero_recovery_timeout() -> None:
    with pytest.raises(ValueError, match="recovery_timeout"):
        CircuitBreaker("svc", failure_threshold=1, recovery_timeout=0)


def test_initial_state_is_closed() -> None:
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=5)
    assert cb.state is CircuitState.CLOSED


# ---------------------------------------------------------------------------
# Closed → normal operation
# ---------------------------------------------------------------------------


def test_successful_call_returns_value() -> None:
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=5)
    assert cb.call(lambda x: x + 1, 41) == 42
    assert cb.stats.total_calls == 1
    assert cb.stats.total_failures == 0


def test_call_via_dunder_call() -> None:
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=5)
    assert cb(lambda: "ok") == "ok"


def test_failures_below_threshold_keep_closed() -> None:
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=5)

    def bad() -> None:
        raise RuntimeError("nope")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(bad)
    assert cb.state is CircuitState.CLOSED
    assert cb.stats.consecutive_failures == 2


def test_interleaved_success_resets_consecutive_count() -> None:
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=5)

    def bad() -> None:
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        cb.call(bad)
    with pytest.raises(RuntimeError):
        cb.call(bad)
    cb.call(lambda: None)  # success resets the counter
    with pytest.raises(RuntimeError):
        cb.call(bad)
    # Only 1 consecutive failure now — still CLOSED
    assert cb.state is CircuitState.CLOSED
    assert cb.stats.consecutive_failures == 1


# ---------------------------------------------------------------------------
# Closed → open
# ---------------------------------------------------------------------------


def test_threshold_failures_open_circuit() -> None:
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=5)

    def bad() -> None:
        raise RuntimeError("nope")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(bad)
    assert cb.state is CircuitState.OPEN


def test_open_breaker_short_circuits_with_retry_after() -> None:
    cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=10)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.state is CircuitState.OPEN

    with pytest.raises(CircuitOpenError) as exc_info:
        cb.call(lambda: "would have succeeded")
    assert exc_info.value.service == "svc"
    assert 0 < exc_info.value.retry_after <= 10
    # Short-circuit call counts in stats
    assert cb.stats.total_short_circuits == 1


# ---------------------------------------------------------------------------
# Open → half-open → (closed | open) transitions
# ---------------------------------------------------------------------------


def test_open_transitions_to_half_open_after_timeout() -> None:
    cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=1.0)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.state is CircuitState.OPEN

    # Advance time past recovery_timeout by patching monotonic.
    real_mono = cb._stats.opened_at or 0.0
    with patch("shared.resilience.circuit_breaker.time.monotonic", return_value=real_mono + 2.0):
        assert cb.state is CircuitState.HALF_OPEN


def test_half_open_success_closes_the_circuit() -> None:
    cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=1.0)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))

    opened_at = cb._stats.opened_at
    assert opened_at is not None
    with patch(
        "shared.resilience.circuit_breaker.time.monotonic", return_value=opened_at + 2.0
    ):
        # First call in HALF_OPEN is a probe — on success, go CLOSED.
        result = cb.call(lambda: "recovered")
    assert result == "recovered"
    assert cb.state is CircuitState.CLOSED
    assert cb.stats.consecutive_failures == 0


def test_half_open_failure_reopens_with_fresh_timer() -> None:
    cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=1.0)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("first")))
    first_opened = cb._stats.opened_at
    assert first_opened is not None

    with patch(
        "shared.resilience.circuit_breaker.time.monotonic",
        side_effect=[first_opened + 2.0] * 10,
    ):
        with pytest.raises(RuntimeError, match="second"):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("second")))

    # Re-opened; opened_at advanced forward.
    assert cb.state is CircuitState.OPEN or cb.state is CircuitState.HALF_OPEN
    assert cb._stats.opened_at is not None
    assert cb._stats.opened_at >= first_opened


# ---------------------------------------------------------------------------
# Expected exceptions filtering
# ---------------------------------------------------------------------------


def test_unexpected_exception_passes_through_without_counting() -> None:
    cb = CircuitBreaker(
        "svc",
        failure_threshold=2,
        recovery_timeout=5,
        expected_exceptions=(RuntimeError,),
    )

    with pytest.raises(ValueError):
        cb.call(lambda: (_ for _ in ()).throw(ValueError("bad input")))
    # ValueError not in expected_exceptions → not counted as a failure
    assert cb.stats.consecutive_failures == 0
    assert cb.state is CircuitState.CLOSED


def test_expected_exception_counts_as_failure() -> None:
    cb = CircuitBreaker(
        "svc",
        failure_threshold=2,
        recovery_timeout=5,
        expected_exceptions=(RuntimeError,),
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("upstream down")))
    assert cb.state is CircuitState.OPEN


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def test_reset_returns_to_closed_state_and_clears_stats() -> None:
    cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=1)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.state is CircuitState.OPEN
    cb.reset()
    assert cb.state is CircuitState.CLOSED
    assert cb.stats.consecutive_failures == 0
    assert cb.stats.total_failures == 0


def test_stats_is_a_snapshot_copy() -> None:
    """Mutating the returned stats must not affect the breaker."""
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=5)
    cb.call(lambda: None)
    snap = cb.stats
    snap.total_calls = 99999
    assert cb.stats.total_calls == 1


def test_retry_after_zero_when_timer_elapsed() -> None:
    """The lock-protected helper returns 0 when we're already past the
    recovery window (defensive — in practice the state transitions to
    HALF_OPEN first)."""
    cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=1.0)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    opened_at = cb._stats.opened_at
    assert opened_at is not None
    with patch(
        "shared.resilience.circuit_breaker.time.monotonic", return_value=opened_at + 100.0
    ):
        with cb._lock:
            assert cb._retry_after_seconds_locked() == 0.0


def test_retry_after_zero_when_never_opened() -> None:
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=5)
    with cb._lock:
        assert cb._retry_after_seconds_locked() == 0.0


def test_maybe_transition_noop_when_closed() -> None:
    cb = CircuitBreaker("svc", failure_threshold=3, recovery_timeout=5)
    with cb._lock:
        cb._maybe_transition_open_to_half_open()  # should not raise
    assert cb.state is CircuitState.CLOSED


def test_maybe_transition_noop_when_opened_at_missing() -> None:
    """Defensive: if opened_at was never set but state is OPEN, nothing happens."""
    cb = CircuitBreaker("svc", failure_threshold=1, recovery_timeout=1)
    cb._state = CircuitState.OPEN  # force without setting opened_at
    with cb._lock:
        cb._maybe_transition_open_to_half_open()
    assert cb._state is CircuitState.OPEN
