"""Group/employer management routes."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.schemas.member import GroupCreate
from src.models.tables import Group, Member
from shared.db.tenant_context import current_tenant_id

logger = logging.getLogger("member-management.routes.groups")

router = APIRouter(prefix="/groups", tags=["groups"])


def _get_db() -> Session:  # pragma: no cover — overridden in tests
    raise NotImplementedError("DB session dependency must be overridden")


def _serialize_group(g: Group) -> dict[str, Any]:
    return {
        "id": str(g.id),
        "tenant_id": str(g.tenant_id),
        "group_number": g.group_number,
        "group_name": g.group_name,
        "employer_name": g.employer_name,
        "employer_tax_id": g.employer_tax_id,
        "contact_email": g.contact_email,
        "contact_phone": g.contact_phone,
        "billing_cycle": g.billing_cycle,
        "payment_terms_days": g.payment_terms_days,
        "effective_date": g.effective_date.isoformat() if g.effective_date else None,
        "termination_date": g.termination_date.isoformat() if g.termination_date else None,
        "is_active": g.is_active,
        "created_at": g.created_at.isoformat(),
    }


@router.get("", summary="List groups (tenant-scoped)")
async def list_groups(
    is_active: bool | None = Query(None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(Group).where(Group.tenant_id == tid)
    if is_active is not None:
        stmt = stmt.where(Group.is_active == is_active)
    stmt = stmt.offset(offset).limit(limit)

    rows = db.execute(stmt).scalars().all()
    return {"groups": [_serialize_group(g) for g in rows], "total": len(rows)}


@router.post("", status_code=201, summary="Create group")
async def create_group(
    body: GroupCreate,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    group = Group(
        id=uuid.uuid4(),
        tenant_id=tid,
        group_number=body.group_number,
        group_name=body.group_name,
        employer_name=body.employer_name,
        employer_tax_id=body.employer_tax_id,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        billing_cycle=body.billing_cycle,
        payment_terms_days=body.payment_terms_days,
        effective_date=date.fromisoformat(body.effective_date),
        default_plan_id=body.default_plan_id,
        is_active=True,
    )

    try:
        db.add(group)
        db.commit()
        db.refresh(group)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "DUPLICATE_GROUP",
                    "message": f"Group number {body.group_number!r} already exists for this tenant",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
        )

    return _serialize_group(group)


@router.put("/{group_id}", summary="Update group")
async def update_group(
    group_id: UUID,
    body: GroupCreate,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(Group).where(Group.id == group_id, Group.tenant_id == tid)
    group = db.execute(stmt).scalar_one_or_none()

    if group is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "GROUP_NOT_FOUND", "message": "Group not found", "correlation_id": str(uuid.uuid4())}},
        )

    group.group_number = body.group_number
    group.group_name = body.group_name
    group.employer_name = body.employer_name
    group.employer_tax_id = body.employer_tax_id
    group.contact_email = body.contact_email
    group.contact_phone = body.contact_phone
    group.billing_cycle = body.billing_cycle
    group.payment_terms_days = body.payment_terms_days
    group.effective_date = date.fromisoformat(body.effective_date)
    if body.default_plan_id is not None:
        group.default_plan_id = body.default_plan_id

    db.commit()
    db.refresh(group)
    return _serialize_group(group)


@router.get("/{group_id}/members", summary="Members in group")
async def get_group_members(
    group_id: UUID,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    # Verify group belongs to tenant first
    grp_stmt = select(Group).where(Group.id == group_id, Group.tenant_id == tid)
    group = db.execute(grp_stmt).scalar_one_or_none()
    if group is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "GROUP_NOT_FOUND", "message": "Group not found", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = (
        select(Member)
        .where(Member.group_id == group_id, Member.tenant_id == tid)
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()

    return {
        "group_id": str(group_id),
        "members": [{"id": str(m.id), "member_id": m.member_id, "status": m.status} for m in rows],
        "total": len(rows),
    }
