"""Coverage period routes.

GET  /members/{id}/coverage
POST /members/{id}/coverage
PUT  /members/{id}/coverage/{period_id}
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import CoveragePeriod, Member
from shared.db.tenant_context import current_tenant_id

logger = logging.getLogger("member-management.routes.coverage")

router = APIRouter(tags=["coverage"])


class CoverageCreate(BaseModel):
    plan_name: str | None = None
    coverage_type: str
    effective_date: date
    termination_date: date | None = None
    benefit_year_start: date
    benefit_year_end: date
    plan_id: UUID | None = None


class CoverageUpdate(BaseModel):
    plan_name: str | None = None
    termination_date: date | None = None
    status: str | None = None


def _get_db() -> Session:  # pragma: no cover — overridden in tests
    raise NotImplementedError("DB session dependency must be overridden")


def _serialize_coverage(c: CoveragePeriod) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "member_id": str(c.member_id),
        "tenant_id": str(c.tenant_id),
        "plan_id": str(c.plan_id) if c.plan_id else None,
        "plan_name": c.plan_name,
        "coverage_type": c.coverage_type,
        "effective_date": c.effective_date.isoformat(),
        "termination_date": c.termination_date.isoformat() if c.termination_date else None,
        "benefit_year_start": c.benefit_year_start.isoformat(),
        "benefit_year_end": c.benefit_year_end.isoformat(),
        "status": c.status,
        "created_at": c.created_at.isoformat(),
    }


def _resolve_member(db: Session, member_id: UUID, tid: uuid.UUID) -> Member:
    stmt = select(Member).where(Member.id == member_id, Member.tenant_id == tid)
    member = db.execute(stmt).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MEMBER_NOT_FOUND", "message": "Member not found", "correlation_id": str(uuid.uuid4())}},
        )
    return member


@router.get("/members/{member_id}/coverage", summary="List coverage periods")
async def get_coverage(
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

    stmt = select(CoveragePeriod).where(
        CoveragePeriod.member_id == member_id,
        CoveragePeriod.tenant_id == tid,
    )
    rows = db.execute(stmt).scalars().all()

    return {"member_id": str(member_id), "coverage_periods": [_serialize_coverage(c) for c in rows]}


@router.post("/members/{member_id}/coverage", status_code=201, summary="Add coverage period")
async def add_coverage(
    member_id: UUID,
    body: CoverageCreate,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    _resolve_member(db, member_id, tid)

    coverage = CoveragePeriod(
        id=uuid.uuid4(),
        tenant_id=tid,
        member_id=member_id,
        plan_id=body.plan_id,
        plan_name=body.plan_name,
        coverage_type=body.coverage_type,
        effective_date=body.effective_date,
        termination_date=body.termination_date,
        benefit_year_start=body.benefit_year_start,
        benefit_year_end=body.benefit_year_end,
        status="active",
    )
    db.add(coverage)
    db.commit()
    db.refresh(coverage)

    return _serialize_coverage(coverage)


@router.put("/members/{member_id}/coverage/{period_id}", summary="Update coverage period")
async def update_coverage(
    member_id: UUID,
    period_id: UUID,
    body: CoverageUpdate,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "MISSING_TENANT", "message": "No tenant context", "correlation_id": str(uuid.uuid4())}},
        )

    _resolve_member(db, member_id, tid)

    stmt = select(CoveragePeriod).where(
        CoveragePeriod.id == period_id,
        CoveragePeriod.member_id == member_id,
        CoveragePeriod.tenant_id == tid,
    )
    coverage = db.execute(stmt).scalar_one_or_none()
    if coverage is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "COVERAGE_NOT_FOUND",
                    "message": "Coverage period not found",
                    "correlation_id": str(uuid.uuid4()),
                }
            },
        )

    if body.plan_name is not None:
        coverage.plan_name = body.plan_name
    if body.termination_date is not None:
        coverage.termination_date = body.termination_date
    if body.status is not None:
        coverage.status = body.status

    db.commit()
    db.refresh(coverage)
    return _serialize_coverage(coverage)
