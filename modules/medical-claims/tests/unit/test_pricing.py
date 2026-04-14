"""Unit tests for pricing logic — 100% coverage required (financial path)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal


from src.services.pricing_service import (
    PricingService,
    quarter_for_date,
)


class TestQuarterForDate:
    def test_q1_january(self):
        assert quarter_for_date(date(2026, 1, 1)) == "2026-Q1"

    def test_q1_march(self):
        assert quarter_for_date(date(2026, 3, 31)) == "2026-Q1"

    def test_q2_april(self):
        assert quarter_for_date(date(2026, 4, 1)) == "2026-Q2"

    def test_q3_july(self):
        assert quarter_for_date(date(2026, 7, 15)) == "2026-Q3"

    def test_q4_october(self):
        assert quarter_for_date(date(2026, 10, 1)) == "2026-Q4"

    def test_q4_december(self):
        assert quarter_for_date(date(2026, 12, 31)) == "2026-Q4"


class TestAspAllowedAmount:
    """Financial precision tests — all amounts must use ROUND_HALF_UP."""

    def test_basic_asp_calculation(self, db_session):
        svc = PricingService(db_session)
        # ASP + 6%: 100.000000 * 1.06 * 1.0 = 106.00
        result = svc.calculate_asp_allowed(
            asp_per_unit=Decimal("100.000000"),
            quantity=Decimal("1.000"),
        )
        assert result == Decimal("106.00")

    def test_asp_calculation_preserves_6dp_before_multiply(self, db_session):
        svc = PricingService(db_session)
        # asp=10.123456, qty=2.5 → (10.123456 * 1.06) * 2.5 = 26.82718... → 26.83
        result = svc.calculate_asp_allowed(
            asp_per_unit=Decimal("10.123456"),
            quantity=Decimal("2.500"),
        )
        expected = (Decimal("10.123456") * Decimal("1.06") * Decimal("2.5")).quantize(
            Decimal("0.01"), rounding=__import__("decimal").ROUND_HALF_UP
        )
        assert result == expected

    def test_asp_never_uses_float(self, db_session):
        svc = PricingService(db_session)
        result = svc.calculate_asp_allowed(
            asp_per_unit=Decimal("0.333333"),
            quantity=Decimal("3.000"),
        )
        assert isinstance(result, Decimal)

    def test_asp_result_is_two_decimal_places(self, db_session):
        svc = PricingService(db_session)
        result = svc.calculate_asp_allowed(
            asp_per_unit=Decimal("9.999999"),
            quantity=Decimal("1.000"),
        )
        # Verify 2dp
        assert result == result.quantize(Decimal("0.01"))

    def test_zero_quantity_gives_zero_allowed(self, db_session):
        svc = PricingService(db_session)
        result = svc.calculate_asp_allowed(
            asp_per_unit=Decimal("100.000000"),
            quantity=Decimal("0.000"),
        )
        assert result == Decimal("0.00")


class TestWasteCalculation:
    def test_waste_is_billed_minus_administered(self, db_session):
        svc = PricingService(db_session)
        waste_qty, waste_amt = svc.calculate_waste(
            billed_quantity=Decimal("2.000"),
            administered_quantity=Decimal("1.500"),
            drug_unit_price=Decimal("100.000000"),
        )
        assert waste_qty == Decimal("0.500")
        assert waste_amt == Decimal("50.00")

    def test_waste_never_negative(self, db_session):
        svc = PricingService(db_session)
        # Administered exceeds billed (data error) → waste = 0
        waste_qty, waste_amt = svc.calculate_waste(
            billed_quantity=Decimal("1.000"),
            administered_quantity=Decimal("1.500"),
            drug_unit_price=Decimal("100.000000"),
        )
        assert waste_qty == Decimal("0.000")
        assert waste_amt == Decimal("0.00")

    def test_waste_amount_uses_6dp_unit_price(self, db_session):
        svc = PricingService(db_session)
        waste_qty, waste_amt = svc.calculate_waste(
            billed_quantity=Decimal("3.000"),
            administered_quantity=Decimal("2.000"),
            drug_unit_price=Decimal("9.999999"),
        )
        expected_amt = (Decimal("1.000") * Decimal("9.999999")).quantize(
            Decimal("0.01"), rounding=__import__("decimal").ROUND_HALF_UP
        )
        assert waste_amt == expected_amt

    def test_waste_decimal_type(self, db_session):
        svc = PricingService(db_session)
        waste_qty, waste_amt = svc.calculate_waste(
            Decimal("2.000"), Decimal("1.000"), Decimal("50.000000")
        )
        assert isinstance(waste_qty, Decimal)
        assert isinstance(waste_amt, Decimal)


class TestAspUpsert:
    def test_upsert_creates_record(self, db_session):
        svc = PricingService(db_session)
        record = svc.upsert_asp(
            hcpcs_code="J0135",
            quarter="2026-Q1",
            effective_date=date(2026, 1, 1),
            asp_per_unit=Decimal("15.500000"),
        )
        assert record.hcpcs_code == "J0135"
        assert record.asp_per_unit == Decimal("15.500000")
        # Payment limit = ASP + 6%
        expected_limit = (Decimal("15.500000") * Decimal("1.06")).quantize(
            Decimal("0.000001"), rounding=__import__("decimal").ROUND_HALF_UP
        )
        assert record.payment_limit == expected_limit

    def test_upsert_updates_existing(self, db_session):
        svc = PricingService(db_session)
        svc.upsert_asp("J9035", "2026-Q2", date(2026, 4, 1), Decimal("200.000000"))
        updated = svc.upsert_asp("J9035", "2026-Q2", date(2026, 4, 1), Decimal("210.000000"))
        assert updated.asp_per_unit == Decimal("210.000000")

    def test_asp_per_unit_stored_as_6dp(self, db_session):
        svc = PricingService(db_session)
        record = svc.upsert_asp("J0881", "2026-Q3", date(2026, 7, 1), Decimal("1.23"))
        # Must be stored as 6dp
        assert record.asp_per_unit == Decimal("1.230000")


class TestAspPricingLookup:
    def test_exact_quarter_match(self, db_session):
        svc = PricingService(db_session)
        svc.upsert_asp("J0185", "2026-Q1", date(2026, 1, 1), Decimal("50.000000"))
        result = svc.get_asp_pricing("J0185", date(2026, 2, 15))
        assert result is not None
        assert result.quarter == "2026-Q1"

    def test_fallback_to_prior_quarter(self, db_session):
        svc = PricingService(db_session)
        svc.upsert_asp("J0190", "2025-Q4", date(2025, 10, 1), Decimal("75.000000"))
        # Query for Q1 2026 — no record, falls back to Q4 2025
        result = svc.get_asp_pricing("J0190", date(2026, 1, 15))
        assert result is not None
        assert result.quarter == "2025-Q4"

    def test_returns_none_when_no_pricing(self, db_session):
        svc = PricingService(db_session)
        result = svc.get_asp_pricing("J9999", date(2026, 1, 1))
        assert result is None
