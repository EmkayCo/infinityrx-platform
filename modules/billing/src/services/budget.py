"""Program financial monitoring service.

Calculates budget utilization, burn rates, projections, and generates alerts.
All money uses Decimal ROUND_HALF_UP.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from src.utils.constants import (
    ALERT_BUDGET_CRITICAL,
    ALERT_BUDGET_LOW,
    ALERT_OVER_BUDGET,
    ALERT_PROJECTED_DEPLETION,
    ALERT_SPEND_RATE_INCREASE,
    ALERT_UNUSUAL_ACTIVITY,
    BUDGET_CRITICAL_FLOOR_PCT,
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
)
from src.utils.money import money


class BudgetService:
    def __init__(self, db: Any, events: Any) -> None:
        self._db = db
        self._events = events

    def calculate_budget_stats(self, budget: dict[str, Any]) -> dict[str, Any]:
        """Calculate remaining, utilization, and over-budget flag."""
        budget_amount = money(budget["budget_amount"] or Decimal("0"))
        spent = money(budget["spent_to_date"])

        remaining = money(max(budget_amount - spent, Decimal("0")))
        over_budget = spent > budget_amount

        if budget_amount > Decimal("0"):
            utilization = money(spent / budget_amount * Decimal("100"))
        else:
            utilization = Decimal("0.00")

        return {
            "remaining": remaining,
            "utilization_percentage": utilization,
            "over_budget": over_budget,
        }

    def calculate_burn_rate(self, snapshots: list[dict[str, Any]], days: int) -> Decimal:
        """Calculate average daily spend from recent snapshots."""
        if not snapshots:
            return money(Decimal("0"))
        total = sum(money(s["daily_spend"]) for s in snapshots)
        count = len(snapshots)
        return money(total / count)

    def project_depletion_date(self, remaining: Decimal, daily_burn_rate: Decimal) -> date | None:
        """Project when the budget will deplete given current burn rate."""
        if daily_burn_rate <= Decimal("0"):
            return None
        days_remaining = int(remaining / daily_burn_rate)
        return date.today() + timedelta(days=days_remaining)

    def evaluate_alerts(
        self,
        budget: dict[str, Any],
        current_burn_7day: Decimal,
        projected_depletion_date: date | None,
        daily_claim_count: int,
        avg_daily_claim_count_30day: Decimal,
    ) -> list[dict[str, Any]]:
        """Evaluate all alert conditions. Return list of alert dicts."""
        alerts: list[dict[str, Any]] = []
        budget_amount = money(budget["budget_amount"] or Decimal("0"))
        spent = money(budget["spent_to_date"])
        remaining = money(max(budget_amount - spent, Decimal("0")))
        burn_30day_avg = money(budget.get("burn_rate_30day_avg", Decimal("0")))
        spend_increase_pct = money(budget["spend_increase_alert_pct"])
        remaining_alert_pct = money(budget["budget_remaining_alert_pct"])
        depletion_alert_days = int(budget["depletion_alert_days"])

        # Over budget
        if spent > budget_amount:
            alerts.append(
                {
                    "alert_type": ALERT_OVER_BUDGET,
                    "severity": SEVERITY_CRITICAL,
                    "message": f"Program is over budget. Spent {spent} vs budget {budget_amount}.",
                    "metric_value": spent,
                    "threshold_value": budget_amount,
                }
            )

        if budget_amount > Decimal("0"):
            remaining_pct = money(remaining / budget_amount * Decimal("100"))
        else:
            remaining_pct = Decimal("0.00")

        # Budget critical (below 10% floor)
        if remaining_pct < BUDGET_CRITICAL_FLOOR_PCT and spent <= budget_amount:
            alerts.append(
                {
                    "alert_type": ALERT_BUDGET_CRITICAL,
                    "severity": SEVERITY_CRITICAL,
                    "message": f"Budget critically low: {remaining_pct}% remaining.",
                    "metric_value": remaining_pct,
                    "threshold_value": BUDGET_CRITICAL_FLOOR_PCT,
                }
            )
        # Budget low (below configured alert pct, above critical floor)
        elif remaining_pct < remaining_alert_pct and spent <= budget_amount:
            alerts.append(
                {
                    "alert_type": ALERT_BUDGET_LOW,
                    "severity": SEVERITY_WARNING,
                    "message": f"Budget low: {remaining_pct}% remaining (threshold: {remaining_alert_pct}%).",
                    "metric_value": remaining_pct,
                    "threshold_value": remaining_alert_pct,
                }
            )

        # Spend rate increase
        if burn_30day_avg > Decimal("0") and current_burn_7day > Decimal("0"):
            increase_pct = money(
                (current_burn_7day - burn_30day_avg) / burn_30day_avg * Decimal("100")
            )
            if increase_pct > spend_increase_pct:
                alerts.append(
                    {
                        "alert_type": ALERT_SPEND_RATE_INCREASE,
                        "severity": SEVERITY_WARNING,
                        "message": f"Burn rate increased {increase_pct}% above 30-day average.",
                        "metric_value": increase_pct,
                        "threshold_value": spend_increase_pct,
                    }
                )

        # Projected depletion
        if projected_depletion_date is not None:
            days_to_depletion = (projected_depletion_date - date.today()).days
            if days_to_depletion <= depletion_alert_days:
                alerts.append(
                    {
                        "alert_type": ALERT_PROJECTED_DEPLETION,
                        "severity": SEVERITY_WARNING,
                        "message": f"Budget projected to deplete in {days_to_depletion} days.",
                        "metric_value": Decimal(str(days_to_depletion)),
                        "threshold_value": Decimal(str(depletion_alert_days)),
                    }
                )

        # Unusual claim volume (3x 30-day average)
        if avg_daily_claim_count_30day > Decimal("0"):
            volume_ratio = Decimal(str(daily_claim_count)) / avg_daily_claim_count_30day
            if volume_ratio > Decimal("3"):
                alerts.append(
                    {
                        "alert_type": ALERT_UNUSUAL_ACTIVITY,
                        "severity": SEVERITY_WARNING,
                        "message": (
                            f"Daily claim count {daily_claim_count} exceeds 3x"
                            f" the 30-day average ({avg_daily_claim_count_30day})."
                        ),
                        "metric_value": Decimal(str(daily_claim_count)),
                        "threshold_value": avg_daily_claim_count_30day * Decimal("3"),
                    }
                )

        return alerts
