"""Report execution engine: definition, execution, output formatting."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from src.utils.constants import (
    ALL_CATEGORIES,
    CSV_MAX_ROWS,
    CSV_WARN_ROWS,
    EXCEL_MAX_ROWS,
    EXCEL_WARN_ROWS,
    FORMAT_CSV,
    FORMAT_EXCEL,
    FORMAT_PDF,
    PDF_MAX_PAGES,
    PDF_WARN_PAGES,
    PHI_FULL_DETAIL,
    PHI_PARTIAL,
    PHI_REDACTED,
)


def validate_report_definition(defn: dict[str, Any]) -> list[str]:
    """Validate a report definition; return list of error strings."""
    errors: list[str] = []

    if not defn.get("name"):
        errors.append("name: required")

    category = defn.get("category")
    if not category:
        errors.append("category: required")
    elif category not in ALL_CATEGORIES:
        errors.append(f"category: must be one of {ALL_CATEGORIES}")

    if not defn.get("data_source"):
        errors.append("data_source: required")

    columns = defn.get("columns")
    if columns is None:
        errors.append("columns: required")
    elif len(columns) == 0:
        errors.append("columns: must have at least one column")

    return errors


def apply_calculated_fields(
    rows: list[dict[str, Any]],
    calc_fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply calculated/derived fields to each row in the result set."""
    if not rows or not calc_fields:
        return list(rows)

    result = [dict(row) for row in rows]

    for field_def in calc_fields:
        formula = field_def.get("formula")
        name = field_def["name"]

        if formula == "percentage":
            num_key = field_def["numerator"]
            den_key = field_def["denominator"]
            for row in result:
                num = Decimal(str(row.get(num_key, 0)))
                den = Decimal(str(row.get(den_key, 0)))
                if den == Decimal("0"):
                    row[name] = Decimal("0.00")
                else:
                    row[name] = (num / den * Decimal("100")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )

        elif formula == "running_total":
            field_key = field_def["field"]
            running = Decimal("0.00")
            for row in result:
                running += Decimal(str(row.get(field_key, 0)))
                row[name] = running

    return result


def apply_phi_masking(
    row: dict[str, Any],
    masking_level: str,
    phi_fields: list[str] | frozenset[str],
) -> dict[str, Any]:
    """Apply PHI masking to a data row per the specified masking level."""
    _valid = {PHI_FULL_DETAIL, PHI_PARTIAL, PHI_REDACTED}
    if masking_level not in _valid:
        raise ValueError(f"Invalid masking level: {masking_level!r}")

    if masking_level == PHI_FULL_DETAIL:
        return dict(row)

    _partial_masked = frozenset(
        {
            "dob",
            "date_of_birth",
            "address",
            "address_line1",
            "address_line2",
            "phone",
            "phone_number",
            "email",
            "ssn",
        }
    )

    result = dict(row)
    for field in phi_fields:
        if field not in row:
            continue
        if masking_level == PHI_REDACTED:
            result[field] = "[REDACTED]"
        elif masking_level == PHI_PARTIAL and field in _partial_masked:
            result[field] = "[MASKED]"

    return result


def build_report_filter(filters: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate a filter dict, coercing types."""
    result: dict[str, Any] = {}

    for key, value in filters.items():
        if key in ("date_from", "date_to", "date_start", "date_end"):
            try:
                result[key] = date.fromisoformat(str(value))
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid date for {key}: {value!r}") from e
        else:
            result[key] = value

    return result


def estimate_output_size(
    estimated_rows: int,
    output_format: str,
) -> dict[str, Any]:
    """Estimate whether output will trigger size warnings or exceed limits."""
    warning = False
    exceeds_limit = False

    if output_format == FORMAT_EXCEL:
        if estimated_rows >= EXCEL_WARN_ROWS:
            warning = True
        if estimated_rows > EXCEL_MAX_ROWS:
            exceeds_limit = True
    elif output_format == FORMAT_CSV:
        if estimated_rows >= CSV_WARN_ROWS:
            warning = True
        if estimated_rows > CSV_MAX_ROWS:
            exceeds_limit = True
    elif output_format == FORMAT_PDF:
        # PDF: estimate pages as rows / 50 per page
        est_pages = estimated_rows // 50
        if est_pages >= PDF_WARN_PAGES:
            warning = True
        if est_pages > PDF_MAX_PAGES:
            exceeds_limit = True

    return {
        "estimated_rows": estimated_rows,
        "output_format": output_format,
        "warning": warning,
        "exceeds_limit": exceeds_limit,
    }


def format_value(value: Any, fmt_type: str) -> str:
    """Format a single value for display in reports."""
    if value is None:
        return ""

    if fmt_type == "currency":
        d = Decimal(str(value))
        return f"${d:,.2f}"

    if fmt_type == "date":
        if isinstance(value, date):
            return value.strftime("%m/%d/%Y")
        return str(value)

    if fmt_type == "percentage":
        d = Decimal(str(value))
        return f"{d:.2f}%"

    if fmt_type == "integer":
        return f"{int(value):,}"

    return str(value)


class ReportEngine:
    """Orchestrates report definition loading, query execution, and output formatting."""

    def __init__(self, db_session: Any, read_replica_session: Any | None = None) -> None:
        self._db = db_session
        self._replica = read_replica_session or db_session

    def format_row(
        self,
        row: dict[str, Any],
        columns: list[dict[str, Any]],
        masking_level: str = PHI_FULL_DETAIL,
        phi_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Format all fields in a row according to column definitions."""
        phi = phi_fields or []
        masked = apply_phi_masking(row, masking_level, phi)
        result: dict[str, Any] = {}
        col_map = {c["field"]: c for c in columns}
        for field, val in masked.items():
            col_def = col_map.get(field, {})
            fmt = col_def.get("format", "string")
            result[field] = format_value(val, fmt)
        return result

    def apply_summary_row(
        self,
        rows: list[dict[str, Any]],
        summary_config: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Compute a summary row (totals/averages) for a set of result rows."""
        if not summary_config or not rows:
            return None

        summary: dict[str, Any] = {}
        for field, agg in summary_config.items():
            values = [Decimal(str(r[field])) for r in rows if field in r]
            if not values:
                summary[field] = Decimal("0.00")
            elif agg == "sum":
                summary[field] = sum(values, Decimal("0"))
            elif agg == "avg":
                summary[field] = (sum(values, Decimal("0")) / len(values)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            elif agg == "count":
                summary[field] = len(values)
            elif agg == "min":
                summary[field] = min(values)
            elif agg == "max":
                summary[field] = max(values)

        return summary
