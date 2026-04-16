"""GTN waterfall API routes."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_tenant_id
from src.services.gtn_waterfall import GTNWaterfallService
from src.utils.money import ZERO

router = APIRouter(prefix="/gtn-waterfall", tags=["gtn-waterfall"])


class GTNSnapshotRequest(BaseModel):
    ndc11: str
    snapshot_date: date
    wac: Decimal
    wholesaler_discount: Decimal = Decimal("0")
    prompt_pay_discount: Decimal = Decimal("0")
    rebates: Decimal = Decimal("0")
    chargebacks: Decimal = Decimal("0")
    copay_assistance: Decimal = Decimal("0")
    copay_misuse_leakage: Decimal = Decimal("0")
    admin_fees: Decimal = Decimal("0")
    drug_name: str | None = None
    program_id: uuid.UUID | None = None
    fwa_data_available: bool = False


@router.post("/snapshot", status_code=201)
async def upsert_snapshot(
    body: GTNSnapshotRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, str]:
    svc = GTNWaterfallService(db)
    snap = svc.upsert_snapshot(
        tenant_id=tenant_id,
        ndc11=body.ndc11,
        snapshot_date=body.snapshot_date,
        wac=body.wac,
        wholesaler_discount=body.wholesaler_discount,
        prompt_pay_discount=body.prompt_pay_discount,
        rebates=body.rebates,
        chargebacks=body.chargebacks,
        copay_assistance=body.copay_assistance,
        copay_misuse_leakage=body.copay_misuse_leakage,
        admin_fees=body.admin_fees,
        drug_name=body.drug_name,
        program_id=body.program_id,
        fwa_data_available=body.fwa_data_available,
    )
    db.commit()
    return {"id": str(snap.id), "net_price": str(snap.net_price), "gtn_ratio": str(snap.gtn_ratio)}


@router.get("/detail")
async def get_waterfall_detail(
    ndc11: str,
    snapshot_date: date,
    program_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    svc = GTNWaterfallService(db)
    snap = svc.get_waterfall(tenant_id, ndc11, snapshot_date, program_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Waterfall snapshot not found")
    return svc.get_waterfall_detail(snap)
