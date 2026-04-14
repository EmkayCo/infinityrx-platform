"""Pydantic schemas for denial management endpoints."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class DenialResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    claim_number: str
    procedure_code: str
    date_of_service: date
    billed_amount: Decimal
    denial_reason_code: str | None
    denial_reason_description: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DenialAnalyticsResponse(BaseModel):
    """Aggregated denial analytics."""
    period_start: date
    period_end: date
    total_denied: int
    denial_rate: Decimal
    by_reason_code: list[dict[str, Any]]
    by_provider: list[dict[str, Any]]
    by_hcpcs: list[dict[str, Any]]


class AppealCreate(BaseModel):
    """Request to initiate an appeal for a denied claim."""
    appeal_reason: str = Field(..., min_length=10, max_length=2000)
    supporting_documentation: str | None = None
