"""Claim CRUD endpoints.

All handlers are async per architecture rules.
PHI responses include Cache-Control: no-store header.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse

from src.api.schemas.claims import (
    ClaimCreate,
    ClaimUpdate,
    ClaimResponse,
    ClaimListResponse,
    ClaimStatusUpdate,
    FileUploadResponse,
)
from src.api.schemas.errors import ErrorEnvelope
from src.services.claim_service import ClaimService

router = APIRouter(prefix="/claims", tags=["claims"])


def _get_db(request: Request):
    return request.state.db


def _get_tenant_id(request: Request) -> uuid.UUID:
    tid = request.headers.get("x-tenant-id")
    if not tid:
        raise HTTPException(status_code=401, detail="Missing x-tenant-id header")
    try:
        return uuid.UUID(tid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid x-tenant-id: must be UUID")


@router.get("", response_model=ClaimListResponse)
async def list_claims(
    request: Request,
    status: str | None = Query(default=None),
    procedure_code: str | None = Query(default=None),
    ndc: str | None = Query(default=None),
    patient_member_id: str | None = Query(default=None),
    rendering_provider_npi: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> ClaimListResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = ClaimService(db)

    items, total = svc.list_claims(
        tenant_id=tenant_id,
        status=status,
        procedure_code=procedure_code,
        ndc=ndc,
        patient_member_id=patient_member_id,
        rendering_provider_npi=rendering_provider_npi,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return ClaimListResponse(
        items=[ClaimResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ClaimResponse, status_code=201)
async def create_claim(request: Request, body: ClaimCreate) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = ClaimService(db)

    try:
        claim = svc.create_claim(tenant_id, body)
    except Exception as exc:
        err = ErrorEnvelope.make(code="CLAIM_CREATE_FAILED", message=str(exc))
        return JSONResponse(status_code=422, content=err.model_dump())

    return JSONResponse(
        status_code=201,
        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(request: Request, claim_id: uuid.UUID) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = ClaimService(db)

    claim = svc.get_claim(tenant_id, claim_id)
    if claim is None:
        err = ErrorEnvelope.make(code="NOT_FOUND", message=f"Claim {claim_id} not found")
        return JSONResponse(status_code=404, content=err.model_dump())

    return JSONResponse(
        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


@router.put("/{claim_id}", response_model=ClaimResponse)
async def update_claim(request: Request, claim_id: uuid.UUID, body: ClaimUpdate) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = ClaimService(db)

    claim = svc.update_claim(tenant_id, claim_id, body)
    if claim is None:
        err = ErrorEnvelope.make(code="NOT_FOUND", message=f"Claim {claim_id} not found")
        return JSONResponse(status_code=404, content=err.model_dump())

    return JSONResponse(
        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


@router.post("/{claim_id}/status", response_model=ClaimResponse)
async def update_claim_status(
    request: Request, claim_id: uuid.UUID, body: ClaimStatusUpdate
) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = ClaimService(db)

    try:
        claim = svc.transition_status(
            tenant_id=tenant_id,
            claim_id=claim_id,
            new_status=body.status,
            denial_reason_code=body.denial_reason_code,
            denial_reason_description=body.denial_reason_description,
        )
    except ValueError as exc:
        err = ErrorEnvelope.make(code="INVALID_TRANSITION", message=str(exc))
        return JSONResponse(status_code=422, content=err.model_dump())

    if claim is None:
        err = ErrorEnvelope.make(code="NOT_FOUND", message=f"Claim {claim_id} not found")
        return JSONResponse(status_code=404, content=err.model_dump())

    return JSONResponse(
        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


@router.post("/upload", response_model=FileUploadResponse)
async def upload_claims_file(
    request: Request,
    file: UploadFile = File(...),
) -> FileUploadResponse:
    """Upload CSV/Excel file of medical claims.

    # TODO: implement CSV/Excel parsing with configurable column mapping
    """
    tenant_id = _get_tenant_id(request)
    # Stub response
    return FileUploadResponse(accepted=0, rejected=0, errors=[{"message": "File upload not yet implemented"}])
