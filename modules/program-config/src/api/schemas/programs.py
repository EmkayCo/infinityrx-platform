"""Pydantic schemas for program-config API endpoints.

All money fields are str (serialized Decimal). No floats anywhere.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Program schemas
# ---------------------------------------------------------------------------


class ProgramCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    program_type: str = Field(..., description="One of: copay, voucher, bridge, debit_card, specialty, workers_comp, 340b, commercial, medicare, medicaid")
    client_id: uuid.UUID
    effective_date: datetime | None = None
    termination_date: datetime | None = None
    bin_number: str | None = Field(None, max_length=10)
    pcn: str | None = Field(None, max_length=20)
    group_id: str | None = Field(None, max_length=20)

    @field_validator("bin_number")
    @classmethod
    def validate_bin(cls, v: str | None) -> str | None:
        if v is not None:
            import re
            if not re.fullmatch(r"\A\d{6}\Z", v):
                raise ValueError("BIN number must be exactly 6 digits")
        return v

    @field_validator("program_type")
    @classmethod
    def validate_program_type(cls, v: str) -> str:
        from src.services.brd_engine import PROGRAM_TYPE_SLUGS
        if v not in PROGRAM_TYPE_SLUGS:
            raise ValueError(f"program_type must be one of: {PROGRAM_TYPE_SLUGS}")
        return v


class ProgramUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    effective_date: datetime | None = None
    termination_date: datetime | None = None
    bin_number: str | None = None
    pcn: str | None = None
    group_id: str | None = None
    wizard_step: int | None = None
    wizard_data: dict[str, Any] | None = None


class ProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    program_type: str
    client_id: uuid.UUID
    status: str
    bin_number: str | None
    pcn: str | None
    group_id: str | None
    effective_date: datetime | None
    termination_date: datetime | None
    wizard_step: int
    post_launch_monitoring: bool
    created_at: datetime
    updated_at: datetime


class ProgramStatusTransitionRequest(BaseModel):
    new_status: str
    reason: str | None = None


# ---------------------------------------------------------------------------
# Program Drug schemas
# ---------------------------------------------------------------------------


class ProgramDrugAddRequest(BaseModel):
    ndc: str = Field(..., min_length=11, max_length=11)
    gpi: str | None = Field(None, max_length=14)
    drug_name: str | None = Field(None, max_length=200)
    copay_amount: str | None = None  # Decimal string
    per_fill_cap: str | None = None
    annual_max: str | None = None

    @field_validator("ndc")
    @classmethod
    def validate_ndc(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"\A\d{11}\Z", v):
            raise ValueError("NDC must be exactly 11 digits")
        return v

    @field_validator("copay_amount", "per_fill_cap", "annual_max", mode="before")
    @classmethod
    def validate_money(cls, v: Any) -> str | None:
        if v is None:
            return None
        try:
            Decimal(str(v))
        except Exception:
            raise ValueError("Money fields must be valid decimal strings")
        return str(v)


class ProgramDrugResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    program_id: uuid.UUID
    ndc: str
    gpi: str | None
    drug_name: str | None
    copay_amount: Decimal | None
    per_fill_cap: Decimal | None
    annual_max: Decimal | None
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# BRD Template schemas
# ---------------------------------------------------------------------------


class BrdTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100)
    program_type: str
    form_builder_schema: dict[str, Any]

    @field_validator("program_type")
    @classmethod
    def validate_program_type(cls, v: str) -> str:
        from src.services.brd_engine import PROGRAM_TYPE_SLUGS
        if v not in PROGRAM_TYPE_SLUGS:
            raise ValueError(f"program_type must be one of: {PROGRAM_TYPE_SLUGS}")
        return v


class BrdTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    program_type: str
    version: int
    form_builder_schema: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# BRD Submission schemas
# ---------------------------------------------------------------------------


class BrdSubmitRequest(BaseModel):
    template_id: uuid.UUID
    program_id: uuid.UUID | None = None
    parsed_data: dict[str, Any]


class BrdReviewRequest(BaseModel):
    action: str  # approve | reject | request_changes
    notes: str | None = None


class BrdSignRequest(BaseModel):
    signer_notes: str | None = None


class BrdSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    template_id: uuid.UUID
    template_version_at_upload: int
    program_id: uuid.UUID | None
    status: str
    parsed_data: dict[str, Any]
    validation_results: dict[str, Any]
    signature_hash: str | None
    signed_at: datetime | None
    applied_at: datetime | None
    created_at: datetime


class BrdValidationResponse(BaseModel):
    valid: bool
    errors: dict[str, str]
    warnings: dict[str, str]


class BrdDiffResponse(BaseModel):
    added: dict[str, Any]
    modified: dict[str, Any]
    removed: dict[str, Any]


# ---------------------------------------------------------------------------
# Contract schemas
# ---------------------------------------------------------------------------


class ContractCreateRequest(BaseModel):
    program_id: uuid.UUID
    client_id: uuid.UUID
    effective_date: datetime
    termination_date: datetime | None = None
    auto_renewal: bool = False
    renewal_notice_days: int = Field(default=90, ge=1, le=365)
    sla: dict[str, Any] = Field(default_factory=dict)
    fees: dict[str, Any] = Field(default_factory=dict)
    spend_cap_config: dict[str, Any] = Field(default_factory=dict)
    bfsf_documentation: dict[str, Any] = Field(default_factory=dict)


class ContractAmendmentRequest(BaseModel):
    effective_date: datetime
    changes: dict[str, Any]
    reason: str


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    program_id: uuid.UUID
    client_id: uuid.UUID
    status: str
    effective_date: datetime
    termination_date: datetime | None
    auto_renewal: bool
    auto_renewal_date: datetime | None
    renewal_notice_days: int
    sla: dict[str, Any]
    fees: dict[str, Any]
    amendments: list[Any]
    spend_cap_config: dict[str, Any]
    bfsf_documentation: dict[str, Any]
    created_at: datetime


# ---------------------------------------------------------------------------
# Onboarding schemas
# ---------------------------------------------------------------------------


class OnboardingStepCompleteRequest(BaseModel):
    step_number: int = Field(..., ge=1)
    action: str = Field(default="completed")  # completed | skip
    notes: str | None = None


class OnboardingWorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    program_id: uuid.UUID
    status: str
    current_step: int
    steps: list[Any]
    go_live_date: datetime | None
    created_at: datetime
    updated_at: datetime


class OnboardingDashboardEntry(BaseModel):
    program_id: uuid.UUID
    program_name: str
    workflow_id: uuid.UUID
    status: str
    current_step: int
    total_steps: int
    bottlenecks: list[dict[str, Any]]
    percent_complete: float


# ---------------------------------------------------------------------------
# Manufacturer self-service schemas
# ---------------------------------------------------------------------------


class ManufacturerConfigCreateRequest(BaseModel):
    manufacturer_id: uuid.UUID
    wizard_data: dict[str, Any] = Field(default_factory=dict)


class ManufacturerConfigUpdateRequest(BaseModel):
    wizard_data: dict[str, Any] | None = None
    accumulator_strategy: str | None = None


class ManufacturerConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    program_id: uuid.UUID | None
    manufacturer_id: uuid.UUID
    review_status: str
    wizard_data: dict[str, Any]
    ai_recommendations: dict[str, Any]
    accumulator_strategy: str | None
    recommended_copay_amount: Decimal | None
    recommended_per_fill_cap: Decimal | None
    recommended_annual_max: Decimal | None
    submitted_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Copay recommendation schemas
# ---------------------------------------------------------------------------


class CopayRecommendRequest(BaseModel):
    drug_wac_per_30_day: str  # Decimal string
    commercial_payer_mix_fraction: str  # Decimal string [0..1]
    competitive_benchmark_copay: str  # Decimal string
    gtn_budget_per_patient: str  # Decimal string
    avg_fills_per_year: int = Field(default=12, ge=1, le=52)

    @field_validator("drug_wac_per_30_day", "competitive_benchmark_copay", "gtn_budget_per_patient")
    @classmethod
    def validate_positive_decimal(cls, v: str) -> str:
        try:
            d = Decimal(v)
            if d < 0:
                raise ValueError("Must be non-negative")
        except Exception:
            raise ValueError("Must be a valid non-negative decimal string")
        return v

    @field_validator("commercial_payer_mix_fraction")
    @classmethod
    def validate_fraction(cls, v: str) -> str:
        try:
            d = Decimal(v)
            if not (Decimal("0") <= d <= Decimal("1")):
                raise ValueError("Must be between 0 and 1")
        except Exception:
            raise ValueError("Must be a decimal string between 0 and 1")
        return v


class CopayRecommendResponse(BaseModel):
    recommended_copay: str
    recommended_per_fill_cap: str
    recommended_annual_max: str
    accumulator_strategy: str
    rationale: dict[str, Any]
    scores: dict[str, str]


# ---------------------------------------------------------------------------
# Error schema
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    code: str
    message: str
    correlation_id: str
    field: str | None = None
