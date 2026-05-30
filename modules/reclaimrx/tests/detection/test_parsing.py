"""Tests for money/date parsing helpers in detection.parsing.

TDD: these tests are written first (RED) before the implementation exists.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date


def test_parse_money_and_date():
    from src.detection.parsing import parse_money, parse_dos

    # parse_money: valid values
    assert parse_money("809.80") == Decimal("809.80")
    assert parse_money("-50.0") == Decimal("-50.0")

    # parse_money: empty / whitespace -> None
    assert parse_money("") is None
    assert parse_money("  ") is None

    # parse_dos: valid ISO date within bounds
    assert parse_dos("2024-12-31") == date(2024, 12, 31)

    # parse_dos: sentinel / garbage dates outside valid range -> None
    assert parse_dos("9999-09-09") is None   # far future sentinel rejected
    assert parse_dos("") is None
    assert parse_dos("1989-01-01") is None    # before 1990 floor rejected


def test_parse_money_invalid_strings():
    """Non-numeric strings must return None (catch InvalidOperation/ValueError)."""
    from src.detection.parsing import parse_money

    assert parse_money("abc") is None
    assert parse_money("$10.00") is None
    assert parse_money(None) is None  # type: ignore[arg-type]


def test_parse_money_never_float():
    """Returned value must be Decimal, never float."""
    from src.detection.parsing import parse_money

    result = parse_money("12.34")
    assert isinstance(result, Decimal)


def test_parse_dos_floor_boundary():
    """1990-01-01 is the floor — valid; 1989-12-31 is rejected."""
    from src.detection.parsing import parse_dos

    assert parse_dos("1990-01-01") == date(1990, 1, 1)
    assert parse_dos("1989-12-31") is None


def test_parse_dos_today_is_valid():
    """Today's date is a valid DOS."""
    from src.detection.parsing import parse_dos

    today = date.today()
    assert parse_dos(today.isoformat()) == today


def test_parse_dos_tomorrow_is_invalid():
    """A date after today is rejected (future DOS not allowed)."""
    from datetime import timedelta
    from src.detection.parsing import parse_dos

    tomorrow = date.today() + timedelta(days=1)
    assert parse_dos(tomorrow.isoformat()) is None


def test_parse_dos_invalid_format():
    """Non-ISO date strings must return None."""
    from src.detection.parsing import parse_dos

    assert parse_dos("12/31/2024") is None
    assert parse_dos("not-a-date") is None
    assert parse_dos(None) is None  # type: ignore[arg-type]
