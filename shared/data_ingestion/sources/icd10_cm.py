"""ICD-10-CM (International Classification of Diseases, Clinical Modification) loader.

CMS publishes the ICD-10-CM diagnosis-code set twice per fiscal year:

* **Annual October release** — ``<FY>-code-descriptions-tabular-order.zip`` —
  e.g. ``2026-code-descriptions-tabular-order.zip`` is the FY2026 file,
  effective 2025-10-01 through 2026-03-31.

* **April mid-year update** — ``april-1-<YYYY>-code-descriptions-tabular-
  order.zip`` — effective YYYY-04-01 through the following September 30.

Both are ZIP archives containing several text files. We parse the
``icd10cm_order_<FY>.txt`` fixed-width file because it carries the richest
row: ordinal, 7-char code, billable flag, 60-char short description,
and variable-length long description.

Row layout (0-indexed):
  [0, 5)    ordinal number
  [6, 13)   code (7 CHAR, right-padded)
  [14, 15)  billable flag ('0' = header/parent, '1' = billable leaf)
  [16, 76)  short description (60 CHAR)
  [77,  ∞)  long description

The target table ``shared.icd10_cm_codes`` is versioned on
``(code, effective_date)`` so retrospective claim adjudication can
resolve the description that was valid at the date of service. Each
load is an upsert against the unique key — prior publications stay
intact.

LESSON-004: \\A...\\Z anchors on every security-sensitive regex.
LESSON-005: log keys prefixed with ``ingest_``.
LESSON-011: Global reference — no TenantScopedMixin.
"""

from __future__ import annotations

import json
import logging
import re
import zipfile
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import Table
from sqlalchemy.sql import text as sql_text

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.batching import ErrorAggregator, flush_upsert_batch
from shared.data_ingestion.downloader import download_to_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "icd10_cm"
_CMS_INDEX_URL = "https://www.cms.gov/medicare/coding-billing/icd-10-codes"
_CMS_FILE_BASE = "https://www.cms.gov"

# Filename matchers — two patterns cover the mid-year-April update and
# the annual October release. April takes precedence when both exist.
# \A..\Z anchoring per LESSON-004 on the matching function below.
_APRIL_ZIP_RE = re.compile(
    r"\Aapril-1-(\d{4})-code-descriptions-tabular-order\.zip\Z",
    re.IGNORECASE,
)
_ANNUAL_ZIP_RE = re.compile(
    r"\A(\d{4})-code-descriptions-tabular-order\.zip\Z",
    re.IGNORECASE,
)

# Text file inside the ZIP that we actually parse — CMS names it
# ``icd10cm_order_<FY>.txt`` inside a ``Code Descriptions/`` folder.
_ORDER_FILE_RE = re.compile(
    r"\AClinical Modification/|Code Descriptions/|\b(?=icd10cm_order_\d{4}\.txt\Z)"
)
_ORDER_FILE_INNER_RE = re.compile(r"icd10cm_order_\d{4}\.txt\Z")

# Download hygiene
_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50 MB ceiling (typical ZIP ~2–3 MB)
_CACHE_DIR = Path("data/reference/icd10-cm")
_BATCH_SIZE = 2_000

# Record layout positions (0-indexed slice bounds)
_COL_ORDINAL = slice(0, 5)
_COL_CODE = slice(6, 13)
_COL_BILLABLE = slice(14, 15)
_COL_SHORT_DESC = slice(16, 76)
_COL_LONG_DESC = slice(77, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _effective_date_from_filename(filename: str) -> date:
    """Return the effective date implied by a CMS ICD-10-CM zip filename.

    ``april-1-YYYY-...zip`` → ``YYYY-04-01``
    ``YYYY-...zip``         → ``(YYYY - 1)-10-01`` (FY starts Oct 1 of prior year)
    """
    m = _APRIL_ZIP_RE.match(filename)
    if m:
        return date(int(m.group(1)), 4, 1)
    m = _ANNUAL_ZIP_RE.match(filename)
    if m:
        return date(int(m.group(1)) - 1, 10, 1)
    raise ValueError(f"Unrecognized ICD-10-CM filename: {filename!r}")


def _choose_latest_filename(hrefs: list[str]) -> str | None:
    """Pick the newest ICD-10-CM descriptions zip from a list of scraped hrefs.

    Both April and annual patterns are considered; the one with the most
    recent effective date wins. Returns the bare filename (no path).
    """
    best_date: date | None = None
    best_filename: str | None = None
    for href in hrefs:
        fn = href.rsplit("/", 1)[-1]
        try:
            ed = _effective_date_from_filename(fn)
        except ValueError:
            continue
        if best_date is None or ed > best_date:
            best_date = ed
            best_filename = fn
    return best_filename


def _parse_fixed_width_line(line: str) -> dict[str, Any] | None:
    """Parse one line of ``icd10cm_order_<YYYY>.txt``. Returns ``None`` on empty."""
    if not line.strip():
        return None
    ordinal_str = line[_COL_ORDINAL].strip()
    code = line[_COL_CODE].strip()
    billable = line[_COL_BILLABLE].strip() == "1"
    short_desc = line[_COL_SHORT_DESC].rstrip()
    long_desc = line[_COL_LONG_DESC].rstrip()

    if not code:
        return None

    try:
        ordinal_num = int(ordinal_str) if ordinal_str else None
    except ValueError:
        ordinal_num = None

    return {
        "ordinal_num": ordinal_num,
        "code": code,
        "is_billable": billable,
        "short_description": short_desc or None,
        "long_description": long_desc or None,
    }


# ---------------------------------------------------------------------------
# Ingester
# ---------------------------------------------------------------------------


class Icd10CmIngester(DataSourceIngester):
    """Full-replace-per-publication loader for CMS ICD-10-CM code set.

    Versioned on ``(code, effective_date)``: each October or April
    publication adds rows for that effective date without disturbing
    prior publications. Claims dated between two publications resolve
    descriptions by selecting the max effective_date <= date_of_service.
    """

    source_name = _SOURCE_NAME

    def __init__(self, db_session: Any, *, source_csv: Path | None = None) -> None:
        super().__init__(db_session)
        # If set, skip download and parse this already-extracted .txt directly.
        # Filename must still match the r"icd10cm_order_\d{4}\.txt" pattern
        # so the effective date can be derived from the outer zip filename
        # via _override_effective_date (used by the CLI for file-upload).
        self._source_override: Path | None = source_csv
        self._override_effective_date: date | None = None

    # ------------------------------------------------------------------
    # download
    # ------------------------------------------------------------------

    async def download(self) -> Path:
        if self._source_override is not None:
            return self._source_override

        filename = await self._resolve_latest_filename()
        if filename is None:
            raise RuntimeError(
                "Could not locate any ICD-10-CM descriptions zip on "
                f"{_CMS_INDEX_URL}. CMS page structure may have changed."
            )
        url = f"{_CMS_FILE_BASE}/files/zip/{filename}"
        logger.info(
            "Downloading ICD-10-CM descriptions zip",
            extra={"ingest_source": self.source_name, "ingest_url": url},
        )
        zip_path = await download_to_file(
            url, _CACHE_DIR, max_bytes=_MAX_DOWNLOAD_BYTES, timeout_seconds=120.0
        )
        return zip_path

    async def _resolve_latest_filename(self) -> str | None:
        """Scrape the CMS ICD-10 index page for the newest descriptions zip."""
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "InfinityRx-ICD10-Loader/1.0"},
        ) as client:
            resp = await client.get(_CMS_INDEX_URL)
            resp.raise_for_status()
        hrefs = re.findall(r'href="([^"]+)"', resp.text)
        return _choose_latest_filename(hrefs)

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Stream-parse the order file inside the zip.

        ``file_path`` may be either the outer zip or a pre-extracted .txt. The
        effective date is resolved from whichever filename we have.
        """
        effective_date = self._resolve_effective_date(file_path)

        if file_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(file_path) as zf:
                inner_name = next(
                    (n for n in zf.namelist() if _ORDER_FILE_INNER_RE.search(n)),
                    None,
                )
                if inner_name is None:
                    raise RuntimeError(
                        f"No icd10cm_order_<YYYY>.txt inside {file_path.name}"
                    )
                with zf.open(inner_name) as fh:
                    for raw_line in fh:
                        parsed = _parse_fixed_width_line(
                            raw_line.decode("latin-1", errors="replace").rstrip("\n")
                        )
                        if parsed is None:
                            continue
                        parsed["effective_date"] = effective_date
                        yield parsed
        else:
            with file_path.open("r", encoding="latin-1", errors="replace") as fh:
                for raw_line in fh:
                    parsed = _parse_fixed_width_line(raw_line.rstrip("\n"))
                    if parsed is None:
                        continue
                    parsed["effective_date"] = effective_date
                    yield parsed

    def _resolve_effective_date(self, file_path: Path) -> date:
        if self._override_effective_date is not None:
            return self._override_effective_date
        try:
            return _effective_date_from_filename(file_path.name)
        except ValueError:
            # Fall back to the parent dir name (e.g. when --source-csv points
            # to the inner .txt whose name is icd10cm_order_YYYY.txt)
            inner = re.search(r"icd10cm_order_(\d{4})\.txt\Z", file_path.name)
            if inner:
                fy = int(inner.group(1))
                return date(fy - 1, 10, 1)
            raise

    # ------------------------------------------------------------------
    # load
    # ------------------------------------------------------------------

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batch-upsert into shared.icd10_cm_codes."""
        table = _get_target_table()
        errors = ErrorAggregator()
        processed = 0
        inserted = 0
        batch: list[dict[str, Any]] = []

        def _flush() -> None:
            nonlocal inserted
            if not batch:
                return
            ins, _dd = flush_upsert_batch(
                self._db,
                source_name=self.source_name,
                table=table,
                unique_key=["code", "effective_date"],
                rows=batch,
                errors=errors,
            )
            inserted += ins
            batch.clear()

        for raw in records:
            processed += 1
            raw["raw_payload"] = {
                k: _json_safe(v) for k, v in raw.items() if k != "raw_payload"
            }
            batch.append(raw)
            if len(batch) >= _BATCH_SIZE:
                _flush()

        _flush()
        errors.log_summary(source_name=self.source_name)

        logger.info(
            "ICD-10-CM load complete",
            extra={
                "ingest_source": self.source_name,
                "ingest_records_processed": processed,
                "ingest_records_inserted": inserted,
                "ingest_records_errored": errors.total_errors,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_in_source=processed,
            records_processed=processed,
            records_inserted=inserted,
            records_errored=errors.total_errors,
        )


# ---------------------------------------------------------------------------
# Table + JSON helpers
# ---------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    """Make one value JSON-safe for the raw_payload column."""
    if isinstance(value, date):
        return value.isoformat()
    return value


def _get_target_table() -> Table:
    """Return the SQLAlchemy Table for ``shared.icd10_cm_codes``."""
    from shared.db.models.icd10_cm_codes import Icd10CmCode
    return Icd10CmCode.__table__


__all__ = [
    "Icd10CmIngester",
    "_choose_latest_filename",
    "_effective_date_from_filename",
    "_parse_fixed_width_line",
]
