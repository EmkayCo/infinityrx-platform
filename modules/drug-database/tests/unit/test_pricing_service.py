"""RED tests for drug pricing service.

Financial rules:
- All prices are Decimal (ROUND_HALF_UP)
- Effective date logic: most recent price where effective_date <= requested_date
- Tenant override checked FIRST before standard pricing
- Price change detection: >5% threshold (configurable)
"""
from __future__ import annotations

import sys
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from src.services.pricing import PriceChangeDetector, PricingService


class TestPricingServiceDecimal:
    """All money values must be Decimal — never float."""

    def test_price_per_unit_is_decimal(self, sample_price_row) -> None:
        assert isinstance(sample_price_row["price_per_unit"], Decimal)

    def test_no_float_in_price_rows(self, sample_price_rows) -> None:
        for row in sample_price_rows:
            assert not isinstance(row["price_per_unit"], float), "price_per_unit must be Decimal"
            if row.get("package_price") is not None:
                assert not isinstance(row["package_price"], float), "package_price must be Decimal"


class TestEffectiveDateLogic:
    def test_returns_most_recent_price_before_requested_date(self) -> None:
        prices = [
            _make_price("2026-01-01", Decimal("10.00")),
            _make_price("2026-03-01", Decimal("12.00")),
            _make_price("2026-06-01", Decimal("15.00")),
        ]
        result = PricingService.select_effective_price(prices, requested_date=date(2026, 4, 1))
        assert result["price_per_unit"] == Decimal("12.00")

    def test_does_not_return_future_price(self) -> None:
        prices = [
            _make_price("2026-01-01", Decimal("10.00")),
            _make_price("2027-01-01", Decimal("20.00")),
        ]
        result = PricingService.select_effective_price(prices, requested_date=date(2026, 6, 1))
        assert result["price_per_unit"] == Decimal("10.00")

    def test_returns_none_when_no_price_effective(self) -> None:
        prices = [_make_price("2027-01-01", Decimal("10.00"))]
        result = PricingService.select_effective_price(prices, requested_date=date(2026, 6, 1))
        assert result is None

    def test_returns_price_on_exact_effective_date(self) -> None:
        prices = [_make_price("2026-04-01", Decimal("10.00"))]
        result = PricingService.select_effective_price(prices, requested_date=date(2026, 4, 1))
        assert result is not None
        assert result["price_per_unit"] == Decimal("10.00")

    def test_excludes_terminated_price(self) -> None:
        prices = [_make_price("2026-01-01", Decimal("10.00"), termination_date=date(2026, 3, 31))]
        result = PricingService.select_effective_price(prices, requested_date=date(2026, 4, 1))
        assert result is None

    def test_includes_price_with_termination_date_in_future(self) -> None:
        prices = [_make_price("2026-01-01", Decimal("10.00"), termination_date=date(2026, 12, 31))]
        result = PricingService.select_effective_price(prices, requested_date=date(2026, 4, 1))
        assert result is not None


class TestTenantOverridePriority:
    def test_tenant_override_takes_priority_over_standard(self) -> None:
        tenant_id = uuid.uuid4()
        standard = _make_price("2026-01-01", Decimal("10.00"), source="cms_nadac")
        override = _make_price("2026-01-01", Decimal("8.50"), source="tenant_mac", tenant_id=tenant_id)

        result = PricingService.resolve_price(
            standard_prices=[standard],
            override_prices=[override],
            requested_date=date(2026, 4, 1),
        )
        assert result["price_per_unit"] == Decimal("8.50")
        assert result["data_source"] == "tenant_mac"

    def test_falls_back_to_standard_when_no_override(self) -> None:
        standard = _make_price("2026-01-01", Decimal("10.00"), source="cms_nadac")
        result = PricingService.resolve_price(
            standard_prices=[standard],
            override_prices=[],
            requested_date=date(2026, 4, 1),
        )
        assert result["price_per_unit"] == Decimal("10.00")
        assert result["data_source"] == "cms_nadac"


class TestPriceChangeDetector:
    def test_detects_increase_above_threshold(self) -> None:
        old = Decimal("10.000000")
        new = Decimal("10.600001")
        result = PriceChangeDetector.compute_change(old, new, threshold_pct=Decimal("5"))
        assert result.is_significant is True
        assert result.change_pct > Decimal("5")

    def test_ignores_change_below_threshold(self) -> None:
        old = Decimal("10.000000")
        new = Decimal("10.400000")
        result = PriceChangeDetector.compute_change(old, new, threshold_pct=Decimal("5"))
        assert result.is_significant is False

    def test_detects_decrease_above_threshold(self) -> None:
        old = Decimal("10.000000")
        new = Decimal("9.000000")
        result = PriceChangeDetector.compute_change(old, new, threshold_pct=Decimal("5"))
        assert result.is_significant is True

    def test_exactly_at_threshold_is_not_significant(self) -> None:
        old = Decimal("10.000000")
        new = Decimal("10.500000")
        result = PriceChangeDetector.compute_change(old, new, threshold_pct=Decimal("5"))
        assert result.is_significant is False

    def test_change_pct_uses_round_half_up(self) -> None:
        old = Decimal("10.000000")
        new = Decimal("10.015000")
        result = PriceChangeDetector.compute_change(old, new, threshold_pct=Decimal("5"))
        # 0.015/10.0 * 100 = 0.15%
        expected = (Decimal("0.015") / Decimal("10.0") * 100).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        assert result.change_pct == expected

    def test_zero_old_price_returns_not_significant(self) -> None:
        result = PriceChangeDetector.compute_change(
            Decimal("0"), Decimal("10.00"), threshold_pct=Decimal("5")
        )
        assert result.is_significant is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_price(
    effective_date: str,
    price: Decimal,
    termination_date: date | None = None,
    source: str = "cms_nadac",
    tenant_id: uuid.UUID | None = None,
) -> dict:
    return {
        "price_per_unit": price,
        "effective_date": date.fromisoformat(effective_date),
        "termination_date": termination_date,
        "data_source": source,
        "tenant_id": tenant_id,
    }


@pytest.fixture
def sample_price_row() -> dict:
    return _make_price("2026-01-01", Decimal("12.340000"))


@pytest.fixture
def sample_price_rows() -> list[dict]:
    return [
        _make_price("2026-01-01", Decimal("12.340000")),
        _make_price("2026-02-01", Decimal("13.000000"), termination_date=date(2026, 6, 30)),
    ]
