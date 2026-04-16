"""API routes for the adjudication engine.

POST /claims/adjudicate — Submit a claim for real-time adjudication
POST /claims/reverse — Submit a reversal for a previously paid claim
GET  /claims/{claim_id} — Retrieve full claim detail
GET  /claims/{claim_id}/trace — Retrieve adjudication trace for a claim
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Header, HTTPException, Request

from shared.utils.money import money

from .schemas import (
    AdjudicateRequest,
    AdjudicationResponse,
    ClaimDetailResponse,
    ClaimTraceResponse,
    ErrorDetail,
    ErrorResponse,
    ReverseRequest,
)
from ..services.adjudication_pipeline import adjudicate, AdjudicationResult
from ..services.ncpdp_parser import (
    ClaimSegment,
    HeaderSegment,
    InsuranceSegment,
    ParsedClaim,
    PatientSegment,
    PricingSegment,
)

logger = logging.getLogger("adjudication_engine.api")

router = APIRouter(prefix="/claims", tags=["claims"])


def _validate_tenant_id(x_tenant_id: str) -> uuid.UUID:
    """Validate and return the tenant ID from the header."""
    try:
        return uuid.UUID(x_tenant_id)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "INVALID_TENANT",
                    "message": "Invalid x-tenant-id header",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
        ) from exc


def _result_to_response(result: AdjudicationResult) -> AdjudicationResponse:
    """Convert an AdjudicationResult to an API response."""
    dur_alerts_dicts = [
        {
            "check_type": a.check_type,
            "severity": a.severity,
            "description": a.description,
            "action": a.action,
        }
        for a in result.dur_alerts
    ]

    return AdjudicationResponse(
        claim_id=result.claim_id,
        status=result.status,
        transaction_type=result.transaction_type,
        ingredient_cost=str(result.ingredient_cost),
        dispensing_fee=str(result.dispensing_fee),
        patient_pay=str(result.patient_pay),
        plan_pay=str(result.plan_pay),
        total_amount=str(result.total_amount),
        pricing_model_used=result.pricing_model_used,
        reject_code=result.reject_code or None,
        reject_reason=result.reject_reason or None,
        reasons=result.reasons,
        dur_alerts=dur_alerts_dicts,
        copay_fraud_score=str(result.copay_fraud_score),
        accumulator_detected=result.accumulator_detected,
        override_applied=result.override_applied,
        therapeutic_alternative_ndc=result.therapeutic_alternative_ndc,
        therapeutic_alternative_savings=str(result.therapeutic_alternative_savings),
    )


@router.post("/adjudicate", response_model=AdjudicationResponse)
async def adjudicate_claim(
    body: AdjudicateRequest,
    x_tenant_id: str = Header(...),
) -> AdjudicationResponse:
    """Submit a pharmacy claim for real-time adjudication.

    Accepts a structured claim request, runs the 13-step adjudication
    pipeline, and returns the result with pricing, DUR alerts, and
    plain English reasons.
    """
    tenant_id = _validate_tenant_id(x_tenant_id)

    # Build ParsedClaim from the API request
    parsed = ParsedClaim(
        header=HeaderSegment(
            version="D0",
            transaction_code=body.transaction_code,
            bin_number=body.bin_number,
            pcn=body.pcn,
        ),
        patient=PatientSegment(
            cardholder_id=body.cardholder_id,
            date_of_birth=body.date_of_birth,
            person_code=body.person_code,
        ),
        insurance=InsuranceSegment(
            cardholder_id=body.cardholder_id,
            group_id=body.group_id,
            plan_id=body.plan_id,
            other_coverage_code=body.other_coverage_code,
        ),
        claim=ClaimSegment(
            ndc=body.drug_ndc,
            quantity_dispensed=money(Decimal(body.quantity)),
            days_supply=body.day_supply,
            daw_code=body.daw_code,
            compound_code=body.compound_code,
            other_coverage_code=body.other_coverage_code,
        ),
        pricing=PricingSegment(
            ingredient_cost_submitted=money(Decimal(body.ingredient_cost_submitted)),
            dispensing_fee_submitted=money(Decimal(body.dispensing_fee_submitted)),
            patient_paid_amount=money(Decimal(body.patient_paid_amount)),
            usual_and_customary=money(Decimal(body.usual_and_customary)),
        ),
    )

    result = adjudicate(parsed, tenant_id)

    logger.info(
        "api.claim_adjudicated",
        extra={
            "svc_claim_id": result.claim_id,
            "svc_status": result.status,
            "svc_tenant_id": str(tenant_id),
        },
    )

    return _result_to_response(result)


@router.post("/reverse", response_model=AdjudicationResponse)
async def reverse_claim(
    body: ReverseRequest,
    x_tenant_id: str = Header(...),
) -> AdjudicationResponse:
    """Submit a reversal for a previously paid claim.

    Creates a B2 reversal transaction that negates the original
    claim amounts.
    """
    tenant_id = _validate_tenant_id(x_tenant_id)

    # Build a minimal ParsedClaim for reversal
    parsed = ParsedClaim(
        header=HeaderSegment(
            version="D0",
            transaction_code="B2",
        ),
    )

    result = adjudicate(parsed, tenant_id)

    logger.info(
        "api.claim_reversed",
        extra={
            "svc_claim_id": result.claim_id,
            "svc_original_claim_id": body.original_claim_id,
            "svc_tenant_id": str(tenant_id),
        },
    )

    return _result_to_response(result)


@router.get("/{claim_id}", response_model=ClaimDetailResponse)
async def get_claim(
    claim_id: str,
    x_tenant_id: str = Header(...),
) -> ClaimDetailResponse:
    """Retrieve full claim detail by ID.

    Returns the complete claim record including pricing breakdown,
    DUR alerts, fraud scoring, and adjudication reasons.
    """
    tenant_id = _validate_tenant_id(x_tenant_id)

    # In production, this queries the database. For now, return 404.
    raise HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": "CLAIM_NOT_FOUND",
                "message": f"Claim {claim_id} not found",
                "correlation_id": str(uuid.uuid4()),
            }
        },
    )


@router.get("/{claim_id}/trace", response_model=ClaimTraceResponse)
async def get_claim_trace(
    claim_id: str,
    x_tenant_id: str = Header(...),
) -> ClaimTraceResponse:
    """Retrieve the adjudication trace for a claim.

    Returns the step-by-step trace of every adjudication decision
    made for the claim, including timing data for each step.
    """
    tenant_id = _validate_tenant_id(x_tenant_id)

    # In production, this queries the database. For now, return 404.
    raise HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": "CLAIM_NOT_FOUND",
                "message": f"Claim trace not found for {claim_id}",
                "correlation_id": str(uuid.uuid4()),
            }
        },
    )
