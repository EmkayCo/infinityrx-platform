"""Prescriber Directory API router — /api/v1/prescribers/"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.dependencies import DBSession, TenantId
from src.api.schemas.prescriber import (
    BatchLookupResponse,
    ControlledSubstanceAuthResponse,
    CredentialAlertResponse,
    DirectoryStatsResponse,
    NpimportResultResponse,
    PrescriberPharmacyRelationshipResponse,
    PrescriberResponse,
    SearchResponse,
    ValidationResponse,
)
from src.models.tables import CredentialAlert, DataRefreshLog, Prescriber, PrescriberPharmacyRelationship
from src.services.taxonomy_service import TaxonomyService
from src.utils.validators import NpiValidationError, validate_npi

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prescribers", tags=["prescribers"])

_taxonomy_service = TaxonomyService()

# DEA schedule values
_VALID_SCHEDULES = frozenset(["2", "2N", "3", "3N", "4", "5"])


def _get_or_404(db: Session, npi: str) -> Prescriber:
    stmt = select(Prescriber).where(Prescriber.npi == npi)
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PRESCRIBER_NOT_FOUND", "message": f"No prescriber found with NPI {npi}"}},
        )
    return row


# ─── Lookup ────────────────────────────────────────────────────────────────────

@router.get("/lookup/{npi}", response_model=PrescriberResponse)
def lookup_by_npi(npi: str, db: DBSession, tenant_id: TenantId) -> Prescriber:
    try:
        validate_npi(npi)
    except NpiValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_NPI", "message": str(exc)}},
        ) from exc
    logger.info("prescriber_lookup", extra={"prescriber_npi": npi[:4] + "XXXXXX", "svc_tenant": str(tenant_id)})
    return _get_or_404(db, npi)


@router.get("/lookup/dea/{dea_number}", response_model=PrescriberResponse)
def lookup_by_dea(dea_number: str, db: DBSession, tenant_id: TenantId) -> Prescriber:
    # DEA numbers must never appear in logs — redact here
    logger.info("prescriber_dea_lookup", extra={"svc_tenant": str(tenant_id)})
    stmt = select(Prescriber).where(Prescriber.dea_number == dea_number.upper())
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PRESCRIBER_NOT_FOUND", "message": "No prescriber found with that DEA number"}},
        )
    return row


# ─── Search ────────────────────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
def search_prescribers(
    db: DBSession,
    tenant_id: TenantId,
    name: Optional[str] = Query(None),
    specialty: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SearchResponse:
    stmt = select(Prescriber)
    if name:
        stmt = stmt.where(
            Prescriber.display_name.ilike(f"%{name}%")
        )
    if specialty:
        stmt = stmt.where(
            Prescriber.primary_specialty.ilike(f"%{specialty}%")
        )
    if state:
        stmt = stmt.where(Prescriber.practice_state == state.upper()[:2])
    if entity_type:
        stmt = stmt.where(Prescriber.entity_type == entity_type)
    if status_filter:
        stmt = stmt.where(Prescriber.status == status_filter)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    rows = db.execute(stmt).scalars().all()

    return SearchResponse(results=list(rows), total=total, page=page, page_size=page_size)


@router.get("/batch", response_model=BatchLookupResponse)
def batch_lookup(
    db: DBSession,
    tenant_id: TenantId,
    npis: list[str] = Query(..., max_length=100),
) -> BatchLookupResponse:
    stmt = select(Prescriber).where(Prescriber.npi.in_(npis))
    rows = db.execute(stmt).scalars().all()
    found = {row.npi: row for row in rows}
    not_found = [npi for npi in npis if npi not in found]
    return BatchLookupResponse(results=found, not_found=not_found)


# ─── Validation ────────────────────────────────────────────────────────────────

@router.get("/validate/{npi}", response_model=ValidationResponse)
def validate_prescriber(npi: str, db: DBSession, tenant_id: TenantId) -> ValidationResponse:
    try:
        validate_npi(npi)
    except NpiValidationError as exc:
        return ValidationResponse(npi=npi, valid=False, reason=str(exc), reason_code="INVALID_NPI_FORMAT")

    stmt = select(Prescriber).where(Prescriber.npi == npi)
    prescriber = db.execute(stmt).scalar_one_or_none()
    if prescriber is None:
        return ValidationResponse(npi=npi, valid=False, reason="NPI not found in directory", reason_code="NPI_NOT_FOUND")

    if prescriber.status == "deactivated":
        return ValidationResponse(npi=npi, valid=False, reason="NPI has been deactivated", reason_code="NPI_DEACTIVATED")

    if prescriber.status == "excluded":
        return ValidationResponse(npi=npi, valid=False, reason="Prescriber is on exclusion list", reason_code="EXCLUDED")

    if prescriber.status == "inactive":
        return ValidationResponse(npi=npi, valid=False, reason="Prescriber is inactive", reason_code="INACTIVE")

    return ValidationResponse(npi=npi, valid=True)


@router.get("/validate/{npi}/controlled/{schedule}", response_model=ControlledSubstanceAuthResponse)
def validate_controlled_substance(
    npi: str,
    schedule: str,
    db: DBSession,
    tenant_id: TenantId,
) -> ControlledSubstanceAuthResponse:
    schedule_upper = schedule.upper()
    if schedule_upper not in _VALID_SCHEDULES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_SCHEDULE", "message": f"Schedule must be one of {sorted(_VALID_SCHEDULES)}"}},
        )

    try:
        validate_npi(npi)
    except NpiValidationError as exc:
        return ControlledSubstanceAuthResponse(
            npi=npi, schedule=schedule_upper, authorized=False,
            reason=str(exc), reason_code="INVALID_NPI_FORMAT"
        )

    stmt = select(Prescriber).where(Prescriber.npi == npi)
    prescriber = db.execute(stmt).scalar_one_or_none()
    if prescriber is None:
        return ControlledSubstanceAuthResponse(
            npi=npi, schedule=schedule_upper, authorized=False,
            reason="NPI not found", reason_code="NPI_NOT_FOUND"
        )

    if prescriber.status not in ("active",):
        return ControlledSubstanceAuthResponse(
            npi=npi, schedule=schedule_upper, authorized=False,
            reason=f"Prescriber status is {prescriber.status}", reason_code="PRESCRIBER_INACTIVE"
        )

    if not prescriber.dea_number:
        return ControlledSubstanceAuthResponse(
            npi=npi, schedule=schedule_upper, authorized=False,
            reason="No DEA registration on file", reason_code="NO_DEA"
        )

    if prescriber.dea_status != "active":
        return ControlledSubstanceAuthResponse(
            npi=npi, schedule=schedule_upper, authorized=False,
            reason=f"DEA status is {prescriber.dea_status}", reason_code="DEA_NOT_ACTIVE"
        )

    authorized_schedules: list[str] = prescriber.dea_schedules or []
    if schedule_upper not in authorized_schedules:
        return ControlledSubstanceAuthResponse(
            npi=npi, schedule=schedule_upper, authorized=False,
            reason=f"DEA not authorized for Schedule {schedule_upper}", reason_code="SCHEDULE_NOT_AUTHORIZED"
        )

    return ControlledSubstanceAuthResponse(npi=npi, schedule=schedule_upper, authorized=True)


# ─── Taxonomy ──────────────────────────────────────────────────────────────────

@router.get("/taxonomies")
def list_taxonomies(tenant_id: TenantId) -> dict:
    entries = _taxonomy_service.all_entries()
    return {
        "taxonomies": [
            {
                "code": e.code,
                "display_name": e.display_name,
                "classification": e.classification,
                "simplified_specialty": e.simplified_specialty,
                "is_prescriber": e.is_prescriber,
                "is_pharmacy": e.is_pharmacy,
            }
            for e in entries
        ]
    }


@router.get("/taxonomies/{code}")
def get_taxonomy(code: str, tenant_id: TenantId) -> dict:
    entry = _taxonomy_service.get_entry(code.upper())
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "TAXONOMY_NOT_FOUND", "message": f"Taxonomy code {code} not found"}},
        )
    return {
        "code": entry.code,
        "display_name": entry.display_name,
        "classification": entry.classification,
        "specialization": entry.specialization,
        "simplified_specialty": entry.simplified_specialty,
        "is_prescriber": entry.is_prescriber,
        "is_pharmacy": entry.is_pharmacy,
        "is_hospital": entry.is_hospital,
    }


@router.get("/specialties")
def list_specialties(tenant_id: TenantId) -> dict:
    specialties = sorted(set(
        e.simplified_specialty
        for e in _taxonomy_service.all_entries()
        if e.simplified_specialty and e.is_prescriber
    ))
    return {"specialties": specialties}


# ─── Organizations ─────────────────────────────────────────────────────────────

@router.get("/organizations", response_model=SearchResponse)
def list_organizations(
    db: DBSession,
    tenant_id: TenantId,
    name: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SearchResponse:
    stmt = select(Prescriber).where(Prescriber.entity_type == "2")
    if name:
        stmt = stmt.where(Prescriber.display_name.ilike(f"%{name}%"))
    if state:
        stmt = stmt.where(Prescriber.practice_state == state.upper()[:2])

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    offset = (page - 1) * page_size
    rows = db.execute(stmt.offset(offset).limit(page_size)).scalars().all()
    return SearchResponse(results=list(rows), total=total, page=page, page_size=page_size)


@router.get("/organizations/{npi}", response_model=PrescriberResponse)
def get_organization(npi: str, db: DBSession, tenant_id: TenantId) -> Prescriber:
    try:
        validate_npi(npi)
    except NpiValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_NPI", "message": str(exc)}},
        ) from exc
    stmt = select(Prescriber).where(Prescriber.npi == npi, Prescriber.entity_type == "2")
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": f"No organization found with NPI {npi}"}},
        )
    return row


# ─── Monitoring ────────────────────────────────────────────────────────────────

@router.get("/monitoring/alerts", response_model=list[CredentialAlertResponse])
def list_alerts(
    db: DBSession,
    tenant_id: TenantId,
    acknowledged: Optional[bool] = Query(None),
) -> list[CredentialAlert]:
    stmt = select(CredentialAlert)
    if acknowledged is False:
        stmt = stmt.where(CredentialAlert.acknowledged_at.is_(None))
    elif acknowledged is True:
        stmt = stmt.where(CredentialAlert.acknowledged_at.is_not(None))
    rows = db.execute(stmt).scalars().all()
    return list(rows)


@router.put("/monitoring/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> dict:
    stmt = select(CredentialAlert).where(CredentialAlert.id == alert_id)
    alert = db.execute(stmt).scalar_one_or_none()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ALERT_NOT_FOUND", "message": "Alert not found"}},
        )
    from datetime import UTC, datetime
    alert.acknowledged_at = datetime.now(UTC)
    alert.acknowledged_by = tenant_id
    db.commit()
    return {"acknowledged": True}


# ─── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=DirectoryStatsResponse)
def directory_stats(db: DBSession, tenant_id: TenantId) -> DirectoryStatsResponse:
    total = db.execute(select(func.count(Prescriber.id))).scalar_one()
    active = db.execute(select(func.count(Prescriber.id)).where(Prescriber.status == "active")).scalar_one()
    inactive = db.execute(select(func.count(Prescriber.id)).where(Prescriber.status == "inactive")).scalar_one()
    deactivated = db.execute(select(func.count(Prescriber.id)).where(Prescriber.status == "deactivated")).scalar_one()
    excluded = db.execute(select(func.count(Prescriber.id)).where(Prescriber.status == "excluded")).scalar_one()

    return DirectoryStatsResponse(
        total_prescribers=total,
        active_prescribers=active,
        inactive_prescribers=inactive,
        deactivated_prescribers=deactivated,
        excluded_prescribers=excluded,
        by_entity_type={},
        by_state={},
    )


# ─── Relationships ──────────────────────────────────────────────────────────────

@router.get("/relationships/{npi}/pharmacies", response_model=list[PrescriberPharmacyRelationshipResponse])
def prescriber_pharmacy_relationships(
    npi: str,
    db: DBSession,
    tenant_id: TenantId,
    period_month: Optional[str] = Query(None, description="Filter by YYYY-MM period"),
    limit: int = Query(50, ge=1, le=500),
) -> list[PrescriberPharmacyRelationshipResponse]:
    try:
        validate_npi(npi)
    except NpiValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_NPI", "message": "NPI must be a valid 10-digit NPI"}},
        )

    stmt = select(PrescriberPharmacyRelationship).where(
        PrescriberPharmacyRelationship.prescriber_npi == npi
    )
    if period_month:
        stmt = stmt.where(PrescriberPharmacyRelationship.period_month == period_month)
    stmt = stmt.order_by(PrescriberPharmacyRelationship.period_month.desc()).limit(limit)

    rows = db.execute(stmt).scalars().all()
    return [
        PrescriberPharmacyRelationshipResponse(
            prescriber_npi=r.prescriber_npi,
            pharmacy_npi=r.pharmacy_npi,
            period_month=r.period_month,
            claim_count=r.claim_count,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get("/relationships/{npi}/stats")
def prescriber_relationship_stats(
    npi: str,
    db: DBSession,
    tenant_id: TenantId,
) -> dict:
    try:
        validate_npi(npi)
    except NpiValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_NPI", "message": "NPI must be a valid 10-digit NPI"}},
        )

    stmt = select(
        func.count(PrescriberPharmacyRelationship.pharmacy_npi.distinct()).label("unique_pharmacies"),
        func.sum(PrescriberPharmacyRelationship.claim_count).label("total_claims"),
        func.count(PrescriberPharmacyRelationship.period_month.distinct()).label("active_months"),
    ).where(PrescriberPharmacyRelationship.prescriber_npi == npi)

    result = db.execute(stmt).one()
    return {
        "prescriber_npi": npi,
        "unique_pharmacies": result.unique_pharmacies or 0,
        "total_claims": int(result.total_claims or 0),
        "active_months": result.active_months or 0,
    }


# ─── Data Refresh ───────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=NpimportResultResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_nppes_refresh(
    db: DBSession,
    tenant_id: TenantId,
    data_source: str = Query("nppes", description="Data source identifier"),
    refresh_type: str = Query("full", description="full or incremental"),
) -> NpimportResultResponse:
    last_log = db.execute(
        select(DataRefreshLog)
        .where(DataRefreshLog.data_source == data_source)
        .order_by(DataRefreshLog.started_at.desc())
    ).scalars().first()

    logger.info(
        "nppes_refresh_requested",
        extra={"svc_data_source": data_source, "svc_refresh_type": refresh_type},
    )

    if last_log and last_log.status == "completed":
        return NpimportResultResponse(
            status=last_log.status,
            records_processed=last_log.records_processed or 0,
            records_added=last_log.records_added or 0,
            records_updated=last_log.records_updated or 0,
            data_source=last_log.data_source,
            refresh_type=last_log.refresh_type,
        )

    return NpimportResultResponse(
        status="queued",
        records_processed=0,
        records_added=0,
        records_updated=0,
        data_source=data_source,
        refresh_type=refresh_type,
    )
