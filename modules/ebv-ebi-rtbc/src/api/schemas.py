"""Pydantic request/response schemas for EBV/EBI/RTBC API endpoints.

All money fields as Decimal. Pydantic v2 models.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from shared.utils.money import ZERO


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


class EligibilityVerifyRequest(BaseModel):
    member_id: str
    as_of_date: date | None = None


class EligibilityBatchRequest(BaseModel):
    member_ids: list[str] = Field(..., min_length=1, max_length=1000)
    as_of_date: date | None = None


class CopayTierResponse(BaseModel):
    tier: str
    copay: Decimal
    coinsurance_pct: Decimal | None = None


class AccumulatorProgressResponse(BaseModel):
    limit: Decimal
    met: Decimal
    remaining: Decimal
    pct_met: Decimal


class EligibilityResponse(BaseModel):
    member_id: str
    status: str
    plan_id: str | None = None
    plan_name: str | None = None
    group_id: str | None = None
    group_name: str | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    copay_summary: list[CopayTierResponse] = Field(default_factory=list)
    benefit_phase: str | None = None
    deductible: AccumulatorProgressResponse | None = None
    oop: AccumulatorProgressResponse | None = None
    response_time_ms: int = 0


# ---------------------------------------------------------------------------
# Benefit Investigation
# ---------------------------------------------------------------------------


class BenefitInvestigateRequest(BaseModel):
    member_id: str
    drug_ndc: str = Field(..., min_length=11, max_length=11)
    plan_id: uuid.UUID | None = None


class QLInfoResponse(BaseModel):
    ql_type: str
    max_quantity: Decimal
    days_supply: int


class CoverageRequirementsResponse(BaseModel):
    pa_required: bool = False
    st_required: bool = False
    ql_info: QLInfoResponse | None = None


class CostBreakdownResponse(BaseModel):
    copay: Decimal = ZERO
    coinsurance: Decimal = ZERO
    deductible_applied: Decimal = ZERO
    total_member_cost: Decimal = ZERO


class AlternativeResponse(BaseModel):
    ndc: str
    name: str
    tier: str
    cost: Decimal
    savings: Decimal


class BenefitInvestigateResponse(BaseModel):
    member_id: str
    drug_ndc: str
    is_covered: bool
    formulary_status: str | None = None
    tier: str | None = None
    requirements: CoverageRequirementsResponse = Field(default_factory=CoverageRequirementsResponse)
    cost_breakdown: CostBreakdownResponse = Field(default_factory=CostBreakdownResponse)
    member_cost_estimate: Decimal = ZERO
    alternatives: list[AlternativeResponse] = Field(default_factory=list)
    specialty_pharmacy_required: bool = False
    site_of_care: str | None = None
    accumulator_status: str = "standard"


# ---------------------------------------------------------------------------
# RTPB (Real-Time Prescription Benefit)
# ---------------------------------------------------------------------------


class RTPBRequest(BaseModel):
    member_id: str
    drug_ndc: str = Field(..., min_length=11, max_length=11)
    prescriber_npi: str | None = None
    pharmacy_npi: str | None = None


class RTPBResponse(BaseModel):
    member_id: str
    drug_ndc: str
    patient_cost: Decimal = ZERO
    formulary_status: str | None = None
    tier: str | None = None
    restrictions: dict[str, Any] = Field(default_factory=dict)
    alternatives: list[AlternativeResponse] = Field(default_factory=list)
    pharmacy_options: list[dict[str, Any]] = Field(default_factory=list)
    v13_compliant: bool = True
    surescripts_transaction_id: str | None = None


# ---------------------------------------------------------------------------
# Member Tools
# ---------------------------------------------------------------------------


class CostEstimateRequest(BaseModel):
    member_id: str
    drug_ndc: str = Field(..., min_length=11, max_length=11)


class CostEstimateResponse(BaseModel):
    member_id: str
    drug_ndc: str
    estimated_cost: Decimal = ZERO
    tier: str | None = None
    formulary_status: str | None = None
    alternatives: list[AlternativeResponse] = Field(default_factory=list)


class PharmacyCompareRequest(BaseModel):
    member_id: str
    drug_ndc: str = Field(..., min_length=11, max_length=11)
    lat: Decimal
    lng: Decimal


class PharmacyOptionResponse(BaseModel):
    npi: str
    name: str
    distance_mi: Decimal
    cost: Decimal
    in_network: bool
    preferred: bool


class PharmacyCompareResponse(BaseModel):
    member_id: str
    drug_ndc: str
    pharmacies: list[PharmacyOptionResponse] = Field(default_factory=list)


class BenefitProgressResponse(BaseModel):
    member_id: str
    deductible: AccumulatorProgressResponse | None = None
    oop: AccumulatorProgressResponse | None = None
    benefit_year_start: date | None = None
    benefit_year_end: date | None = None
    projected_deductible_met_date: date | None = None
    projected_oop_met_date: date | None = None


class DigitalIDCardResponse(BaseModel):
    member_id: str
    member_name: str
    group: str
    bin: str
    pcn: str
    rxbin: str
    copays: dict[str, Decimal] = Field(default_factory=dict)
    pharmacy_help_phone: str
    version: int = 1


# ---------------------------------------------------------------------------
# Hub API
# ---------------------------------------------------------------------------


class HubBVRequest(BaseModel):
    hub_partner_id: str
    member_id: str
    as_of_date: date | None = None


class HubBIRequest(BaseModel):
    hub_partner_id: str
    member_id: str
    drug_ndc: str = Field(..., min_length=11, max_length=11)


class HubStatusUpdateRequest(BaseModel):
    hub_partner_id: str
    member_id: str
    status_type: str
    status_data: dict[str, Any] = Field(default_factory=dict)


class HubResponse(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
