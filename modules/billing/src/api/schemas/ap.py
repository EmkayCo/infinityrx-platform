"""Pydantic schemas for AP and payment batch API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class APRecordResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    claim_record_id: uuid.UUID
    client_id: uuid.UUID
    pay_to_entity_id: uuid.UUID
    pay_to_entity_name: str
    amount: Decimal
    payment_route: str
    status: str
    is_carryover: bool
    created_at: datetime


class APSummaryResponse(BaseModel):
    entity_id: uuid.UUID
    entity_name: str
    total_amount: Decimal
    record_count: int
    status: str


class BatchGenerateRequest(BaseModel):
    payment_route: str
    batch_number: str
    ap_record_ids: list[uuid.UUID] | None = None


class PaymentBatchResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    batch_number: str
    payment_route: str
    total_amount: Decimal
    payment_count: int
    ap_count: int
    status: str
    created_at: datetime


class PaymentResponse(BaseModel):
    id: uuid.UUID
    payment_batch_id: uuid.UUID
    tenant_id: uuid.UUID
    pay_to_entity_id: uuid.UUID
    pay_to_entity_name: str
    amount: Decimal
    claim_count: int
    status: str


class BatchValidateResponse(BaseModel):
    valid: bool
    errors: list[str]


class SettlementRecordRequest(BaseModel):
    payment_id: uuid.UUID
    settlement_date: str
    bank_reference: str | None = None


class ACHReturnRequest(BaseModel):
    payment_id: uuid.UUID
    return_code: str
    return_date: str


class APListParams(BaseModel):
    client_id: uuid.UUID | None = None
    pay_to_entity_id: uuid.UUID | None = None
    status: str | None = None
    payment_route: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
