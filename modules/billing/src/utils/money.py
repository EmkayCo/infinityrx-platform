"""Decimal money helpers — ROUND_HALF_UP only. No floats ever."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def money(value: object) -> Decimal:
    """Convert any numeric to Decimal with 2 decimal places, ROUND_HALF_UP."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def penny_allocate(total: Decimal, count: int) -> list[Decimal]:
    """Split total into count equal parts; remainder penny goes to first item.

    Invariant: sum(result) == total for any valid inputs.
    """
    if count <= 0:
        return []
    per_item = (total / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    allocated = [per_item] * count
    remainder = total - sum(allocated)
    allocated[0] += remainder
    return allocated


def net_claims(amounts: list[Decimal]) -> Decimal:
    """Net a list of amounts (credits are negative). Result is ROUND_HALF_UP."""
    return money(sum(amounts))
