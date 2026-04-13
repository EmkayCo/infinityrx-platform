"""SQLAlchemy slow-query logger.

Attach to an Engine to log any SQL statement exceeding a threshold.
Complements Postgres-side ``log_min_duration_statement`` by capturing:

    * The ORM-issued parameters (Postgres logs bind params separately)
    * Application-level correlation / tenant / user context (via our
      logging filter), so one log file can answer "what slow queries
      did tenant X generate in the last 10 minutes?"
    * Sub-millisecond jitter on the client side (network + serialization)

Threshold defaults to 1000ms to match the Postgres side. Set via
``SLOW_QUERY_THRESHOLD_MS`` env var.

Usage::

    from sqlalchemy import create_engine
    from shared.observability.slow_query import install_slow_query_logger

    engine = create_engine(url)
    install_slow_query_logger(engine, threshold_ms=1000)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

__all__ = ["install_slow_query_logger"]

logger = logging.getLogger("shared.observability.slow_query")


def install_slow_query_logger(engine: Engine, *, threshold_ms: int = 1000) -> None:
    """Install before/after cursor-execute listeners on *engine*.

    Idempotent per Engine: re-calling stacks listeners. Tests that swap
    engines between cases should use fresh engines (the usual pytest
    pattern), so duplication is not a concern in practice.

    Args:
        engine: The SQLAlchemy Engine to instrument. Async engines
            should pass ``engine.sync_engine``.
        threshold_ms: Log any query slower than this many milliseconds.
            Set to 0 to log every query (noisy — dev only).
    """

    @event.listens_for(engine, "before_cursor_execute")
    def _before(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:  # pragma: no cover - trivial setter, exercised via integration
        context._slow_query_start = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        start = getattr(context, "_slow_query_start", None)
        if start is None:  # pragma: no cover - before-hook always sets this
            return
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if elapsed_ms < threshold_ms:
            return

        # Truncate huge statements so logs don't explode on huge COPY
        # or bulk INSERT payloads.
        truncated = statement if len(statement) <= 2000 else statement[:2000] + "…"
        logger.warning(
            "slow_query",
            extra={
                "elapsed_ms": round(elapsed_ms, 2),
                "threshold_ms": threshold_ms,
                "statement": truncated,
                "executemany": executemany,
                # Parameters can contain PHI — NEVER log raw parameters.
                # Log only the count as a diagnostic.
                "param_count": (
                    len(parameters) if isinstance(parameters, (list, tuple, dict)) else 1
                )
                if parameters is not None
                else 0,
            },
        )
