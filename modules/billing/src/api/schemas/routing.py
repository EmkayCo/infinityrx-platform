"""Pydantic schemas for routing rules API endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class RoutingRuleCreateRequest(BaseModel):
    name: str
    priority: int = Field(ge=1, le=9999)
    payment_route: str
    payment_vendor_config_id: uuid.UUID | None = None
    payment_schedule: str | None = None
    match_nrid: str | None = None
    match_program_id: uuid.UUID | None = None
    match_pharmacy_npi: str | None = None
    match_claim_type: str | None = None
    match_client_id: uuid.UUID | None = None


class RoutingRuleUpdateRequest(BaseModel):
    name: str | None = None
    priority: int | None = Field(default=None, ge=1, le=9999)
    payment_route: str | None = None
    payment_vendor_config_id: uuid.UUID | None = None
    payment_schedule: str | None = None
    match_nrid: str | None = None
    match_program_id: uuid.UUID | None = None
    match_pharmacy_npi: str | None = None
    match_claim_type: str | None = None
    match_client_id: uuid.UUID | None = None


class RoutingRuleResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    priority: int
    payment_route: str
    payment_vendor_config_id: uuid.UUID | None = None
    payment_schedule: str | None = None
    match_nrid: str | None = None
    match_program_id: uuid.UUID | None = None
    match_pharmacy_npi: str | None = None
    match_claim_type: str | None = None
    match_client_id: uuid.UUID | None = None
    is_active: bool


class RoutingTestRequest(BaseModel):
    claims: list[dict]


class RoutingTestResponse(BaseModel):
    results: list[dict]
