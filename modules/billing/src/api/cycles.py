"""SP-1 Plan B B1 fix -- Cycles router.

Exposes /api/v1/billing/cycles as the operator-facing "payment cycle" surface.
Backed by PaymentBatch rows; maps batch fields to the Cycle shape expected by
CyclesClient in packages/contract/src/impls/paysync/real.ts.

Why /cycles instead of using /payment-batches directly:
  CyclesClient was specced against an operator-friendly "cycle" concept (one
  billing period per tenant per route), while /payment-batches is an internal
  ledger concept that exposes raw batch mechanics. The thin mapping here keeps
  the TS contract stable without touching the existing /payment-batches surface
  that other billing code depends on.

Batch status -> Cycle status mapping:
  generated, validated           -> open
  pending_close, closing         -> closing
  approved, submitted, settled   -> closed
  (anything else)                -> error

Endpoints:
  GET  /api/v1/billing/cycles              list (paginated)
  GET  /api/v1/billing/cycles/{id}         get by id
  POST /api/v1/billing/cycles/{id}/close   operator closes a cycle
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId
from src.models.tables import PaymentBatch

logger = logging.getLogger("billing.api.cycles")

router = APIRouter(prefix="/api/v1/billing/cycles", tags=["cycles"])

# Batch status values that map to each cycle status.
_OPEN_STATUSES = {"generated", "validated"}
_CLOSING_STATUSES = {"pending_close", "closing"}
_CLOSED_STATUSES = {"approved", "submitted", "settled"}

_CYCLE_STATUS_BY_BATCH: dict[str, str] = {}
for _s in _OPEN_STATUSES:
    _CYCLE_STATUS_BY_BATCH[_s] = "open"
for _s in _CLOSING_STATUSES:
    _CYCLE_STATUS_BY_BATCH[_s] = "closing"
for _s in _CLOSED_STATUSES:
    _CYCLE_STATUS_BY_BATCH[_s] = "closed"

# Reverse map: cycle status -> set of batch statuses (for WHERE clause filtering)
_BATCH_STATUSES_FOR_CYCLE: dict[str, set[str]] = {
    "open": _OPEN_STATUSES,
    "closing": _CLOSING_STATUSES,
    "closed": _CLOSED_STATUSES,
    "error": set(),  # dynamic -- anything not in the above sets
}


def _batch_to_cycle(batch: PaymentBatch) -> dict[str, Any]:
    """Map a PaymentBatch row to the CycleSchema shape."""
    cycle_status = _CYCLE_STATUS_BY_BATCH.get(batch.status, "error")
    return {
        "id": str(batch.id),
        "tenant_id": str(batch.tenant_id),
        "period_label": batch.batch_number,
        "status": cycle_status,
        "window_closed_at": batch.settled_at.isoformat() if batch.settled_at else None,
        "origin_upload_id": None,  # PaymentBatch has no direct upload link; P2 gap
        "total_billed_amount": str(batch.total_amount) if batch.total_amount is not None else None,
        "claim_count": batch.ap_count,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
    }


@router.get("")
async def list_cycles(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None),
) -> JSONResponse:
    """List billing cycles (payment batches) for the tenant, in Cycle shape."""
    stmt = (
        select(PaymentBatch)
        .where(PaymentBatch.tenant_id == tenant_id)
        .order_by(PaymentBatch.created_at.desc())
        .limit(limit)
    )

    if status_filter is not None:
        batch_statuses = _BATCH_STATUSES_FOR_CYCLE.get(status_filter)
        if batch_statuses is not None and batch_statuses:
            stmt = stmt.where(PaymentBatch.status.in_(batch_statuses))
        elif status_filter == "error":
            # "error" = any status not in the known sets
            known = _OPEN_STATUSES | _CLOSING_STATUSES | _CLOSED_STATUSES
            stmt = stmt.where(PaymentBatch.status.not_in(known))
        else:
            # unknown cycle status filter -> empty result
            return JSONResponse(content={"results": [], "total": 0})

    batches = db.execute(stmt).scalars().all()
    results = [_batch_to_cycle(b) for b in batches]
    return JSONResponse(content={"results": results, "total": len(results)})


@router.get("/{cycle_id}")
async def get_cycle(
    cycle_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Get a single billing cycle by id."""
    stmt = select(PaymentBatch).where(
        PaymentBatch.id == cycle_id,
        PaymentBatch.tenant_id == tenant_id,
    )
    batch = db.execute(stmt).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found")
    return JSONResponse(content=_batch_to_cycle(batch))


@router.post("/{cycle_id}/close")
async def close_cycle(
    cycle_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Transition a cycle to 'closing' status (approver-initiated close action)."""
    stmt = select(PaymentBatch).where(
        PaymentBatch.id == cycle_id,
        PaymentBatch.tenant_id == tenant_id,
    )
    batch = db.execute(stmt).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found")

    batch.status = "closing"
    db.commit()
    db.refresh(batch)
    return JSONResponse(content=_batch_to_cycle(batch))