"""Pydantic schemas for HCPCS-NDC crosswalk endpoints."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class CrosswalkResponse(BaseModel):
    id: uuid.UUID
    hcpcs_code: str
    hcpcs_description: str | None
    ndc: str
    ndc_description: str | None
    hcpcs_dosage_descriptor: str | None
    hcpcs_unit_quantity: Decimal | None
    ndc_package_quantity: Decimal | None
    conversion_factor: Decimal | None
    effective_date: date
    termination_date: date | None
    data_source: str | None

    model_config = {"from_attributes": True}


class CrosswalkLookupResponse(BaseModel):
    """Response for HCPCS lookup — may return multiple NDC matches."""
    hcpcs_code: str
    matches: list[CrosswalkResponse]
    confidence: str  # exact, high, medium, low
    requires_manual_review: bool
