"""ASP pricing endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from shared.auth.dependencies import get_current_user

from src.api.schemas.asp import AspPricingResponse, AspRefreshResponse
from src.api.schemas.errors import ErrorEnvelope
from src.services.pricing_service import PricingService, quarter_for_date
from src.jobs.asp_refresh_job import AspRefreshJob

router = APIRouter(prefix="/asp", tags=["asp"], dependencies=[Depends(get_current_user)])  # CR-03


def _get_db(request: Request):
    return request.state.db


@router.get("/current-quarter", response_model=dict)
async def get_current_quarter_summary(request: Request) -> dict:
    """Return current quarter and count of ASP records."""
    from src.models.tables import AspPricing
    from sqlalchemy import func

    db = _get_db(request)
    quarter = quarter_for_date(date.today())
    count = db.query(func.count(AspPricing.id)).filter_by(quarter=quarter).scalar() or 0
    return {"quarter": quarter, "record_count": count}


@router.get("/{hcpcs_code}", response_model=AspPricingResponse)
async def get_asp_pricing(
    request: Request,
    hcpcs_code: str,
    as_of: date = Query(default_factory=date.today),
) -> JSONResponse:
    """Get ASP pricing for a HCPCS code on a given date."""
    db = _get_db(request)
    svc = PricingService(db)
    record = svc.get_asp_response(hcpcs_code.upper(), as_of)
    if record is None:
        err = ErrorEnvelope.make(
            code="NOT_FOUND",
            message=f"No ASP pricing found for {hcpcs_code}",
        )
        return JSONResponse(status_code=404, content=err.model_dump())
    return JSONResponse(content=record.model_dump(mode="json"))


@router.post("/refresh", response_model=AspRefreshResponse)
async def refresh_asp(
    request: Request,
    quarter: str = Query(..., description="Quarter in YYYY-QN format (e.g., 2026-Q1)"),
    records: list[dict] = [],
) -> JSONResponse:
    """Load or refresh ASP pricing data for a quarter."""
    db = _get_db(request)
    job = AspRefreshJob(db)
    try:
        result = job.run(quarter, records)
    except ValueError as exc:
        err = ErrorEnvelope.make(code="INVALID_QUARTER", message=str(exc))
        return JSONResponse(status_code=400, content=err.model_dump())

    return JSONResponse(
        content=AspRefreshResponse(
            quarter=quarter,
            records_loaded=result["loaded"],
            records_skipped=result["skipped"],
            message=f"ASP refresh complete for {quarter}",
        ).model_dump(mode="json")
    )
