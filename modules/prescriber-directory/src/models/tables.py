"""SQLAlchemy ORM models for the prescriber-directory module.

Schema: prescriber_dir
All models follow architecture rules:
- schema prefix: prescriber_dir
- indexes on (status), (npi), (dea_number), (practice_state)
- No money columns in this module, but any future additions MUST use Numeric, never Float.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PrescriberBase(DeclarativeBase):
    """Declarative base for prescriber-directory module."""


class Prescriber(PrescriberBase):
    __tablename__ = "prescribers"
    __table_args__ = (
        UniqueConstraint("npi", name="uq_prescriber_npi"),
        Index("idx_prescriber_status", "status"),
        Index("idx_prescriber_last_name_first", "last_name", "first_name"),
        Index("idx_prescriber_dea", "dea_number"),
        Index("idx_prescriber_taxonomy", "primary_taxonomy_code"),
        Index("idx_prescriber_state", "practice_state"),
        Index("idx_prescriber_specialty", "primary_specialty"),
        {"schema": "prescriber_dir"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    npi: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(5), nullable=False, default="1")

    # Individual name
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prefix: Mapped[str | None] = mapped_column(String(20), nullable=True)
    suffix: Mapped[str | None] = mapped_column(String(20), nullable=True)
    credential: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Organization
    organization_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    organization_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    authorized_official_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authorized_official_title: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Taxonomy / specialty
    primary_taxonomy_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    primary_taxonomy_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    taxonomy_codes: Mapped[Any] = mapped_column(JSON, nullable=True)

    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)

    # Practice address
    practice_address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    practice_address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    practice_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    practice_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    practice_zip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    practice_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    practice_fax: Mapped[str | None] = mapped_column(String(20), nullable=True)
    practice_latitude: Mapped[Any] = mapped_column(Numeric(10, 7), nullable=True)
    practice_longitude: Mapped[Any] = mapped_column(Numeric(10, 7), nullable=True)

    # Mailing address
    mailing_address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mailing_address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mailing_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mailing_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    mailing_zip: Mapped[str | None] = mapped_column(String(10), nullable=True)

    additional_locations: Mapped[Any] = mapped_column(JSON, nullable=True)

    # DEA — never logged (sensitive credential)
    dea_number: Mapped[str | None] = mapped_column(String(9), nullable=True)
    dea_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dea_expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dea_schedules: Mapped[Any] = mapped_column(JSON, nullable=True)
    dea_state: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # State license
    state_license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    state_license_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    state_license_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    state_license_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    additional_state_licenses: Mapped[Any] = mapped_column(JSON, nullable=True)

    # Medicare
    pecos_enrolled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    medicare_participation: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    medicare_opt_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Enumeration / dates
    enumeration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_update_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deactivation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deactivation_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reactivation_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Telehealth
    offers_telehealth: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telehealth_states: Mapped[Any] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    # Data source tracking
    nppes_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dea_last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    license_last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TaxonomyCode(PrescriberBase):
    __tablename__ = "taxonomy_codes"
    __table_args__ = {"schema": "prescriber_dir"}

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    classification: Mapped[str] = mapped_column(String(255), nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    grouping: Mapped[str | None] = mapped_column(String(255), nullable=True)
    simplified_specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_prescriber: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_pharmacy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hospital: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PracticeAffiliation(PrescriberBase):
    __tablename__ = "practice_affiliations"
    __table_args__ = (
        Index("idx_affil_prescriber", "prescriber_id"),
        Index("idx_affil_org", "organization_id"),
        {"schema": "prescriber_dir"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    prescriber_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_source: Mapped[str] = mapped_column(String(50), default="nppes", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CredentialAlert(PrescriberBase):
    __tablename__ = "credential_alerts"
    __table_args__ = (
        Index("idx_alert_prescriber", "prescriber_id"),
        Index("idx_alert_type", "alert_type"),
        {"schema": "prescriber_dir"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    prescriber_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DataRefreshLog(PrescriberBase):
    __tablename__ = "data_refresh_log"
    __table_args__ = {"schema": "prescriber_dir"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    refresh_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_deactivated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PrescriberPharmacyRelationship(PrescriberBase):
    __tablename__ = "prescriber_pharmacy_relationships"
    __table_args__ = (
        # CR-01 v2 HIPAA: unique constraint now includes tenant_id so volumes are
        # isolated per tenant. Old uq_ppr_npi_month (without tenant_id) would allow
        # Tenant A to increment Tenant B's row counts — data mixing.
        UniqueConstraint(
            "tenant_id", "prescriber_npi", "pharmacy_npi", "period_month",
            name="uq_ppr_tenant_npi_month",
        ),
        Index("idx_ppr_tenant_prescriber", "tenant_id", "prescriber_npi"),
        Index("idx_ppr_tenant_pharmacy", "tenant_id", "pharmacy_npi"),
        {"schema": "prescriber_dir"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # CR-01 v2 HIPAA: tenant_id added to isolate volume rows per tenant
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    prescriber_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    pharmacy_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    claim_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StatePrescribingRule(PrescriberBase):
    __tablename__ = "state_prescribing_rules"
    __table_args__ = (
        UniqueConstraint("state_code", "provider_type", name="uq_state_provider_rule"),
        Index("idx_state_rule_state", "state_code"),
        {"schema": "prescriber_dir"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(20), nullable=False)  # MD, DO, NP, PA, DDS, OD...
    can_prescribe_independently: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_collaborative_agreement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    controlled_substance_authority: Mapped[str] = mapped_column(String(20), default="full", nullable=False)  # none, limited, full
    schedule_restrictions: Mapped[Any] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
