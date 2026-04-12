"""Async job scheduler.

Picks up due jobs from core_jobs where next_run_at <= now and status='active',
creates a core_job_runs row, dispatches to the registered handler via JobRunner,
updates the run with outcome, and recomputes next_run_at from the cron
expression. Concurrency-safe via row-level locks (`with_for_update(skip_locked=True)`)
when run against Postgres — on SQLite the locking clause is ignored but the
unit tests still verify the exact same code path.

Emits `job.completed` / `job.failed` events on the shim event bus.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .._shim import events as event_bus
from ..models import Job, JobRun
from .registry import JobRegistry
from .runner import JobRunner

logger = logging.getLogger("core.jobs.scheduler")

EVENT_JOB_COMPLETED = "job.completed"
EVENT_JOB_FAILED = "job.failed"


def compute_next_run(cron_expr: str, base: Optional[datetime] = None) -> datetime:
    """Validate + compute next fire time for a cron expression."""
    base = base or datetime.now(timezone.utc)
    itr = croniter(cron_expr, base)
    return itr.get_next(datetime)


def validate_cron(cron_expr: str) -> bool:
    return croniter.is_valid(cron_expr)


class JobScheduler:
    def __init__(
        self,
        session_factory: sessionmaker,
        registry: JobRegistry,
        *,
        tick_seconds: float = 1.0,
    ) -> None:
        self._Session = session_factory
        self._registry = registry
        self._runner = JobRunner(registry)
        self._tick = tick_seconds
        self._stop = asyncio.Event()

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                await self.tick_once()
            except Exception:  # noqa: BLE001
                logger.exception("scheduler_tick_error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._tick)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()

    async def tick_once(self) -> int:
        """Pick up and dispatch all currently-due jobs. Returns count dispatched."""
        dispatched = 0
        now = datetime.now(timezone.utc)
        session: Session = self._Session()
        try:
            stmt = (
                select(Job)
                .where(Job.status == "active")
                .where(Job.next_run_at.is_not(None))
                .where(Job.next_run_at <= now)
            )
            try:
                stmt = stmt.with_for_update(skip_locked=True)
            except Exception:  # pragma: no cover — defensive for older SA
                pass
            due = list(session.execute(stmt).scalars())
            for job in due:
                run = JobRun(job_id=job.id, status="running", started_at=now)
                session.add(run)
                job.last_run_at = now
                # recompute next_run_at immediately so a second scheduler
                # won't pick up the same job if we're slow to commit
                if job.schedule:
                    job.next_run_at = compute_next_run(job.schedule, now)
                else:
                    job.next_run_at = None
                session.flush()
                run_id = run.id
                job_type = job.job_type
                payload = dict(job.config or {})
                tenant_id = job.tenant_id
                session.commit()

                result = await self._runner.run(job_type=job_type, payload=payload)
                ended = datetime.now(timezone.utc)
                run_row = session.get(JobRun, run_id)
                if run_row is not None:
                    run_row.status = result.status
                    run_row.ended_at = ended
                    run_row.duration_seconds = int((ended - now).total_seconds())
                    run_row.result = result.result or None
                    run_row.error_message = result.error_message
                    run_row.items_processed = result.items_processed
                    run_row.items_failed = result.items_failed
                    session.commit()

                topic = EVENT_JOB_COMPLETED if result.status == "succeeded" else EVENT_JOB_FAILED
                event_bus.publish(
                    topic,
                    {
                        "job_id": job.id,
                        "job_run_id": run_id,
                        "job_type": job_type,
                        "tenant_id": tenant_id,
                        "status": result.status,
                        "error_message": result.error_message,
                        "items_processed": result.items_processed,
                        "items_failed": result.items_failed,
                    },
                )
                dispatched += 1
        finally:
            session.close()
        return dispatched
