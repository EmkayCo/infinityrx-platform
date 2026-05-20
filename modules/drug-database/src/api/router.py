"""Drug database API router — /api/v1/drugs/

Search, lookup, and pricing endpoints query the seeded FDA NDC tables:
  drug_database.drugs              (Drug ORM model, ndc_tables.py)
  drug_database.drug_packages      (DrugPackage ORM model, ndc_tables.py)
  drug_database.drug_nadac_pricing (DrugNADACPricing, pricing_tables.py)

The drug_products table (tables.py) was never migrated and is NOT used.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
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
from src.models.ndc_tables import Drug
from src.models.pricing_tables import DrugNADACPricing
from src.models.tables import (
    DataRefreshLog,
    DrugInteraction,
    DrugPricingHistory,
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


def _drug_to_dict(drug: Drug) -> dict:
    """Map a seeded Drug row to the DrugProductResponse field set.

    Fields with no source column in drug_database.drugs are returned as
    None/False rather than fabricated values.

    Column mapping:
      id                 <- product_id  (string PK, e.g. "0069-4200")
      ndc_11             <- ndc_11
      ndc_formatted      <- derived from product_ndc (insert hyphen after 5th char)
      proprietary_name   <- proprietary_name
      nonproprietary_name <- non_proprietary_name  (note: different column name)
      drug_name_display  <- proprietary_name or non_proprietary_name (first non-null)
      drug_type          <- marketing_category_name (NDA/ANDA/OTC etc.) — closest available
      dea_schedule       <- dea_schedule
      otc_rx             <- None (not in seeded schema)
      dosage_form        <- dosage_form_name
      route_of_administration <- route_name
      strength           <- active_numerator_strength (raw string, first value)
      labeler_name       <- labeler_name
      marketing_status   <- None (end_marketing_date presence used as heuristic would
                            fabricate; return None instead)
      is_specialty       <- False (not in seeded schema)
      is_biosimilar      <- False (not in seeded schema)
      is_glp1            <- False (not in seeded schema)
      gpi_code           <- None (not in seeded schema)
      atc_code           <- None (not in seeded schema)
      therapeutic_class_1 <- None (not in seeded schema; pharm_classes is raw text)
      therapeutic_class_2 <- None (not in seeded schema)
      is_active          <- True unless ndc_exclude_flag == 'E'
      data_source        <- "fda_ndc"
    """
    # Derive a display name: prefer proprietary, fall back to non-proprietary
    display = drug.proprietary_name or drug.non_proprietary_name or drug.product_ndc

    # Format NDC from product_ndc (5-4 format) — append "-00" placeholder for package
    # or just return product_ndc as-is if it already has a hyphen
    ndc_fmt: str | None = None
    if drug.product_ndc:
        parts = drug.product_ndc.split("-")
        if len(parts) == 2:
            ndc_fmt = f"{parts[0]}-{parts[1]}-00"
        else:
            ndc_fmt = drug.product_ndc

    # is_active: exclude if FDA ndc_exclude_flag is "E" (excluded)
    is_active = drug.ndc_exclude_flag != "E"

    # First strength value (semicolon-separated raw field)
    strength: str | None = None
    if drug.active_numerator_strength:
        strength = drug.active_numerator_strength.split(";")[0].strip() or None

    return {
        "id": drug.product_id,
        "ndc_11": drug.ndc_11,
        "ndc_formatted": ndc_fmt,
        "proprietary_name": drug.proprietary_name,
        "nonproprietary_name": drug.non_proprietary_name,
        "drug_name_display": display,
        "drug_type": drug.marketing_category_name,
        "dea_schedule": drug.dea_schedule,
        "otc_rx": None,
        "dosage_form": drug.dosage_form_name,
        "route_of_administration": drug.route_name,
        "strength": strength,
        "labeler_name": drug.labeler_name,
        "marketing_status": None,
        "is_specialty": False,
        "is_biosimilar": False,
        "is_glp1": False,
        "gpi_code": None,
        "atc_code": None,
        "therapeutic_class_1": None,
        "therapeutic_class_2": None,
        "is_active": is_active,
        "data_source": "fda_ndc",
    }


def _nadac_to_pricing_dict(nadac: DrugNADACPricing) -> dict:
    """Map a DrugNADACPricing row to PricingResponse fields."""
    return {
        "ndc_11": nadac.ndc_11,
        "price_type": "NADAC",
        "price_per_unit": nadac.nadac_per_unit,
        "unit_type": nadac.pricing_unit,
        "package_price": None,
        "effective_date": nadac.effective_date,
        "termination_date": None,
        "data_source": "cms_nadac",
    }


# ─── NDC Lookup ──────────────────────────────────────────────────────────────


@router.get("/lookup/batch", response_model=list[DrugProductResponse])
async def batch_lookup(
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
    drugs = db.query(Drug).filter(Drug.ndc_11.in_(normalized)).all()
    return [_drug_to_dict(d) for d in drugs]


@router.get("/lookup/{ndc}", response_model=DrugProductResponse)
async def lookup_drug(ndc: str, db: DBSession, tenant_id: TenantId) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e), 400) from e

    drug = db.query(Drug).filter(Drug.ndc_11 == ndc_11).first()
    if drug is None:
        raise _error("DRUG_NOT_FOUND", f"No drug found for NDC {ndc_11}", 404)
    return _drug_to_dict(drug)


@router.get("/search", response_model=DrugSearchResponse)
async def search_drugs(
    q: str = Query(..., min_length=1),
    drug_type: str | None = Query(None),
    marketing_status: str | None = Query(None),
    is_specialty: bool | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    query = db.query(Drug)

    # Full-text search across name fields, NDC, and labeler
    search_filter = (
        Drug.proprietary_name.ilike(f"%{q}%")
        | Drug.non_proprietary_name.ilike(f"%{q}%")
        | Drug.ndc_11.ilike(f"%{q}%")
        | Drug.labeler_name.ilike(f"%{q}%")
        | Drug.substance_name.ilike(f"%{q}%")
    )
    query = query.filter(search_filter)

    if drug_type:
        # drug_type maps to marketing_category_name in seeded data
        query = query.filter(Drug.marketing_category_name == drug_type)

    # marketing_status and is_specialty have no source column in seeded data;
    # applying these filters would return 0 results — skip silently
    # (fields are still returned as None/False in the response).

    total = query.count()
    results = query.offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [_drug_to_dict(d) for d in results],
    }


# ─── Pricing ─────────────────────────────────────────────────────────────────


@router.get("/pricing/{ndc}", response_model=list[PricingResponse])
async def get_pricing(
    ndc: str,
    as_of: date | None = Query(None),
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e)) from e

    nadac = db.query(DrugNADACPricing).filter(DrugNADACPricing.ndc_11 == ndc_11).first()
    if nadac is None:
        return []

    requested_date = as_of or date.today()
    pricing_dict = _nadac_to_pricing_dict(nadac)
    resolved = PricingService.select_effective_price(
        [
            {
                "price_per_unit": pricing_dict["price_per_unit"],
                "effective_date": pricing_dict["effective_date"],
                "termination_date": pricing_dict["termination_date"],
                "data_source": pricing_dict["data_source"],
                "_obj": pricing_dict,
            }
        ],
        requested_date=requested_date,
    )
    if resolved:
        return [resolved["_obj"]]
    return []


@router.get("/pricing/{ndc}/history", response_model=list[PricingHistoryResponse])
async def get_pricing_history(
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
async def check_interactions(
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
async def get_equivalents(
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
async def list_overrides(db: DBSession, tenant_id: TenantId) -> Any:
    return (
        db.query(TenantPricingOverride)
        .filter(TenantPricingOverride.tenant_id == tenant_id)
        .all()
    )


@router.post("/overrides/upload", response_model=MACUploadResponse)
async def upload_mac_list(
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
async def delete_override(
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
async def get_rems(ndc: str, db: DBSession, tenant_id: TenantId) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e)) from e

    return db.query(RemsProgram).filter(RemsProgram.ndc_11 == ndc_11).all()


# ─── Drug Shortages ────────────────────────────────────────────────────────


@router.get("/shortages", response_model=list[DrugShortageResponse])
async def list_shortages(
    status_filter: str | None = Query(None, alias="status"),
    db: DBSession = None,
    tenant_id: TenantId = None,
) -> Any:
    query = db.query(DrugShortage)
    if status_filter:
        query = query.filter(DrugShortage.shortage_status == status_filter)
    return query.all()


@router.get("/shortages/{ndc}", response_model=list[DrugShortageResponse])
async def get_shortage(ndc: str, db: DBSession, tenant_id: TenantId) -> Any:
    try:
        ndc_11 = normalize_ndc(ndc)
    except InvalidNDCError as e:
        raise _error("INVALID_NDC", str(e)) from e

    return db.query(DrugShortage).filter(DrugShortage.ndc_11 == ndc_11).all()


# ─── Admin / Refresh ──────────────────────────────────────────────────────────


@router.get("/refresh/status", response_model=list[RefreshStatusResponse])
async def refresh_status(db: DBSession, tenant_id: TenantId) -> Any:
    return (
        db.query(DataRefreshLog)
        .order_by(DataRefreshLog.started_at.desc())
        .limit(50)
        .all()
    )


@router.get("/health")
async def health(db: DBSession) -> dict:
    """Real dependency health check (H-13).

    Returns 200 {"status":"healthy"} if DB is reachable.
    Returns 503 {"status":"unhealthy", "failing": [...]} if DB is down.
    """
    failing = []
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception:
        failing.append("database")

    if failing:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "module": "drug-database", "failing": failing},
        )
    return {"status": "healthy", "module": "drug-database"}
