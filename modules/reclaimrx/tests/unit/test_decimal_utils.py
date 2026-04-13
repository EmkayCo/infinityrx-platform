"""Tests for financial Decimal utilities — written FIRST (TDD)."""
from __future__ import annotations

from decimal import Decimal

from src.utils.money import money, penny_allocate, three_tier_recovery


class TestMoney:
    def test_converts_int_to_decimal(self) -> None:
        assert money(100) == Decimal("100.00")

    def test_converts_float_string_to_decimal(self) -> None:
        assert money("123.456") == Decimal("123.46")

    def test_rounds_half_up(self) -> None:
        assert money("0.005") == Decimal("0.01")
        assert money("0.004") == Decimal("0.00")

    def test_negative_amounts(self) -> None:
        assert money("-50.50") == Decimal("-50.50")

    def test_zero(self) -> None:
        assert money(0) == Decimal("0.00")

    def test_large_amount(self) -> None:
        assert money("999999999.99") == Decimal("999999999.99")

    def test_result_is_decimal_type(self) -> None:
        result = money(42)
        assert isinstance(result, Decimal)


class TestPennyAllocate:
    def test_even_split(self) -> None:
        result = penny_allocate(Decimal("100.00"), 4)
        assert result == [Decimal("25.00")] * 4
        assert sum(result) == Decimal("100.00")

    def test_odd_split_allocates_remainder_to_first(self) -> None:
        result = penny_allocate(Decimal("100.00"), 3)
        assert result[0] == Decimal("33.34")
        assert result[1] == Decimal("33.33")
        assert result[2] == Decimal("33.33")
        assert sum(result) == Decimal("100.00")

    def test_single_item(self) -> None:
        result = penny_allocate(Decimal("42.00"), 1)
        assert result == [Decimal("42.00")]

    def test_zero_count_returns_empty(self) -> None:
        result = penny_allocate(Decimal("100.00"), 0)
        assert result == []

    def test_sum_always_equals_total(self) -> None:
        for total_cents in [1, 7, 100, 333, 9999]:
            total = Decimal(total_cents) / 100
            for count in range(1, 11):
                result = penny_allocate(total, count)
                assert sum(result) == total, f"sum failed for total={total}, count={count}"

    def test_all_results_are_decimal(self) -> None:
        result = penny_allocate(Decimal("10.00"), 3)
        assert all(isinstance(r, Decimal) for r in result)

    def test_negative_total(self) -> None:
        result = penny_allocate(Decimal("-9.00"), 3)
        assert sum(result) == Decimal("-9.00")

    def test_one_cent_across_large_count(self) -> None:
        result = penny_allocate(Decimal("0.01"), 100)
        assert result[0] == Decimal("0.01")
        assert all(r == Decimal("0.00") for r in result[1:])
        assert sum(result) == Decimal("0.01")


class TestThreeTierRecovery:
    def test_conservative_is_highest_confidence(self) -> None:
        items = [
            {"amount": Decimal("100.00"), "confidence": "high"},
            {"amount": Decimal("50.00"), "confidence": "medium"},
            {"amount": Decimal("25.00"), "confidence": "low"},
        ]
        result = three_tier_recovery(items)
        assert result["conservative"] == Decimal("100.00")
        assert result["mid"] == Decimal("150.00")
        assert result["aggressive"] == Decimal("175.00")

    def test_empty_items_returns_zeros(self) -> None:
        result = three_tier_recovery([])
        assert result["conservative"] == Decimal("0.00")
        assert result["mid"] == Decimal("0.00")
        assert result["aggressive"] == Decimal("0.00")

    def test_all_high_confidence(self) -> None:
        items = [
            {"amount": Decimal("200.00"), "confidence": "high"},
            {"amount": Decimal("300.00"), "confidence": "high"},
        ]
        result = three_tier_recovery(items)
        assert result["conservative"] == Decimal("500.00")
        assert result["mid"] == Decimal("500.00")
        assert result["aggressive"] == Decimal("500.00")

    def test_tiers_are_monotonically_non_decreasing(self) -> None:
        items = [
            {"amount": Decimal("10.00"), "confidence": "high"},
            {"amount": Decimal("5.00"), "confidence": "medium"},
            {"amount": Decimal("3.00"), "confidence": "low"},
        ]
        result = three_tier_recovery(items)
        assert result["conservative"] <= result["mid"] <= result["aggressive"]

    def test_results_are_decimal_type(self) -> None:
        items = [{"amount": Decimal("1.00"), "confidence": "high"}]
        result = three_tier_recovery(items)
        assert isinstance(result["conservative"], Decimal)
        assert isinstance(result["mid"], Decimal)
        assert isinstance(result["aggressive"], Decimal)

    def test_penny_precision(self) -> None:
        items = [
            {"amount": Decimal("0.01"), "confidence": "high"},
            {"amount": Decimal("0.01"), "confidence": "medium"},
        ]
        result = three_tier_recovery(items)
        assert result["conservative"] == Decimal("0.01")
        assert result["mid"] == Decimal("0.02")


class TestSchemaFloatValidators:
    """Ensure float inputs are rejected/converted at schema boundary (financial safety)."""

    def test_claim_evaluate_request_float_billed_amount_converted(self) -> None:
        from src.api.schemas.schemas import ClaimEvaluateRequest
        req = ClaimEvaluateRequest(
            auth_number="AUTH001",
            date_of_service="2026-01-15",
            pharmacy_npi="1234567890",
            quantity=Decimal("30.000"),
            days_supply=30,
            billed_amount=90.0,
            paid_amount=Decimal("85.00"),
            program_type="manufacturer",
            client_type="manufacturer",
        )
        assert isinstance(req.billed_amount, Decimal)

    def test_recovery_create_float_amount_converted(self) -> None:
        from src.api.schemas.schemas import RecoveryCreate
        rec = RecoveryCreate(
            recovery_method="offset_from_payment",
            amount=500.0,
            confidence_tier="high",
            methodology_tag="Test",
        )
        assert isinstance(rec.amount, Decimal)
