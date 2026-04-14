"""MAC list (Maximum Allowable Cost) CSV upload service.

Parses tenant-uploaded CSV files into TenantPricingOverride records.
Validates: NDC format, price > 0, effective_date present, no duplicate NDC+type.
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from src.utils.ndc import InvalidNDCError, normalize_ndc

logger = logging.getLogger(__name__)

_DATA_SOURCE = "tenant_mac"


class MACListError(ValueError):
    """Raised when a MAC list CSV contains validation errors."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(f"MAC list validation failed with {len(errors)} error(s)")


def parse_mac_list_csv(
    csv_content: str,
    tenant_id: uuid.UUID,
    price_type: str = "MAC",
) -> list[dict[str, Any]]:
    """Parse a tenant MAC list CSV into TenantPricingOverride dicts.

    Expected columns: ndc, price_per_unit, effective_date, [unit_type], [termination_date]

    Raises MACListError if any rows have validation errors (reports ALL errors,
    not just the first).
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)

    errors: list[dict[str, Any]] = []
    seen_ndcs: set[str] = set()
    results: list[dict[str, Any]] = []

    for row_num, row in enumerate(rows, start=2):  # row 1 = header
        row_errors: list[str] = []

        # Validate NDC
        raw_ndc = (row.get("ndc") or "").strip()
        try:
            ndc_11 = normalize_ndc(raw_ndc)
        except InvalidNDCError as e:
            row_errors.append(f"Invalid NDC: {e}")
            ndc_11 = None

        # Validate price
        price_str = (row.get("price_per_unit") or "").strip()
        try:
            price = Decimal(price_str).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            if price <= Decimal("0"):
                row_errors.append("price_per_unit must be > 0")
                price = None
        except (InvalidOperation, ValueError):
            row_errors.append(f"Invalid price_per_unit: {price_str!r}")
            price = None

        # Validate effective_date
        eff_date = _parse_date(row.get("effective_date", ""))
        if eff_date is None:
            row_errors.append("effective_date is required (YYYY-MM-DD)")

        # Check duplicate NDC within this upload
        if ndc_11 is not None:
            if ndc_11 in seen_ndcs:
                row_errors.append(f"Duplicate NDC in upload: {ndc_11}")
            else:
                seen_ndcs.add(ndc_11)

        if row_errors:
            errors.append({"row": row_num, "errors": row_errors})
            continue

        termination_date = _parse_date(row.get("termination_date", ""))
        results.append({
            "tenant_id": tenant_id,
            "ndc_11": ndc_11,
            "price_type": price_type,
            "price_per_unit": price,
            "unit_type": row.get("unit_type") or None,
            "effective_date": eff_date,
            "termination_date": termination_date,
            "data_source": _DATA_SOURCE,
        })

    if errors:
        raise MACListError(errors)

    return results


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val).strip()[:10])
    except (ValueError, TypeError):
        return None
