"""NPPES DataSourceIngester — CMS National Provider Identifier registry.

Downloads the weekly NPPES dissemination file (~50–150 MB), extracts the
CSV, runs the core Prescriber upsert (via existing nppes_upsert.py), and
then populates the satellite tables (prescriber_addresses, prescriber_taxonomies,
prescriber_identifiers, nppes_prescriber_details) via the new ingestion service.

Weekly URL pattern (scrapes CMS index page to find latest week):
    https://download.cms.gov/nppes/NPPES_Data_Dissemination_MMDDYYYY-MMDDYYYY_Weekly.zip

LESSON-010: NPI is public — plaintext, do NOT encrypt.
LESSON-011: Global reference — no TenantScopedMixin.
LESSON-004: All regex uses \\A...\\Z.
LESSON-005: log extra keys prefixed with ingest_ (matches base.py convention).
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.downloader import download_to_file, unzip_if_zipped
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────

_CMS_INDEX_URL = "https://download.cms.gov/nppes/NPI_Files.html"

# Regex to locate the weekly zip href — LESSON-004
_WEEKLY_ZIP_RE = re.compile(
    r"NPPES_Data_Dissemination_\d{8}-\d{8}_Weekly\.zip",
    re.IGNORECASE,
)

# Max size: 300 MB (weekly file ~50–150 MB; leave headroom)
_MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024

# Download cache dir
_CACHE_DIR = Path("/tmp/ifx_ingest/nppes")

# ────────────────────────────────────────────────────────────────────────────
# Field registry — declare all NPPES → prescriber_dir mappings
# ────────────────────────────────────────────────────────────────────────────

_SOURCE = "nppes"
_NPPES_FILE = "npidata_pfile.csv"

# Core prescribers table
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

# nppes_prescriber_details
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

# prescriber_addresses
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

# prescriber_taxonomies (slot 1 as representative)
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

# prescriber_identifiers (slot 1 as representative)
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
# Ingester
# ────────────────────────────────────────────────────────────────────────────

class NppesIngester(DataSourceIngester):
    """Downloads, parses, and loads the CMS NPPES weekly dissemination file.

    Inherits from DataSourceIngester for orchestration (run tracking,
    checksum deduplication, retry, progress callbacks).

    The load() method delegates to two pipelines:
      1. nppes_upsert.run_nppes_import  → core Prescriber table
      2. nppes_ingestion.load_nppes_satellite_tables → satellite tables

    Per LESSON-011 these tables are global reference (no tenant_id).
    Per LESSON-010 NPI is plaintext.
    """

    source_name = "nppes"

    def __init__(self, db_session: Session, *, module_src_path: Path | None = None) -> None:
        super().__init__(db_session)
        # Inject the prescriber-directory src path so we can import its services.
        # When run from scripts/load_nppes.py the caller sets PYTHONPATH, but
        # we also accept an explicit override for testability.
        if module_src_path is not None:
            src_str = str(module_src_path)
            if src_str not in sys.path:
                sys.path.insert(0, src_str)

    # ------------------------------------------------------------------ #
    # Download
    # ------------------------------------------------------------------ #

    async def download(self) -> Path:
        """Scrape CMS index page to find the latest weekly ZIP, then download."""
        url = await self._resolve_weekly_url()
        logger.info(
            "Downloading NPPES weekly file",
            extra={"ingest_source": self.source_name, "ingest_url": url},
        )
        zip_path = await download_to_file(
            url,
            _CACHE_DIR,
            max_bytes=_MAX_DOWNLOAD_BYTES,
            timeout_seconds=600.0,  # large file
        )
        # Extract the ZIP; returns directory containing CSV(s)
        extract_dir = unzip_if_zipped(zip_path, _CACHE_DIR)
        # Return the primary CSV file inside the ZIP
        csv_path = self._find_csv(extract_dir)
        return csv_path

    async def _resolve_weekly_url(self) -> str:
        """Scrape the CMS index page for the latest weekly ZIP href."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(_CMS_INDEX_URL)
            resp.raise_for_status()
            html = resp.text

        matches = _WEEKLY_ZIP_RE.findall(html)
        if not matches:
            raise RuntimeError(
                f"Could not locate weekly NPPES ZIP on {_CMS_INDEX_URL}. "
                "Check the URL pattern or fall back to the full file."
            )
        # Use the first (most prominent) match
        filename = matches[0]
        return f"https://download.cms.gov/nppes/{filename}"

    @staticmethod
    def _find_csv(path: Path) -> Path:
        """Return the primary NPPES data CSV inside *path* (directory or file)."""
        if path.is_file() and path.suffix.lower() == ".csv":
            return path
        if path.is_dir():
            # Primary NPPES data file starts with "npidata_pfile"
            for candidate in sorted(path.iterdir()):
                if candidate.name.startswith("npidata_pfile") and candidate.suffix.lower() == ".csv":
                    return candidate
            # Fallback: any CSV in the directory
            csvs = sorted(path.glob("*.csv"))
            if csvs:
                return csvs[0]
        raise FileNotFoundError(
            f"No NPPES CSV found in extracted directory: {path}"
        )

    # ------------------------------------------------------------------ #
    # Parse — stream CSV rows as dicts
    # ------------------------------------------------------------------ #

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Stream-yield raw CSV rows. Never loads full file into memory."""
        import csv

        with file_path.open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                yield dict(row)

    # ------------------------------------------------------------------ #
    # Load — both core Prescriber table and satellite tables
    # ------------------------------------------------------------------ #

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Load parsed NPPES rows into all prescriber_dir tables.

        Two-pass strategy:
        1. Consume the iterator, write to a temp CSV, run core Prescriber upsert.
        2. Re-read the temp CSV for satellite tables.

        For the weekly file (~100K rows), writing a temp CSV is fast and keeps
        memory bounded — never accumulating full dataset in a list.
        """
        import csv
        import tempfile

        # Write records to temp file (iterator is consumed once)
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf-8",
            newline="",
            dir="/tmp",
        )
        tmp_path = Path(tmp.name)

        fieldnames: list[str] | None = None
        row_count = 0

        try:
            with tmp_path.open("w", newline="", encoding="utf-8") as fh:
                writer: csv.DictWriter | None = None
                for raw in records:
                    if writer is None:
                        fieldnames = list(raw.keys())
                        writer = csv.DictWriter(fh, fieldnames=fieldnames)
                        writer.writeheader()
                    writer.writerow(raw)
                    row_count += 1

            logger.info(
                "NPPES rows buffered to temp file",
                extra={
                    "ingest_source": self.source_name,
                    "ingest_row_count": row_count,
                    "ingest_tmp_path": str(tmp_path),
                },
            )

            # ---- Pass 1: core Prescriber upsert ----
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
                        refresh_type="weekly",
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

            # ---- Pass 2: satellite tables ----
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
            # Clean up temp file
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


_BATCH_SIZE_SATELLITE = 1000

__all__ = ["NppesIngester"]
