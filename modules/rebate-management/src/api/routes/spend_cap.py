"""Spend cap guarantee API routes."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_tenant_id
from src.services.spend_cap import SpendCapService

router = APIRouter(prefix="/spend-cap", tags=["spend-cap"])


class SpendCapCreateRequest(BaseModel):
    contract_id: uuid.UUID
    sponsor_id: uuid.UUID
    cap_type: str = "spend_ceiling"
    guarantee_ceiling: Decimal
    guarantee_period_start: date
    guarantee_period_end: date
    program_id: uuid.UUID | None = None
    refund_terms: dict | None = None


class MonthlyActualRequest(BaseModel):
    guarantee_id: uuid.UUID
    tracking_month: date
    actual_spend: Decimal


@router.post("", status_code=201)
async def create_guarantee(
    body: SpendCapCreateRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, str]:
    svc = SpendCapService(db)
    guarantee = svc.create_guarantee(
        tenant_id=tenant_id,
        contract_id=body.contract_id,
        sponsor_id=body.sponsor_id,
        cap_type=body.cap_type,
        guarantee_ceiling=body.guarantee_ceiling,
        guarantee_period_start=body.guarantee_period_start,
        guarantee_period_end=body.guarantee_period_end,
        program_id=body.program_id,
        refund_terms=body.refund_terms,
    )
    db.commit()
    return {"id": str(guarantee.id), "ceiling": str(guarantee.guarantee_ceiling)}


@router.post("/record-actual")
async def record_monthly_actual(
    body: MonthlyActualRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    svc = SpendCapService(db)
    try:
        record, alerts = svc.record_monthly_actual(
            tenant_id=tenant_id,
            guarantee_id=body.guarantee_id,
            tracking_month=body.tracking_month,
            actual_spend=body.actual_spend,
        )
        db.commit()
        return {
            "id": str(record.id),
            "cumulative_spend": str(record.cumulative_spend),
            "utilization_pct": str(record.utilization_pct),
            "refund_owed": str(record.refund_owed),
            "alerts": alerts,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{guarantee_id}/status")
async def get_guarantee_status(
    guarantee_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    svc = SpendCapService(db)
    try:
        return svc.get_status(tenant_id, guarantee_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
