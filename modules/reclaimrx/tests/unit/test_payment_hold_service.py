"""Tests for payment hold service — TDD first."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session
from src._shim.events import published_events
from src.services.payment_hold_service import PaymentHoldService

from tests.conftest import OTHER_TENANT_ID, TEST_TENANT_ID, TEST_USER_ID


class TestPaymentHoldPlacement:
    def test_place_hold_creates_record(self, db: Session) -> None:
        svc = PaymentHoldService(db)
        hold = svc.place_hold(
            tenant_id=TEST_TENANT_ID,
            entity_type="pharmacy",
            entity_id="1234567890",
            entity_name="Test Pharmacy",
            placed_by=TEST_USER_ID,
            hold_scope="all",
        )
        db.flush()
        assert hold.is_active is True
        assert hold.entity_type == "pharmacy"
        assert hold.entity_id == "1234567890"

    def test_place_hold_publishes_event(self, db: Session) -> None:
        svc = PaymentHoldService(db)
        svc.place_hold(
            tenant_id=TEST_TENANT_ID,
            entity_type="pharmacy",
            entity_id="1234567890",
            entity_name="Test Pharmacy",
            placed_by=TEST_USER_ID,
            hold_scope="all",
        )
        db.flush()
        events = published_events()
        assert any(e.topic == "fwa.payment_hold_placed" for e in events)

    def test_release_hold_deactivates_record(self, db: Session) -> None:
        svc = PaymentHoldService(db)
        hold = svc.place_hold(
            tenant_id=TEST_TENANT_ID,
            entity_type="pharmacy",
            entity_id="9999999999",
            entity_name="Release Test Pharmacy",
            placed_by=TEST_USER_ID,
            hold_scope="all",
        )
        db.flush()
        released = svc.release_hold(
            tenant_id=TEST_TENANT_ID,
            hold_id=hold.id,
            released_by=TEST_USER_ID,
            reason="Investigation resolved - no fraud found",
        )
        db.flush()
        assert released.is_active is False
        assert released.released_by == str(TEST_USER_ID)
        assert released.release_reason == "Investigation resolved - no fraud found"

    def test_release_hold_publishes_event(self, db: Session) -> None:
        svc = PaymentHoldService(db)
        hold = svc.place_hold(
            tenant_id=TEST_TENANT_ID,
            entity_type="pharmacy",
            entity_id="8888888888",
            entity_name="Event Test Pharmacy",
            placed_by=TEST_USER_ID,
            hold_scope="all",
        )
        db.flush()
        svc.release_hold(
            tenant_id=TEST_TENANT_ID,
            hold_id=hold.id,
            released_by=TEST_USER_ID,
            reason="Cleared",
        )
        db.flush()
        events = published_events()
        assert any(e.topic == "fwa.payment_hold_released" for e in events)

    def test_list_active_holds_tenant_scoped(self, db: Session) -> None:
        svc = PaymentHoldService(db)
        svc.place_hold(
            tenant_id=TEST_TENANT_ID,
            entity_type="pharmacy",
            entity_id="7777777777",
            entity_name="Scoped Pharmacy",
            placed_by=TEST_USER_ID,
            hold_scope="all",
        )
        db.flush()
        holds = svc.list_active_holds(tenant_id=OTHER_TENANT_ID)
        assert all(h.tenant_id == str(OTHER_TENANT_ID) for h in holds)

    def test_cannot_release_other_tenant_hold(self, db: Session) -> None:
        svc = PaymentHoldService(db)
        hold = svc.place_hold(
            tenant_id=TEST_TENANT_ID,
            entity_type="pharmacy",
            entity_id="6666666666",
            entity_name="Cross Tenant Pharmacy",
            placed_by=TEST_USER_ID,
            hold_scope="all",
        )
        db.flush()
        with pytest.raises(ValueError, match="not found"):
            svc.release_hold(
                tenant_id=OTHER_TENANT_ID,
                hold_id=hold.id,
                released_by=TEST_USER_ID,
                reason="Bad actor",
            )


class TestPaymentHoldEventPayload:
    def test_hold_placed_event_contains_required_fields(self, db: Session) -> None:
        svc = PaymentHoldService(db)
        svc.place_hold(
            tenant_id=TEST_TENANT_ID,
            entity_type="pharmacy",
            entity_id="5555555555",
            entity_name="Event Payload Pharmacy",
            placed_by=TEST_USER_ID,
            hold_scope="all",
        )
        db.flush()
        events = [e for e in published_events() if e.topic == "fwa.payment_hold_placed"]
        assert len(events) >= 1
        payload = events[0].payload
        assert "tenant_id" in payload
        assert "entity_type" in payload
        assert "entity_id" in payload
        assert "hold_id" in payload

    def test_hold_released_event_contains_required_fields(self, db: Session) -> None:
        svc = PaymentHoldService(db)
        hold = svc.place_hold(
            tenant_id=TEST_TENANT_ID,
            entity_type="pharmacy",
            entity_id="4444444444",
            entity_name="Release Event Pharmacy",
            placed_by=TEST_USER_ID,
            hold_scope="all",
        )
        db.flush()
        svc.release_hold(
            tenant_id=TEST_TENANT_ID,
            hold_id=hold.id,
            released_by=TEST_USER_ID,
            reason="Test done",
        )
        db.flush()
        events = [e for e in published_events() if e.topic == "fwa.payment_hold_released"]
        assert len(events) >= 1
        payload = events[0].payload
        assert "hold_id" in payload
        assert "tenant_id" in payload
        assert "release_reason" in payload
