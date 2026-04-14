"""Tests for member event publishing and claim event consuming (Session 3).

RED tests written before implementation (TDD).
LESSON-006: Every publisher has integration test through route → mocked bus.
"""
from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from src.events.publishers import MemberEventPublisher
from src.events.consumers import ClaimAdjudicatedConsumer, ClaimReversedConsumer

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBER_UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CLAIM_UUID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ACC_UUID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ---------------------------------------------------------------------------
# MemberEventPublisher — EventEnvelope compliance
# ---------------------------------------------------------------------------

class TestMemberEventPublisher:
    @pytest.fixture
    def bus(self):
        b = InMemoryEventBus()
        return b

    @pytest.fixture
    def publisher(self, bus):
        return MemberEventPublisher(bus=bus)

    @pytest.mark.asyncio
    async def test_publish_member_enrolled_event(self, publisher, bus):
        await publisher.member_enrolled(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            correlation_id=uuid.uuid4(),
        )
        assert len(bus.published) == 1
        env = bus.published[0]
        assert env.event_type == "member.enrolled"
        assert env.tenant_id == TENANT_ID
        assert env.ordering_key == str(MEMBER_UUID)
        assert env.schema_version == "1.0"

    @pytest.mark.asyncio
    async def test_publish_member_updated_event(self, publisher, bus):
        await publisher.member_updated(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            changed_fields=["address_line_1", "phone"],
            correlation_id=uuid.uuid4(),
        )
        env = bus.published[0]
        assert env.event_type == "member.updated"
        assert "changed_fields" in env.payload

    @pytest.mark.asyncio
    async def test_publish_member_terminated_event(self, publisher, bus):
        await publisher.member_terminated(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            termination_reason="voluntary_withdrawal",
            termination_date=date(2026, 4, 13),
            correlation_id=uuid.uuid4(),
        )
        env = bus.published[0]
        assert env.event_type == "member.terminated"
        assert env.payload["termination_reason"] == "voluntary_withdrawal"

    @pytest.mark.asyncio
    async def test_publish_accumulator_updated_event(self, publisher, bus):
        await publisher.accumulator_updated(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            accumulator_id=ACC_UUID,
            accumulator_type="individual_deductible",
            accumulated_amount=Decimal("175.00"),
            limit_amount=Decimal("500.00"),
            applied=Decimal("75.00"),
            claim_id=CLAIM_UUID,
            correlation_id=uuid.uuid4(),
        )
        env = bus.published[0]
        assert env.event_type == "member.accumulator_updated"
        # Decimals serialized as str()
        assert env.payload["accumulated_amount"] == "175.00"
        assert env.payload["limit_amount"] == "500.00"
        assert env.payload["applied"] == "75.00"
        assert env.ordering_key == str(MEMBER_UUID)

    @pytest.mark.asyncio
    async def test_publish_benefit_phase_changed_event(self, publisher, bus):
        await publisher.benefit_phase_changed(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            accumulator_id=ACC_UUID,
            old_phase="deductible",
            new_phase="initial_coverage",
            troop=Decimal("500.00"),
            correlation_id=uuid.uuid4(),
        )
        env = bus.published[0]
        assert env.event_type == "member.benefit_phase_changed"
        assert env.payload["old_phase"] == "deductible"
        assert env.payload["new_phase"] == "initial_coverage"
        assert env.payload["troop"] == "500.00"

    @pytest.mark.asyncio
    async def test_publish_cob_changed_event(self, publisher, bus):
        await publisher.cob_changed(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            action="added",
            payer_sequence="secondary",
            correlation_id=uuid.uuid4(),
        )
        env = bus.published[0]
        assert env.event_type == "member.cob_changed"

    @pytest.mark.asyncio
    async def test_publish_member_merged_event(self, publisher, bus):
        surviving_id = uuid.uuid4()
        merged_id = uuid.uuid4()
        await publisher.member_merged(
            tenant_id=TENANT_ID,
            surviving_member_id=surviving_id,
            merged_member_id=merged_id,
            correlation_id=uuid.uuid4(),
        )
        env = bus.published[0]
        assert env.event_type == "member.merged"
        assert env.payload["surviving_member_id"] == str(surviving_id)
        assert env.payload["merged_member_id"] == str(merged_id)

    @pytest.mark.asyncio
    async def test_publish_retroactive_enrollment_event(self, publisher, bus):
        await publisher.retroactive_enrollment(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            effective_date=date(2026, 1, 15),
            retroactive_days=87,
            correlation_id=uuid.uuid4(),
        )
        env = bus.published[0]
        assert env.event_type == "member.retroactive_enrollment"
        assert env.payload["retroactive_days"] == 87

    @pytest.mark.asyncio
    async def test_publish_member_plan_changed_event(self, publisher, bus):
        await publisher.member_plan_changed(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            old_plan_id=uuid.uuid4(),
            new_plan_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
        )
        env = bus.published[0]
        assert env.event_type == "member.plan_changed"

    @pytest.mark.asyncio
    async def test_accumulator_updated_idempotency_key_is_business_key(self, publisher, bus):
        """idempotency_key must be deterministic business-level key, not random."""
        corr = uuid.uuid4()
        await publisher.accumulator_updated(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            accumulator_id=ACC_UUID,
            accumulator_type="individual_deductible",
            accumulated_amount=Decimal("175.00"),
            limit_amount=Decimal("500.00"),
            applied=Decimal("75.00"),
            claim_id=CLAIM_UUID,
            correlation_id=corr,
        )
        env = bus.published[0]
        # idempotency_key must include accumulator_id and claim_id
        assert str(ACC_UUID) in env.idempotency_key
        assert str(CLAIM_UUID) in env.idempotency_key

    @pytest.mark.asyncio
    async def test_no_phi_in_event_payload(self, publisher, bus):
        """PHI fields must never appear in published events."""
        await publisher.member_enrolled(
            tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            correlation_id=uuid.uuid4(),
        )
        env = bus.published[0]
        payload_str = json.dumps(env.payload)
        phi_keys = {"first_name", "last_name", "ssn", "date_of_birth", "address", "phone", "email"}
        for key in phi_keys:
            assert key not in payload_str, f"PHI key {key!r} found in event payload"


# ---------------------------------------------------------------------------
# ClaimAdjudicatedConsumer — consumes claim.adjudicated, updates accumulator
# ---------------------------------------------------------------------------

class TestClaimAdjudicatedConsumer:
    @pytest.fixture
    def idempotency_store(self):
        return InMemoryIdempotencyStore()

    @pytest.mark.asyncio
    async def test_claim_adjudicated_updates_accumulator(self, idempotency_store, db_session):
        """Consumer updates accumulator on claim.adjudicated event."""
        from src.models.tables import Accumulator, AccumulatorLedger, CoveragePeriod, Member, Group

        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number="GCA01",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr = Member(id=MEMBER_UUID, tenant_id=TENANT_ID, member_id="MCA001",
                     rx_bin="610014", first_name_encrypted="A",
                     last_name_encrypted="B", dob_encrypted="1990-01-01", gender="F")
        db_session.add(mbr)
        cov = CoveragePeriod(id=COVERAGE_UUID if 'COVERAGE_UUID' in dir() else uuid.uuid4(),
                             tenant_id=TENANT_ID, member_id=MEMBER_UUID,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        acc = Accumulator(id=ACC_UUID, tenant_id=TENANT_ID, member_id=MEMBER_UUID,
                          coverage_period_id=cov.id, accumulator_type="individual_deductible",
                          limit_amount=Decimal("500.00"), accumulated_amount=Decimal("100.00"))
        db_session.add(acc)
        db_session.flush()

        consumer = ClaimAdjudicatedConsumer(
            db=db_session,
            idempotency_store=idempotency_store,
        )
        payload = {
            "tenant_id": str(TENANT_ID),
            "member_id": str(MEMBER_UUID),
            "claim_id": str(CLAIM_UUID),
            "accumulator_id": str(ACC_UUID),
            "patient_pay": "75.00",
            "accumulator_type": "individual_deductible",
        }
        idempotency_key = f"claim.adjudicated:{CLAIM_UUID}"
        await consumer.handle(idempotency_key, payload)

        db_session.refresh(acc)
        assert acc.accumulated_amount == Decimal("175.00")
        rows = db_session.query(AccumulatorLedger).filter_by(accumulator_id=ACC_UUID).all()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_claim_adjudicated_idempotent_second_call_is_noop(self, idempotency_store, db_session):
        """Duplicate event delivery → accumulator updated only once."""
        from src.models.tables import Accumulator, CoveragePeriod, Member, Group

        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number="GCA02",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr_id = uuid.uuid4()
        mbr = Member(id=mbr_id, tenant_id=TENANT_ID, member_id="MCA002",
                     rx_bin="610014", first_name_encrypted="A",
                     last_name_encrypted="B", dob_encrypted="1990-01-01", gender="F")
        db_session.add(mbr)
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_ID, member_id=mbr_id,
                          coverage_period_id=cov.id, accumulator_type="individual_deductible",
                          limit_amount=Decimal("500.00"), accumulated_amount=Decimal("0.00"))
        db_session.add(acc)
        db_session.flush()

        claim_id = uuid.uuid4()
        consumer = ClaimAdjudicatedConsumer(db=db_session, idempotency_store=idempotency_store)
        payload = {
            "tenant_id": str(TENANT_ID),
            "member_id": str(mbr_id),
            "claim_id": str(claim_id),
            "accumulator_id": str(acc_id),
            "patient_pay": "100.00",
            "accumulator_type": "individual_deductible",
        }
        key = f"claim.adjudicated:{claim_id}"
        await consumer.handle(key, payload)
        await consumer.handle(key, payload)  # duplicate

        db_session.refresh(acc)
        assert acc.accumulated_amount == Decimal("100.00")  # only applied once

    @pytest.mark.asyncio
    async def test_claim_adjudicated_unknown_fields_ignored(self, idempotency_store, db_session):
        """Unknown payload fields from future schema versions are ignored."""
        from src.models.tables import Accumulator, CoveragePeriod, Member, Group

        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number="GCA03",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr_id = uuid.uuid4()
        mbr = Member(id=mbr_id, tenant_id=TENANT_ID, member_id="MCA003",
                     rx_bin="610014", first_name_encrypted="A",
                     last_name_encrypted="B", dob_encrypted="1990-01-01", gender="F")
        db_session.add(mbr)
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_ID, member_id=mbr_id,
                          coverage_period_id=cov.id, accumulator_type="individual_oop_max",
                          limit_amount=Decimal("2000.00"), accumulated_amount=Decimal("0.00"))
        db_session.add(acc)
        db_session.flush()

        claim_id = uuid.uuid4()
        consumer = ClaimAdjudicatedConsumer(db=db_session, idempotency_store=idempotency_store)
        payload = {
            "tenant_id": str(TENANT_ID),
            "member_id": str(mbr_id),
            "claim_id": str(claim_id),
            "accumulator_id": str(acc_id),
            "patient_pay": "200.00",
            "accumulator_type": "individual_oop_max",
            "new_future_field": "some_value",  # unknown field — must not raise
            "schema_version": "2.0",
        }
        key = f"claim.adjudicated:{claim_id}"
        await consumer.handle(key, payload)  # must not raise
        db_session.refresh(acc)
        assert acc.accumulated_amount == Decimal("200.00")


# ---------------------------------------------------------------------------
# ClaimReversedConsumer
# ---------------------------------------------------------------------------

class TestClaimReversedConsumer:
    @pytest.fixture
    def idempotency_store(self):
        return InMemoryIdempotencyStore()

    @pytest.mark.asyncio
    async def test_claim_reversed_decreases_accumulator(self, idempotency_store, db_session):
        from src.models.tables import Accumulator, CoveragePeriod, Member, Group

        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number="GCR01",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr_id = uuid.uuid4()
        mbr = Member(id=mbr_id, tenant_id=TENANT_ID, member_id="MCR001",
                     rx_bin="610014", first_name_encrypted="A",
                     last_name_encrypted="B", dob_encrypted="1990-01-01", gender="M")
        db_session.add(mbr)
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_ID, member_id=mbr_id,
                          coverage_period_id=cov.id, accumulator_type="individual_deductible",
                          limit_amount=Decimal("500.00"), accumulated_amount=Decimal("300.00"))
        db_session.add(acc)
        db_session.flush()

        claim_id = uuid.uuid4()
        consumer = ClaimReversedConsumer(db=db_session, idempotency_store=idempotency_store)
        payload = {
            "tenant_id": str(TENANT_ID),
            "member_id": str(mbr_id),
            "claim_id": str(claim_id),
            "accumulator_id": str(acc_id),
            "patient_pay": "150.00",
            "accumulator_type": "individual_deductible",
        }
        key = f"claim.reversed:{claim_id}"
        await consumer.handle(key, payload)
        db_session.refresh(acc)
        assert acc.accumulated_amount == Decimal("150.00")

    @pytest.mark.asyncio
    async def test_claim_reversed_idempotent(self, idempotency_store, db_session):
        from src.models.tables import Accumulator, CoveragePeriod, Member, Group

        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number="GCR02",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr_id = uuid.uuid4()
        mbr = Member(id=mbr_id, tenant_id=TENANT_ID, member_id="MCR002",
                     rx_bin="610014", first_name_encrypted="A",
                     last_name_encrypted="B", dob_encrypted="1990-01-01", gender="F")
        db_session.add(mbr)
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_ID, member_id=mbr_id,
                          coverage_period_id=cov.id, accumulator_type="individual_deductible",
                          limit_amount=Decimal("500.00"), accumulated_amount=Decimal("200.00"))
        db_session.add(acc)
        db_session.flush()

        claim_id = uuid.uuid4()
        consumer = ClaimReversedConsumer(db=db_session, idempotency_store=idempotency_store)
        payload = {
            "tenant_id": str(TENANT_ID),
            "claim_id": str(claim_id),
            "accumulator_id": str(acc_id),
            "patient_pay": "50.00",
            "accumulator_type": "individual_deductible",
        }
        key = f"claim.reversed:{claim_id}"
        await consumer.handle(key, payload)
        await consumer.handle(key, payload)  # duplicate
        db_session.refresh(acc)
        assert acc.accumulated_amount == Decimal("150.00")  # only reversed once

    @pytest.mark.asyncio
    async def test_claim_reversed_missing_tenant_id_is_no_op(self, idempotency_store, db_session):
        """Payload without tenant_id is silently ignored."""
        consumer = ClaimReversedConsumer(db=db_session, idempotency_store=idempotency_store)
        payload = {
            "claim_id": str(uuid.uuid4()),
            "accumulator_id": str(uuid.uuid4()),
            "patient_pay": "25.00",
        }
        # Should not raise — just returns early
        await consumer.handle(f"claim.reversed:{uuid.uuid4()}", payload)
