"""Tests for event publishers."""
from __future__ import annotations

import uuid
from decimal import Decimal

from src._shim.events import published_events, reset_events
from src.events.publishers import (
    publish_claim_blocked,
    publish_claim_flagged,
    publish_investigation_opened,
    publish_investigation_resolved,
    publish_pharmacy_risk_elevated,
    publish_recovery_collected,
    publish_recovery_demanded,
    publish_suspicious_community_detected,
    publish_tip_received,
    publish_watchlist_added,
)

from tests.conftest import TEST_TENANT_ID


class TestPublishers:
    def test_publish_claim_flagged(self) -> None:
        reset_events()
        publish_claim_flagged(
            tenant_id=TEST_TENANT_ID,
            flagged_claim_id="flag-001",
            claim_id="claim-001",
            rule_code="MFR-001",
            severity="high",
            risk_score=85,
            pharmacy_npi="1234567890",
            action_taken="flag",
        )
        events = published_events()
        assert any(e.topic == "fwa.claim_flagged" for e in events)

    def test_publish_claim_blocked(self) -> None:
        reset_events()
        publish_claim_blocked(
            tenant_id=TEST_TENANT_ID,
            claim_id="claim-002",
            auth_number="AUTH002",
            rule_code="ALL-001",
            reason="Duplicate claim detected",
        )
        events = published_events()
        assert any(e.topic == "fwa.claim_blocked" for e in events)

    def test_publish_investigation_opened(self) -> None:
        reset_events()
        publish_investigation_opened(
            tenant_id=TEST_TENANT_ID,
            investigation_id="inv-001",
            investigation_number="INV-2026-ABCD1234",
            subject_type="pharmacy",
            subject_entity_id="1234567890",
            investigation_type="desk_audit",
            priority="high",
        )
        events = published_events()
        assert any(e.topic == "fwa.investigation_opened" for e in events)

    def test_publish_investigation_resolved(self) -> None:
        reset_events()
        publish_investigation_resolved(
            tenant_id=TEST_TENANT_ID,
            investigation_id="inv-001",
            investigation_number="INV-2026-ABCD1234",
            resolution_type="recovered",
            actual_recovered=Decimal("5000.00"),
        )
        events = published_events()
        assert any(e.topic == "fwa.investigation_resolved" for e in events)

    def test_publish_recovery_demanded(self) -> None:
        reset_events()
        publish_recovery_demanded(
            tenant_id=TEST_TENANT_ID,
            investigation_id="inv-001",
            recovery_id="rec-001",
            amount=Decimal("10000.00"),
            confidence_tier="high",
            methodology_tag="NQ excess",
        )
        events = published_events()
        assert any(e.topic == "fwa.recovery_demanded" for e in events)

    def test_publish_recovery_collected(self) -> None:
        reset_events()
        publish_recovery_collected(
            tenant_id=TEST_TENANT_ID,
            investigation_id="inv-001",
            recovery_id="rec-001",
            amount=Decimal("10000.00"),
        )
        events = published_events()
        assert any(e.topic == "fwa.recovery_collected" for e in events)

    def test_publish_pharmacy_risk_elevated(self) -> None:
        reset_events()
        publish_pharmacy_risk_elevated(
            tenant_id=TEST_TENANT_ID,
            pharmacy_npi="1234567890",
            previous_score=40,
            new_score=80,
            threshold_crossed=75,
        )
        events = published_events()
        assert any(e.topic == "fwa.pharmacy_risk_elevated" for e in events)

    def test_publish_suspicious_community_detected(self) -> None:
        reset_events()
        publish_suspicious_community_detected(
            tenant_id=TEST_TENANT_ID,
            community_id="comm-001",
            node_count=5,
            self_referral_rate=0.85,
            total_amount=250000.0,
        )
        events = published_events()
        assert any(e.topic == "fwa.suspicious_community_detected" for e in events)

    def test_publish_tip_received(self) -> None:
        reset_events()
        publish_tip_received(
            tenant_id=TEST_TENANT_ID,
            tip_id="tip-001",
            tip_type="pharmacy_fraud",
            is_anonymous=True,
        )
        events = published_events()
        assert any(e.topic == "fwa.tip_received" for e in events)

    def test_publish_watchlist_added(self) -> None:
        reset_events()
        publish_watchlist_added(
            tenant_id=TEST_TENANT_ID,
            entity_type="pharmacy",
            entity_id="1234567890",
            fraud_probability_30d=Decimal("0.85"),
        )
        events = published_events()
        assert any(e.topic == "fwa.watchlist_added" for e in events)

    def test_publish_claim_flagged_with_correlation_id(self) -> None:
        reset_events()
        publish_claim_flagged(
            tenant_id=TEST_TENANT_ID,
            flagged_claim_id="flag-002",
            claim_id=None,
            rule_code="MFR-001",
            severity="critical",
            risk_score=95,
            pharmacy_npi="9876543210",
            action_taken="block",
            correlation_id=uuid.uuid4(),
        )
        events = published_events()
        assert any(e.topic == "fwa.claim_flagged" for e in events)
