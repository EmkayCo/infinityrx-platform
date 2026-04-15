"""Market access + what-if simulation API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from shared.auth.dependencies import get_current_user

from src.api.dependencies import DBSession, TenantId
from src.api.schemas.market_access import (
    AccumulatorExposureResponse,
    BenefitDesignScenarioCreate,
    BenefitDesignScenarioResponse,
    CoverageLandscapeResponse,
    CompetitivePositioningResponse,
    PAARequirementResponse,
    PayerMixResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from src.services.market_access import MarketAccessService

router = APIRouter(
    prefix="/market-access",
    tags=["market-access"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/coverage", response_model=CoverageLandscapeResponse)
async def coverage_landscape(
    ndc: str,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = MarketAccessService(db, tenant_id)
    return svc.formulary_coverage_landscape(ndc)


@router.get("/competitive", response_model=CompetitivePositioningResponse)
async def competitive_positioning(
    gpi: str,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = MarketAccessService(db, tenant_id)
    return svc.competitive_positioning(gpi)


@router.get("/pa-requirements", response_model=PAARequirementResponse)
async def pa_requirements(
    ndc: str,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = MarketAccessService(db, tenant_id)
    return svc.pa_requirement_mapping(ndc)


@router.get("/payer-mix", response_model=PayerMixResponse)
async def payer_mix(
    ndc: str,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = MarketAccessService(db, tenant_id)
    return svc.payer_mix_analysis(ndc)


@router.get("/accumulator-exposure", response_model=AccumulatorExposureResponse)
async def accumulator_exposure(
    ndc: str,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = MarketAccessService(db, tenant_id)
    return svc.accumulator_exposure(ndc)


@router.post("/plans/{plan_id}/what-if", response_model=WhatIfResponse)
async def what_if_simulation(
    plan_id: uuid.UUID,
    body: WhatIfRequest,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = MarketAccessService(db, tenant_id)
    try:
        result = svc.what_if_simulation(
            plan_id,
            proposed_config=body.proposed_benefit_config,
            sample_count=body.sample_claims_count,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
