"""HCPCS-NDC crosswalk endpoints."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from shared.auth.dependencies import get_current_user

from src.api.schemas.crosswalk import CrosswalkLookupResponse
from src.api.schemas.errors import ErrorEnvelope
from src.services.mapping_service import MappingService

router = APIRouter(prefix="/crosswalk", tags=["crosswalk"], dependencies=[Depends(get_current_user)])  # CR-03


def _get_db(request: Request):
    return request.state.db


def _get_tenant_id(request: Request) -> uuid.UUID:
    tid = request.headers.get("x-tenant-id")
    if not tid:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Missing x-tenant-id header")
    try:
        return uuid.UUID(tid)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid x-tenant-id: must be UUID")


@router.get("/unmapped", response_model=list[dict])
async def list_unmapped_claims(request: Request) -> list[dict]:
    """List claims pending manual NDC mapping."""
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = MappingService(db)
    claims = svc.list_unmapped_claims(tenant_id)
    return [
        {
            "id": str(c.id),
            "claim_number": c.claim_number,
            "procedure_code": c.procedure_code,
            "mapping_confidence": c.mapping_confidence,
        }
        for c in claims
    ]


@router.get("/{hcpcs_code}", response_model=CrosswalkLookupResponse)
async def lookup_hcpcs(
    request: Request,
    hcpcs_code: str,
    as_of: date | None = Query(default=None),
) -> CrosswalkLookupResponse:
    """Look up all NDCs mapped to a HCPCS code."""
    db = _get_db(request)
    svc = MappingService(db)
    return svc.lookup_crosswalk(hcpcs_code.upper(), as_of=as_of)


@router.post("/claims/{claim_id}/drug-mapping", response_model=dict)
async def set_manual_mapping(
    request: Request,
    claim_id: uuid.UUID,
    ndc: str = Query(..., description="11-digit NDC"),
) -> JSONResponse:
    """Override the drug mapping for a claim (manual mapping)."""
    from src.utils.validators import is_valid_ndc

    if not is_valid_ndc(ndc):
        err = ErrorEnvelope.make(code="INVALID_NDC", message="NDC must be exactly 11 digits", field="ndc")
        return JSONResponse(status_code=400, content=err.model_dump())

    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = MappingService(db)
    claim = svc.set_manual_mapping(tenant_id, claim_id, ndc)
    if claim is None:
        err = ErrorEnvelope.make(code="NOT_FOUND", message=f"Claim {claim_id} not found")
        return JSONResponse(status_code=404, content=err.model_dump())

    return JSONResponse(
        content={"claim_id": str(claim_id), "mapped_ndc": ndc, "mapping_confidence": "manual"}
    )
