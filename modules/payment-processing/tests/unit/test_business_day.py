"""Unit tests for business_day service."""
from __future__ import annotations

from datetime import date

import pytest

from src.services.business_day import (
    add_business_days,
    effective_date_for_batch,
    is_business_day,
    next_business_day,
)


class TestIsBusinessDay:
    def test_monday_is_business_day(self):
        assert is_business_day(date(2026, 4, 13)) is True  # Monday

    def test_saturday_is_not_business_day(self):
        assert is_business_day(date(2026, 4, 11)) is False

    def test_sunday_is_not_business_day(self):
        assert is_business_day(date(2026, 4, 12)) is False

    def test_new_years_day_2026_is_not_business_day(self):
        assert is_business_day(date(2026, 1, 1)) is False

    def test_christmas_2026_is_not_business_day(self):
        assert is_business_day(date(2026, 12, 25)) is False

    def test_regular_friday_is_business_day(self):
        assert is_business_day(date(2026, 4, 10)) is True


class TestNextBusinessDay:
    def test_business_day_returns_itself(self):
        monday = date(2026, 4, 13)
        assert next_business_day(monday) == monday

    def test_saturday_returns_monday(self):
        saturday = date(2026, 4, 11)
        assert next_business_day(saturday) == date(2026, 4, 13)

    def test_sunday_returns_monday(self):
        sunday = date(2026, 4, 12)
        assert next_business_day(sunday) == date(2026, 4, 13)

    def test_holiday_returns_next_business_day(self):
        new_years = date(2026, 1, 1)  # Thursday holiday
        result = next_business_day(new_years)
        assert is_business_day(result)
        assert result > new_years


class TestAddBusinessDays:
    def test_add_zero_returns_same_day(self):
        d = date(2026, 4, 13)
        assert add_business_days(d, 0) == d

    def test_add_one_business_day_from_monday(self):
        monday = date(2026, 4, 13)
        assert add_business_days(monday, 1) == date(2026, 4, 14)

    def test_add_five_skips_weekend(self):
        wednesday = date(2026, 4, 8)
        result = add_business_days(wednesday, 5)
        assert is_business_day(result)

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            add_business_days(date(2026, 4, 13), -1)

    def test_add_two_from_thursday_skips_weekend(self):
        thursday = date(2026, 4, 9)
        result = add_business_days(thursday, 2)
        assert result == date(2026, 4, 13)  # skips Fri to Mon? No: Fri(1) Mon(2)


class TestEffectiveDateForBatch:
    def test_standard_ach_adds_two_business_days(self):
        monday = date(2026, 4, 13)
        result = effective_date_for_batch(monday, same_day=False)
        assert result == add_business_days(monday, 2)

    def test_same_day_ach_is_next_business_day(self):
        monday = date(2026, 4, 13)
        result = effective_date_for_batch(monday, same_day=True)
        assert result == next_business_day(monday)

    def test_result_is_always_business_day(self):
        for d in [
            date(2026, 4, 10),
            date(2026, 4, 11),
            date(2026, 4, 13),
        ]:
            assert is_business_day(effective_date_for_batch(d, same_day=False))
