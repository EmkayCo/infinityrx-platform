"""Pydantic schemas for BFSF documentation endpoints."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class ServiceCatalogCreate(BaseModel):
    service_name: str
    description: str
    estimated_hours: Decimal
    market_rate_per_hour: Decimal
    market_comparables: dict[str, Any] | None = None


class BFSFDocumentCreate(BaseModel):
    sponsor_id: uuid.UUID
    document_type: str
    assessment_year: int
    services_detail: list[dict[str, Any]]
    contract_id: uuid.UUID | None = None


class BFSFApproveRequest(BaseModel):
    approved_by: uuid.UUID


class BFSFRejectRequest(BaseModel):
    rejection_reason: str


class BFSFDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sponsor_id: uuid.UUID
    document_type: str
    assessment_year: int
    total_fee: Decimal
    fair_market_value_justified: bool
    status: str
    version: int
