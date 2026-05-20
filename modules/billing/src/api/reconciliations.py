"""SP-1 Plan C Task B2 -- Reconciliations GET router.

Two endpoints (GET-only; mutations are Plan C B3 scope):
  GET  /api/v1/billing/reconciliations        list reconciliations for tenant (bare array)
  GET  /api/v1/billing/reconciliations/{id}   single reconciliation or 404

# Reconciliation ORM is Plan D scope; this stub returns empty until then.
Contract shape: ReconciliationSchema in packages/contract/src/impls/paysync/types.ts.
RBAC: reads are all roles.
Cache-Control: no-store on all responses per contract rule.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId

logger = logging.getLogger("billing.api.reconciliations")

router = APIRouter(prefix="/api/v1/billing/reconciliations", tags=["reconciliations"])


def _no_store(data: object, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


@router.get("")
async def list_reconciliations(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    # Reconciliation ORM is Plan D scope; returns empty until then.
    return _no_store([])


@router.get("/{reconciliation_id}")
async def get_reconciliation(
    reconciliation_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    # Reconciliation ORM is Plan D scope; always 404 until then.
    raise HTTPException(status_code=404, detail="Reconciliation not found")
