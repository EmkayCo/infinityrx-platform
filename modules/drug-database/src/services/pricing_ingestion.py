"""NADAC + ASP pricing ingestion services, wired through BatchedUpserter.

This file used to hand-roll per-batch commits, in-batch dedup, ON CONFLICT
upserts, and history-row emission in ~500 lines of boilerplate — one copy for
NADAC, another near-identical copy for ASP. Bugs in that boilerplate showed
up as BUG-01, 02, 03, 03a, 05. All of that machinery has moved to
``shared.data_ingestion.batching.BatchedUpserter`` + ``HistoryConfig``.

Each service now just declares:
  - how to validate / normalise a raw parsed dict (``_validate_*_row``)
  - how to build the corresponding history row (``_build_*_history_row``)
  - how to detect whether a current row has changed (``_*_changed``)

…and delegates execution to :class:`BatchedUpserter`.

Data rules (non-negotiable):
  - All price columns: Decimal(18, 6) with ROUND_HALF_UP. Never float.
  - Convert source values via Decimal(str(value)) — NEVER Decimal(float).
  - Regex patterns use \\A...\\Z anchors (LESSON-004).
  - Log extra keys prefixed with ingest_ (LESSON-005).
  - Global reference data — no TenantScopedMixin (LESSON-011).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from shared.data_ingestion.base import IngestionResult
from shared.data_ingestion.batching import BatchedUpserter, HistoryConfig
from shared.data_ingestion.parsers import parse_decimal, strip_or_none
from src.models.pricing_tables import (
    DrugASPPricing,
    DrugASPPricingHistory,
    DrugNADACPricing,
    DrugNADACPricingHistory,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1_000

# LESSON-004: \A...\Z anchors only — never ^...$
_NDC_11_RE = re.compile(r"\A\d{11}\Z")
_HCPCS_RE = re.compile(r"\A[A-Z0-9]{5}\Z")
_QUARTER_RE = re.compile(r"\A\d{4}Q[1-4]\Z")

# BUG-03a (2026-04-15): CMS NADAC legitimately publishes comma-separated
# multi-value explanation codes ("1, 3, 4, 5"). The prior pattern
# \A[A-Za-z0-9\-]{0,10}\Z rejected 478,354 rows in a 2M-row source —
# confirmed as the sole cause via diagnostic error bucketing. Widened to
# accept commas, spaces, and up to 30 chars (actual max observed: 7).
_VALID_EXPLANATION_CODE_RE = re.compile(r"\A[A-Za-z0-9,\s\-]{0,30}\Z")


def _require_decimal(value: Any, field_name: str) -> Decimal:
    result = parse_decimal(value, quantize="0.000001")
    if result is None:
        raise ValueError(f"Required Decimal field '{field_name}' missing/invalid: {value!r}")
    return result


# ---------------------------------------------------------------------------
# NADAC ingestion service
# ---------------------------------------------------------------------------


class NADACIngestionService:
    """Batch upsert service for CMS NADAC pricing data.

    Delegates the batching, commit, dedup, and history-tracking logic to
    :class:`BatchedUpserter`. Preserves ``_validate_nadac_row`` for external
    callers/tests that want to unit-test validation in isolation.
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    # -- Public surface ------------------------------------------------

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        *,
        source_name: str = "cms_nadac",
    ) -> IngestionResult:
        """Stream and upsert NADAC records through :class:`BatchedUpserter`."""
        upserter = BatchedUpserter(
            db=self._db,
            source_name=source_name,
            table=DrugNADACPricing.__table__,
            unique_key=["ndc_11"],
            validate=self._validate_nadac_row,
            history=HistoryConfig(
                table=DrugNADACPricingHistory.__table__,
                unique_key=["ndc_11", "effective_date", "as_of_date"],
                build_history_row=self._build_nadac_history_row,
                change_detector=self._nadac_changed,
            ),
            batch_size=_BATCH_SIZE,
        )
        return upserter.load(records)

    # -- Row validation (public for test visibility) ------------------

    def _validate_nadac_row(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalise + validate one NADAC row. Raises ValueError on reject.

        The input dict is whatever ``CMSNADACIngester.parse()`` yielded —
        ``ndc_11`` already normalised to 11 digits, dates already parsed to
        ``date`` objects.
        """
        ndc_11 = str(raw.get("ndc_11") or "").strip()
        if not _NDC_11_RE.match(ndc_11):
            raise ValueError(f"Invalid ndc_11: {ndc_11!r}")

        nadac_per_unit = _require_decimal(raw.get("nadac_per_unit"), "nadac_per_unit")

        explanation_code = strip_or_none(raw.get("explanation_code"))
        if explanation_code and not _VALID_EXPLANATION_CODE_RE.match(explanation_code):
            raise ValueError(f"Invalid explanation_code: {explanation_code!r}")

        effective_date = raw.get("effective_date")
        as_of_date = raw.get("as_of_date")
        if effective_date is None or as_of_date is None:
            raise ValueError("effective_date and as_of_date are required")

        return {
            "ndc_11": ndc_11,
            "ndc_description": strip_or_none(raw.get("ndc_description")),
            "nadac_per_unit": nadac_per_unit,
            "effective_date": effective_date,
            "pricing_unit": strip_or_none(raw.get("pricing_unit")),
            "pharmacy_type_indicator": strip_or_none(raw.get("pharmacy_type_indicator")),
            "otc": strip_or_none(raw.get("otc")),
            "explanation_code": explanation_code,
            "classification": strip_or_none(raw.get("classification")),
            "generic_nadac_per_unit": parse_decimal(
                raw.get("generic_nadac_per_unit"), quantize="0.000001"
            ),
            "generic_effective_date": raw.get("generic_effective_date"),
            "as_of_date": as_of_date,
        }

    # -- History helpers ----------------------------------------------

    @staticmethod
    def _build_nadac_history_row(row: dict[str, Any]) -> dict[str, Any]:
        """Translate a current-table row into its history-table counterpart."""
        return {
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
        }

    @staticmethod
    def _nadac_changed(prev: dict[str, Any], new: dict[str, Any]) -> bool:
        """A history row is emitted only if price or effective_date changed."""
        return (
            prev.get("nadac_per_unit") != new["nadac_per_unit"]
            or prev.get("effective_date") != new["effective_date"]
        )


# ---------------------------------------------------------------------------
# ASP ingestion service
# ---------------------------------------------------------------------------


class ASPIngestionService:
    """Batch upsert service for CMS ASP pricing data.

    Same shape as :class:`NADACIngestionService`: validation + history
    configuration delegated to :class:`BatchedUpserter`.
    """

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    async def load_records(
        self,
        records: Iterator[dict[str, Any]],
        *,
        source_name: str = "cms_asp",
    ) -> IngestionResult:
        upserter = BatchedUpserter(
            db=self._db,
            source_name=source_name,
            table=DrugASPPricing.__table__,
            unique_key=["hcpcs_code"],
            validate=self._validate_asp_row,
            history=HistoryConfig(
                table=DrugASPPricingHistory.__table__,
                unique_key=["hcpcs_code", "effective_quarter"],
                build_history_row=self._build_asp_history_row,
                change_detector=self._asp_changed,
            ),
            batch_size=_BATCH_SIZE,
        )
        return upserter.load(records)

    def _validate_asp_row(self, raw: dict[str, Any]) -> dict[str, Any]:
        hcpcs_code = str(raw.get("hcpcs_code") or "").strip().upper()
        if not _HCPCS_RE.match(hcpcs_code):
            raise ValueError(f"Invalid hcpcs_code: {hcpcs_code!r}")

        payment_limit = _require_decimal(raw.get("payment_limit"), "payment_limit")

        effective_quarter = str(raw.get("effective_quarter") or "").strip()
        if not _QUARTER_RE.match(effective_quarter):
            raise ValueError(
                f"Invalid effective_quarter (expected YYYYQn): {effective_quarter!r}"
            )

        vaccine_awp = strip_or_none(raw.get("vaccine_awp"))
        if vaccine_awp and vaccine_awp not in ("Y", "N"):
            vaccine_awp = None  # tolerate unexpected values gracefully

        return {
            "hcpcs_code": hcpcs_code,
            "short_description": strip_or_none(raw.get("short_description")),
            "dosage": strip_or_none(raw.get("dosage")),
            "payment_limit": payment_limit,
            "vaccine_awp": vaccine_awp,
            "effective_quarter": effective_quarter,
        }

    @staticmethod
    def _build_asp_history_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "hcpcs_code": row["hcpcs_code"],
            "short_description": row.get("short_description"),
            "dosage": row.get("dosage"),
            "payment_limit": row["payment_limit"],
            "vaccine_awp": row.get("vaccine_awp"),
            "effective_quarter": row["effective_quarter"],
        }

    @staticmethod
    def _asp_changed(prev: dict[str, Any], new: dict[str, Any]) -> bool:
        """A history row is emitted only when the effective_quarter changes."""
        return prev.get("effective_quarter") != new["effective_quarter"]


__all__ = ["ASPIngestionService", "NADACIngestionService"]
