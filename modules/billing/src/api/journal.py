"""SP-1 Plan D Task 3 -- Journal router with hash-chain sync verifier.

Endpoints:
  GET  /api/v1/billing/journal       -- list JournalEntry for tenant
  GET  /api/v1/billing/journal/{id}  -- single entry detail
  POST /api/v1/billing/journal/verify-chain -- synchronous chain verifier

Security:
  - All endpoints require a valid JWT (401 without token).
  - GET list/detail: all roles (auditor, operator, approver) may read.
  - POST verify-chain: auditor-only (per Plan D R1 B2 fix and spec §238).
  - Cache-Control: no-store on every response (journal entries are financial data).
  - PHI audit emitted on every list/detail response.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId
from src.models.tables import JournalEntry

logger = logging.getLogger("billing.api.journal")

router = APIRouter(prefix="/api/v1/billing/journal", tags=["journal"])

# Default limit for synchronous chain verification.  Configurable via env var
# so tests can exercise the too-large path cheaply.
_SYNC_LIMIT_DEFAULT = 10_000


def _sync_limit() -> int:
    try:
        return int(os.environ.get("PAYSYNC_HASH_CHAIN_SYNC_LIMIT", _SYNC_LIMIT_DEFAULT))
    except (TypeError, ValueError):
        return _SYNC_LIMIT_DEFAULT


# ---------------------------------------------------------------------------
# PHI audit helper
# ---------------------------------------------------------------------------


def _emit_phi_audit(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID
) -> None:
    """Best-effort phi_access audit. Never fails the request."""
    try:
        from shared.audit.client import emit_phi_access  # noqa: PLC0415

        emit_phi_access(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except Exception:
        logger.error(
            "billing.journal.phi_audit_failed",
            extra={
                "svc_entity_type": entity_type,
                "svc_entity_id": str(entity_id),
                "svc_tenant_id": str(tenant_id),
            },
        )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _entry_to_dict(entry: JournalEntry) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "tenant_id": str(entry.tenant_id),
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
        "entry_timestamp": entry.entry_timestamp.isoformat() if entry.entry_timestamp else None,
        "entry_type": entry.entry_type,
        "client_id": str(entry.client_id) if entry.client_id else None,
        "client_name": entry.client_name,
        "program_id": str(entry.program_id) if entry.program_id else None,
        "program_name": entry.program_name,
        "pay_to_entity_id": str(entry.pay_to_entity_id) if entry.pay_to_entity_id else None,
        "pay_to_entity_name": entry.pay_to_entity_name,
        "amount": str(entry.amount),
        "category": entry.category,
        "gl_account_code": entry.gl_account_code,
        "gl_class": entry.gl_class,
        "reference_type": entry.reference_type,
        "reference_id": str(entry.reference_id) if entry.reference_id else None,
        "description": entry.description,
        "exported_to_accounting": entry.exported_to_accounting,
        "exported_at": entry.exported_at.isoformat() if entry.exported_at else None,
        "export_reference": entry.export_reference,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "entry_hash": entry.entry_hash,
        "prev_hash": entry.prev_hash,
    }


def _no_store(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# Hash chain helpers (mirror the migration's algorithm exactly)
# ---------------------------------------------------------------------------


# Shared hash helpers live in models/journal_hash so the before_insert event
# listener can call them too. Re-export under the previous private names so
# the rest of this module is unchanged.
from src.models.journal_hash import (  # noqa: PLC0415
    canonical_amount as _canonical_amount,
    compute_entry_hash as _compute_entry_hash,
    naive_utc_iso as _naive_utc_iso,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_journal_entries(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
    limit: int = 100,
) -> JSONResponse:
    """List journal entries for the current tenant, newest first."""
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.tenant_id == tenant_id)
        .order_by(JournalEntry.created_at.desc())
        .limit(limit)
    )
    entries = db.execute(stmt).scalars().all()

    _emit_phi_audit(
        tenant_id=tenant_id,
        user_id=current_user.id,
        entity_type="journal_entry_list",
        entity_id=tenant_id,
    )

    return _no_store([_entry_to_dict(e) for e in entries])


_AUDITOR_ROLE = "auditor"


@router.post("/verify-chain")
async def verify_chain(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Synchronously verify the hash chain for the current tenant.

    RBAC: Auditor only.  Operators and approvers receive 403.

    Returns:
      {
        "verified": true | false | null,
        "too_large": bool,
        "job_id": null,          -- reserved for future async path
        "total_entries": int,
        "broken_at": str | null  -- entry id of first broken link, or null
      }

    If total_entries > PAYSYNC_HASH_CHAIN_SYNC_LIMIT, returns verified=null,
    too_large=true without iterating.
    """
    if not current_user.has_role(_AUDITOR_ROLE):
        raise HTTPException(
            status_code=403,
            detail="Only auditors can run hash-chain verification",
        )

    limit = _sync_limit()

    count_result = db.execute(
        select(func.count()).select_from(JournalEntry).where(
            JournalEntry.tenant_id == tenant_id
        )
    ).scalar_one()
    total: int = int(count_result)

    if total > limit:
        return _no_store({
            "verified": None,
            "too_large": True,
            "job_id": None,
            "total_entries": total,
            "broken_at": None,
        })

    # Iterate in chain order: created_at ASC, id ASC (ties broken by id).
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.tenant_id == tenant_id)
        .order_by(JournalEntry.created_at.asc(), JournalEntry.id.asc())
    )
    entries = db.execute(stmt).scalars().all()

    prev_hash: str | None = None
    for entry in entries:
        recomputed = _compute_entry_hash(entry, prev_hash)

        # Check 1: stored entry_hash must match recomputed hash.
        if entry.entry_hash != recomputed:
            return _no_store({
                "verified": False,
                "too_large": False,
                "job_id": None,
                "total_entries": total,
                "broken_at": str(entry.id),
            })

        # Check 2: stored prev_hash must match what we tracked as prev.
        if entry.prev_hash != prev_hash:
            return _no_store({
                "verified": False,
                "too_large": False,
                "job_id": None,
                "total_entries": total,
                "broken_at": str(entry.id),
            })

        prev_hash = entry.entry_hash

    return _no_store({
        "verified": True,
        "too_large": False,
        "job_id": None,
        "total_entries": total,
        "broken_at": None,
    })


@router.get("/{entry_id}")
async def get_journal_entry(
    entry_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Return a single journal entry for the current tenant."""
    entry = db.execute(
        select(JournalEntry).where(
            JournalEntry.id == entry_id,
            JournalEntry.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()

    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    _emit_phi_audit(
        tenant_id=tenant_id,
        user_id=current_user.id,
        entity_type="journal_entry",
        entity_id=entry_id,
    )

    return _no_store(_entry_to_dict(entry))
