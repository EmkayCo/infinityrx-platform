"""REST API for bank holidays.

Endpoints
---------
GET  /bank-holidays?year=2026&country=US
POST /bank-holidays
GET  /bank-holidays/is-business-day/{iso_date}
GET  /bank-holidays/next-business-day/{iso_date}
"""

from __future__ import annotations

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .._shim.auth import CurrentUser, current_user, require_role
from .._shim.db import get_session
from .schemas import (
    BusinessDayResponse,
    HolidayCreate,
    HolidayRead,
    NextBusinessDayResponse,
)
from .service import BankHolidayService

router = APIRouter(prefix="/bank-holidays", tags=["bank-holidays"])

_ISO_DATE_EXAMPLE = "2026-07-04"


def _parse_iso_date(iso_date: str) -> date:
    """Parse ISO 8601 date string in YYYY-MM-DD format; raise HTTP 422 on failure.

    Python 3.11+ accepts compact format (YYYYMMDD) via ``date.fromisoformat``
    so we enforce the hyphenated form explicitly.
    """
    import re

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso_date):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_date",
                "message": f"Expected ISO 8601 date (YYYY-MM-DD), got: {iso_date!r}",
            },
        )
    # The regex already validates the format; fromisoformat should not raise
    # for a valid YYYY-MM-DD string, but we guard against impossible overflow
    # (e.g., "2026-13-01") which passes the regex but not fromisoformat.
    try:
        return date.fromisoformat(iso_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_date",
                "message": f"Expected ISO 8601 date (YYYY-MM-DD), got: {iso_date!r}",
            },
        )


@router.get("", response_model=List[HolidayRead])
def list_holidays(
    year: int = Query(..., ge=1900, le=2200, description="Calendar year"),
    country: str = Query(default="US", min_length=2, max_length=2),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(current_user),
) -> List[HolidayRead]:
    """List all bank holidays for a given year and country."""
    svc = BankHolidayService(session)
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    rows = svc.list_holidays(start, end, country=country.upper())
    return [HolidayRead.model_validate(r) for r in rows]


@router.post("", response_model=HolidayRead, status_code=201)
def create_holiday(
    body: HolidayCreate,
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(require_role("platform_admin", "tenant_admin")),
) -> HolidayRead:
    """Add a custom (non-federal) bank holiday."""
    svc = BankHolidayService(session)
    try:
        h = svc.add_custom_holiday(
            holiday_date=body.holiday_date,
            name=body.name,
            country=body.country,
            is_bank_holiday=body.is_bank_holiday,
        )
        session.commit()
        session.refresh(h)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "error": "holiday_already_exists",
                "message": (
                    f"A holiday for {body.holiday_date.isoformat()} / {body.country}"
                    " already exists."
                ),
            },
        )
    return HolidayRead.model_validate(h)


@router.get("/is-business-day/{iso_date}", response_model=BusinessDayResponse)
def is_business_day(
    iso_date: str,
    country: str = Query(default="US", min_length=2, max_length=2),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(current_user),
) -> BusinessDayResponse:
    """Check whether a date is a business day."""
    d = _parse_iso_date(iso_date)
    svc = BankHolidayService(session)

    # Determine reason if not a business day
    reason: str | None = None
    if d.weekday() == 5:  # Saturday
        reason = "Saturday"
        is_bd = False
    elif d.weekday() == 6:  # Sunday
        reason = "Sunday"
        is_bd = False
    else:
        # Only rows with is_bank_holiday=True block the business day.
        # _holiday_dates() already filters by is_bank_holiday=True, so if d
        # is in the set we can fetch the name directly from list_holidays.
        holiday_dates = svc._holiday_dates(country.upper())
        if d in holiday_dates:
            rows = svc.list_holidays(d, d, country=country.upper())
            # bank_rows is guaranteed non-empty because d is in holiday_dates
            bank_rows = [r for r in rows if r.is_bank_holiday]
            reason = bank_rows[0].name
            is_bd = False
        else:
            is_bd = True

    return BusinessDayResponse(date=d, is_business_day=is_bd, reason=reason)


@router.get("/next-business-day/{iso_date}", response_model=NextBusinessDayResponse)
def next_business_day(
    iso_date: str,
    country: str = Query(default="US", min_length=2, max_length=2),
    session: Session = Depends(get_session),
    _user: CurrentUser = Depends(current_user),
) -> NextBusinessDayResponse:
    """Return the next business day after the given date."""
    d = _parse_iso_date(iso_date)
    svc = BankHolidayService(session)
    nbd = svc.next_business_day(d, country=country.upper())
    return NextBusinessDayResponse(**{"from": d, "next_business_day": nbd})


__all__ = ["router"]
