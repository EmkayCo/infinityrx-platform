"""Exclusions REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .._shim.auth import CurrentUser, current_user, require_role
from .._shim.db import get_session
from ..models import ExclusionMatch
from .matching import MatchCandidate
from .screening_service import ExclusionScreeningService

router = APIRouter(prefix="/exclusions", tags=["exclusions"])


class ExclusionMatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    exclusion_list_id: Optional[int]
    matched_entity_type: str
    matched_entity_id: str
    match_confidence: str
    status: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    review_reason: Optional[str]
    match_metadata: Optional[Dict[str, Any]]
    created_at: datetime


class ReviewBody(BaseModel):
    action: str = Field(pattern="^(confirm|dismiss)$")
    reason: Optional[str] = None


class ScreenBody(BaseModel):
    entity_type: str
    entity_id: str
    npi: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    state: Optional[str] = None
    organization_name: Optional[str] = None


@router.get("/matches", response_model=List[ExclusionMatchOut], dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
def list_matches(
    status: Optional[str] = None,
    confidence: Optional[str] = None,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> List[ExclusionMatchOut]:
    stmt = select(ExclusionMatch).where(ExclusionMatch.tenant_id == str(user.tenant_id))
    if status:
        stmt = stmt.where(ExclusionMatch.status == status)
    if confidence:
        stmt = stmt.where(ExclusionMatch.match_confidence == confidence)
    stmt = stmt.order_by(ExclusionMatch.created_at.desc())
    rows = session.execute(stmt).scalars().all()
    return [ExclusionMatchOut.model_validate(r) for r in rows]


@router.put("/matches/{match_id}", response_model=ExclusionMatchOut, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
def review_match(
    match_id: str,
    body: ReviewBody,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> ExclusionMatchOut:
    row = session.get(ExclusionMatch, match_id)
    if row is None or row.tenant_id != str(user.tenant_id):
        raise HTTPException(status_code=404, detail={"error": "match_not_found"})
    svc = ExclusionScreeningService(session)
    if body.action == "confirm":
        result = svc.confirm(match_id=match_id, user_id=str(user.id))
    else:
        if not body.reason:
            raise HTTPException(status_code=422, detail={"error": "dismiss_reason_required"})
        try:
            result = svc.dismiss(match_id=match_id, user_id=str(user.id), reason=body.reason)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"error": "invalid_reason", "message": str(exc)}) from exc
    return ExclusionMatchOut.model_validate(result)


@router.post("/screen", response_model=List[ExclusionMatchOut], dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
def screen_entity(
    body: ScreenBody,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> List[ExclusionMatchOut]:
    svc = ExclusionScreeningService(session)
    candidate = MatchCandidate(
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        npi=body.npi,
        first_name=body.first_name,
        last_name=body.last_name,
        state=body.state,
        organization_name=body.organization_name,
    )
    matches = svc.screen_entity(tenant_id=str(user.tenant_id), entity=candidate)
    return [ExclusionMatchOut.model_validate(m) for m in matches]


@router.get("/status", dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
def exclusion_status(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> dict:
    svc = ExclusionScreeningService(session)
    return svc.status(tenant_id=str(user.tenant_id))
