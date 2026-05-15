"""Job seed helpers — ensure platform-level Job rows exist at startup.

Platform-level jobs (tenant_id=NULL) are owned by the platform and must be
present for the scheduler to dispatch them. This module provides idempotent
upsert helpers called from the FastAPI lifespan.

H-07: daily audit chain integrity verification
    Job type:  ``audit.verify_chain``
    Schedule:  ``0 2 * * *`` (02:00 UTC every day)
    Tenant:    NULL (platform-wide — iterates all tenants internally)
"""

from __future__ import annotations

import logging

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
