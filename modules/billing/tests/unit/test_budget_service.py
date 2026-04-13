"""Unit tests for program budget monitoring service."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from src.services.budget import BudgetService
from src.utils.constants import (
    ALERT_BUDGET_CRITICAL,
    ALERT_BUDGET_LOW,
    ALERT_OVER_BUDGET,
    ALERT_PROJECTED_DEPLETION,
    ALERT_UNUSUAL_ACTIVITY,
    BUDGET_ANNUAL,
    SEVERITY_CRITICAL,
)
from src.utils.money import money

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLIENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROGRAM = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


def _svc(events=None) -> BudgetService:
    return BudgetService(db=MagicMock(), events=events or MagicMock())


def _budget(
    budget_amount: Decimal = Decimal("100000.00"),
    spent_to_date: Decimal = Decimal("0.00"),
    spend_increase_alert_pct: Decimal = Decimal("25"),
    budget_remaining_alert_pct: Decimal = Decimal("20"),
    depletion_alert_days: int = 30,
) -> dict:
    return {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "client_id": CLIENT,
        "program_id": PROGRAM,
        "budget_type": BUDGET_ANNUAL,
        "budget_amount": budget_amount,
        "spent_to_date": spent_to_date,
        "burn_rate_30day_avg": Decimal("100.00"),
        "spend_increase_alert_pct": spend_increase_alert_pct,
        "budget_remaining_alert_pct": budget_remaining_alert_pct,
        "depletion_alert_days": depletion_alert_days,
    }


class TestBudgetCalculation:
    def test_remaining_calculated_correctly(self) -> None:
        svc = _svc()
        budget = _budget(budget_amount=Decimal("10000.00"), spent_to_date=Decimal("3000.00"))
        result = svc.calculate_budget_stats(budget)
        assert result["remaining"] == money("7000.00")

    def test_utilization_percentage(self) -> None:
        svc = _svc()
        budget = _budget(budget_amount=Decimal("10000.00"), spent_to_date=Decimal("2500.00"))
        result = svc.calculate_budget_stats(budget)
        assert result["utilization_percentage"] == money("25.00")

    def test_all_amounts_are_decimal(self) -> None:
        svc = _svc()
        budget = _budget()
        result = svc.calculate_budget_stats(budget)
        assert isinstance(result["remaining"], Decimal)
        assert isinstance(result["utilization_percentage"], Decimal)

    def test_over_budget_sets_remaining_to_zero(self) -> None:
        svc = _svc()
        budget = _budget(
            budget_amount=Decimal("10000.00"),
            spent_to_date=Decimal("11000.00"),
        )
        result = svc.calculate_budget_stats(budget)
        assert result["over_budget"] is True


class TestBurnRateCalculation:
    def test_daily_burn_rate_from_snapshots(self) -> None:
        svc = _svc()
        today = date.today()
        snapshots = [
            {"snapshot_date": today - timedelta(days=i), "daily_spend": Decimal("200.00")}
            for i in range(1, 8)
        ]
        rate = svc.calculate_burn_rate(snapshots, days=7)
        assert rate == money("200.00")

    def test_empty_snapshots_returns_zero(self) -> None:
        svc = _svc()
        rate = svc.calculate_burn_rate([], days=7)
        assert rate == money("0.00")

    def test_burn_rate_is_decimal(self) -> None:
        svc = _svc()
        today = date.today()
        snapshots = [{"snapshot_date": today - timedelta(days=1), "daily_spend": Decimal("100.00")}]
        rate = svc.calculate_burn_rate(snapshots, days=7)
        assert isinstance(rate, Decimal)


class TestProjectionCalculation:
    def test_depletion_date_from_burn_rate(self) -> None:
        svc = _svc()
        # 7000 remaining, 100/day burn → 70 days
        depletion = svc.project_depletion_date(
            remaining=Decimal("7000.00"),
            daily_burn_rate=Decimal("100.00"),
        )
        expected = date.today() + timedelta(days=70)
        assert depletion == expected

    def test_zero_burn_rate_returns_none(self) -> None:
        svc = _svc()
        depletion = svc.project_depletion_date(
            remaining=Decimal("7000.00"),
            daily_burn_rate=Decimal("0.00"),
        )
        assert depletion is None


class TestAlertGeneration:
    def test_over_budget_generates_critical_alert(self) -> None:
        svc = _svc()
        alerts = svc.evaluate_alerts(
            budget=_budget(
                budget_amount=Decimal("10000.00"),
                spent_to_date=Decimal("11000.00"),
            ),
            current_burn_7day=Decimal("100.00"),
            projected_depletion_date=None,
            daily_claim_count=50,
            avg_daily_claim_count_30day=Decimal("20.00"),
        )
        types = {a["alert_type"] for a in alerts}
        severities = {a["severity"] for a in alerts}
        assert ALERT_OVER_BUDGET in types
        assert SEVERITY_CRITICAL in severities

    def test_budget_below_20pct_generates_warning(self) -> None:
        svc = _svc()
        budget = _budget(
            budget_amount=Decimal("10000.00"),
            spent_to_date=Decimal("8500.00"),  # 15% remaining
            budget_remaining_alert_pct=Decimal("20"),
        )
        alerts = svc.evaluate_alerts(
            budget=budget,
            current_burn_7day=Decimal("100.00"),
            projected_depletion_date=None,
            daily_claim_count=10,
            avg_daily_claim_count_30day=Decimal("10.00"),
        )
        types = {a["alert_type"] for a in alerts}
        assert ALERT_BUDGET_LOW in types

    def test_budget_below_10pct_generates_critical(self) -> None:
        svc = _svc()
        budget = _budget(
            budget_amount=Decimal("10000.00"),
            spent_to_date=Decimal("9500.00"),  # 5% remaining
            budget_remaining_alert_pct=Decimal("20"),
        )
        alerts = svc.evaluate_alerts(
            budget=budget,
            current_burn_7day=Decimal("100.00"),
            projected_depletion_date=None,
            daily_claim_count=10,
            avg_daily_claim_count_30day=Decimal("10.00"),
        )
        types = {a["alert_type"]: a for a in alerts}
        assert ALERT_BUDGET_CRITICAL in types
        assert types[ALERT_BUDGET_CRITICAL]["severity"] == SEVERITY_CRITICAL

    def test_projected_depletion_within_30_days_generates_warning(self) -> None:
        svc = _svc()
        budget = _budget(depletion_alert_days=30)
        soon = date.today() + timedelta(days=15)
        alerts = svc.evaluate_alerts(
            budget=budget,
            current_burn_7day=Decimal("100.00"),
            projected_depletion_date=soon,
            daily_claim_count=10,
            avg_daily_claim_count_30day=Decimal("10.00"),
        )
        types = {a["alert_type"] for a in alerts}
        assert ALERT_PROJECTED_DEPLETION in types

    def test_unusual_claim_volume_3x_average(self) -> None:
        svc = _svc()
        budget = _budget()
        alerts = svc.evaluate_alerts(
            budget=budget,
            current_burn_7day=Decimal("100.00"),
            projected_depletion_date=None,
            daily_claim_count=100,
            avg_daily_claim_count_30day=Decimal("30.00"),  # 3.33x = unusual
        )
        types = {a["alert_type"] for a in alerts}
        assert ALERT_UNUSUAL_ACTIVITY in types

    def test_no_alerts_for_healthy_program(self) -> None:
        svc = _svc()
        budget = _budget(
            budget_amount=Decimal("100000.00"),
            spent_to_date=Decimal("10000.00"),  # 90% remaining
        )
        alerts = svc.evaluate_alerts(
            budget=budget,
            current_burn_7day=Decimal("100.00"),
            projected_depletion_date=date.today() + timedelta(days=365),
            daily_claim_count=10,
            avg_daily_claim_count_30day=Decimal("10.00"),
        )
        assert alerts == []
