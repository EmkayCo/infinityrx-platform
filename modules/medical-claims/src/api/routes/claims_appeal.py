"""Appeal endpoints on claim resource."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.schemas.claims import ClaimResponse
from src.api.schemas.denials import AppealCreate
from src.api.schemas.errors import ErrorEnvelope
from src.services.denial_service import DenialService

router = APIRouter(prefix="/claims", tags=["appeals"])


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


@router.post("/{claim_id}/appeal", response_model=ClaimResponse)
async def initiate_appeal(
    request: Request, claim_id: uuid.UUID, body: AppealCreate
) -> JSONResponse:
    """Initiate an appeal for a denied claim."""
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = DenialService(db)

    try:
        claim = svc.initiate_appeal(
            tenant_id=tenant_id,
            claim_id=claim_id,
            appeal_reason=body.appeal_reason,
            supporting_documentation=body.supporting_documentation,
        )
    except ValueError as exc:
        err = ErrorEnvelope.make(code="INVALID_APPEAL", message=str(exc))
        return JSONResponse(status_code=422, content=err.model_dump())

    if claim is None:
        err = ErrorEnvelope.make(code="NOT_FOUND", message=f"Claim {claim_id} not found")
        return JSONResponse(status_code=404, content=err.model_dump())

    return JSONResponse(
        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )
