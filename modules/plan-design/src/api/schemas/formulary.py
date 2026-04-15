"""Pydantic schemas for formulary endpoints."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class FormularyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    effective_date: date
    termination_date: date | None = None
    tier_config: dict[str, Any] | None = None
    is_open_formulary: bool = False


class FormularyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    status: str | None = None
    tier_config: dict[str, Any] | None = None
    is_open_formulary: bool | None = None


class FormularyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    current_version: int
    effective_date: date
    termination_date: date | None
    status: str
    tier_config: dict[str, Any] | None
    is_open_formulary: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FormularyDrugCreate(BaseModel):
    ndc: str | None = Field(None, max_length=11)
    gpi_range_start: str | None = None
    gpi_range_end: str | None = None
    drug_name: str | None = None
    tier: str = Field(..., min_length=1, max_length=50)
    therapeutic_class: str | None = None
    pa_required: bool = False
    step_therapy_required: bool = False
    quantity_limit: dict[str, Any] | None = None
    is_specialty: bool = False
    biosimilar_reference_ndc: str | None = None
    is_biosimilar: bool = False
    auto_substitution_allowed: bool = False
    indication_coverage: dict[str, Any] | None = None
    is_ira_negotiated: bool = False
    mfp_price: Decimal | None = None
    effective_date: date
    termination_date: date | None = None

    @field_validator("mfp_price", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        if v is None:
            return None
        return Decimal(str(v))


class FormularyDrugUpdate(BaseModel):
    tier: str | None = None
    pa_required: bool | None = None
    step_therapy_required: bool | None = None
    quantity_limit: dict[str, Any] | None = None
    is_specialty: bool | None = None
    biosimilar_reference_ndc: str | None = None
    auto_substitution_allowed: bool | None = None
    indication_coverage: dict[str, Any] | None = None
    is_ira_negotiated: bool | None = None
    mfp_price: Decimal | None = None
    termination_date: date | None = None

    @field_validator("mfp_price", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        if v is None:
            return None
        return Decimal(str(v))


class FormularyDrugResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    formulary_id: UUID
    ndc: str | None
    gpi_range_start: str | None
    gpi_range_end: str | None
    drug_name: str | None
    tier: str
    therapeutic_class: str | None
    pa_required: bool
    step_therapy_required: bool
    quantity_limit: dict[str, Any] | None
    is_specialty: bool
    biosimilar_reference_ndc: str | None
    is_biosimilar: bool
    auto_substitution_allowed: bool
    indication_coverage: dict[str, Any] | None
    is_ira_negotiated: bool
    mfp_price: Decimal | None
    effective_date: date
    termination_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FormularyVersionResponse(BaseModel):
    id: UUID
    formulary_id: UUID
    version_number: int
    effective_date: date
    snapshot: dict[str, Any]
    change_summary: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DrugImportRequest(BaseModel):
    """Bulk drug tier import — CSV or JSON rows."""

    drugs: list[FormularyDrugCreate]


class DrugImportResponse(BaseModel):
    total: int
    imported: int
    errors: list[dict[str, Any]]


class FormularyImpactRequest(BaseModel):
    """Formulary change modeling request."""

    proposed_changes: list[dict[str, Any]]
    analysis_date: date | None = None
    sample_claims_count: int = Field(1000, ge=1, le=100000)


class FormularyImpactResponse(BaseModel):
    formulary_id: UUID
    total_drugs_affected: int
    estimated_cost_delta: Decimal
    tier_changes: list[dict[str, Any]]
    pa_changes: list[dict[str, Any]]
    analysis_date: date

    @field_validator("estimated_cost_delta", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class FBv60PublishRequest(BaseModel):
    """Trigger NCPDP F&B v60 file generation and publication."""

    publish_to_surescripts: bool = False
    notes: str | None = None


class FBv60PublishResponse(BaseModel):
    publication_id: UUID
    formulary_id: UUID
    formulary_version: int
    status: str
    file_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PTMeetingCreate(BaseModel):
    formulary_id: UUID
    meeting_date: date
    agenda: dict[str, Any] | None = None
    drugs_under_review: list[str] | None = None


class PTMeetingUpdate(BaseModel):
    status: str | None = None
    agenda: dict[str, Any] | None = None
    drugs_under_review: list[str] | None = None
    votes: dict[str, Any] | None = None
    decisions: dict[str, Any] | None = None
    rationale: str | None = None


class PTMeetingResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    formulary_id: UUID
    meeting_date: date
    status: str
    agenda: dict[str, Any] | None
    drugs_under_review: list[str] | None
    votes: dict[str, Any] | None
    decisions: dict[str, Any] | None
    rationale: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
