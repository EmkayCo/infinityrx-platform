"""Job seed — registers system jobs in the core_jobs table.

Idempotent: safe to call multiple times. Inserts missing system jobs
and leaves existing rows unchanged.

CONCERN-3 fix (P0a v2): ``exclusion_refresh`` existed as a handler in
``job_handler.py`` but was never seeded into ``core_jobs``, so the
scheduler never picked it up.  This module seeds it at 03:00 UTC daily
(after OIG/SAM loaders complete, which run at 01:00 UTC and 02:00 UTC
in the production cron table).

Usage — called from app startup (``src/main.py``) after DB is ready:
    from src.jobs.seed import seed_system_jobs
    seed_system_jobs(session)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import Job

logger = logging.getLogger("core.jobs.seed")

# ---------------------------------------------------------------------------
# System job definitions
# ---------------------------------------------------------------------------

# Each entry:  (job_type, name, schedule_cron, config)
# schedule_cron: standard 5-field cron (minute hour dom month dow)
# "0 3 * * *" = 03:00 UTC daily

_SYSTEM_JOBS: list[tuple[str, str, str, dict[str, Any]]] = [
    (
        "exclusion_refresh",
        "Daily Exclusion List Refresh",
        "0 3 * * *",
        {},
    ),
    (
        "verify_audit_chain",
        "Daily Audit Hash Chain Verification",
        "0 4 * * *",
        {},
    ),
]


def seed_system_jobs(session: Session) -> int:
    """Insert any missing system jobs.  Returns count of rows inserted."""
    inserted = 0
    now = datetime.now(timezone.utc)

    # Compute next_run_at using croniter if available; else leave NULL
    # (the scheduler recomputes on first tick via compute_next_run).
    try:
        from .scheduler import compute_next_run
        _compute = compute_next_run
    except Exception:
        _compute = None  # type: ignore[assignment]

    for job_type, name, schedule, config in _SYSTEM_JOBS:
        existing = session.query(Job).filter(Job.job_type == job_type).first()
        if existing is not None:
            continue  # already seeded — do not overwrite

        next_run = None
        if _compute is not None:
            try:
                next_run = _compute(schedule, now)
            except Exception:
                pass

        job = Job(
            name=name,
            job_type=job_type,
            schedule=schedule,
            status="active",
            config=config,
            created_at=now,
            next_run_at=next_run,
        )
        session.add(job)
        inserted += 1
        logger.info(
            "excl_job_seeded",
            extra={"job_type": job_type, "schedule": schedule},
        )

    if inserted > 0:
        session.flush()
        logger.info("excl_jobs_seed_complete excl_count=%d", inserted)

    return inserted
