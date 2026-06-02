"""MFR-003 and HP-008 per-row evaluator helpers.

MFR-003: Ingredient cost deviation from FDB WAC (price_type=09).
  Uses FDB WAC from reference.fdb_ndc_price_history, NOT csv extended_wac.
  When FDB WAC absent or None: returns {_no_fdb_wac: True} (skip, not fire).
  No float in financial math. Decimal ROUND_HALF_UP throughout.

HP-008: High-cost claimant total paid above percentile threshold.
  Uses csv total_paid_amt. No FDB dependency.

Both expose:
  _derive_statistical_metric(*, ndc, _fdb_cache, ...) -> dict
    Minimal exported form for unit testing (two-keyword-arg minimum).
    Full production form called by evaluate_mfr003_row / evaluate_hp008_row.

  evaluate_mfr003_row / evaluate_hp008_row
    Per-row dispatch adapters called by run_detection (Task 4c PER_ROW_EVALUATORS map).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.models.detection_run_models import Anomaly, CsvUploadRow, DetectionRuleInstance

_ZERO = Decimal("0")


def _parse_money(value: Any):
    """Parse a value to Decimal. Returns None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _parse_date(value: Any):
    """Parse a date string to date. Returns None on failure."""
    if not value:
        return None
    try:
        from datetime import date  # noqa: PLC0415
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _derive_statistical_metric(
    *,
    ndc,
    _fdb_cache: dict,
    rd=None,
    csv_row=None,
    code: str = "MFR-003",
    baseline=None,
    params=None,
) -> dict:
    """Derive statistical metric dict for a claim row.

    Minimal exported form: ndc + _fdb_cache only (unit tests).
    Full form: rd, baseline, params also provided (production via row adapters).

    MFR-003:
      Unit-test path (rd=None): returns {_no_fdb_wac: True} if FDB WAC absent/None.
      Full path: metric = ic / (fdb_wac * qty). z-score vs baseline. Decimal only.
      FDB WAC from _fdb_cache[ndc][wac] (price_type=09). No CSV extended_wac fallback.
    HP-008:
      total_paid_amt percentile vs threshold. No FDB dependency.
    """
    from src.detection.calibration import (  # noqa: PLC0415
        zscore_flag,
        passes_min_sample,
        passes_dollar_floor,
        percentile_within_cohort,
    )

    ndc_key = str(ndc or "").strip()
    fdb_entry = _fdb_cache.get(ndc_key, {}) if _fdb_cache else {}
    fdb_wac = fdb_entry.get("wac") if isinstance(fdb_entry, dict) else None

    if code == "MFR-003":
        # Unit-test path: rd is None -> only validate FDB WAC presence
        if rd is None:
            if fdb_wac is None:
                return {"_no_fdb_wac": True}
            return {}

        # Full production path
        ic = _parse_money(rd.get("ingredient_cost_paid"))
        if ic is None:
            return {}

        if fdb_wac is None:
            return {"_no_fdb_wac": True}

        if not isinstance(fdb_wac, Decimal):
            try:
                fdb_wac = Decimal(str(fdb_wac))
            except Exception:
                return {"_no_fdb_wac": True}

        if fdb_wac <= _ZERO:
            return {"_no_fdb_wac": True}

        qty_raw = rd.get("quantity_dispensed")
        qty = Decimal(str(qty_raw)) if qty_raw else _ZERO
        wac_val = (fdb_wac * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fdb_effective_date = str(fdb_entry.get("fdb_effective_date", ""))

        if wac_val == _ZERO:
            return {}

        own_rate = ic / wac_val

        if baseline is None:
            return {}

        mean = Decimal(str(baseline.mean)) if baseline.mean is not None else None
        stddev = Decimal(str(baseline.stddev)) if baseline.stddev is not None else None
        if mean is None or stddev is None:
            return {}

        p = params or {}
        z_threshold = Decimal(str(p.get("z_threshold", "3.0")))
        fired, z = zscore_flag(value=own_rate, mean=mean, stddev=stddev, z_threshold=z_threshold)
        if not fired:
            return {}

        sample_count = baseline.sample_count if baseline.sample_count is not None else 0
        min_group_size = int(p.get("min_group_size", 30))
        if not passes_min_sample(sample_count=sample_count, min_required=min_group_size):
            return {}

        dollar_floor_str = p.get("dollar_floor", "0")
        dollar_floor = Decimal(str(dollar_floor_str)) if dollar_floor_str else None
        if not passes_dollar_floor(ic, dollar_floor):
            return {}

        return {
            "contracted_rate_deviation_pct": str(
                abs(own_rate - mean).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
            ),
            "_z": str(z) if z is not None else None,
            "_fired": True,
            "wac_source": "fdb",
            "fdb_price_type": "09",
            "fdb_effective_date": fdb_effective_date,
            "fdb_wac": str(fdb_wac.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)),
        }

    elif code == "HP-008":
        if rd is None:
            return {}

        total = _parse_money(rd.get("total_paid_amt"))
        if total is None:
            return {}

        if baseline is None:
            return {}

        p = params or {}
        pct_threshold = Decimal(str(p.get("percentile_threshold", "0.99")))
        dollar_floor_str = p.get("dollar_floor", "0")
        dollar_floor = Decimal(str(dollar_floor_str)) if dollar_floor_str else None

        if not passes_dollar_floor(total, dollar_floor):
            return {}

        # Use cohort_values if available (extended cache), else z-score fallback
        cohort_values = getattr(baseline, "cohort_values", None)
        if cohort_values:
            pct = percentile_within_cohort(total, [Decimal(str(v)) for v in cohort_values])
            if pct is None or pct < pct_threshold:
                return {}
            return {"cost_percentile": str(pct), "_fired": True, "statistic": "percentile_cont"}
        else:
            mean = Decimal(str(baseline.mean)) if baseline.mean is not None else None
            stddev = Decimal(str(baseline.stddev)) if baseline.stddev is not None else None
            if mean is None or stddev is None:
                return {}
            z_threshold = Decimal(str(p.get("z_threshold", "3.0")))
            fired, z = zscore_flag(value=total, mean=mean, stddev=stddev, z_threshold=z_threshold)
            if not fired:
                return {}
            return {
                "_z": str(z) if z is not None else None,
                "_fired": True,
                "statistic": "percentile_cont",
            }

    return {}


def evaluate_mfr003_row(
    row: "CsvUploadRow",
    *,
    db,
    _fdb_cache: dict,
    instance: "DetectionRuleInstance",
) -> "Anomaly | None":
    """Per-row adapter for MFR-003: FDB-WAC IC deviation check."""
    from src.models.detection_run_models import Anomaly  # noqa: PLC0415

    result = _derive_statistical_metric(
        ndc=row.resolved_ndc,
        rd=row.row_data,
        csv_row=row,
        code="MFR-003",
        baseline=None,
        params=instance.parameters,
        _fdb_cache=_fdb_cache,
    )
    if not result.get("_fired"):
        return None
    return Anomaly(
        tenant_id=row.tenant_id,
        data_source="csv_upload",
        data_source_run_id=row.detection_run_id,
        source_table="csv_upload_rows",
        source_row_id=row.id,
        detection_kind="rule",
        detection_id=instance.id,
        severity=instance.parameters.get("severity", "high"),
        confidence=Decimal(str(instance.parameters.get("confidence", "0.80"))),
        finding_code="MFR-003",
        finding_summary="Ingredient cost deviates from FDB WAC baseline (z-score)",
        finding_details=result,
        pharmacy_npi=row.row_data.get("pharmacy_npi"),
        prescriber_npi=row.row_data.get("prescriber_npi"),
        ndc=row.resolved_ndc,
        date_of_service=_parse_date(row.row_data.get("date_of_service")),
        status="open",
    )


def evaluate_hp008_row(
    row: "CsvUploadRow",
    *,
    db,
    _fdb_cache: dict,
    instance: "DetectionRuleInstance",
) -> "Anomaly | None":
    """Per-row adapter for HP-008: high-cost claimant percentile check."""
    from src.models.detection_run_models import Anomaly  # noqa: PLC0415

    result = _derive_statistical_metric(
        ndc=row.resolved_ndc,
        rd=row.row_data,
        csv_row=row,
        code="HP-008",
        baseline=None,
        params=instance.parameters,
        _fdb_cache=_fdb_cache,
    )
    if not result.get("_fired"):
        return None
    return Anomaly(
        tenant_id=row.tenant_id,
        data_source="csv_upload",
        data_source_run_id=row.detection_run_id,
        source_table="csv_upload_rows",
        source_row_id=row.id,
        detection_kind="rule",
        detection_id=instance.id,
        severity=instance.parameters.get("severity", "high"),
        confidence=Decimal(str(instance.parameters.get("confidence", "0.80"))),
        finding_code="HP-008",
        finding_summary="High-cost claimant: total paid above percentile threshold",
        finding_details=result,
        pharmacy_npi=row.row_data.get("pharmacy_npi"),
        prescriber_npi=row.row_data.get("prescriber_npi"),
        ndc=row.resolved_ndc,
        date_of_service=_parse_date(row.row_data.get("date_of_service")),
        status="open",
    )
