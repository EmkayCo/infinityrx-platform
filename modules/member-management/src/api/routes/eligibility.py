"""Eligibility check API routes.

GET  /eligibility       — real-time eligibility check
POST /eligibility/270   — inbound 270, returns 271 response body
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from src.services.eligibility_service import (
    EligibilityRequest,
    EligibilityService,
)
from src.services.x12_270_271 import X12ParseError, X12Parser, X12ResponseBuilder

router = APIRouter(tags=["eligibility"])

_eligibility_svc = EligibilityService(redis=None)
_x12_parser = X12Parser()
_x12_builder = X12ResponseBuilder()
_control_counter = 0


def _next_control() -> int:
    global _control_counter
    _control_counter += 1
    return _control_counter


@router.get("/eligibility", summary="Real-time eligibility check")
async def check_eligibility(
    member_id: str = Query(...),
    rx_bin: str = Query(...),
    date_of_service: date = Query(...),
    rx_pcn: str | None = Query(default=None),
    rx_group: str | None = Query(default=None),
    cardholder_id: str | None = Query(default=None),
    person_code: str | None = Query(default=None),
    source: str = Query(default="api"),
    tenant_id: str | None = None,
) -> dict[str, Any]:
    req = EligibilityRequest(
        tenant_id=uuid.UUID(tenant_id) if tenant_id else uuid.uuid4(),
        member_id=member_id,
        rx_bin=rx_bin,
        rx_pcn=rx_pcn,
        rx_group=rx_group,
        cardholder_id=cardholder_id,
        person_code=person_code,
        date_of_service=date_of_service,
        source=source,
    )

    resp = await _eligibility_svc.check(None, req)

    result: dict[str, Any] = {
        "is_eligible": resp.is_eligible,
        "status": resp.status.value,
        "rejection_reason": resp.rejection_reason.value if resp.rejection_reason else None,
        "matched_member_id": str(resp.matched_member_id) if resp.matched_member_id else None,
        "plan_name": resp.plan_name,
        "coverage_type": resp.coverage_type,
        "cob_records": [
            {
                "payer_sequence": c.payer_sequence,
                "other_payer_name": c.other_payer_name,
                "other_payer_bin": c.other_payer_bin,
            }
            for c in resp.cob_records
        ],
    }
    return result


@router.post("/eligibility/270", summary="Process inbound 270, return 271")
async def process_270(request: Request) -> dict[str, Any]:
    body_bytes = await request.body()
    raw_270 = body_bytes.decode("utf-8", errors="replace")

    try:
        inquiry = _x12_parser.parse_270(raw_270)
    except X12ParseError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_270", "message": str(exc)}},
        )

    elig_req = EligibilityRequest(
        tenant_id=uuid.uuid4(),
        member_id=inquiry.member_id,
        rx_bin=inquiry.payer_id,
        date_of_service=inquiry.date_of_service,
        source="270_271",
    )
    elig_resp = await _eligibility_svc.check(None, elig_req)

    control = _next_control()
    if elig_resp.is_eligible:
        response_271 = _x12_builder.build_eligible_271(
            inquiry=inquiry,
            plan_name=elig_resp.plan_name or "UNKNOWN",
            coverage_type=elig_resp.coverage_type or "pharmacy",
            benefit_year_start=elig_resp.benefit_year_start or date(date.today().year, 1, 1),
            benefit_year_end=elig_resp.benefit_year_end or date(date.today().year, 12, 31),
            cob_records=[],
            control_number=control,
        )
    else:
        response_271 = _x12_builder.build_ineligible_271(
            inquiry=inquiry,
            rejection_reason=elig_resp.rejection_reason.value if elig_resp.rejection_reason else "UNKNOWN",
            control_number=control,
        )

    return {
        "is_eligible": elig_resp.is_eligible,
        "rejection_reason": elig_resp.rejection_reason.value if elig_resp.rejection_reason else None,
        "transaction_271": response_271,
    }
