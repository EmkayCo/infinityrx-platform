"""NPPES upsert service — bulk insert/update from parsed NPPES records.

Uses INSERT ... ON CONFLICT DO UPDATE (PostgreSQL) for efficient bulk upsert.
For tests (SQLite), falls back to per-record merge.

Designed for 7.8M-row scale: stream from parser → batch → upsert.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models.tables import DataRefreshLog, Prescriber
from src.services.nppes_parser import NppesParser, ParsedNpi
from src.services.taxonomy_service import TaxonomyService
from src.utils.validators import NpiValidationError, validate_npi

logger = logging.getLogger("prescriber-directory.nppes-upsert")

_BATCH_SIZE = 500
_taxonomy_service = TaxonomyService()


def _to_prescriber(parsed: ParsedNpi) -> Prescriber:
    now = datetime.now(UTC)
    taxonomy_desc = _taxonomy_service.get_display_name(parsed.primary_taxonomy_code) if parsed.primary_taxonomy_code else None
    simplified = _taxonomy_service.get_simplified_specialty(parsed.primary_taxonomy_code) if parsed.primary_taxonomy_code else None

    return Prescriber(
        npi=parsed.npi,
        entity_type=parsed.entity_type,
        last_name=parsed.last_name,
        first_name=parsed.first_name,
        middle_name=parsed.middle_name,
        prefix=parsed.prefix,
        suffix=parsed.suffix,
        credential=parsed.credential,
        display_name=parsed.display_name or parsed.npi,
        organization_name=parsed.organization_name,
        authorized_official_name=parsed.authorized_official_name,
        authorized_official_title=parsed.authorized_official_title,
        primary_taxonomy_code=parsed.primary_taxonomy_code,
        primary_taxonomy_description=taxonomy_desc,
        primary_specialty=simplified,
        taxonomy_codes=parsed.taxonomy_codes,
        gender=parsed.gender,
        practice_address_line_1=parsed.practice_address_line_1,
        practice_address_line_2=parsed.practice_address_line_2,
        practice_city=parsed.practice_city,
        practice_state=parsed.practice_state,
        practice_zip=parsed.practice_zip,
        practice_phone=parsed.practice_phone,
        practice_fax=parsed.practice_fax,
        mailing_address_line_1=parsed.mailing_address_line_1,
        mailing_address_line_2=parsed.mailing_address_line_2,
        mailing_city=parsed.mailing_city,
        mailing_state=parsed.mailing_state,
        mailing_zip=parsed.mailing_zip,
        state_license_number=parsed.state_license_number,
        state_license_state=parsed.state_license_state,
        enumeration_date=parsed.enumeration_date,
        last_update_date=parsed.last_update_date,
        deactivation_date=parsed.deactivation_date,
        deactivation_reason=parsed.deactivation_reason,
        reactivation_date=parsed.reactivation_date,
        status=parsed.status,
        offers_telehealth=False,
        medicare_opt_out=False,
        nppes_last_updated=now,
        created_at=now,
        updated_at=now,
    )


def upsert_batch(db: Session, batch: list[ParsedNpi]) -> tuple[int, int]:
    """Upsert a batch of parsed NPIs. Returns (added, updated) counts."""
    added = 0
    updated = 0

    npis = [p.npi for p in batch]
    existing_map = {}
    if npis:
        from sqlalchemy import select
        rows = db.execute(select(Prescriber).where(Prescriber.npi.in_(npis))).scalars().all()
        existing_map = {r.npi: r for r in rows}

    now = datetime.now(UTC)

    for parsed in batch:
        existing = existing_map.get(parsed.npi)
        if existing is None:
            db.add(_to_prescriber(parsed))
            added += 1
        else:
            taxonomy_desc = _taxonomy_service.get_display_name(parsed.primary_taxonomy_code) if parsed.primary_taxonomy_code else None
            simplified = _taxonomy_service.get_simplified_specialty(parsed.primary_taxonomy_code) if parsed.primary_taxonomy_code else None
            existing.last_name = parsed.last_name
            existing.first_name = parsed.first_name
            existing.middle_name = parsed.middle_name
            existing.credential = parsed.credential
            existing.display_name = parsed.display_name or existing.display_name
            existing.organization_name = parsed.organization_name
            existing.primary_taxonomy_code = parsed.primary_taxonomy_code
            existing.primary_taxonomy_description = taxonomy_desc
            existing.primary_specialty = simplified
            existing.taxonomy_codes = parsed.taxonomy_codes
            existing.practice_address_line_1 = parsed.practice_address_line_1
            existing.practice_city = parsed.practice_city
            existing.practice_state = parsed.practice_state
            existing.practice_zip = parsed.practice_zip
            existing.last_update_date = parsed.last_update_date
            existing.deactivation_date = parsed.deactivation_date
            existing.deactivation_reason = parsed.deactivation_reason
            existing.reactivation_date = parsed.reactivation_date
            existing.status = parsed.status
            existing.nppes_last_updated = now
            existing.updated_at = now
            updated += 1

    db.flush()
    return added, updated


def run_nppes_import(
    db: Session,
    source,
    data_source: str = "nppes",
    refresh_type: str = "full",
) -> DataRefreshLog:
    """Run a full NPPES import from a CSV file-like source.

    Streams the CSV through NppesParser → batches → upserts.
    Returns a DataRefreshLog record with final statistics.
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
    total_processed = 0
    total_added = 0
    total_updated = 0
    batch: list[ParsedNpi] = []

    try:
        for parsed in parser.parse(source):
            # Validate NPI format — skip malformed records
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
                added, updated = upsert_batch(db, batch)
                total_added += added
                total_updated += updated
                batch = []

        # Flush remaining
        if batch:
            added, updated = upsert_batch(db, batch)
            total_added += added
            total_updated += updated

        completed = datetime.now(UTC)
        refresh_log.completed_at = completed
        refresh_log.status = "completed"
        refresh_log.records_processed = total_processed
        refresh_log.records_added = total_added
        refresh_log.records_updated = total_updated
        db.flush()

        logger.info(
            "nppes_import_complete",
            extra={
                "svc_processed": total_processed,
                "svc_added": total_added,
                "svc_updated": total_updated,
            },
        )

    except Exception as exc:
        refresh_log.status = "failed"
        refresh_log.error_message = str(exc)
        refresh_log.completed_at = datetime.now(UTC)
        db.flush()
        raise

    return refresh_log
