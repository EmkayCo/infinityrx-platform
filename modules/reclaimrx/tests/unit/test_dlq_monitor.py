"""Unit tests for check_dlq_depth duration threshold (R1 BLOCK 9 fix).

Tests use a mocked async engine so no real DB is needed.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.jobs.dlq_monitor import check_dlq_depth, _DLQ_DURATION_THRESHOLD_MINUTES


@pytest.mark.asyncio
async def test_ok_when_queue_empty():
    """Empty queue -> status='ok', queued_count=0."""
    now = datetime.now(UTC)
    engine = _stub_engine(count=0, oldest=None)
    result = await check_dlq_depth(engine, _now=now)
    assert result["status"] == "ok"
    assert result["queued_count"] == 0
    assert result["oldest_age_minutes"] is None


@pytest.mark.asyncio
async def test_monitoring_when_count_positive_but_age_under_threshold():
    """Depth > 0 but oldest is 5 minutes old -> 'monitoring' (NOT 'alert')."""
    now = datetime.now(UTC)
    oldest = now - timedelta(minutes=5)
    engine = _stub_engine(count=3, oldest=oldest)
    result = await check_dlq_depth(engine, _now=now)
    assert result["status"] == "monitoring"
    assert result["queued_count"] == 3
    assert result["oldest_age_minutes"] < _DLQ_DURATION_THRESHOLD_MINUTES


@pytest.mark.asyncio
async def test_alert_when_oldest_age_exceeds_threshold():
    """Oldest is 20 minutes old -> 'alert'."""
    now = datetime.now(UTC)
    oldest = now - timedelta(minutes=20)
    engine = _stub_engine(count=1, oldest=oldest)
    result = await check_dlq_depth(engine, _now=now)
    assert result["status"] == "alert"
    assert result["oldest_age_minutes"] > _DLQ_DURATION_THRESHOLD_MINUTES


@pytest.mark.asyncio
async def test_boundary_exactly_at_threshold():
    """Exactly 15 minutes -> still 'monitoring' (rule is '> 15', not '>= 15')."""
    now = datetime.now(UTC)
    oldest = now - timedelta(minutes=15)
    engine = _stub_engine(count=2, oldest=oldest)
    result = await check_dlq_depth(engine, _now=now)
    assert result["status"] == "monitoring"


def _stub_engine(count: int, oldest: datetime | None):
    """Build a mock AsyncEngine whose connect().__aenter__().execute() returns
    a result whose .one() yields (count, oldest).

    R6 BLOCK-19 fix: paired with the implementation switch from AsyncSession
    to conn.execute() directly. We only mock conn.execute() -> result.one().
    """
    result = MagicMock()
    result.one = MagicMock(return_value=(count, oldest))

    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value=result)

    engine = MagicMock()
    engine.connect = MagicMock(return_value=conn)
    return engine
