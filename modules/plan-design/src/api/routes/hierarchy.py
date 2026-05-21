"""Hierarchy API routes — organizations, groups, plans, subgroups, program types."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
import io

from shared.auth.dependencies import get_current_user, CurrentUser

from src.api.dependencies import DBSession, TenantId
from src.api.schemas.hierarchy import (
    BulkImportResponse,
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    PlanCloneRequest,
    PlanCreate,
    PlanPromoteRequest,
    PlanResolveResponse,
    PlanResponse,
    PlanRollbackRequest,
    PlanUpdate,
    ProgramTypeCreate,
    ProgramTypeResponse,
    SubGroupCreate,
    SubGroupResponse,
    SubGroupUpdate,
)
from src.services.hierarchy import HierarchyService

router = APIRouter(
    prefix="/hierarchy",
    tags=["hierarchy"],
    dependencies=[Depends(get_current_user)],
)

# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    org = svc.create_organization(body.model_dump(by_alias=False))
    db.commit()
    return org


@router.get("/organizations", response_model=list[OrganizationResponse])
async def list_organizations(
    db: DBSession,
    tenant_id: TenantId,
    status_filter: str | None = None,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    return svc.list_organizations(status=status_filter)


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    org = svc.get_organization(org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.patch("/organizations/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    org = svc.update_organization(org_id, body.model_dump(exclude_none=True, by_alias=False))
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    db.commit()
    return org


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    group = svc.create_group(body.model_dump())
    db.commit()
    return group


@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(
    db: DBSession,
    tenant_id: TenantId,
    organization_id: uuid.UUID | None = None,
    status_filter: str | None = None,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    return svc.list_groups(organization_id=organization_id, status=status_filter)


@router.get("/groups/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    group = svc.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


@router.patch("/groups/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: uuid.UUID,
    body: GroupUpdate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    group = svc.update_group(group_id, body.model_dump(exclude_none=True))
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    db.commit()
    return group


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: PlanCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    plan = svc.create_plan(body.model_dump())
    db.commit()
    return plan


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    db: DBSession,
    tenant_id: TenantId,
    group_id: uuid.UUID | None = None,
    status_filter: str | None = None,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    return svc.list_plans(group_id=group_id, status=status_filter)


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    plan = svc.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


@router.patch("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    body: PlanUpdate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    plan = svc.update_plan(plan_id, body.model_dump(exclude_none=True))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    db.commit()
    return plan


@router.get("/plans/{plan_id}/resolve", response_model=PlanResolveResponse)
async def resolve_plan(
    plan_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    result = svc.resolve_plan(plan_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return result


@router.post("/plans/{plan_id}/clone", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def clone_plan(
    plan_id: uuid.UUID,
    body: PlanCloneRequest,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    try:
        clone = svc.clone_plan(
            plan_id,
            new_name=body.new_name,
            target_group_id=body.target_group_id,
            copy_formulary=body.copy_formulary,
            copy_network=body.copy_network,
        )
        db.commit()
        return clone
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/promote", response_model=PlanResponse)
async def promote_plan(
    plan_id: uuid.UUID,
    body: PlanPromoteRequest,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    plan = svc.promote_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    db.commit()
    return plan


@router.post("/plans/{plan_id}/rollback", response_model=PlanResponse)
async def rollback_plan(
    plan_id: uuid.UUID,
    body: PlanRollbackRequest,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    plan = svc.rollback_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    db.commit()
    return plan


@router.post("/plans/bulk-import", response_model=BulkImportResponse)
async def bulk_import_plans(
    file: UploadFile,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    csv_content = (await file.read()).decode("utf-8")
    svc = HierarchyService(db, tenant_id)
    result = svc.bulk_import_plans(csv_content)
    db.commit()
    return result


# ---------------------------------------------------------------------------
# SubGroups
# ---------------------------------------------------------------------------


@router.post("/subgroups", response_model=SubGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_subgroup(
    body: SubGroupCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    sg = svc.create_subgroup(body.model_dump())
    db.commit()
    return sg


@router.get("/plans/{plan_id}/subgroups", response_model=list[SubGroupResponse])
async def list_subgroups(
    plan_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    return svc.list_subgroups(plan_id)


@router.patch("/subgroups/{sg_id}", response_model=SubGroupResponse)
async def update_subgroup(
    sg_id: uuid.UUID,
    body: SubGroupUpdate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    sg = svc.update_subgroup(sg_id, body.model_dump(exclude_none=True))
    if sg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SubGroup not found")
    db.commit()
    return sg


# ---------------------------------------------------------------------------
# Program Types
# ---------------------------------------------------------------------------


@router.post("/program-types", response_model=ProgramTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_program_type(
    body: ProgramTypeCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    pt = svc.create_program_type(body.model_dump())
    db.commit()
    return pt


@router.get("/program-types", response_model=list[ProgramTypeResponse])
async def list_program_types(
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = HierarchyService(db, tenant_id)
    return svc.list_program_types()
