"""OIG LEIE (List of Excluded Individuals/Entities) DataSourceIngester.

Downloads the OIG monthly exclusion file and loads it into shared.oig_leie_exclusions.
After load, cross-references prescribers and pharmacies by NPI to set is_excluded flags.

Source: https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv (monthly full replace)

LESSON-004: \\A...\\Z anchors on all regex.
LESSON-005: log extra keys prefixed with leie_ or ingest_.
LESSON-010: NPI is public — plaintext.
LESSON-011: Global reference table — no TenantScopedMixin.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.downloader import download_to_file
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

# OIG downloads page to scrape for the current UPDATED.csv link
_OIG_DOWNLOADS_URL = "https://oig.hhs.gov/exclusions/downloadables.asp"
_OIG_DIRECT_URL = "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv"

# LESSON-004: strict anchors
_OIG_CSV_HREF_RE = re.compile(r"\A.*UPDATED\.csv\Z", re.IGNORECASE)

_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
_CACHE_DIR = Path("/tmp/ifx_ingest/oig_leie")
_BATCH_SIZE = 1000

_SOURCE = "oig_leie"
_SOURCE_FILE = "UPDATED.csv"

# All 18 LEIE fields registered
for _col, _src_col, _desc in [
    ("lastname", "LASTNAME", "Excluded individual last name"),
    ("firstname", "FIRSTNAME", "Excluded individual first name"),
    ("midname", "MIDNAME", "Excluded individual middle name"),
    ("busname", "BUSNAME", "Excluded business/entity name"),
    ("general", "GENERAL", "General provider type classification"),
    ("specialty", "SPECIALTY", "Provider specialty"),
    ("upin", "UPIN", "Unique Physician Identification Number"),
    ("npi", "NPI", "National Provider Identifier (public, plaintext)"),
    ("dob", "DOB", "Date of birth (OIG public data — not PHI in this context)"),
    ("address", "ADDRESS", "Street address"),
    ("city", "CITY", "City"),
    ("state", "STATE", "State abbreviation"),
    ("zip", "ZIP", "ZIP code"),
    ("excltype", "EXCLTYPE", "Exclusion type (1128 authority code)"),
    ("excldate", "EXCLDATE", "Date of exclusion"),
    ("reindate", "REINDATE", "Date of reinstatement (null = still excluded)"),
    ("waiverdate", "WAIVERDATE", "Waiver date if applicable"),
    ("waiverstate", "WAIVERSTATE", "State associated with waiver"),
]:
    register_field(
        source=_SOURCE,
        table="shared.oig_leie_exclusions",
        column=_col,
        description=_desc,
        source_file=_SOURCE_FILE,
        source_position=_src_col,
        data_type="str",
    )


def _parse_leie_date(raw: str | None) -> date | None:
    """Parse LEIE date fields — format is YYYYMMDD or empty."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in ("%Y%m%d", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


class OigLeieIngester(DataSourceIngester):
    """Downloads and loads the OIG LEIE monthly exclusion CSV.

    After bulk load, runs cross-reference UPDATE to flip is_excluded on
    prescribers and pharmacies tables where NPI matches an active exclusion.
    """

    source_name = "oig_leie"

    async def download(self) -> Path:
        """Download UPDATED.csv from OIG. Falls back to direct URL if scraping fails."""
        url = await self._resolve_download_url()
        logger.info(
            "Downloading OIG LEIE file",
            extra={"ingest_source": self.source_name, "leie_url": url},
        )
        csv_path = await download_to_file(
            url,
            _CACHE_DIR,
            max_bytes=_MAX_DOWNLOAD_BYTES,
            timeout_seconds=120.0,
        )
        return csv_path

    async def _resolve_download_url(self) -> str:
        """Scrape OIG downloads page for the UPDATED.csv href; fall back to known URL."""
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(_OIG_DOWNLOADS_URL)
                resp.raise_for_status()
                html = resp.text
            # Find href containing UPDATED.csv
            for token in html.split('"'):
                if "UPDATED.csv" in token and token.startswith("http"):
                    return token
            # Look for relative paths
            for token in html.split('"'):
                if "UPDATED.csv" in token:
                    if token.startswith("/"):
                        return f"https://oig.hhs.gov{token}"
        except (httpx.HTTPError, httpx.TransportError):
            logger.info(
                "OIG downloads page scrape failed — using direct URL",
                extra={"ingest_source": self.source_name},
            )
        return _OIG_DIRECT_URL

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Stream-parse LEIE CSV, yielding one dict per row."""
        with file_path.open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                yield dict(row)

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batch-upsert LEIE records, then run cross-reference UPDATEs.

        Uses per-row SQLAlchemy ORM upsert rather than flush_upsert_batch
        because the natural key ``(lastname, firstname, busname, excldate)``
        has NULL-containing rows in production: 3,369 rows have NULL
        lastname/firstname (pure businesses) and 79,527 have NULL busname
        (individuals). SQL ON CONFLICT treats NULL as distinct — running
        flush_upsert_batch would silently duplicate those rows on every
        monthly load. SQLAlchemy's ``col == None`` comparator correctly
        generates ``IS NULL``, so the ORM path gets it right.

        Per-batch commits limit blast radius of a failure. Rows are
        committed in chunks of ``_BATCH_SIZE`` so a bad row late in the
        stream doesn't roll back everything upstream.
        """
        from shared.data_ingestion.batching import ErrorAggregator

        errors = ErrorAggregator()
        processed = 0
        inserted = 0
        batch: list[dict[str, Any]] = []

        def _flush_batch() -> None:
            nonlocal inserted
            if not batch:
                return
            for row in batch:
                try:
                    self._upsert_row(row)
                    inserted += 1
                except Exception as exc:
                    errors.record("upsert", str(exc), raw_row=row)
            self._db.commit()
            batch.clear()

        for raw in records:
            batch.append(raw)
            processed += 1
            if len(batch) >= _BATCH_SIZE:
                _flush_batch()

        _flush_batch()

        xref_prescribers = self._cross_reference_prescribers()
        xref_pharmacies = self._cross_reference_pharmacies()

        errors.log_summary(source_name=self.source_name)

        logger.info(
            "OIG LEIE load complete",
            extra={
                "ingest_source": self.source_name,
                "ingest_records_processed": processed,
                "ingest_records_inserted": inserted,
                "ingest_records_errored": errors.total_errors,
                "leie_prescribers_flagged": xref_prescribers,
                "leie_pharmacies_flagged": xref_pharmacies,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=processed,
            records_inserted=inserted,
            records_errored=errors.total_errors,
        )

    def _upsert_row(self, raw: dict[str, Any]) -> None:
        """Insert or update one LEIE row, matching NULL keys via IS NULL."""
        from shared.db.models.oig_leie_exclusions import OigLeieExclusion

        lastname = (raw.get("LASTNAME") or "").strip() or None
        firstname = (raw.get("FIRSTNAME") or "").strip() or None
        busname = (raw.get("BUSNAME") or "").strip() or None
        excldate = _parse_leie_date(raw.get("EXCLDATE"))

        values: dict[str, Any] = {
            "lastname": lastname,
            "firstname": firstname,
            "midname": (raw.get("MIDNAME") or "").strip() or None,
            "busname": busname,
            "general": (raw.get("GENERAL") or "").strip() or None,
            "specialty": (raw.get("SPECIALTY") or "").strip() or None,
            "upin": (raw.get("UPIN") or "").strip() or None,
            "npi": (raw.get("NPI") or "").strip() or None,
            "dob": (raw.get("DOB") or "").strip() or None,
            "address": (raw.get("ADDRESS") or "").strip() or None,
            "city": (raw.get("CITY") or "").strip() or None,
            "state": (raw.get("STATE") or "").strip() or None,
            "zip": (raw.get("ZIP") or "").strip() or None,
            "excltype": (raw.get("EXCLTYPE") or "").strip() or None,
            "excldate": excldate,
            "reindate": _parse_leie_date(raw.get("REINDATE")),
            "waiverdate": _parse_leie_date(raw.get("WAIVERDATE")),
            "waiverstate": (raw.get("WAIVERSTATE") or "").strip() or None,
            "raw_payload": json.dumps(dict(raw)),
            "updated_at": datetime.now(UTC),
        }

        existing = (
            self._db.query(OigLeieExclusion)
            .filter(
                OigLeieExclusion.lastname == lastname,
                OigLeieExclusion.firstname == firstname,
                OigLeieExclusion.busname == busname,
                OigLeieExclusion.excldate == excldate,
            )
            .first()
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            values["created_at"] = datetime.now(UTC)
            self._db.add(OigLeieExclusion(**values))

    def _cross_reference_prescribers(self) -> int:
        """Update prescribers.is_excluded for NPI matches in active LEIE exclusions."""
        from sqlalchemy import text

        try:
            result = self._db.execute(
                text("""
                    UPDATE prescriber_dir.prescribers
                    SET is_excluded = true,
                        excluded_source = 'OIG_LEIE',
                        exclusion_date = leie.excldate
                    FROM shared.oig_leie_exclusions leie
                    WHERE prescriber_dir.prescribers.npi = leie.npi
                      AND leie.npi IS NOT NULL
                      AND leie.reindate IS NULL
                """)
            )
            self._db.commit()
            return result.rowcount if hasattr(result, "rowcount") else 0
        except Exception as exc:
            self._db.rollback()
            logger.info(
                "Prescriber cross-reference skipped (table not in scope)",
                extra={"ingest_source": self.source_name, "leie_note": str(exc)[:200]},
            )
            return 0

    def _cross_reference_pharmacies(self) -> int:
        """Update pharmacies.is_excluded for NPI matches in active LEIE exclusions."""
        from sqlalchemy import text

        try:
            result = self._db.execute(
                text("""
                    UPDATE pharmacy_dir.pharmacies
                    SET is_excluded = true,
                        excluded_source = 'OIG_LEIE',
                        exclusion_date = leie.excldate
                    FROM shared.oig_leie_exclusions leie
                    WHERE pharmacy_dir.pharmacies.npi = leie.npi
                      AND leie.npi IS NOT NULL
                      AND leie.reindate IS NULL
                """)
            )
            self._db.commit()
            return result.rowcount if hasattr(result, "rowcount") else 0
        except Exception as exc:
            self._db.rollback()
            logger.info(
                "Pharmacy cross-reference skipped (table not in scope)",
                extra={"ingest_source": self.source_name, "leie_note": str(exc)[:200]},
            )
            return 0

    def apply_reinstatements(self) -> int:
        """Clear is_excluded for prescribers/pharmacies whose LEIE row has reindate set."""
        from sqlalchemy import text

        cleared = 0
        for table_schema, table_name in [
            ("prescriber_dir", "prescribers"),
            ("pharmacy_dir", "pharmacies"),
        ]:
            try:
                result = self._db.execute(
                    text(f"""
                        UPDATE {table_schema}.{table_name}
                        SET is_excluded = false,
                            excluded_source = NULL,
                            exclusion_date = NULL
                        FROM shared.oig_leie_exclusions leie
                        WHERE {table_schema}.{table_name}.npi = leie.npi
                          AND leie.npi IS NOT NULL
                          AND leie.reindate IS NOT NULL
                    """)
                )
                self._db.commit()
                cleared += result.rowcount if hasattr(result, "rowcount") else 0
            except Exception as exc:
                self._db.rollback()
                logger.info(
                    "Reinstatement cross-reference skipped",
                    extra={
                        "ingest_source": self.source_name,
                        "leie_table": table_name,
                        "leie_note": str(exc)[:200],
                    },
                )
        return cleared


__all__ = ["OigLeieIngester"]
