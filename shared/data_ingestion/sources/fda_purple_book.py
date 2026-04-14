"""FDA Purple Book (Biologics License Applications) ingestion source.

Downloads the monthly Purple Book CSV from purplebooksearch.fda.gov/downloads.
Scans the downloads page for the latest CSV href, then downloads and parses it.

Field registry registrations run at module import time.

Data rules:
  - Global reference data — no TenantScopedMixin (LESSON-011).
  - No float columns.
  - LESSON-004: All regex uses \\A...\\Z anchors.
  - LESSON-005: All log extra keys prefixed with ingest_.
  - interchangeable field is CRITICAL for formulary substitution logic.
  - raw_payload captures all extra CSV columns.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "fda_purple_book"
_DEST_DIR = Path("data/reference/fda-purple-book")
_FILENAME = "purple_book.csv"
_BATCH_SIZE = 1_000

_DOWNLOADS_PAGE_URL = "https://purplebooksearch.fda.gov/downloads"

# LESSON-004: \A...\Z anchors for all validation regex.
# Match href containing "purplebook" and ".csv"
_CSV_HREF_RE = re.compile(
    r'\A[^"]*purplebook[^"]*\.csv[^"]*\Z',
    re.IGNORECASE,
)
# Match href attributes inside <a> tags
_HREF_EXTRACT_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

# Date formats used in Purple Book CSV
_DATE_YYYYMMDD_RE = re.compile(r"\A(\d{4})-(\d{2})-(\d{2})\Z")
_DATE_MDY_RE = re.compile(r"\A(\d{1,2})/(\d{1,2})/(\d{4})\Z")
_DATE_MON_YYYY_RE = re.compile(
    r"\A(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})\Z",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ---------------------------------------------------------------------------
# Field registry — run at module import time
# ---------------------------------------------------------------------------

for _col, _desc, _pos, _dtype in [
    ("bla_number",                    "BLA application number (PK)",             "BLA Number",                   "str"),
    ("proprietary_name",              "Brand/proprietary name",                  "Proprietary Name",             "str"),
    ("proper_name",                   "INN/proper (generic) name",               "Proper Name",                  "str"),
    ("bla_type",                      "BLA type: 351(a) original / 351(k) biosimilar", "BLA Type",              "str"),
    ("applicant",                     "Applicant/manufacturer",                  "Applicant",                    "str"),
    ("strength",                      "Strength",                                "Strength",                     "str"),
    ("dosage_form",                   "Dosage form",                             "Dosage Form",                  "str"),
    ("route",                         "Route of administration",                 "Route of Administration",      "str"),
    ("product_presentation",          "Product presentation/description",        "Product Presentation",         "str"),
    ("status",                        "Product status (Active/Discontinued)",    "Status",                       "str"),
    ("licensure_date",                "Date of BLA licensure",                   "Date of Licensure",            "date"),
    ("interchangeable",               "Interchangeable flag (CRITICAL for substitution)", "Interchangeable",    "bool"),
    ("reference_product_bla",         "BLA number of reference product (nullable)", "Reference Product BLA Number", "str"),
    ("reference_product_proper_name", "Proper name of reference product (nullable)", "Reference Product Proper Name", "str"),
    ("exclusivity_expiration_date",   "Exclusivity expiration date (nullable)",  "Exclusivity Expiration Date",  "date"),
    ("raw_payload",                   "All CSV columns as raw JSONB",            "full_row",                     "json"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_purple_book",
        column=_col,
        description=_desc,
        source_file="purplebook_csv",
        source_position=_pos,
        data_type=_dtype,
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _strip_or_none(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_date(value: str | None) -> date | None:
    """Parse YYYY-MM-DD, M/D/YYYY, or Mon YYYY date strings."""
    if not value:
        return None
    stripped = value.strip()

    m = _DATE_YYYYMMDD_RE.match(stripped)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m2 = _DATE_MDY_RE.match(stripped)
    if m2:
        try:
            return date(int(m2.group(3)), int(m2.group(1)), int(m2.group(2)))
        except ValueError:
            return None

    m3 = _DATE_MON_YYYY_RE.match(stripped)
    if m3:
        mon_num = _MONTH_MAP.get(m3.group(1)[:3].lower())
        if mon_num:
            try:
                return date(int(m3.group(2)), mon_num, 1)
            except ValueError:
                return None

    return None


def _parse_interchangeable(value: str | None) -> bool | None:
    """Map Y/N/Yes/No/TRUE/FALSE/1/0 to bool; anything else → None."""
    if not value:
        return None
    upper = value.strip().upper()
    if upper in ("Y", "YES", "TRUE", "1"):
        return True
    if upper in ("N", "NO", "FALSE", "0"):
        return False
    return None


def _find_csv_url(html: str) -> str | None:
    """Extract the latest Purple Book CSV download URL from the downloads page HTML.

    Uses LESSON-004-compliant regex: \\A...\\Z anchors via re.fullmatch applied
    to each extracted href value.
    """
    hrefs = _HREF_EXTRACT_RE.findall(html)
    for href in hrefs:
        if re.fullmatch(r"[^\"']*purplebook[^\"']*\.csv[^\"']*", href, re.IGNORECASE):
            return href
    # Fallback: look for any CSV link containing "purplebook"
    for href in hrefs:
        if "purplebook" in href.lower() and href.lower().endswith(".csv"):
            return href
    return None


def _parse_csv_row(row: dict[str, str], fieldnames: list[str]) -> dict[str, Any]:
    """Parse a single CSV row into a Purple Book dict."""
    raw_payload = {k: v for k, v in row.items()}

    # Flexible column name matching — FDA has varied column headers across releases
    def _get(*keys: str) -> str | None:
        for key in keys:
            for field in fieldnames:
                if field.strip().lower() == key.lower():
                    val = row.get(field, "")
                    return _strip_or_none(val)
        return None

    bla_number = _get("BLA Number", "BLA_Number", "bla_number", "bla")
    if not bla_number:
        return {}

    return {
        "bla_number": bla_number,
        "proprietary_name": _get("Proprietary Name", "Brand Name", "proprietary_name"),
        "proper_name": _get("Proper Name", "Generic Name", "INN", "proper_name"),
        "bla_type": _get("BLA Type", "Type", "bla_type"),
        "applicant": _get("Applicant", "Manufacturer", "Company"),
        "strength": _get("Strength"),
        "dosage_form": _get("Dosage Form", "Dosage_Form"),
        "route": _get("Route of Administration", "Route"),
        "product_presentation": _get("Product Presentation", "Presentation"),
        "status": _get("Status", "Product Status"),
        "licensure_date": _parse_date(_get("Date of Licensure", "Licensure Date", "Approval Date")),
        "interchangeable": _parse_interchangeable(_get("Interchangeable", "Interchangeable?")),
        "reference_product_bla": _get(
            "Reference Product BLA Number", "Reference BLA", "Reference Product BLA"
        ),
        "reference_product_proper_name": _get(
            "Reference Product Proper Name", "Reference Proper Name"
        ),
        "exclusivity_expiration_date": _parse_date(
            _get("Exclusivity Expiration Date", "Exclusivity Date", "Exclusivity Exp Date")
        ),
        "raw_payload": raw_payload,
    }


# ---------------------------------------------------------------------------
# Ingester
# ---------------------------------------------------------------------------


class FdaPurpleBookIngester(DataSourceIngester):
    """Ingester for FDA Purple Book (biologics/biosimilars) monthly CSV.

    Downloads the latest CSV from purplebooksearch.fda.gov, parses all fields,
    and upserts into drug_database.drug_purple_book.

    The interchangeable flag is CRITICAL for formulary substitution logic.

    LESSON-011: Global reference data — no TenantScopedMixin.
    LESSON-004: \\A...\\Z anchors for all regex.
    LESSON-005: All log extra keys prefixed with ingest_.
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Scan downloads page for latest CSV, then download it."""
        _DEST_DIR.mkdir(parents=True, exist_ok=True)
        dest = _DEST_DIR / _FILENAME

        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
        ) as client:
            # Step 1: fetch the downloads page to find the latest CSV href
            try:
                page_resp = await client.get(_DOWNLOADS_PAGE_URL)
                page_resp.raise_for_status()
                csv_url = _find_csv_url(page_resp.text)
            except httpx.TransportError as exc:
                logger.warning(
                    "Purple Book downloads page unreachable",
                    extra={"ingest_source": _SOURCE_NAME, "ingest_error": str(exc)},
                )
                csv_url = None

            if not csv_url:
                # Construct a best-guess URL for the current month
                from datetime import date as _date
                today = _date.today()
                month_abbr = today.strftime("%B").lower()
                csv_url = (
                    f"https://purplebooksearch.fda.gov/downloads/files/"
                    f"{today.year}/purplebook-search-{month_abbr}-data-download.csv"
                )
                logger.info(
                    "Purple Book CSV URL not found on downloads page — using constructed URL",
                    extra={"ingest_source": _SOURCE_NAME, "ingest_url": csv_url},
                )

            # Step 2: resolve relative URLs
            if csv_url.startswith("/"):
                csv_url = f"https://purplebooksearch.fda.gov{csv_url}"

            # Step 3: download CSV
            csv_resp = await client.get(csv_url)
            csv_resp.raise_for_status()
            dest.write_bytes(csv_resp.content)

        logger.info(
            "Purple Book CSV downloaded",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_bytes": dest.stat().st_size,
            },
        )
        return dest

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse Purple Book CSV and yield one dict per BLA record."""
        content = file_path.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(content))
        fieldnames = list(reader.fieldnames or [])
        logger.info(
            "Purple Book CSV headers",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_column_count": len(fieldnames),
                "ingest_columns_preview": fieldnames[:5],
            },
        )
        for row in reader:
            parsed = _parse_csv_row(row, fieldnames)
            if parsed.get("bla_number"):
                yield parsed

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Upsert Purple Book records into drug_database.drug_purple_book."""
        import sys
        from pathlib import Path as _Path

        _repo_root = _Path(__file__).resolve().parents[3]
        _drug_db_root = _repo_root / "modules" / "drug-database"
        for _p in (str(_repo_root), str(_drug_db_root)):
            if _p not in sys.path:
                sys.path.insert(0, _p)

        from src.services.fda_supplementary_ingestion import (  # type: ignore[import]
            PurpleBookIngestionService,
        )

        svc = PurpleBookIngestionService(db_session=self._db)
        return await svc.load_records(records, source_name=_SOURCE_NAME)


__all__ = [
    "FdaPurpleBookIngester",
    "_parse_csv_row",
    "_parse_date",
    "_parse_interchangeable",
    "_find_csv_url",
]
