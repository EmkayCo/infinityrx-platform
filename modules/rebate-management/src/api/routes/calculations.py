"""Rebate calculation API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_tenant_id
from src.api.schemas.calculation import (
    AccrualRequest,
    CalculateRebatesRequest,
    CalculationResultResponse,
    ClaimLineInputSchema,
    RecognizeAccrualRequest,
)
from src.services.calculation import CalculationEngine, ClaimLineInput
from src.utils.money import ZERO

from decimal import Decimal

router = APIRouter(prefix="/calculations", tags=["calculations"])


@router.post("/run-period", response_model=CalculationResultResponse)
async def run_period_calculation(
    body: CalculateRebatesRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> Any:
    engine = CalculationEngine(db)
    claim_lines = [
        ClaimLineInput(
            ndc11=cl.ndc11,
            date_of_service=cl.date_of_service,
            units_dispensed=cl.units_dispensed,
            wac_per_unit=cl.wac_per_unit,
            sponsor_id=cl.sponsor_id,
            claim_id=cl.claim_id,
        )
        for cl in body.claim_lines
    ]
    market_shares = {k: Decimal(str(v)) for k, v in body.market_shares.items()}
    result = engine.run_period(
        tenant_id=tenant_id,
        period_start=body.period_start,
        period_end=body.period_end,
        claim_lines=claim_lines,
        market_shares=market_shares,
    )
    db.commit()
    ndc_dicts = [
        {
            "ndc11": r.ndc11,
            "units_dispensed": str(r.units_dispensed),
            "gross_wac": str(r.gross_wac),
            "base_rebate": str(r.base_rebate),
            "total_rebate": str(r.total_rebate),
        }
        for r in result.ndc_results
    ]
    return CalculationResultResponse(
        period_start=result.period_start,
        period_end=result.period_end,
        total_rebate=str(result.total_rebate),
        ndc_count=len(result.ndc_results),
        transaction_count=len(result.transaction_ids),
        results=ndc_dicts,
    )


@router.post("/accrue")
async def accrue_monthly(
    body: AccrualRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, str]:
    engine = CalculationEngine(db)
    accrual = engine.accrue_monthly(
        tenant_id=tenant_id,
        contract_id=body.contract_id,
        ndc11=body.ndc11,
        accrual_month=body.accrual_month,
        accrued_amount=body.accrued_amount,
    )
    db.commit()
    return {"id": str(accrual.id), "accrued_amount": str(accrual.accrued_amount)}


@router.post("/recognize-accrual")
async def recognize_accrual(
    body: RecognizeAccrualRequest,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict[str, Any]:
    engine = CalculationEngine(db)
    try:
        accrual = engine.recognize_accrual(
            tenant_id=tenant_id,
            accrual_id=body.accrual_id,
            actual_payment_id=body.actual_payment_id,
        )
        db.commit()
        return {"id": str(accrual.id), "recognized": accrual.recognized}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
