"""Tests for event consumers and scheduled jobs."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from shared.events.types import EventEnvelope
from sqlalchemy.orm import Session
from src.events.consumers import (
    CONSUMER_ROUTING,
    handle_ap_created,
    handle_ap_settled,
    handle_claim_adjudicated,
    handle_claim_reversed,
    handle_exclusion_match_found,
    handle_payment_return_suspicious,
    handle_pharmacy_application_submitted,
    handle_pharmacy_ownership_changed,
)
from src.jobs.scheduled import (
    JOB_SCHEDULE,
    job_calculate_false_positive_rates,
    job_check_regulatory_deadlines,
    job_check_statute_deadlines,
    job_expire_payment_holds,
    job_rebuild_fraud_network_graph,
    job_recalculate_entity_profiles,
    job_retrain_ml_models,
    job_take_entity_profile_snapshots,
)
from src.models.tables import PaymentHold

from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def _env(event_type: str, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        correlation_id=uuid.uuid4(),
        source_module="test",
        schema_version="1.0",
        ordering_key="t1",
        idempotency_key=f"{event_type}:{uuid.uuid4()}",
        payload=payload,
    )


class TestEventConsumers:
    """Smoke tests: handlers accept envelopes and return without raising on db=None."""

    @pytest.mark.asyncio
    async def test_handle_claim_adjudicated(self) -> None:
        await handle_claim_adjudicated(
            _env("claim.adjudicated", {"claim_id": "c1", "auth_number": "A1", "pharmacy_npi": "1234567890"}),
            db=None,
            bus=None,
        )

    @pytest.mark.asyncio
    async def test_handle_claim_reversed(self) -> None:
        await handle_claim_reversed(_env("claim.reversed", {"auth_number": "A1"}), db=None, bus=None)

    @pytest.mark.asyncio
    async def test_handle_ap_created(self) -> None:
        await handle_ap_created(_env("ap.created", {"ap_id": "ap1", "claim_id": "c1"}), db=None, bus=None)

    @pytest.mark.asyncio
    async def test_handle_ap_settled(self) -> None:
        await handle_ap_settled(_env("ap.settled", {"ap_id": "ap2", "claim_id": "c1"}), db=None, bus=None)

    @pytest.mark.asyncio
    async def test_handle_exclusion_match_found(self) -> None:
        await handle_exclusion_match_found(
            _env("exclusion.match_found", {"entity_type": "pharmacy", "entity_id": "1234567890"}),
            db=None, bus=None,
        )

    @pytest.mark.asyncio
    async def test_handle_payment_return_suspicious(self) -> None:
        await handle_payment_return_suspicious(
            _env("payment.return_suspicious", {"payment_id": "p1", "entity_id": "1234567890", "amount": "500.00"}),
            db=None, bus=None,
        )

    @pytest.mark.asyncio
    async def test_handle_pharmacy_application_submitted(self) -> None:
        await handle_pharmacy_application_submitted(
            _env("pharmacy.application_submitted", {"pharmacy_npi": "1234567890"}),
            db=None, bus=None,
        )

    @pytest.mark.asyncio
    async def test_handle_pharmacy_ownership_changed(self) -> None:
        await handle_pharmacy_ownership_changed(
            _env("pharmacy.ownership_changed", {"pharmacy_npi": "1234567890"}),
            db=None, bus=None,
        )

    def test_consumer_routing_has_all_handlers(self) -> None:
        expected_topics = {
            "accumulator.updated",
            "claim.adjudicated",
            "claim.reversed",
            "ap.created",
            "ap.settled",
            "exclusion.match_found",
            "payment.return_suspicious",
            "pharmacy.application_submitted",
            "pharmacy.ownership_changed",
        }
        assert expected_topics == set(CONSUMER_ROUTING.keys())


class TestScheduledJobs:
    def test_recalculate_entity_profiles(self, db: Session) -> None:
        result = job_recalculate_entity_profiles(db, str(TEST_TENANT_ID))
        assert "pharmacies" in result
        assert "prescribers" in result
        assert "members" in result

    def test_rebuild_fraud_network_graph(self, db: Session) -> None:
        result = job_rebuild_fraud_network_graph(db, str(TEST_TENANT_ID))
        assert "communities_detected" in result

    def test_retrain_ml_models(self, db: Session) -> None:
        result = job_retrain_ml_models(db, str(TEST_TENANT_ID))
        assert "models_retrained" in result

    def test_check_statute_deadlines(self, db: Session) -> None:
        result = job_check_statute_deadlines(db)
        assert "alerts_sent" in result

    def test_check_regulatory_deadlines(self, db: Session) -> None:
        result = job_check_regulatory_deadlines(db)
        assert "alerts_sent" in result

    def test_expire_payment_holds_no_holds(self, db: Session) -> None:
        result = job_expire_payment_holds(db)
        assert result["expired"] == 0

    def test_expire_payment_holds_expires_past_holds(self, db: Session) -> None:
        past = datetime.now(UTC) - timedelta(days=1)
        hold = PaymentHold(
            tenant_id=str(TEST_TENANT_ID),
            entity_type="pharmacy",
            entity_id="1234567890",
            entity_name="Test Pharmacy",
            hold_scope="all",
            placed_by=str(TEST_USER_ID),
            is_active=True,
            expires_at=past,
        )
        db.add(hold)
        db.flush()
        result = job_expire_payment_holds(db)
        assert result["expired"] >= 1
        db.refresh(hold)
        assert hold.is_active is False
        assert hold.release_reason == "Auto-expired"

    def test_expire_payment_holds_ignores_future_holds(self, db: Session) -> None:
        future = datetime.now(UTC) + timedelta(days=30)
        hold = PaymentHold(
            tenant_id=str(TEST_TENANT_ID),
            entity_type="pharmacy",
            entity_id="9999999999",
            entity_name="Future Pharmacy",
            hold_scope="all",
            placed_by=str(TEST_USER_ID),
            is_active=True,
            expires_at=future,
        )
        db.add(hold)
        db.flush()
        job_expire_payment_holds(db)
        db.refresh(hold)
        assert hold.is_active is True

    def test_expire_payment_holds_ignores_no_expiry(self, db: Session) -> None:
        hold = PaymentHold(
            tenant_id=str(TEST_TENANT_ID),
            entity_type="pharmacy",
            entity_id="8888888888",
            entity_name="No Expiry Pharmacy",
            hold_scope="all",
            placed_by=str(TEST_USER_ID),
            is_active=True,
            expires_at=None,
        )
        db.add(hold)
        db.flush()
        job_expire_payment_holds(db)
        db.refresh(hold)
        assert hold.is_active is True

    def test_calculate_false_positive_rates(self, db: Session) -> None:
        result = job_calculate_false_positive_rates(db, str(TEST_TENANT_ID))
        assert "rules_reviewed" in result

    def test_take_entity_profile_snapshots(self, db: Session) -> None:
        result = job_take_entity_profile_snapshots(db, str(TEST_TENANT_ID))
        assert "snapshots_created" in result

    def test_job_schedule_has_all_jobs(self) -> None:
        expected = {
            "recalculate_entity_profiles",
            "rebuild_fraud_network_graph",
            "retrain_ml_models",
            "check_statute_deadlines",
            "check_regulatory_deadlines",
            "expire_payment_holds",
            "calculate_false_positive_rates",
            "take_entity_profile_snapshots",
        }
        assert expected == set(JOB_SCHEDULE.keys())
