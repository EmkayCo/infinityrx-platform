"""FDA REMS (Risk Evaluation and Mitigation Strategies) ingestion source.

Downloads REMS program data from the openFDA drug label API, filtering for
records with REMS data. Paginates via skip= parameter (max 26000 records).

Field registry registrations run at module import time.

Data rules:
  - Global reference data — no TenantScopedMixin (LESSON-011).
  - No float columns.
  - LESSON-004: All regex uses \\A...\\Z anchors.
  - LESSON-005: All log extra keys prefixed with ingest_.
  - ndc_codes stored as JSONB array.
  - etasu_requirements stored as JSONB dict.
  - raw_payload captures all extra openFDA fields.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "fda_rems"
_DEST_DIR = Path("data/reference/fda-rems")
_FILENAME = "fda_rems.json"
_BATCH_SIZE = 1_000
_API_LIMIT = 100
_API_MAX_SKIP = 26_000
_OPENFDA_URL = "https://api.fda.gov/drug/label.json"

# LESSON-004: \A...\Z anchors for all validation regex
_DATE_RE = re.compile(r"\A(\d{4})(\d{2})(\d{2})\Z")

# ---------------------------------------------------------------------------
# Field registry — run at module import time
# ---------------------------------------------------------------------------

for _col, _desc, _pos, _dtype in [
    ("application_number",           "NDA/BLA application number",              "openfda.application_number", "str"),
    ("rems_program_name",            "REMS program name",                        "rems",                       "str"),
    ("drug_name_brand",              "Brand name",                               "openfda.brand_name",         "str"),
    ("drug_name_generic",            "Generic/INN name",                         "openfda.generic_name",       "str"),
    ("ndc_codes",                    "NDC codes covered by this REMS (JSONB)",   "openfda.package_ndc",        "json"),
    ("rems_type",                    "REMS type (Medication Guide, ETASU, etc)","rems",                       "str"),
    ("etasu_requirements",           "ETASU requirements (JSONB)",               "rems",                       "json"),
    ("initial_approval_date",        "Initial REMS approval date",               "effective_time",             "date"),
    ("most_recent_modification_date","Most recent REMS modification date",       "effective_time",             "date"),
    ("status",                       "REMS status (Active/Modified/Released)",   "rems",                       "str"),
    ("shared_system_name",           "Shared REMS system name (nullable)",       "rems",                       "str"),
    ("raw_payload",                  "Full raw openFDA label payload (JSONB)",   "full_label",                 "json"),
]:
    register_field(
        source=_SOURCE_NAME,
        table="drug_database.drug_rems",
        column=_col,
        description=_desc,
        source_file="openFDA_drug_label_api",
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


def _parse_date_yyyymmdd(value: str | None) -> date | None:
    """Parse YYYYMMDD string to datetime.date; return None for empty/invalid."""
    if not value:
        return None
    stripped = value.strip()
    m = _DATE_RE.match(stripped)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _extract_rems_type(rems_list: list[str] | None) -> str | None:
    """Infer REMS type from keyword presence in REMS text array."""
    if not rems_list:
        return None
    combined = " ".join(rems_list).upper()
    if "ETASU" in combined:
        return "ETASU"
    if "COMMUNICATION PLAN" in combined:
        return "Communication Plan"
    if "MEDICATION GUIDE" in combined:
        return "Medication Guide"
    return _strip_or_none(rems_list[0]) if rems_list else None


def _build_etasu_requirements(rems_list: list[str] | None) -> dict | None:
    """Build ETASU requirements dict from REMS text array."""
    if not rems_list:
        return None
    combined = " ".join(rems_list)
    requirements: dict[str, bool] = {
        "prescriber_certification": bool(re.search(r"prescrib", combined, re.IGNORECASE)),
        "pharmacy_certification": bool(re.search(r"pharmac", combined, re.IGNORECASE)),
        "patient_enrollment": bool(re.search(r"patient.*enroll|enroll.*patient", combined, re.IGNORECASE)),
        "medication_guide": bool(re.search(r"medication guide", combined, re.IGNORECASE)),
        "communication_plan": bool(re.search(r"communication plan", combined, re.IGNORECASE)),
    }
    return requirements


def _parse_record(label: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a single openFDA label JSON record into a REMS dict.

    Returns None if the record lacks a usable application_number.
    """
    openfda = label.get("openfda") or {}

    app_numbers = openfda.get("application_number") or []
    application_number = app_numbers[0] if app_numbers else None
    if not application_number:
        return None
    application_number = application_number.strip()

    rems_list: list[str] = label.get("rems") or []
    rems_program_name = _strip_or_none(rems_list[0]) if rems_list else application_number

    brand_names = openfda.get("brand_name") or []
    generic_names = openfda.get("generic_name") or []
    ndc_codes: list[str] = openfda.get("package_ndc") or []

    effective_time_raw = _strip_or_none(label.get("effective_time"))
    parsed_date = _parse_date_yyyymmdd(effective_time_raw)

    # Collect all source keys for raw_payload (captures any undocumented fields)
    raw_payload: dict[str, Any] = {k: v for k, v in label.items()}

    return {
        "application_number": application_number,
        "rems_program_name": rems_program_name or application_number,
        "drug_name_brand": _strip_or_none(brand_names[0]) if brand_names else None,
        "drug_name_generic": _strip_or_none(generic_names[0]) if generic_names else None,
        "ndc_codes": ndc_codes if ndc_codes else None,
        "rems_type": _extract_rems_type(rems_list),
        "etasu_requirements": _build_etasu_requirements(rems_list),
        "initial_approval_date": parsed_date,
        "most_recent_modification_date": parsed_date,
        "status": "Active",
        "shared_system_name": None,
        "raw_payload": raw_payload,
    }


# ---------------------------------------------------------------------------
# Ingester
# ---------------------------------------------------------------------------


class FdaRemsIngester(DataSourceIngester):
    """Ingester for FDA REMS data via openFDA drug label API.

    Paginates through the openFDA label endpoint filtering for records with
    REMS data. Downloads to a local JSON file, then parses and upserts.

    LESSON-011: Global reference data — no TenantScopedMixin.
    LESSON-004: \\A...\\Z anchors for all regex.
    LESSON-005: All log extra keys prefixed with ingest_.
    """

    source_name = _SOURCE_NAME

    async def download(self) -> Path:
        """Fetch all REMS records from openFDA and write to local JSON file."""
        _DEST_DIR.mkdir(parents=True, exist_ok=True)
        dest = _DEST_DIR / _FILENAME
        all_records: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            skip = 0
            while skip <= _API_MAX_SKIP:
                params = {
                    "search": '(warnings_and_cautions:"REMS" OR boxed_warning:"REMS") AND _exists_:openfda.brand_name',
                    "limit": _API_LIMIT,
                    "skip": skip,
                }
                try:
                    resp = await client.get(_OPENFDA_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        logger.info(
                            "openFDA REMS pagination exhausted",
                            extra={"ingest_source": _SOURCE_NAME, "ingest_skip": skip},
                        )
                        break
                    raise

                results = data.get("results") or []
                if not results:
                    break
                all_records.extend(results)

                total = data.get("meta", {}).get("results", {}).get("total", 0)
                logger.info(
                    "REMS API page fetched",
                    extra={
                        "ingest_source": _SOURCE_NAME,
                        "ingest_skip": skip,
                        "ingest_page_count": len(results),
                        "ingest_total": total,
                    },
                )

                if len(results) < _API_LIMIT:
                    break
                skip += _API_LIMIT

        dest.write_text(json.dumps(all_records), encoding="utf-8")
        logger.info(
            "REMS download complete",
            extra={"ingest_source": _SOURCE_NAME, "ingest_record_count": len(all_records)},
        )
        return dest

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse the downloaded JSON file and yield one dict per REMS record."""
        raw_text = file_path.read_text(encoding="utf-8")
        records: list[dict[str, Any]] = json.loads(raw_text)
        for label in records:
            parsed = _parse_record(label)
            if parsed is not None:
                yield parsed

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batch-upsert REMS records into drug_database.drug_rems."""
        import sys
        from pathlib import Path as _Path

        _repo_root = _Path(__file__).resolve().parents[3]
        _drug_db_root = _repo_root / "modules" / "drug-database"
        for _p in (str(_repo_root), str(_drug_db_root)):
            if _p not in sys.path:
                sys.path.insert(0, _p)

        from src.services.fda_supplementary_ingestion import (  # type: ignore[import]
            RemsIngestionService,
        )

        svc = RemsIngestionService(db_session=self._db)
        return await svc.load_records(records, source_name=_SOURCE_NAME)


__all__ = [
    "FdaRemsIngester",
    "_parse_record",
    "_parse_date_yyyymmdd",
    "_extract_rems_type",
    "_build_etasu_requirements",
]
