"""PA request submission, evaluation, and status routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.schemas import (
    CopayEPARequest,
    CopayEPAResponse,
    CriteriaResultResponse,
    ErrorResponse,
    PAEvaluateRequest,
    PAResponse,
    PAStatusQuery,
    PAStatusResponse,
    PASubmitRequest,
)
from src.services.pa_lifecycle import (
    PALifecycleError,
    check_pa_status,
    create_copay_epa_first_fill,
    create_pa,
    evaluate_pa,
)

router = APIRouter(prefix="/pa-requests", tags=["PA Requests"])


def _get_db(request: Request):
    """Extract DB session from request state (injected by middleware)."""
    return request.state.db


def _get_tenant_id(request: Request) -> uuid.UUID:
    """Extract tenant_id from request headers."""
    header = request.headers.get("x-tenant-id")
    if not header:
        raise HTTPException(status_code=400, detail="Missing x-tenant-id header")
    try:
        return uuid.UUID(header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid x-tenant-id format")


@router.post(
    "",
    response_model=PAResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse}},
)
async def submit_pa(
    body: PASubmitRequest,
    request: Request,
) -> PAResponse:
    """Submit a new prior authorization request."""
    db = _get_db(request)
    tenant_id = _get_tenant_id(request)

    try:
        pa = create_pa(
            db,
            tenant_id=tenant_id,
            member_id=body.member_id,
            prescriber_npi=body.prescriber_npi,
            drug_ndc=body.drug_ndc,
            drug_name=body.drug_name,
            source=body.source,
            plan_id=body.plan_id,
            priority=body.priority,
            program_id=body.program_id,
            clinical_data=body.clinical_data,
        )
        db.commit()
        return PAResponse.model_validate(pa)
    except PALifecycleError as exc:
        db.rollback()
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/{pa_request_id}/evaluate",
    response_model=CriteriaResultResponse,
)
async def evaluate_pa_request(
    pa_request_id: uuid.UUID,
    body: PAEvaluateRequest,
    request: Request,
) -> CriteriaResultResponse:
    """Evaluate a PA request against clinical criteria."""
    db = _get_db(request)
    tenant_id = _get_tenant_id(request)

    try:
        result = evaluate_pa(
            db, pa_request_id, tenant_id,
            member_age=body.member_age,
            member_diagnoses=body.member_diagnoses,
            step_therapy_history=body.step_therapy_history,
            lab_results=body.lab_results,
            member_bmi=body.member_bmi,
            member_comorbidities=body.member_comorbidities,
            lifestyle_intervention_date=body.lifestyle_intervention_date,
        )
        db.commit()
        return CriteriaResultResponse(
            auto_approve=result.auto_approve,
            reasons=result.reasons,
            missing_info=result.missing_info,
        )
    except PALifecycleError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/status",
    response_model=PAStatusResponse,
)
async def get_pa_status(
    member_id: uuid.UUID,
    drug_ndc: str,
    request: Request,
) -> PAStatusResponse:
    """Check PA status for a member+drug combination (consumed by adjudication)."""
    db = _get_db(request)
    tenant_id = _get_tenant_id(request)

    result = check_pa_status(db, tenant_id, member_id, drug_ndc)
    return PAStatusResponse(**result)


@router.post(
    "/{pa_request_id}/copay-epa",
    response_model=CopayEPAResponse,
    status_code=201,
)
async def create_copay_first_fill(
    pa_request_id: uuid.UUID,
    body: CopayEPARequest,
    request: Request,
) -> CopayEPAResponse:
    """Create a copay ePA first-fill record."""
    db = _get_db(request)
    tenant_id = _get_tenant_id(request)

    try:
        record = create_copay_epa_first_fill(
            db, pa_request_id, tenant_id,
            manufacturer_program_id=body.manufacturer_program_id,
            first_fill_amount=body.first_fill_amount,
            first_fill_date=body.first_fill_date,
        )
        db.commit()
        return CopayEPAResponse.model_validate(record)
    except PALifecycleError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
