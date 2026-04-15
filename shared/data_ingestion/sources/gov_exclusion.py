"""Government program BIN/PCN CSV loader.

Loads state Medicaid (and other government program) BIN data from CSV files
produced by the research teammates into shared.government_program_bins.

Expected CSV columns (produced by research teammates 2-6):
  state, bin, pcn, group_number, plan_type, plan_subtype, pbm_name,
  plan_name, mco_name, confidence, source, source_date, notes

Validation rules:
  - BIN: must be 1-6 digits; left-padded with zeros to 6 digits.
  - state: must be a valid 2-letter US state/territory code (or empty for
    federal programs).
  - plan_type: must be one of VALID_PLAN_TYPES.
  - source: must not be empty.
  - Lines starting with # are treated as comments and skipped.

LESSON-004: Use \\A...\\Z regex anchors for all validation.
LESSON-011: GovernmentProgramBin is global reference data — no tenant_id.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from shared.models.gov_exclusion_tables import VALID_PLAN_TYPES, GovernmentProgramBin

logger = logging.getLogger(__name__)

# LESSON-004: strict anchors throughout
_BIN_RE = re.compile(r"\A\d{1,6}\Z")
_STATE_RE = re.compile(r"\A[A-Za-z]{2}\Z")

# All valid US state and territory 2-letter codes
_VALID_STATES = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "MP", "AS",
})

_EXPECTED_COLUMNS = {
    "state", "bin", "pcn", "group_number", "plan_type", "plan_subtype",
    "pbm_name", "plan_name", "mco_name", "confidence", "source",
    "source_date", "notes",
}

_BATCH_SIZE = 500


@dataclass
class CsvIngestionResult:
    """Result of a CSV load operation."""

    source: str
    status: str = "in_progress"  # completed | failed | in_progress
    records_processed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    records_errored: int = 0
    error_message: str | None = None
    error_details: list[dict[str, Any]] = field(default_factory=list)


def _parse_source_date(raw: str | None) -> date | None:
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _validate_row(row: dict[str, str], row_num: int) -> tuple[dict[str, Any] | None, str | None]:
    """Validate and normalize a CSV row.

    Returns (normalized_dict, None) on success or (None, error_message) on failure.
    """
    raw_bin = (row.get("bin") or "").strip()
    if not raw_bin or not _BIN_RE.fullmatch(raw_bin):
        return None, f"Row {row_num}: invalid BIN '{raw_bin}' (must be 1-6 digits)"

    normalized_bin = raw_bin.zfill(6)

    state = (row.get("state") or "").strip().upper() or None
    if state and (not _STATE_RE.fullmatch(state) or state not in _VALID_STATES):
        return None, f"Row {row_num}: invalid state '{state}'"

    plan_type = (row.get("plan_type") or "").strip().upper()
    if not plan_type or plan_type not in VALID_PLAN_TYPES:
        return None, f"Row {row_num}: invalid plan_type '{plan_type}' (must be one of {sorted(VALID_PLAN_TYPES)})"

    source = (row.get("source") or "").strip()
    if not source:
        return None, f"Row {row_num}: source must not be empty"

    confidence = (row.get("confidence") or "HIGH").strip().upper()
    if confidence not in {"HIGH", "MEDIUM", "LOW"}:
        confidence = "HIGH"

    return {
        "bin": normalized_bin,
        "pcn": (row.get("pcn") or "").strip() or None,
        "group_number": (row.get("group_number") or "").strip() or None,
        "plan_type": plan_type,
        "plan_subtype": (row.get("plan_subtype") or "").strip() or None,
        "pbm_name": (row.get("pbm_name") or "").strip() or None,
        "plan_name": (row.get("plan_name") or "").strip() or None,
        "mco_name": (row.get("mco_name") or "").strip() or None,
        "state": state,
        "confidence": confidence,
        "source": source,
        "source_date": _parse_source_date(row.get("source_date")),
        "notes": (row.get("notes") or "").strip() or None,
    }, None


def _upsert_row(db: Session, data: dict[str, Any]) -> str:
    """Upsert one BIN row. Returns 'inserted' or 'updated'."""
    existing = (
        db.query(GovernmentProgramBin)
        .filter(
            GovernmentProgramBin.bin == data["bin"],
            GovernmentProgramBin.pcn == data["pcn"],
            GovernmentProgramBin.group_number == data["group_number"],
        )
        .first()
    )

    now = datetime.now(UTC)

    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        existing.updated_at = now
        return "updated"
    else:
        entry = GovernmentProgramBin(
            id=uuid.uuid4(),
            government_flag=True,
            created_at=now,
            updated_at=now,
            **data,
        )
        db.add(entry)
        return "inserted"


async def load_state_medicaid_csv(file_path: Path, db: Session) -> CsvIngestionResult:
    """Load a state Medicaid CSV file into shared.government_program_bins.

    Skips comment lines (starting with #). Validates each row before upsert.
    Commits in batches of _BATCH_SIZE.

    Parameters
    ----------
    file_path: Path to the CSV file.
    db:        SQLAlchemy Session (caller owns the transaction lifecycle).
    """
    result = CsvIngestionResult(source=str(file_path))

    try:
        with file_path.open(newline="", encoding="utf-8", errors="replace") as fh:
            result = _load_from_reader(fh, db, str(file_path))
    except OSError as exc:
        result.status = "failed"
        result.error_message = str(exc)
        logger.error(
            "Failed to open government exclusion CSV",
            extra={"gov_excl_file": str(file_path), "gov_excl_error": str(exc)},
        )

    return result


async def load_state_medicaid_csv_from_bytes(
    content: bytes, db: Session
) -> CsvIngestionResult:
    """Load government program BINs from raw CSV bytes (used by API import endpoint)."""
    text = content.decode("utf-8", errors="replace")
    return _load_from_reader(io.StringIO(text), db, source="api_upload")


def _load_from_reader(
    fh: Any, db: Session, source: str
) -> CsvIngestionResult:
    """Core CSV parsing and load logic shared by file and bytes entry points."""
    result = CsvIngestionResult(source=source)

    reader = csv.DictReader(
        (line for line in fh if not line.lstrip().startswith("#"))
    )

    batch_actions: list[tuple[dict[str, Any], int]] = []
    row_num = 0

    for raw_row in reader:
        row_num += 1
        result.records_processed += 1

        normalized_data, error = _validate_row(dict(raw_row), row_num)
        if error:
            result.records_errored += 1
            result.error_details.append({"row": row_num, "error": error})
            logger.warning(
                "Government exclusion CSV row validation failed",
                extra={"gov_excl_source": source, "gov_excl_row": row_num, "gov_excl_error": error},
            )
            continue

        batch_actions.append((normalized_data, row_num))

        if len(batch_actions) >= _BATCH_SIZE:
            _flush_batch(db, batch_actions, result, source)
            batch_actions.clear()

    if batch_actions:
        _flush_batch(db, batch_actions, result, source)

    result.status = "completed"
    logger.info(
        "Government exclusion CSV load complete",
        extra={
            "gov_excl_source": source,
            "gov_excl_processed": result.records_processed,
            "gov_excl_inserted": result.records_inserted,
            "gov_excl_updated": result.records_updated,
            "gov_excl_errored": result.records_errored,
        },
    )
    return result


def _flush_batch(
    db: Session,
    batch: list[tuple[dict[str, Any], int]],
    result: CsvIngestionResult,
    source: str,
) -> None:
    for data, row_num in batch:
        try:
            action = _upsert_row(db, data)
            if action == "inserted":
                result.records_inserted += 1
            else:
                result.records_updated += 1
        except Exception as exc:
            result.records_errored += 1
            result.error_details.append({"row": row_num, "error": str(exc)[:300]})
            logger.warning(
                "Government exclusion CSV row upsert failed",
                extra={
                    "gov_excl_source": source,
                    "gov_excl_row": row_num,
                    "gov_excl_error": str(exc)[:200],
                },
            )
    try:
        db.flush()
    except Exception as exc:
        db.rollback()
        logger.error(
            "Government exclusion CSV batch flush failed",
            extra={"gov_excl_source": source, "gov_excl_error": str(exc)[:300]},
        )


__all__ = [
    "load_state_medicaid_csv",
    "load_state_medicaid_csv_from_bytes",
    "CsvIngestionResult",
]
