"""Tests for the processed_events cleanup job.

Uses frozen time to verify the retention cutoff is applied correctly.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shared.events.idempotency import PostgresIdempotencyStore
from shared.events.jobs.cleanup_processed_events import purge_processed_events, run_cleanup


@pytest.fixture
async def engine():
    """SQLite in-memory engine with processed_events table."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        # Create the core schema and processed_events table (SQLite-compatible)
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS processed_events (
                    idempotency_key TEXT NOT NULL,
                    consumer_name   TEXT NOT NULL DEFAULT '',
                    processed_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (idempotency_key, consumer_name)
                )
                """
            )
        )
    yield eng
    await eng.dispose()


async def _seed_rows(engine, rows: list[tuple[str, str, datetime]]) -> None:
    """Insert processed_events rows with specific timestamps."""
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            for key, consumer, ts in rows:
                await session.execute(
                    text(
                        "INSERT OR IGNORE INTO processed_events "
                        "(idempotency_key, consumer_name, processed_at) "
                        "VALUES (:k, :c, :ts)"
                    ),
                    {"k": key, "c": consumer, "ts": ts.isoformat()},
                )


async def _count_rows(engine) -> int:
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM processed_events"))
        return result.scalar_one()


class TestPurgeProcessedEvents:
    async def test_deletes_rows_older_than_retention_period(self, engine) -> None:
        """Rows older than retention_days are deleted; newer rows are kept."""
        now = datetime.now(UTC)
        old_ts = now - timedelta(days=8)
        recent_ts = now - timedelta(days=3)

        await _seed_rows(engine, [
            ("old-key-1", "consumer-a", old_ts),
            ("old-key-2", "consumer-a", old_ts),
            ("recent-key-1", "consumer-a", recent_ts),
        ])

        # Patch purge_expired to use our SQLite engine
        store = PostgresIdempotencyStore(engine)
        # Directly override the purge_expired method to use direct SQL
        # since PostgresIdempotencyStore uses core.processed_events schema
        from sqlalchemy import text as _text

        async def _purge_direct(*, older_than_seconds: int = 7 * 86400) -> int:
            async with engine.begin() as conn:
                result = await conn.execute(
                    _text(
                        "DELETE FROM processed_events "
                        "WHERE processed_at < :cutoff"
                    ),
                    {"cutoff": (now - timedelta(seconds=older_than_seconds)).isoformat()},
                )
                return result.rowcount or 0

        store.purge_expired = _purge_direct  # type: ignore[method-assign]

        with patch(
            "shared.events.jobs.cleanup_processed_events.PostgresIdempotencyStore",
            return_value=store,
        ):
            deleted = await purge_processed_events(engine, retention_days=7)

        assert deleted == 2
        remaining = await _count_rows(engine)
        assert remaining == 1

    async def test_no_rows_deleted_when_all_recent(self, engine) -> None:
        """No rows deleted when all rows are within the retention window."""
        now = datetime.now(UTC)
        await _seed_rows(engine, [
            ("key-1", "c", now - timedelta(days=1)),
            ("key-2", "c", now - timedelta(hours=12)),
        ])

        store = PostgresIdempotencyStore(engine)

        async def _purge_direct(*, older_than_seconds: int = 7 * 86400) -> int:
            async with engine.begin() as conn:
                result = await conn.execute(
                    text("DELETE FROM processed_events WHERE processed_at < :cutoff"),
                    {"cutoff": (now - timedelta(seconds=older_than_seconds)).isoformat()},
                )
                return result.rowcount or 0

        store.purge_expired = _purge_direct  # type: ignore[method-assign]

        with patch(
            "shared.events.jobs.cleanup_processed_events.PostgresIdempotencyStore",
            return_value=store,
        ):
            deleted = await purge_processed_events(engine, retention_days=7)

        assert deleted == 0

    async def test_raises_on_non_positive_retention_days(self, engine) -> None:
        """retention_days=0 raises ValueError."""
        with pytest.raises(ValueError, match="retention_days must be positive"):
            await purge_processed_events(engine, retention_days=0)

    async def test_run_cleanup_returns_monitoring_summary(self, engine) -> None:
        """run_cleanup returns a dict with rows_deleted and cutoff_days."""
        store = PostgresIdempotencyStore(engine)

        async def _purge_zero(*, older_than_seconds: int = 7 * 86400) -> int:
            return 42

        store.purge_expired = _purge_zero  # type: ignore[method-assign]

        with patch(
            "shared.events.jobs.cleanup_processed_events.PostgresIdempotencyStore",
            return_value=store,
        ):
            result = await run_cleanup(engine, retention_days=7)

        assert result == {"rows_deleted": 42, "cutoff_days": 7}

    async def test_custom_retention_days_applied(self, engine) -> None:
        """Custom retention_days is passed through correctly."""
        store = PostgresIdempotencyStore(engine)
        received_seconds = None

        async def _capture(*, older_than_seconds: int = 7 * 86400) -> int:
            nonlocal received_seconds
            received_seconds = older_than_seconds
            return 0

        store.purge_expired = _capture  # type: ignore[method-assign]

        with patch(
            "shared.events.jobs.cleanup_processed_events.PostgresIdempotencyStore",
            return_value=store,
        ):
            await purge_processed_events(engine, retention_days=14)

        assert received_seconds == 14 * 86400
