"""SQLAlchemy ORM models for the edi schema.

All tenant-owned tables inherit TenantScopedMixin.
No Float columns — Numeric only for amounts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base
from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "edi"


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


def _ts_now() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TradingPartner(TenantScopedMixin, Base):
    __tablename__ = "trading_partners"
    __table_args__ = (
        UniqueConstraint("tenant_id", "isa_qualifier", "isa_id", name="uq_tp_isa"),
        Index("ix_tp_tenant", "tenant_id", "is_active"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    partner_type: Mapped[str] = mapped_column(String(50), nullable=False)

    isa_qualifier: Mapped[str] = mapped_column(String(2), nullable=False)
    isa_id: Mapped[str] = mapped_column(String(15), nullable=False)
    gs_id: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)

    supported_transactions: Mapped[Any] = mapped_column(JSONB, nullable=False)
    transport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    transport_config: Mapped[Any] = mapped_column(JSONB, nullable=False)

    test_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    companion_guide_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_transmission_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_transmission_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class ControlNumberSequence(TenantScopedMixin, Base):
    __tablename__ = "control_number_sequences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "trading_partner_id", "sequence_type", name="uq_cn_seq"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    trading_partner_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("edi.trading_partners.id"),
        nullable=True,
    )
    sequence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    current_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    max_value: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=999999999)


class TransactionFile(TenantScopedMixin, Base):
    __tablename__ = "transaction_files"
    __table_args__ = (
        Index("ix_edi_files_tenant", "tenant_id", "direction", "transaction_type", "created_at"),
        Index("ix_edi_files_isa", "isa_control_number"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    trading_partner_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("edi.trading_partners.id"),
        nullable=True,
    )

    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)
    implementation_guide: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    isa_control_number: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)
    gs_control_number: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)

    file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    transaction_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_claim_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_amount: Mapped[Optional[Any]] = mapped_column(Numeric(15, 2), nullable=True)

    validation_status: Mapped[str] = mapped_column(String(50), default="pending")
    validation_errors: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    validation_warnings: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    transmission_status: Mapped[str] = mapped_column(String(50), default="pending")
    transmitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    ack_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    ack_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ack_errors: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    processing_errors: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    expected_response_by: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class TransactionRecord(TenantScopedMixin, Base):
    __tablename__ = "transaction_records"
    __table_args__ = (
        Index("ix_edi_records_file", "transaction_file_id"),
        Index("ix_edi_records_claim", "tenant_id", "claim_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    transaction_file_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("edi.transaction_files.id"),
        nullable=False,
    )

    st_control_number: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)

    claim_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    patient_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider_npi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    payer_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    total_amount: Mapped[Optional[Any]] = mapped_column(Numeric(12, 2), nullable=True)
    paid_amount: Mapped[Optional[Any]] = mapped_column(Numeric(12, 2), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="received")
    validation_errors: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    processing_result: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    internal_claim_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    internal_payment_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = _ts_now()


class ComplianceLog(TenantScopedMixin, Base):
    __tablename__ = "compliance_log"
    __table_args__ = (
        Index("ix_compliance_tenant", "tenant_id", "regulation", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    regulation: Mapped[str] = mapped_column(String(100), nullable=False)
    requirement: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_assessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_assessment_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    assessed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class AS2Certificate(TenantScopedMixin, Base):
    """AS2 certificate lifecycle tracking (PRD §3.19)."""

    __tablename__ = "as2_certificates"
    __table_args__ = (
        Index("ix_as2_cert_tenant", "tenant_id", "status"),
        Index("ix_as2_cert_expiry", "not_after", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    trading_partner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("edi.trading_partners.id"),
        nullable=False,
    )
    cert_type: Mapped[str] = mapped_column(String(20), nullable=False)
    issuer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    not_before: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    not_after: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fingerprint_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class TradingPartnerAgreement(TenantScopedMixin, Base):
    """BAA / TPA tracking (PRD §3.20)."""

    __tablename__ = "trading_partner_agreements"
    __table_args__ = (
        Index("ix_tpa_tenant", "tenant_id", "trading_partner_id"),
        Index("ix_tpa_expiry", "expiry_date", "agreement_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    trading_partner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("edi.trading_partners.id"),
        nullable=False,
    )
    agreement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    executed_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    effective_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    expiry_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    renewal_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    signatory_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    signatory_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class PayerCompanionRule(TenantScopedMixin, Base):
    """Level 4 payer companion guide rules (PRD §3.11)."""

    __tablename__ = "payer_companion_rules"
    __table_args__ = (
        Index("ix_pcr_payer", "tenant_id", "payer_id", "transaction_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    payer_id: Mapped[str] = mapped_column(String(50), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)
    segment: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    element_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_definition: Mapped[Any] = mapped_column(JSONB, nullable=False)
    effective_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()
