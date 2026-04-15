"""Plan Design ORM models — all tenant-scoped tables.

Data model covers PRD §11:
  organizations, groups, plans, subgroups,
  formularies, formulary_drugs, formulary_versions,
  networks, network_pharmacies, network_adequacy, awp_applications,
  plan_templates, pricing_models, plan_pricing,
  benefit_design_scenarios, pt_committee_meetings,
  fb_v60_publications, state_formulary_laws, program_types.

Financial-precision rule: all money columns use sa.Numeric(x,2) or Numeric(x,4).
No Float columns anywhere.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "plan_design"

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class PlanDesignBase(DeclarativeBase):
    """Plan Design module declarative base."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


def _ts_now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------------------------------------------------------------------------
# Program Types (config rows, not enum)
# ---------------------------------------------------------------------------


class ProgramType(PlanDesignBase, TenantScopedMixin):
    """Fully configurable program types — adding a new type is a config row."""

    __tablename__ = "program_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_program_types_tenant_code"),
        Index("ix_program_types_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_rules: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Hierarchy: Organization → Group → Plan → SubGroup
# ---------------------------------------------------------------------------


class Organization(PlanDesignBase, TenantScopedMixin):
    """Top of hierarchy. Maps to a carrier/manufacturer/health plan entity."""

    __tablename__ = "organizations"
    __table_args__ = (
        Index("ix_organizations_tenant_id", "tenant_id"),
        Index("ix_organizations_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tin: Mapped[str | None] = mapped_column(String(20))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class Group(PlanDesignBase, TenantScopedMixin):
    """Group within an organization — BIN/PCN assignment level."""

    __tablename__ = "groups"
    __table_args__ = (
        Index("ix_groups_tenant_org", "tenant_id", "organization_id"),
        Index("ix_groups_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.organizations.id"),
        nullable=False,
    )
    group_id_external: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bin_number: Mapped[str | None] = mapped_column(String(6))
    pcn: Mapped[str | None] = mapped_column(String(20))
    billing_entity_ref: Mapped[str | None] = mapped_column(String(255))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    inherited_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class PricingModelConfig(PlanDesignBase, TenantScopedMixin):
    """Registry of pricing calculator configurations per tenant.

    Adding a new pricing model is a config row + one calculator class.
    """

    __tablename__ = "pricing_models"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_pricing_models_tenant_code"),
        Index("ix_pricing_models_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    calculator_class: Mapped[str] = mapped_column(String(255), nullable=False)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class Plan(PlanDesignBase, TenantScopedMixin):
    """A benefit plan — the core adjudication configuration unit."""

    __tablename__ = "plans"
    __table_args__ = (
        Index("ix_plans_tenant_group", "tenant_id", "group_id"),
        Index("ix_plans_tenant_status", "tenant_id", "status"),
        CheckConstraint(
            "status IN ('draft', 'sandbox', 'test', 'active', 'terminated')",
            name="plans_status_valid",
        ),
        CheckConstraint(
            "cash_pay_comparison_enabled IN (true, false)",
            name="plans_cash_pay_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    group_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.groups.id"),
        nullable=False,
    )
    program_type_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.program_types.id"),
    )
    pricing_model_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.pricing_models.id"),
    )
    formulary_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    network_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_code: Mapped[str | None] = mapped_column(String(50))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")

    # Benefit configuration (JSON for flexibility)
    benefit_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # GLP-1 indication-based coverage (JSONB per drug)
    glp1_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Cash-pay comparison at adjudication
    cash_pay_comparison_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Accumulator rules
    accumulator_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Sandbox promotion tracking
    promoted_from_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    sandbox_version: Mapped[int] = mapped_column(Integer, server_default="1")

    # Deductible (Decimal — ROUND_HALF_UP)
    deductible_individual: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    deductible_family: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    oop_max_individual: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    oop_max_family: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class SubGroup(PlanDesignBase, TenantScopedMixin):
    """Optional sub-group that overrides plan-level settings for a member subset."""

    __tablename__ = "subgroups"
    __table_args__ = (
        Index("ix_subgroups_tenant_plan", "tenant_id", "plan_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.plans.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    override_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Plan Pricing (per-plan, per-network-tier pricing overrides)
# ---------------------------------------------------------------------------


class PlanPricing(PlanDesignBase, TenantScopedMixin):
    """Associates a pricing model with a plan (optionally per network tier)."""

    __tablename__ = "plan_pricing"
    __table_args__ = (
        Index("ix_plan_pricing_tenant_plan", "tenant_id", "plan_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.plans.id"),
        nullable=False,
    )
    pricing_model_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.pricing_models.id"),
        nullable=False,
    )
    network_tier: Mapped[str | None] = mapped_column(String(50))
    drug_tier: Mapped[str | None] = mapped_column(String(50))
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Formulary
# ---------------------------------------------------------------------------


class Formulary(PlanDesignBase, TenantScopedMixin):
    """A drug formulary — unlimited per tenant, effective-dated, versioned."""

    __tablename__ = "formularies"
    __table_args__ = (
        Index("ix_formularies_tenant_id", "tenant_id"),
        Index("ix_formularies_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    current_version: Mapped[int] = mapped_column(Integer, server_default="1")
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    tier_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_open_formulary: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class FormularyVersion(PlanDesignBase, TenantScopedMixin):
    """Immutable snapshot of a formulary at a point in time — enables rollback."""

    __tablename__ = "formulary_versions"
    __table_args__ = (
        Index("ix_formulary_versions_formulary", "tenant_id", "formulary_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    formulary_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.formularies.id"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts_now()


class FormularyDrug(PlanDesignBase, TenantScopedMixin):
    """Drug tier assignment within a formulary.

    Covers: NDC/GPI assignment, PA/ST/QL flags, biosimilar mapping,
    indication-based coverage (GLP-1), IRA negotiated price flag.
    """

    __tablename__ = "formulary_drugs"
    __table_args__ = (
        Index("ix_formulary_drugs_formulary_ndc", "formulary_id", "ndc"),
        Index("ix_formulary_drugs_tenant", "tenant_id", "formulary_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    formulary_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.formularies.id"),
        nullable=False,
    )
    ndc: Mapped[str | None] = mapped_column(String(11))
    gpi_range_start: Mapped[str | None] = mapped_column(String(14))
    gpi_range_end: Mapped[str | None] = mapped_column(String(14))
    drug_name: Mapped[str | None] = mapped_column(String(255))
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    therapeutic_class: Mapped[str | None] = mapped_column(String(100))
    pa_required: Mapped[bool] = mapped_column(Boolean, server_default="false")
    step_therapy_required: Mapped[bool] = mapped_column(Boolean, server_default="false")
    quantity_limit: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_specialty: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Biosimilar mapping
    biosimilar_reference_ndc: Mapped[str | None] = mapped_column(String(11))
    is_biosimilar: Mapped[bool] = mapped_column(Boolean, server_default="false")
    auto_substitution_allowed: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # GLP-1 indication-based coverage (JSONB: {"diabetes": "covered", "obesity": "not_covered"})
    indication_coverage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # IRA negotiated drug
    is_ira_negotiated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    mfp_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class StateFormularyLaw(PlanDesignBase):
    """State substitution/biosimilar law table — global reference, not tenant-scoped."""

    __tablename__ = "state_formulary_laws"
    __table_args__ = (
        UniqueConstraint("state_code", "law_type", name="uq_state_formulary_laws_state_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    law_type: Mapped[str] = mapped_column(String(100), nullable=False)
    allows_biosimilar_substitution: Mapped[bool] = mapped_column(Boolean, server_default="false")
    requires_prescriber_consent: Mapped[bool] = mapped_column(Boolean, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


class Network(PlanDesignBase, TenantScopedMixin):
    """Pharmacy network configuration for a plan."""

    __tablename__ = "networks"
    __table_args__ = (
        Index("ix_networks_tenant_id", "tenant_id"),
        Index("ix_networks_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    tier_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    any_willing_pharmacy_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class NetworkPharmacy(PlanDesignBase, TenantScopedMixin):
    """A pharmacy assignment within a network.

    Covers: tier, pharmacy type, specialty accreditation, site-of-care,
    white/brown/clear bagging, LDD tracking.
    """

    __tablename__ = "network_pharmacies"
    __table_args__ = (
        Index("ix_network_pharmacies_network", "tenant_id", "network_id"),
        Index("ix_network_pharmacies_npi", "npi"),
        CheckConstraint(
            "pharmacy_type IN ('retail', 'mail_order', 'specialty', '340b', 'ltc', 'home_infusion', 'clinic')",
            name="network_pharmacies_type_valid",
        ),
        CheckConstraint(
            "specialty_accreditation IN ('none', 'urac', 'achc', 'both') OR specialty_accreditation IS NULL",
            name="network_pharmacies_accred_valid",
        ),
        CheckConstraint(
            "bagging_model IN ('white', 'brown', 'clear', 'none') OR bagging_model IS NULL",
            name="network_pharmacies_bagging_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    network_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.networks.id"),
        nullable=False,
    )
    npi: Mapped[str] = mapped_column(String(10), nullable=False)
    pharmacy_name: Mapped[str | None] = mapped_column(String(255))
    pharmacy_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="retail")
    network_tier: Mapped[str | None] = mapped_column(String(50))
    specialty_accreditation: Mapped[str | None] = mapped_column(String(20))
    site_of_care_type: Mapped[str | None] = mapped_column(String(50))
    bagging_model: Mapped[str | None] = mapped_column(String(20))
    is_ldd: Mapped[bool] = mapped_column(Boolean, server_default="false")
    ldd_drugs: Mapped[list[str] | None] = mapped_column(JSONB)
    address_line1: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class NetworkAdequacy(PlanDesignBase, TenantScopedMixin):
    """Network adequacy report results by county/ZIP."""

    __tablename__ = "network_adequacy"
    __table_args__ = (
        Index("ix_network_adequacy_network", "tenant_id", "network_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    network_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.networks.id"),
        nullable=False,
    )
    county_fips: Mapped[str | None] = mapped_column(String(5))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    member_count: Mapped[int] = mapped_column(Integer, server_default="0")
    nearest_pharmacy_miles: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    nearest_pharmacy_minutes: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    is_adequate: Mapped[bool] = mapped_column(Boolean, server_default="true")
    gap_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    calculated_at: Mapped[datetime] = _ts_now()


class AWPApplication(PlanDesignBase, TenantScopedMixin):
    """Any Willing Pharmacy application queue (CAA 2026 — effective 2028)."""

    __tablename__ = "awp_applications"
    __table_args__ = (
        Index("ix_awp_applications_network", "tenant_id", "network_id"),
        Index("ix_awp_applications_tenant_status", "tenant_id", "status"),
        CheckConstraint(
            "status IN ('pending', 'under_review', 'approved', 'denied', 'withdrawn')",
            name="awp_applications_status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    network_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.networks.id"),
        nullable=False,
    )
    pharmacy_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    pharmacy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    pharmacy_address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    application_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    decision_notes: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Plan Templates
# ---------------------------------------------------------------------------


class PlanTemplate(PlanDesignBase, TenantScopedMixin):
    """Pre-configured starting points per program type."""

    __tablename__ = "plan_templates"
    __table_args__ = (
        Index("ix_plan_templates_tenant_type", "tenant_id", "program_type_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    program_type_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.program_types.id"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    template_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Benefit Design Scenarios (what-if simulator)
# ---------------------------------------------------------------------------


class BenefitDesignScenario(PlanDesignBase, TenantScopedMixin):
    """Saved what-if scenario for benefit design modeling."""

    __tablename__ = "benefit_design_scenarios"
    __table_args__ = (
        Index("ix_benefit_design_scenarios_plan", "tenant_id", "plan_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.plans.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    total_plan_cost_current: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total_plan_cost_proposed: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    member_oop_avg_current: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    member_oop_avg_proposed: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    members_affected: Mapped[int] = mapped_column(Integer, server_default="0")
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# P&T Committee
# ---------------------------------------------------------------------------


class PTCommitteeMeeting(PlanDesignBase, TenantScopedMixin):
    """Pharmacy & Therapeutics committee meeting record."""

    __tablename__ = "pt_committee_meetings"
    __table_args__ = (
        Index("ix_pt_meetings_tenant_formulary", "tenant_id", "formulary_id"),
        CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'completed', 'cancelled')",
            name="pt_meetings_status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    formulary_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.formularies.id"),
        nullable=False,
    )
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="scheduled")
    agenda: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    drugs_under_review: Mapped[list[str] | None] = mapped_column(JSONB)
    votes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    decisions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# F&B v60 Publications
# ---------------------------------------------------------------------------


class FBv60Publication(PlanDesignBase, TenantScopedMixin):
    """NCPDP Formulary & Benefit Version 60 file publication record."""

    __tablename__ = "fb_v60_publications"
    __table_args__ = (
        Index("ix_fb_v60_tenant_formulary", "tenant_id", "formulary_id"),
        CheckConstraint(
            "status IN ('pending', 'generated', 'published', 'failed')",
            name="fb_v60_status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    formulary_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.formularies.id"),
        nullable=False,
    )
    formulary_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    file_content: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()


__all__ = [
    "PlanDesignBase",
    "ProgramType",
    "Organization",
    "Group",
    "PricingModelConfig",
    "Plan",
    "SubGroup",
    "PlanPricing",
    "Formulary",
    "FormularyVersion",
    "FormularyDrug",
    "StateFormularyLaw",
    "Network",
    "NetworkPharmacy",
    "NetworkAdequacy",
    "AWPApplication",
    "PlanTemplate",
    "BenefitDesignScenario",
    "PTCommitteeMeeting",
    "FBv60Publication",
]
