"""Unit tests for event consumers and publishers."""
from __future__ import annotations

from decimal import Decimal


from src._shim.events import published_events
from src.events import consumers
from src.events.publishers import (
    publish_failed,
    publish_file_generated,
    publish_return_suspicious,
    publish_returned,
    publish_settled,
    publish_submitted,
    publish_vendor_status_changed,
)
from src.utils.constants import (
    EVENT_FAILED,
    EVENT_FILE_GENERATED,
    EVENT_FWA_HOLD_PLACED,
    EVENT_FWA_HOLD_RELEASED,
    EVENT_PAYMENT_BATCH_SUBMITTED,
    EVENT_RETURN_SUSPICIOUS,
    EVENT_RETURNED,
    EVENT_SETTLED,
    EVENT_SUBMITTED,
    EVENT_VENDOR_STATUS_CHANGED,
)


class TestPublishers:
    def test_publish_file_generated(self):
        publish_file_generated(
            tenant_id="T1",
            submission_id="S1",
            billing_payment_batch_id="B1",
            payment_count=5,
            total_amount=Decimal("500.00"),
            file_format="nacha",
        )
        events = published_events()
        assert any(e.topic == EVENT_FILE_GENERATED for e in events)
        ev = next(e for e in events if e.topic == EVENT_FILE_GENERATED)
        assert ev.payload["payment_count"] == 5
        assert ev.payload["total_amount"] == "500.00"

    def test_publish_submitted(self):
        publish_submitted(
            tenant_id="T1",
            submission_id="S1",
            billing_payment_batch_id="B1",
            vendor_reference="REF-001",
            total_amount=Decimal("100.00"),
            payment_count=1,
        )
        topics = [e.topic for e in published_events()]
        assert EVENT_SUBMITTED in topics

    def test_publish_settled(self):
        publish_settled(
            tenant_id="T1",
            billing_payment_id="BP-001",
            submission_id="S1",
            settlement_date="2026-04-15",
            settlement_reference="ACH-REF",
            amount=Decimal("100.00"),
            payment_method_used="ach",
        )
        topics = [e.topic for e in published_events()]
        assert EVENT_SETTLED in topics

    def test_publish_returned(self):
        publish_returned(
            tenant_id="T1",
            billing_payment_id="BP-001",
            submission_id="S1",
            return_code="R01",
            return_reason="NSF",
            amount=Decimal("100.00"),
            default_action="auto_retry",
            is_retryable=True,
        )
        topics = [e.topic for e in published_events()]
        assert EVENT_RETURNED in topics

    def test_publish_return_suspicious(self):
        publish_return_suspicious(
            tenant_id="T1",
            billing_payment_id="BP-001",
            submission_id="S1",
            return_code="R10",
            amount=Decimal("100.00"),
        )
        topics = [e.topic for e in published_events()]
        assert EVENT_RETURN_SUSPICIOUS in topics

    def test_publish_failed(self):
        publish_failed(
            tenant_id="T1",
            submission_id="S1",
            billing_payment_batch_id="B1",
            error="Connection timeout",
        )
        topics = [e.topic for e in published_events()]
        assert EVENT_FAILED in topics

    def test_publish_vendor_status_changed(self):
        publish_vendor_status_changed(
            tenant_id="T1",
            vendor_adapter_id="V1",
            old_status="healthy",
            new_status="degraded",
        )
        topics = [e.topic for e in published_events()]
        assert EVENT_VENDOR_STATUS_CHANGED in topics


class TestConsumers:
    def test_dispatch_payment_batch_submitted(self):
        consumers.dispatch(
            EVENT_PAYMENT_BATCH_SUBMITTED,
            {"batch_id": "B1", "tenant_id": "T1"},
        )

    def test_dispatch_fwa_hold_placed(self):
        consumers.dispatch(
            EVENT_FWA_HOLD_PLACED,
            {"entity_id": "E1", "tenant_id": "T1", "reason": "FWA"},
        )

    def test_dispatch_fwa_hold_released(self):
        consumers.dispatch(
            EVENT_FWA_HOLD_RELEASED,
            {"entity_id": "E1", "tenant_id": "T1"},
        )

    def test_dispatch_unknown_topic_does_not_raise(self):
        consumers.dispatch("unknown.topic", {"data": "value"})

    def test_register_handler_overrides(self):
        called = []
        consumers.register_handler("test.topic", lambda p: called.append(p))
        consumers.dispatch("test.topic", {"key": "value"})
        assert len(called) == 1
        assert called[0] == {"key": "value"}
