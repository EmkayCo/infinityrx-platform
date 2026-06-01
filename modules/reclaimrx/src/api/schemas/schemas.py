"""Pydantic v2 request/response schemas for ReclaimRx API.

All monetary amounts use Decimal. No floats.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# -- Claim Evaluation ---------------------------------------------------------

class ClaimEvaluateRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    claim_id: str | None = None
    auth_number: str
    date_of_service: date
    pharmacy_npi: str = Field(..., min_length=10, max_length=10)
    pharmacy_name: str | None = None
    prescriber_npi: str | None = Field(None, min_length=10, max_length=10)
    member_id: str | None = None
    ndc: str | None = Field(None, min_length=11, max_length=11)
    drug_name: str | None = None
    quantity: Decimal = Field(..., gt=Decimal("0"))
    days_supply: int = Field(..., gt=0)
    billed_amount: Decimal = Field(..., ge=Decimal("0"))
    paid_amount: Decimal = Field(..., ge=Decimal("0"))
    wac_per_unit: Decimal | None = Field(None, ge=Decimal("0"))
    awp_per_unit: Decimal | None = Field(None, ge=Decimal("0"))
    nq: Decimal | None = Field(None, ge=Decimal("0"))
    dv: Decimal | None = Field(None, ge=Decimal("0"))
    program_type: str
    client_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("billed_amount", "paid_amount", mode="before")
    @classmethod
    def no_float_money(cls, v: Any) -> Any:
        if isinstance(v, float):
            return Decimal(str(v))
        return v


class RuleResultSchema(BaseModel):
    flagged: bool
    rule_code: str
    action: str | None
    confidence_tier: str | None
    risk_score: int
    evidence: dict[str, Any]
    severity: str | None


class ClaimEvaluateResponse(BaseModel):
    claim_id: str | None
    auth_number: str
    overall_risk_score: int
    rules_evaluated: int
    flags: list[RuleResultSchema]
    action_required: str | None
    flagged_claim_ids: list[str] = Field(default_factory=list)


# -- Detection Rules ----------------------------------------------------------

class DetectionRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None
    rule_code: str
    name: str
    description: str
    category: str
    client_types: list[str]
    detection_mode: str
    rule_type: str
    default_action: str
    is_system: bool
    is_active: bool
    version: int
    created_at: datetime


# -- Flagged Claims -----------------------------------------------------------

class FlaggedClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    claim_id: str | None
    auth_number: str
    date_of_service: date
    pharmacy_npi: str
    pharmacy_name: str | None
    prescriber_npi: str | None
    member_id: str | None
    ndc: str | None
    drug_name: str | None
    billed_amount: Decimal | None
    paid_amount: Decimal | None
    variance_amount: Decimal | None
    rule_code: str
    rule_name: str
    detection_mode: str
    risk_score: int
    confidence_tier: str
    severity: str
    evidence: dict[str, Any]
    action_taken: str | None
    investigation_status: str
    investigation_id: str | None
    created_at: datetime


class FlaggedClaimUpdate(BaseModel):
    investigation_status: str | None = None
    assigned_to: UUID | None = None
    review_notes: str | None = None
    resolution: str | None = None


# -- Investigations -----------------------------------------------------------

class InvestigationCreate(BaseModel):
    subject_type: str
    subject_entity_id: str
    subject_name: str | None = None
    investigation_type: str
    title: str
    priority: str = "medium"
    date_range_start: date | None = None
    date_range_end: date | None = None
    client_id: UUID | None = None
    program_id: UUID | None = None


class InvestigationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    investigation_number: str
    title: str
    subject_type: str
    subject_entity_id: str
    subject_name: str | None
    investigation_type: str
    date_range_start: date | None
    date_range_end: date | None
    flagged_claim_count: int
    total_flagged_amount: Decimal
    recovery_estimate_conservative: Decimal
    recovery_estimate_mid: Decimal
    recovery_estimate_aggressive: Decimal
    actual_recovered: Decimal
    status: str
    priority: str
    assigned_to: str | None
    opened_at: datetime
    response_due_date: date | None
    resolved_at: datetime | None
    resolution_type: str | None
    litigation_hold: bool
    created_at: datetime
    updated_at: datetime


class InvestigationUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to: UUID | None = None
    response_due_date: date | None = None
    resolution_type: str | None = None
    resolution_notes: str | None = None
    notes: str | None = None


# -- Recoveries ---------------------------------------------------------------

class RecoveryCreate(BaseModel):
    recovery_method: str
    amount: Decimal = Field(..., gt=Decimal("0"))
    confidence_tier: str
    methodology_tag: str

    @field_validator("amount", mode="before")
    @classmethod
    def no_float_amount(cls, v: Any) -> Any:
        if isinstance(v, float):
            return Decimal(str(v))
        return v


class RecoveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    tenant_id: str
    recovery_method: str
    amount: Decimal
    confidence_tier: str
    methodology_tag: str
    status: str
    demand_date: date | None
    response_date: date | None
    collection_date: date | None
    created_at: datetime


# -- Activities ---------------------------------------------------------------

class ActivityCreate(BaseModel):
    activity_type: str
    description: str
    file_id: str | None = None


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    tenant_id: str
    activity_type: str
    description: str
    performed_by: str | None
    file_id: str | None
    created_at: datetime


# -- Payment Holds ------------------------------------------------------------

class PaymentHoldCreate(BaseModel):
    entity_type: str
    entity_id: str
    entity_name: str | None = None
    investigation_id: str | None = None
    hold_scope: str = "all"
    rule_filter: dict[str, Any] | None = None
    amount_threshold: Decimal | None = None
    expires_at: datetime | None = None


class PaymentHoldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    entity_type: str
    entity_id: str
    entity_name: str | None
    investigation_id: str | None
    hold_scope: str
    placed_by: str
    placed_at: datetime
    expires_at: datetime | None
    is_active: bool
    released_by: str | None
    released_at: datetime | None
    release_reason: str | None


class PaymentHoldRelease(BaseModel):
    reason: str = Field(..., min_length=1)


# -- Tips ---------------------------------------------------------------------

class TipCreate(BaseModel):
    tip_type: str
    subject_description: str = Field(..., min_length=1)
    detail_text: str = Field(..., min_length=1)
    reporter_name: str | None = None
    reporter_contact: str | None = None
    is_anonymous: bool = True


class TipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    tip_type: str
    subject_description: str
    detail_text: str
    is_anonymous: bool
    status: str
    investigation_id: str | None
    created_at: datetime


# -- Entity Profiles ----------------------------------------------------------

class PharmacyProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    pharmacy_npi: str
    pharmacy_name: str | None
    avg_daily_claims: Decimal | None
    avg_claim_amount: Decimal | None
    reversal_rate: Decimal | None
    composite_risk_score: int
    risk_trend: str | None
    is_flagged: bool
    flag_count: int
    confirmed_fraud_count: int
    last_calculated_at: datetime | None


class PrescriberProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    prescriber_npi: str
    prescriber_name: str | None
    avg_daily_scripts: Decimal | None
    controlled_substance_rate: Decimal | None
    composite_risk_score: int
    risk_trend: str | None
    last_calculated_at: datetime | None


class MemberProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    member_id: str
    fill_frequency_days: Decimal | None
    pharmacy_shopping_score: int | None
    is_accumulator_plan: bool
    composite_risk_score: int
    last_calculated_at: datetime | None


class AccumulatorDetectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    member_id: str
    plan_bin: str | None
    plan_pcn: str | None
    plan_group: str | None
    detection_method: str
    detection_fill_number: int | None
    detection_confidence: Decimal | None
    program_type: str | None
    copay_assistance_amount: Decimal | None
    amount_not_applied: Decimal | None
    projected_annual_impact: Decimal | None
    created_at: datetime


# -- Detection Console (Foundation Slice) -------------------------------------


class AnomalyRead(BaseModel):
    """Read schema for reclaimrx.anomalies rows (Foundation slice).

    All Decimal amounts serialized as str to preserve precision.
    No floats.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    finding_code: str
    finding_summary: str
    severity: str
    confidence: str
    status: str
    entity_type: str
    pharmacy_npi: str | None
    pharmacy_name: str | None
    prescriber_npi: str | None
    prescriber_name: str | None
    ndc: str | None
    amount_paid: str | None
    amount_billed: str | None
    recovery_amount: str | None
    date_of_service: date | None
    data_source_run_id: str | None
    created_at: datetime


class RuleBreakdownItem(BaseModel):
    finding_code: str
    severity: str
    count: int


class DetectionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_label: str
    status: str
    data_source: str
    source_filename: str | None
    record_count: int
    anomaly_count: int
    period_start: date | None
    period_end: date | None
    started_at: datetime
    completed_at: datetime | None
    failure_reason: str | None
    data_quality: dict | None


class DetectionRunDetail(DetectionRunRead):
    per_rule_breakdown: list[RuleBreakdownItem] = []