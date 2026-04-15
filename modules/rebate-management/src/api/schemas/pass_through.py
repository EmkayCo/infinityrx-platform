"""Pydantic schemas for pass-through ledger endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PassThroughEntryRequest(BaseModel):
    transaction_id: uuid.UUID
    ndc11: str
    period_month: date
    sponsor_id: uuid.UUID
    manufacturer_received: Decimal
    sponsor_passed: Decimal
    rebate_category: str
    remittance_date: date | None = None


class ReconcileMonthRequest(BaseModel):
    sponsor_id: uuid.UUID
    period_month: date
    notes: str | None = None


class PassThroughEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ndc11: str
    period_month: date
    sponsor_id: uuid.UUID
    manufacturer_received: Decimal
    sponsor_passed: Decimal
    rebate_category: str
    entry_hash: str
    prev_hash: str


class ReconciliationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sponsor_id: uuid.UUID
    period_month: date
    total_received: Decimal
    total_passed: Decimal
    difference: Decimal
    is_balanced: bool
