"""Hub integration API routes.

POST /hub/bv            - hub partner benefit verification
POST /hub/bi            - hub partner benefit investigation
POST /hub/status-update - hub partner status update
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.schemas import (
    HubBIRequest,
    HubBVRequest,
    HubResponse,
    HubStatusUpdateRequest,
)
from src.services.benefit_investigation import (
    BenefitDataProvider,
    BenefitInvestigationService,
)
from src.services.eligibility import (
    EligibilityService,
    MemberDataProvider,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hub"])


def _get_eligibility_service() -> EligibilityService:
    return EligibilityService(data_provider=MemberDataProvider())


def _get_benefit_service() -> BenefitInvestigationService:
    return BenefitInvestigationService(data_provider=BenefitDataProvider())


def _parse_tenant(x_tenant_id: str = Header(...)) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid x-tenant-id header") from exc


@router.post("/hub/bv", response_model=HubResponse)
async def hub_benefit_verification(
    body: HubBVRequest,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: EligibilityService = Depends(_get_eligibility_service),
) -> HubResponse:
    """Hub partner benefit verification endpoint."""
    result = await svc.verify_eligibility(
        tenant_id=tenant_id,
        member_id=body.member_id,
        as_of_date=body.as_of_date,
    )

    logger.info(
        "Hub BV request processed",
        extra={
            "svc_name": "ebv.hub",
            "ebv_hub_partner": body.hub_partner_id,
            "ebv_member_id": body.member_id,
        },
    )

    return HubResponse(
        success=True,
        data={
            "member_id": result.member_id,
            "status": result.status.value,
            "plan_name": result.plan_name,
            "coverage_start": str(result.coverage_start) if result.coverage_start else None,
            "coverage_end": str(result.coverage_end) if result.coverage_end else None,
            "benefit_phase": result.benefit_phase.value if result.benefit_phase else None,
        },
    )


@router.post("/hub/bi", response_model=HubResponse)
async def hub_benefit_investigation(
    body: HubBIRequest,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: BenefitInvestigationService = Depends(_get_benefit_service),
) -> HubResponse:
    """Hub partner benefit investigation endpoint."""
    result = await svc.investigate_benefit(
        tenant_id=tenant_id,
        member_id=body.member_id,
        drug_ndc=body.drug_ndc,
    )

    logger.info(
        "Hub BI request processed",
        extra={
            "svc_name": "ebv.hub",
            "ebv_hub_partner": body.hub_partner_id,
            "ebv_member_id": body.member_id,
        },
    )

    return HubResponse(
        success=True,
        data={
            "member_id": result.member_id,
            "drug_ndc": result.drug_ndc,
            "is_covered": result.is_covered,
            "formulary_status": result.formulary_status.value if result.formulary_status else None,
            "tier": result.tier,
            "member_cost_estimate": str(result.member_cost_estimate),
            "pa_required": result.requirements.pa_required,
            "st_required": result.requirements.st_required,
            "specialty_pharmacy_required": result.specialty_pharmacy_required,
            "accumulator_status": result.accumulator_status.value,
        },
    )


@router.post("/hub/status-update", response_model=HubResponse)
async def hub_status_update(
    body: HubStatusUpdateRequest,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
) -> HubResponse:
    """Hub partner status update endpoint (PA decisions, status changes)."""
    logger.info(
        "Hub status update received",
        extra={
            "svc_name": "ebv.hub",
            "ebv_hub_partner": body.hub_partner_id,
            "ebv_member_id": body.member_id,
            "ebv_status_type": body.status_type,
        },
    )

    return HubResponse(
        success=True,
        data={
            "hub_partner_id": body.hub_partner_id,
            "member_id": body.member_id,
            "status_type": body.status_type,
            "acknowledged": True,
        },
    )
