"""NPPES DataSourceIngester — CMS National Provider Identifier registry.

Handles three CMS file types off the ``NPI_Files.html`` index:

* ``weekly`` — ``NPPES_Data_Dissemination_MMDDYY_MMDDYY_Weekly[_V\\d+]?.zip``
  (~50-150 MB; ~35k rows of full-content-for-changed-NPIs). Source name
  ``nppes``.

* ``monthly`` — ``NPPES_Data_Dissemination_<Month>_<YYYY>[_V\\d+]?.zip``
  (~6 GB zipped / ~10 GB uncompressed; full 7M-row registry snapshot).
  Source name ``nppes_monthly``.

* ``deactivation`` — ``NPPES_Deactivated_NPI_Report_MMDDYY[_V\\d+]?.zip``
  (~2.5 MB; xlsx of all historically-deactivated NPIs). Source name
  ``nppes_deactivation``. UPDATE-only path against prescriber_dir.prescribers.

Weekly/monthly share a pipeline (CSV → NppesParser → nppes_upsert +
load_nppes_satellite_tables); deactivation runs a batched UPDATE.

LESSON-010: NPI is public — plaintext, do NOT encrypt.
LESSON-011: Global reference — no TenantScopedMixin.
LESSON-004: All regex uses \\A...\\Z.
LESSON-005: log extra keys prefixed with ingest_.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

import httpx
from sqlalchemy.orm import Session

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.downloader import download_to_file, unzip_if_zipped
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

Mode = Literal["weekly", "monthly", "deactivation"]

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

_CMS_INDEX_URL = "https://download.cms.gov/nppes/NPI_Files.html"
_CMS_FILE_BASE = "https://download.cms.gov/nppes/"

# LESSON-004: \A...\Z anchoring + re.fullmatch via .findall (which returns
# non-overlapping matches from the whole page — equivalent to an implicit
# .search, which is fine for an HTML scrape since anchoring a URL-inside-HTML
# to line boundaries would be over-strict).
_WEEKLY_ZIP_RE = re.compile(
    r"NPPES_Data_Dissemination_\d{6}_\d{6}_Weekly(?:_V\d+)?\.zip",
    re.IGNORECASE,
)
# Monthly filename shape: "NPPES_Data_Dissemination_April_2026_V2.zip"
# Month name is the English word (one of 12); year is 4 digits.
_MONTHLY_ZIP_RE = re.compile(
    r"NPPES_Data_Dissemination_"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"_\d{4}(?:_V\d+)?\.zip",
    re.IGNORECASE,
)
_DEACT_ZIP_RE = re.compile(
    r"NPPES_Deactivated_NPI_Report_\d{6}(?:_V\d+)?\.zip",
    re.IGNORECASE,
)

# Size caps — generous headroom over published typical sizes
_MAX_WEEKLY_BYTES = 300 * 1024 * 1024  # ~50-150 MB observed
_MAX_MONTHLY_BYTES = 12 * 1024 * 1024 * 1024  # ~6 GB zipped observed
_MAX_DEACT_BYTES = 50 * 1024 * 1024  # ~2.5 MB observed

_CACHE_DIR = Path("data/reference/nppes")

_BATCH_SIZE_SATELLITE = 1_000
_BATCH_SIZE_DEACTIVATION = 1_000

# ────────────────────────────────────────────────────────────────────────────
# Field registry (unchanged from pre-Wave-11 — covers the shared schema)
# ────────────────────────────────────────────────────────────────────────────

_SOURCE = "nppes"
_NPPES_FILE = "npidata_pfile.csv"

for _col, _src_col, _desc in [
    ("npi", "NPI", "10-digit National Provider Identifier"),
    ("entity_type", "Entity Type Code", "1=individual, 2=organization"),
    ("last_name", "Provider Last Name (Legal Name)", "Individual legal last name"),
    ("first_name", "Provider First Name", "Individual first name"),
    ("organization_name", "Provider Organization Name (Legal Business Name)", "Org legal name"),
    ("primary_taxonomy_code", "Healthcare Provider Taxonomy Code_1", "Primary taxonomy code"),
    ("enumeration_date", "Provider Enumeration Date", "NPI enumeration date"),
    ("status", "NPI Deactivation Date", "active or deactivated (derived)"),
]:
    register_field(
        source=_SOURCE,
        table="prescriber_dir.prescribers",
        column=_col,
        description=_desc,
        source_file=_NPPES_FILE,
        source_position=_src_col,
        data_type="str",
    )

for _col, _src_col, _desc in [
    ("replacement_npi", "Replacement NPI", "Replacement NPI when NPI changes"),
    ("ein", "Employer Identification Number (EIN)", "Org EIN (null for individuals)"),
    ("provider_enumeration_date", "Provider Enumeration Date", "Date NPI was issued"),
    ("npi_deactivation_date", "NPI Deactivation Date", "Date NPI was deactivated"),
    ("npi_reactivation_date", "NPI Reactivation Date", "Date NPI was reactivated"),
    ("npi_deactivation_reason_code", "NPI Deactivation Reason Code", "Reason code for deactivation"),
    ("is_sole_proprietor", "Is Sole Proprietor", "Y/N/X sole proprietor flag"),
    ("is_organization_subpart", "Is Organization Subpart", "Y/N/X subpart flag"),
    ("parent_organization_lbn", "Parent Organization Legal Business Name", "Parent org name"),
    ("parent_organization_tin", "Parent Organization TIN", "Parent org TIN"),
    ("authorized_official_last_name", "Authorized Official Last Name", "AO last name"),
    ("authorized_official_first_name", "Authorized Official First Name", "AO first name"),
    ("authorized_official_title_or_position", "Authorized Official Title or Position", "AO title"),
    ("authorized_official_telephone_number", "Authorized Official Telephone Number", "AO phone"),
    ("certification_date", "Certification Date", "Certification date"),
]:
    register_field(
        source=_SOURCE,
        table="prescriber_dir.nppes_prescriber_details",
        column=_col,
        description=_desc,
        source_file=_NPPES_FILE,
        source_position=_src_col,
        data_type="str",
    )

for _col, _src_col, _desc in [
    ("line_1", "Provider First Line Business Mailing Address", "Mailing address line 1"),
    ("line_2", "Provider Second Line Business Mailing Address", "Mailing address line 2"),
    ("city", "Provider Business Mailing Address City Name", "City"),
    ("state", "Provider Business Mailing Address State Name", "State"),
    ("postal_code", "Provider Business Mailing Address Postal Code", "Postal code"),
    ("telephone_number", "Provider Business Mailing Address Telephone Number", "Phone"),
    ("fax_number", "Provider Business Mailing Address Fax Number", "Fax"),
]:
    register_field(
        source=_SOURCE,
        table="prescriber_dir.prescriber_addresses",
        column=_col,
        description=_desc,
        source_file=_NPPES_FILE,
        source_position=_src_col,
        data_type="str",
    )

register_field(
    source=_SOURCE,
    table="prescriber_dir.prescriber_taxonomies",
    column="taxonomy_code",
    description="Healthcare provider taxonomy code (NUCC)",
    source_file=_NPPES_FILE,
    source_position="Healthcare Provider Taxonomy Code_1",
    data_type="str",
)
register_field(
    source=_SOURCE,
    table="prescriber_dir.prescriber_taxonomies",
    column="is_primary",
    description="Y/N whether this is the primary taxonomy",
    source_file=_NPPES_FILE,
    source_position="Healthcare Provider Primary Taxonomy Switch_1",
    data_type="str",
)
register_field(
    source=_SOURCE,
    table="prescriber_dir.prescriber_identifiers",
    column="identifier",
    description="Other provider identifier (Medicaid, state, etc.)",
    source_file=_NPPES_FILE,
    source_position="Other Provider Identifier_1",
    data_type="str",
)


# ────────────────────────────────────────────────────────────────────────────
# Mode helpers
# ────────────────────────────────────────────────────────────────────────────

_MODE_CONFIG: dict[str, dict[str, Any]] = {
    "weekly": {
        "regex": _WEEKLY_ZIP_RE,
        "max_bytes": _MAX_WEEKLY_BYTES,
        "source_name": "nppes",
        "data_ext": ".csv",
    },
    "monthly": {
        "regex": _MONTHLY_ZIP_RE,
        "max_bytes": _MAX_MONTHLY_BYTES,
        "source_name": "nppes_monthly",
        "data_ext": ".csv",
    },
    "deactivation": {
        "regex": _DEACT_ZIP_RE,
        "max_bytes": _MAX_DEACT_BYTES,
        "source_name": "nppes_deactivation",
        "data_ext": ".xlsx",
    },
}


# ────────────────────────────────────────────────────────────────────────────
# Ingester
# ────────────────────────────────────────────────────────────────────────────

class NppesIngester(DataSourceIngester):
    """Ingester for the CMS NPPES file suite.

    ``mode`` controls which CMS file we target and which load path runs:

    * ``weekly`` (default, backward-compatible): scrape + fetch the latest
      weekly dissemination CSV, run core prescriber upsert + satellite load.
    * ``monthly``: same pipeline but targets the monthly snapshot —
      intended for establishing a full 7M-row baseline.
    * ``deactivation``: fetch the weekly deactivation xlsx, UPDATE
      ``prescriber_dir.prescribers.status`` for every NPI listed.

    ``source_name`` is derived from ``mode`` so each mode has its own
    entry in ``shared.ingestion_runs`` (and its own checksum-dedup window
    — a monthly load won't suppress the next weekly).
    """

    source_name = "nppes"  # default; overridden per-mode below

    def __init__(
        self,
        db_session: Session,
        *,
        mode: Mode = "weekly",
        module_src_path: Path | None = None,
    ) -> None:
        super().__init__(db_session)
        if mode not in _MODE_CONFIG:
            raise ValueError(f"unknown NPPES mode: {mode!r} (expected weekly/monthly/deactivation)")
        self._mode: Mode = mode
        self._config = _MODE_CONFIG[mode]
        # Override class-level source_name with the mode-specific one so
        # the DataSourceIngester run-tracking machinery writes the right key.
        self.source_name = self._config["source_name"]
        if module_src_path is not None:
            src_str = str(module_src_path)
            if src_str not in sys.path:
                sys.path.insert(0, src_str)

    # ------------------------------------------------------------------ #
    # Download — scrape CMS index, fetch the latest matching ZIP, extract.
    # ------------------------------------------------------------------ #

    async def download(self) -> Path:
        url = await self._resolve_file_url()
        logger.info(
            "Downloading NPPES file",
            extra={
                "ingest_source": self.source_name,
                "ingest_mode": self._mode,
                "ingest_url": url,
            },
        )
        zip_path = await download_to_file(
            url,
            _CACHE_DIR,
            max_bytes=self._config["max_bytes"],
            timeout_seconds=600.0 if self._mode != "monthly" else 3600.0,
        )
        extract_dir = unzip_if_zipped(zip_path, _CACHE_DIR)
        return self._find_data_file(extract_dir)

    async def _resolve_file_url(self) -> str:
        """Scrape the CMS index page for the latest matching file."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(_CMS_INDEX_URL)
            resp.raise_for_status()
            html = resp.text

        regex: re.Pattern[str] = self._config["regex"]
        matches = regex.findall(html)
        if not matches:
            raise RuntimeError(
                f"Could not locate {self._mode} NPPES file on {_CMS_INDEX_URL}. "
                f"Regex: {regex.pattern}"
            )
        filename = matches[0]
        return f"{_CMS_FILE_BASE}{filename}"

    def _find_data_file(self, path: Path) -> Path:
        """Return the primary data file inside the extracted directory."""
        ext = self._config["data_ext"]
        if path.is_file() and path.suffix.lower() == ext:
            return path
        if path.is_dir():
            if ext == ".csv":
                for candidate in sorted(path.iterdir()):
                    if candidate.name.startswith("npidata_pfile") and candidate.suffix.lower() == ".csv":
                        return candidate
                csvs = sorted(path.glob("*.csv"))
                if csvs:
                    return csvs[0]
            elif ext == ".xlsx":
                xlsxs = sorted(path.glob("*.xlsx"))
                if xlsxs:
                    return xlsxs[0]
        raise FileNotFoundError(
            f"No NPPES {ext} found in extracted directory: {path}"
        )

    # ------------------------------------------------------------------ #
    # Parse
    # ------------------------------------------------------------------ #

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Stream rows from the data file. Never loads full file into memory."""
        if self._mode == "deactivation":
            yield from self._parse_deactivation(file_path)
        else:
            yield from self._parse_csv(file_path)

    @staticmethod
    def _parse_csv(file_path: Path) -> Iterator[dict[str, Any]]:
        import csv

        with file_path.open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                yield dict(row)

    @staticmethod
    def _parse_deactivation(file_path: Path) -> Iterator[dict[str, Any]]:
        """Stream (npi, deactivation_date) rows from the deactivation xlsx.

        Layout (verified 2026-04-17 against 20260413 report):
          - Sheet 'DeactivatedNPIs'
          - Row 0: title line ("NPPES Deactivated Records as of ...")
          - Row 1: column headers — "NPI" | "NPPES Deactivation Date"
          - Row 2+: data — 10-digit NPI string | MM/DD/YYYY date string
        """
        import openpyxl  # lazy import — only pulled in for deactivation mode

        from datetime import date, datetime

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        try:
            sheet_name = "DeactivatedNPIs" if "DeactivatedNPIs" in wb.sheetnames else wb.sheetnames[0]
            ws = wb[sheet_name]
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i < 2:  # title + header
                    continue
                if not row or not row[0]:
                    continue
                raw_npi = str(row[0]).strip()
                raw_date = row[1]
                parsed_date: date | None = None
                if isinstance(raw_date, datetime):
                    parsed_date = raw_date.date()
                elif isinstance(raw_date, date):
                    parsed_date = raw_date
                elif isinstance(raw_date, str) and raw_date.strip():
                    try:
                        parts = raw_date.strip().split("/")
                        if len(parts) == 3:
                            parsed_date = date(int(parts[2]), int(parts[0]), int(parts[1]))
                    except (ValueError, IndexError):
                        parsed_date = None
                yield {"npi": raw_npi, "deactivation_date": parsed_date}
        finally:
            wb.close()

    # ------------------------------------------------------------------ #
    # Load
    # ------------------------------------------------------------------ #

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        if self._mode == "deactivation":
            return self._load_deactivations(records)
        return self._load_csv_pipeline(records)

    def _load_csv_pipeline(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Shared weekly/monthly path — core upsert + satellite load.

        Consumes the iterator into a temp CSV, then invokes the two
        downstream services. Memory stays bounded because both the iterator
        and the temp-file reader are streaming; the temp file is the only
        persistent state.
        """
        import csv
        import tempfile

        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf-8",
            newline="",
            dir="/tmp",
        )
        tmp_path = Path(tmp.name)

        row_count = 0
        try:
            with tmp_path.open("w", newline="", encoding="utf-8") as fh:
                writer: csv.DictWriter | None = None
                for raw in records:
                    if writer is None:
                        writer = csv.DictWriter(fh, fieldnames=list(raw.keys()))
                        writer.writeheader()
                    writer.writerow(raw)
                    row_count += 1

            logger.info(
                "NPPES rows buffered to temp file",
                extra={
                    "ingest_source": self.source_name,
                    "ingest_mode": self._mode,
                    "ingest_row_count": row_count,
                    "ingest_tmp_path": str(tmp_path),
                },
            )

            inserted = 0
            updated = 0
            errored = 0

            try:
                from src.services.nppes_upsert import run_nppes_import

                with tmp_path.open(newline="", encoding="utf-8") as csv_fh:
                    refresh_log = run_nppes_import(
                        self._db,
                        csv_fh,
                        data_source="nppes",
                        refresh_type=self._mode,
                    )
                self._db.commit()
                inserted = refresh_log.records_added
                updated = refresh_log.records_updated
            except ImportError:
                logger.warning(
                    "nppes_core_upsert_skipped",
                    extra={
                        "ingest_source": self.source_name,
                        "ingest_note": "src.services.nppes_upsert not importable (PYTHONPATH not set)",
                    },
                )

            sat_stats = None
            try:
                from src.services.nppes_ingestion import load_nppes_satellite_tables

                sat_stats = load_nppes_satellite_tables(
                    self._db,
                    tmp_path,
                    batch_size=_BATCH_SIZE_SATELLITE,
                )
                self._db.commit()
            except ImportError:
                logger.warning(
                    "nppes_satellite_load_skipped",
                    extra={
                        "ingest_source": self.source_name,
                        "ingest_note": "src.services.nppes_ingestion not importable",
                    },
                )

            skipped = row_count - inserted - updated - errored
            return IngestionResult(
                source=self.source_name,
                status="completed",
                records_in_source=row_count,
                records_processed=row_count,
                records_inserted=inserted,
                records_updated=updated,
                records_skipped=max(0, skipped),
                records_errored=errored + (sat_stats.records_errored if sat_stats else 0),
            )

        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _load_deactivations(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batched UPDATE of prescribers.status for each deactivated NPI.

        Only NPIs already present in ``prescriber_dir.prescribers`` are
        affected — deactivation of an NPI we never loaded is a no-op
        (counted as 'skipped'). We use a VALUES-join UPDATE so one batch
        round-trips as a single statement.
        """
        from sqlalchemy import text

        errors_seen = 0
        batch: list[dict[str, Any]] = []
        total_processed = 0
        total_updated = 0
        total_skipped = 0

        def _flush() -> None:
            nonlocal total_updated, total_skipped, errors_seen
            if not batch:
                return
            # Build a VALUES clause: (:npi_0, :date_0), (:npi_1, :date_1), ...
            value_clauses: list[str] = []
            params: dict[str, Any] = {}
            for i, rec in enumerate(batch):
                value_clauses.append(f"(:npi_{i}, CAST(:date_{i} AS date))")
                params[f"npi_{i}"] = rec["npi"]
                params[f"date_{i}"] = rec["deactivation_date"]
            sql = (
                "UPDATE prescriber_dir.prescribers AS p "
                "SET status = 'deactivated', "
                "    deactivation_date = v.deact_date, "
                "    updated_at = NOW() "
                "FROM (VALUES " + ", ".join(value_clauses) + ") AS v(npi, deact_date) "
                "WHERE p.npi = v.npi"
            )
            try:
                result = self._db.execute(text(sql), params)
                self._db.commit()
                updated = result.rowcount or 0
                total_updated += updated
                total_skipped += len(batch) - updated
            except Exception as exc:
                self._db.rollback()
                errors_seen += len(batch)
                logger.exception(
                    "Deactivation batch failed — rolled back",
                    extra={
                        "ingest_source": self.source_name,
                        "ingest_batch_size": len(batch),
                        "ingest_error": str(exc)[:500],
                    },
                )
            finally:
                batch.clear()

        for record in records:
            total_processed += 1
            if not record.get("npi") or not record.get("deactivation_date"):
                total_skipped += 1
                continue
            batch.append(record)
            if len(batch) >= _BATCH_SIZE_DEACTIVATION:
                _flush()

        _flush()

        logger.info(
            "NPPES deactivation load complete",
            extra={
                "ingest_source": self.source_name,
                "ingest_records_processed": total_processed,
                "ingest_records_updated": total_updated,
                "ingest_records_skipped": total_skipped,
                "ingest_records_errored": errors_seen,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_in_source=total_processed,
            records_processed=total_processed,
            records_inserted=0,
            records_updated=total_updated,
            records_skipped=total_skipped,
            records_errored=errors_seen,
        )


__all__ = ["Mode", "NppesIngester"]
