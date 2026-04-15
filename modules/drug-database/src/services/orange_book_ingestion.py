"""Orange Book ingestion service — batch upsert for FDA Orange Book data.

Called by shared.data_ingestion.sources.fda_orange_book.FDAOrangeBookIngester.load().

Handles three tables:
  drug_database.drug_orange_book  — upsert by (appl_type, appl_no, product_no)
  drug_database.drug_patents       — delete-then-insert by (appl_type, appl_no, product_no)
  drug_database.drug_exclusivity   — delete-then-insert by (appl_type, appl_no, product_no)

Products are upserted because we want to preserve the row ID across runs.
Patents and exclusivity are delete-then-insert per (appl_type, appl_no, product_no)
tuple because the FDA Orange Book ZIP is a complete refresh; deleting and
re-inserting guarantees that removed patents are pruned correctly.

Strategy:
  1. Stream all records and accumulate product rows and child rows separately.
  2. Upsert product rows in batches of _BATCH_SIZE.
  3. Collect unique (appl_type, appl_no, product_no) keys that appeared in this run.
  4. For each unique key, delete existing patent + exclusivity rows then re-insert.

Batch size: 1,000 rows per INSERT (stream; never loads all rows into memory).

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors for any regex validation.
LESSON-005: All log extra keys prefixed with ingest_.
Financial precision: no money columns in this module — but no floats introduced.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from shared.data_ingestion.base import IngestionResult
from src.models.orange_book_tables import (
    DrugExclusivity,
    DrugOrangeBook,
    DrugPatent,
    SCHEMA,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1_000


class OrangeBookIngestionService:
    """Batch upsert/replace service for FDA Orange Book data.

    Accepts an iterator of ``{"table": str, "row": dict}`` records produced
    by FDAOrangeBookIngester.parse() and writes them to the drug_database schema.
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        *,
        source_name: str = "fda_orange_book",
    ) -> IngestionResult:
        """Stream records, group by table, batch-upsert products, replace patents/exclusivity.

        Returns a partial IngestionResult (run_id is filled by the base class).
        """
        product_rows: list[dict[str, Any]] = []
        patent_rows: list[dict[str, Any]] = []
        exclusivity_rows: list[dict[str, Any]] = []

        records_processed = 0
        records_inserted = 0
        records_updated = 0
        records_errored = 0
        error_samples: list[dict[str, Any]] = []

        # Accumulate all records from the iterator
        for record in records:
            records_processed += 1
            table = record.get("table")
            row = record.get("row", {})

            if table == "drug_orange_book":
                product_rows.append(row)
                if len(product_rows) >= _BATCH_SIZE:
                    ins, upd, err, smp = self._upsert_product_batch(product_rows)
                    records_inserted += ins
                    records_updated += upd
                    records_errored += err
                    error_samples.extend(smp)
                    product_rows = []

            elif table == "drug_patents":
                patent_rows.append(row)

            elif table == "drug_exclusivity":
                exclusivity_rows.append(row)

        # Flush remaining product rows
        if product_rows:
            ins, upd, err, smp = self._upsert_product_batch(product_rows)
            records_inserted += ins
            records_updated += upd
            records_errored += err
            error_samples.extend(smp)

        # Delete-then-insert patents
        pat_ins, pat_err, pat_smp = self._replace_patents(patent_rows)
        records_inserted += pat_ins
        records_errored += pat_err
        error_samples.extend(pat_smp)

        # Delete-then-insert exclusivity
        exc_ins, exc_err, exc_smp = self._replace_exclusivity(exclusivity_rows)
        records_inserted += exc_ins
        records_errored += exc_err
        error_samples.extend(exc_smp)

        self._db.commit()

        logger.info(
            "Orange Book ingestion load complete",
            extra={
                "ingest_source": source_name,
                "ingest_records_processed": records_processed,
                "ingest_records_inserted": records_inserted,
                "ingest_records_errored": records_errored,
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

    # ------------------------------------------------------------------
    # Product upsert
    # ------------------------------------------------------------------

    def _upsert_product_batch(
        self, rows: list[dict[str, Any]]
    ) -> tuple[int, int, int, list[dict[str, Any]]]:
        """Upsert a batch of drug_orange_book rows by (appl_type, appl_no, product_no).

        Returns (inserted, updated, errored, error_samples).
        """
        now = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        errored = 0
        error_samples: list[dict[str, Any]] = []

        # De-duplicate within batch by (appl_type, appl_no, product_no) — real
        # FDA Orange Book has same product across multiple list revisions.
        deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in rows:
            try:
                key = (
                    row.get("appl_type", ""),
                    row.get("appl_no", ""),
                    row.get("product_no", ""),
                )
                deduped[key] = {**row, "created_at": now, "updated_at": now}
            except Exception as exc:
                errored += 1
                if len(error_samples) < 10:
                    error_samples.append({
                        "field": "product_row",
                        "raw_row": str(row)[:500],
                        "error": str(exc)[:500],
                    })
        valid_rows = list(deduped.values())

        if not valid_rows:
            return inserted, updated, errored, error_samples

        try:
            stmt = pg_insert(DrugOrangeBook.__table__).values(valid_rows)
            update_cols = {
                c.name: stmt.excluded[c.name]
                for c in DrugOrangeBook.__table__.columns
                if c.name not in ("id", "created_at")
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["appl_type", "appl_no", "product_no"],
                set_=update_cols,
            )
            self._db.execute(stmt)
            self._db.commit()  # BUG-05 fix: per-batch durability
            logger.info(
                "Orange Book product batch committed",
                extra={"ingest_source": "fda_orange_book",
                       "ingest_batch_size": len(valid_rows)},
            )
            inserted += len(valid_rows)
        except Exception as exc:
            errored += len(valid_rows)
            logger.exception(
                "Orange Book product batch upsert failed",
                extra={
                    "ingest_source": "fda_orange_book",
                    "ingest_batch_size": len(valid_rows),
                    "ingest_error": str(exc)[:500],
                },
            )
            if len(error_samples) < 10:
                error_samples.append({
                    "field": "product_batch",
                    "raw_row": str(valid_rows[0])[:500],
                    "error": str(exc)[:500],
                })
            self._db.rollback()

        return inserted, updated, errored, error_samples

    # ------------------------------------------------------------------
    # Patent delete-then-insert
    # ------------------------------------------------------------------

    def _replace_patents(
        self, rows: list[dict[str, Any]]
    ) -> tuple[int, int, list[dict[str, Any]]]:
        """Delete existing patents for all (appl_type, appl_no, product_no) keys
        that appear in *rows*, then re-insert.

        Returns (inserted, errored, error_samples).
        """
        now = datetime.now(timezone.utc)
        inserted = 0
        errored = 0
        error_samples: list[dict[str, Any]] = []

        if not rows:
            return inserted, errored, error_samples

        # Collect unique (appl_type, appl_no, product_no) tuples
        seen_keys: set[tuple[str, str, str]] = set()
        for row in rows:
            key = (
                row.get("appl_type") or "",
                row.get("appl_no") or "",
                row.get("product_no") or "",
            )
            seen_keys.add(key)

        # Delete existing records for each key
        for appl_type, appl_no, product_no in seen_keys:
            try:
                self._db.query(DrugPatent).filter(
                    DrugPatent.appl_type == appl_type,
                    DrugPatent.appl_no == appl_no,
                    DrugPatent.product_no == product_no,
                ).delete(synchronize_session=False)
            except Exception as exc:
                logger.exception(
                    "Failed to delete patents for key",
                    extra={
                        "ingest_source": "fda_orange_book",
                        "ingest_appl_type": appl_type,
                        "ingest_appl_no": appl_no,
                        "ingest_product_no": product_no,
                        "ingest_error": str(exc)[:500],
                    },
                )

        self._db.commit()  # commit the deletes before any inserts

        # BUG-05a fix: dedup by the unique constraint tuple
        # (appl_type, appl_no, product_no, patent_no) before batching.
        # Same pattern as drug_exclusivity. Keep last-seen.
        deduped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for r in rows:
            key = (
                r.get("appl_type") or "",
                r.get("appl_no") or "",
                r.get("product_no") or "",
                r.get("patent_no") or "",
            )
            deduped[key] = r
        rows = list(deduped.values())

        # Insert in batches
        for i in range(0, len(rows), _BATCH_SIZE):
            chunk = rows[i : i + _BATCH_SIZE]
            enriched = [{**r, "created_at": now} for r in chunk]
            try:
                self._db.execute(DrugPatent.__table__.insert(), enriched)
                self._db.commit()  # BUG-05 fix: per-batch durability
                inserted += len(enriched)
            except Exception as exc:
                errored += len(enriched)
                logger.exception(
                    "Patent batch insert failed",
                    extra={
                        "ingest_source": "fda_orange_book",
                        "ingest_batch_size": len(enriched),
                        "ingest_error": str(exc)[:500],
                    },
                )
                if len(error_samples) < 10:
                    error_samples.append({
                        "field": "patent_batch",
                        "raw_row": str(enriched[0])[:500],
                        "error": str(exc)[:500],
                    })
                self._db.rollback()

        return inserted, errored, error_samples

    # ------------------------------------------------------------------
    # Exclusivity delete-then-insert
    # ------------------------------------------------------------------

    def _replace_exclusivity(
        self, rows: list[dict[str, Any]]
    ) -> tuple[int, int, list[dict[str, Any]]]:
        """Delete existing exclusivity for all (appl_type, appl_no, product_no) keys
        that appear in *rows*, then re-insert.

        Returns (inserted, errored, error_samples).
        """
        now = datetime.now(timezone.utc)
        inserted = 0
        errored = 0
        error_samples: list[dict[str, Any]] = []

        if not rows:
            return inserted, errored, error_samples

        # Collect unique (appl_type, appl_no, product_no) tuples
        seen_keys: set[tuple[str, str, str]] = set()
        for row in rows:
            key = (
                row.get("appl_type") or "",
                row.get("appl_no") or "",
                row.get("product_no") or "",
            )
            seen_keys.add(key)

        # Delete existing records for each key
        for appl_type, appl_no, product_no in seen_keys:
            try:
                self._db.query(DrugExclusivity).filter(
                    DrugExclusivity.appl_type == appl_type,
                    DrugExclusivity.appl_no == appl_no,
                    DrugExclusivity.product_no == product_no,
                ).delete(synchronize_session=False)
            except Exception as exc:
                logger.exception(
                    "Failed to delete exclusivity for key",
                    extra={
                        "ingest_source": "fda_orange_book",
                        "ingest_appl_type": appl_type,
                        "ingest_appl_no": appl_no,
                        "ingest_product_no": product_no,
                        "ingest_error": str(exc)[:500],
                    },
                )

        self._db.commit()  # commit the deletes before any inserts

        # BUG-05a fix: dedup the entire incoming list by the unique
        # constraint tuple (appl_type, appl_no, product_no,
        # exclusivity_code, exclusivity_date) BEFORE batching. The FDA
        # Orange Book exclusivity file legitimately yields multiple
        # rows with the same key when an exclusivity spans multiple
        # product codes or lists. Keep the last occurrence.
        deduped: dict[tuple[str, str, str, str, Any], dict[str, Any]] = {}
        for r in rows:
            key = (
                r.get("appl_type") or "",
                r.get("appl_no") or "",
                r.get("product_no") or "",
                r.get("exclusivity_code") or "",
                r.get("exclusivity_date"),
            )
            deduped[key] = r
        rows = list(deduped.values())

        # Insert in batches
        for i in range(0, len(rows), _BATCH_SIZE):
            chunk = rows[i : i + _BATCH_SIZE]
            enriched = [{**r, "created_at": now} for r in chunk]
            try:
                self._db.execute(DrugExclusivity.__table__.insert(), enriched)
                self._db.commit()  # BUG-05 fix: per-batch durability
                inserted += len(enriched)
            except Exception as exc:
                errored += len(enriched)
                logger.exception(
                    "Exclusivity batch insert failed",
                    extra={
                        "ingest_source": "fda_orange_book",
                        "ingest_batch_size": len(enriched),
                        "ingest_error": str(exc)[:500],
                    },
                )
                if len(error_samples) < 10:
                    error_samples.append({
                        "field": "exclusivity_batch",
                        "raw_row": str(enriched[0])[:500],
                        "error": str(exc)[:500],
                    })
                self._db.rollback()

        return inserted, errored, error_samples


__all__ = ["OrangeBookIngestionService"]
