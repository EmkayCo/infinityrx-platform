"""Member CRUD and search API routes."""
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

from src.api.schemas.member import (
    MemberCreate,
    MemberTerminate,
    MemberUpdate,
    PhiAccessLevel,
)
from src.models.tables import Member
from src.services.member_service import MemberService
from shared.db.tenant_context import current_tenant_id, set_tenant_context

logger = logging.getLogger("member-management.routes.members")

router = APIRouter(tags=["members"])

_svc = MemberService()

_CORRELATION_ID_KEY = "correlation_id"


def _get_db() -> Session:  # pragma: no cover — overridden in tests
    """Placeholder; tests override this dependency."""
    raise NotImplementedError("DB session dependency must be overridden")


def _serialize_member(m: Member, access_level: PhiAccessLevel) -> dict[str, Any]:
    """Serialize Member ORM row to dict, masking PHI per access level.

    EncryptedString TypeDecorator decrypts transparently on read.
    We never log the decrypted values here.
    """
    raw: dict[str, Any] = {
        "id": str(m.id),
        "tenant_id": str(m.tenant_id),
        "member_id": m.member_id,
        "person_code": m.person_code,
        "cardholder_id": m.cardholder_id,
        "alternate_id": m.alternate_id,
        "first_name": m.first_name_encrypted,
        "middle_name": m.middle_name_encrypted,
        "last_name": m.last_name_encrypted,
        "suffix": m.suffix,
        "date_of_birth": m.dob_encrypted,
        "gender": m.gender,
        "ssn": m.ssn_encrypted,
        "address_line_1": m.address_line_1_encrypted,
        "address_line_2": m.address_line_2_encrypted,
        "city": m.city_encrypted,
        "state": m.state_encrypted,
        "zip_code": m.zip_code_encrypted,
        "country": m.country,
        "phone": m.phone_encrypted,
        "email": m.email_encrypted,
        "preferred_language": m.preferred_language,
        "relationship_code": m.relationship_code,
        "group_id": str(m.group_id) if m.group_id else None,
        "rx_bin": m.rx_bin,
        "rx_pcn": m.rx_pcn,
        "rx_group": m.rx_group,
        "status": m.status,
        "enrollment_date": m.enrollment_date.isoformat() if m.enrollment_date else None,
        "termination_date": m.termination_date.isoformat() if m.termination_date else None,
        "termination_reason": m.termination_reason,
        "is_medicare": m.is_medicare,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat(),
    }
    return _svc.mask_phi(raw, access_level)


@router.get("", summary="Search/list members")
async def list_members(
    member_id: str | None = Query(None),
    status: str | None = Query(None),
    group_id: UUID | None = Query(None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    phi_access: PhiAccessLevel = Query(default=PhiAccessLevel.PARTIAL),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(Member).where(Member.tenant_id == tid)
    if member_id is not None:
        stmt = stmt.where(Member.member_id == member_id)
    if status is not None:
        stmt = stmt.where(Member.status == status)
    if group_id is not None:
        stmt = stmt.where(Member.group_id == group_id)

    stmt = stmt.offset(offset).limit(limit)

    result = db.execute(stmt)
    rows = result.scalars().all()

    members_out = [_serialize_member(m, phi_access) for m in rows]
    return {"members": members_out, "total": len(members_out), "limit": limit, "offset": offset}


@router.post("", status_code=201, summary="Create member (manual enrollment)")
async def create_member(
    body: MemberCreate,
    phi_access: PhiAccessLevel = Query(default=PhiAccessLevel.PARTIAL),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    member = Member(
        id=uuid.uuid4(),
        tenant_id=tid,
        member_id=body.member_id,
        person_code=body.person_code,
        cardholder_id=body.cardholder_id,
        alternate_id=body.alternate_id,
        first_name_encrypted=body.first_name,
        middle_name_encrypted=body.middle_name,
        last_name_encrypted=body.last_name,
        suffix=body.suffix,
        dob_encrypted=body.date_of_birth,
        gender=body.gender,
        ssn_encrypted=body.ssn,
        address_line_1_encrypted=body.address_line_1,
        address_line_2_encrypted=body.address_line_2,
        city_encrypted=body.city,
        state_encrypted=body.state,
        zip_code_encrypted=body.zip_code,
        country=body.country,
        phone_encrypted=body.phone,
        email_encrypted=body.email,
        preferred_language=body.preferred_language,
        relationship_code=body.relationship_code,
        rx_bin=body.rx_bin,
        rx_pcn=body.rx_pcn,
        rx_group=body.rx_group,
        status="active",
        enrollment_date=date.fromisoformat(body.effective_date),
    )

    try:
        db.add(member)
        db.commit()
        db.refresh(member)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "DUPLICATE_MEMBER",
                    "message": f"Member with member_id={body.member_id!r} and person_code={body.person_code!r} already exists for this tenant",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
        )

    logger.info(
        "Member created",
        extra={"svc_member_uuid": str(member.id), "auth_tenant_id": str(tid)},
    )
    return _serialize_member(member, phi_access)


@router.get("/{member_uuid}", summary="Member detail")
async def get_member(
    member_uuid: UUID,
    phi_access: PhiAccessLevel = Query(default=PhiAccessLevel.PARTIAL),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(Member).where(Member.id == member_uuid, Member.tenant_id == tid)
    result = db.execute(stmt)
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}},
        )

    logger.info(
        "PHI access: member detail",
        extra={"svc_member_uuid": str(member_uuid), "auth_tenant_id": str(tid), "audit_action": "phi_access"},
    )
    return _serialize_member(member, phi_access)


@router.put("/{member_uuid}", summary="Update member demographics")
async def update_member(
    member_uuid: UUID,
    body: MemberUpdate,
    phi_access: PhiAccessLevel = Query(default=PhiAccessLevel.PARTIAL),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(Member).where(Member.id == member_uuid, Member.tenant_id == tid)
    result = db.execute(stmt)
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}},
        )

    if body.first_name is not None:
        member.first_name_encrypted = body.first_name
    if body.middle_name is not None:
        member.middle_name_encrypted = body.middle_name
    if body.last_name is not None:
        member.last_name_encrypted = body.last_name
    if body.suffix is not None:
        member.suffix = body.suffix
    if body.date_of_birth is not None:
        member.dob_encrypted = body.date_of_birth
    if body.gender is not None:
        member.gender = body.gender
    if body.ssn is not None:
        member.ssn_encrypted = body.ssn
    if body.address_line_1 is not None:
        member.address_line_1_encrypted = body.address_line_1
    if body.address_line_2 is not None:
        member.address_line_2_encrypted = body.address_line_2
    if body.city is not None:
        member.city_encrypted = body.city
    if body.state is not None:
        member.state_encrypted = body.state
    if body.zip_code is not None:
        member.zip_code_encrypted = body.zip_code
    if body.phone is not None:
        member.phone_encrypted = body.phone
    if body.email is not None:
        member.email_encrypted = body.email
    if body.preferred_language is not None:
        member.preferred_language = body.preferred_language

    db.commit()
    db.refresh(member)
    return _serialize_member(member, phi_access)


@router.post("/{member_uuid}/terminate", summary="Terminate member")
async def terminate_member(
    member_uuid: UUID,
    body: MemberTerminate,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(Member).where(Member.id == member_uuid, Member.tenant_id == tid)
    result = db.execute(stmt)
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}},
        )

    member.status = "terminated"
    member.termination_date = date.fromisoformat(body.termination_date)
    member.termination_reason = body.termination_reason
    db.commit()

    logger.info(
        "Member terminated",
        extra={"svc_member_uuid": str(member_uuid), "auth_tenant_id": str(tid)},
    )
    return {"id": str(member_uuid), "status": "terminated", "termination_date": body.termination_date}


@router.get("/{member_uuid}/id-card", summary="ID card data")
async def get_id_card(
    member_uuid: UUID,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    stmt = select(Member).where(Member.id == member_uuid, Member.tenant_id == tid)
    result = db.execute(stmt)
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}},
        )

    return {
        "member_id": member.member_id,
        "person_code": member.person_code,
        "rx_bin": member.rx_bin,
        "rx_pcn": member.rx_pcn,
        "rx_group": member.rx_group,
        "cardholder_id": member.cardholder_id,
    }
