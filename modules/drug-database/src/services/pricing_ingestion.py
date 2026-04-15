"""Pricing ingestion services for CMS NADAC and ASP data.

Called by shared.data_ingestion.sources.cms_nadac.CMSNADACIngester.load() and
shared.data_ingestion.sources.cms_asp.CMSASPIngester.load().

NADAC service:
  - Upserts drug_database.drug_nadac_pricing by ndc_11 (current row).
  - Inserts into drug_database.drug_nadac_pricing_history ONLY when the
    current row's price or effective_date is actually changing (or the row
    is new). Unique constraint on (ndc_11, effective_date, as_of_date)
    prevents duplicate history rows on re-ingestion.

ASP service:
  - Upserts drug_database.drug_asp_pricing by hcpcs_code (current row).
  - Inserts into drug_database.drug_asp_pricing_history ONLY when the
    effective_quarter changes.  Unique constraint on (hcpcs_code,
    effective_quarter) prevents duplicate history rows on re-ingestion.

Data rules (non-negotiable):
  - All money/price columns: Decimal(18, 6) with ROUND_HALF_UP. Never float.
  - Convert JSON numeric values via Decimal(str(value)) — NEVER Decimal(float).
  - Wrap SQLAlchemy func.sum()/func.avg() in Decimal(str()) per financial rules.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z regex anchors in all validation.
LESSON-005: All log extra keys prefixed with ingest_.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.models.pricing_tables import (
    DrugASPPricing,
    DrugASPPricingHistory,
    DrugNADACPricing,
    DrugNADACPricingHistory,
)
from shared.data_ingestion.base import IngestionResult

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1_000

# LESSON-004: \A...\Z anchors only — never ^...$
_NDC_11_RE = re.compile(r"\A\d{11}\Z")
_HCPCS_RE = re.compile(r"\A[A-Z0-9]{5}\Z")
_QUARTER_RE = re.compile(r"\A\d{4}Q[1-4]\Z")

# Valid NADAC explanation codes. CMS NADAC legitimately publishes
# comma-separated multi-value explanation codes — a single drug row can
# be flagged for multiple reasons simultaneously, e.g. "1, 5" or
# "1, 3, 4, 5". BUG-03a (2026-04-15): the original regex
# `\A[A-Za-z0-9\-]{0,10}\Z` rejected every multi-value row — confirmed
# via diagnostic instrumentation to be the SOLE cause of 478,354 errors
# out of 2,063,346 source rows (23.2% rejection). Widened to allow
# commas, spaces, and up to 30 chars.
_VALID_EXPLANATION_CODE_RE = re.compile(r"\A[A-Za-z0-9,\s\-]{0,30}\Z")


def _parse_decimal(value: Any) -> Decimal | None:
    """Convert a value to Decimal(18,6) ROUND_HALF_UP.

    Accepts str, int, float, or Decimal input.  Always converts via str() to
    avoid IEEE-754 float contamination (financial-precision.md).

    Returns None for empty/None/non-numeric values.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return Decimal(s).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _require_decimal(value: Any, field_name: str) -> Decimal:
    """Like _parse_decimal but raises ValueError for missing/invalid values."""
    result = _parse_decimal(value)
    if result is None:
        raise ValueError(f"Required Decimal field '{field_name}' is missing or invalid: {value!r}")
    return result


# ---------------------------------------------------------------------------
# NADAC ingestion service
# ---------------------------------------------------------------------------


class NADACIngestionService:
    """Batch upsert service for CMS NADAC pricing data.

    Accepts an iterator of dicts produced by CMSNADACIngester.parse() and
    writes them to drug_database.drug_nadac_pricing (current) and
    drug_database.drug_nadac_pricing_history (append-only).
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        *,
        source_name: str = "cms_nadac",
    ) -> IngestionResult:
        """Stream and upsert NADAC records.

        For each record:
          1. Upsert current pricing row by ndc_11.
          2. Insert history row if price or effective_date changed, using
             ON CONFLICT DO NOTHING on (ndc_11, effective_date, as_of_date).
        """
        records_processed = 0
        records_inserted = 0
        records_updated = 0
        records_errored = 0
        error_samples: list[dict[str, Any]] = []

        batch: list[dict[str, Any]] = []

        for raw in records:
            records_processed += 1
            try:
                row = self._validate_nadac_row(raw)
            except ValueError as exc:
                records_errored += 1
                if len(error_samples) < 10:
                    error_samples.append({
                        "field": "nadac_row",
                        "raw_row": str(raw)[:500],
                        "error": str(exc)[:500],
                    })
                continue

            batch.append(row)
            if len(batch) >= _BATCH_SIZE:
                ins, upd, err = self._upsert_batch(batch, error_samples)
                records_inserted += ins
                records_updated += upd
                records_errored += err
                batch = []

        if batch:
            ins, upd, err = self._upsert_batch(batch, error_samples)
            records_inserted += ins
            records_updated += upd
            records_errored += err

        self._db.commit()

        logger.info(
            "NADAC ingestion load complete",
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

    def _validate_nadac_row(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalise a raw NADAC dict from the API.

        Raises ValueError on invalid/missing required fields.
        """
        # NDC normalization handled upstream by CMSNADACIngester.parse()
        ndc_11 = str(raw.get("ndc_11") or "").strip()
        if not _NDC_11_RE.match(ndc_11):
            raise ValueError(f"Invalid ndc_11: {ndc_11!r}")

        nadac_per_unit = _require_decimal(raw.get("nadac_per_unit"), "nadac_per_unit")

        explanation_code = str(raw.get("explanation_code") or "").strip() or None
        if explanation_code and not _VALID_EXPLANATION_CODE_RE.match(explanation_code):
            raise ValueError(f"Invalid explanation_code: {explanation_code!r}")

        return {
            "ndc_11": ndc_11,
            "ndc_description": str(raw.get("ndc_description") or "").strip() or None,
            "nadac_per_unit": nadac_per_unit,
            "effective_date": raw["effective_date"],
            "pricing_unit": str(raw.get("pricing_unit") or "").strip() or None,
            "pharmacy_type_indicator": str(raw.get("pharmacy_type_indicator") or "").strip() or None,
            "otc": str(raw.get("otc") or "").strip() or None,
            "explanation_code": explanation_code,
            "classification": str(raw.get("classification") or "").strip() or None,
            "generic_nadac_per_unit": _parse_decimal(raw.get("generic_nadac_per_unit")),
            "generic_effective_date": raw.get("generic_effective_date"),
            "as_of_date": raw["as_of_date"],
        }

    def _upsert_batch(
        self,
        rows: list[dict[str, Any]],
        error_samples: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        """Upsert a batch of validated NADAC rows.

        Returns (inserted, updated, errored).
        """
        now = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        errored = 0

        # For history rows we need to know which ndc_11s existed before the upsert.
        # Fetch existing rows in a single IN query for the batch.
        ndc_keys = [r["ndc_11"] for r in rows]
        existing: dict[str, tuple[Decimal, Any]] = {}
        try:
            for row_obj in (
                self._db.query(DrugNADACPricing)
                .filter(DrugNADACPricing.ndc_11.in_(ndc_keys))
                .all()
            ):
                existing[row_obj.ndc_11] = (row_obj.nadac_per_unit, row_obj.effective_date)
        except Exception as exc:
            logger.warning(
                "Could not pre-fetch existing NADAC rows",
                extra={"ingest_source": "cms_nadac", "ingest_error": str(exc)[:300]},
            )

        enriched = [{**r, "updated_at": now} for r in rows]
        try:
            stmt = pg_insert(DrugNADACPricing.__table__).values(enriched)
            update_cols = {
                c.name: stmt.excluded[c.name]
                for c in DrugNADACPricing.__table__.columns
                if c.name not in ("ndc_11", "created_at")
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["ndc_11"],
                set_=update_cols,
            )
            self._db.execute(stmt)

            for r in rows:
                ndc = r["ndc_11"]
                prev = existing.get(ndc)
                if prev is None:
                    # New row
                    inserted += 1
                    self._insert_history_row(r)
                else:
                    prev_price, prev_eff_date = prev
                    price_changed = prev_price != r["nadac_per_unit"]
                    eff_changed = prev_eff_date != r["effective_date"]
                    if price_changed or eff_changed:
                        updated += 1
                        self._insert_history_row(r)
                    # else: no change — no history row

            # BUG-03 fix: per-batch commit. Previously the whole run
            # accumulated in a single transaction so a late failure
            # wiped earlier batches AND progress was invisible until
            # the very end.
            self._db.commit()

        except Exception as exc:
            errored += len(rows)
            logger.exception(
                "NADAC batch upsert failed",
                extra={
                    "ingest_source": "cms_nadac",
                    "ingest_batch_size": len(rows),
                    "ingest_error": str(exc)[:500],
                },
            )
            if len(error_samples) < 10:
                error_samples.append({
                    "field": "nadac_batch",
                    "raw_row": str(rows[0])[:500],
                    "error": str(exc)[:500],
                })
            self._db.rollback()

        return inserted, updated, errored

    def _insert_history_row(self, row: dict[str, Any]) -> None:
        """Insert a NADAC history row — ON CONFLICT DO NOTHING prevents duplicates."""
        now = datetime.now(timezone.utc)
        hist_row = {
            "ndc_11": row["ndc_11"],
            "ndc_description": row.get("ndc_description"),
            "nadac_per_unit": row["nadac_per_unit"],
            "effective_date": row["effective_date"],
            "pricing_unit": row.get("pricing_unit"),
            "pharmacy_type_indicator": row.get("pharmacy_type_indicator"),
            "otc": row.get("otc"),
            "explanation_code": row.get("explanation_code"),
            "classification": row.get("classification"),
            "generic_nadac_per_unit": row.get("generic_nadac_per_unit"),
            "generic_effective_date": row.get("generic_effective_date"),
            "as_of_date": row["as_of_date"],
            "created_at": now,
        }
        try:
            stmt = pg_insert(DrugNADACPricingHistory.__table__).values([hist_row])
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["ndc_11", "effective_date", "as_of_date"],
            )
            self._db.execute(stmt)
            self._db.flush()
        except Exception as exc:
            logger.warning(
                "NADAC history insert failed",
                extra={
                    "ingest_source": "cms_nadac",
                    "ingest_ndc_11": row["ndc_11"],
                    "ingest_error": str(exc)[:300],
                },
            )


# ---------------------------------------------------------------------------
# ASP ingestion service
# ---------------------------------------------------------------------------


class ASPIngestionService:
    """Batch upsert service for CMS ASP pricing data.

    Accepts an iterator of dicts produced by CMSASPIngester.parse() and
    writes them to drug_database.drug_asp_pricing (current) and
    drug_database.drug_asp_pricing_history (append-only).
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        *,
        source_name: str = "cms_asp",
    ) -> IngestionResult:
        """Stream and upsert ASP records."""
        records_processed = 0
        records_inserted = 0
        records_updated = 0
        records_errored = 0
        error_samples: list[dict[str, Any]] = []

        batch: list[dict[str, Any]] = []

        for raw in records:
            records_processed += 1
            try:
                row = self._validate_asp_row(raw)
            except ValueError as exc:
                records_errored += 1
                if len(error_samples) < 10:
                    error_samples.append({
                        "field": "asp_row",
                        "raw_row": str(raw)[:500],
                        "error": str(exc)[:500],
                    })
                continue

            batch.append(row)
            if len(batch) >= _BATCH_SIZE:
                ins, upd, err = self._upsert_batch(batch, error_samples)
                records_inserted += ins
                records_updated += upd
                records_errored += err
                batch = []

        if batch:
            ins, upd, err = self._upsert_batch(batch, error_samples)
            records_inserted += ins
            records_updated += upd
            records_errored += err

        self._db.commit()

        logger.info(
            "ASP ingestion load complete",
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

    def _validate_asp_row(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalise a raw ASP dict.

        Raises ValueError on invalid/missing required fields.
        """
        hcpcs_code = str(raw.get("hcpcs_code") or "").strip().upper()
        if not _HCPCS_RE.match(hcpcs_code):
            raise ValueError(f"Invalid hcpcs_code: {hcpcs_code!r}")

        payment_limit = _require_decimal(raw.get("payment_limit"), "payment_limit")

        effective_quarter = str(raw.get("effective_quarter") or "").strip()
        if not _QUARTER_RE.match(effective_quarter):
            raise ValueError(
                f"Invalid effective_quarter (expected YYYYQn): {effective_quarter!r}"
            )

        vaccine_awp_raw = str(raw.get("vaccine_awp") or "").strip() or None
        if vaccine_awp_raw and vaccine_awp_raw not in ("Y", "N"):
            vaccine_awp_raw = None  # tolerate unexpected values gracefully

        return {
            "hcpcs_code": hcpcs_code,
            "short_description": str(raw.get("short_description") or "").strip() or None,
            "dosage": str(raw.get("dosage") or "").strip() or None,
            "payment_limit": payment_limit,
            "vaccine_awp": vaccine_awp_raw,
            "effective_quarter": effective_quarter,
        }

    def _upsert_batch(
        self,
        rows: list[dict[str, Any]],
        error_samples: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        """Upsert a batch of validated ASP rows.

        Returns (inserted, updated, errored).
        """
        now = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        errored = 0

        hcpcs_keys = [r["hcpcs_code"] for r in rows]
        existing: dict[str, str] = {}
        try:
            for row_obj in (
                self._db.query(DrugASPPricing)
                .filter(DrugASPPricing.hcpcs_code.in_(hcpcs_keys))
                .all()
            ):
                existing[row_obj.hcpcs_code] = row_obj.effective_quarter
        except Exception as exc:
            logger.warning(
                "Could not pre-fetch existing ASP rows",
                extra={"ingest_source": "cms_asp", "ingest_error": str(exc)[:300]},
            )

        enriched = [{**r, "updated_at": now} for r in rows]
        try:
            stmt = pg_insert(DrugASPPricing.__table__).values(enriched)
            update_cols = {
                c.name: stmt.excluded[c.name]
                for c in DrugASPPricing.__table__.columns
                if c.name not in ("hcpcs_code", "created_at")
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["hcpcs_code"],
                set_=update_cols,
            )
            self._db.execute(stmt)
            self._db.flush()

            for r in rows:
                hcpcs = r["hcpcs_code"]
                prev_quarter = existing.get(hcpcs)
                if prev_quarter is None:
                    inserted += 1
                    self._insert_history_row(r)
                elif prev_quarter != r["effective_quarter"]:
                    updated += 1
                    self._insert_history_row(r)
                # else: same quarter re-ingested — no history row

        except Exception as exc:
            errored += len(rows)
            logger.exception(
                "ASP batch upsert failed",
                extra={
                    "ingest_source": "cms_asp",
                    "ingest_batch_size": len(rows),
                    "ingest_error": str(exc)[:500],
                },
            )
            if len(error_samples) < 10:
                error_samples.append({
                    "field": "asp_batch",
                    "raw_row": str(rows[0])[:500],
                    "error": str(exc)[:500],
                })
            self._db.rollback()

        return inserted, updated, errored

    def _insert_history_row(self, row: dict[str, Any]) -> None:
        """Insert an ASP history row — ON CONFLICT DO NOTHING prevents duplicates."""
        now = datetime.now(timezone.utc)
        hist_row = {
            "hcpcs_code": row["hcpcs_code"],
            "short_description": row.get("short_description"),
            "dosage": row.get("dosage"),
            "payment_limit": row["payment_limit"],
            "vaccine_awp": row.get("vaccine_awp"),
            "effective_quarter": row["effective_quarter"],
            "created_at": now,
        }
        try:
            stmt = pg_insert(DrugASPPricingHistory.__table__).values([hist_row])
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["hcpcs_code", "effective_quarter"],
            )
            self._db.execute(stmt)
            self._db.flush()
        except Exception as exc:
            logger.warning(
                "ASP history insert failed",
                extra={
                    "ingest_source": "cms_asp",
                    "ingest_hcpcs_code": row["hcpcs_code"],
                    "ingest_error": str(exc)[:300],
                },
            )


__all__ = ["NADACIngestionService", "ASPIngestionService"]
