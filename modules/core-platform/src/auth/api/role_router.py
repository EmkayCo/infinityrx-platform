"""/roles and /permissions routers."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from shared.auth.dependencies import CurrentUser, get_current_user, tenant_admin_only
from src.auth._db import get_session
from src.auth.audit_sink import AuditSink
from src.auth.deps import get_audit_sink
from src.auth.schemas import (
    PermissionResponse,
    RoleCreate,
    RolePermissions,
    RoleResponse,
    RoleUpdate,
)
from src.auth.service import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    assign_role_permissions,
    create_role,
    list_permissions,
    list_roles,
    update_role,
)

router = APIRouter(tags=["roles"])


def _role_response(role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        tenant_id=role.tenant_id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=sorted(p.code for p in role.permissions),
    )


@router.get("/roles", response_model=list[RoleResponse])
def list_roles_(
    caller: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[RoleResponse]:
    return [_role_response(r) for r in list_roles(session, caller.tenant_id)]


@router.post("/roles", response_model=RoleResponse, status_code=201)
def create_role_(
    body: RoleCreate,
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> RoleResponse:
    try:
        role = create_role(
            session,
            tenant_id=caller.tenant_id,
            name=body.name,
            description=body.description,
            actor_id=caller.id,
            audit=audit,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": str(exc)})
    return _role_response(role)


@router.put("/roles/{role_id}", response_model=RoleResponse)
def update_role_(
    role_id: uuid.UUID,
    body: RoleUpdate,
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> RoleResponse:
    try:
        role = update_role(
            session,
            tenant_id=caller.tenant_id,
            role_id=role_id,
            description=body.description,
            actor_id=caller.id,
            audit=audit,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": str(exc)})
    return _role_response(role)


@router.put("/roles/{role_id}/permissions", response_model=RoleResponse)
def assign_role_permissions_(
    role_id: uuid.UUID,
    body: RolePermissions,
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> RoleResponse:
    try:
        role = assign_role_permissions(
            session,
            tenant_id=caller.tenant_id,
            role_id=role_id,
            permission_codes=body.permissions,
            actor_id=caller.id,
            audit=audit,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": str(exc)})
    return _role_response(role)


@router.get("/permissions", response_model=list[PermissionResponse])
def list_permissions_(
    caller: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[PermissionResponse]:
    return [
        PermissionResponse(
            id=p.id,
            module=p.module,
            action=p.action,
            description=p.description,
            code=p.code,
        )
        for p in list_permissions(session)
    ]
