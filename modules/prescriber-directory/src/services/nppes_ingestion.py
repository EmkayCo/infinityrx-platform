"""NPPES ingestion service — full normalized load for prescriber-directory.

Extends the existing NppesParser / nppes_upsert pipeline to also populate:
  - prescriber_dir.nppes_prescriber_details  (extended NPPES fields)
  - prescriber_dir.prescriber_addresses      (mailing + practice, up to 2)
  - prescriber_dir.prescriber_taxonomies     (up to 15 exploded rows)
  - prescriber_dir.prescriber_identifiers    (up to 50 exploded rows)

The core Prescriber upsert remains in nppes_upsert.py. This service layers
the satellite tables on top, called from shared.data_ingestion.sources.nppes.

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
from typing import Any, Iterator

from sqlalchemy.orm import Session

from ..models.nppes_tables import (
    NppesPrescriberDetail,
    PrescriberAddress,
    PrescriberIdentifier,
    PrescriberTaxonomy,
)
from ..models.tables import Prescriber
from ..utils.validators import NpiValidationError, validate_npi

logger = logging.getLogger("prescriber-directory.nppes-ingestion")

# Regex — LESSON-004: use \A...\Z
_NPI_RE = re.compile(r"\A\d{10}\Z")

# Number of taxonomy and identifier columns in NPPES V2
_MAX_TAXONOMIES = 15
_MAX_IDENTIFIERS = 50

# Batch size for satellite-table inserts
_BATCH_SIZE = 1000

# ────────────────────────────────────────────────────────────────────────────
# Date parsing
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


# ────────────────────────────────────────────────────────────────────────────
# Row → satellite objects
# ────────────────────────────────────────────────────────────────────────────

def _build_detail(row: dict[str, str], now: datetime) -> NppesPrescriberDetail:
    """Map a raw NPPES CSV row to NppesPrescriberDetail."""
    return NppesPrescriberDetail(
        npi=row.get("NPI", "").strip(),
        entity_type_code=_or_none(row.get("Entity Type Code", "")),
        replacement_npi=_or_none(row.get("Replacement NPI", "")),
        ein=_or_none(row.get("Employer Identification Number (EIN)", "")),
        provider_last_name_legal=_or_none(row.get("Provider Last Name (Legal Name)", "")),
        provider_first_name=_or_none(row.get("Provider First Name", "")),
        provider_middle_name=_or_none(row.get("Provider Middle Name", "")),
        provider_name_prefix=_or_none(row.get("Provider Name Prefix Text", "")),
        provider_name_suffix=_or_none(row.get("Provider Name Suffix Text", "")),
        provider_credential_text=_or_none(row.get("Provider Credential Text", "")),
        provider_organization_name_legal=_or_none(
            row.get("Provider Organization Name (Legal Business Name)", "")
        ),
        provider_other_organization_name=_or_none(
            row.get("Provider Other Organization Name", "")
        ),
        provider_other_organization_name_type_code=_or_none(
            row.get("Provider Other Organization Name Type Code", "")
        ),
        provider_other_last_name=_or_none(row.get("Provider Other Last Name (former)", "")),
        provider_other_first_name=_or_none(row.get("Provider Other First Name", "")),
        provider_other_middle_name=_or_none(row.get("Provider Other Middle Name", "")),
        provider_other_name_prefix=_or_none(row.get("Provider Other Name Prefix Text", "")),
        provider_other_name_suffix=_or_none(row.get("Provider Other Name Suffix Text", "")),
        provider_other_credential_text=_or_none(row.get("Provider Other Credential Text", "")),
        provider_other_last_name_type_code=_or_none(
            row.get("Provider Other Last Name Type Code", "")
        ),
        provider_enumeration_date=_parse_date(row.get("Provider Enumeration Date", "")),  # type: ignore[arg-type]
        last_update_date=_parse_date(row.get("Last Update Date", "")),  # type: ignore[arg-type]
        npi_deactivation_reason_code=_or_none(row.get("NPI Deactivation Reason Code", "")),
        npi_deactivation_date=_parse_date(row.get("NPI Deactivation Date", "")),  # type: ignore[arg-type]
        npi_reactivation_date=_parse_date(row.get("NPI Reactivation Date", "")),  # type: ignore[arg-type]
        certification_date=_parse_date(row.get("Certification Date", "")),  # type: ignore[arg-type]
        provider_gender_code=_or_none(row.get("Provider Gender Code", "")),
        is_sole_proprietor=_or_none(row.get("Is Sole Proprietor", "")),
        is_organization_subpart=_or_none(row.get("Is Organization Subpart", "")),
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
        authorized_official_name_prefix=_or_none(
            row.get("Authorized Official Name Prefix Text", "")
        ),
        authorized_official_name_suffix=_or_none(
            row.get("Authorized Official Name Suffix Text", "")
        ),
        nppes_loaded_at=now,
    )


def _build_addresses(npi: str, row: dict[str, str], now: datetime) -> list[PrescriberAddress]:
    """Extract mailing and practice addresses; returns 0, 1, or 2 rows."""
    addresses = []

    # Mailing address
    ml1 = _or_none(row.get("Provider First Line Business Mailing Address", ""))
    if ml1:
        addresses.append(
            PrescriberAddress(
                npi=npi,
                address_type="mailing",
                line_1=ml1,
                line_2=_or_none(row.get("Provider Second Line Business Mailing Address", "")),
                city=_or_none(row.get("Provider Business Mailing Address City Name", "")),
                state=_or_none(row.get("Provider Business Mailing Address State Name", "")),
                postal_code=_or_none(
                    row.get("Provider Business Mailing Address Postal Code", "")
                ),
                country_code=_or_none(
                    row.get("Provider Business Mailing Address Country Code (If outside U.S.)", "")
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

    # Practice address
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
                state=_or_none(
                    row.get("Provider Business Practice Location Address State Name", "")
                ),
                postal_code=_or_none(
                    row.get("Provider Business Practice Location Address Postal Code", "")
                ),
                country_code=_or_none(
                    row.get(
                        "Provider Business Practice Location Address Country Code (If outside U.S.)",
                        "",
                    )
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
            break  # stop at first empty slot per spec
        taxonomies.append(
            PrescriberTaxonomy(
                npi=npi,
                sequence=i,
                taxonomy_code=code,
                license_number=_or_none(row.get(f"Provider License Number_{i}", "")),
                license_state_code=_or_none(
                    row.get(f"Provider License Number State Code_{i}", "")
                ),
                is_primary=_or_none(
                    row.get(f"Healthcare Provider Primary Taxonomy Switch_{i}", "")
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
            break  # stop at first empty slot
        identifiers.append(
            PrescriberIdentifier(
                npi=npi,
                sequence=i,
                identifier=ident,
                identifier_type_code=_or_none(
                    row.get(f"Other Provider Identifier Type Code_{i}", "")
                ),
                identifier_state=_or_none(
                    row.get(f"Other Provider Identifier State_{i}", "")
                ),
                identifier_issuer=_or_none(
                    row.get(f"Other Provider Identifier Issuer_{i}", "")
                ),
                updated_at=now,
            )
        )
    return identifiers


# ────────────────────────────────────────────────────────────────────────────
# Pharmacy supplement
# ────────────────────────────────────────────────────────────────────────────

def _maybe_supplement_pharmacy(
    db: Session,
    npi: str,
    entity_type_code: str | None,
    taxonomies: list[PrescriberTaxonomy],
) -> bool:
    """Insert/upsert into pharmacy_directory.pharmacies if conditions met.

    Conditions:
      - entity_type_code == "2" (organization)
      - at least one taxonomy code starts with "333" (pharmacy taxonomy)

    Returns True if supplement was attempted (regardless of T2 table existence).
    T2 may not have landed yet — wrap in try/except and log-and-skip gracefully.
    """
    if entity_type_code != "2":
        return False
    pharmacy_tax = [t for t in taxonomies if t.taxonomy_code and t.taxonomy_code.startswith("333")]
    if not pharmacy_tax:
        return False

    # T2's pharmacies table may not exist yet — attempt and gracefully skip.
    # This supplement path will light up automatically once T2's migrations are applied.
    try:
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
                "name": None,  # T2 will enrich from NPPES organization name
                "taxonomy_code": primary_tax.taxonomy_code,
            },
        )
        return True
    except Exception as exc:
        # T2 table doesn't exist yet — log warning and continue
        logger.warning(
            "nppes_pharmacy_supplement_skipped",
            extra={
                "svc_npi": npi,
                "svc_reason": str(exc)[:200],
                "svc_note": "T2 pharmacy table not yet migrated — supplement will activate after T2 migration",
            },
        )
        return False


# ────────────────────────────────────────────────────────────────────────────
# Batch upsert helpers for satellite tables
# ────────────────────────────────────────────────────────────────────────────

def _upsert_detail(db: Session, detail: NppesPrescriberDetail) -> None:
    """Insert or update NppesPrescriberDetail row keyed on npi."""
    existing = (
        db.query(NppesPrescriberDetail)
        .filter(NppesPrescriberDetail.npi == detail.npi)
        .first()
    )
    if existing is None:
        db.add(detail)
    else:
        # Update all mutable fields
        for col in NppesPrescriberDetail.__table__.columns:
            if col.name in ("id", "npi"):
                continue
            setattr(existing, col.name, getattr(detail, col.name))


def _replace_addresses(db: Session, npi: str, addresses: list[PrescriberAddress]) -> None:
    """Delete existing addresses for NPI and insert fresh rows."""
    db.query(PrescriberAddress).filter(PrescriberAddress.npi == npi).delete()
    for addr in addresses:
        db.add(addr)


def _replace_taxonomies(db: Session, npi: str, taxonomies: list[PrescriberTaxonomy]) -> None:
    """Delete existing taxonomies for NPI and insert fresh rows."""
    db.query(PrescriberTaxonomy).filter(PrescriberTaxonomy.npi == npi).delete()
    for tax in taxonomies:
        db.add(tax)


def _replace_identifiers(db: Session, npi: str, identifiers: list[PrescriberIdentifier]) -> None:
    """Delete existing identifiers for NPI and insert fresh rows."""
    db.query(PrescriberIdentifier).filter(PrescriberIdentifier.npi == npi).delete()
    for ident in identifiers:
        db.add(ident)


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
) -> NppesIngestionStats:
    """Stream-parse a NPPES CSV and populate the satellite tables.

    This is the second-pass pipeline called after the core Prescriber upsert.
    It populates:
      - nppes_prescriber_details
      - prescriber_addresses
      - prescriber_taxonomies
      - prescriber_identifiers
    And attempts the pharmacy supplement for entity_type=2 + taxonomy 333*.

    Parameters
    ----------
    db:
        Synchronous SQLAlchemy Session. Must NOT be tenant-scoped (LESSON-011).
    csv_path:
        Path to the extracted NPPES CSV file.
    batch_size:
        Number of NPI rows to process before flushing to DB.
    progress_every:
        Log a progress line every this many rows.

    Returns
    -------
    NppesIngestionStats
    """
    stats = NppesIngestionStats()
    now = datetime.now(UTC)
    row_count = 0
    batch_count = 0

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row_count += 1
            npi = row.get("NPI", "").strip()

            # Validate NPI — LESSON-004 regex + Luhn
            if not _NPI_RE.fullmatch(npi):
                stats.records_skipped += 1
                logger.debug(
                    "nppes_invalid_npi_format_skipped",
                    extra={"svc_npi_prefix": npi[:4] if npi else "empty"},
                )
                continue
            try:
                validate_npi(npi)
            except NpiValidationError as exc:
                stats.records_errored += 1
                logger.warning(
                    "nppes_luhn_fail_skipped",
                    extra={"svc_npi_prefix": npi[:4], "svc_error": str(exc)[:100]},
                )
                continue

            try:
                entity_type_code = _or_none(row.get("Entity Type Code", ""))

                # Build satellite objects
                detail = _build_detail(row, now)
                addresses = _build_addresses(npi, row, now)
                taxonomies = _build_taxonomies(npi, row, now)
                identifiers = _build_identifiers(npi, row, now)

                # Upsert all tables
                _upsert_detail(db, detail)
                _replace_addresses(db, npi, addresses)
                _replace_taxonomies(db, npi, taxonomies)
                _replace_identifiers(db, npi, identifiers)

                # Pharmacy supplement (entity=2 + taxonomy 333*)
                supplemented = _maybe_supplement_pharmacy(db, npi, entity_type_code, taxonomies)

                # Update stats
                if entity_type_code == "1":
                    stats.individuals += 1
                else:
                    stats.organizations += 1
                if supplemented:
                    stats.pharmacy_supplements += 1
                stats.total_addresses += len(addresses)
                stats.total_taxonomies += len(taxonomies)
                stats.total_identifiers += len(identifiers)

                batch_count += 1
                if batch_count >= batch_size:
                    db.flush()
                    batch_count = 0

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
                stats.records_errored += 1
                logger.warning(
                    "nppes_row_error",
                    extra={"svc_npi": npi[:10], "svc_error": str(exc)[:200]},
                )
                db.rollback()
                # Re-open after rollback so remaining rows can continue
                now = datetime.now(UTC)

    # Final flush
    if batch_count > 0:
        db.flush()

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
