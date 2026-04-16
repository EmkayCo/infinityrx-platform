"""Pydantic schemas for rules-engine API request/response validation."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Rule Type
# ---------------------------------------------------------------------------


class RuleTypeCreate(BaseModel):
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    category: str = Field(..., pattern=r"\A(pricing|coverage|authorization|specialty)\Z")
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class RuleTypeResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    parameter_schema: dict[str, Any]
    description: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Rule Instance
# ---------------------------------------------------------------------------


class RuleInstanceCreate(BaseModel):
    rule_type_id: uuid.UUID
    plan_id: uuid.UUID | None = None
    program_id: uuid.UUID | None = None
    priority_order: int = 0
    parameters: dict[str, Any] = Field(default_factory=dict)
    effective_date: date
    termination_date: date | None = None
    status: str = Field(default="draft", pattern=r"\A(active|inactive|draft)\Z")


class RuleInstanceUpdate(BaseModel):
    priority_order: int | None = None
    parameters: dict[str, Any] | None = None
    effective_date: date | None = None
    termination_date: date | None = None
    status: str | None = Field(default=None, pattern=r"\A(active|inactive|draft)\Z")


class RuleInstanceResponse(BaseModel):
    id: uuid.UUID
    rule_type_id: uuid.UUID
    plan_id: uuid.UUID | None
    program_id: uuid.UUID | None
    priority_order: int
    parameters: dict[str, Any]
    version: int
    effective_date: date
    termination_date: date | None
    status: str
    tenant_id: uuid.UUID

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Rule Pipeline
# ---------------------------------------------------------------------------


class PipelineCreate(BaseModel):
    plan_id: uuid.UUID
    ordered_rule_ids: list[str]


class PipelineUpdate(BaseModel):
    ordered_rule_ids: list[str] | None = None


class PipelineResponse(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    ordered_rule_ids: list[str]
    version: int
    tenant_id: uuid.UUID

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pipeline execution request/response
# ---------------------------------------------------------------------------


class PipelineExecuteRequest(BaseModel):
    claim_id: str
    member_id: str
    member_age: int = 0
    member_state: str = ""
    ndc: str = ""
    drug_name: str = ""
    drug_type: str = ""
    quantity: str = "0"
    days_supply: int = 0
    pharmacy_npi: str = ""
    pharmacy_type: str = ""
    prescriber_npi: str = ""
    plan_id: str = ""
    program_id: str = ""
    ingredient_cost: str = "0.00"


class RuleResultResponse(BaseModel):
    rule_instance_id: str
    rule_type_code: str
    action: str
    modified_values: dict[str, Any]
    message: str
    execution_time_ms: int
    skipped: bool


class PipelineExecuteResponse(BaseModel):
    claim_id: str
    plan_id: str
    final_action: str
    reject_code: str
    reject_message: str
    warnings: list[str]
    conflicts: list[str]
    total_execution_time_ms: int
    results: list[RuleResultResponse]


# ---------------------------------------------------------------------------
# Rule Execution Log
# ---------------------------------------------------------------------------


class ExecutionLogResponse(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    rule_instance_id: uuid.UUID
    result: str
    input_values: dict[str, Any]
    output_values: dict[str, Any]
    execution_time_ms: int
    tenant_id: uuid.UUID

    model_config = {"from_attributes": True}
