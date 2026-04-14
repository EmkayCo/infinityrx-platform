"""Statistical Process Control (SPC) service.

Implements X-bar control charts with Western Electric rules for anomaly detection
on real-time KPI metrics. All calculations use Decimal to prevent float drift.

Control limits: mean +- (sigma_multiplier * std_dev)
Western Electric rules detect non-random patterns beyond single-point violations.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class SPCResult:
    mean: Decimal
    std_dev: Decimal
    ucl: Decimal
    lcl: Decimal
    sigma_multiplier: Decimal
    n: int


@dataclass(frozen=True)
class WesternElectricViolation:
    rule: int
    index: int
    description: str


def calculate_control_limits(
    values: list[Decimal],
    sigma_multiplier: Decimal,
) -> SPCResult:
    """Calculate SPC control limits from a baseline series.

    Args:
        values: Historical data points (at least 2 required).
        sigma_multiplier: Number of standard deviations for control limits.

    Returns:
        SPCResult with mean, std_dev, UCL, LCL.

    Raises:
        ValueError: If fewer than 2 values provided.
    """
    if len(values) < 2:
        raise ValueError("calculate_control_limits requires at least 2 values")

    n = len(values)
    mean = sum(values, Decimal("0")) / Decimal(str(n))

    variance_sum = sum((v - mean) ** 2 for v in values)
    variance = variance_sum / Decimal(str(n))

    std_dev = _decimal_sqrt(variance)

    spread = (sigma_multiplier * std_dev).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    ucl = mean + spread
    lcl = mean - spread

    return SPCResult(
        mean=mean,
        std_dev=std_dev,
        ucl=ucl,
        lcl=lcl,
        sigma_multiplier=sigma_multiplier,
        n=n,
    )


def _decimal_sqrt(value: Decimal) -> Decimal:
    """Compute square root of a Decimal using Newton's method."""
    if value == Decimal("0"):
        return Decimal("0")
    if value < Decimal("0"):
        raise ValueError("Cannot compute sqrt of negative Decimal")
    import math

    x = Decimal(str(math.sqrt(float(value))))
    two = Decimal("2")
    for _ in range(20):
        x_next = (x + value / x) / two
        if abs(x_next - x) < Decimal("1E-10"):
            return x_next
        x = x_next
    return x


def detect_anomaly(
    value: Decimal,
    ucl: Decimal,
    lcl: Decimal,
) -> bool:
    """Return True if value exceeds UCL or falls below LCL (strictly)."""
    return value > ucl or value < lcl


def check_western_electric_rules(
    values: list[Decimal],
    mean: Decimal,
    std_dev: Decimal,
) -> list[WesternElectricViolation]:
    """Detect Western Electric rule violations in a series.

    Rules implemented:
    1. One point beyond 3-sigma.
    2. Two of three consecutive points beyond 2-sigma on the same side.
    3. Four of five consecutive points beyond 1-sigma on the same side.
    4. Eight consecutive points on the same side of the mean.

    Returns list of violations with rule number and index.
    """
    violations: list[WesternElectricViolation] = []

    if not values:
        return violations

    sigma_1 = std_dev
    sigma_2 = Decimal("2") * std_dev
    sigma_3 = Decimal("3") * std_dev

    for i, v in enumerate(values):
        deviation = v - mean

        # Rule 1: one point beyond 3-sigma (strictly)
        if abs(deviation) > sigma_3:
            violations.append(
                WesternElectricViolation(
                    rule=1,
                    index=i,
                    description=f"Point {i} beyond 3-sigma (value={v}, mean={mean})",
                )
            )

    # Rule 2: 2 of 3 consecutive points beyond 2-sigma same side
    for i in range(2, len(values)):
        window = values[i - 2 : i + 1]
        above_2s = [v for v in window if (v - mean) > sigma_2]
        below_2s = [v for v in window if (mean - v) > sigma_2]
        if len(above_2s) >= 2 or len(below_2s) >= 2:
            violations.append(
                WesternElectricViolation(
                    rule=2,
                    index=i,
                    description=f"2 of 3 consecutive points beyond 2-sigma same side (ending at {i})",
                )
            )

    # Rule 3: 4 of 5 consecutive points beyond 1-sigma same side
    for i in range(4, len(values)):
        window = values[i - 4 : i + 1]
        above_1s = [v for v in window if (v - mean) > sigma_1]
        below_1s = [v for v in window if (mean - v) > sigma_1]
        if len(above_1s) >= 4 or len(below_1s) >= 4:
            violations.append(
                WesternElectricViolation(
                    rule=3,
                    index=i,
                    description=f"4 of 5 consecutive points beyond 1-sigma same side (ending at {i})",
                )
            )

    # Rule 4: 8 consecutive points on the same side of the mean
    for i in range(7, len(values)):
        window = values[i - 7 : i + 1]
        all_above = all(v > mean for v in window)
        all_below = all(v < mean for v in window)
        if all_above or all_below:
            violations.append(
                WesternElectricViolation(
                    rule=4,
                    index=i,
                    description=f"8 consecutive points same side of mean (ending at {i})",
                )
            )

    return violations
