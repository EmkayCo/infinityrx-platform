"""/users router — tenant-scoped user CRUD, locking, role assignment."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shared.auth.dependencies import CurrentUser, tenant_admin_only
from src.auth._db import get_session
from src.auth.audit_sink import AuditSink
from src.auth.deps import get_audit_sink
from src.auth.schemas import (
    RoleAssignment,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from src.auth.service import (
    ConflictError,
    NotFoundError,
    assign_user_roles,
    create_user,
    get_user,
    list_users,
    load_authenticated,
    lock_user,
    unlock_user,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


def _to_response(session: Session, user_id: uuid.UUID) -> UserResponse:
    auth = load_authenticated(session, user_id)
    assert auth is not None
    u = auth.user
    return UserResponse(
        id=u.id,
        tenant_id=u.tenant_id,
        email=u.email,
        display_name=u.display_name,
        status=u.status,
        last_login_at=u.last_login_at,
        failed_login_count=u.failed_login_count,
        mfa_enabled=bool(getattr(u, "mfa_enabled", False)),
        created_at=getattr(u, "created_at", None),
        roles=auth.roles,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create(
    body: UserCreate,
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> UserResponse:
    try:
        user = create_user(
            session,
            tenant_id=caller.tenant_id,
            email=body.email,
            display_name=body.display_name,
            password=body.password,
            role_names=body.role_names,
            actor_id=caller.id,
            audit=audit,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": str(exc)})
    except NotFoundError as exc:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "message": str(exc)})
    return _to_response(session, user.id)


@router.get("", response_model=list[UserResponse])
def list_(
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
) -> list[UserResponse]:
    return [_to_response(session, u.id) for u in list_users(session, caller.tenant_id)]


@router.get("/{user_id}", response_model=UserResponse)
def get_(
    user_id: uuid.UUID,
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
) -> UserResponse:
    try:
        get_user(session, caller.tenant_id, user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    return _to_response(session, user_id)


@router.put("/{user_id}", response_model=UserResponse)
def put_(
    user_id: uuid.UUID,
    body: UserUpdate,
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> UserResponse:
    try:
        update_user(
            session,
            tenant_id=caller.tenant_id,
            user_id=user_id,
            display_name=body.display_name,
            status=body.status,
            actor_id=caller.id,
            audit=audit,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    return _to_response(session, user_id)


@router.put("/{user_id}/roles", response_model=UserResponse)
def put_roles(
    user_id: uuid.UUID,
    body: RoleAssignment,
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> UserResponse:
    try:
        assign_user_roles(
            session,
            tenant_id=caller.tenant_id,
            user_id=user_id,
            role_names=body.role_names,
            actor_id=caller.id,
            audit=audit,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    return _to_response(session, user_id)


@router.post("/{user_id}/lock", response_model=UserResponse)
def lock_(
    user_id: uuid.UUID,
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> UserResponse:
    try:
        lock_user(
            session,
            tenant_id=caller.tenant_id,
            user_id=user_id,
            actor_id=caller.id,
            audit=audit,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    return _to_response(session, user_id)


@router.post("/{user_id}/unlock", response_model=UserResponse)
def unlock_(
    user_id: uuid.UUID,
    caller: CurrentUser = Depends(tenant_admin_only),
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> UserResponse:
    try:
        unlock_user(
            session,
            tenant_id=caller.tenant_id,
            user_id=user_id,
            actor_id=caller.id,
            audit=audit,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    return _to_response(session, user_id)
