"""NDC ingestion service — batch upsert for FDA NDC Directory data.

Called by shared.data_ingestion.sources.fda_ndc.FDANDCIngester.load().

Handles four tables:
  drug_database.drugs                   — upsert by product_id (ON CONFLICT DO UPDATE)
  drug_database.drug_packages           — delete-then-insert by drug product_id per run
  drug_database.drug_active_ingredients — delete-then-insert by drug_id per run
  drug_database.drug_pharm_classes      — delete-then-insert by drug_id per run

Child tables (packages, ingredients, pharm classes) are deleted and re-inserted
within the same run rather than upserted, because their PK is a surrogate int
and the source files provide no stable natural key for update detection.

Batch size: 1,000 rows per INSERT (stream; never loads all rows into memory).

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors in any regex validation (see fda_ndc.py).
LESSON-005: All log extra keys prefixed with ingest_.
Financial precision: numerator_strength uses Decimal(18,6) ROUND_HALF_UP.
No floats anywhere.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.models.ndc_tables import (
    Drug,
    DrugActiveIngredient,
    DrugPackage,
    DrugPharmClass,
    SCHEMA,
)
from shared.data_ingestion.base import IngestionResult
from shared.data_ingestion.sources.fda_ndc import _extract_class_type, _parse_strength

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1_000


class NDCIngestionService:
    """Batch upsert service for FDA NDC Directory data.

    Accepts an iterator of ``{"table": str, "row": dict}`` records produced
    by FDANDCIngester.parse() and writes them to the drug_database schema.
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        *,
        source_name: str = "fda_ndc",
    ) -> IngestionResult:
        """Stream records, group by table, batch-upsert drugs, batch-insert children.

        Returns a partial IngestionResult (run_id is filled by the base class).
        """
        # Accumulate all product_ids that appear in this run so we can
        # delete-then-reinsert child rows efficiently.
        drug_rows: list[dict[str, Any]] = []
        package_rows: list[dict[str, Any]] = []

        records_processed = 0
        records_inserted = 0
        records_updated = 0
        records_errored = 0
        error_samples: list[dict[str, Any]] = []

        # --- Phase 1: Accumulate drug rows; stream packages in batches ---
        for record in records:
            records_processed += 1
            table = record.get("table")
            row = record.get("row", {})

            if table == "drugs":
                drug_rows.append(row)
                if len(drug_rows) >= _BATCH_SIZE:
                    ins, upd, err, smp = self._upsert_drug_batch(drug_rows)
                    records_inserted += ins
                    records_updated += upd
                    records_errored += err
                    error_samples.extend(smp)
                    drug_rows = []

            elif table == "drug_packages":
                package_rows.append(row)

        # Flush remaining drug rows
        if drug_rows:
            ins, upd, err, smp = self._upsert_drug_batch(drug_rows)
            records_inserted += ins
            records_updated += upd
            records_errored += err
            error_samples.extend(smp)

        # COMMIT after Phase 1 (drugs). BUG-01 fix: previously the whole
        # run was a single transaction, so any failure in Phase 3
        # (_insert_packages) called self._db.rollback() and torpedoed the
        # drug rows from Phase 1 — leaving drug_database.drugs empty even
        # when `records_inserted=25,000` was reported. Committing here
        # guarantees the drugs table is durably populated before we
        # attempt the dependent insertions in Phases 2 and 3.
        self._db.commit()

        # --- Phase 2: Explode ingredients + pharm classes for upserted drugs ---
        # We reload drug rows via the session so we have all product_ids that
        # were committed. Now that Phase 1 is durable, any rollback inside
        # this phase is scoped to children, not parents.
        self._reload_children_for_all_drugs(error_samples)
        self._db.commit()

        # --- Phase 3: Upsert packages ---
        # Also isolated from Phases 1 and 2 by the commits above.
        pkg_ins, pkg_err, pkg_smp = self._insert_packages(package_rows)
        records_inserted += pkg_ins
        records_errored += pkg_err
        error_samples.extend(pkg_smp)

        self._db.commit()

        logger.info(
            "NDC ingestion load complete",
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
    # Drug upsert
    # ------------------------------------------------------------------

    def _upsert_drug_batch(
        self, rows: list[dict[str, Any]]
    ) -> tuple[int, int, int, list[dict[str, Any]]]:
        """Upsert a batch of drug rows by product_id.

        Returns (inserted, updated, errored, error_samples).
        """
        now = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        errored = 0
        error_samples: list[dict[str, Any]] = []

        valid_rows: list[dict[str, Any]] = []
        for row in rows:
            try:
                valid_rows.append({**row, "updated_at": now})
            except Exception as exc:
                errored += 1
                if len(error_samples) < 10:
                    error_samples.append({"field": "drug_row", "raw_row": str(row)[:500],
                                          "error": str(exc)[:500]})

        if not valid_rows:
            return inserted, updated, errored, error_samples

        # Use SQLAlchemy Core insert for batch upsert (PostgreSQL ON CONFLICT).
        # BUG-01 fix (per-batch commit): we commit at the END of every drug
        # batch, not at the end of Phase 1. If a LATER batch fails, its
        # self._db.rollback() only affects the in-flight batch — not the
        # already-committed rows from earlier batches. Without this, a single
        # bad row in batch 6 would roll back 25,000 rows from batches 1-5.
        try:
            stmt = pg_insert(Drug.__table__).values(valid_rows)
            update_cols = {
                c.name: stmt.excluded[c.name]
                for c in Drug.__table__.columns
                if c.name not in ("product_id", "created_at")
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["product_id"],
                set_=update_cols,
            )
            result = self._db.execute(stmt)
            self._db.commit()  # durable: this batch is safe from later rollbacks
            # rowcount reflects affected rows (inserted + updated)
            affected = result.rowcount if result.rowcount >= 0 else len(valid_rows)
            inserted += len(valid_rows)  # approximate; exact split not available from rowcount
        except Exception as exc:
            errored += len(valid_rows)
            logger.exception(
                "Drug batch upsert failed",
                extra={"ingest_source": "fda_ndc", "ingest_batch_size": len(valid_rows),
                       "ingest_error": str(exc)[:500]},
            )
            if len(error_samples) < 10:
                error_samples.append({"field": "drug_batch", "raw_row": str(valid_rows[0])[:500],
                                      "error": str(exc)[:500]})
            self._db.rollback()

        return inserted, updated, errored, error_samples

    # ------------------------------------------------------------------
    # Child table reload (ingredients + pharm classes)
    # ------------------------------------------------------------------

    def _reload_children_for_all_drugs(
        self, error_samples: list[dict[str, Any]]
    ) -> None:
        """Delete and re-insert ingredient/pharm class rows for all drugs.

        Processes in batches of _BATCH_SIZE drugs at a time to avoid
        loading everything into memory.
        """
        offset = 0
        while True:
            drug_batch: list[Drug] = (
                self._db.query(Drug)
                .order_by(Drug.product_id)
                .offset(offset)
                .limit(_BATCH_SIZE)
                .all()
            )
            if not drug_batch:
                break

            product_ids = [d.product_id for d in drug_batch]

            # Delete existing children
            self._db.query(DrugActiveIngredient).filter(
                DrugActiveIngredient.drug_id.in_(product_ids)
            ).delete(synchronize_session=False)
            self._db.query(DrugPharmClass).filter(
                DrugPharmClass.drug_id.in_(product_ids)
            ).delete(synchronize_session=False)

            # Re-insert
            ingredient_rows: list[dict[str, Any]] = []
            pharm_class_rows: list[dict[str, Any]] = []
            now = datetime.now(timezone.utc)

            for drug in drug_batch:
                # Explode active ingredients
                if drug.substance_name:
                    substances = [s.strip() for s in drug.substance_name.split(";")]
                    strengths_raw = [
                        s.strip()
                        for s in (drug.active_numerator_strength or "").split(";")
                    ]
                    units_raw = [
                        s.strip()
                        for s in (drug.active_ingred_unit or "").split(";")
                    ]

                    if len(strengths_raw) != len(substances) or len(units_raw) != len(substances):
                        # Mismatch — record error and skip
                        msg = (
                            f"Ingredient length mismatch: substances={len(substances)}, "
                            f"strengths={len(strengths_raw)}, units={len(units_raw)}"
                        )
                        logger.warning(
                            "Ingredient length mismatch — skipping drug",
                            extra={"ingest_source": "fda_ndc",
                                   "ingest_product_id": drug.product_id,
                                   "ingest_mismatch": msg},
                        )
                        if len(error_samples) < 10:
                            error_samples.append({
                                "field": "ingredient_lengths",
                                "raw_row": drug.product_id,
                                "error": msg,
                            })
                    else:
                        for seq, (subst, strength_str, unit_str) in enumerate(
                            zip(substances, strengths_raw, units_raw)
                        ):
                            if not subst:
                                continue
                            ingredient_rows.append({
                                "drug_id": drug.product_id,
                                "sequence": seq,
                                "substance_name": subst,
                                "numerator_strength": _parse_strength(strength_str),
                                "unit": unit_str or None,
                                "created_at": now,
                            })

                # Explode pharm classes
                if drug.pharm_classes:
                    for seq, raw_class in enumerate(drug.pharm_classes.split(",")):
                        raw_class = raw_class.strip()
                        if not raw_class:
                            continue
                        text, ctype = _extract_class_type(raw_class)
                        pharm_class_rows.append({
                            "drug_id": drug.product_id,
                            "sequence": seq,
                            "pharm_class": text,
                            "class_type": ctype,
                            "created_at": now,
                        })

            # Batch insert ingredients
            for i in range(0, len(ingredient_rows), _BATCH_SIZE):
                chunk = ingredient_rows[i : i + _BATCH_SIZE]
                if chunk:
                    self._db.execute(DrugActiveIngredient.__table__.insert(), chunk)

            # Batch insert pharm classes
            for i in range(0, len(pharm_class_rows), _BATCH_SIZE):
                chunk = pharm_class_rows[i : i + _BATCH_SIZE]
                if chunk:
                    self._db.execute(DrugPharmClass.__table__.insert(), chunk)

            self._db.flush()
            offset += _BATCH_SIZE

    # ------------------------------------------------------------------
    # Package upsert
    # ------------------------------------------------------------------

    def _insert_packages(
        self, rows: list[dict[str, Any]]
    ) -> tuple[int, int, list[dict[str, Any]]]:
        """Upsert package rows by ndc_package_code_11.

        Returns (inserted, errored, error_samples).
        """
        now = datetime.now(timezone.utc)
        inserted = 0
        errored = 0
        error_samples: list[dict[str, Any]] = []

        for i in range(0, len(rows), _BATCH_SIZE):
            chunk = rows[i : i + _BATCH_SIZE]
            # De-duplicate within batch by ndc_package_code_11 — real FDA data
            # contains same NDC under multiple SPL document IDs; ON CONFLICT
            # cannot handle duplicate conflict keys inside one INSERT statement
            # (CardinalityViolation). Keep the last row (most-recent source order).
            deduped: dict[str, dict[str, Any]] = {}
            for r in chunk:
                key = r.get("ndc_package_code_11")
                if key is None:
                    continue
                deduped[key] = r
            enriched = [{**r, "created_at": now} for r in deduped.values()]
            if not enriched:
                continue
            try:
                stmt = pg_insert(DrugPackage.__table__).values(enriched)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ndc_package_code_11"],
                    set_={
                        c.name: stmt.excluded[c.name]
                        for c in DrugPackage.__table__.columns
                        if c.name not in ("id", "created_at")
                    },
                )
                self._db.execute(stmt)
                self._db.commit()  # per-batch durability (BUG-01)
                inserted += len(enriched)
            except Exception as exc:
                errored += len(enriched)
                logger.exception(
                    "Package batch upsert failed",
                    extra={"ingest_source": "fda_ndc", "ingest_batch_size": len(enriched),
                           "ingest_error": str(exc)[:500]},
                )
                if len(error_samples) < 10:
                    error_samples.append({
                        "field": "package_batch",
                        "raw_row": str(enriched[0])[:500],
                        "error": str(exc)[:500],
                    })
                self._db.rollback()

        return inserted, errored, error_samples


__all__ = ["NDCIngestionService"]
