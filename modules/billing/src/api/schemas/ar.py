"""Pydantic schemas for AR and invoicing API endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class InvoicingConfigResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    billing_frequency: str
    payment_terms_days: int
    auto_send: bool
    delivery_method: str
    auto_approve: bool
    automation_level: str


class InvoicingConfigCreateRequest(BaseModel):
    client_id: uuid.UUID
    billing_frequency: str = "monthly"
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    auto_send: bool = False
    delivery_method: str = "email"
    auto_approve: bool = False
    automation_level: str = "manual"


class InvoiceGenerateRequest(BaseModel):
    client_id: uuid.UUID
    client_name: str
    period_start: date
    period_end: date
    invoice_number: str
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    program_id: uuid.UUID | None = None
    claim_ids: list[uuid.UUID] | None = None


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    invoice_number: str
    period_start: date
    period_end: date
    claims_subtotal: Decimal
    fees_subtotal: Decimal
    adjustments: Decimal
    late_fees: Decimal
    total: Decimal
    status: str
    due_date: date
    created_at: datetime


class InvoiceLineItemResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    line_type: str
    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal


class ARRecordResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    invoice_id: uuid.UUID
    client_id: uuid.UUID
    amount_due: Decimal
    amount_paid: Decimal
    amount_outstanding: Decimal
    status: str
    due_date: date
    aging_bucket: str


class ARPaymentRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"))
    payment_date: date
    payment_reference: str | None = None


class ARDisputeRequest(BaseModel):
    reason: str
    notes: str | None = None


class ARWriteOffRequest(BaseModel):
    reason: str
    approved_by: str


class ARAgingResponse(BaseModel):
    current: Decimal
    days_30: Decimal
    days_60: Decimal
    days_90: Decimal
    days_120_plus: Decimal
    total_outstanding: Decimal


class FeeConfigResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    fee_code: str
    fee_name: str
    calculation_type: str
    amount: Decimal | None = None
    percentage: Decimal | None = None
    is_active: bool


class FeeConfigCreateRequest(BaseModel):
    client_id: uuid.UUID
    fee_code: str
    fee_name: str
    calculation_type: str
    amount: Decimal | None = None
    percentage: Decimal | None = None


class FeeConfigUpdateRequest(BaseModel):
    fee_name: str | None = None
    calculation_type: str | None = None
    amount: Decimal | None = None
    percentage: Decimal | None = None
    is_active: bool | None = None
