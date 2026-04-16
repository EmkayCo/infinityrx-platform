"""Pydantic schemas for PA API request/response validation."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PASubmitRequest(BaseModel):
    """Submit a new prior authorization request."""

    member_id: uuid.UUID
    prescriber_npi: str = Field(min_length=10, max_length=10)
    drug_ndc: str = Field(min_length=11, max_length=11)
    drug_name: str = Field(min_length=1, max_length=255)
    source: str = Field(pattern=r"\A(pharmacy_reject|epa|manual|phone|fhir)\Z")
    priority: str = Field(default="routine", pattern=r"\A(routine|urgent)\Z")
    plan_id: uuid.UUID
    program_id: uuid.UUID | None = None
    clinical_data: dict | None = None


class PADecisionRequest(BaseModel):
    """Record a clinical reviewer decision."""

    decision: str = Field(pattern=r"\A(approved|denied|pend|request_info)\Z")
    reviewer_id: uuid.UUID
    approved_duration_days: int | None = None
    approved_quantity: Decimal | None = None
    review_notes: str | None = None

    @field_validator("approved_quantity", mode="before")
    @classmethod
    def coerce_quantity(cls, v: str | Decimal | None) -> Decimal | None:
        if v is None:
            return None
        return Decimal(str(v))


class PAAppealRequest(BaseModel):
    """Submit an appeal against a denial."""

    appeal_level: int = Field(ge=1, le=5)
    appeal_type: str = Field(
        pattern=r"\A(clinical_reviewer|medical_director|external)\Z"
    )
    regulatory_deadline: date | None = None


class PAEvaluateRequest(BaseModel):
    """Clinical data for PA evaluation."""

    member_age: int | None = None
    member_diagnoses: list[str] | None = None
    step_therapy_history: list[dict] | None = None
    lab_results: dict[str, float] | None = None
    member_bmi: float | None = None
    member_comorbidities: list[str] | None = None
    lifestyle_intervention_date: date | None = None


class CopayEPARequest(BaseModel):
    """Create a copay ePA first-fill record."""

    manufacturer_program_id: str = Field(min_length=1, max_length=50)
    first_fill_amount: Decimal
    first_fill_date: date

    @field_validator("first_fill_amount", mode="before")
    @classmethod
    def coerce_amount(cls, v: str | Decimal) -> Decimal:
        return Decimal(str(v))


class PAStatusQuery(BaseModel):
    """Query PA status for a member+drug combination."""

    member_id: uuid.UUID
    drug_ndc: str = Field(min_length=11, max_length=11)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PAResponse(BaseModel):
    """PA request in API responses."""

    id: uuid.UUID
    member_id: uuid.UUID
    prescriber_npi: str
    drug_ndc: str
    drug_name: str
    source: str
    status: str
    priority: str
    plan_id: uuid.UUID
    program_id: uuid.UUID | None
    criteria_set_version: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PADecisionResponse(BaseModel):
    """PA decision in API responses."""

    id: uuid.UUID
    pa_request_id: uuid.UUID
    decision: str
    approved_duration_days: int | None
    approved_quantity: str | None
    reviewed_by: uuid.UUID
    review_notes: str | None
    decided_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("approved_quantity", mode="before")
    @classmethod
    def serialize_quantity(cls, v: Decimal | None) -> str | None:
        if v is None:
            return None
        return str(v)


class PAAppealResponse(BaseModel):
    """PA appeal in API responses."""

    id: uuid.UUID
    pa_request_id: uuid.UUID
    appeal_level: int
    appeal_type: str
    status: str
    regulatory_deadline: date | None
    filed_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class CriteriaResultResponse(BaseModel):
    """Criteria evaluation result."""

    auto_approve: bool
    reasons: list[str]
    missing_info: list[str]


class CopayEPAResponse(BaseModel):
    """Copay ePA record in API responses."""

    id: uuid.UUID
    pa_request_id: uuid.UUID
    manufacturer_program_id: str
    first_fill_amount: str
    first_fill_date: date
    pa_outcome: str | None
    manufacturer_absorbed_cost: str

    model_config = {"from_attributes": True}

    @field_validator("first_fill_amount", "manufacturer_absorbed_cost", mode="before")
    @classmethod
    def serialize_money(cls, v: Decimal | None) -> str:
        if v is None:
            return "0.00"
        return str(v)


class PAStatusResponse(BaseModel):
    """PA status check result."""

    pa_exists: bool
    pa_id: str | None = None
    status: str | None = None
    approved_until: str | None = None


class ErrorDetail(BaseModel):
    """Standard error response."""

    code: str
    message: str
    field: str | None = None
    correlation_id: str | None = None


class ErrorResponse(BaseModel):
    """Wrapper for error responses."""

    error: ErrorDetail
