"""NCPDP DataQ ingestion service.

Handles batch upsert of parsed NCPDP records into the 13 pharmacy_dir tables.
Called by NCPDPDataQIngester.load() in shared/data_ingestion/sources/ncpdp_dataq.py.

Design:
- Groups records by table name (from parse() yield {"table": "...", "row": {...}}).
- Accumulates 1000-row batches then flushes with SQLAlchemy Core INSERT ... ON CONFLICT.
- Master table (ncpdp_pharmacies) uses upsert by ncpdp_provider_id.
- Child tables (taxonomies, licenses, services, etc.) use delete-then-insert by
  ncpdp_provider_id within each run so stale rows from source drop-offs are purged.
- All SQLAlchemy Core INSERT/DELETE — no ORM add() calls — for performance.

LESSON-011: No TenantScopedMixin; global reference data.
LESSON-005: Log extra keys prefixed with 'ingest_'.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from sqlalchemy import delete, insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from shared.data_ingestion.base import IngestionResult
from ..models.ncpdp_tables import (
    NCPDPPharmacy,
    NCPDPPharmacyAdditionalInfo,
    NCPDPPharmacyCoordinate,
    NCPDPPharmacyErxCapability,
    NCPDPPharmacyFwaAction,
    NCPDPPharmacyMedicaid,
    NCPDPPharmacyPatientCare,
    NCPDPPharmacyProgram,
    NCPDPPharmacyRecertification,
    NCPDPPharmacyRemittance,
    NCPDPPharmacyService,
    NCPDPPharmacyStateLicense,
    NCPDPPharmacyTaxonomy,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 1_000

# Map table name (from parse() yield) → ORM model class
_TABLE_MAP: dict[str, Any] = {
    "ncpdp_pharmacies": NCPDPPharmacy,
    "ncpdp_pharmacy_taxonomies": NCPDPPharmacyTaxonomy,
    "ncpdp_pharmacy_state_licenses": NCPDPPharmacyStateLicense,
    "ncpdp_pharmacy_services": NCPDPPharmacyService,
    "ncpdp_pharmacy_remittance": NCPDPPharmacyRemittance,
    "ncpdp_pharmacy_erx_capabilities": NCPDPPharmacyErxCapability,
    "ncpdp_pharmacy_medicaid": NCPDPPharmacyMedicaid,
    "ncpdp_pharmacy_fwa_actions": NCPDPPharmacyFwaAction,
    "ncpdp_pharmacy_coordinates": NCPDPPharmacyCoordinate,
    "ncpdp_pharmacy_additional_info": NCPDPPharmacyAdditionalInfo,
    "ncpdp_pharmacy_patient_care": NCPDPPharmacyPatientCare,
    "ncpdp_pharmacy_programs": NCPDPPharmacyProgram,
    "ncpdp_pharmacy_recertification": NCPDPPharmacyRecertification,
}

# Child tables that use delete-then-insert strategy (multiple rows per pharmacy).
# Master and tables with a UNIQUE on ncpdp_provider_id use upsert instead.
_DELETE_INSERT_TABLES = {
    "ncpdp_pharmacy_taxonomies",
    "ncpdp_pharmacy_state_licenses",
    "ncpdp_pharmacy_remittance",
    "ncpdp_pharmacy_erx_capabilities",
    "ncpdp_pharmacy_medicaid",
    "ncpdp_pharmacy_fwa_actions",
}

# Tables that use upsert (single row per pharmacy / chain entity)
_UPSERT_TABLES = {
    "ncpdp_pharmacies",
    "ncpdp_pharmacy_services",
    "ncpdp_pharmacy_coordinates",
    "ncpdp_pharmacy_additional_info",
    "ncpdp_pharmacy_patient_care",
    "ncpdp_pharmacy_programs",
    "ncpdp_pharmacy_recertification",
}


class NCPDPIngestionService:
    """Bulk-loads NCPDP DataQ records into the pharmacy_dir schema.

    Called from NCPDPDataQIngester.load().  Caller provides an iterator
    of ``{"table": str, "row": dict}`` records from the parser.
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        *,
        source_name: str = "ncpdp",
    ) -> IngestionResult:
        """Consume the records iterator, batch-insert into all 13 tables."""
        inserted = 0
        updated = 0
        errored = 0
        processed = 0

        # Buffers: table_name → list of row dicts
        buffers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        # Track which ncpdp_provider_ids have been pre-deleted in child tables
        deleted_ids: dict[str, set[str]] = defaultdict(set)

        for record in records:
            table_name = record.get("table", "")
            row = record.get("row", {})
            if not table_name or not row:
                errored += 1
                continue

            processed += 1
            buffers[table_name].append(row)

            if len(buffers[table_name]) >= BATCH_SIZE:
                n_ins, n_upd, n_err = self._flush_buffer(
                    table_name, buffers[table_name], deleted_ids
                )
                inserted += n_ins
                updated += n_upd
                errored += n_err
                buffers[table_name] = []

        # Flush remaining
        for table_name, rows in buffers.items():
            if rows:
                n_ins, n_upd, n_err = self._flush_buffer(
                    table_name, rows, deleted_ids
                )
                inserted += n_ins
                updated += n_upd
                errored += n_err

        self._db.flush()

        logger.info(
            "NCPDP load complete",
            extra={
                "ingest_source": source_name,
                "ingest_processed": processed,
                "ingest_inserted": inserted,
                "ingest_updated": updated,
                "ingest_errored": errored,
            },
        )

        return IngestionResult(
            source=source_name,
            status="completed",
            records_processed=processed,
            records_inserted=inserted,
            records_updated=updated,
            records_errored=errored,
        )

    def _flush_buffer(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        deleted_ids: dict[str, set[str]],
    ) -> tuple[int, int, int]:
        """Flush one batch for a single table. Returns (inserted, updated, errored)."""
        model = _TABLE_MAP.get(table_name)
        if model is None:
            logger.warning(
                "Unknown table in NCPDP batch flush",
                extra={"ingest_table": table_name},
            )
            return 0, 0, len(rows)

        try:
            if table_name in _DELETE_INSERT_TABLES:
                return self._delete_insert_batch(model, table_name, rows, deleted_ids)
            else:
                return self._upsert_batch(model, table_name, rows)
        except Exception as exc:
            logger.error(
                "NCPDP batch flush error",
                extra={
                    "ingest_table": table_name,
                    "ingest_batch_size": len(rows),
                    "ingest_error": str(exc)[:500],
                },
            )
            return 0, 0, len(rows)

    def _delete_insert_batch(
        self,
        model: Any,
        table_name: str,
        rows: list[dict[str, Any]],
        deleted_ids: dict[str, set[str]],
    ) -> tuple[int, int, int]:
        """Delete existing rows for ncpdp_ids in this batch, then insert fresh rows."""
        # Collect unique ncpdp_provider_ids not yet deleted this run
        ids_to_delete = {
            r["ncpdp_provider_id"]
            for r in rows
            if r.get("ncpdp_provider_id")
            and r["ncpdp_provider_id"] not in deleted_ids[table_name]
        }

        if ids_to_delete:
            self._db.execute(
                delete(model).where(
                    model.ncpdp_provider_id.in_(ids_to_delete)
                )
            )
            deleted_ids[table_name].update(ids_to_delete)

        self._db.execute(insert(model), rows)
        return len(rows), 0, 0

    def _upsert_batch(
        self,
        model: Any,
        table_name: str,
        rows: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        """Upsert rows using dialect-appropriate INSERT ... ON CONFLICT DO UPDATE."""
        dialect = self._db.get_bind().dialect.name  # type: ignore[attr-defined]

        if dialect == "sqlite":
            # SQLite: use INSERT OR REPLACE via sqlalchemy dialects.sqlite insert
            stmt = sqlite_insert(model).values(rows)
            # Determine the unique constraint column
            unique_col = self._get_unique_col(table_name)
            if unique_col:
                # Build set clause for all non-key columns
                update_cols = {
                    c.name: getattr(stmt.excluded, c.name)
                    for c in model.__table__.columns
                    if c.name != "id" and c.name != unique_col
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=[unique_col],
                    set_=update_cols,
                )
            self._db.execute(stmt)
        else:
            # PostgreSQL: use INSERT ... ON CONFLICT DO UPDATE
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(model).values(rows)
            unique_col = self._get_unique_col(table_name)
            if unique_col:
                update_cols = {
                    c.name: getattr(stmt.excluded, c.name)
                    for c in model.__table__.columns
                    if c.name != "id" and c.name != unique_col
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=[unique_col],
                    set_=update_cols,
                )
            self._db.execute(stmt)

        return len(rows), 0, 0

    @staticmethod
    def _get_unique_col(table_name: str) -> str | None:
        """Return the upsert key column name for each table."""
        upsert_keys: dict[str, str] = {
            "ncpdp_pharmacies": "ncpdp_provider_id",
            "ncpdp_pharmacy_services": "ncpdp_provider_id",
            "ncpdp_pharmacy_coordinates": "ncpdp_provider_id",
            "ncpdp_pharmacy_additional_info": "chain_entity_id",
            "ncpdp_pharmacy_patient_care": "chain_entity_id",
            "ncpdp_pharmacy_programs": "chain_entity_id",
            "ncpdp_pharmacy_recertification": "chain_entity_id",
        }
        return upsert_keys.get(table_name)


__all__ = ["NCPDPIngestionService", "BATCH_SIZE"]
