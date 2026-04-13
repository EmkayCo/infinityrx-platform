"""shared.resilience — fault-tolerance primitives (circuit breaker, retries)."""

from shared.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)

__all__ = ["CircuitBreaker", "CircuitOpenError", "CircuitState"]
