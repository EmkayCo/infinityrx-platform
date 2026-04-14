"""Financial Decimal utilities for ReclaimRx.

All money math uses Decimal with ROUND_HALF_UP. No floats. Ever.
numpy arrays used ONLY for ML feature vectors, never for money.

``money()`` and ``penny_allocate()`` are re-exported from
:mod:`shared.utils.money` — there is exactly one implementation in the
platform. Reclaimrx-specific helpers like :func:`three_tier_recovery`
stay here because they aren't shared across modules.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from shared.utils.money import TWO_PLACES as _TWO
from shared.utils.money import ZERO as _ZERO
from shared.utils.money import money, penny_allocate

__all__ = ["money", "penny_allocate", "three_tier_recovery"]


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
