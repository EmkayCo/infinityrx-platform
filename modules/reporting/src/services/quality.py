"""Star Ratings and medication adherence (PDC) calculation service.

PDC calculation matches CMS methodology exactly:
- Overlapping fills counted once (union of covered dates)
- Days supply truncated at period end
- Days before period start excluded
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def calculate_pdc(
    fills: list[dict[str, Any]],
    period_start: date,
    period_end: date,
) -> Decimal:
    """Calculate Proportion of Days Covered (PDC) per CMS methodology.

    Args:
        fills: list of {"fill_date": date, "days_supply": int}
        period_start: inclusive start of measurement period
        period_end: inclusive end of measurement period

    Returns:
        PDC as Decimal (0.00 to 1.00), rounded ROUND_HALF_UP to 2 decimal places
    """
    if period_start >= period_end:
        raise ValueError("period_start must be before period_end")

    total_days = (period_end - period_start).days + 1

    # Build set of covered days (union, no double-counting)
    covered_dates: set[date] = set()
    for fill in fills:
        fill_date: date = fill["fill_date"]
        days_supply: int = fill["days_supply"]

        for offset in range(days_supply):
            from datetime import timedelta

            covered_day = fill_date + timedelta(days=offset)
            # Only count days within the measurement period
            if period_start <= covered_day <= period_end:
                covered_dates.add(covered_day)

    days_covered = len(covered_dates)
    pdc = (Decimal(str(days_covered)) / Decimal(str(total_days))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return min(pdc, Decimal("1.00"))


def classify_adherence(pdc: Decimal) -> str:
    """Classify member adherence based on PDC value.

    Returns:
        "adherent" (PDC >= 0.80)
        "at_risk" (0.70 <= PDC < 0.80)
        "non_adherent" (PDC < 0.70)
    """
    if pdc >= Decimal("0.80"):
        return "adherent"
    if pdc >= Decimal("0.70"):
        return "at_risk"
    return "non_adherent"


def identify_adherence_gaps(
    fills: list[dict[str, Any]],
    as_of: date,
) -> list[dict[str, Any]]:
    """Identify gaps in medication coverage as of a given date.

    A gap is a period where the member had no active supply.
    Returns list of {"gap_start": date, "gap_end": date, "gap_days": int}
    """
    if not fills:
        return []

    from datetime import timedelta

    # Sort fills by date
    sorted_fills = sorted(fills, key=lambda f: f["fill_date"])
    gaps = []

    prev_end: date | None = None
    for fill in sorted_fills:
        fill_start: date = fill["fill_date"]
        fill_end = fill_start + timedelta(days=fill["days_supply"] - 1)

        if prev_end is not None and fill_start > prev_end + timedelta(days=1):
            gap_start = prev_end + timedelta(days=1)
            gap_end = fill_start - timedelta(days=1)
            gap_days = (gap_end - gap_start).days + 1
            gaps.append(
                {
                    "gap_start": gap_start,
                    "gap_end": gap_end,
                    "gap_days": gap_days,
                }
            )

        prev_end = max(prev_end, fill_end) if prev_end else fill_end

    # Check for gap between last fill end and as_of date
    if prev_end is not None and as_of > prev_end:
        gap_start = prev_end + timedelta(days=1)
        gap_days = (as_of - gap_start).days + 1
        gaps.append(
            {
                "gap_start": gap_start,
                "gap_end": as_of,
                "gap_days": gap_days,
            }
        )

    return gaps


def project_year_end_pdc(
    current_pdc: Decimal,
    days_elapsed: int,
    total_days: int,
) -> Decimal:
    """Project year-end PDC based on current trajectory.

    Assumes current adherence rate continues for remaining days.
    """
    if days_elapsed <= 0:
        raise ValueError("days_elapsed must be positive")

    projected = current_pdc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return min(projected, Decimal("1.00"))


def calculate_dstar_measure_rate(
    numerator: int,
    denominator: int,
) -> Decimal:
    """Calculate a D-Star quality measure rate as percentage."""
    if denominator <= 0:
        return Decimal("0.00")
    return (Decimal(str(numerator)) / Decimal(str(denominator))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
