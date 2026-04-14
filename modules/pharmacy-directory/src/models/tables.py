"""ORM models for the pharmacy_dir schema.

Pharmacies are a shared directory (no tenant_id). Networks, memberships,
credentialing, and payment info are tenant-scoped (TenantScopedMixin).
"""
from __future__ import annotations

import uuid as _uuid_module
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from shared.crypto.sqlalchemy_types import EncryptedString
from shared.db.tenant_context import TenantScopedMixin
from sqlalchemy import (
    JSON,
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
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import PharmacyBase as Base

# JSON works in both PostgreSQL (as jsonb via column definition) and SQLite
_JSONB = JSON

SCHEMA = "pharmacy_dir"


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        Uuid(),
        primary_key=True,
        default=_uuid_module.uuid4,
    )


def _ts_now() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Pharmacy (shared directory — no tenant_id)
# ---------------------------------------------------------------------------


class Pharmacy(Base):
    __tablename__ = "pharmacies"
    __table_args__ = (
        Index("ix_pharmacy_npi", "npi"),
        Index("ix_pharmacy_nabp", "nabp_number"),
        Index("ix_pharmacy_type", "pharmacy_type"),
        Index("ix_pharmacy_chain", "chain_code"),
        Index("ix_pharmacy_location", "state", "city"),
        Index("ix_pharmacy_geo", "latitude", "longitude"),
        Index("ix_pharmacy_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()

    npi: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    nabp_number: Mapped[str | None] = mapped_column(String(7))
    ncpdp_id: Mapped[str | None] = mapped_column(String(10))
    dea_number: Mapped[str | None] = mapped_column(String(9))
    state_license_number: Mapped[str | None] = mapped_column(String(50))
    state_license_state: Mapped[str | None] = mapped_column(String(2))

    legal_name: Mapped[str] = mapped_column(String(500), nullable=False)
    dba_name: Mapped[str | None] = mapped_column(String(500))
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)

    pharmacy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    chain_name: Mapped[str | None] = mapped_column(String(255))
    chain_code: Mapped[str | None] = mapped_column(String(50))
    store_number: Mapped[str | None] = mapped_column(String(50))

    address_line_1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    county: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2), server_default="US")
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))

    phone: Mapped[str | None] = mapped_column(String(20))
    fax: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(500))

    hours_monday: Mapped[str | None] = mapped_column(String(50))
    hours_tuesday: Mapped[str | None] = mapped_column(String(50))
    hours_wednesday: Mapped[str | None] = mapped_column(String(50))
    hours_thursday: Mapped[str | None] = mapped_column(String(50))
    hours_friday: Mapped[str | None] = mapped_column(String(50))
    hours_saturday: Mapped[str | None] = mapped_column(String(50))
    hours_sunday: Mapped[str | None] = mapped_column(String(50))
    is_24_hour: Mapped[bool] = mapped_column(Boolean, server_default="false")

    accepts_electronic_rx: Mapped[bool] = mapped_column(Boolean, server_default="true")
    dispenses_controlled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    offers_delivery: Mapped[bool] = mapped_column(Boolean, server_default="false")
    offers_compounding: Mapped[bool] = mapped_column(Boolean, server_default="false")
    offers_specialty: Mapped[bool] = mapped_column(Boolean, server_default="false")
    offers_340b: Mapped[bool] = mapped_column(Boolean, server_default="false")
    offers_immunizations: Mapped[bool] = mapped_column(Boolean, server_default="false")
    offers_mtm: Mapped[bool] = mapped_column(Boolean, server_default="false")
    offers_covid_testing: Mapped[bool] = mapped_column(Boolean, server_default="false")
    languages_spoken: Mapped[dict[str, Any] | None] = mapped_column(
        _JSONB, server_default='["en"]'
    )

    ownership_type: Mapped[str | None] = mapped_column(String(50))
    owner_name: Mapped[str | None] = mapped_column(String(255))
    ownership_effective_date: Mapped[date | None] = mapped_column(Date)
    previous_owner_name: Mapped[str | None] = mapped_column(String(255))
    ownership_change_date: Mapped[date | None] = mapped_column(Date)

    is_340b_entity: Mapped[bool] = mapped_column(Boolean, server_default="false")
    hrsa_id: Mapped[str | None] = mapped_column(String(20))
    covered_entity_type: Mapped[str | None] = mapped_column(String(100))

    status: Mapped[str] = mapped_column(String(50), server_default="active")
    deactivation_date: Mapped[date | None] = mapped_column(Date)
    deactivation_reason: Mapped[str | None] = mapped_column(String(255))

    ncpdp_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nppes_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manual_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Network (tenant-scoped)
# ---------------------------------------------------------------------------


class Network(Base, TenantScopedMixin):
    __tablename__ = "networks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "network_code", name="uq_networks_tenant_code"),
        Index("ix_networks_tenant_status", "tenant_id", "is_active"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        Uuid(), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    network_code: Mapped[str] = mapped_column(String(50), nullable=False)
    network_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    any_willing_pharmacy: Mapped[bool] = mapped_column(Boolean, server_default="false")
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# NetworkMembership (tenant-scoped)
# ---------------------------------------------------------------------------


class NetworkMembership(Base, TenantScopedMixin):
    __tablename__ = "network_memberships"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "pharmacy_id",
            "network_id",
            "effective_date",
            name="uq_memberships_tenant_pharmacy_network_date",
        ),
        Index("ix_memberships_tenant_network", "tenant_id", "network_id"),
        Index("ix_memberships_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        Uuid(), nullable=False, index=True
    )
    pharmacy_id: Mapped[UUID] = mapped_column(
        Uuid(),
        ForeignKey(f"{SCHEMA}.pharmacies.id"),
        nullable=False,
    )
    network_id: Mapped[UUID] = mapped_column(
        Uuid(),
        ForeignKey(f"{SCHEMA}.networks.id"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(String(50), server_default="active")
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    termination_reason: Mapped[str | None] = mapped_column(String(255))

    contract_id: Mapped[UUID | None] = mapped_column(Uuid())
    reimbursement_type: Mapped[str | None] = mapped_column(String(50))
    brand_discount: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    generic_discount: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    specialty_discount: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    dispensing_fee: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    admin_fee: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    performance_tier: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# CredentialingApplication (tenant-scoped)
# ---------------------------------------------------------------------------


class CredentialingApplication(Base, TenantScopedMixin):
    __tablename__ = "credentialing_applications"
    __table_args__ = (
        Index("ix_credentialing_tenant_status", "tenant_id", "status"),
        Index("ix_credentialing_npi", "applicant_npi"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        Uuid(), nullable=False, index=True
    )
    pharmacy_id: Mapped[UUID | None] = mapped_column(
        Uuid(), ForeignKey(f"{SCHEMA}.pharmacies.id")
    )

    applicant_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    applicant_name: Mapped[str] = mapped_column(String(500), nullable=False)
    applicant_address: Mapped[str | None] = mapped_column(Text)

    network_id: Mapped[UUID] = mapped_column(
        Uuid(),
        ForeignKey(f"{SCHEMA}.networks.id"),
        nullable=False,
    )
    application_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())

    credentialing_risk_score: Mapped[int | None] = mapped_column(Integer)
    risk_score_factors: Mapped[dict[str, Any] | None] = mapped_column(_JSONB)

    npi_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    state_license_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    state_license_expiry: Mapped[date | None] = mapped_column(Date)
    dea_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    dea_expiry: Mapped[date | None] = mapped_column(Date)
    oig_sam_screened: Mapped[bool] = mapped_column(Boolean, server_default="false")
    oig_sam_clear: Mapped[bool] = mapped_column(Boolean, server_default="false")
    liability_insurance_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    insurance_expiry: Mapped[date | None] = mapped_column(Date)

    status: Mapped[str] = mapped_column(String(50), server_default="submitted")
    reviewed_by: Mapped[UUID | None] = mapped_column(Uuid())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    denial_reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# CredentialingDocument
# ---------------------------------------------------------------------------


class CredentialingDocument(Base):
    __tablename__ = "credentialing_documents"
    __table_args__ = (
        Index("ix_cred_docs_application_id", "application_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    application_id: Mapped[UUID] = mapped_column(
        Uuid(),
        ForeignKey(f"{SCHEMA}.credentialing_applications.id"),
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_id: Mapped[UUID | None] = mapped_column(Uuid())
    status: Mapped[str] = mapped_column(String(50), server_default="pending")
    expiry_date: Mapped[date | None] = mapped_column(Date)
    verified_by: Mapped[UUID | None] = mapped_column(Uuid())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# CredentialMonitoring (tenant-scoped)
# ---------------------------------------------------------------------------


class CredentialMonitoring(Base, TenantScopedMixin):
    __tablename__ = "credential_monitoring"
    __table_args__ = (
        Index("ix_cred_monitor_tenant_pharmacy", "tenant_id", "pharmacy_id"),
        Index("ix_cred_monitor_expiry", "expiry_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        Uuid(), nullable=False, index=True
    )
    pharmacy_id: Mapped[UUID] = mapped_column(
        Uuid(),
        ForeignKey(f"{SCHEMA}.pharmacies.id"),
        nullable=False,
    )
    credential_type: Mapped[str] = mapped_column(String(100), nullable=False)
    current_status: Mapped[str] = mapped_column(String(50), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    alert_days_before_expiry: Mapped[int] = mapped_column(Integer, server_default="90")
    alert_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_verification_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# PharmacyPaymentInfo (tenant-scoped) — sensitive fields encrypted
# ---------------------------------------------------------------------------


class PharmacyPaymentInfo(Base, TenantScopedMixin):
    __tablename__ = "pharmacy_payment_info"
    __table_args__ = (
        UniqueConstraint("tenant_id", "pharmacy_id", name="uq_payment_info_tenant_pharmacy"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        Uuid(), nullable=False, index=True
    )
    pharmacy_id: Mapped[UUID] = mapped_column(
        Uuid(),
        ForeignKey(f"{SCHEMA}.pharmacies.id"),
        nullable=False,
    )

    payment_method_preference: Mapped[str | None] = mapped_column(String(50))

    # Sensitive fields — encrypted at rest
    bank_name: Mapped[str | None] = mapped_column(EncryptedString())
    routing_number: Mapped[str | None] = mapped_column(EncryptedString())
    account_number: Mapped[str | None] = mapped_column(EncryptedString())
    account_type: Mapped[str | None] = mapped_column(String(20))

    remittance_delivery: Mapped[str | None] = mapped_column(String(50))
    remittance_email: Mapped[str | None] = mapped_column(String(255))
    remittance_sftp_config_id: Mapped[UUID | None] = mapped_column(Uuid())

    w9_on_file: Mapped[bool] = mapped_column(Boolean, server_default="false")
    w9_file_id: Mapped[UUID | None] = mapped_column(Uuid())
    tax_id: Mapped[str | None] = mapped_column(EncryptedString())

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# PSAO
# ---------------------------------------------------------------------------


class Psao(Base):
    __tablename__ = "psaos"
    __table_args__ = (
        Index("ix_psaos_npi", "npi"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    psao_id: Mapped[str | None] = mapped_column(String(50))
    npi: Mapped[str | None] = mapped_column(String(10))

    address: Mapped[str | None] = mapped_column(Text)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(20))

    payment_consolidated: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = _ts_now()


class PsaoMembership(Base):
    __tablename__ = "psao_memberships"
    __table_args__ = (
        Index("ix_psao_memberships_pharmacy_id", "pharmacy_id"),
        Index("ix_psao_memberships_psao_id", "psao_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    pharmacy_id: Mapped[UUID] = mapped_column(
        Uuid(),
        ForeignKey(f"{SCHEMA}.pharmacies.id"),
        nullable=False,
    )
    psao_id: Mapped[UUID] = mapped_column(
        Uuid(),
        ForeignKey(f"{SCHEMA}.psaos.id"),
        nullable=False,
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# PharmacyPerformanceSnapshot
# ---------------------------------------------------------------------------


class PharmacyPerformanceSnapshot(Base):
    __tablename__ = "pharmacy_performance_snapshots"
    __table_args__ = (
        Index("ix_perf_snapshot_npi_period", "pharmacy_id", "period_year", "period_month"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    pharmacy_id: Mapped[UUID] = mapped_column(
        Uuid(),
        ForeignKey(f"{SCHEMA}.pharmacies.id"),
        nullable=False,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)

    total_claims: Mapped[int] = mapped_column(Integer, server_default="0")
    total_dollar_volume: Mapped[Decimal] = mapped_column(Numeric(16, 2), server_default="0.00")
    unique_members_served: Mapped[int] = mapped_column(Integer, server_default="0")
    generic_fill_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    reversal_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    fwa_flag_count: Mapped[int] = mapped_column(Integer, server_default="0")
    daw_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    avg_claim_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    created_at: Mapped[datetime] = _ts_now()


__all__ = [
    "Pharmacy",
    "Network",
    "NetworkMembership",
    "CredentialingApplication",
    "CredentialingDocument",
    "CredentialMonitoring",
    "PharmacyPaymentInfo",
    "Psao",
    "PsaoMembership",
    "PharmacyPerformanceSnapshot",
]
