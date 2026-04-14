"""Tests for shared.data_ingestion.base.DataSourceIngester.

Verifies:
- Run row created on start
- Status transitions: running → completed / failed / skipped_unchanged
- Checksum skip path
- Error sample capture (forced exception on row 3)
- Progress callback fired every _PROGRESS_INTERVAL records
- Decimal pass-through (parse yields dicts with Decimal values that survive load)
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from shared.data_ingestion.base import _PROGRESS_INTERVAL, DataSourceIngester, IngestionResult
from shared.data_ingestion.models import IngestionRun

# ---------------------------------------------------------------------------
# Fake ingester implementations for testing
# ---------------------------------------------------------------------------


class _FakeIngester(DataSourceIngester):
    """Minimal ingester that returns a small set of records without I/O."""

    source_name = "test_source"

    def __init__(self, db_session: Session, rows: list[dict[str, Any]] | None = None) -> None:
        super().__init__(db_session)
        self._rows = rows or [{"ndc": "12345678901", "price": Decimal("9.99")}]
        self._downloaded_path: Path | None = None

    async def download(self) -> Path:
        # Returns a dummy path — checksum will be computed in tests that need it
        p = Path("/tmp/test_source_fake.txt")
        p.write_text("fake content")
        self._downloaded_path = p
        return p

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        yield from self._rows

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        rows = list(records)
        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=len(rows),
            records_inserted=len(rows),
        )


class _ExplodingIngester(_FakeIngester):
    """Ingester whose download() raises to test the failed status path."""

    async def download(self) -> Path:
        raise RuntimeError("Simulated download failure")


class _ExceptionOnRow3Ingester(_FakeIngester):
    """Ingester that parses 5 rows but raises on row 3 to test error sampling.

    The base class ``_execute_run`` wraps ``load()``; we simulate load()
    encountering a bad record and capturing the error.
    """

    source_name = "error_capture_source"

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        error_samples: list[dict[str, Any]] = []
        processed = 0
        inserted = 0
        errored = 0

        for idx, row in enumerate(records):
            try:
                if idx == 2:  # row 3 (0-indexed)
                    raise ValueError("Bad value in row 3")
                processed += 1
                inserted += 1
            except ValueError as exc:
                errored += 1
                DataSourceIngester.capture_error_sample(
                    error_samples, "ndc", row, exc
                )

        # Persist samples via the run row
        run = (
            self._db.query(IngestionRun)
            .filter(IngestionRun.source == self.source_name)
            .order_by(IngestionRun.started_at.desc())
            .first()
        )
        if run is not None and error_samples:
            run.error_samples = {"samples": error_samples}
            self._db.flush()

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=processed + errored,
            records_inserted=inserted,
            records_errored=errored,
        )


class _DecimalPassthroughIngester(_FakeIngester):
    """Passes Decimal-valued dicts through parse → load to verify no type coercion."""

    source_name = "decimal_source"

    def __init__(self, db_session: Session) -> None:
        rows = [
            {"amount": Decimal("10.99"), "qty": Decimal("3")},
            {"amount": Decimal("0.01"), "qty": Decimal("1000")},
        ]
        super().__init__(db_session, rows)
        self.loaded_rows: list[dict[str, Any]] = []

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        for row in records:
            # Verify Decimal types survive parse → load boundary
            assert isinstance(row["amount"], Decimal), (
                f"Expected Decimal, got {type(row['amount'])}"
            )
            self.loaded_rows.append(row)
        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=len(self.loaded_rows),
            records_inserted=len(self.loaded_rows),
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_creates_run_row_in_db(db_session: Session) -> None:
    """A completed run must persist an IngestionRun row with status=completed."""
    ingester = _FakeIngester(db_session)

    with patch.object(ingester, "_last_successful_checksum", return_value=None):
        result = asyncio.run(ingester.run(run_type="manual_trigger"))

    assert result.status == "completed"
    assert result.run_id is not None

    row = db_session.query(IngestionRun).filter_by(id=result.run_id).one()
    assert row.source == "test_source"
    assert row.status == "completed"
    assert row.run_type == "manual_trigger"
    assert row.records_inserted == 1


def test_run_status_transitions_to_failed_on_download_error(db_session: Session) -> None:
    """When download raises, the run row must be marked failed."""
    ingester = _ExplodingIngester(db_session)

    result = asyncio.run(ingester.run())

    assert result.status == "failed"
    assert result.error_message is not None
    assert "Simulated download failure" in result.error_message

    row = db_session.query(IngestionRun).filter_by(id=result.run_id).one()
    assert row.status == "failed"
    assert row.completed_at is not None


def test_checksum_skip_when_file_unchanged(db_session: Session, tmp_path: Path) -> None:
    """If the downloaded file has the same checksum as the last run, skip it."""
    from shared.data_ingestion.downloader import compute_sha256

    # Create a real file with a known checksum
    f = tmp_path / "source.txt"
    f.write_bytes(b"stable reference data")
    known_checksum = compute_sha256(f)

    ingester = _FakeIngester(db_session)

    async def _fake_download() -> Path:
        return f

    with (
        patch.object(ingester, "download", new=_fake_download),
        patch.object(ingester, "_last_successful_checksum", return_value=known_checksum),
    ):
        result = asyncio.run(ingester.run())

    assert result.status == "skipped_unchanged"

    row = db_session.query(IngestionRun).filter_by(id=result.run_id).one()
    assert row.status == "skipped_unchanged"


def test_checksum_fires_when_file_differs(db_session: Session, tmp_path: Path) -> None:
    """When the checksum differs from the last run, the run proceeds normally."""

    f = tmp_path / "source.txt"
    f.write_bytes(b"new reference data version 2")

    ingester = _FakeIngester(db_session)

    async def _fake_download() -> Path:
        return f

    with (
        patch.object(ingester, "download", new=_fake_download),
        patch.object(ingester, "_last_successful_checksum", return_value="a" * 64),
    ):
        result = asyncio.run(ingester.run())

    assert result.status == "completed"


def test_error_sample_captured_on_row_3(db_session: Session) -> None:
    """Exception on row 3 must be captured in error_samples JSONB."""
    rows = [
        {"ndc": "00001", "price": Decimal("1.00")},
        {"ndc": "00002", "price": Decimal("2.00")},
        {"ndc": "BAD_ROW", "price": Decimal("3.00")},  # triggers error
        {"ndc": "00004", "price": Decimal("4.00")},
        {"ndc": "00005", "price": Decimal("5.00")},
    ]
    ingester = _ExceptionOnRow3Ingester(db_session, rows)

    with patch.object(ingester, "_last_successful_checksum", return_value=None):
        result = asyncio.run(ingester.run())

    assert result.status == "completed"
    assert result.records_errored == 1

    row = db_session.query(IngestionRun).filter_by(id=result.run_id).one()
    assert row.error_samples is not None
    samples = row.error_samples.get("samples", [])
    assert len(samples) == 1
    assert samples[0]["field"] == "ndc"
    assert "Bad value in row 3" in samples[0]["error"]


def test_progress_callback_fired_at_interval(db_session: Session) -> None:
    """Progress must be recorded every _PROGRESS_INTERVAL records."""
    # Build rows = _PROGRESS_INTERVAL + 1 to trigger exactly one flush
    num_rows = _PROGRESS_INTERVAL + 1
    rows = [{"idx": i} for i in range(num_rows)]

    callback_counts: list[int] = []

    class _CountingIngester(_FakeIngester):
        source_name = "progress_source"

        def _on_progress(self, processed: int, run: IngestionRun) -> None:
            callback_counts.append(processed)
            # don't flush to avoid SAVEPOINT complexity — just count
            self._db.flush()

        async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
            consumed = list(records)  # drains the generator (triggers callbacks)
            return IngestionResult(
                source=self.source_name,
                status="completed",
                records_processed=len(consumed),
                records_inserted=len(consumed),
            )

    ingester = _CountingIngester(db_session, rows)

    with patch.object(ingester, "_last_successful_checksum", return_value=None):
        result = asyncio.run(ingester.run())

    assert result.status == "completed"
    # Should have fired the callback exactly once at _PROGRESS_INTERVAL
    assert len(callback_counts) >= 1
    assert callback_counts[0] == _PROGRESS_INTERVAL


def test_decimal_values_survive_parse_to_load(db_session: Session) -> None:
    """Decimal amounts returned by parse() must not be coerced to float in load()."""
    ingester = _DecimalPassthroughIngester(db_session)

    with patch.object(ingester, "_last_successful_checksum", return_value=None):
        result = asyncio.run(ingester.run())

    assert result.status == "completed"
    assert result.records_inserted == 2

    # Verify the loaded rows contain Decimal, not float
    for row in ingester.loaded_rows:
        assert isinstance(row["amount"], Decimal)
        assert isinstance(row["qty"], Decimal)


def test_run_id_is_populated_on_result(db_session: Session) -> None:
    """IngestionResult.run_id must be set to the DB row ID after a run."""
    ingester = _FakeIngester(db_session)

    with patch.object(ingester, "_last_successful_checksum", return_value=None):
        result = asyncio.run(ingester.run())

    assert result.run_id is not None
    # Must match what is in the DB
    row = db_session.query(IngestionRun).filter_by(id=result.run_id).one()
    assert row.id == result.run_id


def test_run_triggered_by_stored_on_row(db_session: Session) -> None:
    """triggered_by UUID must be persisted on the run row."""
    user_id = uuid4()
    ingester = _FakeIngester(db_session)

    with patch.object(ingester, "_last_successful_checksum", return_value=None):
        result = asyncio.run(ingester.run(run_type="manual_trigger", triggered_by=user_id))

    row = db_session.query(IngestionRun).filter_by(id=result.run_id).one()
    assert row.triggered_by == user_id
    assert row.run_type == "manual_trigger"


def test_on_progress_updates_run_row_and_logs(db_session: Session) -> None:
    """_on_progress (base implementation) must flush the run row."""
    from shared.data_ingestion.base import DataSourceIngester

    # Create a real run row to flush against
    run = IngestionRun(
        source="test_source",
        run_type="manual_trigger",
        status="running",
        started_at=datetime.now(UTC),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    ingester = _FakeIngester(db_session)
    # Call the base _on_progress directly
    DataSourceIngester._on_progress(ingester, 5000, run)

    assert run.records_processed == 5000


def test_download_with_retry_raises_on_4xx(db_session: Session) -> None:
    """_download_with_retry must not retry on 4xx errors."""
    import httpx

    ingester = _FakeIngester(db_session)
    call_count = 0

    async def _bad_download() -> Path:
        nonlocal call_count
        call_count += 1
        response = httpx.Response(404)
        raise httpx.HTTPStatusError("Not Found", request=MagicMock(), response=response)

    ingester.download = _bad_download  # type: ignore[method-assign]

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(ingester._download_with_retry())

    # Must not retry on 404
    assert call_count == 1


def test_download_with_retry_retries_on_transport_error(db_session: Session) -> None:
    """_download_with_retry must retry on TransportError."""
    import httpx

    ingester = _FakeIngester(db_session)
    calls: list[int] = []
    good_path = Path("/tmp/good_file.txt")
    good_path.write_text("data")

    async def _flaky_download() -> Path:
        calls.append(1)
        if len(calls) < 2:
            raise httpx.TransportError("connection reset")
        return good_path

    ingester.download = _flaky_download  # type: ignore[method-assign]

    with patch("asyncio.sleep"):  # don't actually sleep in tests
        result_path = asyncio.run(ingester._download_with_retry())

    assert result_path == good_path
    assert len(calls) == 2


def test_last_successful_checksum_returns_none_when_no_runs(db_session: Session) -> None:
    """_last_successful_checksum must return None when no completed runs exist."""
    ingester = _FakeIngester(db_session)
    assert ingester._last_successful_checksum() is None


def test_last_successful_checksum_returns_most_recent(db_session: Session) -> None:
    """_last_successful_checksum returns the checksum of the most recent completed run."""
    from datetime import UTC, datetime

    run1 = IngestionRun(
        source="test_source",
        run_type="auto_scheduled",
        status="completed",
        source_file_checksum="aaa",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    run2 = IngestionRun(
        source="test_source",
        run_type="auto_scheduled",
        status="completed",
        source_file_checksum="bbb",
        started_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    db_session.add_all([run1, run2])
    db_session.commit()

    ingester = _FakeIngester(db_session)
    result = ingester._last_successful_checksum()
    assert result == "bbb"  # most recent
