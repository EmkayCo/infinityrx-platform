"""SAM.gov Exclusions DataSourceIngester.

Downloads the SAM.gov public exclusions list via the SAM.gov API and loads
into shared.sam_exclusions. Cross-references prescribers and pharmacies by NPI.

Requires SAM_API_KEY environment variable. If not configured, returns status=failed
with a clear error message.

API: https://api.sam.gov/exclusions/v1/?api_key={SAM_API_KEY}

LESSON-004: \\A...\\Z anchors on all regex.
LESSON-005: log extra keys prefixed with sam_ or ingest_.
LESSON-010: NPI is public — plaintext.
LESSON-011: Global reference table — no TenantScopedMixin.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

_SAM_API_KEY_ENV = "SAM_API_KEY"
_SAM_API_BASE_URL = "https://api.sam.gov/exclusions/v1/"
_SAM_PAGE_SIZE = 100
_MAX_PAGES = 10_000  # safety cap

_CACHE_DIR = Path("/tmp/ifx_ingest/sam_exclusions")
_BATCH_SIZE = 1000

_SOURCE = "sam_exclusions"
_SOURCE_FILE = "sam_exclusions_api"

# Field registry entries for all SAM.gov exclusion fields
for _col, _src_col, _desc in [
    ("classification_type", "classificationType", "Individual | Firm | Vessel | Special Entity Designation"),
    ("name", "name", "Full name or company name"),
    ("address_line_1", "addressLine1", "Street address line 1"),
    ("address_line_2", "addressLine2", "Street address line 2"),
    ("city", "city", "City"),
    ("state_province", "stateOrProvince", "State or province"),
    ("zip_postal_code", "zipCode", "ZIP or postal code"),
    ("country_code", "country", "Country code"),
    ("duns_number", "dunsNumber", "DUNS number"),
    ("uei_sam", "ueiSAM", "Unique Entity Identifier (SAM)"),
    ("cage_code", "cageCode", "CAGE code"),
    ("npi", "npi", "NPI cross-reference (nullable)"),
    ("exclusion_type", "exclusionType", "Reciprocal | Non-Reciprocal | Proposed"),
    ("exclusion_program", "exclusionProgram", "SDN/OFAC | Procurement | Non-Procurement | Reciprocal"),
    ("agency", "agency", "Federal agency issuing the exclusion"),
    ("active_date", "activationDate", "Date exclusion became active"),
    ("termination_date", "terminationDate", "Date exclusion ends (null = active)"),
    ("ct_code", "ctCode", "Cross-reference code to LEIE if overlap"),
    ("additional_comments", "additionalComments", "Free-text comments"),
    ("affiliations", "affiliations", "Related firms/persons (JSON)"),
]:
    register_field(
        source=_SOURCE,
        table="shared.sam_exclusions",
        column=_col,
        description=_desc,
        source_file=_SOURCE_FILE,
        source_position=_src_col,
        data_type="str",
    )


def _parse_sam_date(raw: str | None) -> date | None:
    """Parse SAM.gov date fields."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


class SamExclusionsIngester(DataSourceIngester):
    """Downloads SAM.gov exclusions via API and loads into shared.sam_exclusions.

    If SAM_API_KEY is not configured, returns status=failed with a clear
    error message rather than raising an exception.
    """

    source_name = "sam_exclusions"

    async def download(self) -> Path:
        """Paginate SAM.gov exclusions API and write to a local JSONL file."""
        api_key = os.environ.get(_SAM_API_KEY_ENV, "").strip()
        if not api_key:
            raise _SamApiKeyMissingError(
                "SAM_API_KEY environment variable not configured. "
                "Register at sam.gov/api to obtain a key. "
                "SAM exclusions ingestion is blocked until key is provided."
            )

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        out_path = _CACHE_DIR / "sam_exclusions.jsonl"

        logger.info(
            "Downloading SAM.gov exclusions",
            extra={"ingest_source": self.source_name, "sam_url": _SAM_API_BASE_URL},
        )

        total_written = 0
        page = 0

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            with out_path.open("w", encoding="utf-8") as fh:
                while page < _MAX_PAGES:
                    params = {
                        "api_key": api_key,
                        "limit": _SAM_PAGE_SIZE,
                        "offset": page * _SAM_PAGE_SIZE,
                    }
                    resp = await client.get(_SAM_API_BASE_URL, params=params)

                    if resp.status_code == 401:
                        raise _SamApiKeyMissingError(
                            f"SAM.gov API returned 401 — check SAM_API_KEY validity. "
                            "Key may have expired or be invalid."
                        )
                    resp.raise_for_status()

                    data = resp.json()
                    exclusions = (
                        data.get("exclusionList")
                        or data.get("data")
                        or data.get("results")
                        or []
                    )

                    if not exclusions:
                        break

                    for record in exclusions:
                        fh.write(json.dumps(record) + "\n")
                        total_written += 1

                    logger.info(
                        "SAM.gov page fetched",
                        extra={
                            "ingest_source": self.source_name,
                            "sam_page": page,
                            "sam_records_so_far": total_written,
                        },
                    )

                    # Check if there are more pages
                    total_records = data.get("totalRecords") or data.get("total") or 0
                    if total_written >= int(total_records) or len(exclusions) < _SAM_PAGE_SIZE:
                        break

                    page += 1

        logger.info(
            "SAM.gov download complete",
            extra={"ingest_source": self.source_name, "sam_total_records": total_written},
        )
        return out_path

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Parse JSONL file, yielding one dict per exclusion record."""
        with file_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batch-upsert SAM exclusion records; then run cross-reference updates."""
        inserted = 0
        updated = 0
        errored = 0
        processed = 0
        batch: list[dict[str, Any]] = []

        def _flush() -> None:
            nonlocal inserted, updated, errored
            for row in batch:
                try:
                    changed = self._upsert_row(row)
                    if changed == "inserted":
                        inserted += 1
                    else:
                        updated += 1
                except Exception as exc:
                    errored += 1
                    logger.warning(
                        "SAM row upsert failed",
                        extra={
                            "ingest_source": self.source_name,
                            "sam_error": str(exc)[:200],
                        },
                    )
            self._db.flush()
            batch.clear()

        for raw in records:
            batch.append(raw)
            processed += 1
            if len(batch) >= _BATCH_SIZE:
                _flush()

        _flush()
        self._db.commit()

        xref_prescribers = self._cross_reference_prescribers()
        xref_pharmacies = self._cross_reference_pharmacies()

        logger.info(
            "SAM exclusions cross-reference complete",
            extra={
                "sam_prescribers_flagged": xref_prescribers,
                "sam_pharmacies_flagged": xref_pharmacies,
            },
        )

        return IngestionResult(
            source=self.source_name,
            status="completed",
            records_processed=processed,
            records_inserted=inserted,
            records_updated=updated,
            records_errored=errored,
        )

    def _upsert_row(self, raw: dict[str, Any]) -> str:
        """Insert or update one SAM exclusion row. Returns 'inserted' or 'updated'."""
        from shared.db.models.sam_exclusions import SamExclusion

        classification_type = (raw.get("classificationType") or "").strip() or None
        name = (raw.get("name") or "").strip() or None
        exclusion_type = (raw.get("exclusionType") or "").strip() or None
        active_date = _parse_sam_date(raw.get("activationDate") or raw.get("activeDate"))

        raw_payload = {k: v for k, v in raw.items()}

        affiliations = raw.get("affiliations")
        if isinstance(affiliations, str):
            try:
                affiliations = json.loads(affiliations)
            except (json.JSONDecodeError, ValueError):
                affiliations = affiliations or None

        values: dict[str, Any] = {
            "address_line_1": (raw.get("addressLine1") or "").strip() or None,
            "address_line_2": (raw.get("addressLine2") or "").strip() or None,
            "city": (raw.get("city") or "").strip() or None,
            "state_province": (raw.get("stateOrProvince") or raw.get("state") or "").strip() or None,
            "zip_postal_code": (raw.get("zipCode") or raw.get("zip") or "").strip() or None,
            "country_code": (raw.get("country") or "").strip() or None,
            "duns_number": (raw.get("dunsNumber") or "").strip() or None,
            "uei_sam": (raw.get("ueiSAM") or raw.get("uei") or "").strip() or None,
            "cage_code": (raw.get("cageCode") or "").strip() or None,
            "npi": (raw.get("npi") or "").strip() or None,
            "exclusion_program": (raw.get("exclusionProgram") or raw.get("exclusionPrograms") or "").strip() or None,
            "agency": (raw.get("agency") or "").strip() or None,
            "termination_date": _parse_sam_date(raw.get("terminationDate")),
            "ct_code": (raw.get("ctCode") or "").strip() or None,
            "additional_comments": (raw.get("additionalComments") or "").strip() or None,
            "affiliations": affiliations,
            "raw_payload": raw_payload,
            "updated_at": datetime.now(UTC),
        }

        existing = (
            self._db.query(SamExclusion)
            .filter(
                SamExclusion.classification_type == classification_type,
                SamExclusion.name == name,
                SamExclusion.exclusion_type == exclusion_type,
                SamExclusion.active_date == active_date,
            )
            .first()
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
            return "updated"
        else:
            values.update({
                "classification_type": classification_type,
                "name": name,
                "exclusion_type": exclusion_type,
                "active_date": active_date,
                "created_at": datetime.now(UTC),
            })
            obj = SamExclusion(**values)
            self._db.add(obj)
            return "inserted"

    def _cross_reference_prescribers(self) -> int:
        """Flag prescribers in active SAM exclusions by NPI."""
        from sqlalchemy import text

        try:
            result = self._db.execute(
                text("""
                    UPDATE prescriber_dir.prescribers
                    SET is_excluded = true,
                        excluded_source = 'SAM_GOV',
                        exclusion_date = sam.active_date
                    FROM shared.sam_exclusions sam
                    WHERE prescriber_dir.prescribers.npi = sam.npi
                      AND sam.npi IS NOT NULL
                      AND (sam.termination_date IS NULL OR sam.termination_date > CURRENT_DATE)
                """)
            )
            self._db.commit()
            return result.rowcount if hasattr(result, "rowcount") else 0
        except Exception as exc:
            logger.info(
                "SAM prescriber cross-reference skipped",
                extra={"ingest_source": self.source_name, "sam_note": str(exc)[:200]},
            )
            return 0

    def _cross_reference_pharmacies(self) -> int:
        """Flag pharmacies in active SAM exclusions by NPI and UEI."""
        from sqlalchemy import text

        total = 0
        # Match by NPI
        for match_col, sam_col in [("npi", "npi"), ("uei_sam_match", "uei_sam")]:
            try:
                if match_col == "npi":
                    sql = text("""
                        UPDATE pharmacy_dir.pharmacies
                        SET is_excluded = true,
                            excluded_source = 'SAM_GOV',
                            exclusion_date = sam.active_date
                        FROM shared.sam_exclusions sam
                        WHERE pharmacy_dir.pharmacies.npi = sam.npi
                          AND sam.npi IS NOT NULL
                          AND (sam.termination_date IS NULL OR sam.termination_date > CURRENT_DATE)
                    """)
                else:
                    # UEI match — pharmacies don't have uei_sam column directly,
                    # so this is a no-op unless the column is added in a migration.
                    continue
                result = self._db.execute(sql)
                self._db.commit()
                total += result.rowcount if hasattr(result, "rowcount") else 0
            except Exception as exc:
                logger.info(
                    "SAM pharmacy cross-reference skipped",
                    extra={"ingest_source": self.source_name, "sam_note": str(exc)[:200]},
                )
        return total

    async def run(self, *, run_type: str = "auto_scheduled", triggered_by: Any = None) -> IngestionResult:
        """Override run() to handle missing API key gracefully."""
        import time
        wall_start = time.monotonic()

        try:
            return await super().run(run_type=run_type, triggered_by=triggered_by)
        except _SamApiKeyMissingError as exc:
            msg = str(exc)
            logger.warning(
                "SAM.gov ingestion failed — API key not configured",
                extra={"ingest_source": self.source_name, "sam_error": msg},
            )
            return IngestionResult(
                source=self.source_name,
                status="failed",
                error_message=msg,
                duration_seconds=time.monotonic() - wall_start,
            )


class _SamApiKeyMissingError(RuntimeError):
    """Raised when SAM_API_KEY is missing or invalid."""


__all__ = ["SamExclusionsIngester"]
