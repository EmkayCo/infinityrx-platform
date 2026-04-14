"""Site-of-care analytics, 340B, and waste report endpoints."""
from __future__ import annotations

import uuid
from datetime import date

from decimal import ROUND_HALF_UP

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from src.services.detection_340b_service import Detection340bService
from src.clients.pharmacy_directory_client import PharmacyDirectoryClient
from src.api.schemas.claims import ClaimResponse

router = APIRouter(tags=["analytics"])


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


@router.get("/340b/claims", response_model=list[ClaimResponse])
async def get_340b_claims(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = Detection340bService(db, PharmacyDirectoryClient())

    items, total = svc.get_340b_claims(tenant_id, page=page, page_size=page_size)
    return JSONResponse(
        content={
            "items": [ClaimResponse.model_validate(c).model_dump(mode="json") for c in items],
            "total": total,
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/340b/summary")
async def get_340b_summary(request: Request) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)
    svc = Detection340bService(db, PharmacyDirectoryClient())

    from sqlalchemy import func
    from src.models.tables import ClaimRecord
    from decimal import Decimal

    total_340b = (
        db.query(func.count(ClaimRecord.id))
        .filter_by(tenant_id=tenant_id, is_340b=True)
        .scalar()
    ) or 0

    total_340b_paid = (
        db.query(func.sum(ClaimRecord.paid_amount))
        .filter_by(tenant_id=tenant_id, is_340b=True)
        .scalar()
    )
    paid_str = str(Decimal(str(total_340b_paid)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if total_340b_paid else "0.00"

    return JSONResponse(content={"total_340b_claims": total_340b, "total_paid_amount": paid_str})


@router.get("/waste/report")
async def get_waste_report(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)

    from sqlalchemy import func
    from src.models.tables import ClaimRecord
    from decimal import Decimal

    q = (
        db.query(
            ClaimRecord.procedure_code,
            ClaimRecord.rendering_provider_npi,
            func.sum(ClaimRecord.waste_quantity).label("total_waste_qty"),
            func.sum(ClaimRecord.waste_amount).label("total_waste_amount"),
            func.count(ClaimRecord.id).label("claim_count"),
        )
        .filter_by(tenant_id=tenant_id)
        .filter(ClaimRecord.waste_quantity != None)  # noqa: E711
    )
    if date_from:
        q = q.filter(ClaimRecord.date_of_service >= date_from)
    if date_to:
        q = q.filter(ClaimRecord.date_of_service <= date_to)

    rows = q.group_by(ClaimRecord.procedure_code, ClaimRecord.rendering_provider_npi).all()

    result = [
        {
            "procedure_code": row.procedure_code,
            "rendering_provider_npi": row.rendering_provider_npi,
            "total_waste_quantity": str(row.total_waste_qty or "0"),
            "total_waste_amount": str(Decimal(str(row.total_waste_amount or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "claim_count": row.claim_count,
        }
        for row in rows
    ]
    return JSONResponse(content=result)


@router.get("/site-of-care/analysis")
async def site_of_care_analysis(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)

    from sqlalchemy import func
    from src.models.tables import ClaimRecord
    from decimal import Decimal

    q = (
        db.query(
            ClaimRecord.site_of_care,
            func.count(ClaimRecord.id).label("claim_count"),
            func.sum(ClaimRecord.paid_amount).label("total_paid"),
        )
        .filter_by(tenant_id=tenant_id)
    )
    if date_from:
        q = q.filter(ClaimRecord.date_of_service >= date_from)
    if date_to:
        q = q.filter(ClaimRecord.date_of_service <= date_to)

    rows = q.group_by(ClaimRecord.site_of_care).all()
    result = [
        {
            "site_of_care": row.site_of_care or "unknown",
            "claim_count": row.claim_count,
            "total_paid": str(Decimal(str(row.total_paid or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        }
        for row in rows
    ]
    return JSONResponse(content=result)


@router.get("/site-of-care/opportunities")
async def site_of_care_opportunities(request: Request) -> JSONResponse:
    """Return opportunities to steer from hospital outpatient to lower-cost settings."""
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)

    from sqlalchemy import func
    from src.models.tables import ClaimRecord
    from decimal import Decimal

    # Claims at hospital outpatient (highest cost) that could be at office or home
    rows = (
        db.query(
            ClaimRecord.procedure_code,
            func.count(ClaimRecord.id).label("count"),
            func.sum(ClaimRecord.paid_amount).label("total_paid"),
        )
        .filter_by(tenant_id=tenant_id, site_of_care="hospital_outpatient")
        .group_by(ClaimRecord.procedure_code)
        .order_by(func.sum(ClaimRecord.paid_amount).desc())
        .limit(20)
        .all()
    )

    result = [
        {
            "procedure_code": row.procedure_code,
            "count": row.count,
            "total_paid": str(Decimal(str(row.total_paid or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "recommended_setting": "office_infusion",
        }
        for row in rows
    ]
    return JSONResponse(content=result)


@router.get("/stats")
async def get_stats(request: Request) -> JSONResponse:
    tenant_id = _get_tenant_id(request)
    db = _get_db(request)

    from sqlalchemy import func
    from src.models.tables import ClaimRecord

    rows = (
        db.query(ClaimRecord.status, func.count(ClaimRecord.id))
        .filter_by(tenant_id=tenant_id)
        .group_by(ClaimRecord.status)
        .all()
    )
    return JSONResponse(content={"by_status": {status: count for status, count in rows}})
