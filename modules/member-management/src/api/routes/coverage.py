"""Coverage period routes.

GET  /members/{id}/coverage
POST /members/{id}/coverage
PUT  /members/{id}/coverage/{period_id}
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


@router.get("/members/{member_id}/coverage", summary="List coverage periods")
async def get_coverage(member_id: UUID) -> dict[str, Any]:
    return {"member_id": str(member_id), "coverage_periods": []}


@router.post("/members/{member_id}/coverage", status_code=201, summary="Add coverage period")
async def add_coverage(member_id: UUID, body: CoverageCreate) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "member_id": str(member_id),
        "coverage_type": body.coverage_type,
        "effective_date": body.effective_date.isoformat(),
        "benefit_year_start": body.benefit_year_start.isoformat(),
        "benefit_year_end": body.benefit_year_end.isoformat(),
        "status": "active",
    }


@router.put("/members/{member_id}/coverage/{period_id}", summary="Update coverage period")
async def update_coverage(
    member_id: UUID,
    period_id: UUID,
    body: CoverageUpdate,
) -> dict[str, Any]:
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
