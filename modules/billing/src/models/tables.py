"""SQLAlchemy models for the billing module.

All money columns are NUMERIC(n,2) — never Float.
Every table is tenant-scoped.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import enum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class BillingBase(DeclarativeBase):
    """Declarative base for billing module."""


# ---------------------------------------------------------------------------
# CLAIMS INGESTION & ROUTING
# ---------------------------------------------------------------------------


class ClaimRecord(BillingBase):
    __tablename__ = "claim_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "auth_number", name="uq_claim_tenant_auth"),
        Index("idx_claims_tenant_status", "tenant_id", "status"),
        Index("idx_claims_tenant_dos", "tenant_id", "date_of_service"),
        Index("idx_claims_tenant_client", "tenant_id", "client_id"),
        Index("idx_claims_nrid", "tenant_id", "network_reimbursement_id"),
        {"schema": "billing"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    # Source
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_claim_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    # SP-1 Plan B Task 1 (migration 0003): provenance link to the Upload that
    # produced this claim. Nullable for backwards compat with rows ingested
    # before the Upload resource existed; the upload service requires it for
    # all new upload-created claims.
    upload_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing.uploads.id"), nullable=True
    )
    # Pharmacy-claimed amount, pre-adjudication (semantically distinct from
    # net_amount which is the post-adjudication paid amount). 14-digit
    # precision with 4dp preserves source-of-truth precision from CSV
    # uploads for audit/dispute resolution.
    amount_billed: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    # Claim identifiers
    auth_number: Mapped[str] = mapped_column(String(50), nullable=False)
    reversal_of_auth: Mapped[str | None] = mapped_column(String(50), nullable=True)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Claim data
    member_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pharmacy_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    pharmacy_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prescriber_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    drug_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    days_supply: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_of_service: Mapped[date] = mapped_column(Date, nullable=False)
    date_received: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Program / routing
    program_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    program_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    network_reimbursement_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Amounts — ALL Decimal, ROUND_HALF_UP enforced in service layer
    ingredient_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    dispensing_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    patient_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    plan_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    other_payer_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    under_reimbursement: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Classification
    payment_route: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_vendor_config_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    payment_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pay_to_entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    pay_to_entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusion_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_statement: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(50), default="ingested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ap_record: Mapped[APRecord | None] = relationship(back_populates="claim_record")


class RoutingRule(BillingBase):
    __tablename__ = "routing_rules"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)

    # Match criteria (None = match all)
    match_nrid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    match_program_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    match_pharmacy_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    match_claim_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    match_client_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    match_conditions: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    # Action
    payment_route: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_vendor_config_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    payment_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaytoWaterfall(BillingBase):
    __tablename__ = "payto_waterfall"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    program_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FileFormatMapping(BillingBase):
    __tablename__ = "file_format_mappings"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    delimiter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    has_header: Mapped[bool] = mapped_column(Boolean, default=True)
    column_mappings: Mapped[Any] = mapped_column(JSON, nullable=False)
    validation_rules: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# ACCOUNTS PAYABLE
# ---------------------------------------------------------------------------


class APRecord(BillingBase):
    __tablename__ = "ap_records"
    __table_args__ = (
        Index("idx_ap_tenant_status", "tenant_id", "status"),
        Index("idx_ap_payto", "tenant_id", "pay_to_entity_id"),
        Index("idx_ap_client", "tenant_id", "client_id"),
        Index("idx_ap_batch", "payment_batch_id"),
        {"schema": "billing"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    claim_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing.claim_records.id", ondelete="RESTRICT"), nullable=False
    )

    client_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    program_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    program_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    pay_to_entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    pay_to_entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    pay_to_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_route: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_vendor_config_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    payment_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="created")
    payment_batch_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    return_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_carryover: Mapped[bool] = mapped_column(Boolean, default=False)
    carryover_from_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    carryover_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    claim_record: Mapped[ClaimRecord] = relationship(back_populates="ap_record")


class PaymentBatch(BillingBase):
    __tablename__ = "payment_batches"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False)

    payment_route: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_vendor_config_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    payment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ap_count: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="generated")

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    validation_result: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    validation_warnings: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    payment_file_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    # Upload provenance (SP-1 Plan C Task 1): nullable so legacy batches remain valid.
    upload_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing.uploads.id", ondelete="SET NULL"), nullable=True
    )

    data_lock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Optimistic locking (H-12): prevents concurrent batch approval from double-submitting.
    # Increment on every approved/submitted transition; check before mutation.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    payments: Mapped[list[Payment]] = relationship(back_populates="batch")


class Payment(BillingBase):
    __tablename__ = "payments"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing.payment_batches.id", ondelete="RESTRICT"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    pay_to_entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    pay_to_entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    pay_to_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    bank_routing_number: Mapped[str | None] = mapped_column(String(9), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(17), nullable=True)
    bank_account_type: Mapped[str | None] = mapped_column(String(10), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="pending")
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    settlement_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    check_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    return_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    remittance_file_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    batch: Mapped[PaymentBatch] = relationship(back_populates="payments")


# ---------------------------------------------------------------------------
# ACCOUNTS RECEIVABLE
# ---------------------------------------------------------------------------


class InvoicingConfig(BillingBase):
    __tablename__ = "invoicing_configs"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    frequency: Mapped[str] = mapped_column(String(50), nullable=False)
    cycle_dates: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    include_programs: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    include_fees: Mapped[bool] = mapped_column(Boolean, default=True)

    automation_level: Mapped[str] = mapped_column(String(50), default="semi_automatic")
    auto_generate_time: Mapped[str | None] = mapped_column(String(8), nullable=True)

    delivery_method: Mapped[str] = mapped_column(String(50), default="email")
    delivery_recipients: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    invoice_template_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    detail_level: Mapped[str] = mapped_column(String(50), default="program")
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)

    late_fee_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    late_fee_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    late_fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    late_fee_percentage: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    late_fee_grace_days: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Invoice(BillingBase):
    __tablename__ = "invoices"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    invoicing_config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing.invoicing_configs.id", ondelete="SET NULL"), nullable=True
    )

    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_type: Mapped[str] = mapped_column(String(50), nullable=False)

    client_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    claims_subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    fees_subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    adjustments: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    late_fees: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    claim_count: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(50), default="draft")

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)

    paid_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))

    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    pdf_file_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    data_lock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Optimistic locking (H-12)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    line_items: Mapped[list[InvoiceLineItem]] = relationship(back_populates="invoice")
    ar_record: Mapped[ARRecord | None] = relationship(back_populates="invoice")


class InvoiceLineItem(BillingBase):
    __tablename__ = "invoice_line_items"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("billing.invoices.id", ondelete="RESTRICT"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    line_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    program_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    program_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fee_config_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Upload provenance (SP-1 Plan C Task 1): nullable so legacy line items remain valid.
    upload_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing.uploads.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="line_items")


class ARRecord(BillingBase):
    __tablename__ = "ar_records"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("billing.invoices.id", ondelete="RESTRICT"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    amount_due: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    amount_outstanding: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="open")
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    days_outstanding: Mapped[int] = mapped_column(Integer, default=0)
    aging_bucket: Mapped[str | None] = mapped_column(String(20), nullable=True)

    dispute_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispute_opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispute_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispute_resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="ar_record")
    payments: Mapped[list[ARPayment]] = relationship(back_populates="ar_record")


class ARPayment(BillingBase):
    __tablename__ = "ar_payments"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    ar_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing.ar_records.id", ondelete="RESTRICT"), nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)

    recorded_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ar_record: Mapped[ARRecord] = relationship(back_populates="payments")


class Carryover(BillingBase):
    """AP amount carried forward to the next payment cycle.

    Created when an APRecord cannot be fully paid in the current batch
    (e.g. vendor hold, partial funding). The original APRecord keeps its
    status; the Carryover represents the outstanding balance that must be
    included in the next PaymentBatch generation run.

    upload_id is nullable: legacy carryovers pre-dating SP-1 have no upload
    provenance; new carryovers created from an upload-originated APRecord
    MUST have upload_id set at the service layer.
    """

    __tablename__ = "carryovers"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    ap_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing.ap_records.id", ondelete="RESTRICT"), nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

    # Upload provenance (SP-1 Plan C Task 1).
    upload_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing.uploads.id", ondelete="SET NULL"), nullable=True
    )

    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# FINANCIAL JOURNAL
# ---------------------------------------------------------------------------


class JournalEntry(BillingBase):
    __tablename__ = "journal_entries"
    __table_args__ = (
        Index("idx_journal_tenant_date", "tenant_id", "entry_date"),
        Index("idx_journal_client", "tenant_id", "client_id", "entry_date"),
        Index("idx_journal_program", "tenant_id", "program_id", "entry_date"),
        Index("idx_journal_type", "tenant_id", "entry_type"),
        Index("idx_journal_category", "tenant_id", "category"),
        Index("idx_journal_exported", "tenant_id", "exported_to_accounting"),
        {"schema": "billing"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    entry_type: Mapped[str] = mapped_column(String(100), nullable=False)

    client_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    program_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    program_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pay_to_entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    pay_to_entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    category: Mapped[str] = mapped_column(String(100), nullable=False)
    gl_account_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gl_class: Mapped[str | None] = mapped_column(String(100), nullable=True)

    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    exported_to_accounting: Mapped[bool] = mapped_column(Boolean, default=False)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    export_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# PROGRAM FINANCIAL MONITORING
# ---------------------------------------------------------------------------


class ProgramBudget(BillingBase):
    __tablename__ = "program_budgets"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    program_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    budget_type: Mapped[str] = mapped_column(String(50), nullable=False)
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    budget_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    budget_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    spent_to_date: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    remaining: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    utilization_percentage: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))

    burn_rate_daily: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    burn_rate_weekly: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    burn_rate_monthly: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    burn_rate_7day_avg: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    burn_rate_30day_avg: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    burn_rate_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    burn_rate_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    projected_depletion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    projected_period_spend: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    projected_over_budget: Mapped[bool] = mapped_column(Boolean, default=False)

    spend_increase_alert_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("25"))
    budget_remaining_alert_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("20")
    )
    depletion_alert_days: Mapped[int] = mapped_column(Integer, default=30)

    last_calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    alerts: Mapped[list[ProgramBudgetAlert]] = relationship(back_populates="program_budget")
    snapshots: Mapped[list[ProgramBudgetSnapshot]] = relationship(back_populates="program_budget")


class ProgramBudgetAlert(BillingBase):
    __tablename__ = "program_budget_alerts"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    program_budget_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing.program_budgets.id", ondelete="RESTRICT"), nullable=False
    )

    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    comparison_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    program_budget: Mapped[ProgramBudget] = relationship(back_populates="alerts")


class ProgramBudgetSnapshot(BillingBase):
    __tablename__ = "program_budget_snapshots"
    __table_args__ = (
        UniqueConstraint("program_budget_id", "snapshot_date", name="uq_budget_snapshot_date"),
        {"schema": "billing"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    program_budget_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing.program_budgets.id", ondelete="RESTRICT"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    spent_to_date: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    daily_spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_claim_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    program_budget: Mapped[ProgramBudget] = relationship(back_populates="snapshots")


# ---------------------------------------------------------------------------
# FEES
# ---------------------------------------------------------------------------


class FeeConfig(BillingBase):
    __tablename__ = "fee_configs"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fee_code: Mapped[str] = mapped_column(String(50), nullable=False)

    calculation_type: Mapped[str] = mapped_column(String(50), nullable=False)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    tiers: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    custom_formula: Mapped[str | None] = mapped_column(Text, nullable=True)

    applies_to_programs: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    applies_to_claim_types: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    applies_to_nrids: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    split_rules: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# FUNDING
# ---------------------------------------------------------------------------


class FundingConfig(BillingBase):
    __tablename__ = "funding_configs"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    funding_model: Mapped[str] = mapped_column(String(50), nullable=False)

    prefund_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"))
    alert_threshold: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    critical_threshold: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    funding_bank_account_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ledger_entries: Mapped[list[PrefundLedger]] = relationship(back_populates="funding_config")


class PrefundLedger(BillingBase):
    __tablename__ = "prefund_ledger"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    funding_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing.funding_configs.id", ondelete="RESTRICT"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    running_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    funding_config: Mapped[FundingConfig] = relationship(back_populates="ledger_entries")


# ---------------------------------------------------------------------------
# REMITTANCE & DELIVERY
# ---------------------------------------------------------------------------


class RemittanceConfig(BillingBase):
    __tablename__ = "remittance_configs"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    delivery_method: Mapped[str] = mapped_column(String(50), default="sftp")
    sftp_config_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    format_type: Mapped[str] = mapped_column(String(50), default="hipaa_835")
    include_pos_adjustment: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SFTPConfig(BillingBase):
    __tablename__ = "sftp_configs"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(20), default="key")
    remote_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_delivery_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# PAYMENT VENDORS & BANK ACCOUNTS
# ---------------------------------------------------------------------------


class PaymentVendorConfig(BillingBase):
    __tablename__ = "payment_vendor_configs"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    vendor_type: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_credentials_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_delivery_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file_format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    settlement_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expected_settlement_days: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BankAccount(BillingBase):
    __tablename__ = "bank_accounts"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    routing_number: Mapped[str] = mapped_column(String(9), nullable=False)
    account_number: Mapped[str] = mapped_column(String(17), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# ACCOUNTING INTEGRATION
# ---------------------------------------------------------------------------


class AccountingConfig(BillingBase):
    __tablename__ = "accounting_configs"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    system_type: Mapped[str] = mapped_column(String(50), nullable=False)
    export_format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    connection_config: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    field_mapping: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    class_mapping: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    auto_export_ap: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_export_ar: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# SEQUENCES
# ---------------------------------------------------------------------------


class BillingSequence(BillingBase):
    __tablename__ = "sequences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sequence_type", name="uq_sequence_tenant_type"),
        {"schema": "billing"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    sequence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prefix: Mapped[str | None] = mapped_column(String(20), nullable=True)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# UPLOADS (SP-1 Plan B Task 1, migration 0003)
# ---------------------------------------------------------------------------


class UploadStatus(str, enum.Enum):
    parsing = "parsing"
    validation_failed = "validation_failed"
    validated = "validated"
    superseded = "superseded"


class Upload(BillingBase):
    __tablename__ = "uploads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sha256", name="uq_upload_tenant_sha256"),
        Index("idx_uploads_tenant_uploaded_at", "tenant_id", "uploaded_at"),
        {"schema": "billing"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(nullable=False)

    source_platform: Mapped[str | None] = mapped_column(String(256), nullable=True)
    supersedes_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing.uploads.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=UploadStatus.parsing.value
    )
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # row_errors must NEVER contain raw member_id values; only the failure
    # category. Reading via the router emits a phi_access audit entry.
    row_errors: Mapped[Any | None] = mapped_column(JSON, nullable=True)

