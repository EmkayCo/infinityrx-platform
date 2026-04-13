"""Pydantic schemas for claims API endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ClaimSubmitRequest(BaseModel):
    source_type: str
    auth_number: str
    claim_type: str
    pharmacy_npi: str
    date_of_service: date
    net_amount: Decimal = Field(ge=Decimal("0"))
    client_id: uuid.UUID
    program_id: uuid.UUID
    reversal_of_auth: str | None = None
    member_id: str | None = None
    pharmacy_name: str | None = None
    prescriber_npi: str | None = None
    ndc: str | None = None
    drug_name: str | None = None
    quantity: Decimal | None = None
    days_supply: int | None = None
    ingredient_cost: Decimal = Decimal("0")
    dispensing_fee: Decimal = Decimal("0")
    patient_pay: Decimal = Decimal("0")
    plan_pay: Decimal = Decimal("0")
    other_payer_amount: Decimal = Decimal("0")
    under_reimbursement: Decimal = Decimal("0")
    network_reimbursement_id: str | None = None

    @field_validator("pharmacy_npi")
    @classmethod
    def validate_npi(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 10:
            raise ValueError("pharmacy_npi must be exactly 10 digits")
        return v


class ClaimResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    auth_number: str
    claim_type: str
    pharmacy_npi: str
    date_of_service: date
    net_amount: Decimal
    client_id: uuid.UUID
    program_id: uuid.UUID
    status: str
    payment_route: str | None = None
    is_duplicate: bool = False


class ClaimListParams(BaseModel):
    client_id: uuid.UUID | None = None
    program_id: uuid.UUID | None = None
    status: str | None = None
    claim_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
