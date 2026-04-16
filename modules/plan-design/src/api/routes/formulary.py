"""Formulary API routes — drugs, tiers, versioning, F&B v60, P&T committee."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from shared.auth.dependencies import get_current_user

from src.api.dependencies import DBSession, TenantId
from src.api.schemas.formulary import (
    DrugImportRequest,
    DrugImportResponse,
    FBv60PublishRequest,
    FBv60PublishResponse,
    FormularyCreate,
    FormularyDrugCreate,
    FormularyDrugResponse,
    FormularyDrugUpdate,
    FormularyImpactRequest,
    FormularyImpactResponse,
    FormularyResponse,
    FormularyUpdate,
    FormularyVersionResponse,
    PTMeetingCreate,
    PTMeetingResponse,
    PTMeetingUpdate,
)
from src.services.formulary import FormularyService

router = APIRouter(
    prefix="/formularies",
    tags=["formularies"],
    dependencies=[Depends(get_current_user)],
)

# ---------------------------------------------------------------------------
# Formulary CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=FormularyResponse, status_code=status.HTTP_201_CREATED)
async def create_formulary(
    body: FormularyCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    formulary = svc.create_formulary(body.model_dump())
    db.commit()
    return formulary


@router.get("", response_model=list[FormularyResponse])
async def list_formularies(
    status_filter: str | None = None,
    db: DBSession = Depends(),
    tenant_id: TenantId = Depends(),
) -> Any:
    svc = FormularyService(db, tenant_id)
    return svc.list_formularies(status=status_filter)


@router.get("/{formulary_id}", response_model=FormularyResponse)
async def get_formulary(
    formulary_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    formulary = svc.get_formulary(formulary_id)
    if formulary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formulary not found")
    return formulary


@router.patch("/{formulary_id}", response_model=FormularyResponse)
async def update_formulary(
    formulary_id: uuid.UUID,
    body: FormularyUpdate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    formulary = svc.update_formulary(formulary_id, body.model_dump(exclude_none=True))
    if formulary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formulary not found")
    db.commit()
    return formulary


# ---------------------------------------------------------------------------
# Drug Tier Management
# ---------------------------------------------------------------------------


@router.post("/{formulary_id}/drugs", response_model=FormularyDrugResponse, status_code=status.HTTP_201_CREATED)
async def add_drug(
    formulary_id: uuid.UUID,
    body: FormularyDrugCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    drug = svc.add_drug(formulary_id, body.model_dump())
    db.commit()
    return drug


@router.get("/{formulary_id}/drugs", response_model=list[FormularyDrugResponse])
async def list_drugs(
    formulary_id: uuid.UUID,
    ndc: str | None = None,
    tier: str | None = None,
    db: DBSession = Depends(),
    tenant_id: TenantId = Depends(),
) -> Any:
    svc = FormularyService(db, tenant_id)
    return svc.list_drugs(formulary_id, ndc=ndc, tier=tier)


@router.patch("/{formulary_id}/drugs/{drug_id}", response_model=FormularyDrugResponse)
async def update_drug(
    formulary_id: uuid.UUID,
    drug_id: uuid.UUID,
    body: FormularyDrugUpdate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    drug = svc.update_drug(drug_id, body.model_dump(exclude_none=True))
    if drug is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug not found")
    db.commit()
    return drug


@router.post("/{formulary_id}/drugs/import", response_model=DrugImportResponse)
async def import_drugs(
    formulary_id: uuid.UUID,
    body: DrugImportRequest,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    drugs_data = [d.model_dump() for d in body.drugs]
    result = svc.bulk_import_drugs(formulary_id, drugs_data)
    db.commit()
    return result


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------


@router.get("/{formulary_id}/versions", response_model=list[FormularyVersionResponse])
async def list_versions(
    formulary_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    return svc.list_versions(formulary_id)


@router.post("/{formulary_id}/snapshot", response_model=FormularyVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    formulary_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
    current_user: Any = Depends(get_current_user),
) -> Any:
    svc = FormularyService(db, tenant_id)
    try:
        version = svc.create_version_snapshot(
            formulary_id,
            created_by=current_user.id,
        )
        db.commit()
        return version
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# F&B v60 Publication
# ---------------------------------------------------------------------------


@router.post("/{formulary_id}/publish-fb60", response_model=FBv60PublishResponse, status_code=status.HTTP_201_CREATED)
async def publish_fb60(
    formulary_id: uuid.UUID,
    body: FBv60PublishRequest,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    try:
        pub = svc.publish_fb_v60(formulary_id, publish_to_surescripts=body.publish_to_surescripts)
        db.commit()
        return {
            "publication_id": pub.id,
            "formulary_id": pub.formulary_id,
            "formulary_version": pub.formulary_version,
            "status": pub.status,
            "file_path": pub.file_path,
            "created_at": pub.created_at,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Impact Analysis
# ---------------------------------------------------------------------------


@router.post("/{formulary_id}/impact-analysis", response_model=FormularyImpactResponse)
async def impact_analysis(
    formulary_id: uuid.UUID,
    body: FormularyImpactRequest,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    result = svc.formulary_impact_analysis(
        formulary_id,
        proposed_changes=body.proposed_changes,
        analysis_date=body.analysis_date,
    )
    return result


# ---------------------------------------------------------------------------
# Biosimilar Tools
# ---------------------------------------------------------------------------


@router.get("/{formulary_id}/biosimilars/{reference_ndc}", response_model=list[FormularyDrugResponse])
async def get_biosimilar_alternatives(
    formulary_id: uuid.UUID,
    reference_ndc: str,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    return svc.get_biosimilar_alternatives(formulary_id, reference_ndc)


# ---------------------------------------------------------------------------
# P&T Committee
# ---------------------------------------------------------------------------

pt_router = APIRouter(
    prefix="/pt-meetings",
    tags=["pt-committee"],
    dependencies=[Depends(get_current_user)],
)


@pt_router.post("", response_model=PTMeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_pt_meeting(
    body: PTMeetingCreate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    meeting = svc.create_pt_meeting(body.model_dump())
    db.commit()
    return meeting


@pt_router.get("/{meeting_id}", response_model=PTMeetingResponse)
async def get_pt_meeting(
    meeting_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    meeting = svc.get_pt_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


@pt_router.patch("/{meeting_id}", response_model=PTMeetingResponse)
async def update_pt_meeting(
    meeting_id: uuid.UUID,
    body: PTMeetingUpdate,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    svc = FormularyService(db, tenant_id)
    meeting = svc.update_pt_meeting(meeting_id, body.model_dump(exclude_none=True))
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    db.commit()
    return meeting
