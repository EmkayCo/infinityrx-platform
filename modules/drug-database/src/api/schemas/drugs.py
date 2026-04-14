"""Pydantic schemas for drug database API."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.utils.ndc import InvalidNDCError, normalize_ndc


class DrugProductResponse(BaseModel):
    id: uuid.UUID
    ndc_11: str
    ndc_formatted: str | None
    proprietary_name: str | None
    nonproprietary_name: str | None
    drug_name_display: str
    drug_type: str | None
    dea_schedule: str | None
    otc_rx: str | None
    dosage_form: str | None
    route_of_administration: str | None
    strength: str | None
    labeler_name: str | None
    marketing_status: str | None
    is_specialty: bool
    is_biosimilar: bool
    is_glp1: bool
    gpi_code: str | None
    atc_code: str | None
    therapeutic_class_1: str | None
    therapeutic_class_2: str | None
    is_active: bool
    data_source: str


class PricingResponse(BaseModel):
    ndc_11: str
    price_type: str
    price_per_unit: Decimal
    unit_type: str | None
    package_price: Decimal | None
    effective_date: date
    termination_date: date | None
    data_source: str


class PricingHistoryResponse(BaseModel):
    ndc_11: str
    price_type: str
    old_price: Decimal | None
    new_price: Decimal
    change_percentage: Decimal | None
    effective_date: date
    data_source: str
    created_at: datetime


class InteractionResponse(BaseModel):
    drug_1_identifier: str
    drug_2_identifier: str
    drug_1_name: str | None
    drug_2_name: str | None
    severity: str
    interaction_description: str | None
    management_recommendation: str | None


class TherapeuticEquivalenceResponse(BaseModel):
    brand_ndc: str | None
    brand_name: str | None
    generic_ndc: str | None
    generic_name: str | None
    te_code: str
    is_therapeutically_equivalent: bool | None


class DrugSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    results: list[DrugProductResponse]


class MACUploadResponse(BaseModel):
    records_applied: int
    records_skipped: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


class RefreshStatusResponse(BaseModel):
    data_source: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    records_processed: int
    records_added: int
    records_updated: int
    price_changes_detected: int
    error_message: str | None


class TenantOverrideResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    ndc_11: str
    price_type: str
    price_per_unit: Decimal
    unit_type: str | None
    effective_date: date
    termination_date: date | None
    data_source: str


class ErrorResponse(BaseModel):
    error: dict[str, Any]


class NDCLookupParams(BaseModel):
    """Validated NDC path parameter."""

    ndc_11: str

    @field_validator("ndc_11", mode="before")
    @classmethod
    def validate_ndc(cls, v: str) -> str:
        try:
            return normalize_ndc(v)
        except InvalidNDCError as e:
            raise ValueError(str(e)) from e


class DrugShortageResponse(BaseModel):
    id: uuid.UUID
    ndc_11: str | None
    ingredient_name: str | None
    shortage_status: str
    start_date: date | None
    expected_resolution_date: date | None
    reason: str | None


class RemsProgramResponse(BaseModel):
    id: uuid.UUID
    ndc_11: str | None
    ingredient_name: str | None
    rems_program_name: str
    rems_status: str
    certified_pharmacy_required: bool
    certified_prescriber_required: bool
    patient_registry_required: bool
    lab_testing_required: bool
    restricted_distribution: bool
    patient_agreement_required: bool
