"""COB (Coordination of Benefits) routes.

GET    /members/{id}/cob
POST   /members/{id}/cob
PUT    /members/{id}/cob/{cob_id}
DELETE /members/{id}/cob/{cob_id}
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.models.tables import CobRecord, Member
from src.services.cob_service import CobSequence
from shared.db.tenant_context import current_tenant_id

logger = logging.getLogger("member-management.routes.cob")

router = APIRouter(tags=["cob"])

_VALID_SEQUENCES = {s.value for s in CobSequence}


class CobCreate(BaseModel):
    payer_sequence: str
    other_payer_name: str | None = None
    other_payer_bin: str | None = None
    other_payer_pcn: str | None = None
    other_payer_group: str | None = None
    other_payer_member_id: str | None = None
    other_payer_type: str | None = None
    effective_date: date
    termination_date: date | None = None

    @field_validator("payer_sequence")
    @classmethod
    def validate_payer_sequence(cls, v: str) -> str:
        if v not in _VALID_SEQUENCES:
            raise ValueError(f"payer_sequence must be one of: {sorted(_VALID_SEQUENCES)}")
        return v


class CobUpdate(BaseModel):
    termination_date: date | None = None
    other_payer_name: str | None = None


def _get_db() -> Session:  # pragma: no cover — overridden in tests
    raise NotImplementedError("DB session dependency must be overridden")


def _serialize_cob(c: CobRecord) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "member_id": str(c.member_id),
        "payer_sequence": c.payer_sequence,
        "other_payer_name": c.other_payer_name,
        "other_payer_bin": c.other_payer_bin,
        "other_payer_pcn": c.other_payer_pcn,
        "other_payer_group": c.other_payer_group,
        "other_payer_member_id": c.other_payer_member_id,
        "other_payer_type": c.other_payer_type,
        "effective_date": c.effective_date.isoformat(),
        "termination_date": c.termination_date.isoformat() if c.termination_date else None,
        "created_at": c.created_at.isoformat(),
    }


def _resolve_member(db: Session, member_id: UUID, tid: uuid.UUID) -> Member:
    """Return Member row for tenant; raise 404 if missing."""
    stmt = select(Member).where(Member.id == member_id, Member.tenant_id == tid)
    member = db.execute(stmt).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}},
        )
    return member


@router.get("/members/{member_id}/cob", summary="List COB records (active only)")
async def get_cob(
    member_id: UUID,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    _resolve_member(db, member_id, tid)

    today = date.today()
    stmt = select(CobRecord).where(
        and_(
            CobRecord.member_id == member_id,
            CobRecord.tenant_id == tid,
            CobRecord.effective_date <= today,
        )
    ).where(
        (CobRecord.termination_date.is_(None)) | (CobRecord.termination_date > today)
    )
    rows = db.execute(stmt).scalars().all()

    return {"member_id": str(member_id), "cob_records": [_serialize_cob(c) for c in rows]}


@router.post("/members/{member_id}/cob", status_code=201, summary="Add COB record")
async def add_cob(
    member_id: UUID,
    body: CobCreate,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    _resolve_member(db, member_id, tid)

    cob = CobRecord(
        id=uuid.uuid4(),
        tenant_id=tid,
        member_id=member_id,
        payer_sequence=body.payer_sequence,
        other_payer_name=body.other_payer_name,
        other_payer_bin=body.other_payer_bin,
        other_payer_pcn=body.other_payer_pcn,
        other_payer_group=body.other_payer_group,
        other_payer_member_id=body.other_payer_member_id,
        other_payer_type=body.other_payer_type,
        effective_date=body.effective_date,
        termination_date=body.termination_date,
    )
    db.add(cob)
    db.commit()
    db.refresh(cob)

    return _serialize_cob(cob)


@router.put("/members/{member_id}/cob/{cob_id}", summary="Update COB record")
async def update_cob(
    member_id: UUID,
    cob_id: UUID,
    body: CobUpdate,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    _resolve_member(db, member_id, tid)

    stmt = select(CobRecord).where(
        CobRecord.id == cob_id,
        CobRecord.member_id == member_id,
        CobRecord.tenant_id == tid,
    )
    cob = db.execute(stmt).scalar_one_or_none()
    if cob is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "COB_NOT_FOUND",
                    "message": "COB record not found",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
        )

    if body.termination_date is not None:
        cob.termination_date = body.termination_date
    if body.other_payer_name is not None:
        cob.other_payer_name = body.other_payer_name

    db.commit()
    db.refresh(cob)
    return _serialize_cob(cob)


@router.delete("/members/{member_id}/cob/{cob_id}", status_code=204, summary="Remove COB record")
async def delete_cob(
    member_id: UUID,
    cob_id: UUID,
    db: Session = Depends(_get_db),
) -> None:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    _resolve_member(db, member_id, tid)

    stmt = select(CobRecord).where(
        CobRecord.id == cob_id,
        CobRecord.member_id == member_id,
        CobRecord.tenant_id == tid,
    )
    cob = db.execute(stmt).scalar_one_or_none()
    if cob is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "COB_NOT_FOUND",
                    "message": "COB record not found",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
        )

    db.delete(cob)
    db.commit()
