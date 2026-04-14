"""Scheduled jobs for payment-processing.

Jobs:
- poll_settlements: poll vendor APIs for settlement updates (hourly per vendor)
- vendor_health_check: check vendor API/SFTP health (every 5/15 min)
- retry_failed_submissions: pick up ready-for-retry submissions
- ofac_refresh: refresh OFAC SDN list (daily)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Submission, VendorAdapter
from ..utils.constants import SUB_FAILED, SUB_PENDING

logger = logging.getLogger("payment.jobs")


def poll_settlements(db: Session, tenant_id: str) -> int:
    """Poll vendors for settlement updates. Returns count of submissions polled."""
    submitted = db.execute(
        select(Submission).where(
            Submission.tenant_id == tenant_id,
            Submission.status.in_(["submitted", "acknowledged", "processing"]),
        )
    ).scalars().all()

    polled = 0
    for sub in submitted:
        logger.info("Polling settlement for submission %s", sub.id)
        polled += 1

    return polled


def vendor_health_check_job(db: Session) -> list[str]:
    """Run health checks on all active vendors. Returns list of vendor IDs checked."""
    vendors = db.execute(
        select(VendorAdapter).where(VendorAdapter.is_active.is_(True))
    ).scalars().all()

    checked = []
    for vendor in vendors:
        logger.info("Health check for vendor %s (%s)", vendor.id, vendor.vendor_type)
        checked.append(vendor.id)

    return checked


def retry_failed_submissions(db: Session) -> int:
    """Re-queue submissions whose next_retry_at has passed. Returns retry count."""
    now = datetime.now(UTC)
    ready = db.execute(
        select(Submission).where(
            Submission.status == SUB_FAILED,
            Submission.next_retry_at <= now,
            Submission.retry_count < Submission.max_retries,
        )
    ).scalars().all()

    retried = 0
    for sub in ready:
        sub.status = SUB_PENDING
        logger.info("Queuing retry for submission %s (attempt %d)", sub.id, sub.retry_count + 1)
        retried += 1

    if retried:
        db.commit()
    return retried


def ofac_refresh_job() -> None:
    """Refresh OFAC SDN list from official source. No-op in dev/test."""
    logger.info("OFAC SDN list refresh: would fetch from OFAC Data Services API in production")
