"""CMS NADAC weekly pricing file parser.

Parses CMS NADAC CSV into DrugPricing dicts ready for upsert.
Detects price changes against existing prices.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from src.utils.ndc import InvalidNDCError, normalize_ndc

logger = logging.getLogger(__name__)

_PRICE_TYPE = "NADAC"
_DATA_SOURCE = "cms_nadac"


def parse_nadac_csv(csv_content: str) -> list[dict[str, Any]]:
    """Parse CMS NADAC CSV into pricing dicts.

    Returns list of dicts with keys: ndc_11, price_type, price_per_unit,
    unit_type, effective_date, data_source.

    Rows with invalid NDC or non-parseable price are skipped with a warning.
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    results = []

    for row in reader:
        try:
            ndc_11 = normalize_ndc(row.get("ndc", "") or "")
        except InvalidNDCError:
            logger.warning(
                "skipping invalid NADAC NDC",
                extra={"svc_name": "nadac_parser", "raw_ndc": str(row.get("ndc", ""))[:20]},
            )
            continue

        price_str = row.get("nadac_per_unit", "") or row.get("price_per_unit", "")
        try:
            price = Decimal(str(price_str)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            logger.warning(
                "skipping unparseable NADAC price",
                extra={"svc_name": "nadac_parser", "drug_ndc": ndc_11},
            )
            continue

        eff_date = _parse_date(row.get("effective_date", ""))
        if eff_date is None:
            logger.warning(
                "skipping NADAC row — no effective date",
                extra={"svc_name": "nadac_parser", "drug_ndc": ndc_11},
            )
            continue

        results.append({
            "ndc_11": ndc_11,
            "price_type": _PRICE_TYPE,
            "price_per_unit": price,
            "unit_type": row.get("unit_type"),
            "effective_date": eff_date,
            "data_source": _DATA_SOURCE,
        })

    return results


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None
