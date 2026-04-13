"""Unit tests for event publishers, consumers, and scheduled jobs."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from src.events.consumers import (
    handle_ach_return_received,
    handle_claim_adjudicated,
    handle_member_enrolled,
    handle_payment_vendor_confirmed,
)
from src.events.publishers import (
    publish_ar_payment_received,
    publish_budget_alert_fired,
    publish_claim_classified,
    publish_claim_ingested,
    publish_invoice_generated,
    publish_payment_batch_generated,
    publish_payment_batch_voided,
)
from src.jobs.scheduled import (
    run_ap_carryover_check,
    run_ar_aging_update,
    run_budget_monitoring,
    run_budget_snapshot,
    run_invoice_auto_generation,
)

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLIENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROGRAM = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


class TestEventPublishers:
    def test_publish_claim_ingested(self) -> None:
        bus = MagicMock()
        publish_claim_ingested(
            bus,
            tenant_id=TENANT,
            claim_id=uuid.uuid4(),
            auth_number="AUTH001",
            claim_type="new",
            net_amount=Decimal("100.00"),
            client_id=CLIENT,
            program_id=PROGRAM,
        )
        bus.publish.assert_called_once()
        topic, payload = bus.publish.call_args[0]
        assert topic == "claim.ingested"
        assert payload["auth_number"] == "AUTH001"
        assert payload["tenant_id"] == str(TENANT)
        assert "occurred_at" in payload

    def test_publish_claim_classified(self) -> None:
        bus = MagicMock()
        publish_claim_classified(
            bus,
            tenant_id=TENANT,
            claim_id=uuid.uuid4(),
            payment_route="echo",
            is_excluded=False,
            is_statement=False,
        )
        bus.publish.assert_called_once()
        topic, payload = bus.publish.call_args[0]
        assert topic == "claim.classified"
        assert payload["payment_route"] == "echo"

    def test_publish_claim_classified_none_route(self) -> None:
        bus = MagicMock()
        publish_claim_classified(
            bus,
            tenant_id=TENANT,
            claim_id=uuid.uuid4(),
            payment_route=None,
            is_excluded=False,
            is_statement=False,
        )
        _, payload = bus.publish.call_args[0]
        assert payload["payment_route"] is None

    def test_publish_payment_batch_generated(self) -> None:
        bus = MagicMock()
        publish_payment_batch_generated(
            bus,
            tenant_id=TENANT,
            batch_id=uuid.uuid4(),
            batch_number="BATCH001",
            payment_route="echo",
            total_amount=Decimal("1000.00"),
            payment_count=5,
        )
        topic, payload = bus.publish.call_args[0]
        assert topic == "payment_batch.generated"
        assert payload["payment_count"] == 5
        assert payload["total_amount"] == "1000.00"

    def test_publish_payment_batch_voided_with_reason(self) -> None:
        bus = MagicMock()
        publish_payment_batch_voided(
            bus,
            tenant_id=TENANT,
            batch_id=uuid.uuid4(),
            batch_number="BATCH001",
            reason="Error in batch",
        )
        topic, payload = bus.publish.call_args[0]
        assert topic == "payment_batch.voided"
        assert payload["reason"] == "Error in batch"

    def test_publish_payment_batch_voided_no_reason(self) -> None:
        bus = MagicMock()
        publish_payment_batch_voided(
            bus,
            tenant_id=TENANT,
            batch_id=uuid.uuid4(),
            batch_number="BATCH001",
        )
        _, payload = bus.publish.call_args[0]
        assert payload["reason"] is None

    def test_publish_invoice_generated(self) -> None:
        bus = MagicMock()
        publish_invoice_generated(
            bus,
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            invoice_number="INV-001",
            client_id=CLIENT,
            total=Decimal("5000.00"),
            due_date="2026-02-28",
        )
        topic, payload = bus.publish.call_args[0]
        assert topic == "invoice.generated"
        assert payload["invoice_number"] == "INV-001"
        assert payload["total"] == "5000.00"

    def test_publish_ar_payment_received(self) -> None:
        bus = MagicMock()
        publish_ar_payment_received(
            bus,
            tenant_id=TENANT,
            ar_id=uuid.uuid4(),
            client_id=CLIENT,
            amount=Decimal("100.00"),
            payment_date="2026-02-15",
            outstanding_after=Decimal("0.00"),
        )
        topic, payload = bus.publish.call_args[0]
        assert topic == "ar.payment_received"
        assert payload["outstanding_after"] == "0.00"

    def test_publish_budget_alert_fired(self) -> None:
        bus = MagicMock()
        publish_budget_alert_fired(
            bus,
            tenant_id=TENANT,
            program_budget_id=uuid.uuid4(),
            program_id=PROGRAM,
            alert_type="over_budget",
            severity="critical",
            message="Budget exceeded",
        )
        topic, payload = bus.publish.call_args[0]
        assert topic == "budget.alert_fired"
        assert payload["alert_type"] == "over_budget"
        assert payload["severity"] == "critical"


class TestEventConsumers:
    def test_handle_member_enrolled_is_no_op(self) -> None:
        handle_member_enrolled({}, db=MagicMock(), bus=MagicMock())

    def test_handle_claim_adjudicated_is_no_op(self) -> None:
        handle_claim_adjudicated({}, db=MagicMock(), bus=MagicMock())

    def test_handle_payment_vendor_confirmed_is_no_op(self) -> None:
        handle_payment_vendor_confirmed({}, db=MagicMock(), bus=MagicMock())

    def test_handle_ach_return_received_is_no_op(self) -> None:
        handle_ach_return_received({}, db=MagicMock(), bus=MagicMock())


class TestScheduledJobs:
    def test_budget_monitoring_returns_summary(self) -> None:
        result = run_budget_monitoring(db=MagicMock(), bus=MagicMock())
        assert "budgets_evaluated" in result
        assert "alerts_fired" in result
        assert result["budgets_evaluated"] == 0
        assert result["alerts_fired"] == 0

    def test_ar_aging_update_returns_summary(self) -> None:
        result = run_ar_aging_update(db=MagicMock())
        assert "records_updated" in result
        assert result["records_updated"] == 0

    def test_ap_carryover_check_returns_summary(self) -> None:
        result = run_ap_carryover_check(db=MagicMock(), bus=MagicMock())
        assert "carryover_records_created" in result
        assert result["carryover_records_created"] == 0

    def test_invoice_auto_generation_returns_summary(self) -> None:
        result = run_invoice_auto_generation(db=MagicMock(), bus=MagicMock())
        assert "invoices_generated" in result
        assert result["invoices_generated"] == 0

    def test_invoice_auto_generation_with_explicit_date(self) -> None:
        result = run_invoice_auto_generation(
            db=MagicMock(), bus=MagicMock(), run_date=date(2026, 1, 31)
        )
        assert result["invoices_generated"] == 0

    def test_budget_snapshot_returns_summary(self) -> None:
        result = run_budget_snapshot(db=MagicMock())
        assert "snapshots_created" in result
        assert result["snapshots_created"] == 0


class TestAPIDependencies:
    def test_valid_tenant_uuid_header(self) -> None:
        from src.api.dependencies import get_tenant_id

        result = get_tenant_id(x_tenant_id=str(TENANT))
        assert result == TENANT

    def test_invalid_tenant_uuid_raises_http_400(self) -> None:
        from fastapi import HTTPException
        from src.api.dependencies import get_tenant_id

        with pytest.raises(HTTPException) as exc_info:
            get_tenant_id(x_tenant_id="not-a-uuid")
        assert exc_info.value.status_code == 400
