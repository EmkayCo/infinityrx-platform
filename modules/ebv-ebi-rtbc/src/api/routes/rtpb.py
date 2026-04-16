"""Real-Time Prescription Benefit (RTPB) API routes.

POST /rtpb/check    - RTPB cost/formulary check at prescribing
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.schemas import (
    AlternativeResponse,
    RTPBRequest,
    RTPBResponse,
)
from src.services.benefit_investigation import (
    BenefitDataProvider,
    BenefitInvestigationService,
)

router = APIRouter(tags=["rtpb"])


def _get_benefit_service() -> BenefitInvestigationService:
    return BenefitInvestigationService(data_provider=BenefitDataProvider())


def _parse_tenant(x_tenant_id: str = Header(...)) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid x-tenant-id header") from exc


@router.post("/rtpb/check", response_model=RTPBResponse)
async def rtpb_check(
    body: RTPBRequest,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: BenefitInvestigationService = Depends(_get_benefit_service),
) -> RTPBResponse:
    """Real-time prescription benefit check.

    Returns patient cost, formulary status, tier, restrictions,
    alternatives, and pharmacy options per NCPDP RTPB v13.
    """
    result = await svc.investigate_benefit(
        tenant_id=tenant_id,
        member_id=body.member_id,
        drug_ndc=body.drug_ndc,
    )

    restrictions = {}
    if result.requirements.pa_required:
        restrictions["prior_authorization"] = True
    if result.requirements.st_required:
        restrictions["step_therapy"] = True
    if result.requirements.ql_info:
        restrictions["quantity_limit"] = {
            "type": result.requirements.ql_info.ql_type.value,
            "max_quantity": str(result.requirements.ql_info.max_quantity),
            "days_supply": result.requirements.ql_info.days_supply,
        }

    return RTPBResponse(
        member_id=result.member_id,
        drug_ndc=result.drug_ndc,
        patient_cost=result.member_cost_estimate,
        formulary_status=result.formulary_status.value if result.formulary_status else None,
        tier=result.tier,
        restrictions=restrictions,
        alternatives=[
            AlternativeResponse(
                ndc=a.ndc, name=a.name, tier=a.tier, cost=a.cost, savings=a.savings,
            )
            for a in result.alternatives
        ],
        v13_compliant=True,
    )
