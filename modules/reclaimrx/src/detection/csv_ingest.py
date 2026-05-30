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
    Insert CsvUploadRow records in chunks of chunk_size, flush after each
    chunk.  Apply DOS hygiene: rows whose date_of_service fails parse_dos
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
    load_csv never swallows exceptions; partially-flushed chunks are
    rolled back when the caller's surrounding transaction is rolled back.

resolution_method values match the DB CHECK constraint:
    'declared' | 'group_id_lookup' | 'ndc_lookup' | 'manual' | 'unmapped'

v1 scope:
  - declared  : pharmacy_npi is present and non-empty.
  - unmapped  : pharmacy_npi is absent or empty.
  - resolved_client_id and resolved_program_id are always None -- raw
    integer client_id/program_id values are not coerced to UUIDs in v1.
    The raw values remain accessible via the original row dict.
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
    """Stream the CSV file and insert CsvUploadRow records in chunks.

    Reads run.source_path via csv.DictReader -- never loads the whole file
    into memory. Inserts rows in batches of chunk_size, flushing after each
    batch so memory footprint stays bounded.

    DOS hygiene (applies after resolve_row):
      - If date_of_service is present but parse_dos returns None (e.g.
        9999-09-09), the row's resolution_method is overridden to 'unmapped'
        and resolution_notes is set to 'invalid DOS', UNLESS the row was
        already unmapped due to missing pharmacy_npi (in which case the
        existing 'missing pharmacy_npi' note is preserved; the 'invalid DOS'
        reason is still counted in by_reason).
      - Null-NDC rows with a valid pharmacy_npi remain 'declared'; ndc-
        requiring rules simply won't match them in Phase 3.

    After streaming, merges into run.resolution_stats:
      - inserted_count : total rows written to csv_upload_rows
      - declared       : count of rows with resolution_method == 'declared'
      - unmapped       : count of rows with resolution_method == 'unmapped'
      - by_reason      : {resolution_notes: count} for unmapped rows

    Full-coverage gate: inserted_count and expected_count are both present in
    resolution_stats. Phase 3 detection checks
    ``inserted_count == expected_count`` before running rules.

    Chunk failure: exceptions propagate unchanged. The caller must mark the
    run 'failed' in a separate transaction. Partially-inserted chunks are
    rolled back when the caller's surrounding transaction is rolled back.

    Args:
        db:         SQLAlchemy Session.
        run:        DetectionRun in 'in_progress' status.
        chunk_size: Number of rows to add() and flush() at once (default 10).

    Returns:
        Total number of CsvUploadRow records inserted.
    """
    # Late import to avoid circular imports at module load.
    from src.detection.parsing import parse_dos
    from src.models.detection_run_models import CsvUploadRow

    tenant_id: uuid.UUID = run.tenant_id
    detection_run_id: uuid.UUID = run.id
    source_path: str = run.source_path

    inserted_count: int = 0
    declared_count: int = 0
    unmapped_count: int = 0
    by_reason: dict[str, int] = {}

    chunk: list = []

    def _flush_chunk() -> None:
        for obj in chunk:
            db.add(obj)
        db.flush()
        chunk.clear()

    with open(source_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row_number, raw_row in enumerate(reader, start=1):
            # Entity resolution from pharmacy_npi / ndc.
            resolved = resolve_row(raw_row)

            # DOS hygiene: override resolution if date_of_service is invalid.
            dos_str = (raw_row.get("date_of_service", "") or "").strip()
            if dos_str:
                dos_valid = parse_dos(dos_str) is not None
                if not dos_valid:
                    if resolved.resolution_method != "unmapped":
                        # Promote to unmapped; by_reason will be counted below.
                        resolved = ResolvedRow(
                            resolved_pharmacy_npi=resolved.resolved_pharmacy_npi,
                            resolved_ndc=resolved.resolved_ndc,
                            resolved_client_id=resolved.resolved_client_id,
                            resolved_program_id=resolved.resolved_program_id,
                            resolution_method="unmapped",
                            resolution_notes="invalid DOS",
                        )

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

            if resolved.resolution_method == "declared":
                declared_count += 1
            else:
                unmapped_count += 1
                note = resolved.resolution_notes or "unspecified"
                by_reason[note] = by_reason.get(note, 0) + 1

            inserted_count += 1

            if len(chunk) >= chunk_size:
                _flush_chunk()

    # Flush any remaining rows in the last partial chunk.
    if chunk:
        _flush_chunk()

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