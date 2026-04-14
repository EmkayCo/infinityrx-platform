"""DEA Registrations DataSourceIngester.

The DEA bulk registrations file requires an NTIS subscription or data-use
agreement and is typically unavailable for automated download. This ingester:

1. Attempts download from the configured DEA_BULK_FILE_URL env var.
2. If the URL is not configured or the download returns a non-200 response,
   logs INFO (not ERROR) and returns status=skipped_unchanged.

The DEA check digit validator in shared.utils.dea_validator is ALWAYS active
for inline DEA number validation, regardless of bulk file availability.

LESSON-004: \\A...\\Z anchors on all regex.
LESSON-005: log extra keys prefixed with dea_ or ingest_.
LESSON-011: Global reference table — no TenantScopedMixin.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.downloader import download_to_file
from shared.data_ingestion.field_registry import register_field

logger = logging.getLogger(__name__)

_DEA_BULK_FILE_URL_ENV = "DEA_BULK_FILE_URL"
_MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024  # 200 MB
_CACHE_DIR = Path("/tmp/ifx_ingest/dea_registrations")
_BATCH_SIZE = 1000

_SOURCE = "dea_registrations"
_SOURCE_FILE = "dea_registrations.csv"

# Field registry — declare all DEA → prescriber_dir.dea_registrations mappings
for _col, _src_col, _desc in [
    ("dea_number", "DEA_NUMBER", "9-character DEA registration number (PK)"),
    ("registrant_name", "REGISTRANT_NAME", "Full name of registrant"),
    ("address", "ADDRESS", "Street address"),
    ("city", "CITY", "City"),
    ("state", "STATE", "State abbreviation"),
    ("zip", "ZIP", "ZIP code"),
    ("business_activity", "BUSINESS_ACTIVITY", "Registrant type: Practitioner/Pharmacy/Distributor/etc."),
    ("drug_schedules_authorized", "DRUG_SCHEDULES", "Controlled substance schedules authorized (JSON list)"),
    ("expiration_date", "EXPIRATION_DATE", "Registration expiration date"),
    ("registration_status", "REGISTRATION_STATUS", "Active/Expired/Revoked/Surrendered"),
    ("npi", "NPI", "NPI cross-reference (nullable)"),
]:
    register_field(
        source=_SOURCE,
        table="prescriber_dir.dea_registrations",
        column=_col,
        description=_desc,
        source_file=_SOURCE_FILE,
        source_position=_src_col,
        data_type="str",
    )


def _parse_dea_date(raw: str | None) -> date | None:
    """Parse DEA date fields."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in ("%Y%m%d", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


class DeaRegistrationsIngester(DataSourceIngester):
    """DEA bulk registrations ingester.

    When bulk file is unavailable (typical), returns skipped_unchanged.
    The DEA validator in shared.utils.dea_validator remains active for
    inline checks regardless of bulk file availability.
    """

    source_name = "dea_registrations"

    async def download(self) -> Path:
        """Attempt to download DEA bulk file. Raises FileNotFoundError if unavailable."""
        url = os.environ.get(_DEA_BULK_FILE_URL_ENV, "").strip()
        if not url:
            raise _DeaBulkFileUnavailableError(
                "DEA_BULK_FILE_URL not configured — bulk file unavailable; "
                "validator-only mode active"
            )

        logger.info(
            "Attempting DEA bulk file download",
            extra={"ingest_source": self.source_name, "dea_url": url},
        )
        try:
            path = await download_to_file(
                url,
                _CACHE_DIR,
                max_bytes=_MAX_DOWNLOAD_BYTES,
                timeout_seconds=300.0,
            )
            return path
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403, 404):
                raise _DeaBulkFileUnavailableError(
                    f"DEA bulk file not accessible (HTTP {exc.response.status_code}) "
                    "— validator-only mode active"
                ) from exc
            raise

    def parse(self, file_path: Path) -> Iterator[dict[str, Any]]:
        """Stream-parse DEA CSV rows."""
        with file_path.open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                yield dict(row)

    async def load(self, records: Iterator[dict[str, Any]]) -> IngestionResult:
        """Batch-upsert DEA records; then run NPI cross-reference update."""
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
                        "DEA row upsert failed",
                        extra={
                            "ingest_source": self.source_name,
                            "dea_error": str(exc)[:200],
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

        xref_count = self._cross_reference_prescribers()
        logger.info(
            "DEA registrations cross-reference complete",
            extra={"dea_prescribers_updated": xref_count},
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
        """Insert or update one DEA row. Returns 'inserted' or 'updated'."""
        try:
            from src.models.compliance_tables import DeaRegistration  # type: ignore[import]
        except ImportError:
            import sys
            from pathlib import Path as _Path
            _module_root = _Path(__file__).resolve().parents[3] / "modules" / "prescriber-directory"
            if str(_module_root) not in sys.path:
                sys.path.insert(0, str(_module_root))
            from src.models.compliance_tables import DeaRegistration  # type: ignore[import]

        dea_number = (raw.get("DEA_NUMBER") or raw.get("dea_number") or "").strip()
        if not dea_number:
            raise ValueError("DEA_NUMBER missing in row")

        schedules_raw = raw.get("DRUG_SCHEDULES") or raw.get("drug_schedules_authorized") or ""
        if isinstance(schedules_raw, str) and schedules_raw:
            schedules = [s.strip() for s in schedules_raw.split(",") if s.strip()]
        elif isinstance(schedules_raw, list):
            schedules = schedules_raw
        else:
            schedules = []

        raw_payload = json.dumps({k: v for k, v in raw.items()})

        values: dict[str, Any] = {
            "registrant_name": (raw.get("REGISTRANT_NAME") or "").strip() or None,
            "address": (raw.get("ADDRESS") or "").strip() or None,
            "city": (raw.get("CITY") or "").strip() or None,
            "state": (raw.get("STATE") or "").strip() or None,
            "zip": (raw.get("ZIP") or "").strip() or None,
            "business_activity": (raw.get("BUSINESS_ACTIVITY") or "").strip() or None,
            "drug_schedules_authorized": schedules if schedules else None,
            "expiration_date": _parse_dea_date(raw.get("EXPIRATION_DATE")),
            "registration_status": (raw.get("REGISTRATION_STATUS") or "").strip() or None,
            "npi": (raw.get("NPI") or "").strip() or None,
            "raw_payload": raw_payload,
            "updated_at": datetime.now(UTC),
        }

        existing = self._db.get(DeaRegistration, dea_number)
        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
            return "updated"
        else:
            values["dea_number"] = dea_number
            values["created_at"] = datetime.now(UTC)
            obj = DeaRegistration(**values)
            self._db.add(obj)
            return "inserted"

    def _cross_reference_prescribers(self) -> int:
        """UPDATE prescribers DEA columns from dea_registrations WHERE npi matches."""
        from sqlalchemy import text

        try:
            result = self._db.execute(
                text("""
                    UPDATE prescriber_dir.prescribers p
                    SET dea_number = d.dea_number,
                        dea_status = d.registration_status,
                        dea_expiration_date = d.expiration_date,
                        dea_schedules = d.drug_schedules_authorized
                    FROM prescriber_dir.dea_registrations d
                    WHERE p.npi = d.npi
                      AND d.npi IS NOT NULL
                """)
            )
            self._db.commit()
            return result.rowcount if hasattr(result, "rowcount") else 0
        except Exception as exc:
            self._db.rollback()
            logger.info(
                "DEA prescriber cross-reference skipped",
                extra={"ingest_source": self.source_name, "dea_note": str(exc)[:200]},
            )
            return 0

    async def run(self, *, run_type: str = "auto_scheduled", triggered_by: Any = None) -> IngestionResult:
        """Override run() to handle graceful skipping when bulk file unavailable.

        Checks configuration before starting the base class run tracking machinery
        so that an expected-unavailable condition is not recorded as 'failed'.
        """
        import time
        wall_start = time.monotonic()

        url = os.environ.get(_DEA_BULK_FILE_URL_ENV, "").strip()
        if not url:
            msg = (
                "DEA_BULK_FILE_URL not configured — bulk file unavailable; "
                "validator-only mode active"
            )
            logger.info(
                "DEA bulk file not accessible — validator-only mode",
                extra={"ingest_source": self.source_name, "dea_note": msg},
            )
            return IngestionResult(
                source=self.source_name,
                status="skipped_unchanged",
                error_message=msg,
                duration_seconds=time.monotonic() - wall_start,
            )

        return await super().run(run_type=run_type, triggered_by=triggered_by)


class _DeaBulkFileUnavailableError(RuntimeError):
    """Raised when the DEA bulk file is not accessible — not a failure condition."""


__all__ = ["DeaRegistrationsIngester"]
