"""Tests for derive_fields() — derived financial fields from CSV claim rows.

TDD — RED first, then GREEN.

Semantic contract (LOCKED — verified by hand against real data):
- extended_wac is a TOTAL (WAC * qty already multiplied in). Never divide by qty.
- drug_awp is a TOTAL.
- nq  = ingredient_cost_paid  (Decimal)
- dv  = dispensing_fee_paid   (Decimal)
- nq_to_wac_ratio = (dv + nq) / extended_wac  [None when extended_wac == 0]
- dv_to_awp_ratio = dv / drug_awp              [None when drug_awp == 0]
- Reversals (transaction_code == 'B2'): abs() applied to amounts before ratios.

Financial precision: Decimal only, never float. ROUND_HALF_UP on every quantize.
Note on round(Decimal, 4): Python's built-in round() uses banker's rounding on
Decimal; the golden assertions use round() for display comparison only. The stored
ratio values are full-precision Decimal — no quantize is applied inside derive_fields
so downstream callers control precision. The three golden values happen to be
unambiguous at 4 places (no tie-breaking needed) so round() and ROUND_HALF_UP agree.
"""
from __future__ import annotations

from decimal import Decimal


# ---------------------------------------------------------------------------
# Golden-row assertions (hand-verified against real data rows)
# ---------------------------------------------------------------------------

def test_nq_to_wac_golden_rows():
    """Three real data rows must produce the specified 4-decimal ratios."""
    from src.detection.rule_evaluators import derive_fields

    r = derive_fields({
        "extended_wac": "186.19",
        "ingredient_cost_paid": "215.17",
        "dispensing_fee_paid": "1.5",
        "drug_awp": "256.16",
        "quantity_dispensed": "28",
    })
    assert round(r["nq_to_wac_ratio"], 4) == Decimal("1.1637")   # (1.5+215.17)/186.19

    r2 = derive_fields({
        "extended_wac": "171.50",
        "ingredient_cost_paid": "186.5",
        "dispensing_fee_paid": "0.0",
        "drug_awp": "658.36",
        "quantity_dispensed": "45",
    })
    assert round(r2["nq_to_wac_ratio"], 4) == Decimal("1.0875")

    r3 = derive_fields({
        "extended_wac": "1086.62",
        "ingredient_cost_paid": "1101.62",
        "dispensing_fee_paid": "0.0",
        "drug_awp": "1512.00",
        "quantity_dispensed": "60",
    })
    assert round(r3["nq_to_wac_ratio"], 4) == Decimal("1.0138")


def test_dv_to_awp_ratio_normal_row():
    """dv_to_awp_ratio = dispensing_fee_paid / drug_awp on a normal row."""
    from src.detection.rule_evaluators import derive_fields

    # Row 1: dv=1.5, awp=256.16 -> 1.5/256.16 = 0.005855...
    r = derive_fields({
        "extended_wac": "186.19",
        "ingredient_cost_paid": "215.17",
        "dispensing_fee_paid": "1.5",
        "drug_awp": "256.16",
        "quantity_dispensed": "28",
    })
    assert round(r["dv_to_awp_ratio"], 4) == Decimal("0.0059")
    assert isinstance(r["dv_to_awp_ratio"], Decimal)


# ---------------------------------------------------------------------------
# Zero-basis guard
# ---------------------------------------------------------------------------

def test_zero_basis_is_none():
    """When extended_wac == 0 and drug_awp == 0 both ratios must be None."""
    from src.detection.rule_evaluators import derive_fields

    out = derive_fields({
        "extended_wac": "0",
        "ingredient_cost_paid": "5",
        "dispensing_fee_paid": "0",
        "drug_awp": "0",
        "quantity_dispensed": "1",
    })
    assert out["nq_to_wac_ratio"] is None
    assert out["dv_to_awp_ratio"] is None


def test_zero_wac_only_wac_ratio_is_none():
    """When only extended_wac == 0, only nq_to_wac_ratio is None."""
    from src.detection.rule_evaluators import derive_fields

    out = derive_fields({
        "extended_wac": "0",
        "ingredient_cost_paid": "5",
        "dispensing_fee_paid": "1",
        "drug_awp": "100.00",
        "quantity_dispensed": "1",
    })
    assert out["nq_to_wac_ratio"] is None
    assert out["dv_to_awp_ratio"] is not None  # 1/100 = 0.01


def test_zero_awp_only_awp_ratio_is_none():
    """When only drug_awp == 0, only dv_to_awp_ratio is None."""
    from src.detection.rule_evaluators import derive_fields

    out = derive_fields({
        "extended_wac": "100.00",
        "ingredient_cost_paid": "5",
        "dispensing_fee_paid": "1",
        "drug_awp": "0",
        "quantity_dispensed": "1",
    })
    assert out["nq_to_wac_ratio"] is not None
    assert out["dv_to_awp_ratio"] is None


# ---------------------------------------------------------------------------
# B2 reversal: abs() applied before ratio computation
# ---------------------------------------------------------------------------

def test_b2_reversal_uses_abs():
    """For transaction_code == 'B2', abs() is applied to amounts; ratios match the
    positive-amount row exactly."""
    from src.detection.rule_evaluators import derive_fields

    r = derive_fields({
        "extended_wac": "186.19",
        "ingredient_cost_paid": "-215.17",
        "dispensing_fee_paid": "-1.5",
        "drug_awp": "256.16",
        "quantity_dispensed": "28",
        "transaction_code": "B2",
    })
    assert round(r["nq_to_wac_ratio"], 4) == Decimal("1.1637")   # abs applied


def test_b2_reversal_positive_wac_uses_abs():
    """extended_wac and drug_awp also receive abs() under B2 (cover sign-flip on
    denominator)."""
    from src.detection.rule_evaluators import derive_fields

    r = derive_fields({
        "extended_wac": "-186.19",
        "ingredient_cost_paid": "-215.17",
        "dispensing_fee_paid": "-1.5",
        "drug_awp": "-256.16",
        "quantity_dispensed": "28",
        "transaction_code": "B2",
    })
    # All amounts negated → abs → same computation → same ratio
    assert round(r["nq_to_wac_ratio"], 4) == Decimal("1.1637")
    assert round(r["dv_to_awp_ratio"], 4) == Decimal("0.0059")


def test_non_b2_transaction_does_not_abs():
    """A B1 (normal claim) with negative amounts is NOT abs()-ed; sign is preserved."""
    from src.detection.rule_evaluators import derive_fields

    # Negative nq, positive wac → ratio will be negative
    r = derive_fields({
        "extended_wac": "186.19",
        "ingredient_cost_paid": "-215.17",
        "dispensing_fee_paid": "-1.5",
        "drug_awp": "256.16",
        "quantity_dispensed": "28",
        "transaction_code": "B1",
    })
    # (dv+nq) / wac = (-1.5 + -215.17) / 186.19 = negative
    assert r["nq_to_wac_ratio"] < Decimal("0")


# ---------------------------------------------------------------------------
# Return-type / Decimal invariants
# ---------------------------------------------------------------------------

def test_return_values_are_decimal_not_float():
    """nq, dv, and computed ratios must all be Decimal instances, never float."""
    from src.detection.rule_evaluators import derive_fields

    r = derive_fields({
        "extended_wac": "186.19",
        "ingredient_cost_paid": "215.17",
        "dispensing_fee_paid": "1.5",
        "drug_awp": "256.16",
        "quantity_dispensed": "28",
    })
    assert isinstance(r["nq"], Decimal)
    assert isinstance(r["dv"], Decimal)
    assert isinstance(r["nq_to_wac_ratio"], Decimal)
    assert isinstance(r["dv_to_awp_ratio"], Decimal)


def test_nq_equals_ingredient_cost_paid():
    """nq must equal the parsed ingredient_cost_paid exactly."""
    from src.detection.rule_evaluators import derive_fields

    r = derive_fields({
        "extended_wac": "100.00",
        "ingredient_cost_paid": "99.50",
        "dispensing_fee_paid": "2.00",
        "drug_awp": "120.00",
        "quantity_dispensed": "30",
    })
    assert r["nq"] == Decimal("99.50")
    assert r["dv"] == Decimal("2.00")


def test_missing_amounts_treated_as_zero():
    """Missing / None money fields must default to Decimal('0') not raise."""
    from src.detection.rule_evaluators import derive_fields

    r = derive_fields({
        "extended_wac": "100.00",
        "drug_awp": "120.00",
        "quantity_dispensed": "30",
        # ingredient_cost_paid and dispensing_fee_paid absent
    })
    assert r["nq"] == Decimal("0")
    assert r["dv"] == Decimal("0")
    # nq_to_wac_ratio = 0/100 = 0
    assert r["nq_to_wac_ratio"] == Decimal("0")


def test_quantity_dispensed_not_used_in_ratio():
    """quantity_dispensed must NOT divide or multiply in ratio computation —
    extended_wac is already a total. Two rows identical except qty must give
    identical ratios."""
    from src.detection.rule_evaluators import derive_fields

    base = {
        "extended_wac": "186.19",
        "ingredient_cost_paid": "215.17",
        "dispensing_fee_paid": "1.5",
        "drug_awp": "256.16",
    }
    r_28 = derive_fields({**base, "quantity_dispensed": "28"})
    r_99 = derive_fields({**base, "quantity_dispensed": "99"})
    assert r_28["nq_to_wac_ratio"] == r_99["nq_to_wac_ratio"]
