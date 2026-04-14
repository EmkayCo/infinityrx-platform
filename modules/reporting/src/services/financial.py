"""Financial calculation services for reporting.

ALL money operations use Decimal with ROUND_HALF_UP.
No floats. Ever.

``money()`` and ``penny_allocate()`` come from :mod:`shared.utils.money`
(single canonical implementation). Reporting-specific helpers such as
:func:`calculate_ar_aging_buckets` stay here because they aren't shared
across modules.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from shared.utils.money import money, penny_allocate

__all__ = [
    "money",
    "penny_allocate",
    "calculate_ar_aging_buckets",
    "calculate_prefund_burn_rate",
]


def calculate_ar_aging_buckets(invoices: list[dict[str, Any]], as_of: date) -> dict[str, Decimal]:
    """Bucket outstanding invoices by days overdue as of the given date."""
    buckets: dict[str, Decimal] = {
        "0_30": Decimal("0.00"),
        "31_60": Decimal("0.00"),
        "61_90": Decimal("0.00"),
        "91_120": Decimal("0.00"),
        "121_plus": Decimal("0.00"),
    }
    for inv in invoices:
        due_date: date = inv["due_date"]
        amount: Decimal = inv["amount_due"]
        days_overdue = (as_of - due_date).days
        if days_overdue <= 30:
            buckets["0_30"] += amount
        elif days_overdue <= 60:
            buckets["31_60"] += amount
        elif days_overdue <= 90:
            buckets["61_90"] += amount
        elif days_overdue <= 120:
            buckets["91_120"] += amount
        else:
            buckets["121_plus"] += amount
    return buckets


def calculate_prefund_burn_rate(total_spend: Decimal, days: int) -> Decimal:
    """Calculate average daily spend (burn rate)."""
    if days <= 0:
        raise ValueError("days must be positive")
    return (total_spend / Decimal(str(days))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_prefund_projection(balance: Decimal, daily_burn: Decimal) -> int:
    """Return the number of days until balance reaches zero."""
    if daily_burn <= Decimal("0.00"):
        raise ValueError("daily_burn must be positive")
    if balance <= Decimal("0.00"):
        return 0
    return int(balance / daily_burn)


def calculate_cash_flow(ap_total: Decimal, ar_total: Decimal) -> dict[str, Decimal]:
    """Compute net cash flow: AR in minus AP out."""
    net = ar_total - ap_total
    return {
        "ap_out": ap_total,
        "ar_in": ar_total,
        "net": net,
    }


def calculate_spread_pricing(plan_paid: Decimal, pharmacy_paid: Decimal) -> dict[str, Decimal]:
    """Calculate spread: plan paid minus pharmacy paid, with % spread."""
    if plan_paid <= Decimal("0.00"):
        raise ValueError("plan_paid must be positive")
    spread = plan_paid - pharmacy_paid
    spread_pct = (spread / plan_paid * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return {
        "plan_paid": plan_paid,
        "pharmacy_paid": pharmacy_paid,
        "spread": spread,
        "spread_pct": spread_pct,
    }


def calculate_client_profitability(
    fees_collected: Decimal, operational_costs: Decimal
) -> dict[str, Decimal]:
    """Compute client profit and margin percentage."""
    if fees_collected <= Decimal("0.00"):
        raise ValueError("fees must be positive")
    profit = fees_collected - operational_costs
    margin_pct = (profit / fees_collected * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return {
        "fees_collected": fees_collected,
        "operational_costs": operational_costs,
        "profit": profit,
        "margin_pct": margin_pct,
    }


def calculate_program_financial_summary(
    claims: list[dict[str, Any]],
) -> dict[str, Decimal]:
    """Sum spend, fees, and recoveries across all claims."""
    total_spend = Decimal("0.00")
    total_fees = Decimal("0.00")
    total_recoveries = Decimal("0.00")

    for claim in claims:
        total_spend += claim["amount_paid"]
        total_fees += claim["fee"]
        total_recoveries += claim["recovery"]

    net_spend = total_spend - total_recoveries
    return {
        "total_spend": total_spend,
        "total_fees": total_fees,
        "total_recoveries": total_recoveries,
        "net_spend": net_spend,
    }
