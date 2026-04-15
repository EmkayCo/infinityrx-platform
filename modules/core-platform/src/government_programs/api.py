"""Government Programs API — Anti-Kickback Statute BIN/PCN compliance.

Endpoints:
  GET  /api/v1/government-programs/check           — is_government_plan lookup
  GET  /api/v1/government-programs/copay-eligibility — copay card AKS gate
  GET  /api/v1/government-programs/bins             — list / filter BIN table
  GET  /api/v1/government-programs/bins/{id}        — single BIN entry
  POST /api/v1/government-programs/bins             — add entry (admin)
  PUT  /api/v1/government-programs/bins/{id}        — update entry (admin)
  DELETE /api/v1/government-programs/bins/{id}      — delete entry (admin)
  POST /api/v1/government-programs/import           — CSV upload (admin)
  GET  /api/v1/government-programs/coverage-report  — summary stats

LESSON-011: GovernmentProgramBin is global reference data — no tenant_id filter.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from shared.models.gov_exclusion_tables import VALID_CONFIDENCE_LEVELS, VALID_PLAN_TYPES, GovernmentProgramBin
from shared.services.gov_exclusion_service import (
    CopayCardEligibility,
    GovernmentCheckResult,
    GovernmentExclusionService,
    GovernmentPlanInfo,
)

from .._shim.auth import CurrentUser, current_user, require_role
from .._shim.db import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/government-programs", tags=["government-programs"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class GovernmentPlanInfoOut(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: str
    bin: str
    pcn: Optional[str]
    group_number: Optional[str]
    plan_type: str
    plan_subtype: Optional[str]
    pbm_name: Optional[str]
    plan_name: Optional[str]
    mco_name: Optional[str]
    state: Optional[str]
    confidence: str
    notes: Optional[str]


class GovernmentCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    is_government: bool
    confidence: str
    match_type: Optional[str]
    plans: list[GovernmentPlanInfoOut]


class CopayEligibilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    eligible: bool
    status: str
    reason: str
    government_check: GovernmentCheckOut


class GovernmentBinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bin: str
    pcn: Optional[str]
    group_number: Optional[str]
    plan_type: str
    plan_subtype: Optional[str]
    pbm_name: Optional[str]
    plan_name: Optional[str]
    mco_name: Optional[str]
    state: Optional[str]
    government_flag: bool
    occ_codes: Optional[str]
    confidence: str
    source: str
    source_date: Optional[date]
    effective_date: Optional[date]
    end_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class GovernmentBinCreate(BaseModel):
    bin: str = Field(pattern=r"\A\d{6}\Z", description="6-digit BIN")
    pcn: Optional[str] = Field(default=None, max_length=20)
    group_number: Optional[str] = Field(default=None, max_length=20)
    plan_type: str
    plan_subtype: Optional[str] = None
    pbm_name: Optional[str] = None
    plan_name: Optional[str] = None
    mco_name: Optional[str] = None
    state: Optional[str] = Field(default=None, max_length=2)
    occ_codes: Optional[str] = None
    confidence: str = "HIGH"
    source: str
    source_date: Optional[date] = None
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("plan_type")
    @classmethod
    def validate_plan_type(cls, v: str) -> str:
        if v not in VALID_PLAN_TYPES:
            raise ValueError(f"plan_type must be one of: {sorted(VALID_PLAN_TYPES)}")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        if v not in VALID_CONFIDENCE_LEVELS:
            raise ValueError(f"confidence must be one of: {sorted(VALID_CONFIDENCE_LEVELS)}")
        return v


class GovernmentBinUpdate(BaseModel):
    plan_type: Optional[str] = None
    plan_subtype: Optional[str] = None
    pbm_name: Optional[str] = None
    plan_name: Optional[str] = None
    mco_name: Optional[str] = None
    state: Optional[str] = None
    occ_codes: Optional[str] = None
    confidence: Optional[str] = None
    source: Optional[str] = None
    source_date: Optional[date] = None
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("plan_type")
    @classmethod
    def validate_plan_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PLAN_TYPES:
            raise ValueError(f"plan_type must be one of: {sorted(VALID_PLAN_TYPES)}")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CONFIDENCE_LEVELS:
            raise ValueError(f"confidence must be one of: {sorted(VALID_CONFIDENCE_LEVELS)}")
        return v


class ImportResult(BaseModel):
    rows_processed: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    rows_errored: int
    errors: list[dict[str, Any]]


class CoverageReport(BaseModel):
    total_entries: int
    by_plan_type: dict[str, int]
    states_covered: int
    medium_confidence_count: int
    low_confidence_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan_info_to_out(p: GovernmentPlanInfo) -> GovernmentPlanInfoOut:
    return GovernmentPlanInfoOut(
        id=p.id,
        bin=p.bin,
        pcn=p.pcn,
        group_number=p.group_number,
        plan_type=p.plan_type,
        plan_subtype=p.plan_subtype,
        pbm_name=p.pbm_name,
        plan_name=p.plan_name,
        mco_name=p.mco_name,
        state=p.state,
        confidence=p.confidence,
        notes=p.notes,
    )


def _check_to_out(c: GovernmentCheckResult) -> GovernmentCheckOut:
    return GovernmentCheckOut(
        is_government=c.is_government,
        confidence=c.confidence,
        match_type=c.match_type,
        plans=[_plan_info_to_out(p) for p in c.plans],
    )


def _eligibility_to_out(e: CopayCardEligibility) -> CopayEligibilityOut:
    return CopayEligibilityOut(
        eligible=e.eligible,
        status=e.status,
        reason=e.reason,
        government_check=_check_to_out(e.government_check),
    )


# ---------------------------------------------------------------------------
# Read endpoints (no auth required — reference data)
# ---------------------------------------------------------------------------


@router.get("/check", response_model=GovernmentCheckOut)
async def check_government_plan(
    bin: str = Query(description="6-digit BIN"),
    pcn: Optional[str] = Query(default=None),
    group: Optional[str] = Query(default=None),
    occ: Optional[str] = Query(default=None),
    db: Session = Depends(get_session),
) -> GovernmentCheckOut:
    """Check whether a BIN/PCN/Group is a government program."""
    svc = GovernmentExclusionService(db)
    result = svc.is_government_plan(bin=bin, pcn=pcn, group=group, occ=occ)
    return _check_to_out(result)


@router.get("/copay-eligibility", response_model=CopayEligibilityOut)
async def check_copay_eligibility(
    bin: str = Query(description="6-digit BIN"),
    pcn: Optional[str] = Query(default=None),
    group: Optional[str] = Query(default=None),
    occ: Optional[str] = Query(default=None),
    db: Session = Depends(get_session),
) -> CopayEligibilityOut:
    """Determine whether a copay card may be applied (AKS gate)."""
    svc = GovernmentExclusionService(db)
    result = svc.check_copay_card_eligibility(bin=bin, pcn=pcn, group=group, occ=occ)
    return _eligibility_to_out(result)


@router.get("/bins", response_model=list[GovernmentBinOut])
async def list_bins(
    plan_type: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    confidence: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> list[GovernmentBinOut]:
    """List government program BIN entries with optional filters."""
    q = db.query(GovernmentProgramBin)
    if plan_type:
        q = q.filter(GovernmentProgramBin.plan_type == plan_type)
    if state:
        q = q.filter(GovernmentProgramBin.state == state.upper())
    if confidence:
        q = q.filter(GovernmentProgramBin.confidence == confidence)
    rows = q.order_by(GovernmentProgramBin.bin, GovernmentProgramBin.pcn).offset(offset).limit(limit).all()
    return [GovernmentBinOut.model_validate(r) for r in rows]


@router.get("/bins/{bin_id}", response_model=GovernmentBinOut)
async def get_bin(
    bin_id: str,
    db: Session = Depends(get_session),
) -> GovernmentBinOut:
    """Get a single government program BIN entry by ID."""
    row = db.query(GovernmentProgramBin).filter(
        GovernmentProgramBin.id == uuid.UUID(bin_id)
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BIN entry not found")
    return GovernmentBinOut.model_validate(row)


@router.get("/coverage-report", response_model=CoverageReport)
async def coverage_report(
    db: Session = Depends(get_session),
) -> CoverageReport:
    """Summary statistics for the government program BIN table."""
    rows: list[GovernmentProgramBin] = db.query(GovernmentProgramBin).all()
    by_type: dict[str, int] = {}
    states: set[str] = set()
    medium = 0
    low = 0
    for r in rows:
        by_type[r.plan_type] = by_type.get(r.plan_type, 0) + 1
        if r.state:
            states.add(r.state)
        if r.confidence == "MEDIUM":
            medium += 1
        elif r.confidence == "LOW":
            low += 1
    return CoverageReport(
        total_entries=len(rows),
        by_plan_type=by_type,
        states_covered=len(states),
        medium_confidence_count=medium,
        low_confidence_count=low,
    )


# ---------------------------------------------------------------------------
# Admin write endpoints
# ---------------------------------------------------------------------------


@router.post("/bins", response_model=GovernmentBinOut, status_code=status.HTTP_201_CREATED)
async def create_bin(
    body: GovernmentBinCreate,
    caller: CurrentUser = Depends(require_role("platform_admin")),
    db: Session = Depends(get_session),
) -> GovernmentBinOut:
    """Add a government program BIN entry (admin only)."""
    existing = (
        db.query(GovernmentProgramBin)
        .filter(
            GovernmentProgramBin.bin == body.bin,
            GovernmentProgramBin.pcn == body.pcn,
            GovernmentProgramBin.group_number == body.group_number,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A BIN entry with this bin/pcn/group_number already exists.",
        )
    entry = GovernmentProgramBin(
        id=uuid.uuid4(),
        **body.model_dump(),
        updated_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return GovernmentBinOut.model_validate(entry)


@router.put("/bins/{bin_id}", response_model=GovernmentBinOut)
async def update_bin(
    bin_id: str,
    body: GovernmentBinUpdate,
    caller: CurrentUser = Depends(require_role("platform_admin")),
    db: Session = Depends(get_session),
) -> GovernmentBinOut:
    """Update a government program BIN entry (admin only)."""
    try:
        uid = uuid.UUID(bin_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid ID format")
    row = db.query(GovernmentProgramBin).filter(GovernmentProgramBin.id == uid).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BIN entry not found")
    for field_name, value in body.model_dump(exclude_none=True).items():
        setattr(row, field_name, value)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return GovernmentBinOut.model_validate(row)


@router.delete("/bins/{bin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bin(
    bin_id: str,
    caller: CurrentUser = Depends(require_role("platform_admin")),
    db: Session = Depends(get_session),
) -> None:
    """Delete a government program BIN entry (admin only)."""
    try:
        uid = uuid.UUID(bin_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid ID format")
    row = db.query(GovernmentProgramBin).filter(GovernmentProgramBin.id == uid).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BIN entry not found")
    db.delete(row)
    db.commit()


@router.post("/import", response_model=ImportResult)
async def import_csv(
    file: UploadFile = File(description="CSV file with government program BINs"),
    caller: CurrentUser = Depends(require_role("platform_admin")),
    db: Session = Depends(get_session),
) -> ImportResult:
    """Import government program BINs from a CSV file (admin only)."""
    from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

    content = await file.read()
    result = await load_state_medicaid_csv_from_bytes(content, db)
    return ImportResult(
        rows_processed=result.records_processed,
        rows_inserted=result.records_inserted,
        rows_updated=result.records_updated,
        rows_skipped=result.records_skipped,
        rows_errored=result.records_errored,
        errors=result.error_details if hasattr(result, "error_details") else [],
    )


__all__ = ["router"]
