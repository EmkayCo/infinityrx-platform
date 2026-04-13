"""Unit tests for AP engine — 100% coverage on all financial paths."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from src.services.ap import APService
from src.utils.constants import (
    AP_STATUS_CREATED,
    BATCH_STATUS_GENERATED,
    BATCH_STATUS_VOIDED,
    ROUTE_ECHO,
)
from src.utils.money import money

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLIENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROGRAM = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ENTITY_A = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
ENTITY_B = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
USER = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _ap_record(
    amount: Decimal = Decimal("100.00"),
    pay_to_entity_id: uuid.UUID = ENTITY_A,
    pay_to_entity_name: str = "Test Pharmacy",
    status: str = AP_STATUS_CREATED,
    payment_route: str = ROUTE_ECHO,
) -> dict:
    return {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "claim_record_id": uuid.uuid4(),
        "client_id": CLIENT,
        "program_id": PROGRAM,
        "pay_to_entity_id": pay_to_entity_id,
        "pay_to_entity_name": pay_to_entity_name,
        "amount": amount,
        "payment_route": payment_route,
        "status": status,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


def _svc(events=None) -> APService:
    return APService(db=MagicMock(), events=events or MagicMock())


class TestAPRecordCreation:
    def test_create_ap_record_from_claim(self) -> None:
        svc = _svc()
        ap = svc.create_ap_record(
            tenant_id=TENANT,
            claim_id=uuid.uuid4(),
            client_id=CLIENT,
            program_id=PROGRAM,
            pay_to_entity_id=ENTITY_A,
            pay_to_entity_name="Test Pharmacy",
            amount=Decimal("100.00"),
            payment_route=ROUTE_ECHO,
        )
        assert ap.status == AP_STATUS_CREATED
        assert ap.amount == money("100.00")
        assert isinstance(ap.amount, Decimal)

    def test_ap_amount_is_decimal(self) -> None:
        svc = _svc()
        ap = svc.create_ap_record(
            tenant_id=TENANT,
            claim_id=uuid.uuid4(),
            client_id=CLIENT,
            program_id=PROGRAM,
            pay_to_entity_id=ENTITY_A,
            pay_to_entity_name="Test Pharmacy",
            amount=Decimal("55.55"),
            payment_route=ROUTE_ECHO,
        )
        assert isinstance(ap.amount, Decimal)

    def test_create_ap_publishes_event(self) -> None:
        events = MagicMock()
        svc = _svc(events=events)
        svc.create_ap_record(
            tenant_id=TENANT,
            claim_id=uuid.uuid4(),
            client_id=CLIENT,
            program_id=PROGRAM,
            pay_to_entity_id=ENTITY_A,
            pay_to_entity_name="Test Pharmacy",
            amount=Decimal("100.00"),
            payment_route=ROUTE_ECHO,
        )
        events.publish.assert_called_once()
        topic = events.publish.call_args[0][0]
        assert topic == "ap.created"


class TestBatchGeneration:
    def test_group_by_pay_to_entity(self) -> None:
        svc = _svc()
        ap_records = [
            _ap_record(amount=Decimal("100.00"), pay_to_entity_id=ENTITY_A),
            _ap_record(amount=Decimal("50.00"), pay_to_entity_id=ENTITY_A),
            _ap_record(amount=Decimal("75.00"), pay_to_entity_id=ENTITY_B),
        ]
        groups = svc.group_by_entity(ap_records)
        assert len(groups) == 2
        entity_a_group = next(g for g in groups if g.pay_to_entity_id == ENTITY_A)
        assert entity_a_group.total_amount == money("150.00")

    def test_batch_total_equals_sum_of_payments(self) -> None:
        svc = _svc()
        ap_records = [
            _ap_record(amount=Decimal("100.00"), pay_to_entity_id=ENTITY_A),
            _ap_record(amount=Decimal("75.00"), pay_to_entity_id=ENTITY_B),
            _ap_record(amount=Decimal("25.00"), pay_to_entity_id=ENTITY_A),
        ]
        result = svc.generate_batch(
            tenant_id=TENANT,
            payment_route=ROUTE_ECHO,
            ap_records=ap_records,
            batch_number="BATCH001",
        )
        payment_sum = sum(p.amount for p in result.payments)
        assert result.batch.total_amount == payment_sum
        assert result.batch.total_amount == money("200.00")

    def test_batch_total_is_decimal(self) -> None:
        svc = _svc()
        ap_records = [_ap_record(amount=Decimal("33.33"), pay_to_entity_id=ENTITY_A)]
        result = svc.generate_batch(
            tenant_id=TENANT,
            payment_route=ROUTE_ECHO,
            ap_records=ap_records,
            batch_number="BATCH001",
        )
        assert isinstance(result.batch.total_amount, Decimal)

    def test_net_reversals_offsets_same_entity(self) -> None:
        svc = _svc()
        ap_records = [
            _ap_record(amount=Decimal("100.00"), pay_to_entity_id=ENTITY_A),
            _ap_record(amount=Decimal("-25.00"), pay_to_entity_id=ENTITY_A),
        ]
        groups = svc.group_by_entity(ap_records)
        entity_a = next(g for g in groups if g.pay_to_entity_id == ENTITY_A)
        assert entity_a.total_amount == money("75.00")

    def test_batch_status_is_generated(self) -> None:
        svc = _svc()
        ap_records = [_ap_record()]
        result = svc.generate_batch(
            tenant_id=TENANT,
            payment_route=ROUTE_ECHO,
            ap_records=ap_records,
            batch_number="BATCH001",
        )
        assert result.batch.status == BATCH_STATUS_GENERATED

    def test_empty_ap_list_raises(self) -> None:
        svc = _svc()
        with pytest.raises(ValueError, match="empty"):
            svc.generate_batch(
                tenant_id=TENANT,
                payment_route=ROUTE_ECHO,
                ap_records=[],
                batch_number="BATCH001",
            )

    def test_batch_publishes_generated_event(self) -> None:
        events = MagicMock()
        svc = _svc(events=events)
        ap_records = [_ap_record()]
        svc.generate_batch(
            tenant_id=TENANT,
            payment_route=ROUTE_ECHO,
            ap_records=ap_records,
            batch_number="BATCH001",
        )
        topics = [c[0][0] for c in events.publish.call_args_list]
        assert "payment_batch.generated" in topics


class TestBatchValidation:
    def test_validates_batch_total_equals_payment_sum(self) -> None:
        svc = _svc()
        ap_records = [
            _ap_record(amount=Decimal("100.00"), pay_to_entity_id=ENTITY_A),
            _ap_record(amount=Decimal("200.00"), pay_to_entity_id=ENTITY_B),
        ]
        result = svc.generate_batch(
            tenant_id=TENANT,
            payment_route=ROUTE_ECHO,
            ap_records=ap_records,
            batch_number="BATCH001",
        )
        errors = svc.validate_batch(result.batch, result.payments)
        assert errors == []

    def test_negative_payment_amount_is_blocked(self) -> None:
        svc = _svc()
        ap_records = [_ap_record(amount=Decimal("-100.00"), pay_to_entity_id=ENTITY_A)]
        result = svc.generate_batch(
            tenant_id=TENANT,
            payment_route=ROUTE_ECHO,
            ap_records=ap_records,
            batch_number="BATCH001",
        )
        errors = svc.validate_batch(result.batch, result.payments)
        assert any("negative" in e.lower() for e in errors)


class TestVoidBatch:
    def test_void_batch_sets_status_voided(self) -> None:
        svc = _svc()
        ap_records = [_ap_record()]
        result = svc.generate_batch(
            tenant_id=TENANT,
            payment_route=ROUTE_ECHO,
            ap_records=ap_records,
            batch_number="BATCH001",
        )
        svc.void_batch(result.batch, result.payments, reason="test void", voided_by=USER)
        assert result.batch.status == BATCH_STATUS_VOIDED

    def test_void_batch_publishes_event(self) -> None:
        events = MagicMock()
        svc = _svc(events=events)
        ap_records = [_ap_record()]
        result = svc.generate_batch(
            tenant_id=TENANT,
            payment_route=ROUTE_ECHO,
            ap_records=ap_records,
            batch_number="BATCH001",
        )
        events.reset_mock()
        svc.void_batch(result.batch, result.payments, reason="test void", voided_by=USER)
        topics = [c[0][0] for c in events.publish.call_args_list]
        assert "payment_batch.voided" in topics


class TestCarryover:
    def test_create_carryover_from_returned_ap(self) -> None:
        svc = _svc()
        original = _ap_record(amount=Decimal("100.00"))
        carryover = svc.create_carryover(
            original_ap=original,
            return_code="R01",
            return_reason="Insufficient funds",
        )
        assert carryover.amount == original["amount"]
        assert carryover.is_carryover is True
        assert carryover.return_code == "R01"
