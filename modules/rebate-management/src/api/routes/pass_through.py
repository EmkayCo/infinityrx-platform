"""Pass-through ledger API routes (CAA 2026 compliance)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_tenant_id
from src.api.schemas.pass_through import (
    PassThroughEntryRequest,
    PassThroughEntryResponse,
    ReconcileMonthRequest,
    ReconciliationResponse,
)
from src.services.pass_through import PassThroughError, PassThroughService

router = APIRouter(prefix="/pass-through", tags=["pass-through"])


@router.post("/record", status_code=201)
async def record_pass_through(
    body: PassThroughEntryRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, str]:
    svc = PassThroughService(db)
    try:
        entry = svc.record_pass_through(
            tenant_id=tenant_id,
            transaction_id=body.transaction_id,
            ndc11=body.ndc11,
            period_month=body.period_month,
            sponsor_id=body.sponsor_id,
            manufacturer_received=body.manufacturer_received,
            sponsor_passed=body.sponsor_passed,
            rebate_category=body.rebate_category,
            remittance_date=body.remittance_date,
        )
        db.commit()
        return {"id": str(entry.id), "entry_hash": entry.entry_hash}
    except PassThroughError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/entries")
async def list_entries(
    sponsor_id: uuid.UUID | None = None,
    period_month: date | None = None,
    ndc11: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> list[dict[str, Any]]:
    svc = PassThroughService(db)
    entries = svc.get_entries(tenant_id, sponsor_id, period_month, ndc11)
    return [
        {
            "id": str(e.id),
            "ndc11": e.ndc11,
            "period_month": e.period_month.isoformat(),
            "sponsor_id": str(e.sponsor_id),
            "manufacturer_received": str(e.manufacturer_received),
            "sponsor_passed": str(e.sponsor_passed),
            "rebate_category": e.rebate_category,
            "entry_hash": e.entry_hash,
        }
        for e in entries
    ]


@router.post("/reconcile")
async def reconcile_month(
    body: ReconcileMonthRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    svc = PassThroughService(db)
    recon = svc.reconcile_month(
        tenant_id=tenant_id,
        sponsor_id=body.sponsor_id,
        period_month=body.period_month,
        reconciled_by=body.reconciled_by,
        notes=body.notes,
    )
    db.commit()
    return {
        "id": str(recon.id),
        "total_received": str(recon.total_received),
        "total_passed": str(recon.total_passed),
        "difference": str(recon.difference),
        "is_balanced": recon.is_balanced,
    }
