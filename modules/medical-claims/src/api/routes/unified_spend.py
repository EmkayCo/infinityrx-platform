"""Unified drug spend endpoints."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.api.schemas.unified_spend import UnifiedSpendListResponse, UnifiedSpendResponse, DuplicationResponse
from src.services.unified_spend_service import UnifiedDrugSpendService

router = APIRouter(prefix="/unified-spend", tags=["unified-spend"])


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


@router.get("", response_model=UnifiedSpendListResponse)
async def list_unified_spend(
    request: Request,
    ndc: str | None = Query(default=None),
    benefit_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = UnifiedDrugSpendService(db)

    items, total = svc.list_spend(
        tenant_id=tenant_id,
        ndc=ndc,
        benefit_type=benefit_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return JSONResponse(
        content=UnifiedSpendListResponse(
            items=[UnifiedSpendResponse.model_validate(i) for i in items],
            total=total,
        ).model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/member/{member_id}", response_model=UnifiedSpendListResponse)
async def member_drug_timeline(
    request: Request, member_id: uuid.UUID
) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = UnifiedDrugSpendService(db)

    items = svc.get_member_timeline(tenant_id, member_id)
    return JSONResponse(
        content=UnifiedSpendListResponse(
            items=[UnifiedSpendResponse.model_validate(i) for i in items],
            total=len(items),
        ).model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/duplications", response_model=list[DuplicationResponse])
async def get_therapeutic_duplications(request: Request) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = UnifiedDrugSpendService(db)

    duplications = svc.detect_therapeutic_duplications(tenant_id)
    result = []
    for d in duplications:
        result.append(
            DuplicationResponse(
                member_id=d["member_id"],
                member_id_display=d["member_id_display"],
                ndc=d["ndc"],
                drug_name=d["drug_name"],
                date_of_service=d["date_of_service"],
                pharmacy_record=UnifiedSpendResponse.model_validate(d["pharmacy_record"]),
                medical_record=UnifiedSpendResponse.model_validate(d["medical_record"]),
            )
        )
    return JSONResponse(
        content=[r.model_dump(mode="json") for r in result],
        headers={"Cache-Control": "no-store"},
    )
