"""FDA NDC Directory ingestion source.

Downloads https://www.accessdata.fda.gov/cder/ndctext.zip, streams-parses
product.txt and package.txt (tab-delimited, latin-1 encoded), and yields
normalized dicts for upsert into drug_database.drugs, drug_packages,
drug_active_ingredients, and drug_pharm_classes.

NDC-11 normalization rules (LESSON-004 -- \\A...\\Z anchors):
  4-4-2 -> pad labeler segment: 0{labeler}-{product}-{package}
  5-3-2 -> pad product segment:  {labeler}-0{product}-{package}
  5-4-1 -> pad package segment:  {labeler}-{product}-0{package}

Field registry registrations run at module import time so the
/api/v1/data-ingestion/field-catalog endpoint always reflects this source.

LESSON-011: Global reference data — no TenantScopedMixin; shared cross-tenant.
LESSON-004: All regex uses \\A...\\Z anchors (not ^...$).
LESSON-005: All log extra keys prefixed with ingest_.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.downloader import download_to_file, unzip_if_zipped
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "fda_ndc"
_DOWNLOAD_URL = "https://www.accessdata.fda.gov/cder/ndctext.zip"
_DEST_DIR = Path("data/reference/fda-ndc")
_FILENAME = "ndctext.zip"

_BATCH_SIZE = 1_000

# LESSON-004: Use \A...\Z anchors for all security/validation regex.
_NDC_DIGITS_RE = re.compile(r"\A\d{8,11}\Z")

# ---------------------------------------------------------------------------
# Field registry — run at module import time
# ---------------------------------------------------------------------------

for _col, _desc, _pos, _dtype in [
    ("product_id",   "FDA PRODUCTID (labeler-product)",       "PRODUCTID",    "str"),
    ("product_ndc",  "FDA PRODUCTNDC (5-4 format)",           "PRODUCTNDC",   "str"),
    ("ndc_11",       "11-digit NDC in 5-4-2 format",          "PRODUCTNDC",   "str"),
    ("product_type_name", "OTC/PRESCRIPTION/etc.",            "PRODUCTTYPENAME", "str"),
    ("proprietary_name",  "Brand name",                       "PROPRIETARYNAME", "str"),
    ("proprietary_name_suffix", "Brand name suffix",          "PROPRIETARYNAMESUFFIX", "str"),
    ("non_proprietary_name",    "Generic/INN name",           "NONPROPRIETARYNAME", "str"),
    ("dosage_form_name",        "Dosage form",                "DOSAGEFORMNAME", "str"),
    ("route_name",              "Route of administration",    "ROUTENAME", "str"),
    ("start_marketing_date",    "Marketing start (YYYYMMDD)", "STARTMARKETINGDATE", "date"),
    ("end_marketing_date",      "Marketing end (YYYYMMDD)",   "ENDMARKETINGDATE", "date"),
    ("marketing_category_name", "Marketing category",        "MARKETINGCATEGORYNAME", "str"),
    ("application_number",      "Orange Book NDA/ANDA number","APPLICATIONNUMBER", "str"),
    ("labeler_name",            "Labeler/manufacturer name",  "LABELERNAME", "str"),
    ("substance_name",          "Active substance(s), semicolon-separated", "SUBSTANCENAME", "str"),
    ("active_numerator_strength","Strength(s), semicolon-separated",        "ACTIVE_NUMERATOR_STRENGTH", "str"),
    ("active_ingred_unit",      "Unit(s), semicolon-separated",             "ACTIVE_INGRED_UNIT", "str"),
    ("pharm_classes",           "Pharmacological classes, comma-separated", "PHARM_CLASSES", "str"),
    ("dea_schedule",            "DEA schedule (CI-CV) or null",             "DEASCHEDULE", "str"),
    ("ndc_exclude_flag",        "Y=excluded from NDC directory",            "NDCEXCLUDEFLAG", "str"),
    ("listing_record_certified_through", "Annual certification date",       "LISTING_RECORD_CERTIFIED_THROUGH", "date"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drugs",
        column=_col,
        description=_desc,
        source_file="product.txt",
        source_position=_pos,
        data_type=_dtype,
    )

for _col, _desc, _pos, _dtype in [
    ("product_ndc",         "Denormalized PRODUCTNDC",             "PRODUCTNDC", "str"),
    ("ndc_package_code",    "Full NDC including package segment",  "NDCPACKAGECODE", "str"),
    ("ndc_package_code_11", "Normalized 11-digit package NDC",     "NDCPACKAGECODE", "str"),
    ("package_description", "Package size/form description",       "PACKAGEDESCRIPTION", "str"),
    ("start_marketing_date","Marketing start",                     "STARTMARKETINGDATE", "date"),
    ("end_marketing_date",  "Marketing end",                       "ENDMARKETINGDATE", "date"),
    ("ndc_exclude_flag",    "Y=excluded",                          "NDCEXCLUDEFLAG", "str"),
    ("sample_package",      "Y=sample package",                    "SAMPLEPACKAGE", "str"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_packages",
        column=_col,
        description=_desc,
        source_file="package.txt",
        source_position=_pos,
        data_type=_dtype,
    )


# ---------------------------------------------------------------------------
# NDC-11 normalization
# ---------------------------------------------------------------------------

def normalize_ndc_11(raw: str) -> str:
    """Normalize an NDC string to 11-digit 5-4-2 format.

    Accepts NDCs in any of the three common raw formats:
      - 4-4-2  (10 digits, dashes optional): pad labeler to 5
      - 5-3-2  (10 digits, dashes optional): pad product to 4
      - 5-4-1  (10 digits, dashes optional): pad package to 2
      - 11-digit strings (already normalized, 5-4-2): returned as-is

    Parameters
    ----------
    raw:
        Raw NDC string from the FDA file.  May include dashes.

    Returns
    -------
    str
        Zero-padded 11-digit string (no dashes), e.g. "00069420016".

    Raises
    ------
    ValueError
        If the raw NDC is invalid (not 8-11 digits after stripping dashes).
    """
    stripped = raw.replace("-", "").strip()
    # LESSON-004: \A...\Z anchors only — never ^...$
    if not _NDC_DIGITS_RE.match(stripped):
        raise ValueError(f"Invalid NDC (must be 8-11 digits after stripping dashes): {raw!r}")

    length = len(stripped)

    if length == 11:
        # Already 5-4-2; validate segment lengths by just returning it
        return stripped

    if length == 10:
        # Determine format by inspecting dash positions in raw string
        parts = raw.strip().split("-")
        if len(parts) == 3:
            seg_lengths = tuple(len(p) for p in parts)
            if seg_lengths == (4, 4, 2):
                # 4-4-2: pad labeler
                return f"0{parts[0]}{parts[1]}{parts[2]}"
            if seg_lengths == (5, 3, 2):
                # 5-3-2: pad product
                return f"{parts[0]}0{parts[1]}{parts[2]}"
            if seg_lengths == (5, 4, 1):
                # 5-4-1: pad package
                return f"{parts[0]}{parts[1]}0{parts[2]}"
        # No dashes — use heuristic: FDA NDC product file uses 5-4 for PRODUCTNDC
        # and package code adds 2 more digits; strip is 10 digits with no context.
        # Treat as 5-4-1: pad package (most common in FDA files without dashes).
        return stripped[:5] + stripped[5:9] + "0" + stripped[9]

    if length == 9:
        # 4-4-1: pad labeler and package
        return f"0{stripped[:4]}{stripped[4:8]}0{stripped[8]}"

    if length == 8:
        # 4-3-1: pad labeler, product, and package
        return f"0{stripped[:4]}0{stripped[4:7]}0{stripped[7]}"

    raise ValueError(f"Cannot normalize NDC with {length} digits: {raw!r}")


def _parse_date(value: str | None) -> date | None:
    """Parse YYYYMMDD string to datetime.date; return None for empty/invalid."""
    if not value or not value.strip():
        return None
    val = value.strip()
    try:
        return date(int(val[:4]), int(val[4:6]), int(val[6:8]))
    except (ValueError, IndexError):
        return None


def _parse_strength(value: str | None) -> Decimal | None:
    """Parse a strength string to Decimal(18,6) ROUND_HALF_UP; None for non-numeric."""
    if not value or not value.strip():
        return None
    try:
        return Decimal(str(value.strip())).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError):
        return None


def _extract_class_type(pharm_class_raw: str) -> tuple[str, str | None]:
    """Extract class_type from a trailing [TYPE] marker.

    Returns (class_text, class_type_or_None).

    Examples:
        "Beta Blocker [EPC]" → ("Beta Blocker", "EPC")
        "Angiotensin 2 Receptor Blocker" → ("Angiotensin 2 Receptor Blocker", None)
    """
    pharm_class_raw = pharm_class_raw.strip()
    # LESSON-004: use \A...\Z pattern via re.fullmatch
    match = re.fullmatch(r"(.+?)\s*\[([A-Za-z]{2,4})\]", pharm_class_raw)
    if match:
        return match.group(1).strip(), match.group(2)
    return pharm_class_raw, None


def _stream_tsv(path: Path, encoding: str = "latin-1") -> Iterator[dict[str, str]]:
    """Stream a tab-separated file, yielding one dict per data row.

    Handles:
    - BOM stripping on first line
    - Blank/whitespace-only rows
    - Encoding errors replaced (errors='replace')
    """
    with path.open(encoding=encoding, errors="replace", newline="") as fh:
        header: list[str] | None = None
        for line_no, line in enumerate(fh):
            # Strip BOM from the very first line
            if line_no == 0:
                line = line.lstrip("\ufeff")
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            fields = line.split("\t")
            if header is None:
                header = fields
                continue
            # Zip up to header length; extra columns are silently dropped.
            row = dict(zip(header, fields))
            yield row


def _parse_products(product_txt: Path) -> Iterator[dict[str, Any]]:
    """Stream-parse product.txt and yield normalized drug dicts."""
    for row in _stream_tsv(product_txt):
        product_id = (row.get("PRODUCTID") or "").strip()
        if not product_id:
            continue

        product_ndc_raw = (row.get("PRODUCTNDC") or "").strip()
        # NDC-11 for product only (5-4); package code comes from package.txt.
        # Treat PRODUCTNDC as the product segment — skip if malformed.
        # product.txt uses 5-4 format (no package); we store as-is and also
        # compute a best-effort 11-digit using package "00" placeholder only
        # for the drugs table ndc_11 — real 11-digit per package is in package.txt.
        try:
            # PRODUCTNDC is 5-4: 9 digits. Treat as 5-4-? — we set package to "00"
            # for the drugs table index (actual package ndc_11s are in drug_packages).
            digits = product_ndc_raw.replace("-", "")
            if re.fullmatch(r"\A\d{9}\Z", digits):
                # 5-4 format; append "00" to get 11 digits (5-4-2)
                ndc_11 = digits + "00"
            else:
                ndc_11 = normalize_ndc_11(product_ndc_raw)
        except ValueError:
            logger.warning(
                "Skipping product with invalid PRODUCTNDC",
                extra={"ingest_source": _SOURCE_NAME, "ingest_product_id": product_id,
                       "ingest_raw_ndc": product_ndc_raw[:30]},
            )
            continue

        yield {
            "table": "drugs",
            "row": {
                "product_id": product_id,
                "product_ndc": product_ndc_raw,
                "ndc_11": ndc_11,
                "product_type_name": (row.get("PRODUCTTYPENAME") or "").strip() or None,
                "proprietary_name": (row.get("PROPRIETARYNAME") or "").strip() or None,
                "proprietary_name_suffix": (row.get("PROPRIETARYNAMESUFFIX") or "").strip() or None,
                "non_proprietary_name": (row.get("NONPROPRIETARYNAME") or "").strip() or None,
                "dosage_form_name": (row.get("DOSAGEFORMNAME") or "").strip() or None,
                "route_name": (row.get("ROUTENAME") or "").strip() or None,
                "start_marketing_date": _parse_date(row.get("STARTMARKETINGDATE")),
                "end_marketing_date": _parse_date(row.get("ENDMARKETINGDATE")),
                "marketing_category_name": (row.get("MARKETINGCATEGORYNAME") or "").strip() or None,
                "application_number": (row.get("APPLICATIONNUMBER") or "").strip() or None,
                "labeler_name": (row.get("LABELERNAME") or "").strip() or None,
                "substance_name": (row.get("SUBSTANCENAME") or "").strip() or None,
                "active_numerator_strength": (row.get("ACTIVE_NUMERATOR_STRENGTH") or "").strip() or None,
                "active_ingred_unit": (row.get("ACTIVE_INGRED_UNIT") or "").strip() or None,
                "pharm_classes": (row.get("PHARM_CLASSES") or "").strip() or None,
                "dea_schedule": (row.get("DEASCHEDULE") or "").strip() or None,
                "ndc_exclude_flag": (row.get("NDCEXCLUDEFLAG") or "").strip() or None,
                "listing_record_certified_through": _parse_date(
                    row.get("LISTING_RECORD_CERTIFIED_THROUGH")
                ),
            },
        }


def _parse_packages(package_txt: Path) -> Iterator[dict[str, Any]]:
    """Stream-parse package.txt and yield normalized package dicts."""
    for row in _stream_tsv(package_txt):
        product_id = (row.get("PRODUCTID") or "").strip()
        if not product_id:
            continue

        ndc_package_code_raw = (row.get("NDCPACKAGECODE") or "").strip()
        try:
            ndc_11 = normalize_ndc_11(ndc_package_code_raw)
        except ValueError:
            logger.warning(
                "Skipping package with invalid NDCPACKAGECODE",
                extra={"ingest_source": _SOURCE_NAME, "ingest_product_id": product_id,
                       "ingest_raw_ndc": ndc_package_code_raw[:30]},
            )
            continue

        yield {
            "table": "drug_packages",
            "row": {
                "product_id": product_id,
                "product_ndc": (row.get("PRODUCTNDC") or "").strip() or None,
                "ndc_package_code": ndc_package_code_raw,
                "ndc_package_code_11": ndc_11,
                "package_description": (row.get("PACKAGEDESCRIPTION") or "").strip() or None,
                "start_marketing_date": _parse_date(row.get("STARTMARKETINGDATE")),
                "end_marketing_date": _parse_date(row.get("ENDMARKETINGDATE")),
                "ndc_exclude_flag": (row.get("NDCEXCLUDEFLAG") or "").strip() or None,
                "sample_package": (row.get("SAMPLEPACKAGE") or "").strip() or None,
            },
        }


class FDANDCIngester(DataSourceIngester):
    """Ingestion pipeline for the FDA NDC Directory (ndctext.zip).

    Downloads the ZIP, streams product.txt and package.txt, and loads records
    into drug_database.drugs, drug_packages, drug_active_ingredients, and
    drug_pharm_classes.

    This is a global reference-data ingester — NOT tenant-scoped (LESSON-011).
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Download ndctext.zip from FDA and return its local path."""
        return await download_to_file(
            _DOWNLOAD_URL,
            dest_dir=_DEST_DIR,
            filename=_FILENAME,
        )

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Extract ZIP and stream product.txt then package.txt.

        Yields dicts with keys:
            ``{"table": "drugs"|"drug_packages", "row": {...}}``

        The load() method separates them by "table" key.
        """
        extracted = unzip_if_zipped(file_path, file_path.parent)

        if extracted.is_dir():
            product_txt = extracted / "product.txt"
            package_txt = extracted / "package.txt"
        else:
            # In case unzip_if_zipped returned the file unchanged
            product_txt = extracted.parent / "product.txt"
            package_txt = extracted.parent / "package.txt"

        if product_txt.exists():
            yield from _parse_products(product_txt)
        else:
            logger.warning(
                "product.txt not found in extracted ZIP",
                extra={"ingest_source": self.source_name, "ingest_path": str(extracted)},
            )

        if package_txt.exists():
            yield from _parse_packages(package_txt)
        else:
            logger.warning(
                "package.txt not found in extracted ZIP",
                extra={"ingest_source": self.source_name, "ingest_path": str(extracted)},
            )

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batch-upsert parsed records into the drug_database schema.

        Delegates all DB work to the module-level NDCIngestionService, which
        is imported lazily to avoid hard-coupling between shared and the module.
        The drug-database module root must be on sys.path (added by the service
        conftest or the load_fda_ndc.py script) so ``src.services`` resolves.
        """
        from src.services.ndc_ingestion import NDCIngestionService  # requires drug-database on path

        service = NDCIngestionService(db_session=self._db)
        return await service.load_records(records, source_name=self.source_name)


__all__ = [
    "FDANDCIngester",
    "normalize_ndc_11",
]
