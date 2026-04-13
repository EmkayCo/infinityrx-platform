"""US federal bank holiday calculator + idempotent seeder.

Usage
-----
Programmatic::

    from src.bank_holidays.seed import us_federal_holidays, seed_years
    holidays = us_federal_holidays(2026)
    seed_years(session, 2026, 2035)

CLI::

    python -m src.bank_holidays.seed --from 2026 --to 2035

Rules
-----
The eleven US federal holidays are computed per the Office of Personnel
Management (OPM) schedule:

1.  New Year's Day            — Jan 1
2.  Martin Luther King Jr.    — 3rd Monday of January
3.  Washington's Birthday     — 3rd Monday of February
4.  Memorial Day              — last Monday of May
5.  Juneteenth                — Jun 19
6.  Independence Day          — Jul 4
7.  Labor Day                 — 1st Monday of September
8.  Columbus Day              — 2nd Monday of October
9.  Veterans Day              — Nov 11
10. Thanksgiving Day          — 4th Thursday of November
11. Christmas Day             — Dec 25

"Observed" rule for fixed dates (1, 5, 6, 8, 9, 11): if the calendar date
falls on a Saturday the observance is the preceding Friday; if Sunday the
observance is the following Monday.  The name gains " (Observed)" suffix.
"""

from __future__ import annotations

import argparse
import uuid
from calendar import monthcalendar
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Pure-Python model stub for use in contexts where the real ORM model cannot
# be imported (e.g., standalone CLI without a DB connection).  We use the
# actual ORM model when available; otherwise we fall back to this dataclass.
# ---------------------------------------------------------------------------

def _make_holiday(
    holiday_date: date,
    name: str,
    country: str = "US",
    is_federal: bool = True,
    is_bank_holiday: bool = True,
) -> object:
    """Return an unsaved BankHoliday ORM instance.

    Imports the real ORM model from shared; never instantiates a stub.
    """
    from shared.db.models.bank_holidays import BankHoliday

    return BankHoliday(
        id=uuid.uuid4(),
        holiday_date=holiday_date,
        name=name,
        country=country,
        is_federal=is_federal,
        is_bank_holiday=is_bank_holiday,
    )


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------

_MONDAY = 0
_THURSDAY = 3
_SATURDAY = 5
_SUNDAY = 6


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence (1-based) of *weekday* in *month* of *year*.

    *weekday* follows Python's ``date.weekday()`` convention (Monday=0).
    Raises ``ValueError`` if the month has fewer than *n* occurrences.
    """
    cal = monthcalendar(year, month)
    # monthcalendar rows are weeks; weekday column; 0 means day doesn't exist
    days = [week[weekday] for week in cal if week[weekday] != 0]
    if n < 1 or n > len(days):
        raise ValueError(f"No {n}th weekday {weekday} in {year}-{month:02d}")
    return date(year, month, days[n - 1])


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last occurrence of *weekday* in *month* of *year*."""
    cal = monthcalendar(year, month)
    days = [week[weekday] for week in cal if week[weekday] != 0]
    return date(year, month, days[-1])


def _observed(d: date, name: str) -> tuple[date, str]:
    """Apply the standard Saturday/Sunday observance shift.

    Returns ``(observed_date, observed_name)`` where *observed_name* gains
    " (Observed)" when the date is shifted.
    """
    dow = d.weekday()
    if dow == _SATURDAY:
        return d - timedelta(days=1), f"{name} (Observed)"
    if dow == _SUNDAY:
        return d + timedelta(days=1), f"{name} (Observed)"
    return d, name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def us_federal_holidays(year: int) -> list:
    """Return a list of unsaved BankHoliday ORM instances for *year*.

    Only the *observed* dates are returned (i.e., if July 4 falls on a
    Saturday the list contains July 3 marked "Independence Day (Observed)").
    """
    holidays: list = []

    def add(d: date, name: str, apply_observed: bool = True) -> None:
        if apply_observed:
            d, name = _observed(d, name)
        holidays.append(_make_holiday(d, name))

    # 1. New Year's Day (Jan 1, observed)
    add(date(year, 1, 1), "New Year's Day")

    # 2. Martin Luther King Jr. Day (3rd Monday in January)
    add(_nth_weekday(year, 1, _MONDAY, 3), "Martin Luther King Jr. Day", apply_observed=False)

    # 3. Washington's Birthday / Presidents' Day (3rd Monday in February)
    add(_nth_weekday(year, 2, _MONDAY, 3), "Washington's Birthday", apply_observed=False)

    # 4. Memorial Day (last Monday in May)
    add(_last_weekday(year, 5, _MONDAY), "Memorial Day", apply_observed=False)

    # 5. Juneteenth National Independence Day (Jun 19, observed)
    add(date(year, 6, 19), "Juneteenth National Independence Day")

    # 6. Independence Day (Jul 4, observed)
    add(date(year, 7, 4), "Independence Day")

    # 7. Labor Day (1st Monday in September)
    add(_nth_weekday(year, 9, _MONDAY, 1), "Labor Day", apply_observed=False)

    # 8. Columbus Day (2nd Monday in October)
    add(_nth_weekday(year, 10, _MONDAY, 2), "Columbus Day", apply_observed=False)

    # 9. Veterans Day (Nov 11, observed)
    add(date(year, 11, 11), "Veterans Day")

    # 10. Thanksgiving Day (4th Thursday in November)
    add(_nth_weekday(year, 11, _THURSDAY, 4), "Thanksgiving Day", apply_observed=False)

    # 11. Christmas Day (Dec 25, observed)
    add(date(year, 12, 25), "Christmas Day")

    return holidays


def seed_years(session: object, start: int, end: int) -> int:
    """Idempotently insert US federal holidays for *start* through *end* inclusive.

    Uses ``INSERT ... ON CONFLICT DO NOTHING`` so running twice is safe.
    Returns the number of rows actually inserted.

    Parameters
    ----------
    session:
        A SQLAlchemy ``Session`` (sync).
    start, end:
        Inclusive year range.  ``end`` must be >= ``start``.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session as _Session

    if end < start:
        raise ValueError(f"end ({end}) must be >= start ({start})")

    inserted = 0
    for year in range(start, end + 1):
        for h in us_federal_holidays(year):
            result = session.execute(  # type: ignore[union-attr]
                text(
                    "INSERT INTO core.bank_holidays "
                    "(id, holiday_date, name, country, is_federal, is_bank_holiday) "
                    "VALUES (:id, :holiday_date, :name, :country, :is_federal, :is_bank_holiday) "
                    "ON CONFLICT (holiday_date, country) DO NOTHING"
                ),
                {
                    "id": str(h.id),
                    "holiday_date": h.holiday_date,
                    "name": h.name,
                    "country": h.country,
                    "is_federal": h.is_federal,
                    "is_bank_holiday": h.is_bank_holiday,
                },
            )
            inserted += result.rowcount
    session.commit()  # type: ignore[union-attr]
    return inserted


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli() -> None:  # pragma: no cover
    """CLI: python -m src.bank_holidays.seed --from 2026 --to 2035"""
    import os
    import sys

    # Ensure repo root on path so shared.* imports resolve.
    _here = __file__
    for _ in range(5):
        _here = os.path.dirname(_here)
        if os.path.isfile(os.path.join(_here, "pyproject.toml")):
            sys.path.insert(0, _here)
            break

    parser = argparse.ArgumentParser(
        description="Seed US federal bank holidays into core.bank_holidays"
    )
    parser.add_argument("--from", dest="start", type=int, required=True)
    parser.add_argument("--to", dest="end", type=int, required=True)
    args = parser.parse_args()

    from shared.config import get_settings
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL_SYNC)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        count = seed_years(session, args.start, args.end)
        print(f"Inserted {count} holiday rows for {args.start}–{args.end}.")
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    _cli()
