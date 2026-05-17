"""SP-1 Plan C Task B2 -- Payment Runs GET router.

Two endpoints (GET-only; mutations are Plan C B3 scope):
  GET  /api/v1/billing/payment-runs        list payment runs for tenant (bare array)
  GET  /api/v1/billing/payment-runs/{id}   single payment run or 404

# PaymentRun ORM is Plan D scope; this stub returns empty until then.
Contract shape: PaymentRunSchema in packages/contract/src/impls/paysync/types.ts.
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

logger = logging.getLogger("billing.api.payment_runs")

router = APIRouter(prefix="/api/v1/billing/payment-runs", tags=["payment-runs"])


def _no_store(data: object, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


@router.get("")
async def list_payment_runs(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    # PaymentRun ORM is Plan D scope; returns empty until then.
    return _no_store([])


@router.get("/{run_id}")
async def get_payment_run(
    run_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    # PaymentRun ORM is Plan D scope; always 404 until then.
    raise HTTPException(status_code=404, detail="Payment run not found")
