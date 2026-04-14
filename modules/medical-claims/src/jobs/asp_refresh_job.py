"""Quarterly CMS ASP pricing refresh job.

CMS publishes updated ASP files quarterly. This job loads new pricing data
into asp_pricing table. In production, downloads from CMS data.cms.gov.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.services.pricing_service import PricingService, quarter_for_date
from src.utils.validators import is_valid_quarter

logger = logging.getLogger(__name__)


class AspRefreshJob:
    """Loads CMS ASP quarterly pricing into asp_pricing table."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._pricing_svc = PricingService(db)

    def run(self, quarter: str, records: list[dict[str, Any]]) -> dict[str, int]:
        """Load ASP records for a quarter.

        Each record: {hcpcs_code, asp_per_unit, effective_date, hcpcs_description?}

        Returns {"loaded": N, "skipped": N}
        """
        if not is_valid_quarter(quarter):
            raise ValueError(f"Invalid quarter format: {quarter}. Expected YYYY-Q1..Q4")

        loaded = 0
        skipped = 0

        for row in records:
            try:
                hcpcs_code = row.get("hcpcs_code", "").strip().upper()
                if not hcpcs_code:
                    skipped += 1
                    continue

                asp_per_unit_raw = row.get("asp_per_unit")
                if asp_per_unit_raw is None:
                    skipped += 1
                    continue

                asp_per_unit = Decimal(str(asp_per_unit_raw))
                effective_date_raw = row.get("effective_date")
                if isinstance(effective_date_raw, date):
                    effective_date = effective_date_raw
                elif isinstance(effective_date_raw, str):
                    effective_date = date.fromisoformat(effective_date_raw)
                else:
                    effective_date = date.today()

                self._pricing_svc.upsert_asp(
                    hcpcs_code=hcpcs_code,
                    quarter=quarter,
                    effective_date=effective_date,
                    asp_per_unit=asp_per_unit,
                    hcpcs_description=row.get("hcpcs_description"),
                )
                loaded += 1

            except Exception as exc:
                logger.warning(
                    "ASP record load failed",
                    extra={"svc_row": str(row), "svc_error": str(exc)},
                )
                skipped += 1

        logger.info(
            "ASP refresh complete",
            extra={"svc_quarter": quarter, "svc_loaded": loaded, "svc_skipped": skipped},
        )
        return {"loaded": loaded, "skipped": skipped}
