"""Pydantic request/response schemas for pharmacy-directory API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None
    correlation_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# --- Pharmacy lookup ---

class PharmacyResponse(BaseModel):
    id: str
    npi: str
    nabp_number: str | None = None
    legal_name: str
    display_name: str
    pharmacy_type: str
    address_line_1: str
    city: str
    state: str
    zip_code: str
    phone: str | None = None
    status: str
    latitude: str | None = None
    longitude: str | None = None
    distance_miles: float | None = None


class PharmacyListResponse(BaseModel):
    pharmacies: list[PharmacyResponse]
    total: int


class BatchLookupRequest(BaseModel):
    npis: list[str] = Field(..., min_length=1, max_length=100)


# --- Networks ---

class NetworkCreateRequest(BaseModel):
    name: str
    network_code: str
    network_type: str
    effective_date: date
    description: str | None = None
    any_willing_pharmacy: bool = False


class NetworkResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    network_code: str
    network_type: str
    is_active: bool
    any_willing_pharmacy: bool
    effective_date: date
    termination_date: date | None = None


class AddPharmacyToNetworkRequest(BaseModel):
    pharmacy_id: str
    effective_date: date
    reimbursement_type: str | None = None
    brand_discount: Decimal | None = None
    generic_discount: Decimal | None = None
    specialty_discount: Decimal | None = None
    dispensing_fee: Decimal | None = None
    admin_fee: Decimal | None = None
    performance_tier: str | None = None


class NetworkMembershipResponse(BaseModel):
    id: str
    pharmacy_id: str
    network_id: str
    status: str
    effective_date: date
    dispensing_fee: Decimal | None = None
    brand_discount: Decimal | None = None


# --- Credentialing ---

class CredentialingApplicationRequest(BaseModel):
    applicant_npi: str
    applicant_name: str
    network_id: str
    pharmacy_id: str | None = None
    applicant_address: str | None = None


class CredentialingDecisionRequest(BaseModel):
    denial_reason: str | None = None
    review_notes: str | None = None


class CredentialingApplicationResponse(BaseModel):
    id: str
    tenant_id: str
    applicant_npi: str
    applicant_name: str
    network_id: str
    status: str
    credentialing_risk_score: int | None = None
    npi_verified: bool
    state_license_verified: bool
    dea_verified: bool
    oig_sam_screened: bool
    oig_sam_clear: bool


# --- Payment Info ---

class PaymentInfoRequest(BaseModel):
    payment_method_preference: str | None = None
    bank_name: str | None = None
    routing_number: str | None = None
    account_number: str | None = None
    account_type: str | None = None
    remittance_delivery: str | None = None
    remittance_email: str | None = None
    tax_id: str | None = None
    w9_on_file: bool = False


class PaymentInfoResponse(BaseModel):
    id: str
    pharmacy_id: str
    payment_method_preference: str | None = None
    # Sensitive fields masked in response
    bank_name: str | None = None
    routing_number_masked: str | None = None
    account_number_masked: str | None = None
    w9_on_file: bool


# --- PSAOs ---

class PsaoCreateRequest(BaseModel):
    name: str
    psao_id: str | None = None
    npi: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    payment_consolidated: bool = True


class PsaoResponse(BaseModel):
    id: str
    name: str
    psao_id: str | None = None
    npi: str | None = None
    payment_consolidated: bool
    is_active: bool


# --- Adequacy ---

class AdequacyRequest(BaseModel):
    member_locations: list[tuple[Decimal, Decimal, str]]
    area_type: str = "urban"


class AdequacyResponse(BaseModel):
    adequacy_pct: Decimal | None
    member_count: int
    covered_count: int
    radius_miles: float | None = None
    area_type: str | None = None


# --- Stats ---

class DirectoryStatsResponse(BaseModel):
    total_pharmacies: int
    active_pharmacies: int
    total_networks: int
    pending_credentialing: int
