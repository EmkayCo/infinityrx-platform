"""Tests for US federal holiday calculator and seeder.

Coverage requirements: ≥99% on seed.py
Test count: 35+ covering every holiday rule across 2024-2030.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.bank_holidays.seed import (
    _last_weekday,
    _nth_weekday,
    _observed,
    us_federal_holidays,
)


# ---------------------------------------------------------------------------
# Helper: build a dict keyed by holiday name for easy assertion
# ---------------------------------------------------------------------------

def _by_name(year: int) -> dict[str, date]:
    """Return {name: holiday_date} for *year*."""
    holidays = us_federal_holidays(year)
    result: dict[str, date] = {}
    for h in holidays:
        result[h.name] = h.holiday_date
    return result


# ---------------------------------------------------------------------------
# _observed() rule tests
# ---------------------------------------------------------------------------

def test_observed_saturday_shifts_to_friday() -> None:
    # 2026-07-04 is a Saturday
    obs_date, obs_name = _observed(date(2026, 7, 4), "Independence Day")
    assert obs_date == date(2026, 7, 3)
    assert obs_name == "Independence Day (Observed)"


def test_observed_sunday_shifts_to_monday() -> None:
    # 2027-07-04 is a Sunday
    obs_date, obs_name = _observed(date(2027, 7, 4), "Independence Day")
    assert obs_date == date(2027, 7, 5)
    assert obs_name == "Independence Day (Observed)"


def test_observed_weekday_unchanged() -> None:
    # 2025-07-04 is a Friday
    obs_date, obs_name = _observed(date(2025, 7, 4), "Independence Day")
    assert obs_date == date(2025, 7, 4)
    assert obs_name == "Independence Day"


def test_observed_monday_unchanged() -> None:
    obs_date, obs_name = _observed(date(2026, 1, 19), "MLK Day")  # Monday
    assert obs_date == date(2026, 1, 19)
    assert obs_name == "MLK Day"


# ---------------------------------------------------------------------------
# _nth_weekday() tests
# ---------------------------------------------------------------------------

def test_nth_weekday_1st_monday_jan_2026() -> None:
    d = _nth_weekday(2026, 1, 0, 1)
    assert d == date(2026, 1, 5)


def test_nth_weekday_3rd_monday_jan_2026() -> None:
    d = _nth_weekday(2026, 1, 0, 3)
    assert d == date(2026, 1, 19)


def test_nth_weekday_4th_thursday_nov_2026() -> None:
    d = _nth_weekday(2026, 11, 3, 4)
    assert d == date(2026, 11, 26)


def test_nth_weekday_invalid_n_raises() -> None:
    with pytest.raises(ValueError):
        _nth_weekday(2026, 2, 0, 6)  # February 2026 has 4 Mondays; 6th doesn't exist


def test_last_weekday_last_monday_may_2026() -> None:
    d = _last_weekday(2026, 5, 0)
    assert d == date(2026, 5, 25)


def test_last_weekday_last_monday_may_2024() -> None:
    d = _last_weekday(2024, 5, 0)
    assert d == date(2024, 5, 27)


# ---------------------------------------------------------------------------
# 2026 — full calendar year (known dates)
# ---------------------------------------------------------------------------

def test_2026_new_years_day_observed_friday() -> None:
    # Jan 1 2026 = Thursday — no shift
    d = _by_name(2026)
    assert d["New Year's Day"] == date(2026, 1, 1)


def test_2026_mlk_day_jan_19() -> None:
    d = _by_name(2026)
    assert d["Martin Luther King Jr. Day"] == date(2026, 1, 19)


def test_2026_presidents_day_feb_16() -> None:
    d = _by_name(2026)
    assert d["Washington's Birthday"] == date(2026, 2, 16)


def test_2026_memorial_day_may_25() -> None:
    d = _by_name(2026)
    assert d["Memorial Day"] == date(2026, 5, 25)


def test_2026_juneteenth_jun_19() -> None:
    d = _by_name(2026)
    assert d["Juneteenth National Independence Day"] == date(2026, 6, 19)


def test_2026_independence_day_observed_jul_3() -> None:
    # July 4 2026 = Saturday → observed Friday July 3
    d = _by_name(2026)
    assert d["Independence Day (Observed)"] == date(2026, 7, 3)


def test_2026_labor_day_sep_7() -> None:
    d = _by_name(2026)
    assert d["Labor Day"] == date(2026, 9, 7)


def test_2026_columbus_day_oct_12() -> None:
    d = _by_name(2026)
    assert d["Columbus Day"] == date(2026, 10, 12)


def test_2026_veterans_day_nov_11() -> None:
    # Nov 11 2026 = Wednesday — no shift
    d = _by_name(2026)
    assert d["Veterans Day"] == date(2026, 11, 11)


def test_2026_thanksgiving_nov_26() -> None:
    d = _by_name(2026)
    assert d["Thanksgiving Day"] == date(2026, 11, 26)


def test_2026_christmas_dec_25() -> None:
    # Dec 25 2026 = Friday — no shift
    d = _by_name(2026)
    assert d["Christmas Day"] == date(2026, 12, 25)


def test_2026_exactly_11_holidays() -> None:
    assert len(us_federal_holidays(2026)) == 11


# ---------------------------------------------------------------------------
# 2025
# ---------------------------------------------------------------------------

def test_2025_new_years_day_jan_1() -> None:
    d = _by_name(2025)
    assert d["New Year's Day"] == date(2025, 1, 1)


def test_2025_independence_day_jul_4() -> None:
    # July 4 2025 = Friday — no shift
    d = _by_name(2025)
    assert d["Independence Day"] == date(2025, 7, 4)


def test_2025_christmas_observed_dec_25() -> None:
    # Dec 25 2025 = Thursday — no shift
    d = _by_name(2025)
    assert d["Christmas Day"] == date(2025, 12, 25)


def test_2025_veterans_day_nov_11() -> None:
    # Nov 11 2025 = Tuesday — no shift
    d = _by_name(2025)
    assert d["Veterans Day"] == date(2025, 11, 11)


# ---------------------------------------------------------------------------
# 2027 — tests for Sunday-shift cases
# ---------------------------------------------------------------------------

def test_2027_independence_day_observed_monday() -> None:
    # July 4 2027 = Sunday → observed Monday July 5
    d = _by_name(2027)
    assert d["Independence Day (Observed)"] == date(2027, 7, 5)


def test_2027_new_years_day_jan_1() -> None:
    # Jan 1 2027 = Friday — no shift
    d = _by_name(2027)
    assert d["New Year's Day"] == date(2027, 1, 1)


# ---------------------------------------------------------------------------
# 2028 — New Year's Day on Saturday → observed Friday Dec 31 2027
# ---------------------------------------------------------------------------

def test_2028_new_years_day_observed_dec_31_2027() -> None:
    # Jan 1 2028 = Saturday → observed Friday Dec 31 2027
    d = _by_name(2028)
    assert d["New Year's Day (Observed)"] == date(2027, 12, 31)


def test_2028_christmas_observed_monday() -> None:
    # Dec 25 2028 = Monday — no shift
    d = _by_name(2028)
    assert d["Christmas Day"] == date(2028, 12, 25)


# ---------------------------------------------------------------------------
# 2024
# ---------------------------------------------------------------------------

def test_2024_mlk_day_jan_15() -> None:
    d = _by_name(2024)
    assert d["Martin Luther King Jr. Day"] == date(2024, 1, 15)


def test_2024_memorial_day_may_27() -> None:
    d = _by_name(2024)
    assert d["Memorial Day"] == date(2024, 5, 27)


def test_2024_independence_day_jul_4() -> None:
    # July 4 2024 = Thursday — no shift
    d = _by_name(2024)
    assert d["Independence Day"] == date(2024, 7, 4)


def test_2024_veterans_day_observed_monday() -> None:
    # Nov 11 2024 = Monday — no shift
    d = _by_name(2024)
    assert d["Veterans Day"] == date(2024, 11, 11)


def test_2024_thanksgiving_nov_28() -> None:
    d = _by_name(2024)
    assert d["Thanksgiving Day"] == date(2024, 11, 28)


def test_2024_christmas_observed_dec_25() -> None:
    # Dec 25 2024 = Wednesday — no shift
    d = _by_name(2024)
    assert d["Christmas Day"] == date(2024, 12, 25)


# ---------------------------------------------------------------------------
# 2030
# ---------------------------------------------------------------------------

def test_2030_juneteenth_observed_wednesday() -> None:
    # Jun 19 2030 = Wednesday — no shift
    d = _by_name(2030)
    assert d["Juneteenth National Independence Day"] == date(2030, 6, 19)


def test_2030_thanksgiving_nov_28() -> None:
    d = _by_name(2030)
    assert d["Thanksgiving Day"] == date(2030, 11, 28)


# ---------------------------------------------------------------------------
# BankHoliday instance attributes
# ---------------------------------------------------------------------------

def test_holiday_instances_have_uuid_ids() -> None:
    holidays = us_federal_holidays(2026)
    for h in holidays:
        parsed = uuid.UUID(str(h.id))
        assert parsed.version == 4


def test_holiday_instances_country_us() -> None:
    holidays = us_federal_holidays(2026)
    for h in holidays:
        assert h.country == "US"


def test_holiday_instances_is_federal_true() -> None:
    holidays = us_federal_holidays(2026)
    for h in holidays:
        assert h.is_federal is True


def test_holiday_instances_is_bank_holiday_true() -> None:
    holidays = us_federal_holidays(2026)
    for h in holidays:
        assert h.is_bank_holiday is True


# ---------------------------------------------------------------------------
# seed_years: idempotency
# ---------------------------------------------------------------------------

def test_seed_years_invalid_range() -> None:
    from src.bank_holidays.seed import seed_years

    with pytest.raises(ValueError, match="end"):
        seed_years(None, 2026, 2025)


def test_seed_years_idempotent(bh_db_session) -> None:
    """Running seed_years twice yields the same row count."""
    from src.bank_holidays.seed import seed_years

    first = seed_years(bh_db_session, 2026, 2026)
    assert first == 11  # 11 US federal holidays per year

    second = seed_years(bh_db_session, 2026, 2026)
    assert second == 0  # ON CONFLICT DO NOTHING → no new rows


def test_seed_years_multi_year(bh_db_session) -> None:
    from src.bank_holidays.seed import seed_years

    inserted = seed_years(bh_db_session, 2026, 2028)
    # 3 years × 11 holidays = 33 (all unique dates)
    assert inserted == 33


def test_seed_years_idempotent_after_multi(bh_db_session) -> None:
    from src.bank_holidays.seed import seed_years

    seed_years(bh_db_session, 2026, 2028)
    second = seed_years(bh_db_session, 2026, 2028)
    assert second == 0
