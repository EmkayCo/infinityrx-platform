"""ReclaimRx module scheduler -- asyncio.create_task + croniter pattern.

Mirrors the pattern from shared/data_ingestion/scheduler.py (audit 7).
Uses asyncio + croniter only; no third-party scheduler dependency.

Registered jobs (wired in create_app() lifespan):
  - cleanup_processed_events  cron: "0 1 * * *"   (01:00 UTC daily)
  - verify_audit_hash_chain   cron: "0 3 * * *"   (03:00 UTC daily per D14)
  - check_dlq_depth           cron: "*/15 * * * *" (every 15 min per event-bus.md)
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from croniter import croniter

logger = logging.getLogger("reclaimrx.scheduler")

_DEFAULT_TICK_SECONDS: float = 60.0

JobFn = Callable[[], Awaitable[None]]


class ReclaimRxScheduler:
    """Long-running cron scheduler for ReclaimRx jobs.

    Usage::

        scheduler = ReclaimRxScheduler()
        scheduler.register("cleanup", cleanup_fn, cron="0 1 * * *")
        task = asyncio.create_task(scheduler.start())
    """

    def __init__(self, tick_interval_seconds: float = _DEFAULT_TICK_SECONDS) -> None:
        self._tick_interval = tick_interval_seconds
        self._jobs: dict[str, tuple[JobFn, str, datetime | None]] = {}
        self._running = False
        self._running_tasks: set[asyncio.Task] = set()

    def register(self, name: str, fn: JobFn, *, cron: str) -> None:
        """Register a job with a cron expression.

        Args:
            name: Unique job name (used in logs).
            fn: Async callable; zero arguments; called when cron fires.
            cron: Standard 5-field cron expression (UTC).
        """
        next_run = _next_run(cron)
        self._jobs[name] = (fn, cron, next_run)
        logger.info(
            "reclaimrx.scheduler.job_registered",
            extra={"svc_job": name, "svc_cron": cron,
                   "svc_next_run": next_run.isoformat()},
        )

    async def start(self) -> None:
        """Blocking coroutine -- run until stop() is called.

        R8 BLOCK-25 fix: ALWAYS yield to the event loop between ticks via
        asyncio.sleep(self._tick_interval). A bare conditional skip would busy-loop
        when tick_interval_seconds=0 (unit test value), starving stop()/cancel().
        asyncio.sleep(0) still yields control to the loop once per tick.
        """
        self._running = True
        logger.info("reclaimrx.scheduler.started")
        while self._running:
            await self._tick()
            await asyncio.sleep(self._tick_interval)

    async def stop(self) -> None:
        """Stop after the current tick completes."""
        self._running = False

    async def _tick(self) -> None:
        now = datetime.now(UTC)
        for name, (fn, cron, next_run) in list(self._jobs.items()):
            if next_run is not None and next_run <= now:
                logger.info("reclaimrx.scheduler.firing", extra={"svc_job": name})
                task = asyncio.create_task(self._run_job(name, fn))
                self._running_tasks.add(task)
                task.add_done_callback(self._running_tasks.discard)
                self._jobs[name] = (fn, cron, _next_run(cron, after=now))

    async def _run_job(self, name: str, fn: JobFn) -> None:
        try:
            await fn()
        except Exception:
            logger.exception("reclaimrx.scheduler.job_error", extra={"svc_job": name})


def _next_run(cron_expr: str, after: datetime | None = None) -> datetime:
    base = (after or datetime.now(UTC)).replace(tzinfo=None)
    return croniter(cron_expr, base).get_next(datetime).replace(tzinfo=UTC)
