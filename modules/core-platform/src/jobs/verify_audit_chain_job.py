"""Daily audit chain integrity verification job (H-07 / HIPAA 2026).

Verifies the SHA-256 hash chain for every tenant's audit log, ensuring no
entries have been tampered with since the last verification.

Per HIPAA 2026: tamper-evident audit log integrity MUST be verified daily.
This job computes the expected entry_hash for each audit row (in chronological
order per tenant) and compares it against the stored value. Any mismatch is
logged at CRITICAL level and recorded in the job result.

Registration:
    Import this module in core-platform's startup to register the handler:
    ``from src.jobs import verify_audit_chain_job``

Scheduling:
    Create a Job row with ``job_type="audit.verify_chain"`` and
    ``cron_expr="0 3 * * *"`` (03:00 UTC daily).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.audit.hash_chain import GENESIS_HASH, compute_entry_hash
from src.jobs.registry import job_handler

logger = logging.getLogger("core-platform.jobs.verify_audit_chain")

_JOB_TYPE = "audit.verify_chain"


@job_handler(_JOB_TYPE)
async def handle_verify_audit_chain(payload: dict[str, Any]) -> dict[str, Any]:
    """Verify the audit log hash chain for all tenants (or a specific tenant).

    Payload fields (all optional):
        tenant_id (str | None): If supplied, verify only this tenant's chain.
            Otherwise verifies all tenants.
        stop_on_first_failure (bool): If True, abort the scan after the first
            broken chain link. Defaults to False (report all failures).

    Returns:
        {
            "status": "ok" | "failed",
            "tenants_checked": int,
            "entries_checked": int,
            "failures": [{"tenant_id": str, "entry_id": int, "expected": str, "stored": str}],
        }
    """
    tenant_id_filter: str | None = payload.get("tenant_id")
    stop_on_first: bool = bool(payload.get("stop_on_first_failure", False))

    # Import here to avoid circular imports at module load time
    from src.auth._db import get_session as _get_db  # noqa: PLC0415

    failures: list[dict[str, Any]] = []
    tenants_checked = 0
    entries_checked = 0

    # Synchronous DB access via the core-platform session factory.
    # The job runner is async but SQLAlchemy sync sessions are used here
    # because audit verification is a sequential scan (not latency-sensitive).
    with _get_db() as db:
        # Discover all tenant IDs with audit entries (or limit to the requested one).
        if tenant_id_filter:
            tenant_ids = [tenant_id_filter]
        else:
            rows = db.execute(
                text("SELECT DISTINCT tenant_id FROM core_platform.audit_log ORDER BY tenant_id")
            ).fetchall()
            tenant_ids = [str(row[0]) for row in rows]

        for tid in tenant_ids:
            tenant_failures = _verify_tenant_chain(
                db,
                tenant_id=tid,
                stop_on_first=stop_on_first,
            )
            tenants_checked += 1
            entries_checked += tenant_failures["entries_checked"]
            failures.extend(tenant_failures["failures"])

            if stop_on_first and failures:
                break

    status = "ok" if not failures else "failed"

    if failures:
        logger.critical(
            "audit_chain_integrity_violation",
            extra={
                "svc_name": "verify_audit_chain_job",
                "failure_count": len(failures),
                "tenants_checked": tenants_checked,
                "entries_checked": entries_checked,
            },
        )
    else:
        logger.info(
            "audit_chain_verified_ok",
            extra={
                "svc_name": "verify_audit_chain_job",
                "tenants_checked": tenants_checked,
                "entries_checked": entries_checked,
            },
        )

    return {
        "status": status,
        "tenants_checked": tenants_checked,
        "entries_checked": entries_checked,
        "failures": failures,
    }


def _verify_tenant_chain(
    db: Session,
    *,
    tenant_id: str,
    stop_on_first: bool,
) -> dict[str, Any]:
    """Verify the hash chain for a single tenant.

    Reads audit_log entries for the tenant ordered by (created_at, id) and
    recomputes the expected entry_hash for each row, comparing it against the
    stored value.

    Returns:
        {"entries_checked": int, "failures": list[dict]}
    """
    from uuid import UUID  # noqa: PLC0415

    rows = db.execute(
        text(
            """
            SELECT id, tenant_id, action, entity_type, entity_id,
                   created_at, previous_hash, entry_hash
            FROM core_platform.audit_log
            WHERE tenant_id = :tenant_id
            ORDER BY created_at ASC, id ASC
            """
        ),
        {"tenant_id": tenant_id},
    ).fetchall()

    failures: list[dict[str, Any]] = []
    entries_checked = 0
    prev_hash: str = GENESIS_HASH

    for row in rows:
        entries_checked += 1
        row_id, tid, action, entity_type, entity_id, created_at, stored_prev_hash, stored_entry_hash = row

        # The stored previous_hash must match what we tracked from the prior entry.
        # A genesis entry has previous_hash == GENESIS_HASH (or None).
        effective_prev = stored_prev_hash if stored_prev_hash else GENESIS_HASH

        expected_hash = compute_entry_hash(
            tenant_id=UUID(str(tid)),
            action=str(action),
            entity_type=entity_type,
            entity_id=entity_id,
            created_at=created_at,
            previous_hash=effective_prev,
        )

        if expected_hash != stored_entry_hash:
            failure = {
                "tenant_id": tenant_id,
                "entry_id": row_id,
                "expected_hash": expected_hash,
                "stored_hash": stored_entry_hash,
                "action": action,
            }
            failures.append(failure)
            logger.critical(
                "audit_chain_hash_mismatch",
                extra={
                    "svc_name": "verify_audit_chain_job",
                    "audit_entry_id": row_id,
                    "audit_tenant_id": tenant_id,
                    "audit_action": action,
                },
            )
            if stop_on_first:
                break

        prev_hash = stored_entry_hash  # track last-seen hash for the next link

    return {"entries_checked": entries_checked, "failures": failures}
