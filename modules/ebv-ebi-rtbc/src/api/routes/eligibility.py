"""Eligibility verification API routes.

POST /eligibility/verify    - single member verification
POST /eligibility/batch     - batch verification
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.schemas import (
    AccumulatorProgressResponse,
    CopayTierResponse,
    EligibilityBatchRequest,
    EligibilityResponse,
    EligibilityVerifyRequest,
)
from src.services.eligibility import (
    EligibilityService,
    MemberDataProvider,
)

router = APIRouter(tags=["eligibility"])


def _get_eligibility_service() -> EligibilityService:
    """Provide EligibilityService. Overridden in tests."""
    return EligibilityService(data_provider=MemberDataProvider())


def _parse_tenant(x_tenant_id: str = Header(...)) -> uuid.UUID:
    """Validate x-tenant-id header as UUID."""
    try:
        return uuid.UUID(x_tenant_id)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid x-tenant-id header") from exc


@router.post("/eligibility/verify", response_model=EligibilityResponse)
async def verify_eligibility(
    body: EligibilityVerifyRequest,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: EligibilityService = Depends(_get_eligibility_service),
) -> EligibilityResponse:
    """Verify a single member's eligibility."""
    result = await svc.verify_eligibility(
        tenant_id=tenant_id,
        member_id=body.member_id,
        as_of_date=body.as_of_date,
    )
    return _to_response(result)


@router.post("/eligibility/batch", response_model=list[EligibilityResponse])
async def batch_verify_eligibility(
    body: EligibilityBatchRequest,
    tenant_id: uuid.UUID = Depends(_parse_tenant),
    svc: EligibilityService = Depends(_get_eligibility_service),
) -> list[EligibilityResponse]:
    """Batch verify eligibility for multiple members."""
    results = await svc.batch_verify(
        tenant_id=tenant_id,
        member_ids=body.member_ids,
        as_of_date=body.as_of_date,
    )
    return [_to_response(r) for r in results]


def _to_response(result: Any) -> EligibilityResponse:
    deductible = None
    if result.deductible:
        deductible = AccumulatorProgressResponse(
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

    copay_summary = [
        CopayTierResponse(
            tier=c.tier,
            copay=c.copay,
            coinsurance_pct=c.coinsurance_pct,
        )
        for c in result.copay_summary
    ]

    return EligibilityResponse(
        member_id=result.member_id,
        status=result.status.value,
        plan_id=str(result.plan_id) if result.plan_id else None,
        plan_name=result.plan_name,
        group_id=str(result.group_id) if result.group_id else None,
        group_name=result.group_name,
        coverage_start=result.coverage_start,
        coverage_end=result.coverage_end,
        copay_summary=copay_summary,
        benefit_phase=result.benefit_phase.value if result.benefit_phase else None,
        deductible=deductible,
        oop=oop,
        response_time_ms=result.response_time_ms,
    )
