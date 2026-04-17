"""CMS Medicare Part D Prescriber Utilization ingestion source.

Downloads the annual CMS Medicare Part D Prescribers by Provider dataset
from the Socrata API, streaming pages of 50,000 records each into a local
JSON file.  All ~1.2M rows are captured; raw_payload JSONB stores the full
source row as a forward-compatibility fallback.

Socrata API:
  https://data.cms.gov/data-api/v1/dataset/{dataset_id}/data
  Pagination: ?$limit=50000&$offset=N
  Termination: empty results array.

financial-precision.md: ALL money columns converted via Decimal(str(value)).
  NEVER Decimal(float_value).  No float anywhere in this module.
LESSON-010: NPI plaintext — public NPPES identifier.
LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z regex anchors — never ^...$.
LESSON-005: log extra keys prefixed with ingest_.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SOURCE_NAME = "cms_part_d"

# Dataset ID for Medicare Part D Prescribers by Provider.
#
# CMS keeps this ID stable and rolls the data year forward in-place when
# a new CY is released. As of 2025-09-09 the dataset's temporal range is
# 2013-01-01 / 2023-12-31, so ``14d8e8a9-…`` now points to CY2023. When
# CMS publishes CY2024 (expected ~2026-09, their usual cadence), this
# same ID will point at that data — only _CURRENT_DATA_YEAR below needs
# to be bumped. CMS data.json catalog will also be useful for
# confirming.
_DATASET_ID = "14d8e8a9-7e9b-4370-a044-bf97c46b4b44"

# Calendar year of the data currently published at _DATASET_ID. This is
# NOT "current year" and NOT "now.year - 1" — CMS Part D PUFs have a
# 2-3 year privacy-review lag. Bump this when the dataset's temporal
# range in the CMS catalog advances.
_CURRENT_DATA_YEAR = 2023
_API_BASE_URL = f"https://data.cms.gov/data-api/v1/dataset/{_DATASET_ID}/data"
_PAGE_SIZE = 5_000  # data.cms.gov v1 API caps page size; 5000 is a safe limit
_TIMEOUT_SECONDS = 120.0
_DEST_DIR = Path("data/reference/cms-part-d")
_FILENAME = "part_d_prescriber.json"
_BATCH_SIZE = 1_000

# LESSON-004: \A...\Z — never ^...$
_NPI_RE = re.compile(r"\A\d{10}\Z")

# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

_TABLE = "prescriber_directory.medicare_part_d_utilization"
_SRC_FILE = "Socrata API"

for _col, _src, _desc, _dtype in [
    ("npi",                   "Prscrbr_NPI",             "10-digit NPI (plaintext, LESSON-010)",                         "str"),
    ("year",                  "year",                    "Data year (e.g. 2023)",                                        "int"),
    ("prscrbr_last_org_name", "Prscrbr_Last_Org_Name",   "Provider last name or org name",                               "str"),
    ("prscrbr_first_name",    "Prscrbr_First_Name",      "Provider first name",                                          "str"),
    ("prscrbr_city",          "Prscrbr_City",            "Provider city",                                                "str"),
    ("prscrbr_state_abrvtn",  "Prscrbr_State_Abrvtn",    "Provider state abbreviation",                                  "str"),
    ("prscrbr_state_fips",    "Prscrbr_State_FIPS",      "Provider state FIPS code",                                     "str"),
    ("prscrbr_zip5",          "Prscrbr_Zip5",            "Provider 5-digit ZIP",                                         "str"),
    ("prscrbr_ruca",          "Prscrbr_RUCA",            "Rural-Urban Commuting Area code",                              "str"),
    ("prscrbr_cntry",         "Prscrbr_Cntry",           "Provider country",                                             "str"),
    ("prscrbr_type",          "Prscrbr_Type",            "Provider type / specialty",                                    "str"),
    ("prscrbr_type_src",      "Prscrbr_Type_Src",        "Source of provider type (taxonomy or specialty)",              "str"),
    ("tot_clms",              "Tot_Clms",                "Total claims",                                                 "int"),
    ("tot_30day_fills",       "Tot_30day_Fills",         "Total 30-day standardized fills",                              "int"),
    ("tot_day_suply",         "Tot_Day_Suply",           "Total days supply",                                            "int"),
    ("tot_drug_cst",          "Tot_Drug_Cst",            "Total drug cost (Decimal)",                                    "Decimal"),
    ("tot_benes",             "Tot_Benes",               "Total beneficiaries",                                          "int"),
    ("brnd_clms",             "Brnd_Clms",               "Brand claims",                                                 "int"),
    ("brnd_drug_cst",         "Brnd_Drug_Cst",           "Brand drug cost (Decimal)",                                    "Decimal"),
    ("gnrc_clms",             "Gnrc_Clms",               "Generic claims",                                               "int"),
    ("gnrc_drug_cst",         "Gnrc_Drug_Cst",           "Generic drug cost (Decimal)",                                  "Decimal"),
    ("othr_clms",             "Othr_Clms",               "Other claims",                                                 "int"),
    ("othr_drug_cst",         "Othr_Drug_Cst",           "Other drug cost (Decimal)",                                    "Decimal"),
    ("mapd_clms",             "MAPD_Clms",               "Medicare Advantage PD claims",                                 "int"),
    ("mapd_drug_cst",         "MAPD_Drug_Cst",           "Medicare Advantage PD drug cost (Decimal)",                   "Decimal"),
    ("pdp_clms",              "PDP_Clms",                "Standalone Part D plan claims",                                "int"),
    ("pdp_drug_cst",          "PDP_Drug_Cst",            "Standalone Part D drug cost (Decimal)",                       "Decimal"),
    ("lis_clms",              "LIS_Clms",                "Low Income Subsidy claims",                                    "int"),
    ("lis_drug_cst",          "LIS_Drug_Cst",            "LIS drug cost (Decimal)",                                      "Decimal"),
    ("opioid_clms",           "Opioid_Clms",             "Opioid claims",                                                "int"),
    ("opioid_drug_cst",       "Opioid_Drug_Cst",         "Opioid drug cost (Decimal)",                                   "Decimal"),
    ("opioid_prscrbr_rate",   "Opioid_Prscrbr_Rate",     "Opioid prescriber rate (Numeric 7,4)",                         "Decimal"),
    ("opioid_la_clms",        "Opioid_LA_Clms",          "Long-acting opioid claims",                                    "int"),
    ("opioid_la_drug_cst",    "Opioid_LA_Drug_Cst",      "Long-acting opioid drug cost (Decimal)",                      "Decimal"),
    ("antbtc_clms",           "Antbtc_Clms",             "Antibiotic claims",                                            "int"),
    ("antbtc_drug_cst",       "Antbtc_Drug_Cst",         "Antibiotic drug cost (Decimal)",                               "Decimal"),
    ("antpsycht_ge65_clms",   "Antpsycht_GE65_Clms",     "Antipsychotic 65+ claims",                                     "int"),
    ("antpsycht_ge65_drug_cst","Antpsycht_GE65_Drug_Cst","Antipsychotic 65+ drug cost (Decimal)",                        "Decimal"),
    ("bene_avg_age",          "Bene_Avg_Age",            "Average beneficiary age",                                      "int"),
    ("bene_avg_risk_scre",    "Bene_Avg_Risk_Scre",      "Average beneficiary risk score (Numeric 6,4)",                 "Decimal"),
    ("bene_race_wht_cnt",     "Bene_Race_Wht_Cnt",       "White beneficiary count",                                      "int"),
    ("bene_race_black_cnt",   "Bene_Race_Black_Cnt",     "Black beneficiary count",                                      "int"),
    ("bene_race_api_cnt",     "Bene_Race_Api_Cnt",       "Asian/Pacific Islander beneficiary count",                     "int"),
    ("bene_race_hspnc_cnt",   "Bene_Race_Hspnc_Cnt",     "Hispanic beneficiary count",                                   "int"),
    ("bene_race_natind_cnt",  "Bene_Race_Natind_Cnt",    "Native American beneficiary count",                            "int"),
    ("bene_race_othr_cnt",    "Bene_Race_Othr_Cnt",      "Other race beneficiary count",                                 "int"),
    ("bene_dual_cnt",         "Bene_Dual_Cnt",           "Dual eligible (Medicare+Medicaid) count",                      "int"),
    ("bene_ndual_cnt",        "Bene_NDUAL_Cnt",          "Non-dual eligible count",                                      "int"),
    ("ge65_tot_clms",         "GE65_Tot_Clms",           "65+ total claims",                                             "int"),
    ("ge65_tot_drug_cst",     "GE65_Tot_Drug_Cst",       "65+ total drug cost (Decimal)",                                "Decimal"),
    ("ge65_brnd_clms",        "GE65_Brnd_Clms",          "65+ brand claims",                                             "int"),
    ("ge65_brnd_drug_cst",    "GE65_Brnd_Drug_Cst",      "65+ brand drug cost (Decimal)",                                "Decimal"),
    ("ge65_gnrc_clms",        "GE65_Gnrc_Clms",          "65+ generic claims",                                           "int"),
    ("ge65_gnrc_drug_cst",    "GE65_Gnrc_Drug_Cst",      "65+ generic drug cost (Decimal)",                              "Decimal"),
    ("ge65_othr_clms",        "GE65_Othr_Clms",          "65+ other claims",                                             "int"),
    ("ge65_othr_drug_cst",    "GE65_Othr_Drug_Cst",      "65+ other drug cost (Decimal)",                                "Decimal"),
    ("raw_payload",           "raw_payload",             "Full source row as JSONB fallback",                            "dict"),
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


def _parse_decimal_2(value: Any) -> Decimal | None:
    """Convert to Decimal(18,2) ROUND_HALF_UP via str() — NEVER float."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _parse_decimal_4(value: Any) -> Decimal | None:
    """Convert to Decimal(7,4) ROUND_HALF_UP via str() — for rate/risk fields."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return Decimal(s).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(Decimal(s).to_integral_value(rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None


def _get(row: dict[str, Any], *keys: str) -> Any:
    """Return the first non-None value found among *keys* in *row*."""
    for k in keys:
        v = row.get(k)
        if v is not None:
            return v
    return None


def parse_part_d_row(raw: dict[str, Any], year: int) -> dict[str, Any] | None:
    """Parse one CMS Part D API row into a normalized record.

    Returns None if the NPI is missing or invalid.
    Negative values are allowed (CMS adjustment rows can be negative).
    Missing numeric columns → None (not 0).
    """
    npi_raw = str(_get(raw, "Prscrbr_NPI", "PRSCRBR_NPI", "prscrbr_npi") or "").strip()
    if not _NPI_RE.match(npi_raw):
        logger.warning(
            "Part D: skipping row with invalid NPI",
            extra={"ingest_source": _SOURCE_NAME, "ingest_raw_npi": npi_raw[:15]},
        )
        return None

    return {
        "npi": npi_raw,
        "year": year,
        "prscrbr_last_org_name": str(_get(raw, "Prscrbr_Last_Org_Name", "prscrbr_last_org_name") or "").strip() or None,
        "prscrbr_first_name": str(_get(raw, "Prscrbr_First_Name", "prscrbr_first_name") or "").strip() or None,
        "prscrbr_city": str(_get(raw, "Prscrbr_City", "prscrbr_city") or "").strip() or None,
        "prscrbr_state_abrvtn": str(_get(raw, "Prscrbr_State_Abrvtn", "prscrbr_state_abrvtn") or "").strip() or None,
        "prscrbr_state_fips": str(_get(raw, "Prscrbr_State_FIPS", "prscrbr_state_fips") or "").strip() or None,
        "prscrbr_zip5": str(_get(raw, "Prscrbr_Zip5", "Prscrbr_zip5", "prscrbr_zip5") or "").strip() or None,
        "prscrbr_ruca": str(_get(raw, "Prscrbr_RUCA", "prscrbr_ruca") or "").strip() or None,
        "prscrbr_cntry": str(_get(raw, "Prscrbr_Cntry", "prscrbr_cntry") or "").strip() or None,
        "prscrbr_type": str(_get(raw, "Prscrbr_Type", "prscrbr_type") or "").strip() or None,
        "prscrbr_type_src": str(_get(raw, "Prscrbr_Type_Src", "Prscrbr_Type_src", "prscrbr_type_src") or "").strip() or None,
        # Utilization
        "tot_clms": _parse_int(_get(raw, "Tot_Clms", "tot_clms")),
        "tot_30day_fills": _parse_decimal_2(_get(raw, "Tot_30day_Fills", "tot_30day_fills")),
        "tot_day_suply": _parse_int(_get(raw, "Tot_Day_Suply", "tot_day_suply")),
        "tot_drug_cst": _parse_decimal_2(_get(raw, "Tot_Drug_Cst", "tot_drug_cst")),
        "tot_benes": _parse_int(_get(raw, "Tot_Benes", "tot_benes")),
        # Brand/Generic — newer API uses *_Tot_* infix
        "brnd_clms": _parse_int(_get(raw, "Brnd_Tot_Clms", "Brnd_Clms", "brnd_clms")),
        "brnd_drug_cst": _parse_decimal_2(_get(raw, "Brnd_Tot_Drug_Cst", "Brnd_Drug_Cst", "brnd_drug_cst")),
        "gnrc_clms": _parse_int(_get(raw, "Gnrc_Tot_Clms", "Gnrc_Clms", "gnrc_clms")),
        "gnrc_drug_cst": _parse_decimal_2(_get(raw, "Gnrc_Tot_Drug_Cst", "Gnrc_Drug_Cst", "gnrc_drug_cst")),
        "othr_clms": _parse_int(_get(raw, "Othr_Tot_Clms", "Othr_Clms", "othr_clms")),
        "othr_drug_cst": _parse_decimal_2(_get(raw, "Othr_Tot_Drug_Cst", "Othr_Drug_Cst", "othr_drug_cst")),
        # Plan split
        "mapd_clms": _parse_int(_get(raw, "MAPD_Tot_Clms", "MAPD_Clms", "mapd_clms")),
        "mapd_drug_cst": _parse_decimal_2(_get(raw, "MAPD_Tot_Drug_Cst", "MAPD_Drug_Cst", "mapd_drug_cst")),
        "pdp_clms": _parse_int(_get(raw, "PDP_Tot_Clms", "PDP_Clms", "pdp_clms")),
        "pdp_drug_cst": _parse_decimal_2(_get(raw, "PDP_Tot_Drug_Cst", "PDP_Drug_Cst", "pdp_drug_cst")),
        "lis_clms": _parse_int(_get(raw, "LIS_Tot_Clms", "LIS_Clms", "lis_clms")),
        "lis_drug_cst": _parse_decimal_2(_get(raw, "LIS_Drug_Cst", "lis_drug_cst")),
        # Drug classes
        "opioid_clms": _parse_int(_get(raw, "Opioid_Tot_Clms", "Opioid_Clms", "opioid_clms")),
        "opioid_drug_cst": _parse_decimal_2(_get(raw, "Opioid_Tot_Drug_Cst", "Opioid_Drug_Cst", "opioid_drug_cst")),
        "opioid_prscrbr_rate": _parse_decimal_4(_get(raw, "Opioid_Prscrbr_Rate", "opioid_prscrbr_rate")),
        "opioid_la_clms": _parse_int(_get(raw, "Opioid_LA_Tot_Clms", "Opioid_LA_Clms", "opioid_la_clms")),
        "opioid_la_drug_cst": _parse_decimal_2(_get(raw, "Opioid_LA_Tot_Drug_Cst", "Opioid_LA_Drug_Cst", "opioid_la_drug_cst")),
        "antbtc_clms": _parse_int(_get(raw, "Antbtc_Tot_Clms", "Antbtc_Clms", "antbtc_clms")),
        "antbtc_drug_cst": _parse_decimal_2(_get(raw, "Antbtc_Tot_Drug_Cst", "Antbtc_Drug_Cst", "antbtc_drug_cst")),
        "antpsycht_ge65_clms": _parse_int(_get(raw, "Antpsyct_GE65_Tot_Clms", "Antpsycht_GE65_Clms", "antpsycht_ge65_clms")),
        "antpsycht_ge65_drug_cst": _parse_decimal_2(_get(raw, "Antpsyct_GE65_Tot_Drug_Cst", "Antpsycht_GE65_Drug_Cst", "antpsycht_ge65_drug_cst")),
        # Demographics
        "bene_avg_age": _parse_int(_get(raw, "Bene_Avg_Age", "bene_avg_age")),
        "bene_avg_risk_scre": _parse_decimal_4(_get(raw, "Bene_Avg_Risk_Scre", "bene_avg_risk_scre")),
        "bene_race_wht_cnt": _parse_int(_get(raw, "Bene_Race_Wht_Cnt", "bene_race_wht_cnt")),
        "bene_race_black_cnt": _parse_int(_get(raw, "Bene_Race_Black_Cnt", "bene_race_black_cnt")),
        "bene_race_api_cnt": _parse_int(_get(raw, "Bene_Race_Api_Cnt", "bene_race_api_cnt")),
        "bene_race_hspnc_cnt": _parse_int(_get(raw, "Bene_Race_Hspnc_Cnt", "bene_race_hspnc_cnt")),
        "bene_race_natind_cnt": _parse_int(_get(raw, "Bene_Race_Natind_Cnt", "bene_race_natind_cnt")),
        "bene_race_othr_cnt": _parse_int(_get(raw, "Bene_Race_Othr_Cnt", "bene_race_othr_cnt")),
        "bene_dual_cnt": _parse_int(_get(raw, "Bene_Dual_Cnt", "bene_dual_cnt")),
        "bene_ndual_cnt": _parse_int(_get(raw, "Bene_NDUAL_Cnt", "bene_ndual_cnt")),
        # 65+ subset
        "ge65_tot_clms": _parse_int(_get(raw, "GE65_Tot_Clms", "ge65_tot_clms")),
        "ge65_tot_drug_cst": _parse_decimal_2(_get(raw, "GE65_Tot_Drug_Cst", "ge65_tot_drug_cst")),
        "ge65_brnd_clms": _parse_int(_get(raw, "GE65_Brnd_Clms", "ge65_brnd_clms")),
        "ge65_brnd_drug_cst": _parse_decimal_2(_get(raw, "GE65_Brnd_Drug_Cst", "ge65_brnd_drug_cst")),
        "ge65_gnrc_clms": _parse_int(_get(raw, "GE65_Gnrc_Clms", "ge65_gnrc_clms")),
        "ge65_gnrc_drug_cst": _parse_decimal_2(_get(raw, "GE65_Gnrc_Drug_Cst", "ge65_gnrc_drug_cst")),
        "ge65_othr_clms": _parse_int(_get(raw, "GE65_Othr_Clms", "ge65_othr_clms")),
        "ge65_othr_drug_cst": _parse_decimal_2(_get(raw, "GE65_Othr_Drug_Cst", "ge65_othr_drug_cst")),
        # Full source row
        "raw_payload": dict(raw),
    }


# ---------------------------------------------------------------------------
# Ingester
# ---------------------------------------------------------------------------


class CmsPartDPrescriberIngester(DataSourceIngester):
    """Ingests CMS Medicare Part D Prescribers by Provider annual dataset.

    Paginates the Socrata API (50K rows/page) into a single JSON file,
    then batch-upserts 1,000 rows at a time using INSERT ON CONFLICT DO UPDATE.

    Global reference data — NOT tenant-scoped (LESSON-011).
    NPI stored plaintext (LESSON-010).
    All money via Decimal(str(x)) — no float (financial-precision.md).
    """

    source_name = _SOURCE_NAME

    def __init__(self, db_session: Any, *, year: int | None = None) -> None:
        super().__init__(db_session)
        # Default to _CURRENT_DATA_YEAR (the CY actually published at the
        # stable dataset ID), NOT calendar-now-minus-one. CMS Part D PUFs
        # lag 2-3 years, so `datetime.now().year - 1` gets a year CMS
        # hasn't published yet and silently tags every row with the
        # wrong year.
        self._year = year if year is not None else _CURRENT_DATA_YEAR

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
                    "Part D: fetching page",
                    extra={
                        "ingest_source": _SOURCE_NAME,
                        "ingest_offset": offset,
                        "ingest_page_size": _PAGE_SIZE,
                        "ingest_year": self._year,
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
            "Part D: all pages fetched",
            extra={
                "ingest_source": _SOURCE_NAME,
                "ingest_total_records": len(all_records),
                "ingest_year": self._year,
            },
        )
        with dest_path.open("w", encoding="utf-8") as fh:
            json.dump(all_records, fh)
        return dest_path

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse the collected JSON file; yield normalized dicts."""
        # Support both JSON (from Socrata API) and CSV bulk download
        if file_path.suffix.lower() == ".csv":
            yield from self._parse_csv(file_path)
            return
        with file_path.open(encoding="utf-8") as fh:
            records: list[dict[str, Any]] = json.load(fh)
        for raw in records:
            parsed = parse_part_d_row(raw, self._year)
            if parsed is not None:
                yield parsed

    def _parse_csv(self, file_path: Path) -> Iterator[dict[str, Any]]:
        with file_path.open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for raw in reader:
                parsed = parse_part_d_row(dict(raw), self._year)
                if parsed is not None:
                    yield parsed

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batch-upsert Part D rows; INSERT ON CONFLICT (npi, year) DO UPDATE."""
        import importlib
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        _m = importlib.import_module("src.models.medicare_tables")
        PartDModel = _m.MedicarePartDUtilization

        inserted = 0
        updated = 0
        errored = 0
        batch: list[dict[str, Any]] = []
        now = datetime.now(UTC)

        dialect_name = self._db.connection().dialect.name

        def _flush(b: list[dict[str, Any]]) -> tuple[int, int]:
            for row in b:
                row["updated_at"] = now
            if dialect_name == "postgresql":
                tbl = PartDModel.__table__
                stmt = pg_insert(tbl).values(b)
                update_cols = {c.name: stmt.excluded[c.name] for c in tbl.columns if c.name not in ("npi", "year")}
                self._db.execute(stmt.on_conflict_do_update(index_elements=["npi", "year"], set_=update_cols))
            else:
                for row in b:
                    obj = PartDModel(**row)
                    self._db.merge(obj)
            self._db.flush()
            return len(b), 0

        for record in records:
            batch.append(record)
            if len(batch) >= _BATCH_SIZE:
                _ins, _upd = _flush(batch)
                inserted += _ins
                batch = []

        if batch:
            _ins, _upd = _flush(batch)
            inserted += _ins

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=inserted + updated + errored,
            records_inserted=inserted,
            records_updated=updated,
            records_errored=errored,
        )


__all__ = [
    "CmsPartDPrescriberIngester",
    "parse_part_d_row",
    "_parse_decimal_2",
    "_parse_decimal_4",
    "_parse_int",
]
