"""CMS Medicare Opt-Out Affidavits ingestion source.

Downloads the CMS Opt-Out Affidavits dataset (~30K rows) from the Socrata
API and upserts into prescriber_dir.medicare_opt_out.

After loading, cross-references prescriber_dir.prescribers to set
medicare_opt_out = TRUE for currently opted-out providers.

data.cms.gov v1 API:
  https://data.cms.gov/data-api/v1/dataset/{dataset_id}/data
  Pagination: ?size=<page>&offset=<N>   (NOT the older Socrata
  $limit/$offset — that style 404s on the v1 endpoint.)

LESSON-010: NPI plaintext — public NPPES identifier.
LESSON-011: Global reference — no TenantScopedMixin.
LESSON-004: \\A...\\Z regex anchors.
LESSON-005: log extra keys prefixed with ingest_.
financial-precision.md: No money columns in this table — no Decimal needed.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "cms_opt_out"
_DATASET_ID = "9887a515-7552-4693-bf58-735c77af46d7"
_API_BASE_URL = f"https://data.cms.gov/data-api/v1/dataset/{_DATASET_ID}/data"
_PAGE_SIZE = 5_000  # data.cms.gov v1 API uses `size` param, not `$limit`
_TIMEOUT_SECONDS = 60.0
_DEST_DIR = Path("data/reference/cms-opt-out")
_FILENAME = "opt_out.json"
_BATCH_SIZE = 1_000

# LESSON-004: \A...\Z
_NPI_RE = re.compile(r"\A\d{10}\Z")
_DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")

# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

_TABLE = "prescriber_directory.medicare_opt_out"
_SRC_FILE = "Socrata API"

for _col, _src, _desc, _dtype in [
    ("npi",                    "NPI",                    "10-digit NPI (plaintext, LESSON-010)",         "str"),
    ("first_name",             "First Name",             "Provider first name",                          "str"),
    ("last_name",              "Last Name",              "Provider last name",                           "str"),
    ("middle_name",            "Middle Name",            "Provider middle name",                         "str"),
    ("specialty",              "Specialty",              "Provider specialty",                           "str"),
    ("opt_out_effective_date", "Opt Out Effective Date", "Date opt-out became effective",               "date"),
    ("opt_out_end_date",       "Opt Out End Date",       "Date opt-out ends (NULL = indefinite)",       "date"),
    ("order_referring",        "Order/Referring",        "Can provider still order/refer (Y/N)",        "bool"),
    ("address",                "Address",                "Provider practice address",                   "str"),
    ("city",                   "City",                   "Provider city",                               "str"),
    ("state",                  "State",                  "Provider state",                              "str"),
    ("zip",                    "Zip",                    "Provider ZIP code",                           "str"),
    ("phone",                  "Phone",                  "Provider phone number",                       "str"),
    ("raw_payload",            "raw_payload",            "Full source row as JSONB fallback",           "dict"),
]:
    register_field(
        source=_SOURCE_NAME,
        table=_TABLE,
        column=_col,
        description=_desc,
        source_file=_SRC_FILE,
        source_position=_src,
        data_type=_dtype,
    )

# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    s = str(value).strip()
    # Try YYYY-MM-DD
    if _DATE_RE.match(s):
        try:
            parts = s.split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None
    # Try M/D/YYYY (CMS sometimes returns this format)
    if "/" in s:
        try:
            parts = s.split("/")
            if len(parts) == 3:
                return date(int(parts[2]), int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return None
    return None


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    s = str(value).strip().upper()
    if s in ("Y", "YES", "TRUE", "1"):
        return True
    if s in ("N", "NO", "FALSE", "0"):
        return False
    return None


def _get(row: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = row.get(k)
        if v is not None:
            return v
    return None


def parse_opt_out_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Parse one CMS Opt-Out API row into a normalized record.

    Returns None if NPI is missing or invalid.
    """
    npi_raw = str(
        _get(raw, "NPI", "npi", "Npi") or ""
    ).strip()
    if not _NPI_RE.match(npi_raw):
        logger.warning(
            "Opt-Out: skipping row with invalid NPI",
            extra={"ingest_source": _SOURCE_NAME, "ingest_raw_npi": npi_raw[:15]},
        )
        return None

    return {
        "npi": npi_raw,
        "first_name": str(_get(raw, "First Name", "first_name", "firstName") or "").strip() or None,
        "last_name": str(_get(raw, "Last Name", "last_name", "lastName") or "").strip() or None,
        "middle_name": str(_get(raw, "Middle Name", "middle_name", "middleName") or "").strip() or None,
        "specialty": str(_get(raw, "Specialty", "specialty") or "").strip() or None,
        "opt_out_effective_date": _parse_date(
            _get(raw, "Optout Effective Date", "Opt Out Effective Date", "opt_out_effective_date", "optOutEffectiveDate")
        ),
        "opt_out_end_date": _parse_date(
            _get(raw, "Optout End Date", "Opt Out End Date", "opt_out_end_date", "optOutEndDate")
        ),
        "order_referring": _parse_bool(
            _get(raw, "Eligible to Order and Refer", "Order/Referring", "order_referring", "orderReferring", "Order Referring")
        ),
        "address": " ".join(filter(None, [
            str(_get(raw, "First Line Street Address", "Address", "address") or "").strip(),
            str(_get(raw, "Second Line Street Address") or "").strip(),
        ])) or None,
        "city": str(_get(raw, "City Name", "City", "city") or "").strip() or None,
        "state": str(_get(raw, "State Code", "State", "state") or "").strip() or None,
        "zip": str(_get(raw, "Zip code", "Zip", "zip", "ZIP") or "").strip() or None,
        "phone": str(_get(raw, "Phone", "phone") or "").strip() or None,
        "raw_payload": dict(raw),
    }


# ---------------------------------------------------------------------------
# Ingester
# ---------------------------------------------------------------------------


class CmsOptOutIngester(DataSourceIngester):
    """Ingests CMS Medicare Opt-Out Affidavits dataset.

    After upsert, cross-references prescribers table to set
    medicare_opt_out status on matched NPI rows.

    Global reference data — NOT tenant-scoped (LESSON-011).
    NPI plaintext (LESSON-010).
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Paginate CMS Socrata API and write results to a local JSON file."""
        _DEST_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = _DEST_DIR / _FILENAME
        all_records: list[dict[str, Any]] = []
        offset = 0

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_TIMEOUT_SECONDS, connect=30.0),
            follow_redirects=True,
        ) as client:
            while True:
                params = {"size": str(_PAGE_SIZE), "offset": str(offset)}
                logger.info(
                    "Opt-Out: fetching page",
                    extra={
                        "ingest_source": _SOURCE_NAME,
                        "ingest_offset": offset,
                        "ingest_page_size": _PAGE_SIZE,
                    },
                )
                response = await client.get(_API_BASE_URL, params=params)
                response.raise_for_status()
                results: list[dict[str, Any]] = response.json()
                if not results:
                    break
                all_records.extend(results)
                offset += _PAGE_SIZE
                if len(results) < _PAGE_SIZE:
                    break

        logger.info(
            "Opt-Out: all pages fetched",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_total_records": len(all_records),
            },
        )
        with dest_path.open("w", encoding="utf-8") as fh:
            json.dump(all_records, fh)
        return dest_path

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse collected JSON file; yield normalized opt-out dicts."""
        with file_path.open(encoding="utf-8") as fh:
            records: list[dict[str, Any]] = json.load(fh)
        for raw in records:
            parsed = parse_opt_out_row(raw)
            if parsed is not None:
                yield parsed

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batch-upsert opt-out rows via flush_upsert_batch, then cross-reference.

        Wave 10a: switched from hand-rolled pg_insert / ORM-merge branching
        to the shared ``flush_upsert_batch`` primitive. Same in-batch dedup
        semantics (last-wins on NPI, since CMS publishes multiple affidavits
        per provider); cross-reference to prescribers.medicare_opt_out runs
        post-upsert as before.

        SQLite-path note: the shared primitive emits pg_insert + ON CONFLICT
        SQL, which SQLite 3.24+ parses compatibly (our integration tests
        confirm). The pre-refactor ORM-merge fallback is gone.
        """
        import importlib

        from shared.data_ingestion.batching import ErrorAggregator, flush_upsert_batch

        _m = importlib.import_module("src.models.medicare_tables")
        OptOutModel = _m.MedicareOptOut

        errors = ErrorAggregator()
        batch: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        all_npis: list[str] = []
        inserted = 0
        skipped = 0

        def _flush() -> None:
            nonlocal inserted, skipped
            if not batch:
                return
            for row in batch:
                row["updated_at"] = now
            ins, dd = flush_upsert_batch(
                self._db,
                source_name=_SOURCE_NAME,
                table=OptOutModel.__table__,
                unique_key=["npi"],
                rows=batch,
                errors=errors,
            )
            inserted += ins
            skipped += dd
            batch.clear()

        for record in records:
            all_npis.append(record["npi"])
            batch.append(record)
            if len(batch) >= _BATCH_SIZE:
                _flush()

        _flush()

        # Cross-reference: update prescribers.medicare_opt_out
        cross_ref_count = self._update_prescriber_opt_out_status(all_npis, now)

        errors.log_summary(source_name=_SOURCE_NAME)

        logger.info(
            "Opt-Out load complete",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_records_inserted": inserted,
                "ingest_records_skipped": skipped,
                "ingest_records_errored": errors.total_errors,
                "ingest_cross_ref_count": cross_ref_count,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=inserted + skipped + errors.total_errors,
            records_inserted=inserted,
            records_skipped=skipped,
            records_errored=errors.total_errors,
        )

    def _update_prescriber_opt_out_status(
        self,
        opt_out_npis: list[str],
        now: datetime,
    ) -> int:
        """Set medicare_opt_out on prescribers whose NPI is in opt_out table.

        Only sets True for active opt-outs (end_date IS NULL or in the future).
        """
        if not opt_out_npis:
            return 0

        import importlib
        from sqlalchemy import and_, or_, select, update

        _mm = importlib.import_module("src.models.medicare_tables")
        MedicareOptOut = _mm.MedicareOptOut
        _mp = importlib.import_module("src.models.tables")
        Prescriber = _mp.Prescriber

        today = date.today()

        active_npis_stmt = select(MedicareOptOut.npi).where(
            or_(
                MedicareOptOut.opt_out_end_date.is_(None),
                MedicareOptOut.opt_out_end_date > today,
            )
        )
        active_npis = [row[0] for row in self._db.execute(active_npis_stmt).fetchall()]

        ended_npis_stmt = select(MedicareOptOut.npi).where(
            and_(
                MedicareOptOut.opt_out_end_date.isnot(None),
                MedicareOptOut.opt_out_end_date <= today,
            )
        )
        ended_npis = [row[0] for row in self._db.execute(ended_npis_stmt).fetchall()]

        count = 0
        if active_npis:
            result = self._db.execute(
                update(Prescriber)
                .where(Prescriber.npi.in_(active_npis))
                .values(medicare_opt_out=True, updated_at=now)
            )
            count += result.rowcount

        if ended_npis:
            self._db.execute(
                update(Prescriber)
                .where(Prescriber.npi.in_(ended_npis))
                .values(medicare_opt_out=False, updated_at=now)
            )

        self._db.flush()
        return count


__all__ = [
    "CmsOptOutIngester",
    "parse_opt_out_row",
    "_parse_date",
    "_parse_bool",
]
