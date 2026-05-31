"""Calibration primitives for outlier-mode statistical detection rules.

Pure functions -- no I/O, no DB, no side effects.
Financial precision: Decimal only, never float in return values.
Used by Phase 2 recalibrated rules (MFR-003/004, HP-005/008, ALL-005/006).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

_ZERO = Decimal("0")
_ONE = Decimal("1")


def passes_min_sample(*, sample_count: int, min_required: int) -> bool:
    """Return True if sample_count >= min_required."""
    return sample_count >= min_required


def passes_dollar_floor(
    amount: Decimal,
    floor: Optional[Decimal],
) -> bool:
    """Return True if amount >= floor (or floor is None -- no floor check)."""
    if floor is None:
        return True
    return amount >= floor


def zscore_flag(
    *,
    value: Decimal,
    mean: Decimal,
    stddev: Decimal,
    z_threshold: Decimal,
) -> tuple[bool, Optional[Decimal]]:
    """Compute z-score and return (fired, z).

    fired = True when abs(z) >= z_threshold AND stddev > 0.
    Returns (False, None) when stddev == 0 (undefined z).
    z is always positive (we flag outliers above the mean for volume/cost rules).
    """
    if stddev == _ZERO:
        return False, None
    z = (value - mean) / stddev
    fired = z >= z_threshold
    return bool(fired), z.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def percentile_within_cohort(
    value: Decimal,
    cohort_values: list[Decimal],
) -> Optional[Decimal]:
    """Return the proportion of cohort_values at or below value (0.0-1.0).

    Returns None if cohort is empty.
    Uses a simple empirical CDF: (count at or below) / n.
    Maximum value in cohort always returns 1.0.

    This is a pure-Python implementation suitable for moderate cohort sizes
    (hundreds to low thousands of distinct scope-keys). For very large cohorts,
    use SQL percentile_cont instead.
    """
    if not cohort_values:
        return None
    n = len(cohort_values)
    below = sum(1 for v in cohort_values if v < value)
    equal = sum(1 for v in cohort_values if v == value)
    # Rank = proportion at or below value; top value returns exactly 1.0.
    rank = Decimal(str(below + equal))
    pct = rank / Decimal(str(n))
    return pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
