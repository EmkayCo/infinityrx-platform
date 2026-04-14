"""SQLAlchemy models for the drug-database module.

All money columns: Numeric(n,6) for per-unit prices, Numeric(n,2) for package prices.
No Float anywhere.
Every tenant-scoped table inherits TenantScopedMixin.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class DrugBase(DeclarativeBase):
    """Declarative base for drug-database module."""


SCHEMA = "drug_db"


class DrugProduct(DrugBase):
    __tablename__ = "drug_products"
    __table_args__ = (
        Index("idx_drug_ndc", "ndc_11"),
        Index("idx_drug_name", "drug_name_display"),
        Index("idx_drug_gpi", "gpi_code"),
        Index("idx_drug_labeler", "labeler_code"),
        Index("idx_drug_type", "drug_type"),
        Index("idx_drug_nonproprietary", "nonproprietary_name"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    ndc_11: Mapped[str] = mapped_column(String(11), nullable=False, unique=True)
    ndc_formatted: Mapped[str | None] = mapped_column(String(13), nullable=True)
    labeler_code: Mapped[str] = mapped_column(String(5), nullable=False)
    product_code: Mapped[str] = mapped_column(String(4), nullable=False)
    package_code: Mapped[str] = mapped_column(String(2), nullable=False)

    proprietary_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nonproprietary_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    drug_name_display: Mapped[str] = mapped_column(String(500), nullable=False)

    dea_schedule: Mapped[str | None] = mapped_column(String(5), nullable=True)
    otc_rx: Mapped[str | None] = mapped_column(String(3), nullable=True)
    drug_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    dosage_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    route_of_administration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(255), nullable=True)
    strength_number: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    strength_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    package_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    package_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    package_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    package_size_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_dose: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    labeler_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    marketing_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    marketing_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    marketing_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    gpi_code: Mapped[str | None] = mapped_column(String(14), nullable=True)
    gpi_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ahfs_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ahfs_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    usp_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    atc_code: Mapped[str | None] = mapped_column(String(7), nullable=True)
    atc_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    therapeutic_class_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    therapeutic_class_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    therapeutic_class_3: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_specialty: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    specialty_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_limited_distribution: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_biosimilar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reference_biologic_ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)

    is_glp1: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    glp1_indication: Mapped[str | None] = mapped_column(String(100), nullable=True)

    fdb_product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fda_application_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class DrugPricing(DrugBase):
    __tablename__ = "drug_pricing"
    __table_args__ = (
        UniqueConstraint("ndc_11", "price_type", "effective_date", "data_source", name="uq_pricing_ndc_type_date_src"),
        Index("idx_pricing_ndc_type", "ndc_11", "price_type", "effective_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ndc_11: Mapped[str] = mapped_column(String(11), nullable=False)

    price_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    unit_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    package_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class DrugPricingHistory(DrugBase):
    __tablename__ = "drug_pricing_history"
    __table_args__ = (
        Index("idx_pricing_history_ndc", "ndc_11", "effective_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ndc_11: Mapped[str] = mapped_column(String(11), nullable=False)
    price_type: Mapped[str] = mapped_column(String(20), nullable=False)

    old_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    new_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    change_percentage: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class DrugInteraction(DrugBase):
    __tablename__ = "drug_interactions"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    drug_1_identifier: Mapped[str] = mapped_column(String(50), nullable=False)
    drug_1_identifier_type: Mapped[str] = mapped_column(String(20), nullable=False)
    drug_1_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    drug_2_identifier: Mapped[str] = mapped_column(String(50), nullable=False)
    drug_2_identifier_type: Mapped[str] = mapped_column(String(20), nullable=False)
    drug_2_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    interaction_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_significance: Mapped[str | None] = mapped_column(Text, nullable=True)
    management_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="fdb")
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class TherapeuticEquivalence(DrugBase):
    __tablename__ = "therapeutic_equivalence"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    brand_ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generic_ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    generic_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    te_code: Mapped[str] = mapped_column(String(5), nullable=False)
    is_therapeutically_equivalent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    application_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="fda_orange_book")
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class TenantPricingOverride(DrugBase):
    __tablename__ = "tenant_pricing_overrides"
    __table_args__ = (
        UniqueConstraint("tenant_id", "ndc_11", "price_type", "effective_date", name="uq_override_tenant_ndc_type_date"),
        Index("idx_override_tenant_ndc", "tenant_id", "ndc_11"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    ndc_11: Mapped[str] = mapped_column(String(11), nullable=False)

    price_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    unit_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="tenant_mac")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class DataRefreshLog(DrugBase):
    __tablename__ = "data_refresh_log"
    __table_args__ = ({"schema": SCHEMA},)

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
    price_changes_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class DrugShortage(DrugBase):
    __tablename__ = "drug_shortages"
    __table_args__ = (
        Index("idx_shortage_ndc", "ndc_11"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ndc_11: Mapped[str | None] = mapped_column(String(11), nullable=True)
    ingredient_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    shortage_status: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_resolution_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="fda_shortage")
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class RemsProgram(DrugBase):
    __tablename__ = "rems_programs"
    __table_args__ = (
        Index("idx_rems_ndc", "ndc_11"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ndc_11: Mapped[str | None] = mapped_column(String(11), nullable=True)
    ingredient_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    rems_program_name: Mapped[str] = mapped_column(String(500), nullable=False)
    rems_status: Mapped[str] = mapped_column(String(50), nullable=False)

    certified_pharmacy_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    certified_prescriber_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    patient_registry_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lab_testing_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lab_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    restricted_distribution: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    patient_agreement_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="fda_rems")
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
