"""Drug database API router — /api/v1/drugs/"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, status

from src.api.dependencies import DBSession, TenantId
from src.api.schemas.drugs import (
    DrugProductResponse,
    DrugSearchResponse,
    DrugShortageResponse,
    InteractionResponse,
    MACUploadResponse,
    PricingHistoryResponse,
    PricingResponse,
    RefreshStatusResponse,
    RemsProgramResponse,
    TenantOverrideResponse,
    TherapeuticEquivalenceResponse,
)
from src.models.tables import (
    DataRefreshLog,
    DrugInteraction,
    DrugPricing,
    DrugPricingHistory,
    DrugProduct,
    DrugShortage,
    RemsProgram,
    TenantPricingOverride,
    TherapeuticEquivalence,
)
from src.services.interactions import InteractionChecker, InteractionSeverity
from src.services.mac_list import MACListError, parse_mac_list_csv
from src.services.pricing import PricingService
from src.utils.ndc import InvalidNDCError, normalize_ndc

router = APIRouter(prefix="/api/v1/drugs", tags=["drugs"])


def _error(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "correlation_id": str(uuid.uuid4())}},
    )


# ─── NDC Lookup ──────────────────────────────────────────────────────────────


@router.get("/lookup/batch", response_model=list[DrugProductResponse])
def batch_lookup(
    ndcs: list[str] = Query(...),
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    if len(ndcs) > 100:
        raise _error("BATCH_TOO_LARGE", "Batch lookup limited to 100 NDCs", 400)
    normalized = []
    for raw in ndcs:
        try:
            normalized.append(normalize_ndc(raw))
        except InvalidNDCError:
            continue
    drugs = db.query(DrugProduct).filter(DrugProduct.ndc_11.in_(normalized)).all()
    return drugs


@router.get("/lookup/{ndc}", response_model=DrugProductResponse)
def lookup_drug(ndc: str, db: DBSession, tenant_id: TenantId) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e), 400) from e

    drug = db.query(DrugProduct).filter(DrugProduct.ndc_11 == ndc_11).first()
    if drug is None:
        raise _error("DRUG_NOT_FOUND", f"No drug found for NDC {ndc_11}", 404)
    return drug


@router.get("/search", response_model=DrugSearchResponse)
def search_drugs(
    q: str = Query(..., min_length=1),
    drug_type: str | None = Query(None),
    marketing_status: str | None = Query(None),
    is_specialty: bool | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    query = db.query(DrugProduct)

    # Full-text search across name fields and NDC
    search_filter = (
        DrugProduct.drug_name_display.ilike(f"%{q}%")
        | DrugProduct.nonproprietary_name.ilike(f"%{q}%")
        | DrugProduct.proprietary_name.ilike(f"%{q}%")
        | DrugProduct.ndc_11.ilike(f"%{q}%")
        | DrugProduct.labeler_name.ilike(f"%{q}%")
    )
    query = query.filter(search_filter)

    if drug_type:
        query = query.filter(DrugProduct.drug_type == drug_type)
    if marketing_status:
        query = query.filter(DrugProduct.marketing_status == marketing_status)
    if is_specialty is not None:
        query = query.filter(DrugProduct.is_specialty == is_specialty)

    total = query.count()
    results = query.offset(offset).limit(limit).all()
    return {"total": total, "limit": limit, "offset": offset, "results": results}


# ─── Pricing ─────────────────────────────────────────────────────────────────


@router.get("/pricing/{ndc}", response_model=list[PricingResponse])
def get_pricing(
    ndc: str,
    as_of: date | None = Query(None),
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e)) from e

    requested_date = as_of or date.today()
    prices = db.query(DrugPricing).filter(DrugPricing.ndc_11 == ndc_11).all()
    result = []
    for p in prices:
        resolved = PricingService.select_effective_price(
            [
                {
                    "price_per_unit": p.price_per_unit,
                    "effective_date": p.effective_date,
                    "termination_date": p.termination_date,
                    "data_source": p.data_source,
                    "_obj": p,
                }
            ],
            requested_date=requested_date,
        )
        if resolved:
            result.append(resolved["_obj"])
    return result


@router.get("/pricing/{ndc}/history", response_model=list[PricingHistoryResponse])
def get_pricing_history(
    ndc: str,
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e)) from e

    return (
        db.query(DrugPricingHistory)
        .filter(DrugPricingHistory.ndc_11 == ndc_11)
        .order_by(DrugPricingHistory.effective_date.desc())
        .all()
    )


# ─── Clinical ────────────────────────────────────────────────────────────────


@router.get("/interactions", response_model=list[InteractionResponse])
def check_interactions(
    identifiers: list[str] = Query(...),
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    all_interactions = db.query(DrugInteraction).all()
    interaction_dicts = [
        {
            "drug_1_identifier": i.drug_1_identifier,
            "drug_2_identifier": i.drug_2_identifier,
            "drug_1_name": i.drug_1_name,
            "drug_2_name": i.drug_2_name,
            "severity": InteractionSeverity[i.severity.upper()],
            "interaction_description": i.interaction_description,
            "management_recommendation": i.management_recommendation,
        }
        for i in all_interactions
    ]
    results = InteractionChecker.check_pairs(identifiers, interaction_dicts)
    return [
        {
            "drug_1_identifier": r["drug_1_identifier"],
            "drug_2_identifier": r["drug_2_identifier"],
            "drug_1_name": r.get("drug_1_name"),
            "drug_2_name": r.get("drug_2_name"),
            "severity": r["severity"].name.lower(),
            "interaction_description": r.get("interaction_description"),
            "management_recommendation": r.get("management_recommendation"),
        }
        for r in results
    ]


# ─── Therapeutic Equivalence ─────────────────────────────────────────────────


@router.get("/equivalents/{ndc}", response_model=list[TherapeuticEquivalenceResponse])
def get_equivalents(
    ndc: str,
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e)) from e

    return (
        db.query(TherapeuticEquivalence)
        .filter(
            (TherapeuticEquivalence.brand_ndc == ndc_11)
            | (TherapeuticEquivalence.generic_ndc == ndc_11)
        )
        .filter(TherapeuticEquivalence.is_therapeutically_equivalent == True)  # noqa: E712
        .all()
    )


# ─── Tenant MAC Overrides ─────────────────────────────────────────────────────


@router.get("/overrides", response_model=list[TenantOverrideResponse])
def list_overrides(db: DBSession, tenant_id: TenantId) -> Any:
    return (
        db.query(TenantPricingOverride)
        .filter(TenantPricingOverride.tenant_id == tenant_id)
        .all()
    )


@router.post("/overrides/upload", response_model=MACUploadResponse)
def upload_mac_list(
    file: UploadFile,
    db: DBSession,
    tenant_id: TenantId,
) -> Any:
    content = file.file.read().decode("utf-8")
    try:
        records = parse_mac_list_csv(content, tenant_id)
    except MACListError as e:
        raise _error("MAC_LIST_INVALID", str(e), 422) from e

    applied = 0
    for rec in records:
        existing = (
            db.query(TenantPricingOverride)
            .filter(
                TenantPricingOverride.tenant_id == rec["tenant_id"],
                TenantPricingOverride.ndc_11 == rec["ndc_11"],
                TenantPricingOverride.price_type == rec["price_type"],
                TenantPricingOverride.effective_date == rec["effective_date"],
            )
            .first()
        )
        if existing:
            existing.price_per_unit = rec["price_per_unit"]
            existing.unit_type = rec["unit_type"]
            existing.termination_date = rec["termination_date"]
        else:
            db.add(TenantPricingOverride(**rec))
        applied += 1

    db.commit()
    return {"records_applied": applied, "records_skipped": 0, "errors": []}


@router.delete("/overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_override(
    override_id: uuid.UUID,
    db: DBSession,
    tenant_id: TenantId,
) -> None:
    override = (
        db.query(TenantPricingOverride)
        .filter(
            TenantPricingOverride.id == override_id,
            TenantPricingOverride.tenant_id == tenant_id,
        )
        .first()
    )
    if override is None:
        raise _error("OVERRIDE_NOT_FOUND", f"Override {override_id} not found", 404)
    db.delete(override)
    db.commit()


# ─── REMS ────────────────────────────────────────────────────────────────────


@router.get("/rems/{ndc}", response_model=list[RemsProgramResponse])
def get_rems(ndc: str, db: DBSession, tenant_id: TenantId) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e)) from e

    return db.query(RemsProgram).filter(RemsProgram.ndc_11 == ndc_11).all()


# ─── Drug Shortages ────────────────────────────────────────────────────────


@router.get("/shortages", response_model=list[DrugShortageResponse])
def list_shortages(
    status_filter: str | None = Query(None, alias="status"),
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    query = db.query(DrugShortage)
    if status_filter:
        query = query.filter(DrugShortage.shortage_status == status_filter)
    return query.all()


@router.get("/shortages/{ndc}", response_model=list[DrugShortageResponse])
def get_shortage(ndc: str, db: DBSession, tenant_id: TenantId) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e)) from e

    return db.query(DrugShortage).filter(DrugShortage.ndc_11 == ndc_11).all()


# ─── Admin / Refresh ──────────────────────────────────────────────────────────


@router.get("/refresh/status", response_model=list[RefreshStatusResponse])
def refresh_status(db: DBSession, tenant_id: TenantId) -> Any:
    return (
        db.query(DataRefreshLog)
        .order_by(DataRefreshLog.started_at.desc())
        .limit(50)
        .all()
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "module": "drug-database"}
