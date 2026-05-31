"""CSV ingestion helpers: row entity resolution + detection-run creation.

Public API
----------
resolve_row(row) -> ResolvedRow
    Pure function -- no I/O, no DB, no side effects.

create_or_resume_run(db, *, tenant_id, path, created_by, resume, force)
    -> DetectionRun
    Idempotent detection-run creation with advisory lock + partial unique
    index guard.

load_csv(db, run, *, chunk_size=10) -> int
    Stream the CSV at run.source_path row-by-row using csv.DictReader.
    On PostgreSQL: bulk-loads via psycopg2.extras.execute_values in batches
    of _INSERT_BATCH_SIZE rows (default 5,000) accumulated in memory, sent
    to Postgres with page_size=1000.  This path is RLS-safe: COPY FROM is
    rejected by Postgres on RLS-forced tables for non-superuser roles;
    execute_values INSERT respects RLS WITH CHECK and is the fast RLS-safe
    bulk path.  The GUC SET LOCAL app.current_tenant_id is already in effect
    on the same connection so RLS WITH CHECK passes without extra plumbing.
    On other dialects (SQLite in tests): falls back to the original
    ORM add()/flush() path in chunks of chunk_size so all resolution and
    stat logic is fully exercised without a real Postgres connection.

    Apply DOS hygiene: rows whose date_of_service fails parse_dos
    (e.g. 9999-09-09) are marked resolution_method='unmapped' with
    resolution_notes='invalid DOS'.  Null-NDC rows whose pharmacy_npi is
    present remain 'declared'.

    After streaming, populates run.resolution_stats with:
      - inserted_count  : total rows written
      - declared        : rows with resolution_method == 'declared'
      - unmapped        : rows with resolution_method == 'unmapped'
      - by_reason       : {note_string: count} for unmapped rows
      (expected_count is already set by create_or_resume_run)

    Full-coverage gate: records inserted_count alongside expected_count.
    Detection phase (Phase 3) refuses to run unless they match.

    Chunk failure: exceptions propagate to the caller unchanged.  The
    caller must mark the run 'failed' in a *separate* transaction.
    load_csv never swallows exceptions; partially-inserted batches are
    rolled back when the caller's surrounding transaction is rolled back.

resolution_method values match the DB CHECK constraint:
    'declared' | 'group_id_lookup' | 'ndc_lookup' | 'manual' | 'unmapped'

v1 scope:
  - declared  : pharmacy_npi is present and non-empty.
  - unmapped  : pharmacy_npi is absent or empty.
  - resolved_client_id and resolved_program_id are always None -- raw
    integer client_id/program_id values are not coerced to UUIDs in v1.
    The raw values remain accessible via the original row dict.

Performance note
----------------
_INSERT_BATCH_SIZE = 5_000 rows accumulated per execute_values call, with
page_size=1_000 (psycopg2 splits each batch into 1,000-row sub-statements).
For a 2.6M-row file this is ~520 execute_values calls.  Bounded memory:
at ~700 bytes/row the in-flight batch is ~3.5 MB.
"""
from __future__ import annotations

import csv
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Batch size for the PostgreSQL execute_values path.
# 5,000 rows accumulated before each execute_values call (page_size=1,000).
# At ~700 bytes/row this is ~3.5 MB per batch -- bounded memory for 2.6M rows.
# ---------------------------------------------------------------------------
_INSERT_BATCH_SIZE: int = 5_000

# Column order for the bulk INSERT -- must stay in sync with _build_insert_tuple
# and the ORM fallback field list in _stream_orm.
_INSERT_COLUMNS = (
    "id",
    "tenant_id",
    "detection_run_id",
    "row_number",
    "row_data",
    "resolved_pharmacy_npi",
    "resolved_ndc",
    "resolved_client_id",
    "resolved_program_id",
    "resolution_method",
    "resolution_notes",
)

# COPY FROM is rejected by Postgres on RLS-forced tables for non-superuser
# roles; execute_values INSERT respects RLS WITH CHECK and is the fast
# RLS-safe bulk path.
_INSERT_SQL = (
    "INSERT INTO reclaimrx.csv_upload_rows "
    "({cols}) VALUES %s"
).format(cols=", ".join(_INSERT_COLUMNS))


@dataclass
class ResolvedRow:
    """Result of resolving entity identifiers from a raw CSV row dict."""

    resolved_pharmacy_npi: Optional[str]
    resolved_ndc: Optional[str]
    # UUID columns -- always None in v1 (no int->UUID mapping implemented).
    resolved_client_id: Optional[str]
    resolved_program_id: Optional[str]
    # Must be one of: 'declared'|'group_id_lookup'|'ndc_lookup'|'manual'|'unmapped'
    resolution_method: str
    resolution_notes: Optional[str] = field(default=None)


def resolve_row(row: dict) -> ResolvedRow:
    """Resolve entity identifiers from a raw CSV row dictionary.

    Args:
        row: Dict of raw CSV column name -> string value.

    Returns:
        ResolvedRow with resolution_method 'declared' when pharmacy_npi is
        present and non-empty, or 'unmapped' otherwise.

    resolved_client_id and resolved_program_id are always None in v1.
    The raw client_id / program_id values stay in the caller's row dict.
    """
    raw_npi: str = row.get("pharmacy_npi", "") or ""
    raw_ndc: str = row.get("ndc", "") or ""

    npi_clean = raw_npi.strip() or None
    ndc_clean = raw_ndc.strip() or None

    if npi_clean:
        return ResolvedRow(
            resolved_pharmacy_npi=npi_clean,
            resolved_ndc=ndc_clean,
            resolved_client_id=None,
            resolved_program_id=None,
            resolution_method="declared",
            resolution_notes=None,
        )

    return ResolvedRow(
        resolved_pharmacy_npi=None,
        resolved_ndc=ndc_clean,
        resolved_client_id=None,
        resolved_program_id=None,
        resolution_method="unmapped",
        resolution_notes="missing pharmacy_npi",
    )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DetectionRunExistsError(ValueError):
    """Raised when a completed detection run already exists for this file."""


class RunInProgressError(ValueError):
    """Raised when an in_progress run exists and resume=False."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CHUNK = 65_536  # 64 KiB chunks for SHA-256 streaming


def _compute_sha256_and_count(path: str) -> tuple[str, int]:
    """Stream the file once to compute SHA-256 and count data rows.

    The first line is treated as the header and is NOT counted.
    Empty trailing lines do not increment the count.

    Returns:
        (hex_digest, data_row_count)
    """
    h = hashlib.sha256()
    total_lines = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
            total_lines += chunk.count(b"\n")
    # Subtract 1 for the header line; clamp to 0 for edge cases (empty file).
    data_rows = max(0, total_lines - 1)
    return h.hexdigest(), data_rows


def _acquire_advisory_lock(db: Session, key: str) -> None:
    """Acquire a Postgres transaction-scoped advisory lock on hashtext(key).

    The lock is released automatically when the surrounding transaction ends.
    On non-Postgres dialects (SQLite in unit tests) this call will raise;
    callers in that context should patch this function out.
    """
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": key},
    )


def _build_insert_tuple(
    *,
    row_id: uuid.UUID,
    tenant_id: uuid.UUID,
    detection_run_id: uuid.UUID,
    row_number: int,
    row_data: dict,
    resolved_pharmacy_npi: Optional[str],
    resolved_ndc: Optional[str],
    resolved_client_id: Optional[uuid.UUID],
    resolved_program_id: Optional[uuid.UUID],
    resolution_method: str,
    resolution_notes: Optional[str],
) -> tuple:
    """Build one row tuple for psycopg2.extras.execute_values INSERT.

    Pure function -- no I/O, no DB, no side effects.

    Column order matches _INSERT_COLUMNS exactly:
        id, tenant_id, detection_run_id, row_number, row_data,
        resolved_pharmacy_npi, resolved_ndc, resolved_client_id,
        resolved_program_id, resolution_method, resolution_notes.

    row_data is wrapped in psycopg2.extras.Json so psycopg2 passes it as a
    JSONB-typed parameter rather than a plain string.  NULL columns are
    represented as Python None so execute_values inserts SQL NULL.

    Returns an 11-element tuple matching _INSERT_COLUMNS.
    """
    from psycopg2.extras import Json

    return (
        str(row_id),
        str(tenant_id),
        str(detection_run_id),
        row_number,
        Json(row_data),
        resolved_pharmacy_npi,
        resolved_ndc,
        str(resolved_client_id) if resolved_client_id is not None else None,
        str(resolved_program_id) if resolved_program_id is not None else None,
        resolution_method,
        resolution_notes,
    )


def _resolve_and_hygiene(raw_row: dict, parse_dos) -> ResolvedRow:
    """Apply resolve_row then DOS hygiene.

    Shared by both the execute_values path and the ORM fallback path so the
    logic is written exactly once.
    """
    resolved = resolve_row(raw_row)

    dos_str = (raw_row.get("date_of_service", "") or "").strip()
    if dos_str:
        dos_valid = parse_dos(dos_str) is not None
        if not dos_valid:
            if resolved.resolution_method != "unmapped":
                # NPI check takes priority: if already unmapped due to
                # missing pharmacy_npi, preserve that note.
                resolved = ResolvedRow(
                    resolved_pharmacy_npi=resolved.resolved_pharmacy_npi,
                    resolved_ndc=resolved.resolved_ndc,
                    resolved_client_id=resolved.resolved_client_id,
                    resolved_program_id=resolved.resolved_program_id,
                    resolution_method="unmapped",
                    resolution_notes="invalid DOS",
                )
    return resolved


def _update_counters(counters: dict, resolved: ResolvedRow) -> None:
    """Increment the shared stat counters dict in-place."""
    counters["inserted"] = counters["inserted"] + 1
    if resolved.resolution_method == "declared":
        counters["declared"] = counters["declared"] + 1
    else:
        counters["unmapped"] = counters["unmapped"] + 1
        note = resolved.resolution_notes or "unspecified"
        by_reason = counters["by_reason"]
        by_reason[note] = by_reason.get(note, 0) + 1


def _stream_execute_values(
    db: Session,
    source_path: str,
    tenant_id: uuid.UUID,
    detection_run_id: uuid.UUID,
    parse_dos,
    counters: dict,
) -> None:
    """PostgreSQL execute_values bulk INSERT path.

    COPY FROM is rejected by Postgres on RLS-forced tables for non-superuser
    roles; execute_values INSERT respects RLS WITH CHECK and is the fast
    RLS-safe bulk path.

    Streams the source CSV, builds row tuples via _build_insert_tuple, and
    issues one psycopg2.extras.execute_values call per _INSERT_BATCH_SIZE
    rows (page_size=1000 within each call so psycopg2 splits large batches
    into manageable sub-statements).

    Runs on the same DBAPI connection that SQLAlchemy already holds so the
    GUC SET LOCAL app.current_tenant_id is in scope and RLS WITH CHECK on
    reclaimrx.csv_upload_rows passes without extra plumbing.
    """
    from psycopg2.extras import execute_values

    # db.connection() returns the SQLAlchemy Connection object.
    # .connection on that is the underlying raw psycopg2 connection.
    raw_conn = db.connection().connection  # type: ignore[attr-defined]
    cur = raw_conn.cursor()

    batch: list[tuple] = []

    def _flush_batch() -> None:
        if not batch:
            return
        execute_values(cur, _INSERT_SQL, batch, page_size=1000)
        batch.clear()

    with open(source_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row_number, raw_row in enumerate(reader, start=1):
            resolved = _resolve_and_hygiene(raw_row, parse_dos)

            batch.append(_build_insert_tuple(
                row_id=uuid.uuid4(),
                tenant_id=tenant_id,
                detection_run_id=detection_run_id,
                row_number=row_number,
                row_data=dict(raw_row),
                resolved_pharmacy_npi=resolved.resolved_pharmacy_npi,
                resolved_ndc=resolved.resolved_ndc,
                resolved_client_id=resolved.resolved_client_id,
                resolved_program_id=resolved.resolved_program_id,
                resolution_method=resolved.resolution_method,
                resolution_notes=resolved.resolution_notes,
            ))
            _update_counters(counters, resolved)

            if len(batch) >= _INSERT_BATCH_SIZE:
                _flush_batch()

    _flush_batch()
    cur.close()


def _stream_orm(
    db: Session,
    source_path: str,
    tenant_id: uuid.UUID,
    detection_run_id: uuid.UUID,
    parse_dos,
    counters: dict,
    CsvUploadRow,
    chunk_size: int,
) -> None:
    """SQLite / non-PostgreSQL fallback path using ORM add()/flush().

    Keeps all 54-row unit-test fixture assertions working on SQLite so
    resolution and stat logic is fully exercised dialect-independently.
    """
    chunk: list = []

    def _flush_chunk() -> None:
        for obj in chunk:
            db.add(obj)
        db.flush()
        chunk.clear()

    with open(source_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row_number, raw_row in enumerate(reader, start=1):
            resolved = _resolve_and_hygiene(raw_row, parse_dos)

            upload_row = CsvUploadRow(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                detection_run_id=detection_run_id,
                row_number=row_number,
                row_data=dict(raw_row),
                resolved_client_id=resolved.resolved_client_id,
                resolved_program_id=resolved.resolved_program_id,
                resolved_pharmacy_npi=resolved.resolved_pharmacy_npi,
                resolved_ndc=resolved.resolved_ndc,
                resolution_method=resolved.resolution_method,
                resolution_notes=resolved.resolution_notes,
            )
            chunk.append(upload_row)
            _update_counters(counters, resolved)

            if len(chunk) >= chunk_size:
                _flush_chunk()

    if chunk:
        _flush_chunk()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_or_resume_run(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    path: str,
    created_by: uuid.UUID,
    resume: bool = False,
    force: bool = False,
) -> "DetectionRun":  # noqa: F821
    """Create a new DetectionRun, or return/replace an existing one.

    Advisory lock on hashtext(tenant_id:sha256) is acquired before querying
    so concurrent callers for the same file serialise. The partial unique index
    uq_detection_runs_tenant_sha_active (migration 0009) is the DB backstop.

    Args:
        db:          SQLAlchemy Session inside a live transaction.
        tenant_id:   Tenant UUID stored on the run and used as the lock key.
        path:        Filesystem path to the CSV file. Streamed once for SHA-256
                     and row count.
        created_by:  User UUID (NOT NULL column).
        resume:      Return an existing in_progress run unchanged.
        force:       Delete prior csv_upload_rows and create a fresh run when
                     a failed (or completed) run exists.

    Returns:
        DetectionRun with status='in_progress'.

    Raises:
        DetectionRunExistsError: completed run exists and force=False.
        RunInProgressError: in_progress run exists and resume=False.
        IntegrityError (propagated): race past the advisory lock hit the
            partial unique index -- treat as concurrent collision.
    """
    # Late import to avoid circular imports at module load.
    from src.models.detection_run_models import CsvUploadRow, DetectionRun

    sha256, data_row_count = _compute_sha256_and_count(path)
    lock_key = f"{tenant_id}:{sha256}"

    # Serialise concurrent callers before any query or insert.
    _acquire_advisory_lock(db, lock_key)

    existing = (
        db.query(DetectionRun)
        .filter(
            DetectionRun.tenant_id == tenant_id,
            DetectionRun.source_sha256 == sha256,
        )
        .first()
    )

    if existing is not None:
        if existing.status == "completed" and not force:
            raise DetectionRunExistsError(
                f"File already ingested: tenant={tenant_id} sha={sha256[:12]}. "
                "Pass force=True to re-ingest."
            )
        if existing.status == "in_progress":
            if resume:
                return existing
            raise RunInProgressError(
                f"Detection run in progress: id={existing.id} "
                f"tenant={tenant_id} sha={sha256[:12]}. "
                "Pass resume=True to attach to it."
            )
        if existing.status == "failed" or force:
            # Delete stale upload rows; a new run is created below.
            db.query(CsvUploadRow).filter(
                CsvUploadRow.detection_run_id == existing.id
            ).delete(synchronize_session="fetch")
            db.flush()

    filename = Path(path).name
    run_label = f"{filename}:{sha256[:12]}"

    run = DetectionRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        data_source="csv_upload",
        run_label=run_label,
        source_path=path,
        source_filename=filename,
        source_sha256=sha256,
        status="in_progress",
        started_at=datetime.now(UTC),
        created_by=created_by,
        resolution_stats={"expected_count": data_row_count},
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        # Race past advisory lock hit the partial unique index.
        db.rollback()
        raise

    return run


def load_csv(
    db: Session,
    run: "DetectionRun",  # noqa: F821
    *,
    chunk_size: int = 10,
) -> int:
    """Stream the CSV file and bulk-insert CsvUploadRow records.

    Reads run.source_path via csv.DictReader -- never loads the whole file
    into memory.

    Dialect branch:
      PostgreSQL: rows are accumulated into batches of _INSERT_BATCH_SIZE
        tuples and sent via psycopg2.extras.execute_values using the raw
        cursor from the *existing* SQLAlchemy connection.  Because load_csv
        runs on the same connection that already has
        SET LOCAL app.current_tenant_id in effect, RLS WITH CHECK
        policies on reclaimrx.csv_upload_rows pass without any additional
        plumbing.  COPY FROM is NOT used: it is rejected by Postgres on
        RLS-forced tables for non-superuser roles.
      Other dialects (SQLite in tests): original ORM add()/flush() path in
        batches of chunk_size.  All resolution/stat logic is identical so
        the 54-row fixture tests exercise the full code path.

    DOS hygiene (applies after resolve_row):
      - If date_of_service is present but parse_dos returns None (e.g.
        9999-09-09), the row's resolution_method is overridden to 'unmapped'
        and resolution_notes is set to 'invalid DOS', UNLESS the row was
        already unmapped due to missing pharmacy_npi (in which case the
        existing 'missing pharmacy_npi' note is preserved).
      - Null-NDC rows with a valid pharmacy_npi remain 'declared'.

    After streaming, merges into run.resolution_stats:
      - inserted_count : total rows written to csv_upload_rows
      - declared       : count of rows with resolution_method == 'declared'
      - unmapped       : count of rows with resolution_method == 'unmapped'
      - by_reason      : {resolution_notes: count} for unmapped rows

    Args:
        db:         SQLAlchemy Session.
        run:        DetectionRun in 'in_progress' status.
        chunk_size: Number of rows per ORM flush on non-Postgres dialects
                    (default 10).  Ignored on the PostgreSQL execute_values
                    path, which always uses _INSERT_BATCH_SIZE.

    Returns:
        Total number of CsvUploadRow records inserted.
    """
    # Late import to avoid circular imports at module load.
    from src.detection.parsing import parse_dos
    from src.models.detection_run_models import CsvUploadRow

    tenant_id: uuid.UUID = run.tenant_id
    detection_run_id: uuid.UUID = run.id
    source_path: str = run.source_path

    # Shared mutable counters updated by both path implementations.
    counters: dict = {
        "inserted": 0,
        "declared": 0,
        "unmapped": 0,
        "by_reason": {},
    }

    # Determine which path to use based on the active dialect.
    use_execute_values: bool = db.bind.dialect.name == "postgresql"  # type: ignore[union-attr]

    if use_execute_values:
        _stream_execute_values(
            db, source_path, tenant_id, detection_run_id, parse_dos, counters
        )
    else:
        _stream_orm(
            db, source_path, tenant_id, detection_run_id,
            parse_dos, counters, CsvUploadRow, chunk_size,
        )

    inserted_count: int = counters["inserted"]
    declared_count: int = counters["declared"]
    unmapped_count: int = counters["unmapped"]
    by_reason: dict = counters["by_reason"]

    # Merge resolution stats into the run's JSONB column.
    # Reassign to trigger SQLAlchemy JSONB mutation tracking.
    stats = dict(run.resolution_stats)
    stats["inserted_count"] = inserted_count
    stats["declared"] = declared_count
    stats["unmapped"] = unmapped_count
    stats["by_reason"] = by_reason
    run.resolution_stats = stats
    db.flush()

    return inserted_count
