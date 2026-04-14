"""Cleanup job for the processed_events idempotency table.

The event-bus rule requires:
    DELETE FROM processed_events WHERE processed_at < NOW() - INTERVAL '7 days'

This job prevents unbounded table growth at 100M+ events/year throughput.
Without regular cleanup, the processed_events table grows without bound and
idempotency lookups slow down.

Usage
-----
Register with any module's job scheduler::

    from shared.events.jobs.cleanup_processed_events import purge_processed_events

    # In scheduled jobs:
    await purge_processed_events(engine)

Or use the convenience wrapper that returns a summary dict for monitoring::

    result = await run_cleanup(engine)
    # result == {"rows_deleted": 12345, "cutoff_days": 7}
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from shared.events.idempotency import PostgresIdempotencyStore

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


async def purge_processed_events(
    engine: "AsyncEngine",
    *,
    retention_days: int = 7,
) -> int:
    """Delete processed_events rows older than ``retention_days``.

    Uses PostgresIdempotencyStore.purge_expired() which issues a single
    DELETE statement with ON CONFLICT DO NOTHING semantics for safety.

    Args:
        engine: Async SQLAlchemy engine connected to the platform database.
        retention_days: Number of days to retain processed_events rows.
            Default 7 per event-bus rule. Must be positive.

    Returns:
        Number of rows deleted.
    """
    if retention_days <= 0:
        raise ValueError(f"retention_days must be positive, got {retention_days}")

    store = PostgresIdempotencyStore(engine)
    older_than_seconds = retention_days * 86400
    deleted = await store.purge_expired(older_than_seconds=older_than_seconds)
    return deleted


async def run_cleanup(
    engine: "AsyncEngine",
    *,
    retention_days: int = 7,
) -> dict[str, int]:
    """Run the cleanup and return a monitoring-friendly summary dict.

    Args:
        engine: Async SQLAlchemy engine.
        retention_days: Number of days to retain rows (default 7).

    Returns:
        dict with keys:
            rows_deleted: Number of rows removed.
            cutoff_days: The retention_days parameter used.
    """
    deleted = await purge_processed_events(engine, retention_days=retention_days)
    return {
        "rows_deleted": deleted,
        "cutoff_days": retention_days,
    }
