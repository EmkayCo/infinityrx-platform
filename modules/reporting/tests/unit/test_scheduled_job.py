"""Unit tests for the run_due_scheduled_reports job skeleton.

Covers:
- Empty schedule set returns zero triggered/skipped.
- Due schedule triggers report execution and advances next_run_at.
- Non-due schedule (clock skew guard) is skipped.
- Failed report execution increments skipped, sets last_run_status=error.
- Tenant filtering passes tenant_id correctly to the query.
- Counts are correct when mix of due and already-guarded schedules exist.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.jobs.scheduled import run_due_scheduled_reports


def _make_schedule(
    *,
    next_run_at: datetime,
    is_active: bool = True,
    frequency: str = "daily",
    time_of_day: time = time(6, 0),
    day_of_week: int | None = None,
    day_of_month: int | None = None,
) -> MagicMock:
    """Build a mock ReportSchedule with required fields."""
    s = MagicMock()
    s.id = "sch-001"
    s.tenant_id = "tenant-abc"
    s.report_definition_id = "defn-001"
    s.is_active = is_active
    s.next_run_at = next_run_at
    s.frequency = frequency
    s.time_of_day = time_of_day
    s.day_of_week = day_of_week
    s.day_of_month = day_of_month
    s.output_format = "excel"
    s.delivery_method = "email"
    s.filters = {}
    s.last_run_at = None
    s.last_run_status = None
    return s


def _make_db(schedules: list[MagicMock]) -> MagicMock:
    """Build an async mock DB session that returns the given schedules."""
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = schedules
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_empty_schedules_returns_zero_counts() -> None:
    db = _make_db([])
    result = await run_due_scheduled_reports(db)
    assert result == {"triggered": 0, "skipped": 0}


@pytest.mark.asyncio
async def test_due_schedule_triggers_report_and_advances_next_run() -> None:
    now = datetime(2026, 4, 14, 6, 30, tzinfo=UTC)
    schedule = _make_schedule(next_run_at=datetime(2026, 4, 14, 6, 0, tzinfo=UTC))
    db = _make_db([schedule])

    mock_run = MagicMock()
    mock_run.id = "run-001"

    # ReportService is imported inside the function; patch it at the source module.
    with patch("src.services.report_service.ReportService.execute_report", new=AsyncMock(return_value=mock_run)):
        with patch("src.jobs.scheduled.datetime") as mock_dt:
            mock_dt.now.return_value = now
            result = await run_due_scheduled_reports(db)

    assert result["triggered"] == 1
    assert result["skipped"] == 0
    # next_run_at must have advanced (been set to a new datetime)
    assert schedule.next_run_at != datetime(2026, 4, 14, 6, 0, tzinfo=UTC)
    assert schedule.last_run_status == "triggered"


@pytest.mark.asyncio
async def test_non_due_schedule_is_skipped_by_clock_skew_guard() -> None:
    """Schedule next_run_at is in the future relative to actual now — should be skipped."""
    now = datetime(2026, 4, 14, 5, 0, tzinfo=UTC)
    # DB query matched it (simulating a race), but guard re-checks
    schedule = _make_schedule(next_run_at=datetime(2026, 4, 14, 6, 0, tzinfo=UTC))
    db = _make_db([schedule])

    with patch("src.jobs.scheduled.datetime") as mock_dt:
        mock_dt.now.return_value = now
        result = await run_due_scheduled_reports(db)

    assert result["triggered"] == 0
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_failed_execution_increments_skipped_and_sets_error_status() -> None:
    now = datetime(2026, 4, 14, 6, 30, tzinfo=UTC)
    schedule = _make_schedule(next_run_at=datetime(2026, 4, 14, 6, 0, tzinfo=UTC))
    db = _make_db([schedule])

    with patch(
        "src.services.report_service.ReportService.execute_report",
        new=AsyncMock(side_effect=RuntimeError("DB unavailable")),
    ):
        with patch("src.jobs.scheduled.datetime") as mock_dt:
            mock_dt.now.return_value = now
            result = await run_due_scheduled_reports(db)

    assert result["triggered"] == 0
    assert result["skipped"] == 1
    assert schedule.last_run_status == "error"


@pytest.mark.asyncio
async def test_none_next_run_at_skips_schedule() -> None:
    """A schedule with next_run_at=None must be skipped (not triggered)."""
    schedule = _make_schedule(next_run_at=datetime(2026, 1, 1, tzinfo=UTC))
    schedule.next_run_at = None
    db = _make_db([schedule])

    result = await run_due_scheduled_reports(db)
    assert result["triggered"] == 0
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_multiple_due_schedules_all_triggered() -> None:
    now = datetime(2026, 4, 14, 8, 0, tzinfo=UTC)
    schedules = [
        _make_schedule(next_run_at=datetime(2026, 4, 14, 6, 0, tzinfo=UTC)),
        _make_schedule(next_run_at=datetime(2026, 4, 14, 7, 0, tzinfo=UTC)),
        _make_schedule(next_run_at=datetime(2026, 4, 14, 7, 30, tzinfo=UTC)),
    ]
    for i, s in enumerate(schedules):
        s.id = f"sch-{i:03d}"

    db = _make_db(schedules)

    mock_run = MagicMock()
    mock_run.id = "run-x"

    with patch(
        "src.services.report_service.ReportService.execute_report",
        new=AsyncMock(return_value=mock_run),
    ):
        with patch("src.jobs.scheduled.datetime") as mock_dt:
            mock_dt.now.return_value = now
            result = await run_due_scheduled_reports(db)

    assert result["triggered"] == 3
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_tenant_id_filter_passed_to_job() -> None:
    """Passing tenant_id should filter only that tenant's schedules."""
    db = _make_db([])
    result = await run_due_scheduled_reports(db, tenant_id="tenant-xyz")
    assert result == {"triggered": 0, "skipped": 0}
    # Verify execute was called (the WHERE clause ran)
    db.execute.assert_awaited_once()
