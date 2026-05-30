"""CSV ingestion helpers: row entity resolution + detection-run creation.

Public API
----------
resolve_row(row) -> ResolvedRow
    Pure function -- no I/O, no DB, no side effects.

create_or_resume_run(db, *, tenant_id, path, created_by, resume, force)
    -> DetectionRun
    Idempotent detection-run creation with advisory lock + partial unique
    index guard.

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