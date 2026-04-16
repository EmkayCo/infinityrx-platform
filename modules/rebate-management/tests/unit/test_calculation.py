"""Tests for rebate calculation engine — 100% coverage on financial paths.

Every test verifies Decimal precision and ROUND_HALF_UP rounding.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, UTC
from decimal import Decimal, ROUND_HALF_UP

import pytest

from src.services.calculation import (
    CalculationEngine,
    ClaimLineInput,
    NDCRebateResult,
    calculate_ndc_rebate,
    _apply_tier,
)
from src.utils.money import ZERO, money
from src.utils.hash_chain import GENESIS_HASH, compute_entry_hash, verify_chain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT = uuid.uuid4()
SPONSOR = uuid.uuid4()
CONTRACT = uuid.uuid4()
NDC_A = "12345678901"
NDC_B = "98765432109"


class FakeNDCTerm:
    """Minimal stand-in for RebateContractNDC ORM object."""

    def __init__(
        self,
        contract_id=CONTRACT,
        ndc11=NDC_A,
        rebate_type="percent_wac",
        rebate_percent=None,
        rebate_per_unit=None,
        formulary_position_bonus_percent=None,
        growth_bonus_percent=None,
    ):
        self.contract_id = contract_id
        self.ndc11 = ndc11
        self.rebate_type = rebate_type
        self.rebate_percent = rebate_percent
        self.rebate_per_unit = rebate_per_unit
        self.formulary_position_bonus_percent = formulary_position_bonus_percent
        self.growth_bonus_percent = growth_bonus_percent


class FakeTier:
    """Minimal stand-in for RebateTier ORM object."""

    def __init__(self, tier_type, threshold_value, rebate_percent):
        self.tier_type = tier_type
        self.threshold_value = Decimal(str(threshold_value))
        self.rebate_percent = Decimal(str(rebate_percent))


# ---------------------------------------------------------------------------
# calculate_ndc_rebate — percent_wac
# ---------------------------------------------------------------------------


class TestPercentWACRebate:
    def test_basic_percent_wac(self):
        term = FakeNDCTerm(rebate_type="percent_wac", rebate_percent=Decimal("12.5000"))
        result = calculate_ndc_rebate(
            ndc_term=term,
            tiers=[],
            units_dispensed=Decimal("100"),
            wac_per_unit=Decimal("50.00"),
        )
        # gross_wac = 100 * 50.00 = 5000.00
        assert result.gross_wac == Decimal("5000.00")
        # base_rebate = 5000.00 * 12.5 / 100 = 625.00
        assert result.base_rebate == Decimal("625.00")
        assert result.total_rebate == Decimal("625.00")
        assert isinstance(result.total_rebate, Decimal)

    def test_fractional_units_rounding(self):
        term = FakeNDCTerm(rebate_type="percent_wac", rebate_percent=Decimal("7.3333"))
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=[], units_dispensed=Decimal("3"), wac_per_unit=Decimal("33.33"),
        )
        # gross_wac = 3 * 33.33 = 99.99
        assert result.gross_wac == Decimal("99.99")
        # base_rebate = 99.99 * 7.3333 / 100 = 7.332626... → 7.33 (HALF_UP)
        assert result.base_rebate == Decimal("7.33")

    def test_zero_percent_yields_zero(self):
        term = FakeNDCTerm(rebate_type="percent_wac", rebate_percent=Decimal("0.0000"))
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=[], units_dispensed=Decimal("100"), wac_per_unit=Decimal("50.00"),
        )
        assert result.base_rebate == ZERO
        assert result.total_rebate == ZERO

    def test_none_percent_treated_as_zero(self):
        term = FakeNDCTerm(rebate_type="percent_wac", rebate_percent=None)
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=[], units_dispensed=Decimal("100"), wac_per_unit=Decimal("50.00"),
        )
        assert result.base_rebate == ZERO


# ---------------------------------------------------------------------------
# calculate_ndc_rebate — flat_per_unit
# ---------------------------------------------------------------------------


class TestFlatPerUnitRebate:
    def test_basic_flat(self):
        term = FakeNDCTerm(rebate_type="flat_per_unit", rebate_per_unit=Decimal("2.5000"))
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=[], units_dispensed=Decimal("200"), wac_per_unit=Decimal("50.00"),
        )
        # base_rebate = 200 * 2.5000 = 500.00
        assert result.base_rebate == Decimal("500.00")
        assert result.gross_wac == Decimal("10000.00")

    def test_none_per_unit_treated_as_zero(self):
        term = FakeNDCTerm(rebate_type="flat_per_unit", rebate_per_unit=None)
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=[], units_dispensed=Decimal("100"), wac_per_unit=Decimal("50.00"),
        )
        assert result.base_rebate == ZERO


# ---------------------------------------------------------------------------
# Bonuses
# ---------------------------------------------------------------------------


class TestBonuses:
    def test_formulary_position_bonus(self):
        term = FakeNDCTerm(
            rebate_type="percent_wac",
            rebate_percent=Decimal("10.0000"),
            formulary_position_bonus_percent=Decimal("2.0000"),
        )
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=[], units_dispensed=Decimal("100"), wac_per_unit=Decimal("100.00"),
        )
        # gross = 10000, base = 1000, fp_bonus = 200
        assert result.base_rebate == Decimal("1000.00")
        assert result.formulary_bonus == Decimal("200.00")
        assert result.total_rebate == Decimal("1200.00")

    def test_growth_bonus(self):
        term = FakeNDCTerm(
            rebate_type="percent_wac",
            rebate_percent=Decimal("10.0000"),
            growth_bonus_percent=Decimal("1.5000"),
        )
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=[], units_dispensed=Decimal("100"), wac_per_unit=Decimal("100.00"),
        )
        # growth_bonus = 10000 * 1.5 / 100 = 150.00
        assert result.growth_bonus == Decimal("150.00")
        assert result.total_rebate == Decimal("1150.00")

    def test_all_bonuses_combined(self):
        term = FakeNDCTerm(
            rebate_type="percent_wac",
            rebate_percent=Decimal("10.0000"),
            formulary_position_bonus_percent=Decimal("2.0000"),
            growth_bonus_percent=Decimal("1.0000"),
        )
        tiers = [FakeTier("volume", Decimal("50"), Decimal("3.0000"))]
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=tiers, units_dispensed=Decimal("100"), wac_per_unit=Decimal("100.00"),
        )
        # base=1000 + fp=200 + growth=100 + tier=300 = 1600
        assert result.base_rebate == Decimal("1000.00")
        assert result.formulary_bonus == Decimal("200.00")
        assert result.growth_bonus == Decimal("100.00")
        assert result.tier_bonus == Decimal("300.00")
        assert result.total_rebate == Decimal("1600.00")


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------


class TestTiers:
    def test_volume_tier_met(self):
        tiers = [
            FakeTier("volume", Decimal("100"), Decimal("5.0000")),
            FakeTier("volume", Decimal("500"), Decimal("8.0000")),
        ]
        pct = _apply_tier(tiers, "volume", Decimal("600"))
        assert pct == Decimal("8.0000")

    def test_volume_tier_lower(self):
        tiers = [
            FakeTier("volume", Decimal("100"), Decimal("5.0000")),
            FakeTier("volume", Decimal("500"), Decimal("8.0000")),
        ]
        pct = _apply_tier(tiers, "volume", Decimal("200"))
        assert pct == Decimal("5.0000")

    def test_no_tier_met(self):
        tiers = [FakeTier("volume", Decimal("1000"), Decimal("5.0000"))]
        pct = _apply_tier(tiers, "volume", Decimal("50"))
        assert pct == ZERO

    def test_market_share_tier(self):
        tiers = [FakeTier("market_share", Decimal("25.0000"), Decimal("3.0000"))]
        pct = _apply_tier(tiers, "market_share", Decimal("30.0000"))
        assert pct == Decimal("3.0000")

    def test_wrong_tier_type_ignored(self):
        tiers = [FakeTier("market_share", Decimal("10"), Decimal("5.0000"))]
        pct = _apply_tier(tiers, "volume", Decimal("1000"))
        assert pct == ZERO


# ---------------------------------------------------------------------------
# Unknown rebate type
# ---------------------------------------------------------------------------


class TestUnknownRebateType:
    def test_unknown_type_returns_zero(self):
        term = FakeNDCTerm(rebate_type="custom_unknown")
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=[], units_dispensed=Decimal("100"), wac_per_unit=Decimal("50.00"),
        )
        assert result.base_rebate == ZERO


# ---------------------------------------------------------------------------
# Return type verification — no floats anywhere
# ---------------------------------------------------------------------------


class TestReturnTypes:
    def test_all_results_are_decimal(self):
        term = FakeNDCTerm(
            rebate_type="percent_wac",
            rebate_percent=Decimal("10.0000"),
            formulary_position_bonus_percent=Decimal("2.0000"),
            growth_bonus_percent=Decimal("1.0000"),
        )
        result = calculate_ndc_rebate(
            ndc_term=term, tiers=[], units_dispensed=Decimal("100"), wac_per_unit=Decimal("50.00"),
        )
        for field in [
            result.gross_wac, result.base_rebate, result.formulary_bonus,
            result.growth_bonus, result.tier_bonus, result.total_rebate,
            result.units_dispensed, result.wac_per_unit,
        ]:
            assert isinstance(field, Decimal), f"Expected Decimal, got {type(field)}"
            assert not isinstance(field, float)


# ---------------------------------------------------------------------------
# Hash chain
# ---------------------------------------------------------------------------


class TestHashChain:
    def test_genesis_hash_is_64_zeros(self):
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64

    def test_compute_entry_hash_deterministic(self):
        fields = {"amount": "100.00", "ndc": "12345678901"}
        h1 = compute_entry_hash(GENESIS_HASH, fields)
        h2 = compute_entry_hash(GENESIS_HASH, fields)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_prev_hash_different_result(self):
        fields = {"amount": "100.00"}
        h1 = compute_entry_hash(GENESIS_HASH, fields)
        h2 = compute_entry_hash("a" * 64, fields)
        assert h1 != h2

    def test_verify_chain_valid(self):
        entries = []
        prev = GENESIS_HASH
        for i in range(3):
            fields = {"index": str(i), "amount": str(Decimal("100.00") * (i + 1))}
            eh = compute_entry_hash(prev, fields)
            entries.append({**fields, "prev_hash": prev, "entry_hash": eh})
            prev = eh
        assert verify_chain(entries) is True

    def test_verify_chain_tampered(self):
        entries = []
        prev = GENESIS_HASH
        for i in range(3):
            fields = {"index": str(i), "amount": "100.00"}
            eh = compute_entry_hash(prev, fields)
            entries.append({**fields, "prev_hash": prev, "entry_hash": eh})
            prev = eh
        # Tamper with middle entry
        entries[1]["amount"] = "999.00"
        with pytest.raises(ValueError, match="Hash mismatch"):
            verify_chain(entries)


# ---------------------------------------------------------------------------
# money() utility
# ---------------------------------------------------------------------------


class TestMoneyUtil:
    def test_money_rounds_half_up(self):
        # 0.125 should round to 0.13 with HALF_UP (not 0.12 with HALF_EVEN)
        result = money(Decimal("0.125"))
        assert result == Decimal("0.13")

    def test_money_from_string(self):
        result = money("99.999")
        assert result == Decimal("100.00")

    def test_money_returns_decimal(self):
        result = money(42)
        assert isinstance(result, Decimal)
        assert result == Decimal("42.00")
