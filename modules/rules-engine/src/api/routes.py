"""Rules-engine API route handlers.

All handlers are async def per architecture rules.
All request/response bodies use Pydantic schemas.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import TenantId
from src.api.schemas import (
    ExecutionLogResponse,
    PipelineCreate,
    PipelineExecuteRequest,
    PipelineExecuteResponse,
    PipelineResponse,
    PipelineUpdate,
    RuleInstanceCreate,
    RuleInstanceResponse,
    RuleInstanceUpdate,
    RuleResultResponse,
    RuleTypeCreate,
    RuleTypeResponse,
)
from src.services.pipeline import (
    PipelineRule,
    execute_pipeline,
)
from src.services.rule_types import ClaimContext

logger = logging.getLogger("rules_engine.api")

router = APIRouter(prefix="/api/v1/rules-engine", tags=["rules-engine"])


# ---------------------------------------------------------------------------
# Rule Types CRUD
# ---------------------------------------------------------------------------


@router.post("/rule-types", response_model=RuleTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_rule_type(body: RuleTypeCreate) -> dict[str, Any]:
    """Create a new rule type definition."""
    return {
        "id": uuid.uuid4(),
        "code": body.code,
        "name": body.name,
        "category": body.category,
        "parameter_schema": body.parameter_schema,
        "description": body.description,
    }


@router.get("/rule-types", response_model=list[RuleTypeResponse])
async def list_rule_types(
    category: str | None = Query(None),
) -> list[dict[str, Any]]:
    """List all rule types, optionally filtered by category."""
    return []


@router.get("/rule-types/{rule_type_id}", response_model=RuleTypeResponse)
async def get_rule_type(rule_type_id: uuid.UUID) -> dict[str, Any]:
    """Get a single rule type by ID."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule type not found")


# ---------------------------------------------------------------------------
# Rule Instances CRUD
# ---------------------------------------------------------------------------


@router.post("/rule-instances", response_model=RuleInstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_rule_instance(
    body: RuleInstanceCreate,
    tenant_id: TenantId,
) -> dict[str, Any]:
    """Create a new rule instance bound to a plan or program."""
    return {
        "id": uuid.uuid4(),
        "rule_type_id": body.rule_type_id,
        "plan_id": body.plan_id,
        "program_id": body.program_id,
        "priority_order": body.priority_order,
        "parameters": body.parameters,
        "version": 1,
        "effective_date": body.effective_date,
        "termination_date": body.termination_date,
        "status": body.status,
        "tenant_id": tenant_id,
    }


@router.get("/rule-instances", response_model=list[RuleInstanceResponse])
async def list_rule_instances(
    tenant_id: TenantId,
    plan_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> list[dict[str, Any]]:
    """List rule instances for the tenant, optionally filtered by plan or status."""
    return []


@router.get("/rule-instances/{instance_id}", response_model=RuleInstanceResponse)
async def get_rule_instance(
    instance_id: uuid.UUID,
    tenant_id: TenantId,
) -> dict[str, Any]:
    """Get a single rule instance by ID."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule instance not found")


@router.put("/rule-instances/{instance_id}", response_model=RuleInstanceResponse)
async def update_rule_instance(
    instance_id: uuid.UUID,
    body: RuleInstanceUpdate,
    tenant_id: TenantId,
) -> dict[str, Any]:
    """Update a rule instance (creates a new version)."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule instance not found")


@router.delete("/rule-instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule_instance(
    instance_id: uuid.UUID,
    tenant_id: TenantId,
) -> None:
    """Soft-delete (deactivate) a rule instance."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule instance not found")


# ---------------------------------------------------------------------------
# Pipelines CRUD
# ---------------------------------------------------------------------------


@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    body: PipelineCreate,
    tenant_id: TenantId,
) -> dict[str, Any]:
    """Create a new rule pipeline for a plan."""
    return {
        "id": uuid.uuid4(),
        "plan_id": body.plan_id,
        "ordered_rule_ids": body.ordered_rule_ids,
        "version": 1,
        "tenant_id": tenant_id,
    }


@router.get("/pipelines", response_model=list[PipelineResponse])
async def list_pipelines(
    tenant_id: TenantId,
    plan_id: uuid.UUID | None = Query(None),
) -> list[dict[str, Any]]:
    """List pipelines, optionally filtered by plan."""
    return []


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: uuid.UUID,
    tenant_id: TenantId,
) -> dict[str, Any]:
    """Get a single pipeline by ID."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")


@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: uuid.UUID,
    body: PipelineUpdate,
    tenant_id: TenantId,
) -> dict[str, Any]:
    """Update a pipeline's ordered rule IDs."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")


# ---------------------------------------------------------------------------
# Pipeline Execution
# ---------------------------------------------------------------------------


@router.post("/pipelines/{pipeline_id}/execute", response_model=PipelineExecuteResponse)
async def execute_pipeline_endpoint(
    pipeline_id: uuid.UUID,
    body: PipelineExecuteRequest,
    tenant_id: TenantId,
) -> dict[str, Any]:
    """Execute a pipeline against a claim context.

    In production this loads rules from the database. For now, returns
    an empty pipeline result to satisfy the API contract.
    """
    ctx = ClaimContext(
        claim_id=body.claim_id,
        member_id=body.member_id,
        member_age=body.member_age,
        member_state=body.member_state,
        ndc=body.ndc,
        drug_name=body.drug_name,
        drug_type=body.drug_type,
        quantity=Decimal(body.quantity),
        days_supply=body.days_supply,
        pharmacy_npi=body.pharmacy_npi,
        pharmacy_type=body.pharmacy_type,
        prescriber_npi=body.prescriber_npi,
        plan_id=body.plan_id,
        program_id=body.program_id,
        ingredient_cost=Decimal(body.ingredient_cost),
    )

    result = execute_pipeline(ctx, [])

    return {
        "claim_id": result.claim_id,
        "plan_id": result.plan_id,
        "final_action": result.final_action.value,
        "reject_code": result.reject_code,
        "reject_message": result.reject_message,
        "warnings": result.warnings,
        "conflicts": result.conflicts,
        "total_execution_time_ms": result.total_execution_time_ms,
        "results": [],
    }


# ---------------------------------------------------------------------------
# Execution Logs
# ---------------------------------------------------------------------------


@router.get("/execution-logs", response_model=list[ExecutionLogResponse])
async def list_execution_logs(
    tenant_id: TenantId,
    claim_id: uuid.UUID | None = Query(None),
    rule_instance_id: uuid.UUID | None = Query(None),
) -> list[dict[str, Any]]:
    """List rule execution logs, optionally filtered by claim or rule instance."""
    return []
