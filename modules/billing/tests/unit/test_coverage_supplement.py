"""Supplemental tests to reach ≥99% branch coverage on all billing services."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from src.services.ap import APService
from src.services.ar import ARService, FeeConfigData
from src.services.budget import BudgetService
from src.services.journal import JournalService
from src.utils.constants import (
    ALERT_SPEND_RATE_INCREASE,
    BATCH_STATUS_GENERATED,
    CATEGORY_CLAIMS_PAYABLE,
    FEE_PER_MEMBER_PER_MONTH,
    FEE_PER_TRANSACTION,
    JOURNAL_AP_CREATED,
    ROUTE_ECHO,
)
from src.utils.money import money

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLIENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROGRAM = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ENTITY_A = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


class TestARMissingCoverage:
    def test_per_member_per_month_fee(self) -> None:
        svc = ARService(db=MagicMock(), events=MagicMock())
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="PMPM",
            calculation_type=FEE_PER_MEMBER_PER_MONTH,
            amount=Decimal("5.00"),
            percentage=None,
            tiers=None,
        )
        claims = [
            {"net_amount": Decimal("100.00"), "ingredient_cost": Decimal("0"), "member_id": "M001"},
            {"net_amount": Decimal("100.00"), "ingredient_cost": Decimal("0"), "member_id": "M002"},
            {
                "net_amount": Decimal("100.00"),
                "ingredient_cost": Decimal("0"),
                "member_id": "M001",
            },  # dup
        ]
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == money("10.00")  # 2 unique members × $5.00

    def test_per_transaction_fee(self) -> None:
        svc = ARService(db=MagicMock(), events=MagicMock())
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="TRANS",
            calculation_type=FEE_PER_TRANSACTION,
            amount=Decimal("0.50"),
            percentage=None,
            tiers=None,
        )
        claims = [
            {"net_amount": Decimal("100.00"), "ingredient_cost": Decimal("0")} for _ in range(4)
        ]
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == money("2.00")

    def test_tiered_volume_fee_open_ended_tier(self) -> None:
        svc = ARService(db=MagicMock(), events=MagicMock())
        tiers = [
            {"min_claims": 0, "max_claims": 100, "fee_per_claim": "1.00"},
            {"min_claims": 101, "max_claims": None, "fee_per_claim": "0.60"},
        ]
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="TIER",
            calculation_type="tiered_volume",
            amount=None,
            percentage=None,
            tiers=tiers,
        )
        claims = [
            {"net_amount": Decimal("100.00"), "ingredient_cost": Decimal("0")} for _ in range(200)
        ]
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == money("120.00")  # 200 × $0.60

    def test_tiered_no_matching_tier_returns_zero(self) -> None:
        svc = ARService(db=MagicMock(), events=MagicMock())
        tiers: list = []
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="TIER",
            calculation_type="tiered_volume",
            amount=None,
            percentage=None,
            tiers=tiers,
        )
        claims = [{"net_amount": Decimal("100.00"), "ingredient_cost": Decimal("0")}]
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == Decimal("0.00")

    def test_ar_payment_publishes_event(self) -> None:
        events = MagicMock()
        svc = ARService(db=MagicMock(), events=events)
        ar = svc.create_ar_record(
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            client_id=CLIENT,
            amount_due=Decimal("100.00"),
            due_date=date(2026, 2, 28),
        )
        svc.record_payment(ar, amount=Decimal("50.00"), payment_date=date(2026, 2, 15))
        topics = [c[0][0] for c in events.publish.call_args_list]
        assert "ar.payment_received" in topics


class TestBudgetMissingCoverage:
    def test_zero_budget_amount_utilization(self) -> None:
        svc = BudgetService(db=MagicMock(), events=MagicMock())
        budget = {
            "id": uuid.uuid4(),
            "tenant_id": TENANT,
            "client_id": CLIENT,
            "program_id": PROGRAM,
            "budget_type": "unlimited",
            "budget_amount": Decimal("0.00"),
            "spent_to_date": Decimal("0.00"),
            "burn_rate_30day_avg": Decimal("0.00"),
            "spend_increase_alert_pct": Decimal("25"),
            "budget_remaining_alert_pct": Decimal("20"),
            "depletion_alert_days": 30,
        }
        result = svc.calculate_budget_stats(budget)
        assert result["utilization_percentage"] == Decimal("0.00")

    def test_no_spend_rate_alert_when_avg_is_zero(self) -> None:
        svc = BudgetService(db=MagicMock(), events=MagicMock())
        budget = {
            "budget_amount": Decimal("100000.00"),
            "spent_to_date": Decimal("10000.00"),
            "burn_rate_30day_avg": Decimal("0.00"),
            "spend_increase_alert_pct": Decimal("25"),
            "budget_remaining_alert_pct": Decimal("20"),
            "depletion_alert_days": 30,
        }
        alerts = svc.evaluate_alerts(
            budget=budget,
            current_burn_7day=Decimal("0.00"),
            projected_depletion_date=None,
            daily_claim_count=10,
            avg_daily_claim_count_30day=Decimal("10.00"),
        )
        types = {a["alert_type"] for a in alerts}
        assert ALERT_SPEND_RATE_INCREASE not in types

    def test_zero_budget_sets_remaining_pct_zero_no_low_alert(self) -> None:
        svc = BudgetService(db=MagicMock(), events=MagicMock())
        budget = {
            "budget_amount": Decimal("0.00"),
            "spent_to_date": Decimal("0.00"),
            "burn_rate_30day_avg": Decimal("100.00"),
            "spend_increase_alert_pct": Decimal("25"),
            "budget_remaining_alert_pct": Decimal("20"),
            "depletion_alert_days": 30,
        }
        alerts = svc.evaluate_alerts(
            budget=budget,
            current_burn_7day=Decimal("100.00"),
            projected_depletion_date=None,
            daily_claim_count=10,
            avg_daily_claim_count_30day=Decimal("10.00"),
        )
        # No over_budget when spent=0 and budget=0
        types = {a["alert_type"] for a in alerts}
        # Zero budget → remaining_pct = 0, below critical_floor, but spent NOT > budget_amount
        assert "over_budget" not in types


class TestJournalMissingCoverage:
    def test_query_with_client_filter(self) -> None:
        svc = JournalService(db=MagicMock(), events=MagicMock())
        entry_a = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("100.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Client A entry",
            entry_date=date(2026, 1, 15),
            client_id=CLIENT,
        )
        other_client = uuid.uuid4()
        entry_b = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("200.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Client B entry",
            entry_date=date(2026, 1, 15),
            client_id=other_client,
        )
        results = svc.query_entries([entry_a, entry_b], tenant_id=TENANT, client_id=CLIENT)
        assert len(results) == 1
        assert results[0].client_id == CLIENT

    def test_query_with_program_filter(self) -> None:
        svc = JournalService(db=MagicMock(), events=MagicMock())
        program = uuid.uuid4()
        entry = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("100.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Program entry",
            entry_date=date(2026, 1, 15),
            program_id=program,
        )
        results = svc.query_entries([entry], tenant_id=TENANT, program_id=program)
        assert len(results) == 1

    def test_query_with_category_filter(self) -> None:
        svc = JournalService(db=MagicMock(), events=MagicMock())
        entry = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("100.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Claims payable",
            entry_date=date(2026, 1, 15),
        )
        results = svc.query_entries([entry], tenant_id=TENANT, category=CATEGORY_CLAIMS_PAYABLE)
        assert len(results) == 1
        results_other = svc.query_entries([entry], tenant_id=TENANT, category="other_category")
        assert len(results_other) == 0

    def test_query_with_entry_type_filter(self) -> None:
        svc = JournalService(db=MagicMock(), events=MagicMock())
        entry = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("100.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="AP created",
            entry_date=date(2026, 1, 15),
        )
        results = svc.query_entries([entry], tenant_id=TENANT, entry_type=JOURNAL_AP_CREATED)
        assert len(results) == 1
        results_other = svc.query_entries([entry], tenant_id=TENANT, entry_type="other_type")
        assert len(results_other) == 0

    def test_query_unexported_only(self) -> None:
        svc = JournalService(db=MagicMock(), events=MagicMock())
        entry1 = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("100.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Not exported",
            entry_date=date(2026, 1, 15),
        )
        entry2 = svc.create_entry(
            tenant_id=TENANT,
            entry_type=JOURNAL_AP_CREATED,
            amount=Decimal("200.00"),
            category=CATEGORY_CLAIMS_PAYABLE,
            description="Exported",
            entry_date=date(2026, 1, 15),
        )
        svc.mark_exported([entry2], export_reference="QB-001")
        results = svc.query_entries([entry1, entry2], tenant_id=TENANT, unexported_only=True)
        assert len(results) == 1
        assert results[0].description == "Not exported"


class TestARCustomFeeAndEdgeCases:
    def test_custom_fee_raises_not_implemented(self) -> None:
        svc = ARService(db=MagicMock(), events=MagicMock())
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="CUSTOM",
            calculation_type="custom",
            amount=Decimal("1.00"),
            percentage=None,
            tiers=None,
        )
        with pytest.raises(ValueError, match="Custom fee"):
            svc.calculate_fee(
                fee_config, [{"net_amount": Decimal("100.00"), "ingredient_cost": Decimal("0")}]
            )

    def test_tiered_open_tier_not_matching(self) -> None:
        """Open-ended tier (max_claims=None) where count < min_claims — no match."""
        svc = ARService(db=MagicMock(), events=MagicMock())
        tiers = [
            {"min_claims": 500, "max_claims": None, "fee_per_claim": "0.50"},
        ]
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="TIER",
            calculation_type="tiered_volume",
            amount=None,
            percentage=None,
            tiers=tiers,
        )
        # Only 10 claims, tier requires ≥500
        claims = [
            {"net_amount": Decimal("100.00"), "ingredient_cost": Decimal("0")} for _ in range(10)
        ]
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == Decimal("0.00")


class TestBudgetAlertEdgeCases:
    def test_spend_rate_increase_alert_fires(self) -> None:
        svc = BudgetService(db=MagicMock(), events=MagicMock())
        budget = {
            "budget_amount": Decimal("100000.00"),
            "spent_to_date": Decimal("10000.00"),
            "burn_rate_30day_avg": Decimal("100.00"),  # 30-day avg
            "spend_increase_alert_pct": Decimal("25"),
            "budget_remaining_alert_pct": Decimal("20"),
            "depletion_alert_days": 30,
        }
        # 7-day burn at 200 = 100% increase over 30-day avg of 100 → exceeds 25% threshold
        alerts = svc.evaluate_alerts(
            budget=budget,
            current_burn_7day=Decimal("200.00"),
            projected_depletion_date=None,
            daily_claim_count=10,
            avg_daily_claim_count_30day=Decimal("10.00"),
        )
        types = {a["alert_type"] for a in alerts}
        assert ALERT_SPEND_RATE_INCREASE in types

    def test_no_unusual_activity_when_avg_claim_count_zero(self) -> None:
        svc = BudgetService(db=MagicMock(), events=MagicMock())
        budget = {
            "budget_amount": Decimal("100000.00"),
            "spent_to_date": Decimal("10000.00"),
            "burn_rate_30day_avg": Decimal("0.00"),
            "spend_increase_alert_pct": Decimal("25"),
            "budget_remaining_alert_pct": Decimal("20"),
            "depletion_alert_days": 30,
        }
        from src.utils.constants import ALERT_UNUSUAL_ACTIVITY

        alerts = svc.evaluate_alerts(
            budget=budget,
            current_burn_7day=Decimal("0.00"),
            projected_depletion_date=None,
            daily_claim_count=1000,
            avg_daily_claim_count_30day=Decimal("0.00"),  # zero — no unusual activity alert
        )
        types = {a["alert_type"] for a in alerts}
        assert ALERT_UNUSUAL_ACTIVITY not in types


class TestAPValidationBatchTotalMismatch:
    def test_batch_total_mismatch_generates_error(self) -> None:
        svc = APService(db=MagicMock(), events=MagicMock())
        # Manually construct a batch with wrong total
        batch = __import__("src.services.ap", fromlist=["PaymentBatchData"]).PaymentBatchData(
            id=uuid.uuid4(),
            tenant_id=TENANT,
            batch_number="BATCH999",
            payment_route=ROUTE_ECHO,
            total_amount=money("500.00"),  # wrong
            payment_count=1,
            ap_count=1,
            status=BATCH_STATUS_GENERATED,
        )
        payments = [
            __import__("src.services.ap", fromlist=["PaymentData"]).PaymentData(
                id=uuid.uuid4(),
                payment_batch_id=batch.id,
                tenant_id=TENANT,
                pay_to_entity_id=ENTITY_A,
                pay_to_entity_name="Test",
                amount=money("100.00"),  # different from batch total
                claim_count=1,
            )
        ]
        errors = svc.validate_batch(batch, payments)
        assert any("total" in e.lower() for e in errors)
