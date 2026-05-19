"""DLQ depth monitor -- event-bus.md rule:
    "MUST monitor DLQ depth -- alert when > 0 for > 15 minutes."

Runs every 15 minutes via ReclaimRxScheduler (cron: "*/15 * * * *").
Queries EventDLQEntry for 'queued' status. Logs CRITICAL if depth > 0
and oldest entry is older than the threshold.

Advisory-lock hash (for graph job reference in Plan A3):
    import zlib
    lock_key = zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF
    # NEVER use Python hash() -- PYTHONHASHSEED-randomized (codex BLOCK 7)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("reclaimrx.jobs.dlq_monitor")

_DLQ_DURATION_THRESHOLD_MINUTES = 15  # event-bus.md: "> 0 for > 15 minutes"


async def check_dlq_depth(engine: "AsyncEngine", *, _now: datetime | None = None) -> dict[str, Any]:
    """Count queued DLQ entries; alert if oldest queued is older than 15 minutes.

    R1 BLOCK 9 fix: event-bus.md says "alert when depth > 0 for > 15 minutes",
    NOT "alert immediately when depth > 0". A queued entry that has only just
    failed is not yet an operational incident -- the dispatcher retry loop may
    drain it on its next pass. We alert only when the OLDEST queued entry has
    persisted past the duration threshold.

    Returns:
        dict: status ('ok' | 'monitoring' | 'alert'),
              queued_count (int),
              oldest_first_failed_at (ISO-8601 or None),
              oldest_age_minutes (float or None),
              threshold_minutes (15),
              checked_at (ISO-8601).
    """
    from sqlalchemy import func  # noqa: PLC0415
    from shared.db.models.events import EventDLQEntry  # noqa: PLC0415

    now = _now if _now is not None else datetime.now(UTC)

    # R6 BLOCK-19 fix: use await conn.execute(stmt) directly on the AsyncConnection
    # instead of wrapping in an AsyncSession. Direct conn.execute is the supported
    # SQLAlchemy idiom for non-ORM read-only aggregates, avoids session overhead,
    # and lets the test fixture be a plain async mock.
    async with engine.connect() as conn:
        result = await conn.execute(
            select(
                func.count(EventDLQEntry.id),
                func.min(EventDLQEntry.first_failed_at),
            ).where(EventDLQEntry.status == "queued")
        )
        count, oldest_first_failed_at = result.one()

    age_minutes: float | None = None
    if oldest_first_failed_at is not None:
        # Defensive: DB may return naive datetime depending on driver -- coerce to UTC.
        if oldest_first_failed_at.tzinfo is None:
            oldest_first_failed_at = oldest_first_failed_at.replace(tzinfo=UTC)
        age_minutes = (now - oldest_first_failed_at).total_seconds() / 60.0

    if count == 0:
        status = "ok"
    elif age_minutes is not None and age_minutes > _DLQ_DURATION_THRESHOLD_MINUTES:
        status = "alert"
    else:
        # Depth > 0 but oldest entry is within the 15-minute grace window.
        status = "monitoring"

    log = {
        "svc_dlq_queued_count": count,
        "svc_dlq_status": status,
        "svc_dlq_oldest_age_minutes": age_minutes,
        "svc_dlq_threshold_minutes": _DLQ_DURATION_THRESHOLD_MINUTES,
        "audit_action": "dlq_depth_check",
    }

    if status == "alert":
        logger.critical("reclaimrx.dlq.depth_alert", extra=log)
    elif status == "monitoring":
        logger.warning("reclaimrx.dlq.depth_monitoring", extra=log)
    else:
        logger.info("reclaimrx.dlq.depth_ok", extra=log)

    return {
        "status": status,
        "queued_count": count,
        "oldest_first_failed_at": (
            oldest_first_failed_at.isoformat() if oldest_first_failed_at else None
        ),
        "oldest_age_minutes": age_minutes,
        "threshold_minutes": _DLQ_DURATION_THRESHOLD_MINUTES,
        "checked_at": now.isoformat(),
    }
