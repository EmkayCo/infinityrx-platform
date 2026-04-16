"""FDA supplementary ingestion services: Drug Shortages + Purple Book.

Called by the two remaining supplementary ingester load() methods in
shared/. REMS was extracted in Wave 9d — its upsert path lives in
shared/data_ingestion/sources/fda_rems.py directly, using flush_upsert_batch
from shared.data_ingestion.batching.

Remaining services:
  DrugShortagesIngestionService — drug_database.drug_shortages (upsert) + drug_shortages_history (append)
  PurpleBookIngestionService   — drug_database.drug_purple_book (upsert)

Strategy:
  - Stream records in batches of 1,000.
  - INSERT ON CONFLICT DO UPDATE for current-state tables.
  - INSERT only (no conflict clause) for drug_shortages_history.
  - PostgreSQL pg_insert used for upserts.

These two services are candidates for the same flush_upsert_batch refactor
REMS just received; tracked as follow-up, not scoped to Wave 9.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors for any regex validation.
LESSON-005: All log extra keys prefixed with ingest_.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from shared.data_ingestion.base import IngestionResult
from src.models.fda_supplementary_tables import (
    DrugPurpleBook,
    DrugShortage,
    DrugShortageHistory,
    SCHEMA,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1_000


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# RemsIngestionService was removed in Wave 9d. REMS upsert path now lives
# inline in shared/data_ingestion/sources/fda_rems.py using flush_upsert_batch
# from shared.data_ingestion.batching. drug_rems_ndc replacement done as
# a single bulk DELETE + INSERT after the parent upsert commits.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Drug Shortages service
# ---------------------------------------------------------------------------


class DrugShortagesIngestionService:
    """Batch upsert/append service for FDA Drug Shortages.

    drug_shortages: INSERT ON CONFLICT DO UPDATE.
    drug_shortages_history: append-only INSERT (no conflict clause).
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        *,
        source_name: str = "fda_drug_shortages",
    ) -> IngestionResult:
        rows: list[dict[str, Any]] = []
        records_processed = 0
        records_inserted = 0
        records_updated = 0
        records_errored = 0
        error_samples: list[dict[str, Any]] = []
        today = date.today()

        for record in records:
            records_processed += 1
            rows.append(record)
            if len(rows) >= _BATCH_SIZE:
                ins, upd, err, smp = self._upsert_shortages_batch(rows, today)
                records_inserted += ins
                records_updated += upd
                records_errored += err
                error_samples.extend(smp)
                rows = []

        if rows:
            ins, upd, err, smp = self._upsert_shortages_batch(rows, today)
            records_inserted += ins
            records_updated += upd
            records_errored += err
            error_samples.extend(smp)

        self._db.flush()

        logger.info(
            "Drug shortages ingestion complete",
            extra={
                "ingest_source": source_name,
                "ingest_processed": records_processed,
                "ingest_inserted": records_inserted,
                "ingest_updated": records_updated,
                "ingest_errored": records_errored,
            },
        )

        return IngestionResult(
            source=source_name,
            status="completed",
            records_processed=records_processed,
            records_inserted=records_inserted,
            records_updated=records_updated,
            records_errored=records_errored,
        )

    def _upsert_shortages_batch(
        self, rows: list[dict[str, Any]], snapshot_date: date
    ) -> tuple[int, int, int, list[dict[str, Any]]]:
        inserted = 0
        updated = 0
        errored = 0
        samples: list[dict[str, Any]] = []

        now = _utcnow()
        for row in rows:
            try:
                drug_name = row.get("drug_name_generic") or ""
                if not drug_name:
                    continue
                app_number = row.get("application_number") or ""

                shortage_vals = {
                    "drug_name_generic": drug_name,
                    "application_number": app_number or None,
                    "ndc_codes": row.get("ndc_codes"),
                    "status": row.get("status"),
                    "shortage_reason": row.get("shortage_reason"),
                    "date_first_posted": row.get("date_first_posted"),
                    "date_last_updated": row.get("date_last_updated"),
                    "date_resolved": row.get("date_resolved"),
                    "manufacturers": row.get("manufacturers"),
                    "therapeutic_category": row.get("therapeutic_category"),
                    "estimated_resupply_date": row.get("estimated_resupply_date"),
                    "alternative_therapies": row.get("alternative_therapies"),
                    "raw_payload": row.get("raw_payload"),
                    "created_at": now,
                    "updated_at": now,
                }

                stmt = pg_insert(DrugShortage).values(**shortage_vals)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_drug_shortages_pk",
                    set_={
                        "ndc_codes": stmt.excluded.ndc_codes,
                        "status": stmt.excluded.status,
                        "shortage_reason": stmt.excluded.shortage_reason,
                        "date_last_updated": stmt.excluded.date_last_updated,
                        "date_resolved": stmt.excluded.date_resolved,
                        "manufacturers": stmt.excluded.manufacturers,
                        "therapeutic_category": stmt.excluded.therapeutic_category,
                        "estimated_resupply_date": stmt.excluded.estimated_resupply_date,
                        "alternative_therapies": stmt.excluded.alternative_therapies,
                        "raw_payload": stmt.excluded.raw_payload,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                result = self._db.execute(stmt)
                if result.rowcount and result.rowcount > 0:
                    inserted += 1
                else:
                    updated += 1

                # Append-only history snapshot
                history_row = DrugShortageHistory(
                    snapshot_date=snapshot_date,
                    drug_name_generic=drug_name,
                    application_number=app_number or None,
                    ndc_codes=row.get("ndc_codes"),
                    status=row.get("status"),
                    shortage_reason=row.get("shortage_reason"),
                    date_first_posted=row.get("date_first_posted"),
                    date_last_updated=row.get("date_last_updated"),
                    date_resolved=row.get("date_resolved"),
                    manufacturers=row.get("manufacturers"),
                    therapeutic_category=row.get("therapeutic_category"),
                    estimated_resupply_date=row.get("estimated_resupply_date"),
                    alternative_therapies=row.get("alternative_therapies"),
                    raw_payload=row.get("raw_payload"),
                    ingested_at=now,
                )
                self._db.add(history_row)

            except Exception as exc:
                errored += 1
                logger.warning(
                    "Drug shortage row upsert error",
                    extra={
                        "ingest_source": "fda_drug_shortages",
                        "ingest_drug_name": row.get("drug_name_generic", "")[:50],
                        "ingest_error": str(exc)[:200],
                    },
                )
                if len(samples) < 10:
                    samples.append({"row": str(row)[:300], "error": str(exc)[:200]})

        return inserted, updated, errored, samples


# ---------------------------------------------------------------------------
# Purple Book service
# ---------------------------------------------------------------------------


class PurpleBookIngestionService:
    """Batch upsert service for FDA Purple Book (biologics).

    Upserts drug_purple_book by bla_number (PK).
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        *,
        source_name: str = "fda_purple_book",
    ) -> IngestionResult:
        rows: list[dict[str, Any]] = []
        records_processed = 0
        records_inserted = 0
        records_updated = 0
        records_errored = 0
        error_samples: list[dict[str, Any]] = []

        for record in records:
            records_processed += 1
            rows.append(record)
            if len(rows) >= _BATCH_SIZE:
                ins, upd, err, smp = self._upsert_purple_book_batch(rows)
                records_inserted += ins
                records_updated += upd
                records_errored += err
                error_samples.extend(smp)
                rows = []

        if rows:
            ins, upd, err, smp = self._upsert_purple_book_batch(rows)
            records_inserted += ins
            records_updated += upd
            records_errored += err
            error_samples.extend(smp)

        self._db.flush()

        logger.info(
            "Purple Book ingestion complete",
            extra={
                "ingest_source": source_name,
                "ingest_processed": records_processed,
                "ingest_inserted": records_inserted,
                "ingest_updated": records_updated,
                "ingest_errored": records_errored,
            },
        )

        return IngestionResult(
            source=source_name,
            status="completed",
            records_processed=records_processed,
            records_inserted=records_inserted,
            records_updated=records_updated,
            records_errored=records_errored,
        )

    def _upsert_purple_book_batch(
        self, rows: list[dict[str, Any]]
    ) -> tuple[int, int, int, list[dict[str, Any]]]:
        inserted = 0
        updated = 0
        errored = 0
        samples: list[dict[str, Any]] = []

        now = _utcnow()
        for row in rows:
            try:
                bla_number = (row.get("bla_number") or "").strip()
                if not bla_number:
                    continue

                with self._db.begin_nested():
                    stmt = pg_insert(DrugPurpleBook).values(
                        bla_number=bla_number,
                        proprietary_name=row.get("proprietary_name"),
                        proper_name=row.get("proper_name"),
                        bla_type=row.get("bla_type"),
                        applicant=row.get("applicant"),
                        strength=row.get("strength"),
                        dosage_form=row.get("dosage_form"),
                        route=row.get("route"),
                        product_presentation=row.get("product_presentation"),
                        status=row.get("status"),
                        licensure_date=row.get("licensure_date"),
                        interchangeable=row.get("interchangeable"),
                        reference_product_bla=row.get("reference_product_bla"),
                        reference_product_proper_name=row.get("reference_product_proper_name"),
                        exclusivity_expiration_date=row.get("exclusivity_expiration_date"),
                        raw_payload=row.get("raw_payload"),
                        created_at=now,
                        updated_at=now,
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["bla_number"],
                        set_={
                            "proprietary_name": stmt.excluded.proprietary_name,
                            "proper_name": stmt.excluded.proper_name,
                            "bla_type": stmt.excluded.bla_type,
                            "applicant": stmt.excluded.applicant,
                            "strength": stmt.excluded.strength,
                            "dosage_form": stmt.excluded.dosage_form,
                            "route": stmt.excluded.route,
                            "product_presentation": stmt.excluded.product_presentation,
                            "status": stmt.excluded.status,
                            "licensure_date": stmt.excluded.licensure_date,
                            "interchangeable": stmt.excluded.interchangeable,
                            "reference_product_bla": stmt.excluded.reference_product_bla,
                            "reference_product_proper_name": stmt.excluded.reference_product_proper_name,
                            "exclusivity_expiration_date": stmt.excluded.exclusivity_expiration_date,
                            "raw_payload": stmt.excluded.raw_payload,
                            "updated_at": stmt.excluded.updated_at,
                        },
                    )
                    result = self._db.execute(stmt)
                    if result.rowcount and result.rowcount > 0:
                        inserted += 1
                    else:
                        updated += 1

            except Exception as exc:
                errored += 1
                logger.warning(
                    "Purple Book row upsert error",
                    extra={
                        "ingest_source": "fda_purple_book",
                        "ingest_bla_number": row.get("bla_number", "")[:20],
                        "ingest_error": str(exc)[:200],
                    },
                )
                if len(samples) < 10:
                    samples.append({"row": str(row)[:300], "error": str(exc)[:200]})

        return inserted, updated, errored, samples


__all__ = [
    "DrugShortagesIngestionService",
    "PurpleBookIngestionService",
]
