"""Job seed helpers — ensure platform-level Job rows exist at startup.

Platform-level jobs (tenant_id=NULL) are owned by the platform and must be
present for the scheduler to dispatch them. This module provides idempotent
upsert helpers called from the FastAPI lifespan.

Two patterns coexist here:

1. ``ensure_audit_chain_job(db)`` — H-07 specific (audit chain integrity).
   Job type:  ``audit.verify_chain``
   Schedule:  ``0 2 * * *`` (02:00 UTC every day)
   Tenant:    NULL (platform-wide — iterates all tenants internally)

2. ``seed_system_jobs(db)`` — P0a CONCERN-3 (registry-driven seed for
   bulk system jobs). Currently seeds ``exclusion_refresh`` at 03:00 UTC,
   chained after OIG/SAM loaders complete (01:00/02:00 UTC).

Both helpers are idempotent — safe to call on every startup. The audit
chain job is intentionally kept as its own helper because H-07 has
specific schema/status invariants the platform must preserve across
restarts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Job
from .scheduler import compute_next_run

logger = logging.getLogger("core-platform.jobs.seed")

#: Cron expression for the daily audit chain verification (02:00 UTC).
AUDIT_CHAIN_VERIFY_CRON = "0 2 * * *"
#: Job type key — matches the @job_handler decorator in verify_audit_chain_job.
AUDIT_CHAIN_VERIFY_JOB_TYPE = "audit.verify_chain"


def ensure_audit_chain_job(db: Session) -> bool:
    """Idempotent upsert: create the audit chain verification Job row if absent.

    Safe to call on every startup — returns True when a new row is inserted,
    False when the row already exists (no update is performed so any manual
    schedule/status changes survive restarts).

    The job has tenant_id=NULL so the scheduler (which queries all active
    jobs, not just tenant-scoped ones) picks it up regardless of which tenant
    is in context.
    """
    existing = db.execute(
        select(Job).where(Job.job_type == AUDIT_CHAIN_VERIFY_JOB_TYPE)
    ).scalar_one_or_none()

    if existing is not None:
        logger.debug(
            "audit_chain_job_already_exists",
            extra={
                "svc_name": "jobs.seed",
                "job_id": existing.id,
                "job_status": existing.status,
            },
        )
        return False

    job = Job(
        tenant_id=None,  # platform-wide; visible to platform_admin only via API
        name="Daily audit chain integrity verification (H-07)",
        job_type=AUDIT_CHAIN_VERIFY_JOB_TYPE,
        schedule=AUDIT_CHAIN_VERIFY_CRON,
        status="active",
        config={},
        next_run_at=compute_next_run(AUDIT_CHAIN_VERIFY_CRON),
    )
    db.add(job)
    db.commit()
    logger.info(
        "audit_chain_job_seeded",
        extra={
            "svc_name": "jobs.seed",
            "job_type": AUDIT_CHAIN_VERIFY_JOB_TYPE,
            "schedule": AUDIT_CHAIN_VERIFY_CRON,
        },
    )
    return True


# ---------------------------------------------------------------------------
# Registry-driven system job seed (P0a CONCERN-3)
# ---------------------------------------------------------------------------

# Each entry:  (job_type, name, schedule_cron, config)
# schedule_cron: standard 5-field cron (minute hour dom month dow)
#
# NOTE: audit chain verification is owned by ``ensure_audit_chain_job()``
# above (H-07 spec). Do NOT add ``audit.verify_chain`` here or it will be
# double-seeded with conflicting job_type/schedule.
_SYSTEM_JOBS: list[tuple[str, str, str, dict[str, Any]]] = [
    (
        "exclusion_refresh",
        "Daily Exclusion List Refresh",
        "0 3 * * *",  # 03:00 UTC, after OIG/SAM loaders complete
        {},
    ),
]


def seed_system_jobs(session: Session) -> int:
    """Insert any missing system jobs from ``_SYSTEM_JOBS``.

    Returns the count of rows inserted. Idempotent — existing rows are
    not modified so manual schedule/status changes survive restarts.
    """
    inserted = 0
    now = datetime.now(timezone.utc)

    for job_type, name, schedule, config in _SYSTEM_JOBS:
        existing = session.query(Job).filter(Job.job_type == job_type).first()
        if existing is not None:
            continue  # already seeded — do not overwrite

        try:
            next_run = compute_next_run(schedule, now)
        except Exception:
            next_run = None

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
            "system_job_seeded",
            extra={"svc_name": "jobs.seed", "job_type": job_type, "schedule": schedule},
        )

    if inserted > 0:
        session.flush()
        logger.info(
            "system_jobs_seed_complete",
            extra={"svc_name": "jobs.seed", "inserted_count": inserted},
        )

    return inserted