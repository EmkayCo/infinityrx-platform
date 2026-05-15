"""Aggregate OIG LEIE + SAM.gov exclusions into core.exclusion_list.

Reads from shared.oig_leie_exclusions and shared.sam_exclusions,
normalizes each source to the ExclusionListEntry schema, and upserts
into core_exclusion_list (SQLite shim) / core.exclusion_list (Postgres).

Natural upsert key:
  OIG: (source='OIG', npi)               when npi is present
  OIG: (source='OIG', last_name, first_name, organization_name, state) when npi absent
  SAM: (source='SAM', npi)               when npi is present
  SAM: (source='SAM', last_name, first_name, organization_name, state) when npi absent

Delisting: rows present in core_exclusion_list that are NOT in either
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
    ENCRYPTION_KEY_ACTIVE              — required by ExclusionListEntry Base

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
# Tests override these via run_aggregation(oig_table=..., sam_table=...).
_DEFAULT_OIG_TABLE = "shared.oig_leie_exclusions"
_DEFAULT_SAM_TABLE = "shared.sam_exclusions"


# ---------------------------------------------------------------------------
# Normalizers: source row → ExclusionListEntry field dict
# ---------------------------------------------------------------------------

def _normalize_oig(row: object) -> dict:
    """Map one OIG LEIE row to ExclusionListEntry columns."""
    # OIG stores DOB as a string — not used in ExclusionListEntry schema.
    # NPI may be 10 digits (OIG omits leading/trailing spaces in CSV).
    npi: Optional[str] = row.npi if row.npi and len(row.npi) == 10 and row.npi.isdigit() else None
    entity_type = "individual" if row.lastname else "organization"

    excl_date: Optional[datetime] = None
    if row.excldate:
        excl_date = datetime(row.excldate.year, row.excldate.month, row.excldate.day, tzinfo=timezone.utc)

    reinstate_date: Optional[datetime] = None
    if row.reindate:
        reinstate_date = datetime(row.reindate.year, row.reindate.month, row.reindate.day, tzinfo=timezone.utc)

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

    excl_date: Optional[datetime] = None
    if row.active_date:
        excl_date = datetime(row.active_date.year, row.active_date.month, row.active_date.day, tzinfo=timezone.utc)

    reinstate_date: Optional[datetime] = None
    if row.termination_date:
        reinstate_date = datetime(
            row.termination_date.year, row.termination_date.month, row.termination_date.day, tzinfo=timezone.utc
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


def _upsert(session: Session, data: dict) -> str:
    """Upsert one normalized row. Returns 'inserted' | 'updated'."""
    now = datetime.now(timezone.utc)
    stmt, _ = _lookup_key(data)
    existing = session.execute(stmt).scalars().first()
    if existing is None:
        row = ExclusionListEntry(last_updated=now, **data)
        session.add(row)
        return "inserted"
    for k, v in data.items():
        setattr(existing, k, v)
    existing.last_updated = now
    return "updated"


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
) -> AggregationResult:
    """Full aggregation: OIG → exclusion_list, SAM → exclusion_list, delist.

    Args:
        session:   SQLAlchemy session connected to the target database.
        oig_table: Qualified table name for OIG source (override in tests).
        sam_table: Qualified table name for SAM source (override in tests).

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
            action = _upsert(session, data)
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
            action = _upsert(session, data)
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
    _mark_delisted(session, result, oig_table=oig_table, sam_table=sam_table)

    return result


def _build_active_keys(
    session: Session,
    oig_table: str,
    sam_table: str,
) -> tuple[set[str], set[str]]:
    """Return (oig_npi_set, sam_npi_set) of currently-active OIG/SAM NPIs."""
    oig_npis: set[str] = set()
    for row in session.execute(
        text(f"SELECT npi FROM {oig_table} WHERE npi IS NOT NULL")  # nosec
    ).all():
        oig_npis.add(row[0])

    sam_npis: set[str] = set()
    for row in session.execute(
        text(f"SELECT npi FROM {sam_table} WHERE npi IS NOT NULL")  # nosec
    ).all():
        sam_npis.add(row[0])

    return oig_npis, sam_npis


def _mark_delisted(
    session: Session,
    result: AggregationResult,
    *,
    oig_table: str,
    sam_table: str,
) -> None:
    """Mark NPI-keyed rows in core_exclusion_list that no longer appear in source.

    Only acts on rows that:
    1. Have an NPI (non-NPI rows are harder to match reliably without a
       name-fuzzy-match pass — deferred).
    2. Have reinstate_date IS NULL (already-terminated rows are left alone).

    For rows that qualify, sets reinstate_date = NOW() to signal delisting.
    """
    now = datetime.now(timezone.utc)
    oig_npis, sam_npis = _build_active_keys(session, oig_table, sam_table)

    # Fetch all core_exclusion_list NPI rows that are still "active" (no reinstate_date)
    active_rows = session.execute(
        select(ExclusionListEntry)
        .where(ExclusionListEntry.npi.isnot(None))
        .where(ExclusionListEntry.reinstate_date.is_(None))
    ).scalars().all()

    for row in active_rows:
        source_set = oig_npis if row.source == "OIG" else sam_npis
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
