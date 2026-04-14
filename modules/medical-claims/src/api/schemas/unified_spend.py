"""Pydantic schemas for unified drug spend endpoints."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class UnifiedSpendResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    member_id: uuid.UUID | None
    member_id_display: str | None
    ndc: str | None
    drug_name: str | None
    therapeutic_class: str | None
    benefit_type: str
    pharmacy_claim_id: uuid.UUID | None
    medical_claim_id: uuid.UUID | None
    date_of_service: date
    billed_amount: Decimal | None
    allowed_amount: Decimal | None
    paid_amount: Decimal | None
    patient_pay: Decimal | None
    quantity: Decimal | None
    days_supply: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnifiedSpendListResponse(BaseModel):
    items: list[UnifiedSpendResponse]
    total: int


class DuplicationResponse(BaseModel):
    """Therapeutic duplication: same drug on both benefits."""
    member_id: uuid.UUID | None
    member_id_display: str | None
    ndc: str
    drug_name: str | None
    pharmacy_record: UnifiedSpendResponse
    medical_record: UnifiedSpendResponse
    date_of_service: date
