"""Abstract base class for all reference-data ingestion pipelines.

Subclasses implement ``download``, ``parse``, and ``load``. The ``run``
method provides the full orchestration loop: run tracking, checksum-based
deduplication, progress reporting, error sampling, retry with exponential
backoff, and timing breakdown.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from shared.data_ingestion.models import IngestionRun

logger = logging.getLogger(__name__)

# Number of error samples to capture per run
_MAX_ERROR_SAMPLES = 10

# Progress callback interval (records)
_PROGRESS_INTERVAL = 10_000

# Retry configuration for download()
_MAX_DOWNLOAD_ATTEMPTS = 3
_RETRY_DELAYS: tuple[float, float, float] = (1.0, 2.0, 4.0)


@dataclass
class IngestionResult:
    """Returned by ``DataSourceIngester.run()`` after a pipeline completes.

    All count fields are integers. No floats — per project financial precision
    rules (even though these are record counts, not money, the convention is
    enforced globally to prevent accidental float introduction).
    """

    source: str
    status: str  # completed | failed | skipped_unchanged | cancelled
    records_in_source: int = 0
    records_processed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_errored: int = 0
    duration_seconds: float = 0.0
    error_message: str | None = None
    run_id: UUID | None = None


class DataSourceIngester(ABC):
    """Base class for all reference-data ingestion pipelines.

    Subclasses must set ``source_name`` and implement ``download``,
    ``parse``, and ``load``. The ``run`` method is the single entry point
    called by the scheduler or the manual-trigger API.

    ``_db_session`` is a synchronous SQLAlchemy Session used exclusively for
    run tracking rows (IngestionRun, IngestionSchedule). The ingester does NOT
    use the tenant-scoped async session factory because ingestion tracking is
    cross-tenant (LESSON-011).
    """

    source_name: str  # must be set by every subclass

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def download(self) -> Path:
        """Download the source file and return its local path."""

    @abstractmethod
    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse *file_path* and yield one dict per source record."""

    @abstractmethod
    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Bulk-load parsed records; return the partial result."""

    # ------------------------------------------------------------------
    # Progress callback
    # ------------------------------------------------------------------

    def _on_progress(self, processed: int, run: IngestionRun) -> None:
        """Update the run row every ``_PROGRESS_INTERVAL`` records."""
        run.records_processed = processed
        self._db.flush()
        logger.info(
            "Ingestion progress",
            extra={
                "ingest_source": self.source_name,
                "ingest_records_processed": processed,
            },
        )

    # ------------------------------------------------------------------
    # Checksum helper
    # ------------------------------------------------------------------

    def _last_successful_checksum(self) -> str | None:
        """Return the checksum of the most recent completed run, or None."""
        row = (
            self._db.query(IngestionRun)
            .filter(
                IngestionRun.source == self.source_name,
                IngestionRun.status == "completed",
                IngestionRun.source_file_checksum.isnot(None),
            )
            .order_by(IngestionRun.started_at.desc())
            .first()
        )
        return row.source_file_checksum if row else None

    # ------------------------------------------------------------------
    # Download with retry wrapper
    # ------------------------------------------------------------------

    async def _download_with_retry(self) -> Path:
        """Attempt ``download()`` up to ``_MAX_DOWNLOAD_ATTEMPTS`` times."""
        last_error: Exception | None = None
        for attempt in range(_MAX_DOWNLOAD_ATTEMPTS):
            if attempt > 0:
                delay = _RETRY_DELAYS[attempt - 1]
                logger.warning(
                    "Retrying download",
                    extra={
                        "ingest_source": self.source_name,
                        "ingest_attempt": attempt,
                        "ingest_delay_s": delay,
                    },
                )
                await asyncio.sleep(delay)
            try:
                return await self.download()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise  # 4xx — not transient
                last_error = exc
                logger.warning(
                    "Transient download error",
                    extra={"ingest_source": self.source_name, "ingest_error": str(exc)},
                )
        raise RuntimeError(
            f"Download failed after {_MAX_DOWNLOAD_ATTEMPTS} attempts for {self.source_name}"
        ) from last_error

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    async def run(
        self,
        *,
        run_type: str = "auto_scheduled",
        triggered_by: UUID | None = None,
    ) -> IngestionResult:
        """Full pipeline: track → download → checksum compare → parse → load.

        Parameters
        ----------
        run_type:
            One of ``auto_scheduled``, ``manual_trigger``, ``file_upload``.
        triggered_by:
            UUID of the user or system entity that initiated this run.
        """
        wall_start = time.monotonic()
        started_at = datetime.now(UTC)

        # Create run row
        run = IngestionRun(
            source=self.source_name,
            run_type=run_type,
            status="running",
            started_at=started_at,
            triggered_by=triggered_by,
        )
        self._db.add(run)
        self._db.commit()
        self._db.refresh(run)

        logger.info(
            "Ingestion run started",
            extra={
                "ingest_source": self.source_name,
                "ingest_run_id": str(run.id),
                "ingest_run_type": run_type,
            },
        )

        try:
            result = await self._execute_run(run, run_type, triggered_by)
        except Exception as exc:
            error_msg = str(exc)
            logger.exception(
                "Ingestion run failed",
                extra={
                    "ingest_source": self.source_name,
                    "ingest_run_id": str(run.id),
                    "ingest_error": error_msg,
                },
            )
            run.status = "failed"
            run.error_message = error_msg
            run.completed_at = datetime.now(UTC)
            self._db.commit()
            return IngestionResult(
                source=self.source_name,
                status="failed",
                error_message=error_msg,
                duration_seconds=time.monotonic() - wall_start,
                run_id=run.id,
            )

        run.completed_at = datetime.now(UTC)
        self._db.commit()
        result.run_id = run.id
        return result

    async def _execute_run(
        self,
        run: IngestionRun,
        run_type: str,
        triggered_by: UUID | None,
    ) -> IngestionResult:
        """Inner execution — separated so the outer ``run()`` can wrap it."""
        wall_start = time.monotonic()

        # ----- Download ------------------------------------------------
        t0 = time.monotonic()
        file_path = await self._download_with_retry()
        download_seconds = int(time.monotonic() - t0)
        run.download_seconds = download_seconds

        # Capture file metadata
        file_size = file_path.stat().st_size if file_path.is_file() else None
        run.source_file_name = file_path.name
        run.source_file_size_bytes = file_size

        # ----- Checksum -----------------------------------------------
        from shared.data_ingestion.downloader import compute_sha256

        checksum = compute_sha256(file_path) if file_path.is_file() else None
        run.source_file_checksum = checksum
        self._db.flush()

        last_checksum = self._last_successful_checksum()
        if checksum and last_checksum and checksum == last_checksum:
            run.status = "skipped_unchanged"
            run.completed_at = datetime.now(UTC)
            self._db.commit()
            logger.info(
                "Skipping unchanged source",
                extra={
                    "ingest_source": self.source_name,
                    "ingest_checksum": checksum,
                },
            )
            return IngestionResult(
                source=self.source_name,
                status="skipped_unchanged",
                duration_seconds=time.monotonic() - wall_start,
            )

        # ----- Parse + Load -------------------------------------------
        t1 = time.monotonic()

        error_samples: list[dict[str, Any]] = []
        records_in_source = 0
        progress_counter = 0

        def _tracked_records() -> Iterator[dict[str, Any]]:
            """Wrap parse() to count records and collect error samples."""
            nonlocal records_in_source, progress_counter
            for raw in self.parse(file_path):
                records_in_source += 1
                progress_counter += 1
                if progress_counter >= _PROGRESS_INTERVAL:
                    self._on_progress(records_in_source, run)
                    progress_counter = 0
                yield raw

        parse_start = time.monotonic()
        tracked = _tracked_records()
        parse_end_holder: list[float] = []

        async def _load_with_timing() -> IngestionResult:
            """Wrap load() to capture parse vs load timing."""
            partial = await self.load(tracked)
            parse_end_holder.append(time.monotonic())
            return partial

        partial_result = await _load_with_timing()
        total_after_load = time.monotonic()

        parse_seconds = int(
            (parse_end_holder[0] if parse_end_holder else total_after_load) - parse_start
        )
        load_seconds = int(total_after_load - t1) - parse_seconds

        run.records_in_source = records_in_source
        run.records_processed = partial_result.records_processed
        run.records_inserted = partial_result.records_inserted
        run.records_updated = partial_result.records_updated
        run.records_skipped = partial_result.records_skipped
        run.records_errored = partial_result.records_errored
        run.parse_seconds = max(parse_seconds, 0)
        run.load_seconds = max(load_seconds, 0)

        if error_samples:
            run.error_samples = {"samples": error_samples}

        run.status = "completed"
        self._db.flush()

        logger.info(
            "Ingestion run completed",
            extra={
                "ingest_source": self.source_name,
                "ingest_records_processed": run.records_processed,
                "ingest_records_inserted": run.records_inserted,
                "ingest_records_errored": run.records_errored,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_in_source=records_in_source,
            records_processed=partial_result.records_processed,
            records_inserted=partial_result.records_inserted,
            records_updated=partial_result.records_updated,
            records_skipped=partial_result.records_skipped,
            records_errored=partial_result.records_errored,
            duration_seconds=time.monotonic() - wall_start,
        )

    # ------------------------------------------------------------------
    # Error sampling helper (called by subclass load() implementations)
    # ------------------------------------------------------------------

    @staticmethod
    def capture_error_sample(
        samples: list[dict[str, Any]],
        field_name: str,
        raw_row: Any,
        exc: Exception,
    ) -> None:
        """Append an error sample if the cap has not been reached."""
        if len(samples) < _MAX_ERROR_SAMPLES:
            samples.append(
                {
                    "field": field_name,
                    "raw_row": str(raw_row)[:500],
                    "error": str(exc)[:500],
                }
            )


__all__ = ["DataSourceIngester", "IngestionResult"]
