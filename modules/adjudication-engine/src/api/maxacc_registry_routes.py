"""Admin endpoints for maxacc-registry (Wave 44a M6).

Operator-portal-facing surface over the global maxacc_registry schema:

  /admin/maxacc-registry/source-lists                 (GET, POST, PATCH, DELETE)
  /admin/maxacc-registry/lookup/ndc/{ndc}             (GET — read-side)
  /admin/maxacc-registry/lookup/bin/{bin}             (GET — read-side)
  /admin/maxacc-registry/runs                         (GET — list)
  /admin/maxacc-registry/runs/{run_id}                (GET — detail)
  /admin/maxacc-registry/runs/curated-seed           (POST — multipart)
  /admin/maxacc-registry/runs/scraper-output         (POST — multipart)
  /admin/maxacc-registry/vendor-pbm-relationships     (GET, POST, PATCH, DELETE)
  /admin/maxacc-registry/vendor-pbm-relationships/seed (POST)

Auth gating:
  * Reads:  operator | platform_admin | fwa_investigator
  * Writes: platform_admin

NB: maxacc_registry is GLOBAL reference data — no tenant_id, no RLS.
The session factory does NOT install tenant loaders.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from shared.auth.dependencies import CurrentUser, get_current_user, require_roles


logger = logging.getLogger("adjudication_engine.maxacc_registry_admin")

router = APIRouter(prefix="/admin/maxacc-registry", tags=["admin-maxacc-registry"])


_READ_ROLES = require_roles("platform_admin", "fwa_investigator", "operator")
_ADMIN_ONLY = require_roles("platform_admin")


# ---------------------------------------------------------------------------
# Session factory (no RLS — global reference data)
# ---------------------------------------------------------------------------


_factory = None


_ROLE_PAIRS = {
    "ifx_dev_app":  ("ifx_dev_admin",  "dev_admin_password"),
    "ifx_mock_app": ("ifx_mock_admin", "mock_admin_password"),
}


def _resolve_admin_url() -> str:
    """maxacc_registry is platform-owned reference data — app role has
    SELECT only. Admin operations (CRUD source_lists, ingest, vendor PBM
    catalog edits) need the admin role.

    Resolution order:
      1. ADMIN_DATABASE_URL — full URL override
      2. swap ``ifx_*_app`` for ``ifx_*_admin`` in DATABASE_URL_SYNC
    """
    import re  # noqa: PLC0415

    override = os.environ.get("ADMIN_DATABASE_URL")
    if override:
        return override.replace("+asyncpg", "+psycopg2")

    url = os.environ.get("DATABASE_URL_SYNC")
    if not url:
        raise RuntimeError(
            "DATABASE_URL_SYNC not set; maxacc-registry admin endpoints "
            "need a sync DB URL"
        )
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")

    # Match optional driver prefix + role + password.
    m = re.match(
        r"^(postgresql(?:\+psycopg2)?://)([^:]+):([^@]+)@(.+)$", url,
    )
    if m is None:
        return url  # caller will see the original error if it can't connect
    scheme, role, _pw, rest = m.group(1), m.group(2), m.group(3), m.group(4)
    pair = _ROLE_PAIRS.get(role)
    if pair is None:
        return url
    admin_role, default_pw = pair
    pw_override = os.environ.get(
        f"IFX_{admin_role.replace('ifx_', '').replace('_admin', '').upper()}"
        f"_ADMIN_PASSWORD"
    )
    return f"{scheme}{admin_role}:{pw_override or default_pw}@{rest}"


def _get_factory():
    global _factory
    if _factory is None:
        url = _resolve_admin_url()
        engine = create_engine(url, future=True)
        sm = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        _factory = sm
    return _factory


def _reset_factory_for_tests() -> None:
    global _factory
    _factory = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_uuid(s: str, field_name: str = "id") -> UUID:
    try:
        return UUID(s)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=400, detail=f"invalid {field_name}: {s!r}"
        ) from exc


# ---------------------------------------------------------------------------
# Schemas — source lists
# ---------------------------------------------------------------------------


class SourceListIn(BaseModel):
    source_name: str = Field(..., min_length=1, max_length=120)
    source_type: str = Field(
        ..., description="ndc_list | employer_list | bin_pcn_list | curated"
    )
    source_url: str | None = None
    vendor_name: str | None = Field(None, max_length=120)
    scrape_strategy: str = Field("manual_upload")
    scrape_cadence: str = Field("never")
    notes: str | None = None


class SourceListPatch(BaseModel):
    source_url: str | None = None
    scrape_strategy: str | None = None
    scrape_cadence: str | None = None
    active: bool | None = None
    notes: str | None = None


class SourceListOut(BaseModel):
    id: str
    source_name: str
    source_type: str
    source_url: str | None
    vendor_name: str | None
    scrape_strategy: str
    scrape_cadence: str
    active: bool
    last_imported_at: str | None
    notes: str | None


# ---------------------------------------------------------------------------
# Schemas — runs
# ---------------------------------------------------------------------------


class RunOut(BaseModel):
    id: str
    source_list_id: str
    status: str
    records_imported: int
    records_added: int
    records_unchanged: int
    records_marked_dropped: int
    import_started_at: str | None
    import_completed_at: str | None
    failure_reason: str | None
    notes: str | None
    errors: list[str] = []


# ---------------------------------------------------------------------------
# Schemas — lookups
# ---------------------------------------------------------------------------


class NdcLookupOut(BaseModel):
    is_listed: bool
    currently_listed: bool
    sources: list[dict[str, Any]] = []
    first_observed_at: str | None = None
    last_observed_at: str | None = None


class BinLookupOut(BaseModel):
    is_listed: bool
    matched_specificity: str
    vendor_name: str | None = None
    employer_or_plan_label: str | None = None
    confidence: str | None = None
    pbm_carrier: str | None = None
    exclusive_specialty_pharmacy: str | None = None
    is_exclusive_relationship: bool = False
    notes: str | None = None
    source_list_id: str | None = None


# ---------------------------------------------------------------------------
# Schemas — vendor PBM
# ---------------------------------------------------------------------------


class VendorPbmIn(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=120)
    pbm_carrier: str = Field(..., min_length=1, max_length=120)
    exclusive_specialty_pharmacy: str | None = Field(None, max_length=120)
    is_exclusive_relationship: bool = False
    effective_from: date
    termination_date: date | None = None
    notes: str | None = None


class VendorPbmPatch(BaseModel):
    pbm_carrier: str | None = None
    exclusive_specialty_pharmacy: str | None = None
    is_exclusive_relationship: bool | None = None
    termination_date: date | None = None
    notes: str | None = None


class VendorPbmOut(BaseModel):
    id: str
    vendor_name: str
    pbm_carrier: str
    exclusive_specialty_pharmacy: str | None
    is_exclusive_relationship: bool
    effective_from: str
    termination_date: str | None
    notes: str | None


# ---------------------------------------------------------------------------
# Source lists — CRUD
# ---------------------------------------------------------------------------


def _row_to_source_list_out(r) -> SourceListOut:
    return SourceListOut(
        id=str(r["id"]),
        source_name=r["source_name"],
        source_type=r["source_type"],
        source_url=r["source_url"],
        vendor_name=r["vendor_name"],
        scrape_strategy=r["scrape_strategy"],
        scrape_cadence=r["scrape_cadence"],
        active=r["active"],
        last_imported_at=r["last_imported_at"].isoformat()
        if r["last_imported_at"] else None,
        notes=r["notes"],
    )


@router.get(
    "/source-lists",
    response_model=list[SourceListOut],
    dependencies=[Depends(_READ_ROLES)],
)
async def list_source_lists(
    list_type: str | None = Query(default=None),
    active_only: bool = Query(default=True),
) -> list[SourceListOut]:
    factory = _get_factory()
    with factory() as sess:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if active_only:
            clauses.append("active = TRUE")
        if list_type is not None:
            clauses.append("source_type = :t")
            params["t"] = list_type
        sql = (
            "SELECT id, source_name, source_type, source_url, vendor_name, "
            "scrape_strategy, scrape_cadence, active, last_imported_at, notes "
            "FROM maxacc_registry.source_lists"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY source_name"
        rows = sess.execute(text(sql), params).mappings().all()
    return [_row_to_source_list_out(r) for r in rows]


@router.get(
    "/source-lists/{source_list_id}",
    response_model=SourceListOut,
    dependencies=[Depends(_READ_ROLES)],
)
async def get_source_list(source_list_id: str) -> SourceListOut:
    sid = _coerce_uuid(source_list_id, "source_list_id")
    factory = _get_factory()
    with factory() as sess:
        row = sess.execute(
            text(
                "SELECT id, source_name, source_type, source_url, vendor_name, "
                "scrape_strategy, scrape_cadence, active, last_imported_at, notes "
                "FROM maxacc_registry.source_lists WHERE id = :id"
            ),
            {"id": str(sid)},
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="source list not found")
    return _row_to_source_list_out(row)


@router.post(
    "/source-lists",
    response_model=SourceListOut,
    status_code=201,
    dependencies=[Depends(_ADMIN_ONLY)],
)
async def create_source_list(body: SourceListIn) -> SourceListOut:
    new_id = uuid.uuid4()
    factory = _get_factory()
    with factory() as sess:
        try:
            sess.execute(
                text(
                    "INSERT INTO maxacc_registry.source_lists "
                    "(id, source_name, source_type, source_url, vendor_name, "
                    " scrape_strategy, scrape_cadence, notes) "
                    "VALUES (:id, :name, :type, :url, :vendor, :strat, :cad, :notes)"
                ),
                {
                    "id": str(new_id),
                    "name": body.source_name,
                    "type": body.source_type,
                    "url": body.source_url,
                    "vendor": body.vendor_name,
                    "strat": body.scrape_strategy,
                    "cad": body.scrape_cadence,
                    "notes": body.notes,
                },
            )
            sess.commit()
        except Exception as exc:
            sess.rollback()
            msg = str(exc)
            if "uq_source_lists_name_vendor" in msg:
                raise HTTPException(
                    status_code=409,
                    detail="source_list with this (source_name, vendor_name) already exists",
                ) from exc
            if "ck_source_lists_" in msg or "violates check" in msg.lower():
                raise HTTPException(status_code=422, detail=msg) from exc
            raise
        row = sess.execute(
            text(
                "SELECT id, source_name, source_type, source_url, vendor_name, "
                "scrape_strategy, scrape_cadence, active, last_imported_at, notes "
                "FROM maxacc_registry.source_lists WHERE id = :id"
            ),
            {"id": str(new_id)},
        ).mappings().first()
    return _row_to_source_list_out(row)


@router.patch(
    "/source-lists/{source_list_id}",
    response_model=SourceListOut,
    dependencies=[Depends(_ADMIN_ONLY)],
)
async def patch_source_list(
    source_list_id: str, body: SourceListPatch,
) -> SourceListOut:
    sid = _coerce_uuid(source_list_id, "source_list_id")
    updates: dict[str, Any] = {}
    if body.source_url is not None:
        updates["source_url"] = body.source_url
    if body.scrape_strategy is not None:
        updates["scrape_strategy"] = body.scrape_strategy
    if body.scrape_cadence is not None:
        updates["scrape_cadence"] = body.scrape_cadence
    if body.active is not None:
        updates["active"] = body.active
    if body.notes is not None:
        updates["notes"] = body.notes
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates) + ", updated_at = now()"
    params = {**updates, "id": str(sid)}
    factory = _get_factory()
    with factory() as sess:
        result = sess.execute(
            text(
                f"UPDATE maxacc_registry.source_lists SET {set_clause} "
                f"WHERE id = :id"
            ),
            params,
        )
        if result.rowcount == 0:
            sess.rollback()
            raise HTTPException(status_code=404, detail="source list not found")
        sess.commit()
        row = sess.execute(
            text(
                "SELECT id, source_name, source_type, source_url, vendor_name, "
                "scrape_strategy, scrape_cadence, active, last_imported_at, notes "
                "FROM maxacc_registry.source_lists WHERE id = :id"
            ),
            {"id": str(sid)},
        ).mappings().first()
    return _row_to_source_list_out(row)


@router.delete(
    "/source-lists/{source_list_id}",
    status_code=204,
    dependencies=[Depends(_ADMIN_ONLY)],
)
async def delete_source_list(source_list_id: str) -> None:
    """Hard-delete a source list. Cascades to ndc_list_entries +
    bin_pcn_group_vendor_map; import_runs are RESTRICTed (operator
    must clean those up first)."""
    sid = _coerce_uuid(source_list_id, "source_list_id")
    factory = _get_factory()
    with factory() as sess:
        try:
            result = sess.execute(
                text("DELETE FROM maxacc_registry.source_lists WHERE id = :id"),
                {"id": str(sid)},
            )
            if result.rowcount == 0:
                sess.rollback()
                raise HTTPException(
                    status_code=404, detail="source list not found"
                )
            sess.commit()
        except HTTPException:
            raise
        except Exception as exc:
            sess.rollback()
            if "import_runs" in str(exc).lower():
                raise HTTPException(
                    status_code=409,
                    detail="source list has import_runs; remove runs first",
                ) from exc
            raise


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


@router.get(
    "/lookup/ndc/{ndc}",
    response_model=NdcLookupOut,
    dependencies=[Depends(_READ_ROLES)],
)
async def lookup_ndc(
    ndc: str,
    as_of_date: date | None = Query(default=None),
) -> NdcLookupOut:
    from maxacc_registry.queries.lookup import (  # noqa: PLC0415
        ndc_on_any_maximizer_list,
    )

    factory = _get_factory()
    with factory() as sess:
        result = ndc_on_any_maximizer_list(sess, ndc, as_of_date=as_of_date)
    return NdcLookupOut(
        is_listed=result.is_listed,
        currently_listed=result.currently_listed,
        sources=[
            {
                "source_list_id": str(s.source_list_id),
                "source_name": s.source_name,
                "vendor_name": s.vendor_name,
                "source_type": s.source_type,
            }
            for s in result.sources
        ],
        first_observed_at=result.first_observed_at.isoformat()
        if result.first_observed_at else None,
        last_observed_at=result.last_observed_at.isoformat()
        if result.last_observed_at else None,
    )


@router.get(
    "/lookup/bin/{bin}",
    response_model=BinLookupOut,
    dependencies=[Depends(_READ_ROLES)],
)
async def lookup_bin(
    bin: str,
    pcn: str | None = Query(default=None),
    group_id: str | None = Query(default=None),
    as_of_date: date | None = Query(default=None),
) -> BinLookupOut:
    from maxacc_registry.queries.lookup import (  # noqa: PLC0415
        resolve_bin_pcn_group_vendor,
    )

    factory = _get_factory()
    with factory() as sess:
        result = resolve_bin_pcn_group_vendor(
            sess, bin, pcn=pcn, group_id=group_id, as_of_date=as_of_date,
        )
    return BinLookupOut(
        is_listed=result.is_listed,
        matched_specificity=result.matched_specificity,
        vendor_name=result.vendor_name,
        employer_or_plan_label=result.employer_or_plan_label,
        confidence=result.confidence,
        pbm_carrier=result.pbm_carrier,
        exclusive_specialty_pharmacy=result.exclusive_specialty_pharmacy,
        is_exclusive_relationship=result.is_exclusive_relationship,
        notes=result.notes,
        source_list_id=str(result.source_list_id) if result.source_list_id else None,
    )


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


def _row_to_run_out(r, errors: list[str] | None = None) -> RunOut:
    return RunOut(
        id=str(r["id"]),
        source_list_id=str(r["source_list_id"]),
        status=r["status"],
        records_imported=r["records_imported"],
        records_added=r["records_added"],
        records_unchanged=r["records_unchanged"],
        records_marked_dropped=r["records_marked_dropped"],
        import_started_at=r["import_started_at"].isoformat()
        if r["import_started_at"] else None,
        import_completed_at=r["import_completed_at"].isoformat()
        if r["import_completed_at"] else None,
        failure_reason=r["failure_reason"],
        notes=r["notes"],
        errors=errors or [],
    )


@router.get(
    "/runs",
    response_model=list[RunOut],
    dependencies=[Depends(_READ_ROLES)],
)
async def list_runs(
    source_list_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[RunOut]:
    clauses: list[str] = []
    params: dict[str, Any] = {"lim": limit}
    if source_list_id is not None:
        sid = _coerce_uuid(source_list_id, "source_list_id")
        clauses.append("source_list_id = :sid")
        params["sid"] = str(sid)
    if status is not None:
        clauses.append("status = :st")
        params["st"] = status
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT id, source_list_id, status, records_imported, records_added, "
        "records_unchanged, records_marked_dropped, import_started_at, "
        "import_completed_at, failure_reason, notes "
        f"FROM maxacc_registry.import_runs{where} "
        "ORDER BY import_started_at DESC LIMIT :lim"
    )
    factory = _get_factory()
    with factory() as sess:
        rows = sess.execute(text(sql), params).mappings().all()
    return [_row_to_run_out(r) for r in rows]


@router.get(
    "/runs/{run_id}",
    response_model=RunOut,
    dependencies=[Depends(_READ_ROLES)],
)
async def get_run(run_id: str) -> RunOut:
    rid = _coerce_uuid(run_id, "run_id")
    factory = _get_factory()
    with factory() as sess:
        row = sess.execute(
            text(
                "SELECT id, source_list_id, status, records_imported, "
                "records_added, records_unchanged, records_marked_dropped, "
                "import_started_at, import_completed_at, failure_reason, notes "
                "FROM maxacc_registry.import_runs WHERE id = :id"
            ),
            {"id": str(rid)},
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return _row_to_run_out(row)


@router.post(
    "/runs/curated-seed",
    response_model=list[RunOut],
    dependencies=[Depends(_ADMIN_ONLY)],
)
async def post_curated_seed_run(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RunOut]:
    """Operator uploads a curated seed CSV. Each unique (source_name,
    vendor_name) bucket in the file becomes its own ImportRun."""
    from maxacc_registry.ingest.curated_seed import (  # noqa: PLC0415
        import_curated_seed_file,
    )

    suffix = Path(file.filename or "seed.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, dir="/tmp",
    ) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        factory = _get_factory()
        with factory() as sess:
            try:
                reports = import_curated_seed_file(
                    sess, tmp_path, imported_by=current_user.id,
                )
            except Exception as exc:
                sess.rollback()
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        out: list[RunOut] = []
        with factory() as sess:
            for rep in reports:
                row = sess.execute(
                    text(
                        "SELECT id, source_list_id, status, records_imported, "
                        "records_added, records_unchanged, "
                        "records_marked_dropped, import_started_at, "
                        "import_completed_at, failure_reason, notes "
                        "FROM maxacc_registry.import_runs WHERE id = :id"
                    ),
                    {"id": str(rep.run_id)},
                ).mappings().first()
                if row is not None:
                    out.append(_row_to_run_out(row, errors=rep.errors))
        return out
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


@router.post(
    "/runs/scraper-output",
    response_model=RunOut,
    dependencies=[Depends(_ADMIN_ONLY)],
)
async def post_scraper_output_run(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> RunOut:
    """Operator uploads a single scraper-output JSON envelope."""
    from maxacc_registry.ingest._common import IngestionFailure  # noqa: PLC0415
    from maxacc_registry.ingest.scraper_output import (  # noqa: PLC0415
        import_scraper_output,
    )

    suffix = Path(file.filename or "scrape.json").suffix or ".json"
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, dir="/tmp",
    ) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        factory = _get_factory()
        with factory() as sess:
            try:
                report = import_scraper_output(
                    sess, tmp_path, imported_by=current_user.id,
                )
            except IngestionFailure as exc:
                sess.rollback()
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        with factory() as sess:
            row = sess.execute(
                text(
                    "SELECT id, source_list_id, status, records_imported, "
                    "records_added, records_unchanged, records_marked_dropped, "
                    "import_started_at, import_completed_at, failure_reason, notes "
                    "FROM maxacc_registry.import_runs WHERE id = :id"
                ),
                {"id": str(report.run_id)},
            ).mappings().first()
        if row is None:
            raise HTTPException(status_code=500, detail="run row not found post-import")
        return _row_to_run_out(row, errors=report.errors)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# Vendor PBM relationships — CRUD
# ---------------------------------------------------------------------------


def _row_to_vendor_pbm_out(r) -> VendorPbmOut:
    return VendorPbmOut(
        id=str(r["id"]),
        vendor_name=r["vendor_name"],
        pbm_carrier=r["pbm_carrier"],
        exclusive_specialty_pharmacy=r["exclusive_specialty_pharmacy"],
        is_exclusive_relationship=r["is_exclusive_relationship"],
        effective_from=r["effective_from"].isoformat(),
        termination_date=r["termination_date"].isoformat()
        if r["termination_date"] else None,
        notes=r["notes"],
    )


@router.get(
    "/vendor-pbm-relationships",
    response_model=list[VendorPbmOut],
    dependencies=[Depends(_READ_ROLES)],
)
async def list_vendor_pbm_relationships(
    active_only: bool = Query(default=True),
) -> list[VendorPbmOut]:
    factory = _get_factory()
    with factory() as sess:
        sql = (
            "SELECT id, vendor_name, pbm_carrier, exclusive_specialty_pharmacy, "
            "is_exclusive_relationship, effective_from, termination_date, notes "
            "FROM maxacc_registry.vendor_pbm_relationships"
        )
        if active_only:
            sql += (
                " WHERE termination_date IS NULL OR "
                "termination_date >= CURRENT_DATE"
            )
        sql += " ORDER BY vendor_name"
        rows = sess.execute(text(sql)).mappings().all()
    return [_row_to_vendor_pbm_out(r) for r in rows]


@router.post(
    "/vendor-pbm-relationships",
    response_model=VendorPbmOut,
    status_code=201,
    dependencies=[Depends(_ADMIN_ONLY)],
)
async def create_vendor_pbm_relationship(body: VendorPbmIn) -> VendorPbmOut:
    new_id = uuid.uuid4()
    factory = _get_factory()
    with factory() as sess:
        try:
            sess.execute(
                text(
                    "INSERT INTO maxacc_registry.vendor_pbm_relationships "
                    "(id, vendor_name, pbm_carrier, exclusive_specialty_pharmacy, "
                    " is_exclusive_relationship, effective_from, termination_date, "
                    " notes) "
                    "VALUES (:id, :v, :p, :sp, :ex, :ef, :td, :n)"
                ),
                {
                    "id": str(new_id),
                    "v": body.vendor_name,
                    "p": body.pbm_carrier,
                    "sp": body.exclusive_specialty_pharmacy,
                    "ex": body.is_exclusive_relationship,
                    "ef": body.effective_from,
                    "td": body.termination_date,
                    "n": body.notes,
                },
            )
            sess.commit()
        except Exception as exc:
            sess.rollback()
            msg = str(exc)
            if "uq_vendor_pbm_vendor_name" in msg:
                raise HTTPException(
                    status_code=409,
                    detail=f"vendor {body.vendor_name!r} already has a relationship row",
                ) from exc
            if "ck_vendor_pbm_termination_after_effective" in msg:
                raise HTTPException(
                    status_code=422,
                    detail="termination_date must be >= effective_from",
                ) from exc
            raise
        row = sess.execute(
            text(
                "SELECT id, vendor_name, pbm_carrier, exclusive_specialty_pharmacy, "
                "is_exclusive_relationship, effective_from, termination_date, notes "
                "FROM maxacc_registry.vendor_pbm_relationships WHERE id = :id"
            ),
            {"id": str(new_id)},
        ).mappings().first()
    return _row_to_vendor_pbm_out(row)


@router.patch(
    "/vendor-pbm-relationships/{relationship_id}",
    response_model=VendorPbmOut,
    dependencies=[Depends(_ADMIN_ONLY)],
)
async def patch_vendor_pbm_relationship(
    relationship_id: str, body: VendorPbmPatch,
) -> VendorPbmOut:
    rid = _coerce_uuid(relationship_id, "relationship_id")
    updates: dict[str, Any] = {}
    if body.pbm_carrier is not None:
        updates["pbm_carrier"] = body.pbm_carrier
    if body.exclusive_specialty_pharmacy is not None:
        updates["exclusive_specialty_pharmacy"] = body.exclusive_specialty_pharmacy
    if body.is_exclusive_relationship is not None:
        updates["is_exclusive_relationship"] = body.is_exclusive_relationship
    if body.termination_date is not None:
        updates["termination_date"] = body.termination_date
    if body.notes is not None:
        updates["notes"] = body.notes
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates) + ", updated_at = now()"
    params = {**updates, "id": str(rid)}
    factory = _get_factory()
    with factory() as sess:
        try:
            result = sess.execute(
                text(
                    f"UPDATE maxacc_registry.vendor_pbm_relationships "
                    f"SET {set_clause} WHERE id = :id"
                ),
                params,
            )
            if result.rowcount == 0:
                sess.rollback()
                raise HTTPException(
                    status_code=404, detail="relationship not found"
                )
            sess.commit()
        except HTTPException:
            raise
        except Exception as exc:
            sess.rollback()
            if "ck_vendor_pbm_termination_after_effective" in str(exc):
                raise HTTPException(
                    status_code=422,
                    detail="termination_date must be >= effective_from",
                ) from exc
            raise
        row = sess.execute(
            text(
                "SELECT id, vendor_name, pbm_carrier, exclusive_specialty_pharmacy, "
                "is_exclusive_relationship, effective_from, termination_date, notes "
                "FROM maxacc_registry.vendor_pbm_relationships WHERE id = :id"
            ),
            {"id": str(rid)},
        ).mappings().first()
    return _row_to_vendor_pbm_out(row)


@router.delete(
    "/vendor-pbm-relationships/{relationship_id}",
    status_code=204,
    dependencies=[Depends(_ADMIN_ONLY)],
)
async def delete_vendor_pbm_relationship(relationship_id: str) -> None:
    rid = _coerce_uuid(relationship_id, "relationship_id")
    factory = _get_factory()
    with factory() as sess:
        result = sess.execute(
            text(
                "DELETE FROM maxacc_registry.vendor_pbm_relationships "
                "WHERE id = :id"
            ),
            {"id": str(rid)},
        )
        if result.rowcount == 0:
            sess.rollback()
            raise HTTPException(status_code=404, detail="relationship not found")
        sess.commit()


@router.post(
    "/vendor-pbm-relationships/seed",
    response_model=list[VendorPbmOut],
    dependencies=[Depends(_ADMIN_ONLY)],
)
async def seed_vendor_pbm_catalog() -> list[VendorPbmOut]:
    """Re-run the canonical 10-vendor seed (idempotent UPSERT)."""
    from maxacc_registry.seeding.vendor_pbm_seed import (  # noqa: PLC0415
        seed_vendor_pbm_relationships,
    )

    factory = _get_factory()
    with factory() as sess:
        seed_vendor_pbm_relationships(sess)
        rows = sess.execute(
            text(
                "SELECT id, vendor_name, pbm_carrier, exclusive_specialty_pharmacy, "
                "is_exclusive_relationship, effective_from, termination_date, notes "
                "FROM maxacc_registry.vendor_pbm_relationships "
                "ORDER BY vendor_name"
            )
        ).mappings().all()
    return [_row_to_vendor_pbm_out(r) for r in rows]
