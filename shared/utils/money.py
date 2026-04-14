"""Canonical money helpers for the InfinityRx platform.

Every decimal rounding operation on a monetary value goes through these
helpers. Module-local ``money.py`` / ``decimal_utils.py`` files in
billing, payment-processing, reclaimrx, and reporting re-export from
here so there is exactly one source of truth.

Principle 1 of CLAUDE.md: Decimal with ROUND_HALF_UP for all money.
No floats. Ever.

Consolidation history
---------------------
Prior to P2 of the emergency wiring pass, four independent copies of
``money()`` and ``penny_allocate()`` existed across the implemented
modules. The audit's AP-010 anti-pattern warns specifically against this
shape (copy-paste service logic), because divergence goes undetected
until a production rounding discrepancy surfaces in reconciliation.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

__all__ = [
    "TWO_PLACES",
    "ZERO",
    "money",
    "penny_allocate",
    "net_claims",
]

#: Two-decimal-place quantum for money to cents.
TWO_PLACES = Decimal("0.01")

#: Conventional zero. Use ``ZERO`` rather than ``Decimal("0")`` in money
#: accumulators so it's obvious the caller is operating on money.
ZERO = Decimal("0.00")


def money(value: Any) -> Decimal:
    """Return ``value`` as ``Decimal`` rounded to 2 decimal places (HALF_UP).

    Accepts any value that :class:`Decimal` can construct from — ``str``,
    ``int``, ``Decimal``, or even ``float`` (coerced via ``str()`` first
    to defeat IEEE 754 drift). Never pass a naked ``float`` from
    application code — wrap it here or, better, pass a ``str``.
    """
    if isinstance(value, Decimal):
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def penny_allocate(total: Decimal, count: int) -> list[Decimal]:
    """Split ``total`` into ``count`` equal parts, remainder in first item.

    Invariant: ``sum(penny_allocate(total, n)) == total`` for every valid
    input. The remainder (at most ``count - 1`` pennies) is applied to
    ``items[0]``; all other items are identical.

    Returns ``[]`` if ``count <= 0``.

    Note on negative remainder (LESSON-003): when ``per_item`` rounds up,
    the remainder can be negative and ``items[0]`` becomes *smaller* than
    the rest — not larger. Callers must not assume ``items[0] >=
    items[1]``.
    """
    if count <= 0:
        return []
    per_item = (total / count).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    allocated = [per_item] * count
    remainder = total - sum(allocated)
    allocated[0] = (allocated[0] + remainder).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    return allocated


def net_claims(amounts: list[Decimal]) -> Decimal:
    """Sum a list of amounts as Decimal(2dp, ROUND_HALF_UP).

    Used by billing for net-of-credits summation. Credits are expected
    to be represented as negative amounts by the caller.
    """
    return money(sum(amounts))
