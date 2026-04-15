"""Pydantic schemas for plan hierarchy endpoints."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    tin: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    effective_date: date
    termination_date: date | None = None
    metadata_: dict[str, Any] | None = Field(None, alias="metadata")

    model_config = {"populate_by_name": True}


class OrganizationUpdate(BaseModel):
    name: str | None = None
    tin: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    status: str | None = None
    metadata_: dict[str, Any] | None = Field(None, alias="metadata")

    model_config = {"populate_by_name": True}


class OrganizationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    tin: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    effective_date: date
    termination_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


class GroupCreate(BaseModel):
    organization_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    group_id_external: str | None = None
    bin_number: str | None = None
    pcn: str | None = None
    billing_entity_ref: str | None = None
    effective_date: date
    termination_date: date | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    group_id_external: str | None = None
    bin_number: str | None = None
    pcn: str | None = None
    billing_entity_ref: str | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    status: str | None = None


class GroupResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    organization_id: UUID
    name: str
    group_id_external: str | None
    bin_number: str | None
    pcn: str | None
    effective_date: date
    termination_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class BenefitConfig(BaseModel):
    """Benefit configuration for a plan."""

    copay_structure: str = "flat"  # flat | percentage | tiered | step | custom
    copay_tiers: dict[str, Any] | None = None
    deductible_applies_to: str = "all"  # all | brand | specialty
    deductible_type: str = "individual"  # individual | family | both
    coinsurance_pct: Decimal | None = None
    benefit_phases: list[dict[str, Any]] | None = None
    day_supply_rules: dict[str, Any] | None = None
    annual_max_amount: Decimal | None = None
    lifetime_max_amount: Decimal | None = None

    @field_validator("coinsurance_pct", "annual_max_amount", "lifetime_max_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        if v is None:
            return None
        return Decimal(str(v))


class PlanCreate(BaseModel):
    group_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    plan_code: str | None = None
    program_type_id: UUID | None = None
    pricing_model_id: UUID | None = None
    formulary_id: UUID | None = None
    network_id: UUID | None = None
    effective_date: date
    termination_date: date | None = None
    benefit_config: dict[str, Any] | None = None
    glp1_config: dict[str, Any] | None = None
    cash_pay_comparison_enabled: bool = False
    accumulator_config: dict[str, Any] | None = None
    deductible_individual: Decimal | None = None
    deductible_family: Decimal | None = None
    oop_max_individual: Decimal | None = None
    oop_max_family: Decimal | None = None

    @field_validator(
        "deductible_individual", "deductible_family", "oop_max_individual", "oop_max_family",
        mode="before",
    )
    @classmethod
    def coerce_decimal(cls, v):
        if v is None:
            return None
        return Decimal(str(v))


class PlanUpdate(BaseModel):
    name: str | None = None
    plan_code: str | None = None
    program_type_id: UUID | None = None
    pricing_model_id: UUID | None = None
    formulary_id: UUID | None = None
    network_id: UUID | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    status: str | None = None
    benefit_config: dict[str, Any] | None = None
    glp1_config: dict[str, Any] | None = None
    cash_pay_comparison_enabled: bool | None = None
    accumulator_config: dict[str, Any] | None = None
    deductible_individual: Decimal | None = None
    deductible_family: Decimal | None = None
    oop_max_individual: Decimal | None = None
    oop_max_family: Decimal | None = None

    @field_validator(
        "deductible_individual", "deductible_family", "oop_max_individual", "oop_max_family",
        mode="before",
    )
    @classmethod
    def coerce_decimal(cls, v):
        if v is None:
            return None
        return Decimal(str(v))


class PlanResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    group_id: UUID
    name: str
    plan_code: str | None
    program_type_id: UUID | None
    pricing_model_id: UUID | None
    formulary_id: UUID | None
    network_id: UUID | None
    effective_date: date
    termination_date: date | None
    status: str
    benefit_config: dict[str, Any] | None
    glp1_config: dict[str, Any] | None
    cash_pay_comparison_enabled: bool
    deductible_individual: Decimal | None
    deductible_family: Decimal | None
    oop_max_individual: Decimal | None
    oop_max_family: Decimal | None
    sandbox_version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanResolveResponse(BaseModel):
    """Resolved effective plan config with inheritance applied."""

    plan_id: UUID
    tenant_id: UUID
    resolved_at: datetime
    effective_config: dict[str, Any]
    inheritance_chain: list[dict[str, Any]]


class PlanCloneRequest(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=255)
    target_group_id: UUID | None = None
    copy_formulary: bool = True
    copy_network: bool = True


class PlanPromoteRequest(BaseModel):
    notes: str | None = None


class PlanRollbackRequest(BaseModel):
    target_version: int
    reason: str | None = None


# ---------------------------------------------------------------------------
# SubGroup
# ---------------------------------------------------------------------------


class SubGroupCreate(BaseModel):
    plan_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    override_config: dict[str, Any] | None = None
    effective_date: date
    termination_date: date | None = None


class SubGroupUpdate(BaseModel):
    name: str | None = None
    override_config: dict[str, Any] | None = None
    effective_date: date | None = None
    termination_date: date | None = None


class SubGroupResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    plan_id: UUID
    name: str
    override_config: dict[str, Any] | None
    effective_date: date
    termination_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Bulk import/export
# ---------------------------------------------------------------------------


class BulkImportResponse(BaseModel):
    total_rows: int
    created: int
    updated: int
    errors: list[dict[str, Any]]


class ProgramTypeCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    default_rules: dict[str, Any] | None = None


class ProgramTypeResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    description: str | None
    default_rules: dict[str, Any] | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
