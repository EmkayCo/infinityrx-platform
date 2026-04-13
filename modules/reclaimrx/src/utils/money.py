"""Financial Decimal utilities for ReclaimRx.

All money math uses Decimal with ROUND_HALF_UP. No floats. Ever.
numpy arrays used ONLY for ML feature vectors, never for money.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

_TWO = Decimal("0.01")
_ZERO = Decimal("0.00")


def money(value: Any) -> Decimal:
    """Convert any numeric value to Decimal with 2 decimal places, ROUND_HALF_UP."""
    if isinstance(value, Decimal):
        return value.quantize(_TWO, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(_TWO, rounding=ROUND_HALF_UP)


def penny_allocate(total: Decimal, count: int) -> list[Decimal]:
    """Split total into count equal parts, allocating remainder penny to first item.

    Guarantees: sum(result) == total for any valid inputs.
    """
    if count <= 0:
        return []
    per_item = (total / count).quantize(_TWO, rounding=ROUND_HALF_UP)
    allocated = [per_item] * count
    remainder = total - sum(allocated)
    # remainder is always a multiple of 0.01 (possibly negative)
    allocated[0] = (allocated[0] + remainder).quantize(_TWO, rounding=ROUND_HALF_UP)
    return allocated


def three_tier_recovery(items: list[dict]) -> dict[str, Decimal]:
    """Calculate conservative/mid/aggressive recovery from tiered confidence items.

    - conservative: sum of "high" confidence items only
    - mid: sum of "high" + "medium" confidence items
    - aggressive: sum of all items (high + medium + low)

    Each item must have: {"amount": Decimal, "confidence": "high"|"medium"|"low"}
    All amounts calculated with ROUND_HALF_UP at each step.
    """
    conservative = _ZERO
    mid = _ZERO
    aggressive = _ZERO

    for item in items:
        amt = item["amount"].quantize(_TWO, rounding=ROUND_HALF_UP)
        confidence = item["confidence"]
        aggressive = (aggressive + amt).quantize(_TWO, rounding=ROUND_HALF_UP)
        if confidence in ("high", "medium"):
            mid = (mid + amt).quantize(_TWO, rounding=ROUND_HALF_UP)
        if confidence == "high":
            conservative = (conservative + amt).quantize(_TWO, rounding=ROUND_HALF_UP)

    return {
        "conservative": conservative,
        "mid": mid,
        "aggressive": aggressive,
    }
