"""Unit tests for event publishers and consumers."""
from __future__ import annotations

import uuid

import pytest

from shared.events import InMemoryEventBus, EventEnvelope
from src.events.publishers import (
    publish_claim_received,
    publish_claim_priced,
    publish_claim_adjudicated,
    publish_claim_denied,
    publish_340b_detected,
    publish_unified_spend_updated,
    publish_therapeutic_duplication,
)
from src.events.consumers import handle_edi_837_received, handle_pharmacy_claim_adjudicated


TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLAIM = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CORR = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


class TestPublishers:
    @pytest.mark.asyncio
    async def test_publish_claim_received(self):
        bus = InMemoryEventBus()
        await publish_claim_received(bus, TENANT, CLAIM, CORR, "CLM-1", "J0135", "2026-01-15", "250.00")
        events = bus.published
        assert len(events) == 1
        assert events[0].event_type == "medical_claim.received"
        assert events[0].tenant_id == TENANT
        assert events[0].ordering_key == str(CLAIM)
        assert events[0].idempotency_key == f"medical_claim:{CLAIM}:medical_claim.received"

    @pytest.mark.asyncio
    async def test_publish_claim_priced(self):
        bus = InMemoryEventBus()
        await publish_claim_priced(bus, TENANT, CLAIM, CORR, "265.00", "265.00")
        assert bus.published[0].event_type == "medical_claim.priced"
        assert bus.published[0].payload["allowed_amount"] == "265.00"

    @pytest.mark.asyncio
    async def test_publish_claim_adjudicated(self):
        bus = InMemoryEventBus()
        await publish_claim_adjudicated(bus, TENANT, CLAIM, CORR, "paid", "265.00")
        assert bus.published[0].event_type == "medical_claim.adjudicated"

    @pytest.mark.asyncio
    async def test_publish_claim_denied(self):
        bus = InMemoryEventBus()
        await publish_claim_denied(bus, TENANT, CLAIM, CORR, "197", "Prior auth required")
        evt = bus.published[0]
        assert evt.event_type == "medical_claim.denied"
        assert evt.payload["denial_reason_code"] == "197"

    @pytest.mark.asyncio
    async def test_publish_340b_detected(self):
        bus = InMemoryEventBus()
        await publish_340b_detected(bus, TENANT, CLAIM, CORR, "340B:1234567890", "1234567890")
        assert bus.published[0].event_type == "medical_claim.340b_detected"

    @pytest.mark.asyncio
    async def test_publish_unified_spend_updated(self):
        bus = InMemoryEventBus()
        spend_id = uuid.uuid4()
        await publish_unified_spend_updated(bus, TENANT, CLAIM, CORR, spend_id, "medical")
        assert bus.published[0].event_type == "medical_claim.unified_spend_updated"

    @pytest.mark.asyncio
    async def test_publish_therapeutic_duplication(self):
        bus = InMemoryEventBus()
        await publish_therapeutic_duplication(bus, TENANT, CLAIM, CORR, str(uuid.uuid4()), "12345678901", "2026-01-01")
        assert bus.published[0].event_type == "medical_claim.therapeutic_duplication"

    @pytest.mark.asyncio
    async def test_event_payload_amounts_are_strings(self):
        """Financial amounts must be serialized as strings in event payloads."""
        bus = InMemoryEventBus()
        await publish_claim_priced(bus, TENANT, CLAIM, CORR, "106.00", "100.00")
        payload = bus.published[0].payload
        assert isinstance(payload["allowed_amount"], str)
        assert isinstance(payload["paid_amount"], str)


class TestConsumers:
    @pytest.mark.asyncio
    async def test_handle_edi_837_received(self, db_session, tenant_id):
        from src.services.claim_service import ClaimService

        svc = ClaimService(db_session)
        envelope = EventEnvelope(
            event_type="edi.837_received",
            tenant_id=tenant_id,
            correlation_id=CORR,
            source_module="edi-compliance",
            payload={
                "transaction_type": "837P",
                "transaction_record_id": str(uuid.uuid4()),
                "claim_lines": [
                    {
                        "claim_number": "EDI-EVT-001",
                        "claim_line_number": 1,
                        "procedure_code": "J0135",
                        "patient_member_id": "MBR-EVT",
                        "rendering_provider_npi": "1234567890",
                        "date_of_service": "2026-02-20",
                        "billed_amount": "300.00",
                    }
                ],
            },
        )
        await handle_edi_837_received(envelope, claim_service=svc, db=db_session)
        items, total = svc.list_claims(tenant_id)
        claim_numbers = {c.claim_number for c in items}
        assert "EDI-EVT-001" in claim_numbers

    @pytest.mark.asyncio
    async def test_handle_pharmacy_claim_adjudicated(self, db_session, tenant_id, member_id):
        from src.services.unified_spend_service import UnifiedDrugSpendService
        from src.models.tables import UnifiedDrugSpend

        svc = UnifiedDrugSpendService(db_session)
        pharm_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_type="claim.adjudicated",
            tenant_id=tenant_id,
            correlation_id=CORR,
            source_module="billing",
            payload={
                "claim_id": str(pharm_id),
                "member_id": str(member_id),
                "member_id_display": "MBR-PHM",
                "ndc": "12345678901",
                "drug_name": "Adalimumab",
                "date_of_service": "2026-03-10",
                "billed_amount": "500.00",
                "allowed_amount": "450.00",
                "paid_amount": "400.00",
                "patient_pay": "50.00",
                "quantity": "1.0",
                "days_supply": 28,
                "therapeutic_class": "Biologic",
            },
        )
        await handle_pharmacy_claim_adjudicated(envelope, unified_spend_service=svc)

        rows = db_session.query(UnifiedDrugSpend).filter_by(
            tenant_id=tenant_id, pharmacy_claim_id=pharm_id
        ).all()
        assert len(rows) == 1
        assert rows[0].drug_name == "Adalimumab"
        assert rows[0].benefit_type == "pharmacy"

    @pytest.mark.asyncio
    async def test_handle_pharmacy_claim_missing_claim_id(self, db_session, tenant_id):
        """Consumer must handle missing claim_id gracefully."""
        from src.services.unified_spend_service import UnifiedDrugSpendService

        svc = UnifiedDrugSpendService(db_session)
        envelope = EventEnvelope(
            event_type="claim.adjudicated",
            tenant_id=tenant_id,
            correlation_id=CORR,
            source_module="billing",
            payload={},  # missing claim_id
        )
        # Should not raise
        await handle_pharmacy_claim_adjudicated(envelope, unified_spend_service=svc)
