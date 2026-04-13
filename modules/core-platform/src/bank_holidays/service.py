"""Business-day service for NACHA batch scheduling.

Usage::

    from src.bank_holidays.service import BankHolidayService
    svc = BankHolidayService(session)
    svc.is_business_day(date(2026, 7, 3))   # False — Independence Day Observed
    svc.next_business_day(date(2026, 7, 3)) # date(2026, 7, 6) — Monday

Performance
-----------
Holidays are queried once per call and stored in a ``frozenset`` for O(1)
date membership checks.  The per-call query is fast (table is small, indexed),
and the result is a plain Python frozenset — no additional caching layer is
needed at this scale.  If profiling shows this to be a bottleneck, add a
module-level TTL cache (5-minute) at the call site.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models.bank_holidays import BankHoliday

if TYPE_CHECKING:
    pass

_SATURDAY = 5
_SUNDAY = 6


class BankHolidayService:
    """Business-day calculations backed by the ``core.bank_holidays`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _holiday_dates(self, country: str) -> frozenset[date]:
        """Return the set of bank-holiday dates for *country*.

        Executes a lightweight SELECT each call (small table, indexed).
        """
        rows = self._session.execute(
            select(BankHoliday.holiday_date).where(
                BankHoliday.country == country,
                BankHoliday.is_bank_holiday.is_(True),
            )
        ).scalars().all()
        return frozenset(rows)

    def _is_weekend(self, d: date) -> bool:
        return d.weekday() >= _SATURDAY

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_business_day(self, d: date, country: str = "US") -> bool:
        """Return ``True`` iff *d* is not a weekend and not a bank holiday."""
        if self._is_weekend(d):
            return False
        return d not in self._holiday_dates(country)

    def next_business_day(self, d: date, country: str = "US") -> date:
        """Return the smallest date strictly after *d* that is a business day."""
        holidays = self._holiday_dates(country)
        candidate = d + timedelta(days=1)
        while self._is_weekend(candidate) or candidate in holidays:
            candidate += timedelta(days=1)
        return candidate

    def previous_business_day(self, d: date, country: str = "US") -> date:
        """Return the largest date strictly before *d* that is a business day."""
        holidays = self._holiday_dates(country)
        candidate = d - timedelta(days=1)
        while self._is_weekend(candidate) or candidate in holidays:
            candidate -= timedelta(days=1)
        return candidate

    def add_business_days(self, d: date, n: int, country: str = "US") -> date:
        """Return the date that is *n* business days after (or before) *d*.

        * ``n > 0`` — move forward
        * ``n == 0`` — return *d* itself (even if *d* is not a business day)
        * ``n < 0`` — move backward (equivalent to subtracting ``|n|`` business days)
        """
        if n == 0:
            return d
        holidays = self._holiday_dates(country)
        current = d
        step = timedelta(days=1) if n > 0 else timedelta(days=-1)
        remaining = abs(n)
        while remaining > 0:
            current += step
            if not self._is_weekend(current) and current not in holidays:
                remaining -= 1
        return current

    def list_holidays(
        self, start: date, end: date, country: str = "US"
    ) -> list[BankHoliday]:
        """Return all bank-holiday rows with ``holiday_date`` in [start, end]."""
        rows = self._session.execute(
            select(BankHoliday)
            .where(
                BankHoliday.country == country,
                BankHoliday.holiday_date >= start,
                BankHoliday.holiday_date <= end,
            )
            .order_by(BankHoliday.holiday_date)
        ).scalars().all()
        return list(rows)

    def add_custom_holiday(
        self,
        holiday_date: date,
        name: str,
        country: str = "US",
        is_bank_holiday: bool = True,
    ) -> BankHoliday:
        """Insert a custom (non-federal) holiday and return the persisted row.

        Raises ``sqlalchemy.exc.IntegrityError`` if a row for (holiday_date,
        country) already exists.
        """
        import uuid as _uuid

        h = BankHoliday(
            id=_uuid.uuid4(),
            holiday_date=holiday_date,
            name=name,
            country=country,
            is_federal=False,
            is_bank_holiday=is_bank_holiday,
        )
        self._session.add(h)
        self._session.flush()
        return h


__all__ = ["BankHolidayService"]
