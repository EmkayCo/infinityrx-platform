"""Pydantic schemas for market access intelligence endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator


class CoverageLandscapeResponse(BaseModel):
    """Which plans cover this drug, at what tier."""

    ndc: str
    total_plans_checked: int
    covered_plans: int
    coverage_pct: Decimal
    tier_breakdown: dict[str, int]
    pa_required_pct: Decimal
    formularies: list[dict[str, Any]]

    @field_validator("coverage_pct", "pa_required_pct", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class CompetitivePositioningResponse(BaseModel):
    """Drug placement vs competitors in same therapeutic class."""

    gpi: str
    therapeutic_class: str | None
    drugs_in_class: list[dict[str, Any]]
    tier_distribution: dict[str, dict[str, int]]
    pa_burden_comparison: dict[str, Decimal]


class PAARequirementResponse(BaseModel):
    """Which plans require PA and what criteria."""

    ndc: str
    plans_requiring_pa: int
    pa_criteria_summary: list[dict[str, Any]]


class PayerMixResponse(BaseModel):
    """Payer mix analysis: % commercial vs Medicare vs Medicaid."""

    ndc: str
    commercial_pct: Decimal
    medicare_pct: Decimal
    medicaid_pct: Decimal
    other_pct: Decimal
    total_covered_lives: int

    @field_validator("commercial_pct", "medicare_pct", "medicaid_pct", "other_pct", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class AccumulatorExposureResponse(BaseModel):
    """Accumulator/maximizer exposure for a drug."""

    ndc: str
    commercially_insured_patients: int
    on_accumulator_plan_pct: Decimal
    on_maximizer_plan_pct: Decimal

    @field_validator("on_accumulator_plan_pct", "on_maximizer_plan_pct", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class WhatIfRequest(BaseModel):
    """Benefit design what-if simulation request."""

    proposed_benefit_config: dict[str, Any]
    sample_claims_count: int = 1000
    include_drug_level_detail: bool = False


class WhatIfResponse(BaseModel):
    """Benefit design what-if simulation results."""

    plan_id: UUID
    scenario_name: str | None
    current_total_cost: Decimal
    proposed_total_cost: Decimal
    cost_delta: Decimal
    cost_delta_pct: Decimal
    member_oop_avg_current: Decimal
    member_oop_avg_proposed: Decimal
    members_affected: int
    drug_level_impacts: list[dict[str, Any]]

    @field_validator(
        "current_total_cost", "proposed_total_cost", "cost_delta",
        "cost_delta_pct", "member_oop_avg_current", "member_oop_avg_proposed",
        mode="before",
    )
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class BenefitDesignScenarioCreate(BaseModel):
    name: str
    scenario_config: dict[str, Any]


class BenefitDesignScenarioResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    plan_id: UUID
    name: str
    scenario_config: dict[str, Any]
    results: dict[str, Any] | None
    total_plan_cost_current: Decimal | None
    total_plan_cost_proposed: Decimal | None
    member_oop_avg_current: Decimal | None
    member_oop_avg_proposed: Decimal | None
    members_affected: int

    model_config = {"from_attributes": True}
