"""Pydantic schemas for network endpoints."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class NetworkCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    effective_date: date
    termination_date: date | None = None
    tier_config: dict[str, Any] | None = None
    any_willing_pharmacy_enabled: bool = False


class NetworkUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    status: str | None = None
    tier_config: dict[str, Any] | None = None
    any_willing_pharmacy_enabled: bool | None = None


class NetworkResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    effective_date: date
    termination_date: date | None
    status: str
    tier_config: dict[str, Any] | None
    any_willing_pharmacy_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NetworkPharmacyCreate(BaseModel):
    npi: str = Field(..., min_length=10, max_length=10)
    pharmacy_name: str | None = None
    pharmacy_type: str = "retail"
    network_tier: str | None = None
    specialty_accreditation: str | None = None
    site_of_care_type: str | None = None
    bagging_model: str | None = None
    is_ldd: bool = False
    ldd_drugs: list[str] | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    effective_date: date
    termination_date: date | None = None

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        if v is None:
            return None
        return Decimal(str(v))


class NetworkPharmacyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    network_id: UUID
    npi: str
    pharmacy_name: str | None
    pharmacy_type: str
    network_tier: str | None
    specialty_accreditation: str | None
    site_of_care_type: str | None
    bagging_model: str | None
    is_ldd: bool
    ldd_drugs: list[str] | None
    address_line1: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    effective_date: date
    termination_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NetworkAdequacyResponse(BaseModel):
    """Network adequacy report (time/distance by county/ZIP)."""

    network_id: UUID
    total_member_count: int
    adequate_zip_count: int
    inadequate_zip_count: int
    adequacy_pct: Decimal
    gaps: list[dict[str, Any]]
    calculated_at: datetime

    @field_validator("adequacy_pct", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class AWPApplicationCreate(BaseModel):
    pharmacy_npi: str = Field(..., min_length=10, max_length=10)
    pharmacy_name: str = Field(..., min_length=1, max_length=255)
    pharmacy_address: str | None = None
    application_data: dict[str, Any] | None = None


class AWPApplicationUpdate(BaseModel):
    status: str | None = None
    decision_notes: str | None = None


class AWPApplicationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    network_id: UUID
    pharmacy_npi: str
    pharmacy_name: str
    pharmacy_address: str | None
    status: str
    application_data: dict[str, Any] | None
    decision_notes: str | None
    decided_at: datetime | None
    submitted_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
