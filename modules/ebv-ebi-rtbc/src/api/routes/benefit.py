"""Benefit investigation API routes.

POST /benefit/investigate   - deep benefit investigation for a drug/member
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.schemas import (
    AlternativeResponse,
    BenefitInvestigateRequest,
    BenefitInvestigateResponse,
    CostBreakdownResponse,
    CoverageRequirementsResponse,
    QLInfoResponse,
)
from src.services.benefit_investigation import (
    BenefitDataProvider,
    BenefitInvestigationService,
)

router = APIRouter(tags=["benefit"])


def _get_benefit_service() -> BenefitInvestigationService:
    """Provide BenefitInvestigationService. Overridden in tests."""
    return BenefitInvestigationService(data_provider=BenefitDataProvider())


def _parse_tenant(x_tenant_id: str = Header(...)) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid x-tenant-id header") from exc


@router.post("/benefit/investigate", response_model=BenefitInvestigateResponse)
async def investigate_benefit(
    body: BenefitInvestigateRequest,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: BenefitInvestigationService = Depends(_get_benefit_service),
) -> BenefitInvestigateResponse:
    """Perform a deep benefit investigation for a drug/member combination."""
    result = await svc.investigate_benefit(
        tenant_id=tenant_id,
        member_id=body.member_id,
        drug_ndc=body.drug_ndc,
        plan_id=body.plan_id,
    )

    ql_info = None
    if result.requirements.ql_info:
        ql_info = QLInfoResponse(
            ql_type=result.requirements.ql_info.ql_type.value,
            max_quantity=result.requirements.ql_info.max_quantity,
            days_supply=result.requirements.ql_info.days_supply,
        )

    return BenefitInvestigateResponse(
        member_id=result.member_id,
        drug_ndc=result.drug_ndc,
        is_covered=result.is_covered,
        formulary_status=result.formulary_status.value if result.formulary_status else None,
        tier=result.tier,
        requirements=CoverageRequirementsResponse(
            pa_required=result.requirements.pa_required,
            st_required=result.requirements.st_required,
            ql_info=ql_info,
        ),
        cost_breakdown=CostBreakdownResponse(
            copay=result.cost_breakdown.copay,
            coinsurance=result.cost_breakdown.coinsurance,
            deductible_applied=result.cost_breakdown.deductible_applied,
            total_member_cost=result.cost_breakdown.total_member_cost,
        ),
        member_cost_estimate=result.member_cost_estimate,
        alternatives=[
            AlternativeResponse(
                ndc=a.ndc, name=a.name, tier=a.tier, cost=a.cost, savings=a.savings,
            )
            for a in result.alternatives
        ],
        specialty_pharmacy_required=result.specialty_pharmacy_required,
        site_of_care=result.site_of_care,
        accumulator_status=result.accumulator_status.value,
    )
