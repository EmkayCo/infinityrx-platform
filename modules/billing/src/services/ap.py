"""Accounts Payable engine.

Handles: AP record creation, payment batch generation, validation, void workflow,
carryover management. All money uses Decimal ROUND_HALF_UP.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src.utils.constants import (
    AP_STATUS_CREATED,
    BATCH_STATUS_GENERATED,
    BATCH_STATUS_VOIDED,
)
from src.utils.money import money


@dataclass
class APRecordData:
    id: uuid.UUID
    tenant_id: uuid.UUID
    claim_record_id: uuid.UUID
    client_id: uuid.UUID
    pay_to_entity_id: uuid.UUID
    pay_to_entity_name: str
    amount: Decimal
    payment_route: str
    status: str
    program_id: uuid.UUID | None = None
    payment_vendor_config_id: uuid.UUID | None = None
    payment_schedule: str | None = None
    pay_to_npi: str | None = None
    payment_batch_id: uuid.UUID | None = None
    settlement_date: Any | None = None
    return_code: str | None = None
    return_reason: str | None = None
    is_carryover: bool = False
    carryover_from_id: uuid.UUID | None = None
    carryover_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PaymentData:
    id: uuid.UUID
    payment_batch_id: uuid.UUID
    tenant_id: uuid.UUID
    pay_to_entity_id: uuid.UUID
    pay_to_entity_name: str
    amount: Decimal
    claim_count: int
    status: str = "pending"
    bank_routing_number: str | None = None
    bank_account_number: str | None = None
    bank_account_type: str | None = None
    payment_method: str | None = None
    return_code: str | None = None
    return_reason: str | None = None


@dataclass
class PaymentBatchData:
    id: uuid.UUID
    tenant_id: uuid.UUID
    batch_number: str
    payment_route: str
    total_amount: Decimal
    payment_count: int
    ap_count: int
    status: str
    payment_vendor_config_id: uuid.UUID | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    approved_by: uuid.UUID | None = None
    submitted_at: datetime | None = None
    settled_at: datetime | None = None
    validation_result: Any | None = None
    validation_warnings: Any | None = None
    data_lock: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PaymentGroup:
    pay_to_entity_id: uuid.UUID
    pay_to_entity_name: str
    total_amount: Decimal
    ap_records: list[dict[str, Any]]


@dataclass
class BatchGenerationResult:
    batch: PaymentBatchData
    payments: list[PaymentData]


class APService:
    def __init__(self, db: Any, events: Any) -> None:
        self._db = db
        self._events = events

    def create_ap_record(
        self,
        tenant_id: uuid.UUID,
        claim_id: uuid.UUID,
        client_id: uuid.UUID,
        program_id: uuid.UUID | None,
        pay_to_entity_id: uuid.UUID,
        pay_to_entity_name: str,
        amount: Decimal,
        payment_route: str,
        payment_vendor_config_id: uuid.UUID | None = None,
        payment_schedule: str | None = None,
        pay_to_npi: str | None = None,
    ) -> APRecordData:
        ap = APRecordData(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_record_id=claim_id,
            client_id=client_id,
            program_id=program_id,
            pay_to_entity_id=pay_to_entity_id,
            pay_to_entity_name=pay_to_entity_name,
            amount=money(amount),
            payment_route=payment_route,
            payment_vendor_config_id=payment_vendor_config_id,
            payment_schedule=payment_schedule,
            pay_to_npi=pay_to_npi,
            status=AP_STATUS_CREATED,
        )
        self._events.publish(
            "ap.created",
            {
                "tenant_id": str(tenant_id),
                "ap_id": str(ap.id),
                "claim_id": str(claim_id),
                "amount": str(ap.amount),
                "payment_route": payment_route,
            },
        )
        return ap

    def group_by_entity(self, ap_records: list[dict[str, Any]]) -> list[PaymentGroup]:
        """Group AP records by pay-to entity and net their amounts."""
        groups: dict[uuid.UUID, PaymentGroup] = {}
        for ap in ap_records:
            entity_id = ap["pay_to_entity_id"]
            if entity_id not in groups:
                groups[entity_id] = PaymentGroup(
                    pay_to_entity_id=entity_id,
                    pay_to_entity_name=ap["pay_to_entity_name"],
                    total_amount=Decimal("0"),
                    ap_records=[],
                )
            groups[entity_id].total_amount = money(
                groups[entity_id].total_amount + money(ap["amount"])
            )
            groups[entity_id].ap_records.append(ap)
        return list(groups.values())

    def generate_batch(
        self,
        tenant_id: uuid.UUID,
        payment_route: str,
        ap_records: list[dict[str, Any]],
        batch_number: str,
        payment_vendor_config_id: uuid.UUID | None = None,
    ) -> BatchGenerationResult:
        if not ap_records:
            raise ValueError("Cannot generate batch from empty AP record list")

        groups = self.group_by_entity(ap_records)
        batch_id = uuid.uuid4()
        now = datetime.now(UTC)

        payments = [
            PaymentData(
                id=uuid.uuid4(),
                payment_batch_id=batch_id,
                tenant_id=tenant_id,
                pay_to_entity_id=g.pay_to_entity_id,
                pay_to_entity_name=g.pay_to_entity_name,
                amount=money(g.total_amount),
                claim_count=len(g.ap_records),
            )
            for g in groups
        ]

        total_amount = money(sum(p.amount for p in payments))

        batch = PaymentBatchData(
            id=batch_id,
            tenant_id=tenant_id,
            batch_number=batch_number,
            payment_route=payment_route,
            payment_vendor_config_id=payment_vendor_config_id,
            total_amount=total_amount,
            payment_count=len(payments),
            ap_count=len(ap_records),
            status=BATCH_STATUS_GENERATED,
            generated_at=now,
            created_at=now,
            updated_at=now,
        )

        self._events.publish(
            "payment_batch.generated",
            {
                "tenant_id": str(tenant_id),
                "batch_id": str(batch_id),
                "batch_number": batch_number,
                "total_amount": str(total_amount),
                "payment_count": len(payments),
            },
        )
        return BatchGenerationResult(batch=batch, payments=payments)

    def validate_batch(self, batch: PaymentBatchData, payments: list[PaymentData]) -> list[str]:
        """Return list of blocking validation errors. Empty list = valid."""
        errors: list[str] = []
        payment_sum = money(sum(p.amount for p in payments))
        if payment_sum != batch.total_amount:
            errors.append(f"Batch total {batch.total_amount} != sum of payments {payment_sum}")
        for payment in payments:
            if payment.amount < Decimal("0"):
                errors.append(
                    f"Negative payment amount {payment.amount} for entity"
                    f" {payment.pay_to_entity_name!r} — AP credits must offset debits"
                )
        return errors

    def void_batch(
        self,
        batch: PaymentBatchData,
        payments: list[PaymentData],
        reason: str,
        voided_by: uuid.UUID,
    ) -> None:
        batch.status = BATCH_STATUS_VOIDED
        batch.updated_at = datetime.now(UTC)
        for payment in payments:
            payment.status = "voided"
        self._events.publish(
            "payment_batch.voided",
            {
                "tenant_id": str(batch.tenant_id),
                "batch_id": str(batch.id),
                "reason": reason,
                "voided_by": str(voided_by),
            },
        )

    def create_carryover(
        self,
        original_ap: dict[str, Any],
        return_code: str,
        return_reason: str,
    ) -> APRecordData:
        """Create a carryover AP record when an ACH payment is returned."""
        original_id = original_ap["id"]
        return APRecordData(
            id=uuid.uuid4(),
            tenant_id=original_ap["tenant_id"],
            claim_record_id=original_ap["claim_record_id"],
            client_id=original_ap["client_id"],
            pay_to_entity_id=original_ap["pay_to_entity_id"],
            pay_to_entity_name=original_ap["pay_to_entity_name"],
            amount=money(original_ap["amount"]),
            payment_route=original_ap["payment_route"],
            status=AP_STATUS_CREATED,
            is_carryover=True,
            carryover_from_id=original_id,
            carryover_reason=return_reason,
            return_code=return_code,
            return_reason=return_reason,
        )
