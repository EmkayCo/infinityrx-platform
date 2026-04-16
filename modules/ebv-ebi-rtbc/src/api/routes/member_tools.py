"""Member-facing tools API routes.

POST /member/cost-estimate          - drug cost estimate
POST /member/pharmacy-compare       - pharmacy cost comparison
GET  /member/{member_id}/progress   - deductible/OOP progress
GET  /member/{member_id}/id-card    - digital ID card
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.schemas import (
    AccumulatorProgressResponse,
    AlternativeResponse,
    BenefitProgressResponse,
    CostEstimateRequest,
    CostEstimateResponse,
    DigitalIDCardResponse,
    PharmacyCompareRequest,
    PharmacyCompareResponse,
    PharmacyOptionResponse,
)
from src.services.benefit_investigation import (
    BenefitDataProvider,
    BenefitInvestigationService,
)
from src.services.eligibility import (
    EligibilityService,
    MemberDataProvider,
)
from src.services.member_tools import (
    IDCardDataProvider,
    MemberToolsService,
    PharmacyDataProvider,
)

router = APIRouter(tags=["member-tools"])


def _get_member_tools_service() -> MemberToolsService:
    """Provide MemberToolsService. Overridden in tests."""
    return MemberToolsService(
        eligibility_service=EligibilityService(data_provider=MemberDataProvider()),
        benefit_service=BenefitInvestigationService(data_provider=BenefitDataProvider()),
        pharmacy_provider=PharmacyDataProvider(),
        id_card_provider=IDCardDataProvider(),
    )


def _parse_tenant(x_tenant_id: str = Header(...)) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid x-tenant-id header") from exc


@router.post("/member/cost-estimate", response_model=CostEstimateResponse)
async def drug_cost_estimate(
    body: CostEstimateRequest,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: MemberToolsService = Depends(_get_member_tools_service),
) -> CostEstimateResponse:
    """Estimate a member's out-of-pocket cost for a specific drug."""
    result = await svc.drug_cost_estimate(
        tenant_id=tenant_id,
        member_id=body.member_id,
        drug_ndc=body.drug_ndc,
    )
    return CostEstimateResponse(
        member_id=result.member_id,
        drug_ndc=result.drug_ndc,
        estimated_cost=result.estimated_cost,
        tier=result.tier,
        formulary_status=result.formulary_status,
        alternatives=[
            AlternativeResponse(
                ndc=a.ndc, name=a.name, tier=a.tier, cost=a.cost, savings=a.savings,
            )
            for a in result.alternatives
        ],
    )


@router.post("/member/pharmacy-compare", response_model=PharmacyCompareResponse)
async def pharmacy_cost_comparison(
    body: PharmacyCompareRequest,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: MemberToolsService = Depends(_get_member_tools_service),
) -> PharmacyCompareResponse:
    """Compare drug cost across nearby pharmacies sorted by distance."""
    result = await svc.pharmacy_cost_comparison(
        tenant_id=tenant_id,
        member_id=body.member_id,
        drug_ndc=body.drug_ndc,
        lat=body.lat,
        lng=body.lng,
    )
    return PharmacyCompareResponse(
        member_id=result.member_id,
        drug_ndc=result.drug_ndc,
        pharmacies=[
            PharmacyOptionResponse(
                npi=p.npi, name=p.name, distance_mi=p.distance_mi,
                cost=p.cost, in_network=p.in_network, preferred=p.preferred,
            )
            for p in result.pharmacies
        ],
    )


@router.get("/member/{member_id}/progress", response_model=BenefitProgressResponse)
async def benefit_progress(
    member_id: str,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: MemberToolsService = Depends(_get_member_tools_service),
) -> BenefitProgressResponse:
    """Get deductible/OOP progress bars and projected trajectory."""
    result = await svc.benefit_progress(
        tenant_id=tenant_id,
        member_id=member_id,
    )

    ded = None
    if result.deductible:
        ded = AccumulatorProgressResponse(
            limit=result.deductible.limit,
            met=result.deductible.met,
            remaining=result.deductible.remaining,
            pct_met=result.deductible.pct_met,
        )

    oop = None
    if result.oop:
        oop = AccumulatorProgressResponse(
            limit=result.oop.limit,
            met=result.oop.met,
            remaining=result.oop.remaining,
            pct_met=result.oop.pct_met,
        )

    return BenefitProgressResponse(
        member_id=result.member_id,
        deductible=ded,
        oop=oop,
        benefit_year_start=result.benefit_year_start,
        benefit_year_end=result.benefit_year_end,
        projected_deductible_met_date=result.projected_deductible_met_date,
        projected_oop_met_date=result.projected_oop_met_date,
    )


@router.get("/member/{member_id}/id-card", response_model=DigitalIDCardResponse)
async def digital_id_card(
    member_id: str,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: MemberToolsService = Depends(_get_member_tools_service),
) -> Any:
    """Retrieve the member's digital ID card."""
    result = await svc.digital_id_card(
        tenant_id=tenant_id,
        member_id=member_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="ID card not found for member")

    return DigitalIDCardResponse(
        member_id=result.member_id,
        member_name=result.member_name,
        group=result.group,
        bin=result.bin,
        pcn=result.pcn,
        rxbin=result.rxbin,
        copays=result.copays,
        pharmacy_help_phone=result.pharmacy_help_phone,
        version=result.version,
    )
