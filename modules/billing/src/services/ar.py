"""Accounts Receivable engine.

Handles: invoice generation, fee calculation (8 types), AR record creation,
payment recording, aging, dispute, write-off, void workflows.
All money uses Decimal ROUND_HALF_UP.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from src.utils.constants import (
    AGING_30,
    AGING_60,
    AGING_90,
    AGING_120_PLUS,
    AGING_CURRENT,
    AR_STATUS_DISPUTED,
    AR_STATUS_OPEN,
    AR_STATUS_PAID,
    AR_STATUS_PARTIALLY_PAID,
    AR_STATUS_WRITTEN_OFF,
    FEE_CUSTOM,
    FEE_FLAT_MONTHLY,
    FEE_PER_CLAIM_FLAT,
    FEE_PER_CLAIM_PERCENTAGE,
    FEE_PER_MEMBER_PER_MONTH,
    FEE_PER_TRANSACTION,
    FEE_PERCENTAGE_OF_INGREDIENT_COST,
    FEE_TIERED_VOLUME,
    INVOICE_STATUS_DRAFT,
)
from src.utils.money import money


@dataclass
class FeeConfigData:
    id: uuid.UUID
    fee_code: str
    calculation_type: str
    amount: Decimal | None
    percentage: Decimal | None
    tiers: list[dict[str, Any]] | None


@dataclass
class InvoiceRequest:
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    period_start: date
    period_end: date
    invoice_number: str
    payment_terms_days: int = 30
    invoice_type: str = "combined"
    adjustments: Decimal = field(default_factory=lambda: Decimal("0"))
    late_fees: Decimal = field(default_factory=lambda: Decimal("0"))
    invoicing_config_id: uuid.UUID | None = None


@dataclass
class InvoiceData:
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    invoice_number: str
    invoice_type: str
    period_start: date
    period_end: date
    claims_subtotal: Decimal
    fees_subtotal: Decimal
    adjustments: Decimal
    late_fees: Decimal
    total: Decimal
    claim_count: int
    status: str
    due_date: date | None
    payment_terms_days: int
    paid_amount: Decimal
    data_lock: bool = False
    invoicing_config_id: uuid.UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    generated_at: datetime | None = None


@dataclass
class ARRecordData:
    id: uuid.UUID
    tenant_id: uuid.UUID
    invoice_id: uuid.UUID
    client_id: uuid.UUID
    amount_due: Decimal
    amount_paid: Decimal
    amount_outstanding: Decimal
    status: str
    due_date: date
    days_outstanding: int = 0
    aging_bucket: str | None = None
    dispute_reason: str | None = None
    dispute_opened_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ARService:
    def __init__(self, db: Any, events: Any) -> None:
        self._db = db
        self._events = events

    def calculate_fee(self, fee_config: FeeConfigData, claims: list[dict[str, Any]]) -> Decimal:
        """Calculate fee amount using the configured calculation type."""
        calc = fee_config.calculation_type

        if calc == FEE_PER_CLAIM_FLAT:
            return money((fee_config.amount or Decimal("0")) * len(claims))

        if calc == FEE_PER_CLAIM_PERCENTAGE:
            total_net = sum(money(c["net_amount"]) for c in claims)
            pct = (fee_config.percentage or Decimal("0")) / Decimal("100")
            return money(total_net * pct)

        if calc == FEE_PERCENTAGE_OF_INGREDIENT_COST:
            total_ic = sum(money(c.get("ingredient_cost", Decimal("0"))) for c in claims)
            pct = (fee_config.percentage or Decimal("0")) / Decimal("100")
            return money(total_ic * pct)

        if calc == FEE_FLAT_MONTHLY:
            return money(fee_config.amount or Decimal("0"))

        if calc == FEE_PER_MEMBER_PER_MONTH:
            # Requires member count; count distinct member_ids in claims
            members = {c.get("member_id") for c in claims if c.get("member_id")}
            return money((fee_config.amount or Decimal("0")) * len(members))

        if calc == FEE_PER_TRANSACTION:
            return money((fee_config.amount or Decimal("0")) * len(claims))

        if calc == FEE_TIERED_VOLUME:
            return self._tiered_volume_fee(fee_config, len(claims))

        if calc == FEE_CUSTOM:
            raise ValueError("Custom fee calculation requires runtime evaluation — not implemented")

        raise ValueError(f"Unknown fee calculation type: {calc!r}")

    def _tiered_volume_fee(self, fee_config: FeeConfigData, claim_count: int) -> Decimal:
        tiers = fee_config.tiers or []
        for tier in tiers:
            min_c = int(tier["min_claims"])
            max_c = tier.get("max_claims")
            if max_c is None:
                if claim_count >= min_c:
                    return money(Decimal(str(tier["fee_per_claim"])) * claim_count)
            else:
                if min_c <= claim_count <= int(max_c):
                    return money(Decimal(str(tier["fee_per_claim"])) * claim_count)
        return Decimal("0.00")

    def generate_invoice(
        self,
        req: InvoiceRequest,
        claims: list[dict[str, Any]],
        fee_configs: list[FeeConfigData],
    ) -> InvoiceData:
        claims_subtotal = money(sum(money(c["net_amount"]) for c in claims))
        fees_subtotal = money(sum(self.calculate_fee(fc, claims) for fc in fee_configs))
        adjustments = money(req.adjustments)
        late_fees = money(req.late_fees)
        total = money(claims_subtotal + fees_subtotal + adjustments + late_fees)

        now = datetime.now(UTC)
        due_date = date.today() + timedelta(days=req.payment_terms_days)

        invoice = InvoiceData(
            id=uuid.uuid4(),
            tenant_id=req.tenant_id,
            client_id=req.client_id,
            client_name=req.client_name,
            invoice_number=req.invoice_number,
            invoice_type=req.invoice_type,
            period_start=req.period_start,
            period_end=req.period_end,
            claims_subtotal=claims_subtotal,
            fees_subtotal=fees_subtotal,
            adjustments=adjustments,
            late_fees=late_fees,
            total=total,
            claim_count=len(claims),
            status=INVOICE_STATUS_DRAFT,
            due_date=due_date,
            payment_terms_days=req.payment_terms_days,
            paid_amount=Decimal("0.00"),
            invoicing_config_id=req.invoicing_config_id,
            created_at=now,
            updated_at=now,
            generated_at=now,
        )
        self._events.publish(
            "invoice.generated",
            {
                "tenant_id": str(req.tenant_id),
                "invoice_id": str(invoice.id),
                "invoice_number": req.invoice_number,
                "total": str(total),
                "client_id": str(req.client_id),
            },
        )
        return invoice

    def create_ar_record(
        self,
        tenant_id: uuid.UUID,
        invoice_id: uuid.UUID,
        client_id: uuid.UUID,
        amount_due: Decimal,
        due_date: date,
    ) -> ARRecordData:
        amount_due = money(amount_due)
        return ARRecordData(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            client_id=client_id,
            amount_due=amount_due,
            amount_paid=Decimal("0.00"),
            amount_outstanding=amount_due,
            status=AR_STATUS_OPEN,
            due_date=due_date,
        )

    def record_payment(
        self,
        ar: ARRecordData,
        amount: Decimal,
        payment_date: date,
    ) -> None:
        amount = money(amount)
        ar.amount_paid = money(ar.amount_paid + amount)
        outstanding = money(ar.amount_due - ar.amount_paid)
        ar.amount_outstanding = money(max(outstanding, Decimal("0")))
        if ar.amount_outstanding == Decimal("0.00"):
            ar.status = AR_STATUS_PAID
        else:
            ar.status = AR_STATUS_PARTIALLY_PAID
        ar.updated_at = datetime.now(UTC)
        self._events.publish(
            "ar.payment_received",
            {
                "tenant_id": str(ar.tenant_id),
                "ar_id": str(ar.id),
                "amount": str(amount),
                "status": ar.status,
            },
        )

    def open_dispute(self, ar: ARRecordData, reason: str) -> None:
        ar.status = AR_STATUS_DISPUTED
        ar.dispute_reason = reason
        ar.dispute_opened_at = datetime.now(UTC)
        ar.updated_at = datetime.now(UTC)
        self._events.publish(
            "ar.disputed",
            {
                "tenant_id": str(ar.tenant_id),
                "ar_id": str(ar.id),
                "reason": reason,
            },
        )

    def write_off(self, ar: ARRecordData, approved_by: uuid.UUID) -> None:
        ar.status = AR_STATUS_WRITTEN_OFF
        ar.updated_at = datetime.now(UTC)
        self._events.publish(
            "ar.written_off",
            {
                "tenant_id": str(ar.tenant_id),
                "ar_id": str(ar.id),
                "approved_by": str(approved_by),
                "amount_written_off": str(ar.amount_outstanding),
            },
        )

    def aging_bucket(self, days_outstanding: int) -> str:
        """Return the AR aging bucket label for a given number of days outstanding.

        Standard AR aging: current (0), 30 (1-30), 60 (31-60), 90 (61-90), 120_plus (91+).
        """
        if days_outstanding == 0:
            return AGING_CURRENT
        if days_outstanding <= 30:
            return AGING_30
        if days_outstanding <= 60:
            return AGING_60
        if days_outstanding <= 90:
            return AGING_90
        return AGING_120_PLUS
