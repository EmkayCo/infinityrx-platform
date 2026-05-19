"""Daily audit hash-chain verification job.

Scheduled at 03:00 UTC per D14 + .claude/rules/hipaa-2026.md:
    "MUST run daily integrity verification job."
    "MUST compute entry_hash on EVERY audit log write -- never write with empty hash."

Walks ThresholdConfigAudit rows in chronological order per tenant,
verifies each entry's prev_entry_hash matches the prior entry's entry_hash.
Logs CRITICAL + alerts on any break.

Also verifies no entry has an empty entry_hash (write-time invariant).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("reclaimrx.jobs.audit_chain")


def verify_audit_hash_chain(
    session: Session,
    *,
    tenant_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Walk ThresholdConfigAudit entries, verify hash chain integrity.

    R6 WARN-2 fix: plain def (NOT async def). Body uses sync session.execute()
    against a sync Session, which would block the asyncio event loop for the
    full table-walk duration if called directly from a coroutine. The scheduler
    wrapper in main.py lifespan calls it via asyncio.to_thread() so the sync
    work runs in a worker thread and the event loop stays responsive.

    Args:
        session: SQLAlchemy Session (sync).
        tenant_id: If provided, verify only entries for this tenant.
            If None, verifies all tenants (used in scheduled daily run).

    Returns:
        dict with keys: status ('ok'|'alert'|'no_entries'), breaks (int),
        empty_hashes (int), entries_checked (int), checked_at (ISO-8601).
    """
    from src.models.tables import ThresholdConfigAudit  # noqa: PLC0415 -- local import

    # R1 CONCERN 8 fix: deterministic ordering across same-timestamp rows.
    # Without the secondary id key, two entries written in the same millisecond
    # can swap order across runs, producing non-deterministic hash-chain verification.
    q = select(ThresholdConfigAudit).order_by(
        ThresholdConfigAudit.tenant_id,
        ThresholdConfigAudit.changed_at,
        ThresholdConfigAudit.id,
    )
    if tenant_id is not None:
        q = q.where(ThresholdConfigAudit.tenant_id == str(tenant_id))

    entries = session.execute(q).scalars().all()

    if not entries:
        return {
            "status": "no_entries",
            "breaks": 0,
            "empty_hashes": 0,
            "entries_checked": 0,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    breaks = 0
    empty_hashes = 0
    prev_by_tenant: dict[str, str | None] = {}

    for entry in entries:
        tid = entry.tenant_id

        # Check for empty entry_hash (write-time invariant from hipaa-2026.md)
        if not entry.entry_hash:
            empty_hashes += 1
            logger.critical(
                "reclaimrx.audit_chain.empty_entry_hash",
                extra={
                    "svc_entry_id": str(entry.id),
                    "svc_tenant_id": tid,
                    "audit_action": "audit_chain_verification",
                },
            )

        # Check prev_entry_hash matches prior entry's entry_hash
        expected_prev = prev_by_tenant.get(tid)
        if expected_prev is not None and entry.prev_entry_hash != expected_prev:
            breaks += 1
            logger.critical(
                "reclaimrx.audit_chain.hash_break",
                extra={
                    "svc_entry_id": str(entry.id),
                    "svc_tenant_id": tid,
                    "svc_expected_prev_prefix16": expected_prev[:16],
                    "svc_actual_prev_prefix16": str(entry.prev_entry_hash)[:16],
                    "audit_action": "audit_chain_verification",
                },
            )

        prev_by_tenant[tid] = entry.entry_hash

    status = "ok" if (breaks == 0 and empty_hashes == 0) else "alert"
    result = {
        "status": status,
        "breaks": breaks,
        "empty_hashes": empty_hashes,
        "entries_checked": len(entries),
        "checked_at": datetime.now(UTC).isoformat(),
    }
    if status == "alert":
        logger.critical(
            "reclaimrx.audit_chain.verification_failed",
            extra={"svc_breaks": breaks, "svc_empty_hashes": empty_hashes,
                   "audit_action": "audit_chain_verification"},
        )
    else:
        logger.info(
            "reclaimrx.audit_chain.verification_ok",
            extra={"svc_entries_checked": len(entries),
                   "audit_action": "audit_chain_verification"},
        )
    return result
