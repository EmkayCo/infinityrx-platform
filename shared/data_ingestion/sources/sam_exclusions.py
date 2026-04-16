"""SAM.gov Exclusions DataSourceIngester.

Downloads the SAM.gov public exclusions list via the SAM.gov API and loads
into shared.sam_exclusions. Cross-references prescribers and pharmacies by NPI.

Requires SAM_API_KEY environment variable. If not configured, returns status=failed
with a clear error message.

API: https://api.sam.gov/entity-information/v4/exclusions?api_key={SAM_API_KEY}
Pagination: &size=1000&page=N (zero-indexed). Follow ``links.nextLink`` until absent.

LOADER-BUG-07a history:
  - 2026-04-15: hardcoded v1 endpoint /exclusions/v1/ returned 404.
    Changed to /entity-information/v3/exclusions but never end-to-end
    tested. v3 also 404s.
  - 2026-04-16 (this commit): wave 7 end-to-end verification confirmed
    the working endpoint is /entity-information/v4/exclusions, which
    has a completely different nested response shape. Rewrote the
    download paginator (size/page, nextLink-driven) and added
    ``_flatten_v4_record`` to project the nested JSON into the flat
    dict shape the upsert path expects.

v4 response shape:
  {"totalRecords": N,
   "excludedEntity": [
     {"exclusionDetails": {"classificationType", "exclusionType",
                           "exclusionProgram", "excludingAgencyName"},
      "exclusionIdentification": {"entityName", "firstName", "lastName",
                                   "npi", "ueiSAM", "cageCode"},
      "exclusionActions": {"listOfActions": [{"activateDate",
                                               "terminationDate",
                                               "recordStatus"}]},
      "exclusionPrimaryAddress": {"addressLine1", "city",
                                   "stateOrProvinceCode", "zipCode",
                                   "countryCode"},
      "exclusionOtherInformation": {"ctCode", "additionalComments"}},
     ...],
   "links": {"selfLink", "nextLink"}}

v4 dates are MM-DD-YYYY (e.g. "03-09-2026"), not ISO.

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
_SAM_API_BASE_URL = "https://api.sam.gov/entity-information/v4/exclusions"
_SAM_PAGE_SIZE = 1000  # API caps at 1000 per page
_MAX_PAGES = 10_000  # safety cap

_CACHE_DIR = Path("data/reference/sam_exclusions")
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
    """Parse SAM.gov date fields.

    v4 uses MM-DD-YYYY (``03-09-2026``). Earlier endpoints returned
    ISO ``YYYY-MM-DD`` — both accepted for forward/backward compat.
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _flatten_v4_record(entity: dict[str, Any]) -> dict[str, Any]:
    """Project a v4 ``excludedEntity`` record into the flat shape expected
    by ``_upsert_row``.

    v4 nests fields under ``exclusionDetails`` / ``exclusionIdentification`` /
    ``exclusionActions.listOfActions[0]`` / ``exclusionPrimaryAddress`` /
    ``exclusionOtherInformation``. We use the first ``listOfActions`` entry
    for the active/termination dates (the record structure allows multiple
    actions per exclusion; the first is the most recent / currently-active
    one in every sample we've seen).

    Raises ValueError if the entity is missing ``exclusionDetails`` — the
    minimal required top-level shape. This lets the Wave 8 load() loop
    log-and-continue on malformed records rather than inserting a
    mostly-empty row.
    """
    if not isinstance(entity, dict) or "exclusionDetails" not in entity:
        raise ValueError(
            f"missing exclusionDetails; top-level keys: "
            f"{list(entity) if isinstance(entity, dict) else type(entity).__name__}"
        )

    details = entity.get("exclusionDetails") or {}
    ident = entity.get("exclusionIdentification") or {}
    actions = (entity.get("exclusionActions") or {}).get("listOfActions") or []
    primary_action = actions[0] if actions else {}
    address = entity.get("exclusionPrimaryAddress") or {}
    other = entity.get("exclusionOtherInformation") or {}

    # Name: use entityName if set, else concatenate first/middle/last.
    name = (ident.get("entityName") or "").strip()
    if not name:
        parts = [
            (ident.get("firstName") or "").strip(),
            (ident.get("middleName") or "").strip(),
            (ident.get("lastName") or "").strip(),
        ]
        name = " ".join(p for p in parts if p).strip() or None

    return {
        "classificationType": details.get("classificationType"),
        "name": name,
        "exclusionType": details.get("exclusionType"),
        "exclusionProgram": details.get("exclusionProgram"),
        "agency": details.get("excludingAgencyName"),
        "npi": ident.get("npi"),
        "ueiSAM": ident.get("ueiSAM"),
        "cageCode": ident.get("cageCode"),
        "dunsNumber": ident.get("dnbOpenData"),
        "activationDate": primary_action.get("activateDate"),
        "terminationDate": primary_action.get("terminationDate"),
        "updateDate": primary_action.get("updateDate"),
        "addressLine1": address.get("addressLine1"),
        "addressLine2": address.get("addressLine2"),
        "city": address.get("city"),
        "stateOrProvince": address.get("stateOrProvinceCode"),
        "zipCode": address.get("zipCode"),
        "country": address.get("countryCode"),
        "ctCode": other.get("ctCode"),
        "additionalComments": other.get("additionalComments"),
        "affiliations": (other.get("references") or {}).get("referencesList"),
    }


# ---------------------------------------------------------------------------
# psycopg2-based upsert path (Wave 8)
#
# The Wave 7 SamExclusionsIngester.load() routes records through a SQLAlchemy
# ORM upsert (self._upsert_row) that handles the NULL-containing natural key
# correctly via SQLAlchemy's `== None → IS NULL` comparator. Wave 8's extract
# driver uses raw psycopg2 connections instead and needs the same NULL-aware
# upsert at module scope. We mirror the ORM semantics with IS NOT DISTINCT
# FROM on the four natural-key columns.
# ---------------------------------------------------------------------------


def get_db_connection():
    """Return a new psycopg2 connection using DATABASE_URL_SYNC.

    Caller is responsible for commit/close (the Wave 8 load() uses it as a
    context manager, which psycopg2 Connection already supports).
    """
    import psycopg2  # local import so this module doesn't hard-depend on it

    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL_SYNC / DATABASE_URL not set — cannot connect to Postgres."
        )
    # psycopg2 doesn't understand SQLAlchemy-style driver prefixes.
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return psycopg2.connect(url)


_UPSERT_COLUMNS = (
    "classification_type",
    "name",
    "exclusion_type",
    "exclusion_program",
    "agency",
    "npi",
    "uei_sam",
    "cage_code",
    "duns_number",
    "active_date",
    "termination_date",
    "address_line_1",
    "address_line_2",
    "city",
    "state_province",
    "zip_postal_code",
    "country_code",
    "ct_code",
    "additional_comments",
    "affiliations",
    "raw_payload",
)


def _build_sam_values(flat: dict[str, Any]) -> dict[str, Any]:
    """Shape a flattened v4 record into the sam_exclusions column layout."""
    return {
        "classification_type": (flat.get("classificationType") or "").strip() or None,
        "name": (flat.get("name") or "").strip() or None,
        "exclusion_type": (flat.get("exclusionType") or "").strip() or None,
        "exclusion_program": (flat.get("exclusionProgram") or "").strip() or None,
        "agency": (flat.get("agency") or "").strip() or None,
        "npi": (flat.get("npi") or "").strip() or None,
        "uei_sam": (flat.get("ueiSAM") or "").strip() or None,
        "cage_code": (flat.get("cageCode") or "").strip() or None,
        "duns_number": (flat.get("dunsNumber") or "").strip() or None,
        "active_date": _parse_sam_date(flat.get("activationDate")),
        "termination_date": _parse_sam_date(flat.get("terminationDate")),
        "address_line_1": (flat.get("addressLine1") or "").strip() or None,
        "address_line_2": (flat.get("addressLine2") or "").strip() or None,
        "city": (flat.get("city") or "").strip() or None,
        "state_province": (flat.get("stateOrProvince") or "").strip() or None,
        "zip_postal_code": (flat.get("zipCode") or "").strip() or None,
        "country_code": (flat.get("country") or "").strip() or None,
        "ct_code": (flat.get("ctCode") or "").strip() or None,
        "additional_comments": (flat.get("additionalComments") or "").strip() or None,
        "affiliations": json.dumps(flat.get("affiliations")) if flat.get("affiliations") else None,
        "raw_payload": json.dumps(flat),
    }


def _upsert_row(conn: Any, flat: dict[str, Any]) -> None:
    """Upsert one SAM exclusion row via raw psycopg2.

    Uses ``IS NOT DISTINCT FROM`` on the natural-key lookup so rows with
    NULL in any of ``(classification_type, name, exclusion_type, active_date)``
    match correctly — SQL ``=`` treats NULL as distinct, which would
    duplicate ~30% of the SAM.gov dataset on every run. Mirrors the
    NULL-aware behaviour of SQLAlchemy's ORM ``== None → IS NULL``.
    """
    values = _build_sam_values(flat)
    now = datetime.now(UTC)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM shared.sam_exclusions
            WHERE classification_type IS NOT DISTINCT FROM %s
              AND name IS NOT DISTINCT FROM %s
              AND exclusion_type IS NOT DISTINCT FROM %s
              AND active_date IS NOT DISTINCT FROM %s
            LIMIT 1
            """,
            (
                values["classification_type"],
                values["name"],
                values["exclusion_type"],
                values["active_date"],
            ),
        )
        existing = cur.fetchone()

        update_cols = [c for c in _UPSERT_COLUMNS
                        if c not in ("classification_type", "name",
                                      "exclusion_type", "active_date")]

        if existing is not None:
            set_clause = ", ".join(f"{c} = %s" for c in update_cols) + ", updated_at = %s"
            cur.execute(
                f"UPDATE shared.sam_exclusions SET {set_clause} WHERE id = %s",
                [*(values[c] for c in update_cols), now, existing[0]],
            )
        else:
            col_list = ", ".join(_UPSERT_COLUMNS) + ", created_at, updated_at"
            placeholders = ", ".join(["%s"] * (len(_UPSERT_COLUMNS) + 2))
            cur.execute(
                f"INSERT INTO shared.sam_exclusions ({col_list}) VALUES ({placeholders})",
                [*(values[c] for c in _UPSERT_COLUMNS), now, now],
            )


class SamExclusionsIngester(DataSourceIngester):
    """Downloads SAM.gov exclusions via API and loads into shared.sam_exclusions.

    If SAM_API_KEY is not configured, returns status=failed with a clear
    error message rather than raising an exception.
    """

    source_name = "sam_exclusions"

    @staticmethod
    async def _get_with_retry(
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, Any],
        *,
        max_attempts: int = 6,
    ) -> httpx.Response:
        """GET with exponential-backoff retry on 429 / 5xx / transport errors.

        SAM.gov's v4 exclusions API rate-limits bursts — a size=1000 paginated
        crawl hits 429 after a handful of pages. Back off 2/4/8/16/32 seconds
        (capped) and honour ``Retry-After`` when the server sets it.
        """
        import asyncio

        attempt = 0
        while True:
            try:
                resp = await client.get(url, params=params)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt >= max_attempts - 1:
                    raise
                delay = min(2 ** attempt, 32)
                logger.warning(
                    "SAM.gov request transport error — retrying",
                    extra={
                        "ingest_source": "sam_exclusions",
                        "sam_error": str(exc)[:200],
                        "sam_attempt": attempt + 1,
                        "sam_delay_s": delay,
                    },
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue

            if resp.status_code not in (429, 500, 502, 503, 504):
                return resp
            if attempt >= max_attempts - 1:
                return resp  # let caller raise_for_status

            retry_after = resp.headers.get("Retry-After")
            try:
                delay = int(retry_after) if retry_after else min(2 ** attempt, 32)
            except ValueError:
                delay = min(2 ** attempt, 32)

            logger.warning(
                "SAM.gov rate-limit / transient error — retrying",
                extra={
                    "ingest_source": "sam_exclusions",
                    "sam_status": resp.status_code,
                    "sam_attempt": attempt + 1,
                    "sam_delay_s": delay,
                },
            )
            await asyncio.sleep(delay)
            attempt += 1

    async def download(self) -> Path:
        """Paginate the SAM.gov v4 exclusions API and write to a local JSONL.

        v4 pagination: ``size=N&page=I`` (I is zero-indexed). The response
        includes ``links.nextLink`` when another page is available; we
        loop until ``nextLink`` is absent or the page returns empty.
        Records are flattened to the shape ``_upsert_row`` expects.
        """
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
            "Downloading SAM.gov exclusions (v4)",
            extra={"ingest_source": self.source_name, "sam_url": _SAM_API_BASE_URL},
        )

        total_written = 0
        page = 0
        total_records: int | None = None

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            with out_path.open("w", encoding="utf-8") as fh:
                while page < _MAX_PAGES:
                    params = {
                        "api_key": api_key,
                        "size": _SAM_PAGE_SIZE,
                        "page": page,
                    }
                    resp = await self._get_with_retry(client, _SAM_API_BASE_URL, params)

                    if resp.status_code == 401:
                        raise _SamApiKeyMissingError(
                            "SAM.gov API returned 401 — check SAM_API_KEY validity. "
                            "Key may have expired or be invalid."
                        )
                    resp.raise_for_status()

                    data = resp.json()
                    if total_records is None:
                        total_records = int(data.get("totalRecords") or 0)

                    entities = data.get("excludedEntity") or []
                    if not entities:
                        break

                    for entity in entities:
                        flat = _flatten_v4_record(entity)
                        fh.write(json.dumps(flat) + "\n")
                        total_written += 1

                    logger.info(
                        "SAM.gov page fetched",
                        extra={
                            "ingest_source": self.source_name,
                            "sam_page": page,
                            "sam_records_so_far": total_written,
                            "sam_total_records": total_records,
                        },
                    )

                    # Stop when we've consumed all records, the page was
                    # short, or the API didn't offer a next link.
                    links = data.get("links") or {}
                    if (
                        (total_records and total_written >= total_records)
                        or len(entities) < _SAM_PAGE_SIZE
                        or not links.get("nextLink")
                    ):
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
            self._db.rollback()
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
                self._db.rollback()
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
