"""Unit tests for actuarial repricing calculations.

Financial calculations must be Decimal/ROUND_HALF_UP — no floats.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.services.actuarial_service import ActuarialService, _money


class TestActuarialMoney:
    def test_money_rounds_half_up(self) -> None:
        assert _money("100.005") == Decimal("100.01")

    def test_money_returns_decimal(self) -> None:
        result = _money(42)
        assert isinstance(result, Decimal)


class TestRepriceClaims:
    def _make_service(self) -> ActuarialService:
        db = MagicMock()
        db.execute = AsyncMock()
        return ActuarialService(db)

    @pytest.mark.asyncio
    async def test_zero_discounts_no_change(self) -> None:
        svc = self._make_service()
        claims = [{"amount_paid": "100.00"}, {"amount_paid": "200.00"}]
        result = await svc.reprice_claims(
            "tenant1",
            {
                "claims": claims,
                "formulary_discount_pct": "0.00",
                "network_discount_pct": "0.00",
                "rebate_estimate_pct": "0.00",
            },
        )
        assert Decimal(result["total_original_cost"]) == Decimal("300.00")
        assert Decimal(result["total_repriced_cost"]) == Decimal("300.00")
        assert Decimal(result["estimated_rebates"]) == Decimal("0.00")
        assert Decimal(result["net_cost"]) == Decimal("300.00")
        assert Decimal(result["estimated_savings"]) == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_10_percent_formulary_discount(self) -> None:
        svc = self._make_service()
        claims = [{"amount_paid": "1000.00"}]
        result = await svc.reprice_claims(
            "tenant1",
            {
                "claims": claims,
                "formulary_discount_pct": "10.00",
                "network_discount_pct": "0.00",
                "rebate_estimate_pct": "0.00",
            },
        )
        assert Decimal(result["total_repriced_cost"]) == Decimal("900.00")

    @pytest.mark.asyncio
    async def test_rebates_subtracted_from_repriced(self) -> None:
        svc = self._make_service()
        claims = [{"amount_paid": "1000.00"}]
        result = await svc.reprice_claims(
            "tenant1",
            {
                "claims": claims,
                "formulary_discount_pct": "0.00",
                "network_discount_pct": "0.00",
                "rebate_estimate_pct": "10.00",
            },
        )
        assert Decimal(result["estimated_rebates"]) == Decimal("100.00")
        assert Decimal(result["net_cost"]) == Decimal("900.00")

    @pytest.mark.asyncio
    async def test_savings_equals_original_minus_net(self) -> None:
        svc = self._make_service()
        claims = [{"amount_paid": "500.00"}, {"amount_paid": "500.00"}]
        result = await svc.reprice_claims(
            "tenant1",
            {
                "claims": claims,
                "formulary_discount_pct": "5.00",
                "network_discount_pct": "5.00",
                "rebate_estimate_pct": "5.00",
            },
        )
        original = Decimal(result["total_original_cost"])
        net = Decimal(result["net_cost"])
        savings = Decimal(result["estimated_savings"])
        assert savings == original - net

    @pytest.mark.asyncio
    async def test_all_monetary_outputs_are_strings_of_decimal(self) -> None:
        svc = self._make_service()
        result = await svc.reprice_claims(
            "t1",
            {
                "claims": [{"amount_paid": "100.00"}],
                "formulary_discount_pct": "0",
                "network_discount_pct": "0",
                "rebate_estimate_pct": "0",
            },
        )
        for key in [
            "total_original_cost",
            "total_repriced_cost",
            "estimated_rebates",
            "net_cost",
            "estimated_savings",
        ]:
            val = Decimal(result[key])
            assert isinstance(val, Decimal)
            assert "e" not in result[key].lower()  # no scientific notation

    @pytest.mark.asyncio
    async def test_empty_claims_returns_zeros(self) -> None:
        svc = self._make_service()
        result = await svc.reprice_claims("t1", {"claims": []})
        assert Decimal(result["total_original_cost"]) == Decimal("0.00")
        assert Decimal(result["estimated_savings"]) == Decimal("0.00")
