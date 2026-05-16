"""Aggregate OIG LEIE + SAM.gov exclusions into core.exclusion_list.

Reads from shared.oig_leie_exclusions and shared.sam_exclusions,
normalizes each source to the ExclusionListEntry schema, and upserts
into core.exclusion_list via the ORM model (single code path for both
Postgres production and SQLite test environments).

Production target
-----------------
**core.exclusion_list** (schema ``core``) — the canonical table defined by
``src.models.ExclusionListEntry`` (``__tablename__="exclusion_list"``,
``__table_args__={"schema": "core"}``).  SQLAlchemy resolves the schema prefix
on Postgres automatically.  The shim's ``create_all()`` strips ``schema=``
for SQLite so test fixtures work without a Postgres connection.

P0a v3 naming unification (BLOCK-1 follow-up): the previous dual-path design
maintained a bare-name ORM path (``core_exclusion_list``) for SQLite tests
and a schema-qualified raw-SQL path for Postgres.  Both paths are now unified:
the ORM model is always schema-qualified; the shim's ``create_all()`` strips
the schema for SQLite.  ``excl_table`` parameters are retained for
backward-compatibility but ignored in write/delist paths.

Natural upsert key:
  OIG: (source='OIG', npi)               when npi is present
  OIG: (source='OIG', last_name, first_name, organization_name, state) when npi absent
  SAM: (source='SAM', npi)               when npi is present
  SAM: (source='SAM', last_name, first_name, organization_name, state) when npi absent

Delisting: rows present in core.exclusion_list that are NOT in either
source and whose reinstate_date is None are marked with reinstate_date =
NOW() (the standard "terminated" signal for this schema). Rows that
already have a reinstate_date are left unchanged.

Idempotent: safe to run multiple times. Re-running refreshes last_updated
timestamps and re-applies delistings without creating duplicates.

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python modules/core-platform/scripts/aggregate_exclusion_list.py

Environment:
    DATABASE_URL_SYNC (or DATABASE_URL) — set by switch_env.sh

LESSON-011: core.exclusion_list is GLOBAL reference data — no tenant_id.
LESSON-010: OIG/SAM names are public data — no PHI encryption needed.
LESSON-005: log extra keys prefixed with excl_ to avoid LogRecord collisions.
"""

from __future__ import annotations

import logging
import os
import sys
import types
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

_MODULE_ROOT = Path(__file__).resolve().parent.parent  # .../modules/core-platform
_REPO_ROOT = _MODULE_ROOT.parent.parent               # repo root
for _p in (_REPO_ROOT, _MODULE_ROOT):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# noqa: E402 — sys.path manipulation must happen before these imports
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from src.models import ExclusionListEntry  # noqa: E402

logger = logging.getLogger("excl.aggregator")

# Production table names (schema-qualified for Postgres).
# Tests override oig_table/sam_table via run_aggregation(oig_table=..., sam_table=...).
_DEFAULT_OIG_TABLE = "shared.oig_leie_exclusions"
_DEFAULT_SAM_TABLE = "shared.sam_exclusions"
# Canonical table identifier — kept for _mark_delisted raw-SQL delisting path.
# The ORM model (ExclusionListEntry, schema="core", tablename="exclusion_list")
# is the single source of truth for writes; this constant is the schema-qualified
# string used for the SELECT/UPDATE delist pass in _mark_delisted.
_DEFAULT_EXCL_TABLE = "core.exclusion_list"

# CONCERN-1 fix: minimum row counts that signal a complete source snapshot.
# If a source load delivers fewer rows than this threshold, delisting is
# suppressed for that source — a partial load must not falsely reinstate
# legitimate exclusions.  Defaults are generous lower bounds well below
# the known OIG (~83k) and SAM (~167k) table sizes; override via env vars.
_OIG_MIN_ROWS_FOR_DELIST = int(os.environ.get("EXCL_OIG_MIN_ROWS", "60000"))
_SAM_MIN_ROWS_FOR_DELIST = int(os.environ.get("EXCL_SAM_MIN_ROWS", "100000"))


# ---------------------------------------------------------------------------
# Normalizers: source row → ExclusionListEntry field dict
# ---------------------------------------------------------------------------

def _normalize_oig(row: object) -> dict:
    """Map one OIG LEIE row to ExclusionListEntry columns.

    Date columns are returned as ``date`` objects (not ``datetime``) to match
    the production ``core.exclusion_list`` column type (``Date``, not
    ``DateTime``).  The SQLite shim uses ``DateTime`` but SQLAlchemy accepts
    a ``date`` object for both types — alignment ensures Postgres writes land
    in the correct column without implicit truncation.
    """
    # OIG stores DOB as a string — not used in ExclusionListEntry schema.
    # NPI may be 10 digits (OIG omits leading/trailing spaces in CSV).
    npi: Optional[str] = row.npi if row.npi and len(row.npi) == 10 and row.npi.isdigit() else None
    entity_type = "individual" if row.lastname else "organization"

    # BLOCK-1 fix: use date not datetime to match production Date column type.
    excl_date: Optional[date] = None
    if row.excldate:
        excl_date = date(row.excldate.year, row.excldate.month, row.excldate.day)

    reinstate_date: Optional[date] = None
    if row.reindate:
        reinstate_date = date(row.reindate.year, row.reindate.month, row.reindate.day)

    return {
        "source": "OIG",
        "entity_type": entity_type,
        "npi": npi,
        "first_name": (row.firstname or "").strip() or None,
        "last_name": (row.lastname or "").strip() or None,
        "organization_name": (row.busname or "").strip() or None,
        "state": row.state if row.state and len(row.state) == 2 else None,
        "exclusion_type": (row.excltype or "").strip() or None,
        "exclusion_date": excl_date,
        "reinstate_date": reinstate_date,
    }


def _normalize_sam(row: object) -> dict:
    """Map one SAM.gov row to ExclusionListEntry columns."""
    npi: Optional[str] = row.npi if row.npi and len(row.npi) == 10 and row.npi.isdigit() else None

    # SAM classification_type: 'Individual' → individual, else organization
    ct = (row.classification_type or "").lower()
    entity_type = "individual" if "individual" in ct else "organization"

    # SAM name field is a full name for individuals or company name for orgs.
    # Split into first/last only for individuals when a space is present.
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization_name: Optional[str] = None
    name = (row.name or "").strip()

    if entity_type == "individual" and name:
        # Best-effort split: SAM stores "LAST, FIRST" or "FIRST LAST"
        if "," in name:
            parts = name.split(",", 1)
            last_name = parts[0].strip() or None
            first_name = parts[1].strip() or None
        else:
            # No comma — treat the whole name as last_name for matching
            last_name = name or None
    else:
        organization_name = name or None

    # BLOCK-1 fix: use date not datetime to match production Date column type.
    excl_date: Optional[date] = None
    if row.active_date:
        excl_date = date(row.active_date.year, row.active_date.month, row.active_date.day)

    reinstate_date: Optional[date] = None
    if row.termination_date:
        reinstate_date = date(
            row.termination_date.year, row.termination_date.month, row.termination_date.day
        )

    # SAM state_province may be a full state name or 2-letter code
    state = row.state_province
    if state and len(state) != 2:
        state = None  # can't reliably normalize to 2-char; leave null

    return {
        "source": "SAM",
        "entity_type": entity_type,
        "npi": npi,
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": organization_name,
        "state": state,
        "exclusion_type": (row.exclusion_type or "").strip() or None,
        "exclusion_date": excl_date,
        "reinstate_date": reinstate_date,
    }


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def _lookup_key(data: dict):
    """Build the (stmt, key_desc) used to find an existing row for upsert.

    Priority: NPI (most reliable cross-source identifier) > name+state combo.
    """
    source = data["source"]
    npi = data["npi"]
    if npi:
        return (
            select(ExclusionListEntry)
            .where(ExclusionListEntry.source == source)
            .where(ExclusionListEntry.npi == npi),
            f"npi={npi}",
        )
    return (
        select(ExclusionListEntry)
        .where(ExclusionListEntry.source == source)
        .where(ExclusionListEntry.last_name == data.get("last_name"))
        .where(ExclusionListEntry.first_name == data.get("first_name"))
        .where(ExclusionListEntry.organization_name == data.get("organization_name"))
        .where(ExclusionListEntry.state == data.get("state")),
        f"name={data.get('last_name')},{data.get('first_name')}/{data.get('organization_name')}",
    )


def _upsert_orm(session: Session, data: dict) -> str:
    """Upsert one normalized row via the ORM (ExclusionListEntry).

    ExclusionListEntry carries schema="core" for Postgres; SQLite test engines
    have schema stripped by db_shim.create_all() so the table is always reachable
    as "exclusion_list" without a schema prefix.

    CONCERN-2 fix: when an NPI is present and no NPI-keyed row exists,
    fall back to a name-key lookup before inserting. If a name-key match
    exists with NULL NPI, upgrade that row with the NPI rather than creating
    a duplicate row.

    Returns 'inserted' | 'updated'.
    """
    now = datetime.now(timezone.utc)
    stmt, _ = _lookup_key(data)
    existing = session.execute(stmt).scalars().first()

    # CONCERN-2: NPI fallback — if NPI lookup found nothing, check name-key
    if existing is None and data.get("npi"):
        name_stmt = (
            select(ExclusionListEntry)
            .where(ExclusionListEntry.source == data["source"])
            .where(ExclusionListEntry.last_name == data.get("last_name"))
            .where(ExclusionListEntry.first_name == data.get("first_name"))
            .where(ExclusionListEntry.organization_name == data.get("organization_name"))
            .where(ExclusionListEntry.state == data.get("state"))
            .where(ExclusionListEntry.npi.is_(None))
        )
        existing = session.execute(name_stmt).scalars().first()

    if existing is None:
        row = ExclusionListEntry(last_updated=now, **data)
        session.add(row)
        return "inserted"
    for k, v in data.items():
        setattr(existing, k, v)
    existing.last_updated = now
    return "updated"


def _upsert(session: Session, data: dict, excl_table: str = _DEFAULT_EXCL_TABLE) -> str:
    """Upsert one normalized row via the ORM (ExclusionListEntry).

    The ``excl_table`` parameter is accepted for backward-compatibility but
    ignored — the ORM model (schema="core", tablename="exclusion_list") is the
    single write path for both Postgres and SQLite tests (the shim's create_all
    strips schema= for SQLite so the table is always reachable as "exclusion_list").
    """
    return _upsert_orm(session, data)


# ---------------------------------------------------------------------------
# Aggregation runner
# ---------------------------------------------------------------------------

class AggregationResult:
    def __init__(self) -> None:
        self.oig_seen = 0
        self.oig_inserted = 0
        self.oig_updated = 0
        self.oig_skipped = 0
        self.sam_seen = 0
        self.sam_inserted = 0
        self.sam_updated = 0
        self.sam_skipped = 0
        self.delisted = 0
        self.errors: list[str] = []

    @property
    def total_inserted(self) -> int:
        return self.oig_inserted + self.sam_inserted

    @property
    def total_updated(self) -> int:
        return self.oig_updated + self.sam_updated

    @property
    def total_errors(self) -> int:
        return len(self.errors)


def _iter_oig_rows(session: Session, table: str):
    """Yield OigLeieExclusion-like objects from the source table.

    Uses text() SQL so the table name can be schema-qualified for Postgres
    (default: shared.oig_leie_exclusions) or bare for SQLite tests.
    Returns lightweight SimpleNamespace-like row mappings.
    """
    sql = text(f"""
        SELECT id, npi, lastname, firstname, busname, state, excltype,
               excldate, reindate
        FROM {table}
    """)  # nosec — table name is a controlled constant, never user input
    for row in session.execute(sql).mappings():
        yield types.SimpleNamespace(
            id=row["id"],
            npi=row["npi"],
            lastname=row["lastname"],
            firstname=row["firstname"],
            busname=row["busname"],
            state=row["state"],
            excltype=row["excltype"],
            # Dates may arrive as strings (SQLite) or date objects (Postgres)
            excldate=_coerce_date(row["excldate"]),
            reindate=_coerce_date(row["reindate"]),
        )


def _iter_sam_rows(session: Session, table: str):
    """Yield SamExclusion-like objects from the source table."""
    sql = text(f"""
        SELECT id, npi, name, classification_type, exclusion_type,
               active_date, termination_date, state_province
        FROM {table}
    """)  # nosec — controlled constant
    for row in session.execute(sql).mappings():
        yield types.SimpleNamespace(
            id=row["id"],
            npi=row["npi"],
            name=row["name"],
            classification_type=row["classification_type"],
            exclusion_type=row["exclusion_type"],
            active_date=_coerce_date(row["active_date"]),
            termination_date=_coerce_date(row["termination_date"]),
            state_province=row["state_province"],
        )


def _coerce_date(val) -> Optional[date]:
    """Convert string 'YYYY-MM-DD' or date object to a date, or None."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    # SQLite returns dates as strings
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None


def run_aggregation(
    session: Session,
    *,
    oig_table: str = _DEFAULT_OIG_TABLE,
    sam_table: str = _DEFAULT_SAM_TABLE,
    excl_table: str = _DEFAULT_EXCL_TABLE,
    oig_min_rows: int | None = None,
    sam_min_rows: int | None = None,
) -> AggregationResult:
    """Full aggregation: OIG → exclusion_list, SAM → exclusion_list, delist.

    Args:
        session:      SQLAlchemy session connected to the target database.
        oig_table:    Qualified table name for OIG source (override in tests).
        sam_table:    Qualified table name for SAM source (override in tests).
        excl_table:   Retained for backward-compatibility; ignored in write/delist
                      paths (the ORM model is always used).  Kept as a parameter
                      so existing call-sites do not need immediate updates.
        oig_min_rows: Minimum OIG source rows required to allow delisting.
                      Pass 0 in tests to disable the completeness guard.
                      Defaults to ``_OIG_MIN_ROWS_FOR_DELIST`` (env-driven).
        sam_min_rows: Minimum SAM source rows required to allow delisting.
                      Pass 0 in tests to disable the completeness guard.
                      Defaults to ``_SAM_MIN_ROWS_FOR_DELIST`` (env-driven).

    Flushes every 500 rows to keep memory bounded on large source tables
    (OIG ~83k rows, SAM ~167k rows). Does NOT commit — caller commits.
    """
    result = AggregationResult()
    FLUSH_EVERY = 500

    # -- OIG LEIE --
    logger.info("excl_source=OIG starting aggregation from %s", oig_table)
    for i, oig_row in enumerate(_iter_oig_rows(session, oig_table), start=1):
        result.oig_seen += 1
        try:
            data = _normalize_oig(oig_row)
        except Exception as exc:
            result.oig_skipped += 1
            result.errors.append(f"OIG normalize row={oig_row.id}: {exc}")
            logger.warning("excl_normalize_error excl_source=OIG excl_row_id=%s: %s", oig_row.id, exc)
            continue
        try:
            action = _upsert(session, data, excl_table)
        except Exception as exc:
            result.oig_skipped += 1
            result.errors.append(f"OIG upsert row={oig_row.id}: {exc}")
            logger.warning("excl_upsert_error excl_source=OIG excl_row_id=%s: %s", oig_row.id, exc)
            continue
        if action == "inserted":
            result.oig_inserted += 1
        else:
            result.oig_updated += 1
        if i % FLUSH_EVERY == 0:
            session.flush()
            logger.debug("excl_flush excl_source=OIG excl_row_count=%d", i)

    session.flush()
    logger.info(
        "excl_oig_done",
        extra={
            "excl_seen": result.oig_seen,
            "excl_inserted": result.oig_inserted,
            "excl_updated": result.oig_updated,
            "excl_skipped": result.oig_skipped,
        },
    )

    # -- SAM --
    logger.info("excl_source=SAM starting aggregation from %s", sam_table)
    for i, sam_row in enumerate(_iter_sam_rows(session, sam_table), start=1):
        result.sam_seen += 1
        try:
            data = _normalize_sam(sam_row)
        except Exception as exc:
            result.sam_skipped += 1
            result.errors.append(f"SAM normalize row={sam_row.id}: {exc}")
            logger.warning("excl_normalize_error excl_source=SAM excl_row_id=%s: %s", sam_row.id, exc)
            continue
        try:
            action = _upsert(session, data, excl_table)
        except Exception as exc:
            result.sam_skipped += 1
            result.errors.append(f"SAM upsert row={sam_row.id}: {exc}")
            logger.warning("excl_upsert_error excl_source=SAM excl_row_id=%s: %s", sam_row.id, exc)
            continue
        if action == "inserted":
            result.sam_inserted += 1
        else:
            result.sam_updated += 1
        if i % FLUSH_EVERY == 0:
            session.flush()
            logger.debug("excl_flush excl_source=SAM excl_row_count=%d", i)

    session.flush()
    logger.info(
        "excl_sam_done",
        extra={
            "excl_seen": result.sam_seen,
            "excl_inserted": result.sam_inserted,
            "excl_updated": result.sam_updated,
            "excl_skipped": result.sam_skipped,
        },
    )

    # -- Delisting: collect IDs seen in this run, mark missing actives --
    _mark_delisted(
        session, result,
        oig_table=oig_table, sam_table=sam_table, excl_table=excl_table,
        oig_min_rows=oig_min_rows, sam_min_rows=sam_min_rows,
    )

    return result


def _build_active_keys(
    session: Session,
    oig_table: str,
    sam_table: str,
) -> tuple[set[str], set[str], int, int]:
    """Return (oig_npi_set, sam_npi_set, oig_total_rows, sam_total_rows).

    Total row counts are used by the CONCERN-1 completeness gate in
    ``_mark_delisted`` to refuse delisting when a source table looks
    incomplete (e.g. a partial load was interrupted).
    """
    oig_npis: set[str] = set()
    for row in session.execute(
        text(f"SELECT npi FROM {oig_table} WHERE npi IS NOT NULL")  # nosec
    ).all():
        oig_npis.add(row[0])

    oig_total = session.execute(
        text(f"SELECT COUNT(*) FROM {oig_table}")  # nosec
    ).scalar() or 0

    sam_npis: set[str] = set()
    for row in session.execute(
        text(f"SELECT npi FROM {sam_table} WHERE npi IS NOT NULL")  # nosec
    ).all():
        sam_npis.add(row[0])

    sam_total = session.execute(
        text(f"SELECT COUNT(*) FROM {sam_table}")  # nosec
    ).scalar() or 0

    return oig_npis, sam_npis, int(oig_total), int(sam_total)


def _mark_delisted(
    session: Session,
    result: AggregationResult,
    *,
    oig_table: str,
    sam_table: str,
    excl_table: str,
    oig_min_rows: int | None = None,
    sam_min_rows: int | None = None,
) -> None:
    """Mark NPI-keyed rows in excl_table that no longer appear in source.

    Only acts on rows that:
    1. Have an NPI (non-NPI rows are harder to match reliably without a
       name-fuzzy-match pass — deferred).
    2. Have reinstate_date IS NULL (already-terminated rows are left alone).
    3. CONCERN-1 completeness gate: the source table must have at least
       ``_OIG_MIN_ROWS_FOR_DELIST`` / ``_SAM_MIN_ROWS_FOR_DELIST`` rows
       to confirm the load completed.  A partial load must not falsely
       reinstate legitimate active exclusions.

    For rows that qualify, sets reinstate_date = TODAY (Date column type)
    to signal delisting.

    Uses the ORM exclusively (excl_table parameter retained for call-site
    compatibility but not used in the query).
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    oig_npis, sam_npis, oig_total, sam_total = _build_active_keys(session, oig_table, sam_table)

    # CONCERN-1 fix: gate delisting on completeness — suppress per source if
    # the source table looks incomplete (partial load or ingestion failure).
    # ``oig_min_rows`` / ``sam_min_rows`` override the module-level constants;
    # pass 0 in tests to disable the guard entirely.
    _oig_threshold = _OIG_MIN_ROWS_FOR_DELIST if oig_min_rows is None else oig_min_rows
    _sam_threshold = _SAM_MIN_ROWS_FOR_DELIST if sam_min_rows is None else sam_min_rows
    oig_delist_ok = oig_total >= _oig_threshold
    sam_delist_ok = sam_total >= _sam_threshold
    if not oig_delist_ok:
        logger.warning(
            "excl_delist_suppressed excl_source=OIG excl_source_rows=%d excl_min_required=%d",
            oig_total, _oig_threshold,
        )
    if not sam_delist_ok:
        logger.warning(
            "excl_delist_suppressed excl_source=SAM excl_source_rows=%d excl_min_required=%d",
            sam_total, _sam_threshold,
        )

    # Unified ORM path — ExclusionListEntry carries schema="core" for Postgres;
    # SQLite test engine has schema stripped by db_shim.create_all() so the
    # table is always reachable.  The ``excl_table`` parameter is kept for
    # backward-compatibility but is not used here.
    active_rows = session.execute(
        select(ExclusionListEntry)
        .where(ExclusionListEntry.npi.isnot(None))
        .where(ExclusionListEntry.reinstate_date.is_(None))
    ).scalars().all()

    for row in active_rows:
        source_set = oig_npis if row.source == "OIG" else sam_npis
        delist_ok = oig_delist_ok if row.source == "OIG" else sam_delist_ok
        if not delist_ok:
            continue  # completeness gate
        if row.npi not in source_set:
            row.reinstate_date = now
            row.last_updated = now
            result.delisted += 1

    if result.delisted > 0:
        session.flush()
        logger.info("excl_delisted excl_count=%d", result.delisted)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _resolve_db_url() -> str:
    url = (
        os.environ.get("DATABASE_URL_SYNC_REFERENCE")
        or os.environ.get("DATABASE_URL_SYNC")
        or os.environ.get("DATABASE_URL")
    )
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    # Downgrade asyncpg URLs to sync psycopg2 for this script
    return url.replace("postgresql+asyncpg://", "postgresql://")


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
    )

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        result = run_aggregation(session)
        session.commit()

    print(f"\n{'=' * 60}")
    print("Exclusion List Aggregation Result")
    print(f"{'=' * 60}")
    print(f"  OIG  seen:     {result.oig_seen:,}")
    print(f"  OIG  inserted: {result.oig_inserted:,}")
    print(f"  OIG  updated:  {result.oig_updated:,}")
    print(f"  OIG  skipped:  {result.oig_skipped:,}")
    print(f"  SAM  seen:     {result.sam_seen:,}")
    print(f"  SAM  inserted: {result.sam_inserted:,}")
    print(f"  SAM  updated:  {result.sam_updated:,}")
    print(f"  SAM  skipped:  {result.sam_skipped:,}")
    print(f"  Delisted:      {result.delisted:,}")
    print(f"  Errors:        {result.total_errors:,}")
    print(f"{'=' * 60}")
    print(f"  Total inserted: {result.total_inserted:,}")
    print(f"  Total updated:  {result.total_updated:,}")
    print(f"{'=' * 60}")

    if result.errors:
        logger.warning(
            "excl_aggregation_errors excl_error_count=%d first_error=%s",
            result.total_errors,
            result.errors[0],
        )

    if result.total_errors > 0 and result.total_inserted == 0 and result.total_updated == 0:
        logger.error("excl_aggregation_all_failed — check logs for normalize/upsert errors")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
