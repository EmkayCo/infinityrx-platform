"""Denial management and appeal endpoints."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from shared.auth.dependencies import get_current_user

from src.api.schemas.denials import DenialResponse
from src.services.denial_service import DenialService

router = APIRouter(prefix="/denials", tags=["denials"], dependencies=[Depends(get_current_user)])  # CR-03


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


@router.get("", response_model=list[DenialResponse])
async def list_denials(
    request: Request,
    reason_code: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = DenialService(db)

    items, total = svc.list_denied_claims(
        tenant_id=tenant_id,
        reason_code=reason_code,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return JSONResponse(
        content=[DenialResponse.model_validate(c).model_dump(mode="json") for c in items],
        headers={"Cache-Control": "no-store"},
    )


@router.get("/analytics")
async def denial_analytics(
    request: Request,
    date_from: date = Query(...),
    date_to: date = Query(...),
) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = DenialService(db)

    analytics = svc.get_denial_analytics(tenant_id, date_from, date_to)
    # Convert date/Decimal to JSON-serializable
    import json
    from decimal import Decimal

    def _default(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, date):
            return obj.isoformat()
        raise TypeError(f"Not serializable: {type(obj)}")

    return JSONResponse(content=json.loads(json.dumps(analytics, default=_default)))
