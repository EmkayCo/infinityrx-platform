"""SQLAlchemy ORM models for the medical_claims schema.

All money columns: Numeric — never Float.
All PHI columns: EncryptedString.
Every tenant-owned table: TenantScopedMixin.
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
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.crypto.sqlalchemy_types import EncryptedString
from shared.db.models.phi_mixin import PHIMixin
from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "medical_claims"


class MedicalClaimsBase(DeclarativeBase):
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


class ClaimRecord(MedicalClaimsBase, TenantScopedMixin, PHIMixin):
    """Medical benefit drug claim at the service line level.

    PHI columns (patient_member_id, diagnosis_code_1..4) are stored as
    AES-256-GCM ciphertext via EncryptedString (LargeBinary in DB).
    Encrypted columns cannot be used as B-tree index keys; tenant+status
    and tenant+date indexes remain for query performance.
    """

    __tablename__ = "claim_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "claim_number", "claim_line_number", name="uq_claim_line"),
        Index("idx_medical_tenant_date", "tenant_id", "date_of_service"),
        Index("idx_medical_provider", "tenant_id", "rendering_provider_npi"),
        Index("idx_medical_ndc", "tenant_id", "ndc"),
        Index("idx_medical_hcpcs", "tenant_id", "procedure_code"),
        Index("idx_medical_status", "tenant_id", "status"),
        Index("idx_medical_claim_num", "tenant_id", "claim_number"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )

    # Claim identity
    claim_number: Mapped[str] = mapped_column(String(50), nullable=False)
    claim_line_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    claim_type: Mapped[str] = mapped_column(String(10), nullable=False)  # professional, institutional

    # Source
    source_transaction_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_file_type: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 837P, 837I, manual, api
    received_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    # Patient — PHI encrypted (AES-256-GCM via EncryptedString, stored as LargeBinary)
    # member_id links to the UUID PK in member-management; patient_member_id is the
    # human-readable member identifier which constitutes PHI under HIPAA §164.514(b)(2)(i).
    member_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    patient_member_id: Mapped[str] = mapped_column(EncryptedString(), nullable=False)
    patient_first_name_encrypted: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    patient_last_name_encrypted: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    patient_dob_encrypted: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    patient_gender: Mapped[str | None] = mapped_column(String(1), nullable=True)

    # Subscriber
    subscriber_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscriber_relationship: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Provider
    rendering_provider_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    rendering_provider_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rendering_provider_taxonomy: Mapped[str | None] = mapped_column(String(20), nullable=True)

    billing_provider_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    billing_provider_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Tax ID (EIN/SSN-equivalent) — PHI-adjacent; encrypted at rest
    billing_provider_tax_id: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)

    referring_provider_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)

    facility_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    facility_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Service
    date_of_service: Mapped[date] = mapped_column(Date, nullable=False)
    date_of_service_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    place_of_service: Mapped[str | None] = mapped_column(String(2), nullable=True)
    type_of_bill: Mapped[str | None] = mapped_column(String(4), nullable=True)

    # Procedure
    procedure_code: Mapped[str] = mapped_column(String(10), nullable=False)
    procedure_code_type: Mapped[str] = mapped_column(String(10), nullable=False, default="HCPCS")
    modifier_1: Mapped[str | None] = mapped_column(String(5), nullable=True)
    modifier_2: Mapped[str | None] = mapped_column(String(5), nullable=True)
    modifier_3: Mapped[str | None] = mapped_column(String(5), nullable=True)
    modifier_4: Mapped[str | None] = mapped_column(String(5), nullable=True)
    revenue_code: Mapped[str | None] = mapped_column(String(4), nullable=True)

    # Drug identification
    ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    ndc_qualifier: Mapped[str | None] = mapped_column(String(2), nullable=True)
    drug_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    drug_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    drug_unit: Mapped[str | None] = mapped_column(String(5), nullable=True)
    drug_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    # HCPCS-to-NDC mapping
    mapped_ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    mapping_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Diagnosis — PHI: ICD-10 codes are PHI when linked to a specific member record
    # (HIPAA §164.514(b)(2)(i)). Stored as AES-256-GCM ciphertext (LargeBinary).
    diagnosis_code_1: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    diagnosis_code_2: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    diagnosis_code_3: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    diagnosis_code_4: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    diagnosis_code_qualifier: Mapped[str | None] = mapped_column(String(5), nullable=True, default="ABK")
    diagnosis_pointer: Mapped[str | None] = mapped_column(String(4), nullable=True)

    # Amounts — all Decimal, ROUND_HALF_UP at service layer
    billed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    allowed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    patient_responsibility: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    copay_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    coinsurance_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    deductible_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    adjustment_reason_codes: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    # Drug waste
    waste_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    waste_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Site of care
    site_of_care: Mapped[str | None] = mapped_column(String(50), nullable=True)
    administration_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 340B
    is_340b: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    entity_340b_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # COB
    payer_sequence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    other_payer_paid: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Authorization
    prior_auth_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prior_auth_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Processing status workflow
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="received")

    denial_reason_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    denial_reason_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Accumulator impact
    applied_to_deductible: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    applied_to_oop: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class HcpcsNdcCrosswalk(MedicalClaimsBase):
    """HCPCS-to-NDC crosswalk reference table. Not tenant-scoped (shared reference data)."""

    __tablename__ = "hcpcs_ndc_crosswalk"
    __table_args__ = (
        UniqueConstraint("hcpcs_code", "ndc", "effective_date", name="uq_hcpcs_ndc_date"),
        Index("idx_hcpcs_crosswalk", "hcpcs_code", "effective_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()

    hcpcs_code: Mapped[str] = mapped_column(String(10), nullable=False)
    hcpcs_description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    ndc_description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    hcpcs_dosage_descriptor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hcpcs_unit_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    ndc_package_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    conversion_factor: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    data_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_updated_at: Mapped[datetime] = _ts_now()


class AspPricing(MedicalClaimsBase):
    """CMS ASP (Average Sales Price) quarterly pricing. Not tenant-scoped (CMS published data)."""

    __tablename__ = "asp_pricing"
    __table_args__ = (
        UniqueConstraint("hcpcs_code", "quarter", name="uq_asp_hcpcs_quarter"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()

    hcpcs_code: Mapped[str] = mapped_column(String(10), nullable=False)
    hcpcs_description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # DECIMAL(12,6) — never downcast to 2dp before multiplying by quantity
    asp_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    payment_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    quarter: Mapped[str] = mapped_column(String(6), nullable=False)  # YYYY-QN
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="cms_asp")
    last_updated_at: Mapped[datetime] = _ts_now()


class UnifiedDrugSpend(MedicalClaimsBase, TenantScopedMixin):
    """Unified drug spend view across pharmacy and medical benefits."""

    __tablename__ = "unified_drug_spend"
    __table_args__ = (
        Index("idx_unified_spend_tenant", "tenant_id", "date_of_service"),
        Index("idx_unified_spend_member", "tenant_id", "member_id"),
        Index("idx_unified_spend_ndc", "tenant_id", "ndc"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )

    member_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    member_id_display: Mapped[str | None] = mapped_column(String(100), nullable=True)

    ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    drug_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    therapeutic_class: Mapped[str | None] = mapped_column(String(255), nullable=True)

    benefit_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pharmacy, medical

    pharmacy_claim_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    medical_claim_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    date_of_service: Mapped[date] = mapped_column(Date, nullable=False)

    billed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    allowed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    patient_pay: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    days_supply: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = _ts_now()


__all__ = [
    "MedicalClaimsBase",
    "ClaimRecord",
    "HcpcsNdcCrosswalk",
    "AspPricing",
    "UnifiedDrugSpend",
]
