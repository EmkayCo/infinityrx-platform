"""SP-1 Plan C Task B2 -- Bank Settlements GET router.

Two endpoints (GET-only; mutations are Plan C B3 scope):
  GET  /api/v1/billing/bank-settlements        list bank settlements for tenant (bare array)
  GET  /api/v1/billing/bank-settlements/{id}   single bank settlement or 404

# BankSettlement ORM is Plan D scope; this stub returns empty until then.
Contract shape: BankSettlementSchema in packages/contract/src/impls/paysync/types.ts.
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

logger = logging.getLogger("billing.api.bank_settlements")

router = APIRouter(prefix="/api/v1/billing/bank-settlements", tags=["bank-settlements"])


def _no_store(data: object, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


@router.get("")
async def list_bank_settlements(
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    # BankSettlement ORM is Plan D scope; returns empty until then.
    return _no_store([])


@router.get("/{settlement_id}")
async def get_bank_settlement(
    settlement_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    # BankSettlement ORM is Plan D scope; always 404 until then.
    raise HTTPException(status_code=404, detail="Bank settlement not found")
