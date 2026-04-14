"""Pydantic schemas for prescriber-directory API."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TaxonomyCodeEntry(BaseModel):
    code: str
    is_primary: bool
    license_number: str | None = None
    license_state: str | None = None


class PrescriberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    npi: str
    entity_type: str
    display_name: str

    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    credential: str | None = None

    organization_name: str | None = None

    primary_taxonomy_code: str | None = None
    primary_taxonomy_description: str | None = None
    primary_specialty: str | None = None
    taxonomy_codes: list[dict[str, Any]] | None = None

    gender: str | None = None

    practice_address_line_1: str | None = None
    practice_address_line_2: str | None = None
    practice_city: str | None = None
    practice_state: str | None = None
    practice_zip: str | None = None
    practice_phone: str | None = None

    dea_status: str | None = None
    dea_expiration_date: date | None = None
    dea_schedules: list[str] | None = None

    state_license_number: str | None = None
    state_license_state: str | None = None
    state_license_status: str | None = None
    state_license_expiry: date | None = None

    pecos_enrolled: bool | None = None
    medicare_participation: bool | None = None
    medicare_opt_out: bool = False

    enumeration_date: date | None = None
    last_update_date: date | None = None
    deactivation_date: date | None = None

    status: str
    offers_telehealth: bool = False

    nppes_last_updated: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PrescriberSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    npi: str
    entity_type: str
    display_name: str
    primary_specialty: str | None = None
    practice_city: str | None = None
    practice_state: str | None = None
    practice_zip: str | None = None
    status: str
    dea_status: str | None = None


class SearchResponse(BaseModel):
    results: list[PrescriberSearchResult]
    total: int
    page: int
    page_size: int


class ValidationResponse(BaseModel):
    npi: str
    valid: bool
    reason: str | None = None
    reason_code: str | None = None


class ControlledSubstanceAuthResponse(BaseModel):
    npi: str
    schedule: str
    authorized: bool
    reason: str | None = None
    reason_code: str | None = None


class BatchLookupRequest(BaseModel):
    npis: list[str]


class BatchLookupResponse(BaseModel):
    results: dict[str, PrescriberResponse | None]
    not_found: list[str]


class CredentialAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prescriber_id: uuid.UUID
    alert_type: str
    severity: str
    message: str
    acknowledged_at: datetime | None = None
    created_at: datetime


class DirectoryStatsResponse(BaseModel):
    total_prescribers: int
    active_prescribers: int
    inactive_prescribers: int
    deactivated_prescribers: int
    excluded_prescribers: int
    by_entity_type: dict[str, int]
    by_state: dict[str, int]
    last_nppes_refresh: datetime | None = None


class PrescriberPharmacyRelationshipResponse(BaseModel):
    prescriber_npi: str
    pharmacy_npi: str
    period_month: str
    claim_count: int
    created_at: datetime
    updated_at: datetime


class NpimportResultResponse(BaseModel):
    status: str
    records_processed: int
    records_added: int
    records_updated: int
    data_source: str
    refresh_type: str
