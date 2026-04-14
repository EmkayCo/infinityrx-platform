"""CMS ASP (Average Sales Price) drug pricing ingestion source.

Downloads the latest quarterly ASP pricing XLSX file from the CMS website:
  https://www.cms.gov/medicare/payment/all-fee-schedules/part-b-drugs/asp-drug-pricing-files

Strategy:
  1. Fetch the CMS page HTML.
  2. Scan anchor hrefs for XLSX files matching known naming patterns:
       - "YYYY Q N ASP Pricing File" (old style)
       - "ASP_Pricing_File_YYYY_QN.xlsx" (new style)
       - Any .xlsx href on the page with "asp" in the name (fallback)
  3. Pick the most recently dated match.
  4. Download the XLSX with download_to_file().
  5. Parse with openpyxl — read header row, map fields, yield records.

Fields from ASP:
  HCPCS Code, Short Description, HCPCS Code Dosage, Payment Limit,
  Vaccine AWP (Y/N — column may be absent; tolerate), Effective Quarter
  (YYYYQN — inferred from filename if not in file)

Data rules (non-negotiable):
  - Payment Limit: Decimal(18, 6) ROUND_HALF_UP — never float.
  - Convert XLSX numeric cells via Decimal(str(value)).
  - No float anywhere in this module.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors for all security/validation regex.
LESSON-005: All log extra keys prefixed with ingest_.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import zipfile

import httpx
import openpyxl

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.downloader import download_to_file
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "cms_asp"
_CMS_PAGE_URL = "https://www.cms.gov/medicare/payment/part-b-drugs/asp-pricing-files"
_DEST_DIR = Path("data/reference/cms-asp")
_TIMEOUT_SECONDS = 120.0

# LESSON-004: \A...\Z anchors only — never ^...$
# Quarter pattern in filename: YYYY_Q1, YYYY_Q2, ... or YYYYQ1, YYYYQ2, ...
_FILENAME_QUARTER_RE = re.compile(
    r"\A.*?(\d{4})[_\s-]?[Qq]([1-4]).*\Z", re.IGNORECASE
)
_QUARTER_FIELD_RE = re.compile(r"\A\d{4}Q[1-4]\Z")

# ---------------------------------------------------------------------------
# Field registry — run at module import time
# ---------------------------------------------------------------------------

for _col, _desc, _pos, _dtype in [
    ("hcpcs_code",        "HCPCS code",                           "HCPCS Code",                 "str"),
    ("short_description", "Short Description",                     "Short Description",           "str"),
    ("dosage",            "HCPCS Code Dosage, e.g. '10 mg'",       "HCPCS Code Dosage",           "str"),
    ("payment_limit",     "Payment Limit (ASP + 6%) — Decimal(18,6)", "Payment Limit",            "Decimal"),
    ("vaccine_awp",       "Y/N — Vaccine AWP indicator",           "Vaccine AWP",                 "str"),
    ("effective_quarter", "Effective quarter YYYYQN",              "Effective Quarter (inferred)", "str"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_asp_pricing",
        column=_col,
        description=_desc,
        source_file="CMS ASP XLSX",
        source_position=_pos,
        data_type=_dtype,
    )

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _parse_decimal(value: Any) -> Decimal | None:
    """Convert a cell value to Decimal(18,6) ROUND_HALF_UP.

    Always converts via str() to avoid IEEE-754 float contamination
    (financial-precision.md).  Returns None for empty/None/non-numeric.
    """
    if value is None:
        return None
    s = str(value).strip().lstrip("$").strip()
    if not s:
        return None
    try:
        return Decimal(s).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


_MONTH_TO_QUARTER: dict[str, str] = {
    "january": "Q1", "february": "Q1", "march": "Q1",
    "april": "Q2", "may": "Q2", "june": "Q2",
    "july": "Q3", "august": "Q3", "september": "Q3",
    "october": "Q4", "november": "Q4", "december": "Q4",
}

_MONTH_YEAR_RE = re.compile(
    r"\A.*?(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"[_\-\s]*(\d{4}).*\Z",
    re.IGNORECASE,
)


def _infer_quarter_from_filename(filename: str) -> str | None:
    """Extract quarter string (e.g. '2026Q2') from a filename.

    Accepts patterns like:
      - ASP_Pricing_File_2026_Q2.xlsx           → "2026Q2"
      - 2026_Q2_ASP_Drug_Pricing.xlsx           → "2026Q2"
      - april-2026-medicare-part-b-pricing.zip  → "2026Q2"
      - october-2025-asp-pricing.zip            → "2025Q4"

    Returns None if no recognizable quarter is found.
    """
    # Try explicit quarter pattern first (e.g. 2026_Q2 or 2026Q2)
    # LESSON-004: using re.fullmatch-equivalent via \A...\Z
    m = _FILENAME_QUARTER_RE.match(filename)
    if m:
        year = m.group(1)
        quarter_num = m.group(2)
        return f"{year}Q{quarter_num}"

    # Try month-name pattern (e.g. april-2026-...)
    m2 = _MONTH_YEAR_RE.match(filename)
    if m2:
        month_name = m2.group(1).lower()
        year = m2.group(2)
        quarter = _MONTH_TO_QUARTER.get(month_name)
        if quarter:
            return f"{year}{quarter}"

    return None


def _find_latest_xlsx_url(page_html: str, base_url: str) -> str | None:
    """Scan page HTML for ASP pricing download links, return the best candidate.

    CMS publishes ASP files as either XLSX or ZIP (containing XLSX inside).
    Preference order:
      1. Anchor hrefs containing both "asp" and ".xlsx" (case-insensitive).
      2. Anchor hrefs containing "asp" and "pricing" and ".zip" (CMS ZIP format).
      3. Any .xlsx href on the page (fallback).

    Returns the absolute URL of the latest match, or None.
    """
    # Extract all href values from <a> tags
    href_re = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    hrefs = href_re.findall(page_html)

    asp_xlsx_links: list[str] = []
    asp_zip_links: list[str] = []

    for href in hrefs:
        lower = href.lower()
        if lower.endswith(".xlsx") and "asp" in lower:
            absolute = urljoin(base_url, href)
            asp_xlsx_links.append(absolute)
        elif lower.endswith(".zip") and (
            ("asp" in lower and "pricing" in lower)
            or ("payment-limit" in lower)
            or ("asp-pricing" in lower)
        ):
            absolute = urljoin(base_url, href)
            asp_zip_links.append(absolute)

    # Prefer XLSX over ZIP; fallback to ZIP
    candidates = asp_xlsx_links or asp_zip_links

    if not candidates:
        # Fallback: any xlsx on the page
        for href in hrefs:
            if href.lower().endswith(".xlsx"):
                candidates.append(urljoin(base_url, href))

    if not candidates:
        return None

    # Pick the latest entry — sort by inferred quarter (YYYYQN), then by filename.
    def _sort_key(url: str) -> str:
        fname = url.split("/")[-1].split("?")[0]
        q = _infer_quarter_from_filename(fname)
        # Replace Q with 0 for lexicographic sort: "2026Q2" → "2026Q2" sorts correctly
        return q or "0000Q0"

    candidates.sort(key=_sort_key)
    return candidates[-1]


def _iter_excel_rows(file_path: Path) -> Iterator[tuple[Any, ...]]:
    """Stream all rows from an Excel file (XLSX or XLS format).

    Yields tuples of cell values.  XLS support requires the xlrd package.
    XLSX support uses openpyxl.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".xls":
        try:
            import xlrd  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "xlrd is required to parse .xls files. "
                "Install it with: pip install xlrd"
            ) from exc
        wb = xlrd.open_workbook(str(file_path))
        ws = wb.sheet_by_index(0)
        for i in range(ws.nrows):
            yield tuple(ws.row_values(i))
    else:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            yield row
        wb.close()


def _parse_xlsx(
    file_path: Path,
    *,
    effective_quarter_override: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Parse an ASP pricing Excel file (XLSX or XLS), yielding one dict per data row.

    Column header matching is case/whitespace-insensitive.  The Vaccine AWP
    column is optional — records without it will have ``vaccine_awp=None``.

    CMS files may have multiple title/meta rows before the actual column header.
    This function scans all rows to find the one containing "HCPCS Code" as the
    header, then treats subsequent rows as data.

    effective_quarter is read from the file if a column named "Effective Quarter"
    (or similar) exists; otherwise it is inferred from the filename via
    ``_infer_quarter_from_filename``.
    """
    # Normalize header names: strip, lower, collapse internal whitespace
    def _normalize(h: Any) -> str:
        return re.sub(r"\s+", " ", str(h or "").strip().lower())

    # Column index lookup (case/whitespace-insensitive)
    def _find_col(headers: list[str], col_candidates: list[str]) -> int | None:
        for cand in col_candidates:
            cand_norm = _normalize(cand)
            if cand_norm in headers:
                return headers.index(cand_norm)
        return None

    # Collect all rows; find the header row by scanning for "hcpcs code"
    all_rows = list(_iter_excel_rows(file_path))
    header_idx: int | None = None
    for i, row in enumerate(all_rows):
        row_lower = [_normalize(c) for c in row]
        if "hcpcs code" in row_lower or "hcpcs" in row_lower:
            header_idx = i
            break

    if header_idx is None:
        logger.warning(
            "ASP Excel file: could not find HCPCS Code header row",
            extra={"ingest_source": _SOURCE_NAME, "ingest_file": file_path.name},
        )
        return

    headers = [_normalize(h) for h in all_rows[header_idx]]

    col_hcpcs = _find_col(headers, ["hcpcs code", "hcpcs"])
    col_desc = _find_col(headers, ["short description", "description"])
    col_dosage = _find_col(headers, ["hcpcs code dosage", "dosage"])
    col_payment = _find_col(headers, ["payment limit", "payment limit (asp + 6%)", "asp + 6%"])
    col_vaccine = _find_col(headers, ["vaccine awp%", "vaccine awp", "vaccine"])
    col_quarter = _find_col(headers, ["effective quarter", "quarter"])

    if col_hcpcs is None or col_payment is None:
        logger.warning(
            "ASP Excel missing required columns",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_headers": headers[:20],
            },
        )
        return

    # Infer quarter from filename if not in file
    filename_quarter = _infer_quarter_from_filename(file_path.name)

    for data_row in all_rows[header_idx + 1:]:
        if not any(cell is not None and str(cell).strip() for cell in data_row):
            continue  # skip empty rows

        def _cell(idx: int | None) -> Any:
            if idx is None or idx >= len(data_row):
                return None
            return data_row[idx]

        hcpcs_raw = str(_cell(col_hcpcs) or "").strip().upper()
        # Strip .0 suffix from float HCPCS codes (xlrd returns numeric cells as floats)
        if hcpcs_raw.endswith(".0"):
            hcpcs_raw = hcpcs_raw[:-2]
        if not hcpcs_raw:
            continue

        payment_raw = _cell(col_payment)
        payment_limit = _parse_decimal(payment_raw)
        if payment_limit is None:
            continue

        # Effective quarter: from column > override > filename
        quarter: str | None = None
        if col_quarter is not None:
            q_raw = str(_cell(col_quarter) or "").strip()
            if _QUARTER_FIELD_RE.match(q_raw):
                quarter = q_raw
        if quarter is None:
            quarter = effective_quarter_override or filename_quarter

        if quarter is None:
            logger.warning(
                "ASP: cannot determine effective_quarter for row",
                extra={"ingest_source": _SOURCE_NAME, "ingest_hcpcs": hcpcs_raw},
            )
            continue

        vaccine_raw = str(_cell(col_vaccine) or "").strip() or None

        yield {
            "hcpcs_code": hcpcs_raw,
            "short_description": str(_cell(col_desc) or "").strip() or None,
            "dosage": str(_cell(col_dosage) or "").strip() or None,
            "payment_limit": payment_limit,
            "vaccine_awp": vaccine_raw,
            "effective_quarter": quarter,
        }


# ---------------------------------------------------------------------------
# Ingester class
# ---------------------------------------------------------------------------


class CMSASPIngester(DataSourceIngester):
    """Ingestion pipeline for the CMS ASP drug pricing quarterly XLSX files.

    Scrapes the CMS page, finds the latest quarter's XLSX URL, downloads it,
    then parses and upserts into drug_database.drug_asp_pricing (current) and
    drug_database.drug_asp_pricing_history (append-only).

    This is a global reference-data ingester — NOT tenant-scoped (LESSON-011).
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Scrape the CMS page for the latest ASP pricing file, download and return path.

        CMS publishes ASP files as XLSX or as ZIP archives containing XLSX files.
        This method handles both: downloads the file (XLSX or ZIP), and if a ZIP is
        downloaded, extracts the first XLSX inside it and returns that path.
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_TIMEOUT_SECONDS, connect=30.0),
            follow_redirects=True,
        ) as client:
            logger.info(
                "ASP: fetching CMS page for pricing file links",
                extra={"ingest_source": _SOURCE_NAME, "ingest_url": _CMS_PAGE_URL},
            )
            response = await client.get(_CMS_PAGE_URL)
            response.raise_for_status()
            page_html = response.text

        file_url = _find_latest_xlsx_url(page_html, _CMS_PAGE_URL)
        if not file_url:
            raise RuntimeError(
                f"Could not find an ASP pricing file download link on {_CMS_PAGE_URL}"
            )

        logger.info(
            "ASP: downloading pricing file",
            extra={"ingest_source": _SOURCE_NAME, "ingest_url": file_url},
        )
        downloaded_path = await download_to_file(file_url, dest_dir=_DEST_DIR)

        # If a ZIP was downloaded, extract the first Excel file inside it
        if downloaded_path.suffix.lower() == ".zip":
            return self._extract_xlsx_from_zip(downloaded_path)

        return downloaded_path

    def _extract_xlsx_from_zip(self, zip_path: Path) -> Path:
        """Extract the first Excel file (XLSX or XLS) from a ZIP archive.

        CMS historically published XLS files inside ZIP archives; newer files
        use XLSX.  This method handles both formats.  Returns the extracted path.
        """
        extract_dir = zip_path.parent / zip_path.stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            all_names = zf.namelist()
            xlsx_names = [n for n in all_names if n.lower().endswith(".xlsx")]
            xls_names = [n for n in all_names if n.lower().endswith(".xls") and not n.lower().endswith(".xlsx")]
            # Prefer XLSX, fall back to XLS (older CMS format)
            candidates = xlsx_names or xls_names
            if not candidates:
                raise RuntimeError(
                    f"No Excel file found inside ZIP: {zip_path}"
                )
            # Prefer names containing "payment limit"; fall back to first
            preferred = [n for n in candidates if "payment limit" in n.lower() or "asp" in n.lower()]
            target_name = (preferred or candidates)[0]
            zf.extract(target_name, path=extract_dir)

        extracted = extract_dir / target_name
        logger.info(
            "ASP: extracted XLSX from ZIP",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_zip": str(zip_path),
                "ingest_xlsx": str(extracted),
            },
        )
        return extracted

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse the ASP XLSX and yield normalized dicts.

        Each yielded dict contains the normalized fields ready for upsert.
        Rows missing HCPCS code or payment limit are skipped.
        """
        yield from _parse_xlsx(file_path)

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Bulk-upsert parsed ASP records into drug_database.

        Delegates to ASPIngestionService, imported lazily so that
        drug-database module root must be on sys.path (added by conftest or
        load script) for ``src.services`` to resolve.
        """
        from src.services.pricing_ingestion import ASPIngestionService  # requires drug-database on path

        service = ASPIngestionService(db_session=self._db)
        return await service.load_records(records, source_name=self.source_name)


__all__ = ["CMSASPIngester"]
