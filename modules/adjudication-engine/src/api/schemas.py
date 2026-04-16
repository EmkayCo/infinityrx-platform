"""Pydantic schemas for adjudication engine API."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdjudicateRequest(BaseModel):
    """Request body for claim adjudication."""

    model_config = ConfigDict(strict=True)

    bin_number: str = Field(..., min_length=6, max_length=6)
    pcn: str = Field(..., max_length=20)
    transaction_code: str = Field(..., pattern=r"\A(B1|B2|B3|E1)\Z")

    # Patient
    cardholder_id: str = Field(..., min_length=1, max_length=20)
    person_code: str = Field(default="01", max_length=3)
    date_of_birth: str = Field(..., min_length=8, max_length=8)

    # Insurance
    group_id: str = Field(default="", max_length=15)
    plan_id: str = Field(default="", max_length=8)

    # Claim
    pharmacy_npi: str = Field(..., min_length=10, max_length=10)
    prescriber_npi: str = Field(..., min_length=10, max_length=10)
    drug_ndc: str = Field(..., min_length=11, max_length=11)
    drug_name: str = Field(default="", max_length=255)
    quantity: str = Field(...)  # Decimal as string
    day_supply: int = Field(..., ge=1, le=365)
    date_of_service: str = Field(..., min_length=8, max_length=10)
    daw_code: str = Field(default="0", max_length=2)
    compound_code: str = Field(default="0", max_length=1)

    # Pricing submitted
    ingredient_cost_submitted: str = Field(...)  # Decimal as string
    dispensing_fee_submitted: str = Field(...)  # Decimal as string
    patient_paid_amount: str = Field(default="0.00")
    usual_and_customary: str = Field(default="0.00")

    # Optional COB
    other_coverage_code: str = Field(default="")


class AdjudicationResponse(BaseModel):
    """Response body for claim adjudication result."""

    model_config = ConfigDict(from_attributes=True)

    claim_id: str
    status: str  # paid/rejected/reversed/pending
    transaction_type: str

    # Pricing — serialized as strings for Decimal fidelity
    ingredient_cost: str
    dispensing_fee: str
    patient_pay: str
    plan_pay: str
    total_amount: str
    pricing_model_used: str

    # Rejection
    reject_code: str | None = None
    reject_reason: str | None = None

    # Plain English reasons
    reasons: list[str]

    # DUR alerts
    dur_alerts: list[dict[str, Any]] = Field(default_factory=list)

    # Fraud
    copay_fraud_score: str = "0.0000"

    # Accumulator
    accumulator_detected: bool = False

    # Override
    override_applied: bool = False

    # Therapeutic alternative
    therapeutic_alternative_ndc: str = ""
    therapeutic_alternative_savings: str = "0.00"


class ClaimDetailResponse(BaseModel):
    """Full claim detail including trace."""

    model_config = ConfigDict(from_attributes=True)

    claim_id: str
    tenant_id: str
    member_id: str
    pharmacy_npi: str
    prescriber_npi: str
    drug_ndc: str
    drug_name: str
    quantity: str
    day_supply: int
    date_of_service: str
    transaction_type: str
    status: str

    # Pricing
    ingredient_cost: str
    dispensing_fee: str
    patient_pay: str
    plan_pay: str
    total_amount: str
    pricing_model_used: str | None

    # Adjudication details
    reject_code: str | None
    reject_reason: str | None
    adjudication_reasons: list[str] | None
    dur_alerts: list[dict[str, Any]] | None
    cob_details: dict[str, Any] | None
    accumulator_detected: bool
    copay_fraud_score: str | None
    override_applied: bool

    created_at: str


class ClaimTraceResponse(BaseModel):
    """Claim trace detail."""

    claim_id: str
    trace: list[dict[str, Any]]


class ReverseRequest(BaseModel):
    """Request body for claim reversal."""

    model_config = ConfigDict(strict=True)

    original_claim_id: str = Field(...)
    pharmacy_npi: str = Field(..., min_length=10, max_length=10)
    reason: str = Field(default="")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail


class ErrorDetail(BaseModel):
    """Error detail."""

    code: str
    message: str
    field: str | None = None
    correlation_id: str
