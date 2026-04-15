"""SQLAlchemy ORM tables for payment_proc schema.

All money columns use NUMERIC(precision, scale) — never Float.
UUID primary keys generated server-side.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from .._shim.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class VendorAdapter(Base):
    """payment_proc.vendor_adapters — one record per payment vendor per tenant."""

    __tablename__ = "payment_proc_vendor_adapters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    vendor_type: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Connection
    connection_type: Mapped[str] = mapped_column(String(50), nullable=False)
    api_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sftp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sftp_port: Mapped[int] = mapped_column(Integer, default=22)
    sftp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sftp_remote_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credentials_vault_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # File format
    file_format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_naming_pattern: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Settlement
    settlement_method: Mapped[str] = mapped_column(String(50), nullable=False)
    settlement_poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    expected_settlement_days: Mapped[int] = mapped_column(Integer, default=2)

    # Capabilities
    supports_ach: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_eft: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_virtual_card: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_check: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_same_day_ach: Mapped[bool] = mapped_column(Boolean, default=False)

    # Health
    status: Mapped[str] = mapped_column(String(50), default="active")
    last_submission_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_submission_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_settlement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_count_24h: Mapped[int] = mapped_column(Integer, default=0)

    # Failover chain — JSON list of vendor_adapter IDs in priority order
    failover_chain: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Submission(Base):
    """payment_proc.submissions — each file/API call sent to a vendor."""

    __tablename__ = "payment_proc_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    vendor_adapter_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Reference to Billing
    billing_payment_batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Idempotency key — derived from tenant+batch+vendor+timestamp
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    submission_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    encryption_key_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    payment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="pending")

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    vendor_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # OFAC screening result
    ofac_screened: Mapped[bool] = mapped_column(Boolean, default=False)
    ofac_screened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # NACHA 2026 fraud monitoring
    fraud_monitoring_logged: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Settlement(Base):
    """payment_proc.settlement_records — per-payment settlement tracking."""

    __tablename__ = "payment_proc_settlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    submission_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    billing_payment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    pay_to_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    pay_to_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="pending")

    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    settlement_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_method_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    check_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trace_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    return_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    vendor_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor_status: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Payment hold support (from ReclaimRx FWA)
    is_held: Mapped[bool] = mapped_column(Boolean, default=False)
    hold_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_settlement_tenant_status", "tenant_id", "status"),
        Index("idx_settlement_billing_payment", "billing_payment_id"),
    )


class AchReturnCode(Base):
    """payment_proc.ach_return_codes — pre-loaded R01-R85 table."""

    __tablename__ = "payment_proc_ach_return_codes"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    is_retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    default_action: Mapped[str] = mapped_column(String(50), nullable=False)
    retry_delay_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    triggers_fwa_alert: Mapped[bool] = mapped_column(Boolean, default=False)


class VendorHealthLog(Base):
    """payment_proc.vendor_health_log — health check history."""

    __tablename__ = "payment_proc_vendor_health_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    vendor_adapter_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OfacSdnEntry(Base):
    """OFAC Specially Designated Nationals entry — a blocked entity.

    Seeded from https://sanctionssearch.ofac.treas.gov/ SDN CSV (or an API
    integration when credentials are available). Tenant-agnostic reference
    data: the SDN list is shared across all tenants.
    """

    __tablename__ = "payment_proc_ofac_sdn"
    __table_args__ = (
        Index("idx_ofac_sdn_type", "sdn_type"),
        Index("idx_ofac_sdn_name", "canonical_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    sdn_uid: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    sdn_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "individual" | "entity" | "vessel"
    program: Mapped[str | None] = mapped_column(String(50), nullable=True)  # SDN program code (e.g. SDGT, CYBER2)
    canonical_name: Mapped[str] = mapped_column(String(500), nullable=False)  # lowercased, stripped
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)  # newline-separated AKA names
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(String(3), nullable=True)  # ISO 3166-1 alpha-3
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="SDN")  # SDN | CONS | NS-PLC
    source_list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class OfacScreeningAlert(Base):
    """Audit record of every OFAC hit — payment blocked, investigation opened."""

    __tablename__ = "payment_proc_ofac_alerts"
    __table_args__ = (
        Index("idx_ofac_alert_tenant", "tenant_id", "created_at"),
        Index("idx_ofac_alert_entity", "tenant_id", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sdn_uid: Mapped[str] = mapped_column(String(50), nullable=False)
    sdn_canonical_name: Mapped[str] = mapped_column(String(500), nullable=False)
    match_confidence: Mapped[str] = mapped_column(String(20), nullable=False)  # exact | probable | possible
    match_score: Mapped[int] = mapped_column(Integer, nullable=False)
    match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked_payment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)  # open | cleared | confirmed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PayeeEnrollment(Base):
    """payment_proc.payee_enrollments — enrollment status per pharmacy per vendor."""

    __tablename__ = "payment_proc_payee_enrollments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    vendor_adapter_id: Mapped[str] = mapped_column(String(36), nullable=False)

    pay_to_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    pay_to_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pay_to_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    enrollment_status: Mapped[str] = mapped_column(String(50), default="not_enrolled")
    preferred_payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (UniqueConstraint("tenant_id", "vendor_adapter_id", "pay_to_entity_id"),)
