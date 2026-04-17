"""State Medicaid BIN/PCN bulk loader.

Loads regional CSV files (northeast, southeast, midwest, south_central, west)
into shared.government_program_bins for Medicaid plan identification.

CSV format (header required):
  bin,pcn,group_number,state,plan_type,plan_subtype,mco_name,plan_name,
  pbm_name,confidence,source,source_date,effective_date,notes

Rules:
  - BIN: 6 digits; left-pad with zeros if 1–5 digits provided
  - state: 2-letter US state/territory code (see VALID_STATES)
  - plan_type: MEDICAID_FFS | MEDICAID_MCO | MEDICAID_CHIP | MEDICAID_DUAL
  - confidence: HIGH | MEDIUM | LOW
  - source: not empty
  - Lines starting with '#' are skipped (comments)

Upsert logic: ON CONFLICT (bin, pcn, group_number) DO UPDATE using
  higher-confidence row when confidence differs; otherwise overwrite
  non-key fields.

LESSON-004: re.fullmatch() for all security-sensitive regex.
LESSON-005: log extra keys prefixed with medicaid_ or ingest_.
LESSON-011: Global reference table — no TenantScopedMixin.
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.models.gov_exclusion_tables import (
    GovernmentProgramBin,
    VALID_CONFIDENCE_LEVELS,
)

logger = logging.getLogger(__name__)

_MEDICAID_PLAN_TYPES = frozenset({
    "MEDICAID_FFS",
    "MEDICAID_MCO",
    "MEDICAID_CHIP",
    "MEDICAID_DUAL",
})

# All 50 states + DC + US territories (56 total)
VALID_STATES: frozenset[str] = frozenset({
    # 50 states
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    # DC + territories
    "DC", "PR", "VI", "GU", "MP", "AS",
})

# LESSON-004: re.fullmatch() — never re.match() for security-sensitive validation
_BIN_RE = re.compile(r"\A\d{1,6}\Z")
_STATE_LIKE_RE = re.compile(r"\A[A-Za-z]{2}\Z")

_CONFIDENCE_RANK: dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

_REGIONS = ["northeast", "southeast", "midwest", "south_central", "west"]
_MEDICAID_DATA_DIR = Path("data/reference/medicaid")

_BATCH_SIZE = 500


@dataclass
class RowError:
    row_number: int
    raw: dict[str, str]
    reason: str


@dataclass
class LoadResult:
    region: str
    file_path: Path
    rows_parsed: int = 0
    rows_upserted: int = 0
    rows_skipped: int = 0
    errors: list[RowError] = field(default_factory=list)
    per_state_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class BulkLoadSummary:
    results: dict[str, LoadResult] = field(default_factory=dict)
    cross_region_duplicates: int = 0
    plan_type_conflicts: list[dict[str, str]] = field(default_factory=list)
    states_covered: list[str] = field(default_factory=list)
    states_missing: list[str] = field(default_factory=list)
    total_upserted: int = 0


def _parse_date(raw: str | None) -> Optional[date]:
    if not raw or not raw.strip():
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _validate_row(
    row: dict[str, str], row_number: int
) -> tuple[dict[str, str] | None, RowError | None]:
    """Validate and normalize one CSV row.

    Returns (normalized_dict, None) on success, (None, RowError) on failure.
    """
    raw_bin = row.get("bin", "").strip()
    if not raw_bin or not _BIN_RE.fullmatch(raw_bin):
        return None, RowError(row_number, row, f"Invalid BIN: {raw_bin!r}")

    # Left-pad BIN to 6 digits
    normalized_bin = raw_bin.zfill(6)

    state = row.get("state", "").strip().upper()
    if not _STATE_LIKE_RE.fullmatch(state) or state not in VALID_STATES:
        return None, RowError(row_number, row, f"Invalid state: {state!r}")

    plan_type = row.get("plan_type", "").strip().upper()
    if plan_type not in _MEDICAID_PLAN_TYPES:
        return None, RowError(row_number, row, f"Invalid plan_type: {plan_type!r}")

    confidence = row.get("confidence", "").strip().upper()
    if confidence not in VALID_CONFIDENCE_LEVELS:
        return None, RowError(row_number, row, f"Invalid confidence: {confidence!r}")

    source = row.get("source", "").strip()
    if not source:
        return None, RowError(row_number, row, "source must not be empty")

    return {
        "bin": normalized_bin,
        "pcn": row.get("pcn", "").strip() or None,
        "group_number": row.get("group_number", "").strip() or None,
        "state": state,
        "plan_type": plan_type,
        "plan_subtype": row.get("plan_subtype", "").strip() or None,
        "mco_name": row.get("mco_name", "").strip() or None,
        "plan_name": row.get("plan_name", "").strip() or None,
        "pbm_name": row.get("pbm_name", "").strip() or None,
        "confidence": confidence,
        "source": source,
        "source_date": _parse_date(row.get("source_date")),
        "effective_date": _parse_date(row.get("effective_date")),
        "notes": row.get("notes", "").strip() or None,
    }, None


def _upsert_row(db: Session, normalized: dict[str, str]) -> str:
    """Upsert one validated row. Returns 'inserted' or 'updated'."""
    existing: GovernmentProgramBin | None = (
        db.query(GovernmentProgramBin)
        .filter(
            GovernmentProgramBin.bin == normalized["bin"],
            GovernmentProgramBin.pcn == normalized["pcn"],
            GovernmentProgramBin.group_number == normalized["group_number"],
        )
        .first()
    )

    if existing is None:
        row = GovernmentProgramBin(
            bin=normalized["bin"],
            pcn=normalized["pcn"],
            group_number=normalized["group_number"],
            state=normalized["state"],
            plan_type=normalized["plan_type"],
            plan_subtype=normalized["plan_subtype"],
            mco_name=normalized["mco_name"],
            plan_name=normalized["plan_name"],
            pbm_name=normalized["pbm_name"],
            confidence=normalized["confidence"],
            source=normalized["source"],
            source_date=normalized["source_date"],
            effective_date=normalized["effective_date"],
            notes=normalized["notes"],
            government_flag=True,
        )
        db.add(row)
        return "inserted"

    # Prefer higher-confidence row (lower rank number = better confidence)
    incoming_rank = _CONFIDENCE_RANK.get(normalized["confidence"], 99)
    existing_rank = _CONFIDENCE_RANK.get(existing.confidence, 99)
    if incoming_rank <= existing_rank:
        existing.state = normalized["state"]
        existing.plan_type = normalized["plan_type"]
        existing.plan_subtype = normalized["plan_subtype"]
        existing.mco_name = normalized["mco_name"]
        existing.plan_name = normalized["plan_name"]
        existing.pbm_name = normalized["pbm_name"]
        existing.confidence = normalized["confidence"]
        existing.source = normalized["source"]
        existing.source_date = normalized["source_date"]
        existing.effective_date = normalized["effective_date"]
        existing.notes = normalized["notes"]
        existing.government_flag = True
    return "updated"


def _build_conflict_list(
    key_to_regions: dict[tuple[str, str | None, str | None], list[tuple[str, str]]]
) -> list[dict[str, str]]:
    """Build conflict report from the key→(region, plan_type) map."""
    conflicts = []
    for (bin_val, pcn, grp), entries in key_to_regions.items():
        plan_types = {pt for _, pt in entries}
        if len(plan_types) > 1:
            region_a, pt_a = entries[0]
            region_b, pt_b = entries[-1]
            conflicts.append({
                "bin": bin_val,
                "pcn": pcn or "",
                "group_number": grp or "",
                "region_a": region_a,
                "plan_type_a": pt_a,
                "region_b": region_b,
                "plan_type_b": pt_b,
            })
            logger.error(
                "Medicaid plan_type conflict detected",
                extra={
                    "medicaid_bin": bin_val,
                    "medicaid_pcn": pcn,
                    "medicaid_conflict_types": str(plan_types),
                },
            )
    return conflicts


class StateMedicaidBinLoader:
    """Bulk loader for regional Medicaid BIN/PCN CSV files.

    Validates, deduplicates, and upserts rows into
    shared.government_program_bins. Tracks per-state counts and
    aggregates validation errors without aborting the whole load.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def load_csv(self, file_path: Path, region: str = "") -> LoadResult:
        """Load one regional CSV file.

        Skips comment lines (starting with '#'). Validates each row.
        Upserts valid rows. Aggregates errors without aborting.
        Flushes in batches of _BATCH_SIZE to limit memory usage.
        """
        result = LoadResult(region=region or file_path.stem, file_path=file_path)

        if not file_path.is_file():
            result.errors.append(
                RowError(0, {}, f"File not found: {file_path}")
            )
            logger.error(
                "Medicaid CSV file not found",
                extra={"medicaid_file": str(file_path)},
            )
            return result

        batch_count = 0

        with file_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(
                (line for line in fh if not line.lstrip().startswith("#"))
            )

            for row_number, raw_row in enumerate(reader, start=2):
                result.rows_parsed += 1
                normalized, error = _validate_row(raw_row, row_number)
                if error is not None:
                    result.errors.append(error)
                    result.rows_skipped += 1
                    continue

                assert normalized is not None
                _upsert_row(self._db, normalized)
                result.rows_upserted += 1
                state = normalized["state"]
                result.per_state_counts[state] = (
                    result.per_state_counts.get(state, 0) + 1
                )

                batch_count += 1
                if batch_count >= _BATCH_SIZE:
                    self._db.flush()
                    batch_count = 0

        if batch_count > 0:
            self._db.flush()

        self._db.commit()

        logger.info(
            "Medicaid CSV loaded",
            extra={
                "medicaid_region": result.region,
                "medicaid_rows_parsed": result.rows_parsed,
                "medicaid_rows_upserted": result.rows_upserted,
                "medicaid_rows_skipped": result.rows_skipped,
                "medicaid_error_count": len(result.errors),
            },
        )
        return result

    def load_all_regions(
        self,
        data_dir: Path = _MEDICAID_DATA_DIR,
    ) -> dict[str, LoadResult]:
        """Load all 5 regional CSV files and return per-region results."""
        return {
            region: self.load_csv(data_dir / f"{region}.csv", region=region)
            for region in _REGIONS
        }

    def detect_conflicts(
        self,
        results: dict[str, LoadResult],
    ) -> list[dict[str, str]]:
        """Detect cross-region plan_type conflicts for the same BIN/PCN/Group.

        A conflict is two regions providing different plan_types for the
        same natural key after loading. Returns a list of conflict dicts
        with keys: bin, pcn, group_number, region_a, plan_type_a,
        region_b, plan_type_b.

        Called AFTER load_all_regions. Queries the live DB state.
        """
        # Build (bin, pcn, group_number) → set of plan_types seen across regions
        key_to_regions: dict[tuple[str, str | None, str | None], list[tuple[str, str]]] = {}

        for region, result in results.items():
            if result.rows_upserted == 0:
                continue
            rows: list[GovernmentProgramBin] = (
                self._db.query(GovernmentProgramBin)
                .filter(
                    GovernmentProgramBin.state.in_(
                        list(result.per_state_counts.keys())
                    ),
                    GovernmentProgramBin.plan_type.in_(list(_MEDICAID_PLAN_TYPES)),
                )
                .all()
            )
            for row in rows:
                key = (row.bin, row.pcn, row.group_number)
                entry = (region, row.plan_type)
                if key not in key_to_regions:
                    key_to_regions[key] = [entry]
                else:
                    key_to_regions[key].append(entry)

        return _build_conflict_list(key_to_regions)

    def build_summary(
        self,
        results: dict[str, LoadResult],
        conflicts: list[dict[str, str]],
    ) -> BulkLoadSummary:
        """Aggregate load results into a BulkLoadSummary."""
        summary = BulkLoadSummary(results=results, plan_type_conflicts=conflicts)
        summary.total_upserted = sum(r.rows_upserted for r in results.values())

        # States covered = union of per_state_counts keys across all regions
        covered: set[str] = set()
        for result in results.values():
            covered.update(result.per_state_counts.keys())
        summary.states_covered = sorted(covered)
        summary.states_missing = sorted(VALID_STATES - covered)

        # Cross-region duplicates: same natural key loaded by >1 region
        # (not a conflict — same plan_type, just reported for transparency)
        key_regions: dict[tuple[str, str | None, str | None], set[str]] = {}
        for region, result in results.items():
            if result.rows_upserted == 0:
                continue
            rows: list[GovernmentProgramBin] = (
                self._db.query(GovernmentProgramBin)
                .filter(
                    GovernmentProgramBin.state.in_(
                        list(result.per_state_counts.keys()) or ["__NONE__"]
                    ),
                    GovernmentProgramBin.plan_type.in_(list(_MEDICAID_PLAN_TYPES)),
                )
                .all()
            )
            for row in rows:
                key = (row.bin, row.pcn, row.group_number)
                if key not in key_regions:
                    key_regions[key] = {region}
                else:
                    key_regions[key].add(region)

        summary.cross_region_duplicates = sum(
            1 for regions in key_regions.values() if len(regions) > 1
        )
        return summary


from collections.abc import Iterator as _Iterator
from typing import Any as _Any

from shared.data_ingestion.base import DataSourceIngester, IngestionResult


class MedicaidBinIngester(DataSourceIngester):
    """DataSourceIngester wrapper around StateMedicaidBinLoader.

    The confidence-based upsert and plan_type-conflict detection live in
    ``StateMedicaidBinLoader``; wrapping it in a DataSourceIngester exposes
    the medicaid loader through the same orchestration surface as the
    other refactored loaders (download/parse/load/run) without duplicating
    the specialised confidence-resolution logic.

    No HTTP download — regional CSVs are pre-staged under
    ``data/reference/medicaid/``. ``download()`` returns that directory
    path; ``parse()`` is a no-op because ``StateMedicaidBinLoader`` owns
    the read+validate+upsert cycle per file, and ``load()`` just invokes
    it across all five regional CSVs.
    """

    source_name = "state_medicaid_bins"

    async def download(self) -> Path:
        if not _MEDICAID_DATA_DIR.is_dir():
            raise FileNotFoundError(
                f"Medicaid data dir missing: {_MEDICAID_DATA_DIR}. "
                "Regional CSVs must be pre-staged."
            )
        return _MEDICAID_DATA_DIR

    def parse(self, file_path: Path) -> _Iterator[dict[str, _Any]]:
        return iter([])

    async def load(
        self, records: _Iterator[dict[str, _Any]]
    ) -> IngestionResult:
        loader = StateMedicaidBinLoader(db=self._db)
        results = loader.load_all_regions()
        total_parsed = sum(r.rows_parsed for r in results.values())
        total_upserted = sum(r.rows_upserted for r in results.values())
        total_skipped = sum(r.rows_skipped for r in results.values())
        total_errors = sum(len(r.errors) for r in results.values())

        for region, result in results.items():
            logger.info(
                "Medicaid region loaded",
                extra={
                    "ingest_source": self.source_name,
                    "medicaid_region": region,
                    "medicaid_rows_parsed": result.rows_parsed,
                    "medicaid_rows_upserted": result.rows_upserted,
                    "medicaid_rows_skipped": result.rows_skipped,
                    "medicaid_error_count": len(result.errors),
                },
            )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=total_parsed,
            records_inserted=total_upserted,
            records_skipped=total_skipped,
            records_errored=total_errors,
        )


__all__ = [
    "BulkLoadSummary",
    "LoadResult",
    "MedicaidBinIngester",
    "RowError",
    "StateMedicaidBinLoader",
    "VALID_STATES",
    "_MEDICAID_DATA_DIR",
    "_MEDICAID_PLAN_TYPES",
    "_REGIONS",
    "_build_conflict_list",
]
