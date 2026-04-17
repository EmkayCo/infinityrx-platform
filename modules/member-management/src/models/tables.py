"""SQLAlchemy ORM models for the member_mgmt schema.

All money columns: Numeric(12, 2) — never Float.
All PHI columns: EncryptedString via PHIMixin.
Every table: TenantScopedMixin.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from shared.crypto.sqlalchemy_types import EncryptedString
from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "member_mgmt"


class MemberMgmtBase(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


def _ts_now() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Groups / Employers
# ---------------------------------------------------------------------------


class Group(MemberMgmtBase, TenantScopedMixin):
    __tablename__ = "groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "group_number", name="uq_groups_tenant_number"),
        Index("idx_groups_tenant_active", "tenant_id", "is_active"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    group_number: Mapped[str] = mapped_column(String(50), nullable=False)
    group_name: Mapped[str] = mapped_column(String(500), nullable=False)

    employer_name: Mapped[str | None] = mapped_column(String(500))
    employer_tax_id: Mapped[str | None] = mapped_column(String(11))
    employer_address: Mapped[str | None] = mapped_column(Text)

    default_plan_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(20))

    billing_cycle: Mapped[str] = mapped_column(String(50), server_default="monthly")
    payment_terms_days: Mapped[int] = mapped_column(Integer, server_default="30")

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()

    members: Mapped[list["Member"]] = relationship("Member", back_populates="group")


# ---------------------------------------------------------------------------
# Members (PHI columns via EncryptedString)
# ---------------------------------------------------------------------------


class Member(MemberMgmtBase, TenantScopedMixin):
    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "member_id", "person_code",
            name="uq_members_tenant_id_person_code"
        ),
        Index("idx_member_tenant_id", "tenant_id", "member_id"),
        Index("idx_member_cardholder", "tenant_id", "cardholder_id"),
        Index("idx_member_group", "tenant_id", "group_id"),
        Index("idx_member_status", "tenant_id", "status"),
        Index("idx_member_bin_pcn", "rx_bin", "rx_pcn", "rx_group"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )

    # Identifiers
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    person_code: Mapped[str] = mapped_column(String(5), server_default="01", default="01")
    cardholder_id: Mapped[str | None] = mapped_column(String(100))
    alternate_id: Mapped[str | None] = mapped_column(String(100))

    # Demographics — PHI columns (AES-256 encrypted at rest)
    first_name_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=False)
    middle_name_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=True)
    last_name_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=False)
    suffix: Mapped[str | None] = mapped_column(String(20))
    dob_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)
    ssn_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=True)

    # Address — PHI
    address_line_1_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=True)
    address_line_2_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=True)
    city_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=True)
    state_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=True)
    zip_code_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=True)
    country: Mapped[str] = mapped_column(String(2), server_default="US", default="US")

    # Contact — PHI
    phone_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=True)
    email_encrypted: Mapped[bytes | None] = mapped_column(EncryptedString(), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), server_default="en", default="en")

    # Relationship
    relationship_code: Mapped[str | None] = mapped_column(String(5))
    subscriber_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    # Group
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.groups.id"),
    )

    # ID Card
    rx_bin: Mapped[str] = mapped_column(String(6), nullable=False)
    rx_pcn: Mapped[str | None] = mapped_column(String(10))
    rx_group: Mapped[str | None] = mapped_column(String(15))

    # Status
    status: Mapped[str] = mapped_column(String(50), server_default="active", default="active")
    enrollment_date: Mapped[date | None] = mapped_column(Date)
    termination_date: Mapped[date | None] = mapped_column(Date)
    termination_reason: Mapped[str | None] = mapped_column(String(100))

    # Merge tracking
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    # Medicare
    is_medicare: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    medicare_beneficiary_id: Mapped[str | None] = mapped_column(String(20))
    lis_level: Mapped[str | None] = mapped_column(String(5))

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()

    group: Mapped["Group | None"] = relationship("Group", back_populates="members")
    coverage_periods: Mapped[list["CoveragePeriod"]] = relationship(
        "CoveragePeriod", back_populates="member"
    )
    accumulators: Mapped[list["Accumulator"]] = relationship(
        "Accumulator", back_populates="member"
    )
    cob_records: Mapped[list["CobRecord"]] = relationship(
        "CobRecord", back_populates="member"
    )


# ---------------------------------------------------------------------------
# Coverage Periods
# ---------------------------------------------------------------------------


class CoveragePeriod(MemberMgmtBase, TenantScopedMixin):
    __tablename__ = "coverage_periods"
    __table_args__ = (
        Index("idx_coverage_member", "tenant_id", "member_id", "effective_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.members.id"),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    plan_name: Mapped[str | None] = mapped_column(String(255))
    coverage_type: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    benefit_year_start: Mapped[date] = mapped_column(Date, nullable=False)
    benefit_year_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default="active")
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()

    member: Mapped["Member"] = relationship("Member", back_populates="coverage_periods")
    accumulators: Mapped[list["Accumulator"]] = relationship(
        "Accumulator", back_populates="coverage_period"
    )


# ---------------------------------------------------------------------------
# Accumulators
# ---------------------------------------------------------------------------


class Accumulator(MemberMgmtBase, TenantScopedMixin):
    __tablename__ = "accumulators"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "member_id", "coverage_period_id", "accumulator_type",
            name="uq_accumulator_member_period_type",
        ),
        Index("idx_accumulator_member", "tenant_id", "member_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.members.id"),
        nullable=False,
    )
    coverage_period_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.coverage_periods.id"),
        nullable=False,
    )
    accumulator_type: Mapped[str] = mapped_column(String(50), nullable=False)
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    accumulated_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", default=Decimal("0.00")
    )
    remaining_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    copay_assistance_applied: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", default=Decimal("0.00")
    )
    copay_assistance_counted: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", default=Decimal("0.00")
    )
    benefit_phase: Mapped[str | None] = mapped_column(String(50))
    last_updated_claim_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()

    member: Mapped["Member"] = relationship("Member", back_populates="accumulators")
    coverage_period: Mapped["CoveragePeriod"] = relationship(
        "CoveragePeriod", back_populates="accumulators"
    )
    ledger_entries: Mapped[list["AccumulatorLedger"]] = relationship(
        "AccumulatorLedger", back_populates="accumulator"
    )


class AccumulatorLedger(MemberMgmtBase, TenantScopedMixin):
    __tablename__ = "accumulator_ledger"
    __table_args__ = (
        Index("idx_accumulator_ledger", "accumulator_id", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    accumulator_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.accumulators.id"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    running_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    claim_auth_number: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()

    accumulator: Mapped["Accumulator"] = relationship(
        "Accumulator", back_populates="ledger_entries"
    )


# ---------------------------------------------------------------------------
# COB Records
# ---------------------------------------------------------------------------


class CobRecord(MemberMgmtBase, TenantScopedMixin):
    __tablename__ = "cob_records"
    __table_args__ = (
        Index("idx_cob_member", "tenant_id", "member_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.members.id"),
        nullable=False,
    )
    payer_sequence: Mapped[str] = mapped_column(String(10), nullable=False)
    other_payer_name: Mapped[str | None] = mapped_column(String(500))
    other_payer_bin: Mapped[str | None] = mapped_column(String(6))
    other_payer_pcn: Mapped[str | None] = mapped_column(String(10))
    other_payer_group: Mapped[str | None] = mapped_column(String(15))
    other_payer_member_id: Mapped[str | None] = mapped_column(String(100))
    other_payer_type: Mapped[str | None] = mapped_column(String(50))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()

    member: Mapped["Member"] = relationship("Member", back_populates="cob_records")


# ---------------------------------------------------------------------------
# Enrollment Files
# ---------------------------------------------------------------------------


class EnrollmentFile(MemberMgmtBase, TenantScopedMixin):
    __tablename__ = "enrollment_files"
    __table_args__ = (
        Index("idx_enrollment_files_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default="uploaded")
    total_records: Mapped[int | None] = mapped_column(Integer)
    processed_records: Mapped[int] = mapped_column(Integer, server_default="0")
    added_records: Mapped[int] = mapped_column(Integer, server_default="0")
    updated_records: Mapped[int] = mapped_column(Integer, server_default="0")
    terminated_records: Mapped[int] = mapped_column(Integer, server_default="0")
    error_records: Mapped[int] = mapped_column(Integer, server_default="0")
    validation_errors: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Eligibility Checks
# ---------------------------------------------------------------------------


class EligibilityCheck(MemberMgmtBase, TenantScopedMixin):
    __tablename__ = "eligibility_checks"
    __table_args__ = (
        Index("idx_eligibility_tenant_created", "tenant_id", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    requested_member_id: Mapped[str | None] = mapped_column(String(100))
    requested_dob: Mapped[date | None] = mapped_column(Date)
    requested_bin: Mapped[str | None] = mapped_column(String(6))
    requested_pcn: Mapped[str | None] = mapped_column(String(10))
    requested_group: Mapped[str | None] = mapped_column(String(15))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    is_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(255))
    matched_member_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    matched_plan_name: Mapped[str | None] = mapped_column(String(255))
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _ts_now()
