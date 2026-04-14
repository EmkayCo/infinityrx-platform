"""Pydantic schemas for claim CRUD endpoints."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.utils.validators import is_valid_npi, is_valid_ndc


class ClaimCreate(BaseModel):
    """Request schema for POST /claims."""

    claim_number: str = Field(..., max_length=50)
    claim_line_number: int = Field(default=1, ge=1)
    claim_type: str = Field(..., pattern="^(professional|institutional)$")

    source_file_type: str | None = Field(default="api", max_length=10)

    patient_member_id: str = Field(..., max_length=100)
    patient_first_name: str | None = Field(default=None, max_length=255)
    patient_last_name: str | None = Field(default=None, max_length=255)
    patient_dob: date | None = None
    patient_gender: str | None = Field(default=None, max_length=1)

    subscriber_id: str | None = Field(default=None, max_length=100)
    subscriber_relationship: str | None = Field(default=None, max_length=5)

    rendering_provider_npi: str = Field(..., max_length=10)
    rendering_provider_name: str | None = Field(default=None, max_length=500)
    rendering_provider_taxonomy: str | None = Field(default=None, max_length=20)

    billing_provider_npi: str | None = Field(default=None, max_length=10)
    billing_provider_name: str | None = Field(default=None, max_length=500)
    billing_provider_tax_id: str | None = Field(default=None, max_length=11)

    referring_provider_npi: str | None = Field(default=None, max_length=10)
    facility_npi: str | None = Field(default=None, max_length=10)
    facility_name: str | None = Field(default=None, max_length=500)

    date_of_service: date
    date_of_service_end: date | None = None
    place_of_service: str | None = Field(default=None, max_length=2)
    type_of_bill: str | None = Field(default=None, max_length=4)

    procedure_code: str = Field(..., max_length=10)
    procedure_code_type: str = Field(default="HCPCS", max_length=10)
    modifier_1: str | None = Field(default=None, max_length=5)
    modifier_2: str | None = Field(default=None, max_length=5)
    modifier_3: str | None = Field(default=None, max_length=5)
    modifier_4: str | None = Field(default=None, max_length=5)
    revenue_code: str | None = Field(default=None, max_length=4)

    ndc: str | None = Field(default=None, max_length=11)
    ndc_qualifier: str | None = Field(default=None, max_length=2)
    drug_name: str | None = Field(default=None, max_length=500)
    drug_quantity: Decimal | None = None
    drug_unit: str | None = Field(default=None, max_length=5)
    drug_unit_price: Decimal | None = None

    diagnosis_code_1: str | None = Field(default=None, max_length=10)
    diagnosis_code_2: str | None = Field(default=None, max_length=10)
    diagnosis_code_3: str | None = Field(default=None, max_length=10)
    diagnosis_code_4: str | None = Field(default=None, max_length=10)
    diagnosis_code_qualifier: str | None = Field(default="ABK", max_length=5)
    diagnosis_pointer: str | None = Field(default=None, max_length=4)

    billed_amount: Decimal
    allowed_amount: Decimal | None = None
    paid_amount: Decimal | None = None
    patient_responsibility: Decimal | None = None
    copay_amount: Decimal | None = None
    coinsurance_amount: Decimal | None = None
    deductible_amount: Decimal | None = None

    payer_sequence: str | None = Field(default=None, max_length=10)
    other_payer_paid: Decimal | None = None

    prior_auth_number: str | None = Field(default=None, max_length=50)
    prior_auth_status: str | None = Field(default=None, max_length=50)

    @field_validator("rendering_provider_npi")
    @classmethod
    def validate_rendering_npi(cls, v: str) -> str:
        if not is_valid_npi(v):
            raise ValueError("rendering_provider_npi must be exactly 10 digits")
        return v

    @field_validator("billing_provider_npi")
    @classmethod
    def validate_billing_npi(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_npi(v):
            raise ValueError("billing_provider_npi must be exactly 10 digits")
        return v

    @field_validator("referring_provider_npi")
    @classmethod
    def validate_referring_npi(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_npi(v):
            raise ValueError("referring_provider_npi must be exactly 10 digits")
        return v

    @field_validator("facility_npi")
    @classmethod
    def validate_facility_npi(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_npi(v):
            raise ValueError("facility_npi must be exactly 10 digits")
        return v

    @field_validator("ndc")
    @classmethod
    def validate_ndc(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_ndc(v):
            raise ValueError("ndc must be exactly 11 digits")
        return v


class ClaimUpdate(BaseModel):
    """Request schema for PUT /claims/{id}."""

    status: str | None = None
    mapped_ndc: str | None = None
    mapping_confidence: str | None = None
    allowed_amount: Decimal | None = None
    paid_amount: Decimal | None = None
    patient_responsibility: Decimal | None = None
    copay_amount: Decimal | None = None
    coinsurance_amount: Decimal | None = None
    deductible_amount: Decimal | None = None
    waste_quantity: Decimal | None = None
    waste_amount: Decimal | None = None
    site_of_care: str | None = None
    administration_method: str | None = None
    is_340b: bool | None = None
    entity_340b_id: str | None = None
    denial_reason_code: str | None = None
    denial_reason_description: str | None = None
    applied_to_deductible: Decimal | None = None
    applied_to_oop: Decimal | None = None
    adjustment_reason_codes: list[Any] | None = None


class ClaimResponse(BaseModel):
    """Response schema for a single claim."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    claim_number: str
    claim_line_number: int
    claim_type: str
    source_file_type: str | None
    received_date: date
    patient_member_id: str
    patient_gender: str | None
    rendering_provider_npi: str
    billing_provider_npi: str | None
    date_of_service: date
    procedure_code: str
    procedure_code_type: str
    modifier_1: str | None
    modifier_2: str | None
    modifier_3: str | None
    modifier_4: str | None
    ndc: str | None
    drug_name: str | None
    drug_quantity: Decimal | None
    drug_unit: str | None
    mapped_ndc: str | None
    mapping_confidence: str | None
    billed_amount: Decimal
    allowed_amount: Decimal | None
    paid_amount: Decimal | None
    patient_responsibility: Decimal | None
    waste_quantity: Decimal | None
    waste_amount: Decimal | None
    site_of_care: str | None
    administration_method: str | None
    is_340b: bool
    payer_sequence: str | None
    status: str
    denial_reason_code: str | None
    applied_to_deductible: Decimal | None
    applied_to_oop: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClaimListResponse(BaseModel):
    items: list[ClaimResponse]
    total: int
    page: int
    page_size: int


class ClaimStatusUpdate(BaseModel):
    """Request schema for status transitions."""
    status: str = Field(..., pattern="^(received|validated|priced|adjudicated|paid|denied|appealed|voided)$")
    denial_reason_code: str | None = None
    denial_reason_description: str | None = None


class FileUploadResponse(BaseModel):
    """Response after bulk file upload."""
    accepted: int
    rejected: int
    errors: list[dict[str, Any]]
