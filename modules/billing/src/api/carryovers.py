"""SP-1 Plan C Task B2 -- Carryovers GET router.

Two endpoints (GET-only; mutations are Plan C B3 scope):
  GET  /api/v1/billing/carryovers        list carryovers for tenant (bare array)
  GET  /api/v1/billing/carryovers/{id}   single carryover or 404

ORM: Carryover (billing.carryovers table, committed 5eb024f1).
Contract shape: CarryoverSchema in packages/contract/src/impls/paysync/types.ts.
RBAC: reads are all roles.
Cache-Control: no-store on all responses per contract rule.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId
from src.models.tables import Carryover

logger = logging.getLogger("billing.api.carryovers")

router = APIRouter(prefix="/api/v1/billing/carryovers", tags=["carryovers"])


def _no_store(data: object, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _carryover_to_dict(c: Carryover) -> dict:
    return {
        "id": str(c.id),
        "tenant_id": str(c.tenant_id),
        "ap_record_id": str(c.ap_record_id),
        "amount": str(c.amount),
        "reason": c.reason,
        "upload_id": str(c.upload_id) if c.upload_id is not None else None,
        "resolved": c.resolved,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at is not None else None,
        "resolved_by": str(c.resolved_by) if c.resolved_by is not None else None,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


@router.get("")
async def list_carryovers(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    stmt = (
        select(Carryover)
        .where(Carryover.tenant_id == tenant_id)
        .order_by(Carryover.created_at.desc())
    )
    rows = list(db.execute(stmt).scalars().all())
    return _no_store([_carryover_to_dict(r) for r in rows])


@router.get("/{carryover_id}")
async def get_carryover(
    carryover_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    stmt = select(Carryover).where(
        Carryover.id == carryover_id,
        Carryover.tenant_id == tenant_id,
    )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Carryover not found")
    return _no_store(_carryover_to_dict(row))
