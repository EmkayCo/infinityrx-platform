"""PA decision and appeal routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import (
    PAAppealRequest,
    PAAppealResponse,
    PADecisionRequest,
    PADecisionResponse,
)
from src.services.pa_lifecycle import (
    PALifecycleError,
    decide_pa,
    submit_appeal,
)

router = APIRouter(prefix="/pa-requests", tags=["PA Decisions"])


def _get_db(request: Request):
    """Extract DB session from request state."""
    return request.state.db


def _get_tenant_id(request: Request) -> uuid.UUID:
    """Extract and validate tenant_id from request headers."""
    header = request.headers.get("x-tenant-id")
    if not header:
        raise HTTPException(status_code=400, detail="Missing x-tenant-id header")
    try:
        return uuid.UUID(header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid x-tenant-id format")


@router.post(
    "/{pa_request_id}/decisions",
    response_model=PADecisionResponse,
    status_code=201,
)
async def record_decision(
    pa_request_id: uuid.UUID,
    body: PADecisionRequest,
    request: Request,
) -> PADecisionResponse:
    """Record a clinical reviewer's decision on a PA request."""
    db = _get_db(request)
    tenant_id = _get_tenant_id(request)

    try:
        decision = decide_pa(
            db, pa_request_id, tenant_id,
            decision=body.decision,
            reviewer_id=body.reviewer_id,
            approved_duration_days=body.approved_duration_days,
            approved_quantity=body.approved_quantity,
            review_notes=body.review_notes,
        )
        db.commit()
        return PADecisionResponse.model_validate(decision)
    except PALifecycleError as exc:
        db.rollback()
        if "not found" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/{pa_request_id}/appeals",
    response_model=PAAppealResponse,
    status_code=201,
)
async def file_appeal(
    pa_request_id: uuid.UUID,
    body: PAAppealRequest,
    request: Request,
) -> PAAppealResponse:
    """Submit an appeal against a PA denial."""
    db = _get_db(request)
    tenant_id = _get_tenant_id(request)

    try:
        appeal = submit_appeal(
            db, pa_request_id, tenant_id,
            appeal_level=body.appeal_level,
            appeal_type=body.appeal_type,
            regulatory_deadline=body.regulatory_deadline,
        )
        db.commit()
        return PAAppealResponse.model_validate(appeal)
    except PALifecycleError as exc:
        db.rollback()
        if "not found" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))
