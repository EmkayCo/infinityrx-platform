"""Pydantic schemas for ASP pricing endpoints."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class AspPricingResponse(BaseModel):
    id: uuid.UUID
    hcpcs_code: str
    hcpcs_description: str | None
    asp_per_unit: Decimal
    payment_limit: Decimal | None
    quarter: str
    effective_date: date
    data_source: str

    model_config = {"from_attributes": True}


class AspRefreshResponse(BaseModel):
    quarter: str
    records_loaded: int
    records_skipped: int
    message: str
