"""Reference-data ingestion scheduler.

Runs as a long-lived asyncio Task inside a FastAPI lifespan context.
Every 60 seconds it checks each registered source against its cron
expression and fires an ingestion run if due. In-flight runs are skipped
to prevent overlapping executions.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.data_ingestion.models import IngestionRun, IngestionSchedule

logger = logging.getLogger(__name__)

# Cron expressions for each well-known source.
# None → manual-only; the scheduler will never auto-fire.
DEFAULT_SCHEDULES: dict[str, str | None] = {
    "fda_ndc": "0 2 * * *",          # Daily 2 AM
    "cms_nadac": "0 3 * * 1",         # Weekly Monday 3 AM
    "fda_orange_book": "0 4 1 * *",   # Monthly 1st 4 AM
    "nppes": "0 3 * * 2",             # Weekly Tuesday 3 AM
    "nppes_monthly": "0 4 15 * *",    # Monthly 15th 4 AM (CMS posts ~10-12th; 15th = buffer)
    "nppes_deactivation": "0 5 15 * *",  # Monthly 15th 5 AM (1h after monthly to avoid overlap)
    "cms_asp": "0 4 1 1,4,7,10 *",   # Quarterly
    "ncpdp": None,                     # Manual only
    "rxnorm": "0 1 1-7 * 1",           # First Monday of month, 1 AM
    "fda_rems": "0 5 * * 3",           # Weekly Wednesday 5 AM
    "fda_drug_shortages": "0 6 * * *", # Daily 6 AM
    "fda_purple_book": "0 5 15 * *",   # Monthly 15th 5 AM
    "oig_leie": "0 2 20 * *",          # Monthly 20th 2 AM
    "dea_registrations": "0 6 1 * *",  # Monthly 1st 6 AM
    "sam_exclusions": "0 3 20 * *",    # Monthly 20th 3 AM
    "cms_opt_out": "0 4 15 * *",       # Monthly 15th 4 AM
    "icd10_cm": "0 2 15 4,10 *",       # 15th of April + October, 2 AM
                                       # CMS publishes the annual release
                                       # around Oct 1 and a mid-year update
                                       # around April 1; day-15 gives a
                                       # two-week buffer for the files to
                                       # actually land on download.cms.gov.
    "hcpcs": "0 3 15 1,4,7,10 *",      # 15th of Jan/Apr/Jul/Oct, 3 AM
                                       # Quarterly alpha-numeric release —
                                       # CMS typically posts in the first
                                       # week of the month, day-15 is safe.
                                       # 1h after icd10_cm to avoid sharing
                                       # a DB-session slot.
}

# Interval between scheduler ticks
_TICK_INTERVAL_SECONDS: int = 60

# Type alias for the factory that creates a fresh ingester instance
IngesterFactory = Callable[[], Any]  # -> DataSourceIngester


class IngestionScheduler:
    """Long-running scheduler that fires ingestion runs based on cron expressions.

    Usage (in FastAPI lifespan)::

        scheduler = IngestionScheduler(session_factory=lambda: db_session)
        scheduler.register("fda_ndc", FdaNdcIngester, "0 2 * * *")
        scheduler.register("cms_nadac", CmsNadacIngester, "0 3 * * 1")
        task = asyncio.create_task(scheduler.start())
    """

    def __init__(self, session_factory: Callable[[], Any]) -> None:  # Any = context manager yielding Session
        self._session_factory = session_factory
        self._sources: dict[str, tuple[IngesterFactory, str | None]] = {}
        self._running: bool = False

    def register(
        self,
        source_name: str,
        ingester_factory: IngesterFactory,
        cron: str | None,
    ) -> None:
        """Register a source and its ingester factory.

        Parameters
        ----------
        source_name:
            Unique source identifier (e.g. ``"fda_ndc"``).
        ingester_factory:
            Zero-argument callable that returns a fresh :class:`DataSourceIngester`.
        cron:
            Cron expression string, or ``None`` for manual-only sources.
        """
        self._sources[source_name] = (ingester_factory, cron)
        logger.info(
            "Ingestion source registered",
            extra={"ingest_source": source_name, "ingest_cron": cron},
        )

    async def start(self) -> None:
        """Blocking coroutine — run until cancelled.

        On each tick:
        1. Upsert schedule rows in the database.
        2. Check each enabled source for a due run.
        3. Skip sources with an in-flight run (status='running').
        4. Fire a run if the cron expression says it is time.
        5. Update ``next_run_at`` for all sources.
        """
        self._running = True
        logger.info(
            "IngestionScheduler started",
            extra={"ingest_tick_interval": _TICK_INTERVAL_SECONDS},
        )
        await self._upsert_schedules()

        while self._running:
            try:
                await self._tick()
            except Exception:
                logger.exception("Scheduler tick error")
            await asyncio.sleep(_TICK_INTERVAL_SECONDS)

    async def stop(self) -> None:
        """Signal the scheduler to stop after the current tick completes."""
        self._running = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _upsert_schedules(self) -> None:
        """Ensure a schedule row exists for every registered source."""
        with self._session_factory() as session:
            for source_name, (_, cron) in self._sources.items():
                existing = session.execute(
                    select(IngestionSchedule).where(
                        IngestionSchedule.source == source_name
                    )
                ).scalar_one_or_none()

                if existing is None:
                    next_run = _next_run_at(cron) if cron else None
                    schedule = IngestionSchedule(
                        source=source_name,
                        cron_expression=cron,
                        enabled=True,
                        next_run_at=next_run,
                    )
                    session.add(schedule)
                else:
                    # Update cron expression if it changed
                    if existing.cron_expression != cron:
                        existing.cron_expression = cron
                    if existing.next_run_at is None and cron:
                        existing.next_run_at = _next_run_at(cron)
                session.commit()

    async def _tick(self) -> None:
        """Single scheduler tick — check all sources and fire if due."""
        now = datetime.now(UTC)

        with self._session_factory() as session:
            schedules = session.execute(
                select(IngestionSchedule)
            ).scalars().all()

            for schedule in schedules:
                source_name = schedule.source
                if source_name not in self._sources:
                    continue

                if not schedule.enabled:
                    continue

                cron = schedule.cron_expression
                if cron is None:
                    continue  # Manual-only

                # Skip if already running
                if self._is_in_flight(session, source_name):
                    logger.debug(
                        "Skipping in-flight source",
                        extra={"ingest_source": source_name},
                    )
                    continue

                # Check if due
                if schedule.next_run_at is None or schedule.next_run_at <= now:
                    logger.info(
                        "Firing scheduled ingestion run",
                        extra={"ingest_source": source_name, "ingest_cron": cron},
                    )
                    task = asyncio.create_task(self._fire(source_name))
                    # Store reference to prevent garbage collection before completion
                    self._running_tasks: set = getattr(self, "_running_tasks", set())
                    self._running_tasks.add(task)
                    task.add_done_callback(self._running_tasks.discard)

                # Update next_run_at regardless
                schedule.next_run_at = _next_run_at(cron, now)
                session.commit()

    def _is_in_flight(self, session: Session, source_name: str) -> bool:
        """Return True if there is a running run for this source."""
        row = session.execute(
            select(IngestionRun).where(
                IngestionRun.source == source_name,
                IngestionRun.status == "running",
            )
        ).scalar_one_or_none()
        return row is not None

    async def _fire(self, source_name: str) -> None:
        """Create a fresh ingester and execute a run."""
        ingester_factory, _ = self._sources[source_name]
        with self._session_factory() as session:
            ingester = ingester_factory()
            ingester._db = session
            try:
                result = await ingester.run(run_type="auto_scheduled")
                logger.info(
                    "Scheduled run finished",
                    extra={
                        "ingest_source": source_name,
                        "ingest_status": result.status,
                        "ingest_records_processed": result.records_processed,
                    },
                )
            except Exception:
                logger.exception(
                    "Scheduled run error",
                    extra={"ingest_source": source_name},
                )

            # Update last_success_at and last_run_id on the schedule row
            if hasattr(result, "run_id") and result.run_id is not None:
                schedule = session.execute(
                    select(IngestionSchedule).where(
                        IngestionSchedule.source == source_name
                    )
                ).scalar_one_or_none()
                if schedule is not None:
                    schedule.last_run_id = result.run_id
                    if result.status == "completed":
                        schedule.last_success_at = datetime.now(UTC)
                    session.commit()


def _next_run_at(cron_expression: str, after: datetime | None = None) -> datetime:
    """Return the next scheduled datetime for *cron_expression*.

    Uses croniter's ``get_next()`` method with UTC reference time.
    """
    base = after or datetime.now(UTC)
    # croniter expects naive datetime; we strip tz and re-attach UTC
    naive_base = base.replace(tzinfo=None)
    cron = croniter(cron_expression, naive_base)
    next_naive: datetime = cron.get_next(datetime)
    return next_naive.replace(tzinfo=UTC)


__all__ = [
    "DEFAULT_SCHEDULES",
    "IngesterFactory",
    "IngestionScheduler",
]
