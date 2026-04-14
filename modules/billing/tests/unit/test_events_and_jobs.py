"""Unit tests for event publishers, consumers, and scheduled jobs."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from shared.events.in_memory_bus import InMemoryEventBus
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
    publish_payment_batch_submitted,
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
CORR = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


class TestEventPublishers:
    @pytest.mark.asyncio
    async def test_publish_claim_ingested_emits_correct_envelope(self) -> None:
        bus = InMemoryEventBus()
        await bus.start()
        await publish_claim_ingested(
            bus,
            tenant_id=TENANT,
            claim_id=uuid.UUID("aaaa0001-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            correlation_id=CORR,
            auth_number="AUTH001",
            claim_type="new",
            net_amount=Decimal("100.00"),
            client_id=CLIENT,
            program_id=PROGRAM,
        )
        assert len(bus.published) == 1
        envelope = bus.published[0]
        assert envelope.event_type == "claim.ingested"
        assert envelope.tenant_id == TENANT
        assert envelope.schema_version == "1.0"
        assert envelope.payload["auth_number"] == "AUTH001"
        assert envelope.payload["net_amount"] == "100.00"
        assert "occurred_at" in envelope.payload

    @pytest.mark.asyncio
    async def test_publish_claim_classified_emits_correct_envelope(self) -> None:
        bus = InMemoryEventBus()
        await bus.start()
        claim_id = uuid.uuid4()
        await publish_claim_classified(
            bus,
            tenant_id=TENANT,
            claim_id=claim_id,
            correlation_id=CORR,
            payment_route="echo",
            is_excluded=False,
            is_statement=False,
        )
        envelope = bus.published[0]
        assert envelope.event_type == "claim.classified"
        assert envelope.payload["payment_route"] == "echo"
        assert envelope.ordering_key == str(claim_id)

    @pytest.mark.asyncio
    async def test_publish_claim_classified_none_route(self) -> None:
        bus = InMemoryEventBus()
        await bus.start()
        await publish_claim_classified(
            bus,
            tenant_id=TENANT,
            claim_id=uuid.uuid4(),
            correlation_id=CORR,
            payment_route=None,
            is_excluded=False,
            is_statement=False,
        )
        envelope = bus.published[0]
        assert envelope.payload["payment_route"] is None

    @pytest.mark.asyncio
    async def test_publish_payment_batch_submitted_uses_correct_topic(self) -> None:
        """Topic is payment_batch.submitted (not .generated) — CR-01 reconciliation."""
        bus = InMemoryEventBus()
        await bus.start()
        batch_id = uuid.uuid4()
        await publish_payment_batch_submitted(
            bus,
            tenant_id=TENANT,
            batch_id=batch_id,
            correlation_id=CORR,
            batch_number="BATCH001",
            payment_route="echo",
            total_amount=Decimal("1000.00"),
            payment_count=5,
        )
        envelope = bus.published[0]
        assert envelope.event_type == "payment_batch.submitted"
        assert envelope.payload["payment_count"] == 5
        assert envelope.payload["total_amount"] == "1000.00"
        assert envelope.ordering_key == str(batch_id)
        assert envelope.idempotency_key == f"payment_batch.submitted:{batch_id}"

    @pytest.mark.asyncio
    async def test_publish_payment_batch_voided_with_reason(self) -> None:
        bus = InMemoryEventBus()
        await bus.start()
        await publish_payment_batch_voided(
            bus,
            tenant_id=TENANT,
            batch_id=uuid.uuid4(),
            correlation_id=CORR,
            batch_number="BATCH001",
            reason="Error in batch",
        )
        envelope = bus.published[0]
        assert envelope.event_type == "payment_batch.voided"
        assert envelope.payload["reason"] == "Error in batch"

    @pytest.mark.asyncio
    async def test_publish_payment_batch_voided_no_reason(self) -> None:
        bus = InMemoryEventBus()
        await bus.start()
        await publish_payment_batch_voided(
            bus,
            tenant_id=TENANT,
            batch_id=uuid.uuid4(),
            correlation_id=CORR,
            batch_number="BATCH001",
        )
        envelope = bus.published[0]
        assert envelope.payload["reason"] is None

    @pytest.mark.asyncio
    async def test_publish_invoice_generated_emits_correct_envelope(self) -> None:
        bus = InMemoryEventBus()
        await bus.start()
        await publish_invoice_generated(
            bus,
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            correlation_id=CORR,
            invoice_number="INV-001",
            client_id=CLIENT,
            total=Decimal("5000.00"),
            due_date="2026-02-28",
        )
        envelope = bus.published[0]
        assert envelope.event_type == "invoice.generated"
        assert envelope.payload["invoice_number"] == "INV-001"
        assert envelope.payload["total"] == "5000.00"

    @pytest.mark.asyncio
    async def test_publish_ar_payment_received_emits_correct_envelope(self) -> None:
        bus = InMemoryEventBus()
        await bus.start()
        await publish_ar_payment_received(
            bus,
            tenant_id=TENANT,
            ar_id=uuid.uuid4(),
            correlation_id=CORR,
            client_id=CLIENT,
            amount=Decimal("100.00"),
            payment_date="2026-02-15",
            outstanding_after=Decimal("0.00"),
        )
        envelope = bus.published[0]
        assert envelope.event_type == "ar.payment_received"
        assert envelope.payload["outstanding_after"] == "0.00"

    @pytest.mark.asyncio
    async def test_publish_budget_alert_fired_emits_correct_envelope(self) -> None:
        bus = InMemoryEventBus()
        await bus.start()
        await publish_budget_alert_fired(
            bus,
            tenant_id=TENANT,
            program_budget_id=uuid.uuid4(),
            correlation_id=CORR,
            program_id=PROGRAM,
            alert_type="over_budget",
            severity="critical",
            message="Budget exceeded",
        )
        envelope = bus.published[0]
        assert envelope.event_type == "budget.alert_fired"
        assert envelope.payload["alert_type"] == "over_budget"
        assert envelope.payload["severity"] == "critical"


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
