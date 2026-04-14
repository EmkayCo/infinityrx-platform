"""Contract tests for event schemas.

Verify that published event payloads match the documented schema in docs/api-contracts/.
Verify consumer can parse publisher's payload.
"""
from __future__ import annotations

from decimal import Decimal


from src._shim.events import published_events
from src.events.publishers import (
    publish_file_generated,
    publish_return_suspicious,
    publish_returned,
    publish_submitted,
    publish_vendor_status_changed,
)
from src.utils.constants import (
    EVENT_FILE_GENERATED,
    EVENT_RETURN_SUSPICIOUS,
    EVENT_RETURNED,
    EVENT_SUBMITTED,
    EVENT_VENDOR_STATUS_CHANGED,
)


class TestPaymentBatchSubmittedContract:
    """Contract: payment_batch.submitted from Billing."""

    def test_consumer_handles_minimal_payload(self):
        from src.events.consumers import handle_payment_batch_submitted
        payload = {
            "batch_id": "BATCH-001",
            "tenant_id": "T1",
            "vendor_config_id": "VC-001",
            "payment_count": 10,
            "total_amount": "1500.00",
        }
        # Must not raise
        handle_payment_batch_submitted(payload)

    def test_consumer_handles_partial_payload(self):
        from src.events.consumers import handle_payment_batch_submitted
        handle_payment_batch_submitted({"tenant_id": "T1"})


class TestFwaHoldContract:
    """Contract: fwa.payment_hold_placed / fwa.payment_hold_released from ReclaimRx."""

    def test_hold_placed_consumer(self):
        from src.events.consumers import handle_fwa_hold_placed
        payload = {
            "entity_id": "ENT-001",
            "tenant_id": "T1",
            "reason": "Suspected fraud — Rule FWA-012",
            "investigation_id": "INV-001",
        }
        handle_fwa_hold_placed(payload)

    def test_hold_released_consumer(self):
        from src.events.consumers import handle_fwa_hold_released
        payload = {
            "entity_id": "ENT-001",
            "tenant_id": "T1",
            "investigation_id": "INV-001",
        }
        handle_fwa_hold_released(payload)


class TestPaymentFileGeneratedContract:
    def test_published_schema(self):
        publish_file_generated(
            tenant_id="T1",
            submission_id="S1",
            billing_payment_batch_id="B1",
            payment_count=5,
            total_amount=Decimal("500.00"),
            file_format="nacha",
        )
        events = [e for e in published_events() if e.topic == EVENT_FILE_GENERATED]
        assert len(events) == 1
        payload = events[0].payload
        # Required fields per contract
        assert "tenant_id" in payload
        assert "submission_id" in payload
        assert "billing_payment_batch_id" in payload
        assert "payment_count" in payload
        assert "total_amount" in payload
        # Amount must be string (no float in events)
        assert isinstance(payload["total_amount"], str)
        assert "." in payload["total_amount"]


class TestPaymentSubmittedContract:
    def test_published_schema(self):
        publish_submitted(
            tenant_id="T1",
            submission_id="S1",
            billing_payment_batch_id="B1",
            vendor_reference="REF-001",
            total_amount=Decimal("100.00"),
            payment_count=1,
        )
        events = [e for e in published_events() if e.topic == EVENT_SUBMITTED]
        assert len(events) == 1
        payload = events[0].payload
        assert "tenant_id" in payload
        assert "submission_id" in payload
        assert "billing_payment_batch_id" in payload
        assert isinstance(payload["total_amount"], str)


class TestPaymentReturnedContract:
    def test_published_schema(self):
        publish_returned(
            tenant_id="T1",
            billing_payment_id="BP-001",
            submission_id="S1",
            return_code="R01",
            return_reason="Insufficient Funds",
            amount=Decimal("100.00"),
            default_action="auto_retry",
            is_retryable=True,
        )
        events = [e for e in published_events() if e.topic == EVENT_RETURNED]
        assert len(events) == 1
        payload = events[0].payload
        assert "return_code" in payload
        assert "default_action" in payload
        assert "is_retryable" in payload
        assert isinstance(payload["amount"], str)

    def test_return_amount_is_string_not_float(self):
        publish_returned(
            tenant_id="T1",
            billing_payment_id="BP-001",
            submission_id="S1",
            return_code="R02",
            return_reason=None,
            amount=Decimal("99.99"),
            default_action="carryover",
            is_retryable=False,
        )
        events = [e for e in published_events() if e.topic == EVENT_RETURNED]
        for ev in events:
            assert isinstance(ev.payload["amount"], str)
            # Must not be float representation
            assert "e" not in ev.payload["amount"].lower()


class TestSuspiciousReturnContract:
    def test_published_schema(self):
        publish_return_suspicious(
            tenant_id="T1",
            billing_payment_id="BP-001",
            submission_id="S1",
            return_code="R10",
            amount=Decimal("100.00"),
        )
        events = [e for e in published_events() if e.topic == EVENT_RETURN_SUSPICIOUS]
        assert len(events) == 1
        payload = events[0].payload
        assert payload["return_code"] == "R10"
        assert isinstance(payload["amount"], str)


class TestVendorStatusChangedContract:
    def test_published_schema(self):
        publish_vendor_status_changed(
            tenant_id="T1",
            vendor_adapter_id="V1",
            old_status="healthy",
            new_status="down",
        )
        events = [e for e in published_events() if e.topic == EVENT_VENDOR_STATUS_CHANGED]
        assert len(events) == 1
        payload = events[0].payload
        assert "old_status" in payload
        assert "new_status" in payload
        assert "vendor_adapter_id" in payload
