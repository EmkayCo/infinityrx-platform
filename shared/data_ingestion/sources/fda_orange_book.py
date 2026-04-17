"""FDA Orange Book ingestion source.

Downloads https://www.fda.gov/media/76860/download, extracts the ZIP, and
streams-parses three tilde-delimited (~) files:
  products.txt    → drug_database.drug_orange_book
  patent.txt      → drug_database.drug_patents
  exclusivity.txt → drug_database.drug_exclusivity

Field registry registrations run at module import time so the
/api/v1/data-ingestion/field-catalog endpoint always reflects this source.

Data rules (non-negotiable):
  - Global reference data — no TenantScopedMixin (LESSON-011).
  - Dates: "Mmm DD, YYYY" (e.g., "Jan 1, 1982") → datetime.date via parse_mmm_dd_yyyy.
    Special case: "Approved Prior to Jan 1, 1982" → date(1982, 1, 1), flag=True.
  - Y/N → Boolean True/False; empty or other → NULL.
  - Strip all fields. Empty string → NULL.
  - dosage_form and route split from "DF;Route" field on first semicolon.
  - application_number computed as "{appl_type}{appl_no:0>6}" (e.g. "NDA019787").

LESSON-004: All regex uses \\A...\\Z anchors — never re.match with ^...$ anchors.
LESSON-005: All log extra keys prefixed with ingest_.
LESSON-011: No TenantScopedMixin — cross-tenant global reference data.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.date_parsers import parse_mmm_dd_yyyy
from shared.data_ingestion.downloader import download_to_file, unzip_if_zipped
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "fda_orange_book"
_DOWNLOAD_URL = "https://www.fda.gov/media/76860/download"
_DEST_DIR = Path("data/reference/fda-orange-book")
_FILENAME = "orange_book.zip"

_BATCH_SIZE = 1_000

# drug_orange_book.te_code is String(10); the FDA source emits comma-separated
# multi-value TE codes like "AB1,AB2,AB3,AB4" (up to 15 chars observed) that
# blow the column. We NULL them out rather than truncate to preserve a parseable
# value — a truncated code would be malformed.
_TE_CODE_MAX_LEN = 10

# Sentinel text for "Approved Prior to Jan 1, 1982"
_APPROVED_PRIOR_TEXT = "Approved Prior to Jan 1, 1982"
_APPROVED_PRIOR_DATE = date(1982, 1, 1)

# LESSON-004: Use \A...\Z anchors for all validation regex
_APPL_NO_RE = re.compile(r"\A\d{1,6}\Z")
_APPL_TYPE_RE = re.compile(r"\A[A-Z]{1,5}\Z")

# ---------------------------------------------------------------------------
# Field registry — run at module import time
# ---------------------------------------------------------------------------

for _col, _desc, _pos, _dtype in [
    ("ingredient",              "Active ingredient(s)",                      "Ingredient",           "str"),
    ("dosage_form",             "Dosage form (split from DF;Route)",         "DF;Route",             "str"),
    ("route",                   "Route of administration (split from DF;Route)", "DF;Route",         "str"),
    ("trade_name",              "Trade/brand name",                          "Trade_Name",           "str"),
    ("applicant",               "Short applicant code",                      "Applicant",            "str"),
    ("strength",                "Drug strength",                             "Strength",             "str"),
    ("appl_type",               "Application type (N=NDA, A=ANDA, BLA)",     "Appl_Type",           "str"),
    ("appl_no",                 "Application number digits",                  "Appl_No",             "str"),
    ("application_number",      "Computed NDA/ANDA number for cross-ref",    "Appl_Type+Appl_No",   "str"),
    ("product_no",              "Product number within application",          "Product_No",           "str"),
    ("te_code",                 "Therapeutic equivalence code",               "TE_Code",             "str"),
    ("approval_date",           "Date of approval (Mmm DD, YYYY)",           "Approval_Date",        "date"),
    ("approved_prior_to_1982",  "True when approved before Jan 1, 1982",     "Approval_Date",        "bool"),
    ("rld",                     "Reference Listed Drug flag",                 "RLD",                  "bool"),
    ("rs",                      "Reference Standard flag",                    "RS",                   "bool"),
    ("product_type",            "Product type: RX, OTC, DISCN",              "Type",                 "str"),
    ("applicant_full_name",     "Full applicant name",                        "Applicant_Full_Name", "str"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_orange_book",
        column=_col,
        description=_desc,
        source_file="products.txt",
        source_position=_pos,
        data_type=_dtype,
    )

for _col, _desc, _pos, _dtype in [
    ("appl_type",           "Application type",                     "Appl_Type",        "str"),
    ("appl_no",             "Application number digits",             "Appl_No",          "str"),
    ("product_no",          "Product number",                        "Product_No",        "str"),
    ("application_number",  "Computed cross-ref number",             "Appl_Type+Appl_No","str"),
    ("patent_no",           "Patent number (may contain letters)",   "Patent_No",         "str"),
    ("patent_expire_date",  "Patent expiration date (Mmm DD, YYYY)", "Patent_Expire_Date","date"),
    ("drug_substance_flag", "Covers drug substance (Y→True)",        "Drug_Substance_Flag","bool"),
    ("drug_product_flag",   "Covers drug product (Y→True)",          "Drug_Product_Flag", "bool"),
    ("patent_use_code",     "Use code for method-of-use patents",    "Patent_Use_Code",  "str"),
    ("delist_flag",         "Delisted flag (Y→True)",                "Delist_Flag",       "bool"),
    ("submission_date",     "Submission date (Mmm DD, YYYY)",        "Submission_Date",   "date"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_patents",
        column=_col,
        description=_desc,
        source_file="patent.txt",
        source_position=_pos,
        data_type=_dtype,
    )

for _col, _desc, _pos, _dtype in [
    ("appl_type",           "Application type",                     "Appl_Type",         "str"),
    ("appl_no",             "Application number digits",             "Appl_No",           "str"),
    ("product_no",          "Product number",                        "Product_No",         "str"),
    ("application_number",  "Computed cross-ref number",             "Appl_Type+Appl_No", "str"),
    ("exclusivity_code",    "Exclusivity code (NCE, ODE, PED, etc.)","Exclusivity_Code", "str"),
    ("exclusivity_date",    "Exclusivity expiration (Mmm DD, YYYY)", "Exclusivity_Date",  "date"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_exclusivity",
        column=_col,
        description=_desc,
        source_file="exclusivity.txt",
        source_position=_pos,
        data_type=_dtype,
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _strip_or_none(value: str) -> str | None:
    """Strip a field value; return None if the result is an empty string."""
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def _yn_to_bool(value: str) -> bool | None:
    """Convert Y/Yes/N/No to True/False; anything else (including empty) → None.

    The FDA Orange Book uses "Yes"/"No" for RLD and RS fields; some other
    FDA datasets use "Y"/"N". Both forms are accepted (case-insensitive).
    """
    stripped = value.strip().upper() if value else ""
    if stripped in ("Y", "YES"):
        return True
    if stripped in ("N", "NO"):
        return False
    return None


def _compute_application_number(appl_type: str, appl_no: str) -> str | None:
    """Build the cross-reference application number.

    Mirrors the format stored in drug_database.drugs.application_number
    (e.g., "NDA019787").

    Rules:
      - appl_type "N" → prefix "NDA"
      - appl_type "A" → prefix "ANDA"
      - appl_type "BLA" → prefix "BLA"
      - Other types: use appl_type as-is
      - appl_no is zero-padded to 6 digits

    Returns None if either input is blank.
    """
    at = (appl_type or "").strip()
    an = (appl_no or "").strip()
    if not at or not an:
        return None
    if at.upper() == "N":
        prefix = "NDA"
    elif at.upper() == "A":
        prefix = "ANDA"
    else:
        prefix = at.upper()
    # Zero-pad appl_no to at least 6 digits
    try:
        padded = str(int(an)).zfill(6)
    except ValueError:
        padded = an
    return f"{prefix}{padded}"


def _parse_approval_date(raw: str) -> tuple[date | None, bool]:
    """Parse the Approval_Date field.

    Returns (date_value, approved_prior_to_1982).

    Special case: if the raw value contains "Prior to Jan 1, 1982" (case-
    insensitive), return (date(1982, 1, 1), True).

    Otherwise parse via parse_mmm_dd_yyyy; return (parsed_date, False).

    Per LESSON-004, parse_mmm_dd_yyyy requires the caller to strip whitespace
    before passing the value, because the function uses strict \\A...\\Z anchors
    on the raw input (no pre-stripping) to guarantee trailing newlines are rejected.
    """
    stripped = raw.strip() if raw else ""
    if not stripped:
        return None, False
    if "prior to jan 1, 1982" in stripped.lower():
        return _APPROVED_PRIOR_DATE, True
    parsed = parse_mmm_dd_yyyy(stripped)
    return parsed, False


def _split_df_route(df_route: str) -> tuple[str | None, str | None]:
    """Split a "DF;Route" field into (dosage_form, route).

    Returns the two parts after stripping whitespace. If there is no semicolon,
    all text goes into dosage_form and route is None.
    """
    if not df_route or not df_route.strip():
        return None, None
    parts = df_route.strip().split(";", 1)
    dosage_form = parts[0].strip() or None
    route = parts[1].strip() or None if len(parts) > 1 else None
    return dosage_form, route


# ---------------------------------------------------------------------------
# Per-file parsers
# ---------------------------------------------------------------------------


def _parse_products(file_path: Path) -> Iterator[dict[str, Any]]:
    """Parse products.txt and yield {"table": "drug_orange_book", "row": dict} records.

    The file is tilde-delimited (~). First line is a header row.
    Encoding: latin-1 (FDA files use latin-1 to handle trademark/copyright chars).

    Yields one dict per line.
    """
    with file_path.open(encoding="latin-1") as fh:
        header_line = fh.readline()
        headers = [h.strip() for h in header_line.split("~")]
        logger.info(
            "Orange Book products.txt headers",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_header_count": len(headers),
                "ingest_headers": headers[:5],
            },
        )
        for line in fh:
            line = line.rstrip("\n\r")
            if not line:
                continue
            fields = line.split("~")
            # Defensive: pad to header length
            while len(fields) < len(headers):
                fields.append("")
            row_raw = dict(zip(headers, fields))

            appl_type = _strip_or_none(row_raw.get("Appl_Type", "")) or ""
            appl_no = _strip_or_none(row_raw.get("Appl_No", "")) or ""
            # The real FDA products.txt header for the dosage form/route column is
            # "DF;Route" (a literal semicolon in the column name). We look up that
            # key first; fall back to "DF" for compatibility with simplified test data.
            df_route_raw = row_raw.get("DF;Route", row_raw.get("DF", "")) or ""
            dosage_form, route = _split_df_route(df_route_raw)
            approval_date, prior_flag = _parse_approval_date(
                row_raw.get("Approval_Date", "") or ""
            )

            te_code = _strip_or_none(row_raw.get("TE_Code", ""))
            if te_code is not None and len(te_code) > _TE_CODE_MAX_LEN:
                te_code = None  # multi-value code exceeds String(10); see _TE_CODE_MAX_LEN

            row: dict[str, Any] = {
                "ingredient": _strip_or_none(row_raw.get("Ingredient", "")),
                "dosage_form": dosage_form,
                "route": route,
                "trade_name": _strip_or_none(row_raw.get("Trade_Name", "")),
                "applicant": _strip_or_none(row_raw.get("Applicant", "")),
                "strength": _strip_or_none(row_raw.get("Strength", "")),
                "appl_type": appl_type,
                "appl_no": appl_no,
                "application_number": _compute_application_number(appl_type, appl_no),
                "product_no": _strip_or_none(row_raw.get("Product_No", "")) or "",
                "te_code": te_code,
                "approval_date": approval_date,
                "approved_prior_to_1982": prior_flag,
                "rld": _yn_to_bool(row_raw.get("RLD", "")),
                "rs": _yn_to_bool(row_raw.get("RS", "")),
                "product_type": _strip_or_none(row_raw.get("Type", "")),
                "applicant_full_name": _strip_or_none(
                    row_raw.get("Applicant_Full_Name", "")
                ),
            }
            yield {"table": "drug_orange_book", "row": row}


def _parse_patents(file_path: Path) -> Iterator[dict[str, Any]]:
    """Parse patent.txt and yield {"table": "drug_patents", "row": dict} records.

    The file is tilde-delimited (~). First line is a header row.
    Encoding: latin-1.
    """
    with file_path.open(encoding="latin-1") as fh:
        header_line = fh.readline()
        headers = [h.strip() for h in header_line.split("~")]
        for line in fh:
            line = line.rstrip("\n\r")
            if not line:
                continue
            fields = line.split("~")
            while len(fields) < len(headers):
                fields.append("")
            row_raw = dict(zip(headers, fields))

            appl_type = _strip_or_none(row_raw.get("Appl_Type", "")) or ""
            appl_no = _strip_or_none(row_raw.get("Appl_No", "")) or ""

            # Per LESSON-004: strip before passing to parse_mmm_dd_yyyy so that
            # the strict \A...\Z fullmatch correctly rejects trailing whitespace.
            _expire_raw = (
                row_raw.get("Patent_Expire_Date_Text", "")
                or row_raw.get("Patent_Expire_Date", "")
            ).strip()
            _submit_raw = (row_raw.get("Submission_Date", "") or "").strip()

            row: dict[str, Any] = {
                "appl_type": appl_type,
                "appl_no": appl_no,
                "product_no": _strip_or_none(row_raw.get("Product_No", "")) or "",
                "application_number": _compute_application_number(appl_type, appl_no),
                "patent_no": _strip_or_none(row_raw.get("Patent_No", "")) or "",
                "patent_expire_date": parse_mmm_dd_yyyy(_expire_raw) if _expire_raw else None,
                # Real FDA patent.txt uses "Drug_Substance_Flag" / "Drug_Product_Flag";
                # fall back to "Drug_Substance" / "Drug_Product" for test data compatibility.
                "drug_substance_flag": _yn_to_bool(
                    row_raw.get("Drug_Substance_Flag", row_raw.get("Drug_Substance", ""))
                ),
                "drug_product_flag": _yn_to_bool(
                    row_raw.get("Drug_Product_Flag", row_raw.get("Drug_Product", ""))
                ),
                "patent_use_code": _strip_or_none(
                    row_raw.get("Patent_Use_Code", "")
                ),
                "delist_flag": _yn_to_bool(row_raw.get("Delist_Flag", "")),
                "submission_date": parse_mmm_dd_yyyy(_submit_raw) if _submit_raw else None,
            }
            yield {"table": "drug_patents", "row": row}


def _parse_exclusivity(file_path: Path) -> Iterator[dict[str, Any]]:
    """Parse exclusivity.txt and yield {"table": "drug_exclusivity", "row": dict} records.

    The file is tilde-delimited (~). First line is a header row.
    Encoding: latin-1.
    """
    with file_path.open(encoding="latin-1") as fh:
        header_line = fh.readline()
        headers = [h.strip() for h in header_line.split("~")]
        for line in fh:
            line = line.rstrip("\n\r")
            if not line:
                continue
            fields = line.split("~")
            while len(fields) < len(headers):
                fields.append("")
            row_raw = dict(zip(headers, fields))

            appl_type = _strip_or_none(row_raw.get("Appl_Type", "")) or ""
            appl_no = _strip_or_none(row_raw.get("Appl_No", "")) or ""

            # Per LESSON-004: strip before passing to parse_mmm_dd_yyyy.
            _exc_date_raw = (row_raw.get("Exclusivity_Date", "") or "").strip()

            row: dict[str, Any] = {
                "appl_type": appl_type,
                "appl_no": appl_no,
                "product_no": _strip_or_none(row_raw.get("Product_No", "")) or "",
                "application_number": _compute_application_number(appl_type, appl_no),
                "exclusivity_code": _strip_or_none(
                    row_raw.get("Exclusivity_Code", "")
                ) or "",
                "exclusivity_date": parse_mmm_dd_yyyy(_exc_date_raw) if _exc_date_raw else None,
            }
            yield {"table": "drug_exclusivity", "row": row}


# ---------------------------------------------------------------------------
# Ingester
# ---------------------------------------------------------------------------


class FDAOrangeBookIngester(DataSourceIngester):
    """Ingester for the FDA Orange Book ZIP.

    Downloads orange_book.zip, extracts it, and passes three files
    to parse(): products.txt, patent.txt, exclusivity.txt.

    Delegates DB writes to modules/drug-database/src/services/orange_book_ingestion.py
    (OrangeBookIngestionService).

    LESSON-011: Global reference data — no TenantScopedMixin.
    LESSON-004: \\A...\\Z anchors used for all regex.
    LESSON-005: All log extra keys prefixed with ingest_.
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Download the Orange Book ZIP to data/reference/fda-orange-book/."""
        return await download_to_file(
            _DOWNLOAD_URL,
            dest_dir=_DEST_DIR,
            filename=_FILENAME,
        )

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Extract ZIP and parse products.txt → patent.txt → exclusivity.txt.

        Yields {"table": str, "row": dict} records in that order.
        """
        extracted_dir = unzip_if_zipped(file_path, file_path.parent)

        # Resolve individual file paths (ZIP may or may not use a subdirectory)
        if extracted_dir.is_dir():
            base = extracted_dir
        else:
            base = extracted_dir.parent

        products_path = base / "products.txt"
        patent_path = base / "patent.txt"
        exclusivity_path = base / "exclusivity.txt"

        logger.info(
            "Parsing Orange Book ZIP",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_products_exists": products_path.exists(),
                "ingest_patent_exists": patent_path.exists(),
                "ingest_exclusivity_exists": exclusivity_path.exists(),
            },
        )

        if products_path.exists():
            yield from _parse_products(products_path)
        else:
            logger.warning(
                "products.txt not found in Orange Book ZIP",
                extra={"ingest_source": _SOURCE_NAME, "ingest_base_dir": str(base)},
            )

        if patent_path.exists():
            yield from _parse_patents(patent_path)
        else:
            logger.warning(
                "patent.txt not found in Orange Book ZIP",
                extra={"ingest_source": _SOURCE_NAME, "ingest_base_dir": str(base)},
            )

        if exclusivity_path.exists():
            yield from _parse_exclusivity(exclusivity_path)
        else:
            logger.warning(
                "exclusivity.txt not found in Orange Book ZIP",
                extra={"ingest_source": _SOURCE_NAME, "ingest_base_dir": str(base)},
            )

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Route parsed records to shared batching primitives.

        Products are upserted in BATCH_SIZE chunks by (appl_type, appl_no,
        product_no). Patents and exclusivity are each a single scoped-replace
        pass: we buffer the full file in memory (16K patents, 2K exclusivity
        — both tiny), delete every (appl_type, appl_no, product_no) scope
        that appears, then re-insert the deduped rows. A single-pass flush
        per child table avoids the cross-batch scope-deletion problem that
        would otherwise eat the first batch's rows when a scope spans two
        flushes.
        """
        import sys
        from pathlib import Path as _Path

        from shared.data_ingestion.batching import (
            ErrorAggregator,
            flush_scoped_replace_batch,
            flush_upsert_batch,
        )

        _repo_root = _Path(__file__).resolve().parents[3]
        _drug_db_root = _repo_root / "modules" / "drug-database"
        for _p in (str(_repo_root), str(_drug_db_root)):
            if _p not in sys.path:
                sys.path.insert(0, _p)

        from src.models.orange_book_tables import (  # type: ignore[import]
            DrugExclusivity,
            DrugOrangeBook,
            DrugPatent,
        )

        errors = ErrorAggregator()
        product_buffer: list[dict[str, Any]] = []
        patent_rows: list[dict[str, Any]] = []
        exclusivity_rows: list[dict[str, Any]] = []
        processed = 0
        inserted = 0
        skipped = 0

        def _flush_products() -> None:
            nonlocal inserted, skipped
            if not product_buffer:
                return
            ins, dd = flush_upsert_batch(
                self._db,
                source_name=self.source_name,
                table=DrugOrangeBook.__table__,
                unique_key=["appl_type", "appl_no", "product_no"],
                rows=product_buffer,
                errors=errors,
            )
            inserted += ins
            skipped += dd
            product_buffer.clear()

        for record in records:
            tbl = record.get("table")
            row = record.get("row")
            if not tbl or not row:
                errors.record("empty_record", "missing table or row")
                continue
            processed += 1

            if tbl == "drug_orange_book":
                product_buffer.append(row)
                if len(product_buffer) >= _BATCH_SIZE:
                    _flush_products()
            elif tbl == "drug_patents":
                patent_rows.append(row)
            elif tbl == "drug_exclusivity":
                exclusivity_rows.append(row)
            else:
                errors.record("unknown_table", f"no config for table {tbl}", raw_row=row)

        _flush_products()

        # Patents: one-shot scoped-replace. Delete every scope the incoming
        # file touches, then re-insert all deduped rows. Uniqueness tuple
        # matches the DB UNIQUE constraint so duplicate rows in the source
        # don't violate it.
        pat_ins, pat_dd = flush_scoped_replace_batch(
            self._db,
            source_name=self.source_name,
            table=DrugPatent.__table__,
            scope_key=["appl_type", "appl_no", "product_no"],
            unique_key=["appl_type", "appl_no", "product_no", "patent_no"],
            rows=patent_rows,
            errors=errors,
        )
        inserted += pat_ins
        skipped += pat_dd

        exc_ins, exc_dd = flush_scoped_replace_batch(
            self._db,
            source_name=self.source_name,
            table=DrugExclusivity.__table__,
            scope_key=["appl_type", "appl_no", "product_no"],
            unique_key=[
                "appl_type",
                "appl_no",
                "product_no",
                "exclusivity_code",
                "exclusivity_date",
            ],
            rows=exclusivity_rows,
            errors=errors,
        )
        inserted += exc_ins
        skipped += exc_dd

        errors.log_summary(source_name=self.source_name)

        logger.info(
            "Orange Book load complete",
            extra={
                "ingest_source": self.source_name,
                "ingest_records_processed": processed,
                "ingest_records_inserted": inserted,
                "ingest_records_skipped": skipped,
                "ingest_records_errored": errors.total_errors,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=processed,
            records_inserted=inserted,
            records_skipped=skipped,
            records_errored=errors.total_errors,
        )


__all__ = [
    "FDAOrangeBookIngester",
    "_compute_application_number",
    "_parse_approval_date",
    "_parse_exclusivity",
    "_parse_patents",
    "_parse_products",
    "_split_df_route",
    "_strip_or_none",
    "_yn_to_bool",
]
