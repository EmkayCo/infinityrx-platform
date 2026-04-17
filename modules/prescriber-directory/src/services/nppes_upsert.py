"""NPPES upsert service — bulk upsert of the core Prescriber table from parsed rows.

Streams parsed NPPES records through the shared ``flush_upsert_batch``
primitive: in-batch dedup, pg_insert + ``ON CONFLICT DO UPDATE``, per-batch
commit, ``ErrorAggregator`` for diagnostic logging.

Designed for 7M-row scale. The previous per-row ORM ``SELECT IN`` + hand-
update pattern (pre-Wave-11) issued one SELECT and hundreds of INSERT/UPDATE
statements per 500-row batch; this path issues one INSERT ... ON CONFLICT
statement per 1,000-row batch.

Cross-reference protection: NPPES is source-of-truth for identity, address,
taxonomy, and status, but NOT for DEA, state-license verification results,
PECOS enrollment, Medicare opt-out, telehealth registration, or OIG/OFAC/SAM
exclusion status — those fields are written by dedicated loaders and must
survive every NPPES reload. We list them in ``_IMMUTABLE_ON_UPDATE`` so the
``ON CONFLICT DO UPDATE`` clause leaves them untouched.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from shared.data_ingestion.batching import ErrorAggregator, flush_upsert_batch
from src.models.tables import DataRefreshLog, Prescriber
from src.services.nppes_parser import NppesParser, ParsedNpi
from src.services.taxonomy_service import TaxonomyService
from src.utils.validators import NpiValidationError, validate_npi

logger = logging.getLogger("prescriber-directory.nppes-upsert")

_BATCH_SIZE = 1_000
_taxonomy_service = TaxonomyService()

# Columns that NPPES does NOT own — other loaders write these, and an NPPES
# reload must never clobber them. Together with ``id`` and ``created_at``
# (the standard immutables), this is the full list of prescribers columns
# excluded from the ``ON CONFLICT DO UPDATE`` SET clause.
_IMMUTABLE_ON_UPDATE: tuple[str, ...] = (
    # Standard immutables
    "id",
    "created_at",
    # Geocoding + multi-source enrichment
    "organization_type",
    "practice_latitude",
    "practice_longitude",
    "additional_locations",
    # DEA loader owns these
    "dea_number",
    "dea_status",
    "dea_expiration_date",
    "dea_schedules",
    "dea_state",
    "dea_last_verified",
    # State-license verification service owns these
    "state_license_number",
    "state_license_state",
    "state_license_status",
    "state_license_expiry",
    "additional_state_licenses",
    "license_last_verified",
    # Medicare / PECOS cross-refs
    "pecos_enrolled",
    "medicare_participation",
    "medicare_opt_out",  # cms_opt_out loader owns this
    # Telehealth registry
    "offers_telehealth",
    "telehealth_states",
    # Manual override tracker
    "manual_last_updated",
    # Exclusion cross-refs (OIG LEIE / OFAC / SAM loaders own these)
    "is_excluded",
    "excluded_source",
    "exclusion_date",
    "exclusion_type",
)


def _to_row_dict(parsed: ParsedNpi, now: datetime) -> dict[str, Any]:
    """Convert a ``ParsedNpi`` to a dict suitable for ``flush_upsert_batch``.

    Only includes NPPES-owned columns. Cross-reference columns left out of
    this dict are populated by their dedicated loaders on INSERT (via column
    defaults / server_default) and preserved on UPDATE via
    ``_IMMUTABLE_ON_UPDATE``.

    ``display_name`` falls back to NPI when the parser produced no name —
    previously the ORM upsert preferred the existing row's display_name on
    update, but ``flush_upsert_batch`` applies a single SET clause across
    all rows in the batch, so we pin a deterministic fallback here.
    """
    taxonomy_desc = (
        _taxonomy_service.get_display_name(parsed.primary_taxonomy_code)
        if parsed.primary_taxonomy_code
        else None
    )
    specialty = (
        _taxonomy_service.get_simplified_specialty(parsed.primary_taxonomy_code)
        if parsed.primary_taxonomy_code
        else None
    )
    return {
        "npi": parsed.npi,
        "entity_type": parsed.entity_type,
        "last_name": parsed.last_name,
        "first_name": parsed.first_name,
        "middle_name": parsed.middle_name,
        "prefix": parsed.prefix,
        "suffix": parsed.suffix,
        "credential": parsed.credential,
        "display_name": parsed.display_name or parsed.npi,
        "organization_name": parsed.organization_name,
        "authorized_official_name": parsed.authorized_official_name,
        "authorized_official_title": parsed.authorized_official_title,
        "primary_taxonomy_code": parsed.primary_taxonomy_code,
        "primary_taxonomy_description": taxonomy_desc,
        "primary_specialty": specialty,
        "taxonomy_codes": parsed.taxonomy_codes,
        "gender": parsed.gender,
        "practice_address_line_1": parsed.practice_address_line_1,
        "practice_address_line_2": parsed.practice_address_line_2,
        "practice_city": parsed.practice_city,
        "practice_state": parsed.practice_state,
        "practice_zip": parsed.practice_zip,
        "practice_phone": parsed.practice_phone,
        "practice_fax": parsed.practice_fax,
        "mailing_address_line_1": parsed.mailing_address_line_1,
        "mailing_address_line_2": parsed.mailing_address_line_2,
        "mailing_city": parsed.mailing_city,
        "mailing_state": parsed.mailing_state,
        "mailing_zip": parsed.mailing_zip,
        "enumeration_date": parsed.enumeration_date,
        "last_update_date": parsed.last_update_date,
        "deactivation_date": parsed.deactivation_date,
        "deactivation_reason": parsed.deactivation_reason,
        "reactivation_date": parsed.reactivation_date,
        "status": parsed.status,
        "nppes_last_updated": now,
    }


def upsert_batch(db: Session, batch: list[ParsedNpi]) -> tuple[int, int]:
    """Upsert a batch of parsed NPIs. Returns ``(added, updated)`` counts.

    Pre-Wave-11 compatibility shim: determines added vs updated by probing
    existing NPIs before the upsert. The full-pipeline path
    (``run_nppes_import``) uses ``flush_upsert_batch`` directly and treats
    the distinction as cosmetic — the DataRefreshLog still reports both.
    """
    if not batch:
        return 0, 0

    from sqlalchemy import select

    npis = [p.npi for p in batch]
    existing_npis: set[str] = set()
    if npis:
        rows = db.execute(select(Prescriber.npi).where(Prescriber.npi.in_(npis))).scalars().all()
        existing_npis = set(rows)

    now = datetime.now(UTC)
    row_dicts = [_to_row_dict(p, now) for p in batch]

    errors = ErrorAggregator()
    flush_upsert_batch(
        db,
        source_name="nppes",
        table=Prescriber.__table__,
        unique_key=["npi"],
        rows=row_dicts,
        errors=errors,
        immutable_on_update=_IMMUTABLE_ON_UPDATE,
    )
    if errors.total_errors:
        errors.log_summary(source_name="nppes")

    # Invalidate the ORM identity map so subsequent reads in the same session
    # see values we just wrote via pg_insert (which bypasses the ORM).
    db.expire_all()

    added = sum(1 for p in batch if p.npi not in existing_npis)
    updated = len(batch) - added
    return added, updated


def run_nppes_import(
    db: Session,
    source,
    data_source: str = "nppes",
    refresh_type: str = "full",
) -> DataRefreshLog:
    """Run a full NPPES import from a CSV file-like source.

    Streams the CSV through ``NppesParser`` → 1,000-row batches →
    ``flush_upsert_batch``. Returns a ``DataRefreshLog`` record with final
    statistics; ``ErrorAggregator`` summary is logged separately.
    """
    start = datetime.now(UTC)
    refresh_log = DataRefreshLog(
        data_source=data_source,
        refresh_type=refresh_type,
        started_at=start,
        status="in_progress",
        created_at=start,
    )
    db.add(refresh_log)
    db.flush()

    parser = NppesParser()
    errors = ErrorAggregator()
    total_processed = 0
    total_upserted = 0
    batch: list[ParsedNpi] = []
    batch_added = 0
    batch_updated = 0

    def _flush() -> None:
        nonlocal total_upserted, batch_added, batch_updated
        if not batch:
            return
        a, u = upsert_batch(db, batch)
        batch_added += a
        batch_updated += u
        total_upserted += len(batch)
        batch.clear()

    try:
        for parsed in parser.parse(source):
            try:
                validate_npi(parsed.npi)
            except NpiValidationError:
                logger.warning(
                    "nppes_invalid_npi_skipped",
                    extra={"svc_npi_prefix": parsed.npi[:4] if parsed.npi else "NONE"},
                )
                continue

            batch.append(parsed)
            total_processed += 1
            if len(batch) >= _BATCH_SIZE:
                _flush()

        _flush()

        completed = datetime.now(UTC)
        refresh_log.completed_at = completed
        refresh_log.status = "completed"
        refresh_log.records_processed = total_processed
        refresh_log.records_added = batch_added
        refresh_log.records_updated = batch_updated
        db.flush()

        errors.log_summary(source_name=data_source)
        logger.info(
            "nppes_import_complete",
            extra={
                "svc_processed": total_processed,
                "svc_added": batch_added,
                "svc_updated": batch_updated,
            },
        )

    except Exception as exc:
        refresh_log.status = "failed"
        refresh_log.error_message = str(exc)
        refresh_log.completed_at = datetime.now(UTC)
        db.flush()
        raise

    return refresh_log
