"""Pydantic schemas for rebate contract endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NDCTermCreate(BaseModel):
    ndc11: str = Field(..., min_length=11, max_length=11)
    rebate_type: str  # percent_wac, flat_per_unit
    effective_date: date
    rebate_percent: Decimal | None = None
    rebate_per_unit: Decimal | None = None
    drug_name: str | None = None
    formulary_position: str | None = None
    formulary_position_bonus_percent: Decimal | None = None
    growth_bonus_percent: Decimal | None = None
    termination_date: date | None = None


class TierCreate(BaseModel):
    tier_name: str
    tier_type: str  # volume, market_share
    threshold_value: Decimal
    rebate_percent: Decimal


class ContractCreateRequest(BaseModel):
    manufacturer_id: uuid.UUID
    manufacturer_name: str
    contract_number: str
    contract_type: str
    effective_date: date
    payment_frequency: str = "quarterly"
    termination_date: date | None = None
    minimum_volume_threshold: Decimal | None = None
    bfsf_only: bool = False
    notes: str | None = None
    ndc_terms: list[NDCTermCreate] = Field(default_factory=list)
    tiers: list[TierCreate] = Field(default_factory=list)


class ContractStatusTransition(BaseModel):
    new_status: str
    approved_by: uuid.UUID | None = None


class ContractAmendRequest(BaseModel):
    updates: dict[str, Any]


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    manufacturer_id: uuid.UUID
    manufacturer_name: str
    contract_number: str
    contract_type: str
    status: str
    effective_date: date
    termination_date: date | None
    payment_frequency: str
    bfsf_only: bool
    version: int
    created_at: Any
    updated_at: Any
