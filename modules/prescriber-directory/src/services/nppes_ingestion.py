"""NPPES ingestion service — populates the satellite tables from a parsed CSV.

Writes to:
  - prescriber_dir.nppes_prescriber_details  (extended NPPES fields, 1 per NPI)
  - prescriber_dir.prescriber_addresses      (mailing + practice, up to 2 per NPI)
  - prescriber_dir.prescriber_taxonomies     (up to 15 exploded rows per NPI)
  - prescriber_dir.prescriber_identifiers    (up to 50 exploded rows per NPI)

Core ``prescriber_dir.prescribers`` upsert lives in ``nppes_upsert.py`` —
this service layers the satellites on top, called from
``shared.data_ingestion.sources.nppes`` after the core pass completes.

Wave-11 refactor: the four tables were previously written row-at-a-time via
``db.query().filter().delete()`` followed by ``db.add()`` per ORM instance —
~O(14M) DB round-trips for a 7M-row monthly baseline. Now they're batched
via the shared ``flush_upsert_batch`` (details, keyed on npi) and
``flush_scoped_replace_batch`` (addresses/taxonomies/identifiers, scoped
per npi with composite unique keys).

LESSON-010: NPI is public — plaintext throughout, do NOT encrypt.
LESSON-011: Global reference — no TenantScopedMixin on any table here.
LESSON-004: All regex uses re.fullmatch or \\A...\\Z anchors.
LESSON-005: log extra keys prefixed with svc_ to avoid LogRecord collisions.
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from shared.data_ingestion.batching import (
    ErrorAggregator,
    flush_scoped_replace_batch,
    flush_scoped_replace_batch_copy,
    flush_upsert_batch,
    flush_upsert_batch_copy,
)

from ..models.nppes_tables import (
    NppesPrescriberDetail,
    PrescriberAddress,
    PrescriberIdentifier,
    PrescriberTaxonomy,
)
from ..utils.validators import NpiValidationError, validate_npi

logger = logging.getLogger("prescriber-directory.nppes-ingestion")

# Regex — LESSON-004
_NPI_RE = re.compile(r"\A\d{10}\Z")

# NPPES V2 column counts
_MAX_TAXONOMIES = 15
_MAX_IDENTIFIERS = 50

# Number of NPIs processed before a full 4-table flush
_BATCH_SIZE = 1_000


# ────────────────────────────────────────────────────────────────────────────
# Date + value parsing
# ────────────────────────────────────────────────────────────────────────────

def _parse_date(value: str) -> "datetime | None":
    """Parse NPPES MM/DD/YYYY date string, returning None on empty/invalid."""
    from datetime import date as _date
    v = (value or "").strip()
    if not v:
        return None
    try:
        parts = v.split("/")
        if len(parts) == 3:
            return _date(int(parts[2]), int(parts[0]), int(parts[1]))  # type: ignore[return-value]
    except (ValueError, IndexError):
        pass
    return None


def _or_none(v: str | None) -> str | None:
    if not v:
        return None
    stripped = v.strip()
    return stripped if stripped else None


def _state_or_none(value: str | None) -> str | None:
    """Return a 2-char US state/territory code, or None for anything else.

    Mirrors nppes_parser._state_or_none (applied to the core prescribers
    table) — extended to the satellite address + taxonomy + identifier
    tables whose state columns are also VARCHAR(2). Foreign provider rows
    populate these with region names ("ONTARIO", "ENGLAND", "MAHARASHTRA,
    INDIA") that overflow the target column and fail the batch INSERT.
    Dropping them to NULL at parse time is strictly better than losing
    the whole batch.
    """
    v = (value or "").strip().upper()
    if len(v) == 2 and v.isalpha():
        return v
    return None


def _fit_or_none(value: str | None, max_len: int) -> str | None:
    """Return ``value`` if it fits within ``max_len`` characters, else None.

    Used for VARCHAR-constrained columns where the source occasionally
    overflows. NULL is preferred over truncation because a partial
    postal code / reason code is meaningless for downstream matching.
    """
    v = (value or "").strip()
    if not v or len(v) > max_len:
        return None
    return v


# ────────────────────────────────────────────────────────────────────────────
# Row → satellite ORM objects
# (Returning ORM objects preserves the _build_* API that existing tests
#  exercise directly. The flush path below converts to dicts at the boundary.)
# ────────────────────────────────────────────────────────────────────────────

def _build_detail(row: dict[str, str], now: datetime) -> NppesPrescriberDetail:
    """Map a raw NPPES CSV row to NppesPrescriberDetail."""
    return NppesPrescriberDetail(
        npi=row.get("NPI", "").strip(),
        entity_type_code=_fit_or_none(row.get("Entity Type Code", ""), 1),
        replacement_npi=_fit_or_none(row.get("Replacement NPI", ""), 10),
        ein=_or_none(row.get("Employer Identification Number (EIN)", "")),
        provider_last_name_legal=_or_none(row.get("Provider Last Name (Legal Name)", "")),
        provider_first_name=_or_none(row.get("Provider First Name", "")),
        provider_middle_name=_or_none(row.get("Provider Middle Name", "")),
        provider_name_prefix=_fit_or_none(row.get("Provider Name Prefix Text", ""), 10),
        provider_name_suffix=_fit_or_none(row.get("Provider Name Suffix Text", ""), 10),
        provider_credential_text=_or_none(row.get("Provider Credential Text", "")),
        provider_organization_name_legal=_or_none(
            row.get("Provider Organization Name (Legal Business Name)", "")
        ),
        provider_other_organization_name=_or_none(
            row.get("Provider Other Organization Name", "")
        ),
        provider_other_organization_name_type_code=_fit_or_none(
            row.get("Provider Other Organization Name Type Code", ""), 2
        ),
        provider_other_last_name=_or_none(row.get("Provider Other Last Name (former)", "")),
        provider_other_first_name=_or_none(row.get("Provider Other First Name", "")),
        provider_other_middle_name=_or_none(row.get("Provider Other Middle Name", "")),
        provider_other_name_prefix=_fit_or_none(row.get("Provider Other Name Prefix Text", ""), 10),
        provider_other_name_suffix=_fit_or_none(row.get("Provider Other Name Suffix Text", ""), 10),
        provider_other_credential_text=_or_none(row.get("Provider Other Credential Text", "")),
        provider_other_last_name_type_code=_fit_or_none(
            row.get("Provider Other Last Name Type Code", ""), 2
        ),
        provider_enumeration_date=_parse_date(row.get("Provider Enumeration Date", "")),  # type: ignore[arg-type]
        last_update_date=_parse_date(row.get("Last Update Date", "")),  # type: ignore[arg-type]
        npi_deactivation_reason_code=_fit_or_none(row.get("NPI Deactivation Reason Code", ""), 2),
        npi_deactivation_date=_parse_date(row.get("NPI Deactivation Date", "")),  # type: ignore[arg-type]
        npi_reactivation_date=_parse_date(row.get("NPI Reactivation Date", "")),  # type: ignore[arg-type]
        certification_date=_parse_date(row.get("Certification Date", "")),  # type: ignore[arg-type]
        provider_gender_code=_fit_or_none(row.get("Provider Gender Code", ""), 1),
        is_sole_proprietor=_fit_or_none(row.get("Is Sole Proprietor", ""), 1),
        is_organization_subpart=_fit_or_none(row.get("Is Organization Subpart", ""), 1),
        parent_organization_lbn=_or_none(
            row.get("Parent Organization Legal Business Name", "")
        ),
        parent_organization_tin=_or_none(row.get("Parent Organization TIN", "")),
        authorized_official_last_name=_or_none(
            row.get("Authorized Official Last Name", "")
        ),
        authorized_official_first_name=_or_none(
            row.get("Authorized Official First Name", "")
        ),
        authorized_official_middle_name=_or_none(
            row.get("Authorized Official Middle Name", "")
        ),
        authorized_official_title_or_position=_or_none(
            row.get("Authorized Official Title or Position", "")
        ),
        authorized_official_telephone_number=_or_none(
            row.get("Authorized Official Telephone Number", "")
        ),
        authorized_official_credential=_or_none(
            row.get("Authorized Official Credential", "")
        ),
        authorized_official_name_prefix=_fit_or_none(
            row.get("Authorized Official Name Prefix Text", ""), 10
        ),
        authorized_official_name_suffix=_fit_or_none(
            row.get("Authorized Official Name Suffix Text", ""), 10
        ),
        nppes_loaded_at=now,
    )


def _build_addresses(npi: str, row: dict[str, str], now: datetime) -> list[PrescriberAddress]:
    """Extract mailing and practice addresses; returns 0, 1, or 2 rows."""
    addresses = []

    ml1 = _or_none(row.get("Provider First Line Business Mailing Address", ""))
    if ml1:
        addresses.append(
            PrescriberAddress(
                npi=npi,
                address_type="mailing",
                line_1=ml1,
                line_2=_or_none(row.get("Provider Second Line Business Mailing Address", "")),
                city=_or_none(row.get("Provider Business Mailing Address City Name", "")),
                state=_state_or_none(row.get("Provider Business Mailing Address State Name", "")),
                postal_code=_fit_or_none(
                    row.get("Provider Business Mailing Address Postal Code", ""), 10
                ),
                country_code=_fit_or_none(
                    row.get("Provider Business Mailing Address Country Code (If outside U.S.)", ""), 3
                ),
                telephone_number=_or_none(
                    row.get("Provider Business Mailing Address Telephone Number", "")
                ),
                fax_number=_or_none(
                    row.get("Provider Business Mailing Address Fax Number", "")
                ),
                updated_at=now,
            )
        )

    pl1 = _or_none(
        row.get("Provider First Line Business Practice Location Address", "")
    )
    if pl1:
        addresses.append(
            PrescriberAddress(
                npi=npi,
                address_type="practice",
                line_1=pl1,
                line_2=_or_none(
                    row.get("Provider Second Line Business Practice Location Address", "")
                ),
                city=_or_none(
                    row.get("Provider Business Practice Location Address City Name", "")
                ),
                state=_state_or_none(
                    row.get("Provider Business Practice Location Address State Name", "")
                ),
                postal_code=_fit_or_none(
                    row.get("Provider Business Practice Location Address Postal Code", ""), 10
                ),
                country_code=_fit_or_none(
                    row.get(
                        "Provider Business Practice Location Address Country Code (If outside U.S.)",
                        "",
                    ),
                    3,
                ),
                telephone_number=_or_none(
                    row.get("Provider Business Practice Location Address Telephone Number", "")
                ),
                fax_number=_or_none(
                    row.get("Provider Business Practice Location Address Fax Number", "")
                ),
                updated_at=now,
            )
        )

    return addresses


def _build_taxonomies(npi: str, row: dict[str, str], now: datetime) -> list[PrescriberTaxonomy]:
    """Explode taxonomy slots _1.._15; stop at first empty taxonomy code."""
    taxonomies = []
    for i in range(1, _MAX_TAXONOMIES + 1):
        code = _or_none(row.get(f"Healthcare Provider Taxonomy Code_{i}", ""))
        if not code:
            break
        taxonomies.append(
            PrescriberTaxonomy(
                npi=npi,
                sequence=i,
                taxonomy_code=code,
                license_number=_or_none(row.get(f"Provider License Number_{i}", "")),
                license_state_code=_state_or_none(
                    row.get(f"Provider License Number State Code_{i}", "")
                ),
                is_primary=_fit_or_none(
                    row.get(f"Healthcare Provider Primary Taxonomy Switch_{i}", ""), 1
                ),
                taxonomy_group=_or_none(
                    row.get(f"Healthcare Provider Taxonomy Group_{i}", "")
                ),
                updated_at=now,
            )
        )
    return taxonomies


def _build_identifiers(npi: str, row: dict[str, str], now: datetime) -> list[PrescriberIdentifier]:
    """Explode other-provider identifier slots _1.._50; stop at first empty."""
    identifiers = []
    for i in range(1, _MAX_IDENTIFIERS + 1):
        ident = _or_none(row.get(f"Other Provider Identifier_{i}", ""))
        if not ident:
            break
        identifiers.append(
            PrescriberIdentifier(
                npi=npi,
                sequence=i,
                identifier=ident,
                identifier_type_code=_fit_or_none(
                    row.get(f"Other Provider Identifier Type Code_{i}", ""), 2
                ),
                identifier_state=_state_or_none(
                    row.get(f"Other Provider Identifier State_{i}", "")
                ),
                identifier_issuer=_or_none(
                    row.get(f"Other Provider Identifier Issuer_{i}", "")
                ),
                updated_at=now,
            )
        )
    return identifiers


def _orm_to_dict(obj: Any) -> dict[str, Any]:
    """Extract column values from an ORM instance to a plain dict.

    Excludes the auto-increment ``id`` column so flush_* primitives let the
    DB assign new values on insert.
    """
    return {
        c.name: getattr(obj, c.name)
        for c in obj.__table__.columns
        if c.name != "id"
    }


# ────────────────────────────────────────────────────────────────────────────
# Pharmacy supplement (unchanged from pre-Wave-11 — already uses ON CONFLICT)
# ────────────────────────────────────────────────────────────────────────────

def _pharmacy_table_exists(db: Session) -> bool:
    """Check if ``pharmacy_directory.pharmacies`` exists.

    Uses Postgres's ``to_regclass`` (returns NULL for missing tables)
    so the check itself never aborts the current transaction. Under
    SQLite tests ``to_regclass`` doesn't exist and the Exception path
    returns False — which is correct, since the test SQLite schema
    never contains T2's tables anyway.
    """
    from sqlalchemy import text

    try:
        result = db.execute(
            text("SELECT to_regclass('pharmacy_directory.pharmacies')")
        ).scalar()
        return result is not None
    except Exception:
        # SQLite or any dialect without to_regclass — treat as "not available"
        db.rollback()
        return False


def _maybe_supplement_pharmacy(
    db: Session,
    npi: str,
    entity_type_code: str | None,
    taxonomies: list[PrescriberTaxonomy],
) -> bool:
    """Insert/upsert into pharmacy_directory.pharmacies if conditions met.

    Callers MUST check ``_pharmacy_table_exists(db)`` before invoking this
    in a loop — we do not re-check per row. If the table is missing the
    caller should skip calling this function entirely; otherwise the raw
    SQL would abort the enclosing transaction.

    Conditions:
      - entity_type_code == "2" (organization)
      - at least one taxonomy code starts with "333" (pharmacy taxonomy)
    """
    if entity_type_code != "2":
        return False
    pharmacy_tax = [t for t in taxonomies if t.taxonomy_code and t.taxonomy_code.startswith("333")]
    if not pharmacy_tax:
        return False

    from sqlalchemy import text

    primary_tax = next((t for t in pharmacy_tax if t.is_primary == "Y"), pharmacy_tax[0])
    db.execute(
        text(
            """
            INSERT INTO pharmacy_directory.pharmacies
                (npi, pharmacy_name, taxonomy_code, npi_source, created_at, updated_at)
            VALUES
                (:npi, :name, :taxonomy_code, 'nppes', NOW(), NOW())
            ON CONFLICT (npi) DO UPDATE SET
                taxonomy_code = EXCLUDED.taxonomy_code,
                updated_at    = NOW()
            """
        ),
        {
            "npi": npi,
            "name": None,
            "taxonomy_code": primary_tax.taxonomy_code,
        },
    )
    return True


# ────────────────────────────────────────────────────────────────────────────
# Public entry point
# ────────────────────────────────────────────────────────────────────────────

class NppesIngestionStats:
    """Running totals from a single ingestion pass."""

    def __init__(self) -> None:
        self.individuals: int = 0
        self.organizations: int = 0
        self.pharmacy_supplements: int = 0
        self.total_addresses: int = 0
        self.total_taxonomies: int = 0
        self.total_identifiers: int = 0
        self.records_errored: int = 0
        self.records_skipped: int = 0

    @property
    def total_prescribers(self) -> int:
        return self.individuals + self.organizations


def load_nppes_satellite_tables(
    db: Session,
    csv_path: Path,
    *,
    batch_size: int = _BATCH_SIZE,
    progress_every: int = 10_000,
    use_copy: bool = True,
) -> NppesIngestionStats:
    """Stream-parse a NPPES CSV and populate the satellite tables.

    Second-pass pipeline, run after the core ``prescribers`` upsert. Populates
    nppes_prescriber_details, prescriber_addresses, prescriber_taxonomies,
    prescriber_identifiers; attempts a pharmacy supplement for
    entity_type=2 + taxonomy 333*.

    Batching: up to ``batch_size`` NPIs worth of rows are buffered per table,
    then flushed together via the shared flush primitives. DB round-trip count
    drops from O(4 × N) to O(4 × N / batch_size).

    Parameters
    ----------
    db:
        Synchronous SQLAlchemy Session. Must NOT be tenant-scoped (LESSON-011).
    csv_path:
        Path to the extracted NPPES CSV file.
    batch_size:
        Number of NPIs to buffer before flushing all four tables.
    progress_every:
        Log a progress line every this many rows.
    use_copy:
        When True (default), route each satellite flush through the COPY-
        staging primitives (``flush_upsert_batch_copy`` /
        ``flush_scoped_replace_batch_copy``) — 3-10x faster than the VALUES
        path for the 30M-row monthly satellite pass. On non-PostgreSQL
        dialects (SQLite tests) the COPY primitives transparently fall back
        to VALUES, so the flag has no visible effect there. Set False to
        force the VALUES path even on Postgres (bench comparisons only).

    Returns
    -------
    NppesIngestionStats
    """
    stats = NppesIngestionStats()
    errors = ErrorAggregator()
    source_name = "nppes_satellite"
    now = datetime.now(UTC)
    row_count = 0

    # Dispatch to COPY or VALUES primitives for every flush in this run.
    _upsert_fn = flush_upsert_batch_copy if use_copy else flush_upsert_batch
    _replace_fn = (
        flush_scoped_replace_batch_copy if use_copy else flush_scoped_replace_batch
    )

    # Probe once — if T2's pharmacy table doesn't exist we skip the
    # supplement path entirely. Checking per-row would either pollute
    # the transaction (plain try/except) or force SAVEPOINT nesting
    # (incompatible with test-fixture SAVEPOINT isolation).
    pharmacy_available = _pharmacy_table_exists(db)
    if not pharmacy_available:
        logger.info(
            "nppes_pharmacy_supplement_disabled",
            extra={
                "svc_source": source_name,
                "svc_note": "pharmacy_directory.pharmacies not present — pharmacy "
                            "supplement will activate once T2 migrations land",
            },
        )

    # Per-table buffers of row dicts
    pending_details: list[dict[str, Any]] = []
    pending_addresses: list[dict[str, Any]] = []
    pending_taxonomies: list[dict[str, Any]] = []
    pending_identifiers: list[dict[str, Any]] = []
    pending_npis = 0

    def _flush() -> None:
        """Flush all four satellite buffers via shared primitives."""
        nonlocal pending_details, pending_addresses, pending_taxonomies
        nonlocal pending_identifiers, pending_npis
        if pending_details:
            _upsert_fn(
                db,
                source_name=source_name,
                table=NppesPrescriberDetail.__table__,
                unique_key=["npi"],
                rows=pending_details,
                errors=errors,
            )
        if pending_addresses:
            _replace_fn(
                db,
                source_name=source_name,
                table=PrescriberAddress.__table__,
                scope_key=["npi"],
                unique_key=["npi", "address_type"],
                rows=pending_addresses,
                errors=errors,
            )
        if pending_taxonomies:
            _replace_fn(
                db,
                source_name=source_name,
                table=PrescriberTaxonomy.__table__,
                scope_key=["npi"],
                unique_key=["npi", "sequence"],
                rows=pending_taxonomies,
                errors=errors,
            )
        if pending_identifiers:
            _replace_fn(
                db,
                source_name=source_name,
                table=PrescriberIdentifier.__table__,
                scope_key=["npi"],
                unique_key=["npi", "sequence"],
                rows=pending_identifiers,
                errors=errors,
            )
        # Invalidate ORM identity map so tests reading via ORM see post-flush state
        db.expire_all()
        pending_details = []
        pending_addresses = []
        pending_taxonomies = []
        pending_identifiers = []
        pending_npis = 0

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row_count += 1
            npi = row.get("NPI", "").strip()

            # NPI validation — LESSON-004 regex + Luhn
            if not _NPI_RE.fullmatch(npi):
                stats.records_skipped += 1
                continue
            try:
                validate_npi(npi)
            except NpiValidationError as exc:
                errors.record("luhn", str(exc), raw_row={"npi_prefix": npi[:4]})
                continue

            try:
                entity_type_code = _or_none(row.get("Entity Type Code", ""))

                detail = _build_detail(row, now)
                addresses = _build_addresses(npi, row, now)
                taxonomies = _build_taxonomies(npi, row, now)
                identifiers = _build_identifiers(npi, row, now)

                pending_details.append(_orm_to_dict(detail))
                for addr in addresses:
                    pending_addresses.append(_orm_to_dict(addr))
                for tax in taxonomies:
                    pending_taxonomies.append(_orm_to_dict(tax))
                for ident in identifiers:
                    pending_identifiers.append(_orm_to_dict(ident))

                # Pharmacy supplement (raw SQL, per-row — acceptable since
                # only a small subset of orgs trigger it). Skipped entirely
                # when the target table isn't present.
                supplemented = (
                    _maybe_supplement_pharmacy(db, npi, entity_type_code, taxonomies)
                    if pharmacy_available
                    else False
                )

                if entity_type_code == "1":
                    stats.individuals += 1
                else:
                    stats.organizations += 1
                if supplemented:
                    stats.pharmacy_supplements += 1
                stats.total_addresses += len(addresses)
                stats.total_taxonomies += len(taxonomies)
                stats.total_identifiers += len(identifiers)

                pending_npis += 1
                if pending_npis >= batch_size:
                    _flush()

                if row_count % progress_every == 0:
                    logger.info(
                        "nppes_ingestion_progress",
                        extra={
                            "svc_rows_read": row_count,
                            "svc_prescribers": stats.total_prescribers,
                            "svc_taxonomies": stats.total_taxonomies,
                        },
                    )

            except Exception as exc:
                errors.record("row_build", str(exc), raw_row={"npi": npi})
                logger.warning(
                    "nppes_row_error",
                    extra={"svc_npi": npi[:10], "svc_error": str(exc)[:200]},
                )

    # Final flush
    if pending_npis > 0:
        _flush()

    # Propagate the canonical error tally from ErrorAggregator (which counts
    # both row-level validation + batch-flush failures) into stats.
    stats.records_errored = errors.total_errors

    errors.log_summary(source_name=source_name)

    logger.info(
        "nppes_satellite_load_complete",
        extra={
            "svc_individuals": stats.individuals,
            "svc_organizations": stats.organizations,
            "svc_pharmacy_supplements": stats.pharmacy_supplements,
            "svc_total_addresses": stats.total_addresses,
            "svc_total_taxonomies": stats.total_taxonomies,
            "svc_total_identifiers": stats.total_identifiers,
            "svc_records_errored": stats.records_errored,
        },
    )
    return stats


__all__ = ["NppesIngestionStats", "load_nppes_satellite_tables"]
