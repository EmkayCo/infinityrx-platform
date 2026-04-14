"""Tests for PostgresIdempotencyStore.purge_expired (P4.24).

Without row-level TTL, the processed_events table would grow unbounded
at 100M events/year throughput. purge_expired deletes rows older than
the cutoff and returns the row count for operational monitoring.

The test uses an in-process fake engine to exercise the SQL and assert
the DELETE statement is constructed correctly, without requiring a
live Postgres instance.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.events.idempotency import PostgresIdempotencyStore


class _FakeResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _FakeConn:
    def __init__(self, rowcount: int) -> None:
        self.executed: list[tuple[str, dict]] = []
        self._rowcount = rowcount

    async def __aenter__(self) -> "_FakeConn":
        return self

    async def __aexit__(self, *_a) -> bool:
        return False

    async def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params or {}))
        return _FakeResult(self._rowcount)


class _FakeEngine:
    def __init__(self, rowcount: int = 0) -> None:
        self.conn = _FakeConn(rowcount)

    def begin(self):
        return self.conn


async def test_purge_expired_issues_delete_with_cutoff() -> None:
    engine = _FakeEngine(rowcount=42)
    store = PostgresIdempotencyStore(engine)  # type: ignore[arg-type]

    deleted = await store.purge_expired(older_than_seconds=3600)

    assert deleted == 42
    assert len(engine.conn.executed) == 1
    stmt, params = engine.conn.executed[0]
    assert "DELETE FROM core.processed_events" in stmt
    assert "processed_at" in stmt
    assert params["secs"] == "3600"


async def test_purge_expired_default_retention_is_7_days() -> None:
    engine = _FakeEngine(rowcount=0)
    store = PostgresIdempotencyStore(engine)  # type: ignore[arg-type]

    await store.purge_expired()

    _, params = engine.conn.executed[0]
    # 7 days in seconds
    assert params["secs"] == str(7 * 86400)


async def test_purge_expired_returns_zero_when_no_rows_match() -> None:
    engine = _FakeEngine(rowcount=0)
    store = PostgresIdempotencyStore(engine)  # type: ignore[arg-type]

    deleted = await store.purge_expired(older_than_seconds=1)

    assert deleted == 0
