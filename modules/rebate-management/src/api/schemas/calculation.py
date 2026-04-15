"""Pydantic schemas for calculation endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class ClaimLineInputSchema(BaseModel):
    ndc11: str
    date_of_service: date
    units_dispensed: Decimal
    wac_per_unit: Decimal
    sponsor_id: uuid.UUID
    claim_id: uuid.UUID | None = None


class CalculateRebatesRequest(BaseModel):
    period_start: date
    period_end: date
    claim_lines: list[ClaimLineInputSchema]
    market_shares: dict[str, str] = {}  # ndc11 -> decimal string


class CalculationResultResponse(BaseModel):
    period_start: date
    period_end: date
    total_rebate: str
    ndc_count: int
    transaction_count: int
    results: list[dict[str, Any]]


class AccrualRequest(BaseModel):
    contract_id: uuid.UUID
    ndc11: str
    accrual_month: date
    accrued_amount: Decimal


class RecognizeAccrualRequest(BaseModel):
    accrual_id: uuid.UUID
    actual_payment_id: uuid.UUID | None = None
