"""Tests for BankHolidayService — 100% branch coverage required.

All tests use the ``bh_db_session`` fixture which wraps each test in a
rolled-back transaction against the real ``core.bank_holidays`` table.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from src.bank_holidays.service import BankHolidayService


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _seed_holiday(session, d: date, name: str, country: str = "US") -> None:
    """Insert a single holiday row directly via ORM."""
    from shared.db.models.bank_holidays import BankHoliday
    import uuid

    session.add(
        BankHoliday(
            id=uuid.uuid4(),
            holiday_date=d,
            name=name,
            country=country,
            is_federal=True,
            is_bank_holiday=True,
        )
    )
    session.flush()


def _seed_non_bank_holiday(session, d: date, name: str, country: str = "US") -> None:
    """Insert a federal holiday that is NOT a bank holiday."""
    from shared.db.models.bank_holidays import BankHoliday
    import uuid

    session.add(
        BankHoliday(
            id=uuid.uuid4(),
            holiday_date=d,
            name=name,
            country=country,
            is_federal=True,
            is_bank_holiday=False,
        )
    )
    session.flush()


# ---------------------------------------------------------------------------
# is_business_day
# ---------------------------------------------------------------------------

def test_is_business_day_regular_tuesday(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    # 2026-07-07 = Tuesday, no holidays
    assert svc.is_business_day(date(2026, 7, 7)) is True


def test_is_business_day_saturday(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    # 2026-07-04 = Saturday
    assert svc.is_business_day(date(2026, 7, 4)) is False


def test_is_business_day_sunday(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    # 2026-07-05 = Sunday
    assert svc.is_business_day(date(2026, 7, 5)) is False


def test_is_business_day_on_holiday(bh_db_session) -> None:
    _seed_holiday(bh_db_session, date(2026, 7, 3), "Independence Day (Observed)")
    svc = BankHolidayService(bh_db_session)
    assert svc.is_business_day(date(2026, 7, 3)) is False


def test_is_business_day_non_bank_holiday_counts_as_business(bh_db_session) -> None:
    """is_bank_holiday=False rows must NOT block business days."""
    _seed_non_bank_holiday(bh_db_session, date(2026, 10, 12), "Columbus Day")
    svc = BankHolidayService(bh_db_session)
    # Oct 12 2026 = Monday; is_bank_holiday=False → still a business day
    assert svc.is_business_day(date(2026, 10, 12)) is True


def test_is_business_day_different_country(bh_db_session) -> None:
    """A holiday for CA does not affect US business days."""
    _seed_holiday(bh_db_session, date(2026, 7, 1), "Canada Day", country="CA")
    svc = BankHolidayService(bh_db_session)
    # July 1 2026 = Wednesday; no US holiday → business day
    assert svc.is_business_day(date(2026, 7, 1), country="US") is True
    assert svc.is_business_day(date(2026, 7, 1), country="CA") is False


def test_is_business_day_monday(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    # 2026-07-06 = Monday, no holiday
    assert svc.is_business_day(date(2026, 7, 6)) is True


def test_is_business_day_friday(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    # 2026-07-10 = Friday
    assert svc.is_business_day(date(2026, 7, 10)) is True


# ---------------------------------------------------------------------------
# next_business_day
# ---------------------------------------------------------------------------

def test_next_business_day_from_friday(bh_db_session) -> None:
    """Friday → Monday (skip weekend)."""
    svc = BankHolidayService(bh_db_session)
    result = svc.next_business_day(date(2026, 7, 10))  # Friday
    assert result == date(2026, 7, 13)  # Monday


def test_next_business_day_from_saturday(bh_db_session) -> None:
    """Saturday → Monday."""
    svc = BankHolidayService(bh_db_session)
    result = svc.next_business_day(date(2026, 7, 4))  # Saturday
    assert result == date(2026, 7, 6)  # Monday


def test_next_business_day_from_sunday(bh_db_session) -> None:
    """Sunday → Monday."""
    svc = BankHolidayService(bh_db_session)
    result = svc.next_business_day(date(2026, 7, 5))  # Sunday
    assert result == date(2026, 7, 6)  # Monday


def test_next_business_day_skips_holiday(bh_db_session) -> None:
    """Monday is a holiday → skip to Tuesday."""
    _seed_holiday(bh_db_session, date(2026, 9, 7), "Labor Day")
    svc = BankHolidayService(bh_db_session)
    result = svc.next_business_day(date(2026, 9, 4))  # Friday
    assert result == date(2026, 9, 8)  # Tuesday (Monday is Labor Day)


def test_next_business_day_skips_multiple_holidays(bh_db_session) -> None:
    """Consecutive holidays: Mon + Tue blocked → Wednesday."""
    _seed_holiday(bh_db_session, date(2026, 1, 5), "Holiday A")
    _seed_holiday(bh_db_session, date(2026, 1, 6), "Holiday B")
    svc = BankHolidayService(bh_db_session)
    result = svc.next_business_day(date(2026, 1, 4))  # Sunday
    assert result == date(2026, 1, 7)  # Wednesday


def test_next_business_day_from_normal_weekday(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    result = svc.next_business_day(date(2026, 7, 7))  # Tuesday
    assert result == date(2026, 7, 8)  # Wednesday


# ---------------------------------------------------------------------------
# previous_business_day
# ---------------------------------------------------------------------------

def test_previous_business_day_from_monday(bh_db_session) -> None:
    """Monday → Friday."""
    svc = BankHolidayService(bh_db_session)
    result = svc.previous_business_day(date(2026, 7, 6))  # Monday
    assert result == date(2026, 7, 3)  # Friday


def test_previous_business_day_from_saturday(bh_db_session) -> None:
    """Saturday → Friday."""
    svc = BankHolidayService(bh_db_session)
    result = svc.previous_business_day(date(2026, 7, 4))  # Saturday
    assert result == date(2026, 7, 3)  # Friday


def test_previous_business_day_from_sunday(bh_db_session) -> None:
    """Sunday → Friday."""
    svc = BankHolidayService(bh_db_session)
    result = svc.previous_business_day(date(2026, 7, 5))  # Sunday
    assert result == date(2026, 7, 3)  # Friday


def test_previous_business_day_skips_holiday(bh_db_session) -> None:
    """Friday is a holiday → Thursday."""
    _seed_holiday(bh_db_session, date(2026, 7, 3), "Independence Day (Observed)")
    svc = BankHolidayService(bh_db_session)
    result = svc.previous_business_day(date(2026, 7, 6))  # Monday
    assert result == date(2026, 7, 2)  # Thursday (Friday is holiday)


def test_previous_business_day_from_wednesday(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    result = svc.previous_business_day(date(2026, 7, 8))  # Wednesday
    assert result == date(2026, 7, 7)  # Tuesday


# ---------------------------------------------------------------------------
# add_business_days
# ---------------------------------------------------------------------------

def test_add_business_days_zero(bh_db_session) -> None:
    """n=0 returns d unchanged, even on a weekend."""
    svc = BankHolidayService(bh_db_session)
    d = date(2026, 7, 4)  # Saturday
    assert svc.add_business_days(d, 0) == d


def test_add_business_days_one(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    result = svc.add_business_days(date(2026, 7, 6), 1)  # Monday + 1
    assert result == date(2026, 7, 7)  # Tuesday


def test_add_business_days_ten(bh_db_session) -> None:
    """10 business days from 2026-07-06 (Monday)."""
    svc = BankHolidayService(bh_db_session)
    result = svc.add_business_days(date(2026, 7, 6), 10)
    # 10 business days from Mon Jul 6: Tue7, Wed8, Thu9, Fri10, Mon13, Tue14,
    # Wed15, Thu16, Fri17, Mon20
    assert result == date(2026, 7, 20)


def test_add_business_days_negative(bh_db_session) -> None:
    """n=-3: go back 3 business days from 2026-07-09 (Thursday)."""
    svc = BankHolidayService(bh_db_session)
    result = svc.add_business_days(date(2026, 7, 9), -3)
    # Thu-3: Wed8, Tue7, Mon6
    assert result == date(2026, 7, 6)


def test_add_business_days_skips_holiday(bh_db_session) -> None:
    """Holiday on the path is not counted as a business day."""
    _seed_holiday(bh_db_session, date(2026, 9, 7), "Labor Day")
    svc = BankHolidayService(bh_db_session)
    # 1 business day from Friday Sep 4: Mon Sep 7 is Labor Day → Tue Sep 8
    result = svc.add_business_days(date(2026, 9, 4), 1)
    assert result == date(2026, 9, 8)


def test_add_business_days_negative_skips_holiday(bh_db_session) -> None:
    """Negative n also skips holidays."""
    _seed_holiday(bh_db_session, date(2026, 9, 7), "Labor Day")
    svc = BankHolidayService(bh_db_session)
    # -1 from Tuesday Sep 8: Mon Sep 7 is holiday → Fri Sep 4
    result = svc.add_business_days(date(2026, 9, 8), -1)
    assert result == date(2026, 9, 4)


def test_add_business_days_from_holiday_start(bh_db_session) -> None:
    """Start date is itself a holiday; n=0 returns it unchanged."""
    _seed_holiday(bh_db_session, date(2026, 9, 7), "Labor Day")
    svc = BankHolidayService(bh_db_session)
    assert svc.add_business_days(date(2026, 9, 7), 0) == date(2026, 9, 7)


def test_add_business_days_large_n(bh_db_session) -> None:
    """Sanity check: 5 business days == next week same day (no holidays)."""
    svc = BankHolidayService(bh_db_session)
    result = svc.add_business_days(date(2026, 7, 6), 5)  # Mon → next Mon
    assert result == date(2026, 7, 13)


# ---------------------------------------------------------------------------
# list_holidays
# ---------------------------------------------------------------------------

def test_list_holidays_empty_range(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    result = svc.list_holidays(date(2099, 1, 1), date(2099, 12, 31))
    assert result == []


def test_list_holidays_returns_rows_in_range(bh_db_session) -> None:
    _seed_holiday(bh_db_session, date(2026, 7, 3), "Independence Day (Observed)")
    _seed_holiday(bh_db_session, date(2026, 9, 7), "Labor Day")
    svc = BankHolidayService(bh_db_session)
    result = svc.list_holidays(date(2026, 7, 1), date(2026, 8, 31))
    assert len(result) == 1
    assert result[0].holiday_date == date(2026, 7, 3)


def test_list_holidays_inclusive_bounds(bh_db_session) -> None:
    _seed_holiday(bh_db_session, date(2026, 7, 3), "Independence Day (Observed)")
    svc = BankHolidayService(bh_db_session)
    # Exact start bound
    result = svc.list_holidays(date(2026, 7, 3), date(2026, 7, 3))
    assert len(result) == 1
    # Exclusive — one day before
    result2 = svc.list_holidays(date(2026, 7, 4), date(2026, 7, 10))
    assert len(result2) == 0


def test_list_holidays_ordered_by_date(bh_db_session) -> None:
    _seed_holiday(bh_db_session, date(2026, 11, 26), "Thanksgiving")
    _seed_holiday(bh_db_session, date(2026, 9, 7), "Labor Day")
    _seed_holiday(bh_db_session, date(2026, 12, 25), "Christmas Day")
    svc = BankHolidayService(bh_db_session)
    result = svc.list_holidays(date(2026, 9, 1), date(2026, 12, 31))
    dates = [r.holiday_date for r in result]
    assert dates == sorted(dates)


def test_list_holidays_filters_by_country(bh_db_session) -> None:
    _seed_holiday(bh_db_session, date(2026, 7, 1), "Canada Day", country="CA")
    _seed_holiday(bh_db_session, date(2026, 7, 3), "US Holiday", country="US")
    svc = BankHolidayService(bh_db_session)
    us_result = svc.list_holidays(date(2026, 7, 1), date(2026, 7, 31), country="US")
    ca_result = svc.list_holidays(date(2026, 7, 1), date(2026, 7, 31), country="CA")
    assert all(r.country == "US" for r in us_result)
    assert all(r.country == "CA" for r in ca_result)


# ---------------------------------------------------------------------------
# add_custom_holiday
# ---------------------------------------------------------------------------

def test_add_custom_holiday_inserts_row(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    h = svc.add_custom_holiday(date(2026, 8, 15), "Custom Closure")
    assert h.holiday_date == date(2026, 8, 15)
    assert h.name == "Custom Closure"
    assert h.country == "US"
    assert h.is_federal is False
    assert h.is_bank_holiday is True


def test_add_custom_holiday_non_bank(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    h = svc.add_custom_holiday(date(2026, 8, 16), "Informational Only", is_bank_holiday=False)
    assert h.is_bank_holiday is False


def test_add_custom_holiday_different_country(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    h = svc.add_custom_holiday(date(2026, 8, 4), "Civic Holiday", country="CA")
    assert h.country == "CA"


def test_add_custom_holiday_blocks_business_day(bh_db_session) -> None:
    svc = BankHolidayService(bh_db_session)
    # Aug 17 2026 = Monday, no holiday by default
    assert svc.is_business_day(date(2026, 8, 17)) is True
    svc.add_custom_holiday(date(2026, 8, 17), "Custom Closure")
    assert svc.is_business_day(date(2026, 8, 17)) is False


def test_add_custom_holiday_duplicate_raises(bh_db_session) -> None:
    """Duplicate (date, country) raises IntegrityError — tested via savepoint."""
    svc = BankHolidayService(bh_db_session)
    svc.add_custom_holiday(date(2026, 8, 15), "First")
    # Use a nested transaction (SAVEPOINT) so the outer transaction stays valid
    # after the expected IntegrityError.
    with pytest.raises(IntegrityError):
        with bh_db_session.begin_nested():
            svc.add_custom_holiday(date(2026, 8, 15), "Duplicate")
