"""CMS NADAC (National Average Drug Acquisition Cost) ingestion source.

Downloads the full NADAC dataset from the CMS Medicaid data API (Socrata),
paginating with limit/offset until the API returns an empty results array.
All pages are collected into a single local JSON file; the SHA-256 of that
file is used for checksum-based deduplication.

API endpoint:
  https://data.medicaid.gov/api/1/datastore/query/fbb83258-11c7-47f5-8b18-5f8e79f7e704/0
  Pagination: ?limit=10000&offset=0  — increment offset by 10K each page.
  Response shape: {"results": [...], "count": N, "schema": {...}}

All 12 source fields are ingested:
  NDC Description, NDC, NADAC_Per_Unit, Effective_Date, Pricing_Unit,
  Pharmacy_Type_Indicator, OTC, Explanation_Code, Classification_for_Rate_Setting,
  Corresponding_Generic_Drug_NADAC_Per_Unit, Corresponding_Generic_Drug_Effective_Date,
  As_of_Date

Data rules (non-negotiable):
  - NADAC_Per_Unit and generic counterpart: Decimal(18, 6) ROUND_HALF_UP.
  - Convert API numeric strings via Decimal(str(value)) — NEVER Decimal(float).
  - No float anywhere in this module.
  - Dates: parse ISO 8601 / YYYY-MM-DD strings to datetime.date.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors for all security/validation regex.
LESSON-005: All log extra keys prefixed with ingest_.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.downloader import compute_sha256
from shared.data_ingestion.field_registry import register_field
from shared.data_ingestion.sources.fda_ndc import normalize_ndc_11

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "cms_nadac"
_API_BASE_URL = (
    "https://data.medicaid.gov/api/1/datastore/query"
    "/fbb83258-11c7-47f5-8b18-5f8e79f7e704/0"
)
# CMS Medicaid DKAN API hard-caps per-page responses at 8000 records.
# Requests with limit > 8000 return HTTP 400.
_PAGE_SIZE = 8_000
_DEST_DIR = Path("data/reference/cms-nadac")
_FILENAME = "nadac_full.json"
_TIMEOUT_SECONDS = 120.0

# LESSON-004: \A...\Z anchors — never ^...$
_DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")

# ---------------------------------------------------------------------------
# Field registry — run at module import time
# ---------------------------------------------------------------------------

for _col, _desc, _pos, _dtype in [
    ("ndc_11",              "11-digit normalized NDC (5-4-2)",                        "NDC",                                        "str"),
    ("ndc_description",     "NDC Description from CMS NADAC",                         "NDC_Description",                            "str"),
    ("nadac_per_unit",      "NADAC price per unit — Decimal(18,6)",                   "NADAC_Per_Unit",                             "Decimal"),
    ("effective_date",      "Date NADAC price became effective",                       "Effective_Date",                             "date"),
    ("pricing_unit",        "Unit of measure: ML, GM, EA, etc.",                      "Pricing_Unit",                               "str"),
    ("pharmacy_type_indicator", "C=Chain, I=Independent, blank=combined",             "Pharmacy_Type_Indicator",                    "str"),
    ("otc",                 "Y=OTC, N=Rx",                                            "OTC",                                        "str"),
    ("explanation_code",    "CMS explanation code",                                   "Explanation_Code",                           "str"),
    ("classification",      "B, G, B-BIO, B-ANDA — classification for rate setting", "Classification_for_Rate_Setting",            "str"),
    ("generic_nadac_per_unit",    "Corresponding generic drug NADAC per unit",        "Corresponding_Generic_Drug_NADAC_Per_Unit",  "Decimal"),
    ("generic_effective_date",    "Corresponding generic drug effective date",        "Corresponding_Generic_Drug_Effective_Date",  "date"),
    ("as_of_date",          "As of date for this NADAC snapshot",                     "As_of_Date",                                 "date"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_nadac_pricing",
        column=_col,
        description=_desc,
        source_file="Socrata API",
        source_position=_pos,
        data_type=_dtype,
    )

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _parse_date(value: str | None) -> date | None:
    """Parse YYYY-MM-DD string to datetime.date; return None for empty/invalid."""
    if not value:
        return None
    v = value.strip()
    # Accept ISO 8601 YYYY-MM-DD
    if _DATE_RE.match(v):
        try:
            parts = v.split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None
    # Also accept YYYY/MM/DD
    v2 = v.replace("/", "-")
    if _DATE_RE.match(v2):
        try:
            parts = v2.split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None
    return None


def _parse_decimal(value: Any) -> Decimal | None:
    """Convert a value to Decimal(18,6) ROUND_HALF_UP.

    Always converts via str() to avoid IEEE-754 float contamination
    (financial-precision.md).  Returns None for empty/None/non-numeric.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return Decimal(s).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _parse_record(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Parse one NADAC API result dict into a normalized record dict.

    Returns None if the record is missing required fields (NDC, price, dates).
    Column names in the API use mixed-case with spaces and underscores.
    """
    # NDC — normalize to 11-digit via T3 helper
    ndc_raw = str(raw.get("ndc") or raw.get("NDC") or "").strip()
    if not ndc_raw:
        return None
    try:
        ndc_11 = normalize_ndc_11(ndc_raw)
    except ValueError:
        logger.warning(
            "NADAC: skipping record with invalid NDC",
            extra={"ingest_source": _SOURCE_NAME, "ingest_raw_ndc": ndc_raw[:30]},
        )
        return None

    # Required price
    price_raw = raw.get("nadac_per_unit") or raw.get("NADAC_Per_Unit")
    nadac_per_unit = _parse_decimal(price_raw)
    if nadac_per_unit is None:
        return None

    # Required dates
    eff_date = _parse_date(
        str(raw.get("effective_date") or raw.get("Effective_Date") or "")
    )
    as_of = _parse_date(
        str(raw.get("as_of_date") or raw.get("As_of_Date") or "")
    )
    if eff_date is None or as_of is None:
        return None

    # Optional description
    ndc_description = str(
        raw.get("ndc_description") or raw.get("NDC_Description") or ""
    ).strip() or None

    # Optional fields
    pricing_unit = str(
        raw.get("pricing_unit") or raw.get("Pricing_Unit") or ""
    ).strip() or None

    pharmacy_type = str(
        raw.get("pharmacy_type_indicator") or raw.get("Pharmacy_Type_Indicator") or ""
    ).strip() or None

    otc = str(raw.get("otc") or raw.get("OTC") or "").strip() or None

    explanation_code = str(
        raw.get("explanation_code") or raw.get("Explanation_Code") or ""
    ).strip() or None

    classification = str(
        raw.get("classification_for_rate_setting")
        or raw.get("Classification_for_Rate_Setting")
        or ""
    ).strip() or None

    generic_price_raw = (
        raw.get("corresponding_generic_drug_nadac_per_unit")
        or raw.get("Corresponding_Generic_Drug_NADAC_Per_Unit")
    )
    generic_nadac = _parse_decimal(generic_price_raw)

    generic_eff_raw = (
        raw.get("corresponding_generic_drug_effective_date")
        or raw.get("Corresponding_Generic_Drug_Effective_Date")
        or ""
    )
    generic_eff_date = _parse_date(str(generic_eff_raw))

    return {
        "ndc_11": ndc_11,
        "ndc_description": ndc_description,
        "nadac_per_unit": nadac_per_unit,
        "effective_date": eff_date,
        "pricing_unit": pricing_unit,
        "pharmacy_type_indicator": pharmacy_type,
        "otc": otc,
        "explanation_code": explanation_code,
        "classification": classification,
        "generic_nadac_per_unit": generic_nadac,
        "generic_effective_date": generic_eff_date,
        "as_of_date": as_of,
    }


# ---------------------------------------------------------------------------
# Ingester class
# ---------------------------------------------------------------------------


class CMSNADACIngester(DataSourceIngester):
    """Ingestion pipeline for the CMS NADAC dataset.

    Downloads the full NADAC dataset by paginating the Socrata API
    (10K records per page) into a single local JSON file.

    The SHA-256 of the accumulated JSON file is used for checksum-based
    deduplication — if the API returns the same data as last run, the
    ingestion is skipped.

    This is a global reference-data ingester — NOT tenant-scoped (LESSON-011).
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Paginate the Socrata API and write all results to a single JSON file.

        Returns the path to the collected JSON file.  The checksum of that file
        is computed by the base class ``run()`` method after download.
        """
        _DEST_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = _DEST_DIR / _FILENAME

        all_records: list[dict[str, Any]] = []
        offset = 0

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_TIMEOUT_SECONDS, connect=30.0),
            follow_redirects=True,
        ) as client:
            while True:
                params = {
                    "limit": str(_PAGE_SIZE),
                    "offset": str(offset),
                }
                logger.info(
                    "NADAC: fetching page",
                    extra={
                        "ingest_source": _SOURCE_NAME,
                        "ingest_offset": offset,
                        "ingest_page_size": _PAGE_SIZE,
                    },
                )
                response = await client.get(_API_BASE_URL, params=params)
                response.raise_for_status()
                payload = response.json()

                results: list[dict[str, Any]] = payload.get("results", [])
                if not results:
                    # API returned empty page — done
                    break

                all_records.extend(results)
                offset += _PAGE_SIZE

                # If API returned fewer records than page size, this was the last page
                if len(results) < _PAGE_SIZE:
                    break

        logger.info(
            "NADAC: all pages fetched",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_total_records": len(all_records),
            },
        )

        # Write to file as JSON array
        with dest_path.open("w", encoding="utf-8") as fh:
            json.dump(all_records, fh)

        return dest_path

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse the collected JSON file and yield normalized NADAC dicts.

        Each yielded dict contains the normalized fields ready for upsert.
        Records missing required fields (NDC, price, dates) are skipped.
        """
        with file_path.open(encoding="utf-8") as fh:
            records: list[dict[str, Any]] = json.load(fh)

        for raw in records:
            parsed = _parse_record(raw)
            if parsed is not None:
                yield parsed

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Bulk-upsert parsed NADAC records into drug_database.

        Delegates to NADACIngestionService, imported lazily so that
        drug-database module root must be on sys.path (added by conftest or
        load script) for ``src.services`` to resolve.
        """
        from src.services.pricing_ingestion import NADACIngestionService  # requires drug-database on path

        service = NADACIngestionService(db_session=self._db)
        return await service.load_records(records, source_name=self.source_name)


__all__ = ["CMSNADACIngester"]
