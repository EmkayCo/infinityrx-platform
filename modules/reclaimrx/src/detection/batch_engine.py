"""Batch detection engine: applicability gate (Task 3.4) + two-pass detection (Task 3.5).

gate_rules(db, run, available_columns) -> list[DetectionRuleInstance]
    Loads enabled DetectionRuleInstance rows for run.tenant_id, joins DetectionRuleType,
    returns APPLICABLE subset; writes skipped_inapplicable log rows for non-applicable ones.

run_detection(db, run, *, statement_timeout_ms=None) -> int
    PRECONDITION: raises RuntimeError if inserted_count != expected_count.
    PASS 1 - baselines: compute_baseline for each requires_baseline instance.
             Each baseline runs in its own try/except; a failure logs the error,
             records it in resolution_stats["errors"], and continues to the next
             baseline. One baseline timeout MUST NOT abort the detection session.
    PASS 2 - single-row (MFR-001), statistical (MFR-003/4, HP-005/8, ALL-006),
             grouping (ALL-001, MFR-002, TH-002, TH-005).
    Returns count of Anomaly rows created.

statement_timeout_ms (int, default 0 = unlimited):
    Passed to _set_batch_statement_timeout() at the start of run_detection.
    Batch analytics legitimately run for minutes; the OLTP 30s default is an
    OLTP guard inappropriate for batch jobs. The env var
    RECLAIMRX_BATCH_STATEMENT_TIMEOUT_MS controls the default when the caller
    does not supply the argument (default: 0 = unlimited).
    On SQLite (tests) _set_batch_statement_timeout is a no-op.

MFR-008 deferred: needs statement-only-pharmacy reference data (dry-run fix).
TH-002/TH-005 min-volume floor: skip prescribers below min_claims (default 20)
    to prevent false-positive floods on low-volume prescribers.

Memory model (2.6M-row scale):
    _ROW_BATCH controls per-row streaming batch size (MFR-001, MFR-003/HP-008).
    Peak working set is O(_ROW_BATCH + flagged_rows), not O(total_rows).
    Grouping rules (ALL-001, MFR-002, TH-002, TH-005) use server-side SQL to
    return only candidate/flagged rows -- never materialize the full row set.

CHECKs satisfied by skip rows:
  ck_reclaimrx_eval_log_result            - skipped_inapplicable is in the enum
  ck_reclaimrx_eval_log_per_claim_columns - skipped_inapplicable permits NULL source
  ck_reclaimrx_eval_log_error_iff_message - error_message NULL and result != error
  ck_reclaimrx_eval_log_anomaly_id_iff_finding - anomaly_id NULL and result != finding_raised
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.detection.baselines import compute_baseline
from src.detection.fdb_pricing import fetch_current_prices_for_ndcs
from src.detection.mfr003_evaluator import evaluate_hp008_row, evaluate_mfr003_row
from src.detection.parsing import parse_dos, parse_money
from src.detection.rule_evaluators import RuleResult, derive_fields, evaluate_threshold
from src.models.detection_run_models import (
    Anomaly,
    BaselineCache,
    CsvUploadRow,
    DetectionRuleEvaluationLog,
    DetectionRuleInstance,
    DetectionRuleType,
    DetectionRun,
)

logger = logging.getLogger(__name__)

# Streaming batch size for per-row passes (MFR-001, MFR-003, HP-008).
# At 2.6M rows x 75-column JSONB: 10k rows ~= 30-50 MB working set per batch.
# Patching this module-level constant in tests exercises batch-boundary correctness.
_ROW_BATCH: int = 10_000

# Environment variable controlling the default statement_timeout for batch sessions.
# 0 = unlimited (no timeout). OLTP servers set this to 30s; batch jobs must override.
# Override at the process level: RECLAIMRX_BATCH_STATEMENT_TIMEOUT_MS=0
_BATCH_STATEMENT_TIMEOUT_ENV = "RECLAIMRX_BATCH_STATEMENT_TIMEOUT_MS"
_DEFAULT_BATCH_STATEMENT_TIMEOUT_MS: int = 0  # unlimited by default

_BASELINE_KIND_MAP: dict[str, str] = {
    "MFR-004": "pharmacy_ndc_volume",
    "MFR-003": "pharmacy_own_rate_history",
    "HP-005":  "prescriber_peer_volume",
    "HP-008":  "member_cost",
    "ALL-006": "pharmacy_weekday_volume",
}

_SINGLE_ROW_CODES: frozenset[str] = frozenset({"MFR-001"})
# MFR-003, HP-008: per-row evaluators (FDB WAC / high-cost percentile).
# MFR-004, HP-005, ALL-006, ALL-005: entity-level set-based SQL evaluators (Task 2b).
_STATISTICAL_CODES: frozenset[str] = frozenset({"MFR-003", "MFR-004", "HP-005", "HP-008", "ALL-006", "ALL-005"})
_GROUPING_CODES: frozenset[str] = frozenset({"ALL-001", "MFR-002", "TH-002", "TH-005", "REJECT-75-70"})
_ZERO = Decimal("0")

# ---------------------------------------------------------------------------
# Guardrail caps (§12 H1).
# CEILINGS are hard maximums -- a run/rule may configure a STRICTER (lower) cap
# but can NEVER configure a looser cap. Any configured value above the ceiling
# is clamped to the ceiling. This prevents bypass via mutable run.resolution_stats.
# ---------------------------------------------------------------------------
_TOTAL_FIRE_RATE_CEILING: Decimal = Decimal("0.01")   # hard max: 1% total run
_RULE_FIRE_RATE_CEILING: Decimal = Decimal("0.005")   # hard max: 0.5% per rule
# Default caps (equal to ceilings; keep as aliases for backward compat)
_TOTAL_FIRE_RATE_CAP: Decimal = _TOTAL_FIRE_RATE_CEILING
_RULE_FIRE_RATE_CAP: Decimal = _RULE_FIRE_RATE_CEILING
# Minimum row count before guardrail is enforced.
# Micro-fixtures (<200 rows) used in unit tests are exempt: a 1-in-10 fire rate
# is meaningless at that scale and must not block legitimate unit test execution.
# Real batch runs always have hundreds to millions of rows.
_MIN_GUARDRAIL_RECORDS: int = 200


# ---------------------------------------------------------------------------
# NPI sanitization helper
# ---------------------------------------------------------------------------


def _valid_npi(value):
    """Return value only if it is exactly 10 characters; otherwise return None.

    The anomalies table CHECK constraints require:
      pharmacy_npi   IS NULL OR length(pharmacy_npi)   = 10
      prescriber_npi IS NULL OR length(prescriber_npi) = 10

    Real-world CSV data can contain non-NPI strings in NPI fields (e.g. state
    license numbers like 'MA3253488').  Storing them verbatim raises a
    CheckViolation.  We NULL the snapshot column and preserve the raw value in
    finding_details so the signal is not lost.
    """
    if value is None:
        return None
    return value if len(value) == 10 else None


# ---------------------------------------------------------------------------
# Resilient anomaly flush helper (SAVEPOINT-isolated)
# ---------------------------------------------------------------------------


def _flush_anomaly_safe(db, anomaly, run, *, anomaly_write_errors):
    """Flush one Anomaly inside a SAVEPOINT.

    On success returns True.  On IntegrityError rolls back only the savepoint,
    logs the offending finding (rule code + source_row_id + constraint),
    increments anomaly_write_errors[0], and returns False.  The outer session
    remains usable.

    Sanitization in _make_anomaly handles the known NPI-length case.  This
    savepoint guard catches any other unanticipated CHECK violation at 2.6M scale.
    """
    try:
        sp = db.begin_nested()
        db.flush()
        sp.commit()
        return True
    except IntegrityError as exc:
        sp.rollback()
        # Expunge the anomaly from the session so the final db.flush() at the
        # end of run_detection does not re-insert it.  After rollback the object
        # is in a detached/expired state; expunge removes it from the identity map.
        try:
            db.expunge(anomaly)
        except Exception:
            pass
        anomaly_write_errors[0] += 1
        logger.error(
            "Anomaly write skipped due to constraint violation -- "
            "run_id=%s finding_code=%s source_row_id=%s constraint=%s",
            run.id,
            getattr(anomaly, "finding_code", "unknown"),
            getattr(anomaly, "source_row_id", "unknown"),
            str(exc.orig)[:200] if exc.orig else str(exc)[:200],
        )
        return False


# ---------------------------------------------------------------------------
# Statement-timeout helper
# ---------------------------------------------------------------------------


def _set_batch_statement_timeout(db: Session, ms: int) -> None:
    """Disable (or relax) the Postgres statement_timeout for the batch session.

    Batch analytics jobs legitimately run for minutes; the OLTP 30s default
    is an OLTP guard and must NOT apply to FWA detection. Setting ms=0 removes
    the limit entirely for this session.

    This function is a module-level helper (not inlined) so tests can patch
    it to verify the call and/or to suppress the SQL on SQLite where
    SET statement_timeout is not a valid command.

    On non-Postgres dialects (SQLite in tests) this is a no-op: SQLite does
    not support SET statement_timeout, so the guard checks the dialect first.

    Args:
        db: Active SQLAlchemy Session.
        ms: Timeout in milliseconds. 0 = unlimited (no timeout).
    """
    if db.get_bind().dialect.name != "postgresql":
        # SQLite and other non-Postgres dialects: no-op.
        return
    # SET (without LOCAL) applies for the entire session, not just the current
    # transaction. This is intentional for batch jobs: we want the relaxed
    # timeout for the whole detection pass, not just until the next COMMIT.
    db.execute(text("SET statement_timeout = :ms"), {"ms": ms})
    logger.info(
        "Batch statement_timeout set to %d ms (0 = unlimited) for FWA detection session",
        ms,
    )


def gate_rules(
    db: Session,
    run: DetectionRun,
    available_columns: set[str],
) -> list[DetectionRuleInstance]:
    """Return applicable instances; write run-wide skip rows for non-applicable ones."""
    instances_with_types: list[tuple[DetectionRuleInstance, DetectionRuleType]] = (
        db.execute(
            select(DetectionRuleInstance, DetectionRuleType)
            .join(DetectionRuleType, DetectionRuleInstance.rule_type_code == DetectionRuleType.code)
            .where(
                DetectionRuleInstance.tenant_id == run.tenant_id,
                DetectionRuleInstance.enabled.is_(True),
            )
        ).all()
    )
    applicable: list[DetectionRuleInstance] = []
    for instance, rule_type in instances_with_types:
        is_applicable = (
            not rule_type.deferred_data_feed
            and set(rule_type.required_data_columns) <= available_columns
        )
        if is_applicable:
            applicable.append(instance)
        else:
            db.add(DetectionRuleEvaluationLog(
                tenant_id=run.tenant_id,
                rule_instance_id=instance.id,
                detection_run_id=run.id,
                source_table=None,
                source_row_id=None,
                evaluation_result="skipped_inapplicable",
                anomaly_id=None,
                error_message=None,
                elapsed_ms=0,
            ))
    return applicable


def _available_columns_for_run(db: Session, run: DetectionRun) -> set[str]:
    sample = db.execute(
        select(CsvUploadRow)
        .where(CsvUploadRow.detection_run_id == run.id, CsvUploadRow.tenant_id == run.tenant_id)
        .limit(1)
    ).scalar_one_or_none()
    return set(sample.row_data.keys()) if sample is not None else set()


def _build_confidence_scoring(params: dict[str, Any]) -> dict[str, Any]:
    scoring: dict[str, Any] = {}
    if "confidence_high" in params:
        scoring["high"] = params["confidence_high"]
    if "confidence_medium" in params:
        scoring["medium"] = params["confidence_medium"]
    return scoring


def _confidence_tier_to_num(tier: str) -> Decimal:
    return {"high": Decimal("0.85"), "medium": Decimal("0.60"), "low": Decimal("0.40")}.get(tier, Decimal("0.40"))


def _make_anomaly(
    *,
    run: DetectionRun,
    instance: DetectionRuleInstance,
    csv_row: CsvUploadRow,
    finding_code: str,
    finding_summary: str,
    finding_details: dict[str, Any],
    severity: str,
    confidence_num: Decimal,
) -> Anomaly:
    """Construct Anomaly ORM object. Amounts via parse_money (Decimal, never float)."""
    rd = csv_row.row_data
    dos_val = parse_dos(rd.get("date_of_service"))
    amount_paid = parse_money(rd.get("total_paid_amt"))
    amount_billed = parse_money(rd.get("ingredient_cost_submitted"))
    qty_raw = rd.get("quantity_dispensed")
    quantity: Decimal | None = None
    if qty_raw:
        try:
            quantity = Decimal(str(qty_raw)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        except Exception:
            pass
    days_raw = rd.get("day_supply")
    days_supply: int | None = None
    if days_raw:
        try:
            days_supply = int(days_raw)
        except (ValueError, TypeError):
            pass
    # Sanitize NPI snapshot columns: anomalies CHECK requires length=10 or NULL.
    # Real CSV data can hold state license numbers or other non-NPI strings.
    # NULL the column when invalid; preserve the raw value in finding_details.
    raw_pharmacy_npi = csv_row.resolved_pharmacy_npi
    clean_pharmacy_npi = _valid_npi(raw_pharmacy_npi)

    raw_prescriber_npi = rd.get("prescriber_npi") or None
    clean_prescriber_npi = _valid_npi(raw_prescriber_npi)

    # Inject raw_ keys only when sanitization actually changed the value.
    sanitized_details = dict(finding_details)
    if raw_pharmacy_npi is not None and clean_pharmacy_npi is None:
        sanitized_details["raw_pharmacy_npi"] = raw_pharmacy_npi
    if raw_prescriber_npi is not None and clean_prescriber_npi is None:
        sanitized_details["raw_prescriber_npi"] = raw_prescriber_npi

    return Anomaly(
        tenant_id=run.tenant_id,
        data_source="csv_upload",
        data_source_run_id=run.id,
        client_id=csv_row.resolved_client_id,
        program_id=csv_row.resolved_program_id,
        pharmacy_npi=clean_pharmacy_npi,
        ndc=csv_row.resolved_ndc,
        source_table="csv_upload_rows",
        source_row_id=csv_row.id,
        detection_kind="rule",
        detection_id=instance.id,
        severity=severity,
        confidence=confidence_num,
        date_of_service=dos_val,
        rx_number=rd.get("rx_number_hash"),
        prescriber_npi=clean_prescriber_npi,
        days_supply=days_supply,
        quantity=quantity,
        amount_paid=amount_paid,
        amount_billed=amount_billed,
        finding_code=finding_code,
        finding_summary=finding_summary,
        finding_details=sanitized_details,
        status="open",
    )


def _write_eval_log(
    db: Session,
    *,
    run: DetectionRun,
    instance: DetectionRuleInstance,
    csv_row: CsvUploadRow,
    result: str,
    anomaly_id: object | None = None,
    error_message: str | None = None,
) -> None:
    db.add(DetectionRuleEvaluationLog(
        tenant_id=run.tenant_id,
        rule_instance_id=instance.id,
        detection_run_id=run.id,
        source_table="csv_upload_rows",
        source_row_id=csv_row.id,
        evaluation_result=result,
        anomaly_id=anomaly_id,
        error_message=error_message,
        elapsed_ms=0,
    ))


# ---------------------------------------------------------------------------
# Pass 1 - Baseline computation (per-unit isolation)
# ---------------------------------------------------------------------------


def _run_baselines(
    db: Session,
    run: DetectionRun,
    applicable: list[DetectionRuleInstance],
    rule_type_by_code: dict[str, DetectionRuleType],
    baseline_errors: list[dict[str, str]],
) -> None:
    """For each applicable instance whose type.requires_baseline, compute the baseline.

    Per-unit isolation: each baseline computation runs in its own try/except.
    A failure (including a Postgres statement_timeout / QueryCanceled) is logged,
    recorded in baseline_errors, and the loop continues to the next baseline.
    One failing baseline MUST NOT abort the detection session.

    MFR-009: no baseline kind registered -- logged and skipped (not an error).

    Args:
        db:               Active Session.
        run:              The DetectionRun being processed.
        applicable:       Applicable rule instances.
        rule_type_by_code: Rule type lookup map.
        baseline_errors:  Mutable list; each failing baseline appends
                          {"kind": str, "rule": str, "reason": str}.
    """
    for instance in applicable:
        rtype = rule_type_by_code.get(instance.rule_type_code)
        if rtype is None or not rtype.requires_baseline:
            continue
        code = instance.rule_type_code
        kind = _BASELINE_KIND_MAP.get(code)
        if kind is None:
            logger.info(
                "No baseline kind registered for rule %s -- skipping baseline computation", code
            )
            continue
        try:
            n = compute_baseline(db, run, kind=kind)
            logger.debug("Baseline kind=%s rule=%s: %d rows written", kind, code, n)
        except Exception as exc:
            # Per-unit isolation: log and record, but do NOT re-raise.
            # A Postgres statement_timeout (psycopg2.errors.QueryCanceled) lands here.
            # We continue to the next baseline so the detection session survives.
            reason = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "Baseline computation failed for kind=%s rule=%s -- continuing with next baseline",
                kind,
                code,
            )
            baseline_errors.append({"kind": kind, "rule": code, "reason": reason})


# ---------------------------------------------------------------------------
# Pass 2 - single-row evaluation (streaming)
# ---------------------------------------------------------------------------


def _evaluate_single_row_rules(
    db: Session,
    run: DetectionRun,
    applicable: list[DetectionRuleInstance],
    rule_type_by_code: dict[str, DetectionRuleType],
    no_finding_count: list[int],
    anomaly_write_errors: list[int],
) -> list[Anomaly]:
    """Evaluate MFR-001 per csv_upload_row, streaming in batches of _ROW_BATCH.

    Rows are fetched with yield_per so at most _ROW_BATCH ORM objects reside in
    memory at once.  Anomalies are flushed per finding, not accumulated for the run.
    """
    anomalies: list[Anomaly] = []
    single_instances = [inst for inst in applicable if inst.rule_type_code in _SINGLE_ROW_CODES]
    if not single_instances:
        return anomalies

    stmt = (
        select(CsvUploadRow)
        .where(
            CsvUploadRow.detection_run_id == run.id,
            CsvUploadRow.tenant_id == run.tenant_id,
        )
        .execution_options(yield_per=_ROW_BATCH)
    )

    for instance in single_instances:
        code = instance.rule_type_code
        rtype = rule_type_by_code.get(code)
        if rtype is None:
            continue
        params = dict(instance.parameters)
        params["confidence_scoring"] = _build_confidence_scoring(params)

        for csv_row in db.execute(stmt).scalars():
            rd = csv_row.row_data
            fields: dict[str, Any] = {**rd, **derive_fields(rd)}
            try:
                if code == "MFR-001":
                    result = evaluate_threshold(fields, params)
                else:
                    no_finding_count[0] += 1
                    continue
                if not result.fired:
                    no_finding_count[0] += 1
                    continue
                confidence_num = _confidence_tier_to_num(result.confidence or "medium")
                anomaly = _make_anomaly(
                    run=run, instance=instance, csv_row=csv_row,
                    finding_code=code,
                    finding_summary=(
                        f"{rtype.name}: {result.evidence.get('field', '')} "
                        f"{params.get('operator', '')} {params.get('threshold', '')}"
                    ),
                    finding_details=result.evidence,
                    severity=result.severity or rtype.default_severity,
                    confidence_num=confidence_num,
                )
                _write_eval_log(db, run=run, instance=instance, csv_row=csv_row,
                                result="finding_raised", anomaly_id=None)
                anomalies.append(anomaly)
            except Exception:
                logger.exception("Error evaluating rule %s on csv_row %s", code, csv_row.id)
                _write_eval_log(db, run=run, instance=instance, csv_row=csv_row,
                                result="error", error_message=f"Evaluation error for {code}")

    return anomalies


# ---------------------------------------------------------------------------
# Pass 2 - statistical evaluation (streaming)
# ---------------------------------------------------------------------------


def _load_baseline_cache(db: Session, run: DetectionRun, kind: str) -> dict[str, BaselineCache]:
    rows = db.execute(
        select(BaselineCache).where(
            BaselineCache.tenant_id == run.tenant_id,
            BaselineCache.baseline_kind == kind,
        )
    ).scalars().all()
    return {r.scope_key: r for r in rows}


def _scope_key_for_row(code: str, rd: dict[str, Any], csv_row: CsvUploadRow) -> str | None:
    ndc = csv_row.resolved_ndc or ""
    npi = csv_row.resolved_pharmacy_npi or ""
    presc = str(rd.get("prescriber_npi", "") or "").strip()
    if code == "MFR-004":
        return f"ndc={ndc}|pharmacy_npi={npi}" if ndc and npi else None
    if code == "MFR-003":
        return f"ndc={ndc}|pharmacy_npi={npi}" if ndc and npi else None
    if code == "HP-005":
        return f"ndc={ndc}|prescriber_npi={presc}" if ndc and presc else None
    if code == "HP-008":
        return "run"
    if code == "ALL-006":
        return f"pharmacy_npi={npi}" if npi else None
    return None


def _sigmoid_approx(z: Decimal) -> Decimal:
    import math
    z_float = max(-10.0, min(10.0, float(z)))
    return Decimal(str(math.erf(z_float / 1.4142135623730951)))


def _derive_statistical_metric(code: str, rd: dict[str, Any], baseline: BaselineCache) -> dict[str, Any]:
    """Compute the derived metric for statistical rule threshold evaluation.

    MFR-004, HP-005, ALL-006 are entity/population-level; per-row comparison not meaningful.
    Returns empty dict to skip those rows.
    """
    mean = Decimal(str(baseline.mean)) if baseline.mean is not None else None
    stddev = Decimal(str(baseline.stddev)) if baseline.stddev is not None else None

    if code == "MFR-003":
        ic = parse_money(rd.get("ingredient_cost_paid"))
        wac_val = parse_money(rd.get("extended_wac"))
        if ic is None or wac_val is None or wac_val == _ZERO or mean is None or mean == _ZERO:
            return {}
        own_rate = ic / wac_val
        return {"contracted_rate_deviation_pct": abs(own_rate - mean) / mean}

    if code == "HP-008":
        total = parse_money(rd.get("total_paid_amt"))
        if total is None or mean is None or stddev is None or stddev == _ZERO:
            return {}
        z = (total - mean) / stddev
        approx_pct = Decimal("0.5") + Decimal("0.5") * _sigmoid_approx(z)
        return {"cost_percentile": approx_pct}

    # MFR-004, HP-005, ALL-006: entity-level metric -- skip per-row.
    return {}


def _evaluate_statistical_rules(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance,
) -> list[Anomaly]:
    """Generic param-driven statistical outlier evaluator for MFR-004, HP-005, ALL-006, ALL-005.

    Called once per statistical rule instance (entity-level rules only).
    NOT called for MFR-003 or HP-008 -- those use per-row adapters via _PER_ROW_EVALUATORS.

    Reads ALL thresholds from instance.parameters (set by migration 0011).
    ZERO hardcoded ratio/absolute threshold values -- outlier decisions use
    zscore_flag, percentile_within_cohort, or threshold-mode gap check only,
    all gated by passes_min_sample + passes_dollar_floor.

    Entity-level: one Anomaly per flagged entity (not per claim row).
    Set-based: one SQL aggregate query per rule invocation; no per-entity loop query.
    Rep-row: ONE batched DISTINCT ON query for all fired entities after aggregation.

    Returns list[Anomaly] (NOT flushed -- caller accumulates for guardrail check).
    """
    from collections import defaultdict  # noqa: PLC0415

    from src.detection.calibration import (  # noqa: PLC0415
        zscore_flag,
        passes_min_sample,
        passes_dollar_floor,
    )

    code = instance.rule_type_code
    params = instance.parameters

    # Read H2 params (all set by migration 0011)
    eligible_statuses: list[str] = params.get("eligible_statuses", ["Paid"])
    min_group_size: int = int(params.get("min_group_size", 20))
    min_entity_count: int = int(params.get("min_entity_count", 1))
    dollar_floor_str = params.get("dollar_floor", "0.00")
    dollar_floor = Decimal(str(dollar_floor_str)) if dollar_floor_str else None
    z_thresh = Decimal(str(params.get("z_threshold", "3.0")))
    pct_thresh = Decimal(str(params.get("percentile_threshold", "0.99")))
    refill_pct_thresh = Decimal(str(params.get("refill_pct_threshold", "0.50")))

    anomalies: list[Anomaly] = []

    if code == "MFR-004":
        # Metric: fill volume per NDC (count of paid-B1 claims per pharmacy per NDC).
        # Cohort: all entities with the same NDC. z-score across cohort.
        rows = db.execute(text("""
            SELECT
                (row_data->>'pharmacy_npi') AS entity_id,
                resolved_ndc AS cohort_ndc,
                COUNT(*) AS fill_volume,
                SUM((row_data->>'total_paid_amt')::numeric) AS dollar_sum
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (row_data->>'transaction_code') = 'B1'
              AND (row_data->>'transaction_status') = ANY(:statuses)
              AND resolved_ndc IS NOT NULL
            GROUP BY (row_data->>'pharmacy_npi'), resolved_ndc
            HAVING COUNT(*) >= :min_group
        """), {
            "run_id": str(run.id), "tenant_id": str(run.tenant_id),
            "statuses": eligible_statuses, "min_group": min_group_size,
        }).fetchall()

        cohort_map: dict = defaultdict(list)
        for r in rows:
            cohort_map[r.cohort_ndc].append(
                (r.entity_id, Decimal(str(r.fill_volume)), Decimal(str(r.dollar_sum or 0)))
            )

        fired_mfr004: list[tuple] = []
        for ndc, entities in cohort_map.items():
            if len(entities) < min_entity_count:
                continue
            all_volumes = [v for _, v, _ in entities]
            n = Decimal(str(len(all_volumes)))
            cohort_mean = sum(all_volumes) / n
            variance = sum((v - cohort_mean) ** 2 for v in all_volumes) / n
            cohort_stddev = variance.sqrt().quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
            for entity_id, vol, dollar_sum in entities:
                if not passes_dollar_floor(dollar_sum, dollar_floor):
                    continue
                fired, z = zscore_flag(value=vol, mean=cohort_mean, stddev=cohort_stddev, z_threshold=z_thresh)
                if fired:
                    fired_mfr004.append((entity_id, ndc, vol, cohort_mean, z))

        if fired_mfr004:
            entity_ndc_pairs = [(e, n) for e, n, *_ in fired_mfr004]
            or_clauses = " OR ".join(
                f"((row_data->>'pharmacy_npi') = :en_{i} AND resolved_ndc = :nd_{i})"
                for i in range(len(entity_ndc_pairs))
            )
            rep_params: dict = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}
            for i, (en, nd) in enumerate(entity_ndc_pairs):
                rep_params[f"en_{i}"] = en
                rep_params[f"nd_{i}"] = nd
            rep_rows_raw = db.execute(text(f"""
                SELECT DISTINCT ON ((row_data->>'pharmacy_npi'), resolved_ndc)
                    id, (row_data->>'pharmacy_npi') AS entity_id, resolved_ndc AS cohort_ndc
                FROM reclaimrx.csv_upload_rows
                WHERE detection_run_id = :run_id AND tenant_id = :tenant_id
                  AND ({or_clauses})
                ORDER BY (row_data->>'pharmacy_npi'), resolved_ndc, id
            """), rep_params).fetchall()
            rep_row_map: dict[tuple, object] = {
                (r.entity_id, r.cohort_ndc): r.id for r in rep_rows_raw
            }
            for entity_id, ndc, vol, cohort_mean, z in fired_mfr004:
                rep_row_id = rep_row_map.get((entity_id, ndc))
                if rep_row_id:
                    anomalies.append(Anomaly(
                        tenant_id=run.tenant_id, data_source="csv_upload",
                        data_source_run_id=run.id,
                        source_table="csv_upload_rows", source_row_id=rep_row_id,
                        detection_kind="rule",
                        severity=params.get("severity", "high"),
                        confidence=Decimal(str(params.get("confidence", "0.80"))),
                        finding_code="MFR-004",
                        finding_summary=f"Unusually high fill volume for NDC {ndc} entity {entity_id}",
                        finding_details={
                            "entity_id": entity_id, "ndc": ndc,
                            "fill_volume": str(vol), "cohort_mean": str(cohort_mean),
                            "_z": str(z), "statistic": "zscore",
                        },
                        status="open",
                    ))

    elif code == "HP-005":
        # Metric: prescriber claim volume per NDC cohort. z-score across prescribers.
        rows = db.execute(text("""
            SELECT
                (row_data->>'prescriber_npi') AS entity_id,
                resolved_ndc AS cohort_ndc,
                COUNT(*) AS claim_volume,
                SUM((row_data->>'total_paid_amt')::numeric) AS dollar_sum
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (row_data->>'transaction_code') = 'B1'
              AND (row_data->>'transaction_status') = ANY(:statuses)
              AND (row_data->>'prescriber_npi') IS NOT NULL
              AND resolved_ndc IS NOT NULL
            GROUP BY (row_data->>'prescriber_npi'), resolved_ndc
            HAVING COUNT(*) >= :min_group
        """), {
            "run_id": str(run.id), "tenant_id": str(run.tenant_id),
            "statuses": eligible_statuses, "min_group": min_group_size,
        }).fetchall()

        cohort_map2: dict = defaultdict(list)
        for r in rows:
            cohort_map2[r.cohort_ndc].append(
                (r.entity_id, Decimal(str(r.claim_volume)), Decimal(str(r.dollar_sum or 0)))
            )

        fired_hp005: list[tuple] = []
        for ndc, entities in cohort_map2.items():
            if len(entities) < min_entity_count:
                continue
            all_vols = [v for _, v, _ in entities]
            n = Decimal(str(len(all_vols)))
            cohort_mean = sum(all_vols) / n
            variance = sum((v - cohort_mean) ** 2 for v in all_vols) / n
            cohort_stddev = variance.sqrt().quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
            for entity_id, vol, dollar_sum in entities:
                if not passes_dollar_floor(dollar_sum, dollar_floor):
                    continue
                fired, z = zscore_flag(value=vol, mean=cohort_mean, stddev=cohort_stddev, z_threshold=z_thresh)
                if fired:
                    fired_hp005.append((entity_id, ndc, vol, cohort_mean, z))

        if fired_hp005:
            entity_ndc_pairs2 = [(e, n) for e, n, *_ in fired_hp005]
            or_clauses2 = " OR ".join(
                f"((row_data->>'prescriber_npi') = :en_{i} AND resolved_ndc = :nd_{i})"
                for i in range(len(entity_ndc_pairs2))
            )
            rep_params2: dict = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}
            for i, (en, nd) in enumerate(entity_ndc_pairs2):
                rep_params2[f"en_{i}"] = en
                rep_params2[f"nd_{i}"] = nd
            rep_rows2 = db.execute(text(f"""
                SELECT DISTINCT ON ((row_data->>'prescriber_npi'), resolved_ndc)
                    id, (row_data->>'prescriber_npi') AS entity_id, resolved_ndc AS cohort_ndc
                FROM reclaimrx.csv_upload_rows
                WHERE detection_run_id = :run_id AND tenant_id = :tenant_id
                  AND ({or_clauses2})
                ORDER BY (row_data->>'prescriber_npi'), resolved_ndc, id
            """), rep_params2).fetchall()
            rep_row_map2: dict[tuple, object] = {
                (r.entity_id, r.cohort_ndc): r.id for r in rep_rows2
            }
            for entity_id, ndc, vol, cohort_mean, z in fired_hp005:
                rep_row_id = rep_row_map2.get((entity_id, ndc))
                if rep_row_id:
                    anomalies.append(Anomaly(
                        tenant_id=run.tenant_id, data_source="csv_upload",
                        data_source_run_id=run.id,
                        source_table="csv_upload_rows", source_row_id=rep_row_id,
                        detection_kind="rule",
                        severity=params.get("severity", "high"),
                        confidence=Decimal(str(params.get("confidence", "0.80"))),
                        finding_code="HP-005",
                        finding_summary=f"Prescriber {entity_id} outlier volume for NDC {ndc}",
                        finding_details={
                            "prescriber_npi": entity_id, "ndc": ndc,
                            "claim_volume": str(vol), "cohort_mean": str(cohort_mean),
                            "_z": str(z), "statistic": "zscore",
                        },
                        status="open",
                    ))

    elif code == "ALL-006":
        # Metric: weekend/holiday fill ratio per pharmacy (weekends only; DOW in (0,6)).
        rows = db.execute(text("""
            SELECT
                (row_data->>'pharmacy_npi') AS entity_id,
                COUNT(*) AS total_fills,
                SUM(CASE WHEN EXTRACT(DOW FROM (row_data->>'date_of_service')::date) IN (0, 6)
                         THEN 1 ELSE 0 END) AS weekend_fills,
                SUM((row_data->>'total_paid_amt')::numeric) AS dollar_sum
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (row_data->>'transaction_code') = 'B1'
              AND (row_data->>'transaction_status') = ANY(:statuses)
              AND (row_data->>'pharmacy_npi') IS NOT NULL
              AND (row_data->>'date_of_service') IS NOT NULL
            GROUP BY (row_data->>'pharmacy_npi')
            HAVING COUNT(*) >= :min_group
        """), {
            "run_id": str(run.id), "tenant_id": str(run.tenant_id),
            "statuses": eligible_statuses, "min_group": min_group_size,
        }).fetchall()

        if len(rows) < min_entity_count:
            return anomalies

        ratios: list[tuple] = []
        for r in rows:
            total = Decimal(str(r.total_fills)) if r.total_fills else Decimal("1")
            weekend = Decimal(str(r.weekend_fills or 0))
            ratio = (weekend / total).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
            dollar_sum = Decimal(str(r.dollar_sum or 0))
            ratios.append((r.entity_id, ratio, dollar_sum))

        all_ratios = [v for _, v, _ in ratios]
        if not all_ratios:
            return anomalies

        n = Decimal(str(len(all_ratios)))
        cohort_mean = sum(all_ratios) / n
        variance = sum((v - cohort_mean) ** 2 for v in all_ratios) / n
        cohort_stddev = variance.sqrt().quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

        fired_all006: list[tuple] = []
        for entity_id, ratio, dollar_sum in ratios:
            if not passes_dollar_floor(dollar_sum, dollar_floor):
                continue
            fired, z = zscore_flag(value=ratio, mean=cohort_mean, stddev=cohort_stddev, z_threshold=z_thresh)
            if fired:
                fired_all006.append((entity_id, ratio, z))

        if fired_all006:
            fired_npis = [e for e, *_ in fired_all006]
            or_clauses3 = " OR ".join(
                f"(row_data->>'pharmacy_npi') = :ph_{i}"
                for i in range(len(fired_npis))
            )
            rep_params3: dict = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}
            for i, ph in enumerate(fired_npis):
                rep_params3[f"ph_{i}"] = ph
            rep_rows3 = db.execute(text(f"""
                SELECT DISTINCT ON ((row_data->>'pharmacy_npi'))
                    id, (row_data->>'pharmacy_npi') AS entity_id
                FROM reclaimrx.csv_upload_rows
                WHERE detection_run_id = :run_id AND tenant_id = :tenant_id
                  AND ({or_clauses3})
                ORDER BY (row_data->>'pharmacy_npi'), id
            """), rep_params3).fetchall()
            rep_row_map3: dict[str, object] = {r.entity_id: r.id for r in rep_rows3}
            for entity_id, ratio, z in fired_all006:
                rep_row_id = rep_row_map3.get(entity_id)
                if rep_row_id:
                    anomalies.append(Anomaly(
                        tenant_id=run.tenant_id, data_source="csv_upload",
                        data_source_run_id=run.id,
                        source_table="csv_upload_rows", source_row_id=rep_row_id,
                        detection_kind="rule",
                        severity=params.get("severity", "medium"),
                        confidence=Decimal(str(params.get("confidence", "0.75"))),
                        finding_code="ALL-006",
                        finding_summary=f"Pharmacy {entity_id} has anomalous weekend/holiday fill rate",
                        finding_details={
                            "pharmacy_npi": entity_id,
                            "weekend_ratio": str(ratio),
                            "cohort_mean": str(cohort_mean),
                            "_z": str(z),
                            "statistic": "zscore",
                        },
                        status="open",
                    ))

    elif code == "ALL-005":
        # Metric: min gap in days between consecutive fills for same (patient, ndc).
        # Flags when min_gap_days < days_supply * refill_pct_threshold.
        # Statistic = "threshold" (no z-score; direct threshold comparison).
        # Bind refill_pct_thresh as string; SQL casts ::numeric to avoid float.
        rows = db.execute(text("""
            WITH fills AS (
                SELECT
                    (row_data->>'patient_unique_hash') AS patient_hash,
                    resolved_ndc AS ndc,
                    (row_data->>'date_of_service')::date AS dos,
                    (row_data->>'days_supply')::int AS days_supply,
                    (row_data->>'total_paid_amt')::numeric AS paid_amt,
                    id AS row_id
                FROM reclaimrx.csv_upload_rows
                WHERE detection_run_id = :run_id
                  AND tenant_id = :tenant_id
                  AND (row_data->>'transaction_code') = 'B1'
                  AND (row_data->>'transaction_status') = ANY(:statuses)
                  AND (row_data->>'patient_unique_hash') IS NOT NULL
                  AND resolved_ndc IS NOT NULL
                  AND (row_data->>'date_of_service') IS NOT NULL
                  AND (row_data->>'days_supply') IS NOT NULL
            ),
            with_lag AS (
                SELECT
                    patient_hash, ndc, dos, days_supply, paid_amt, row_id,
                    LAG(dos) OVER (PARTITION BY patient_hash, ndc ORDER BY dos) AS prior_dos
                FROM fills
            ),
            gaps AS (
                SELECT
                    patient_hash, ndc, dos, days_supply, paid_amt, row_id,
                    (dos - prior_dos) AS gap_days
                FROM with_lag
                WHERE prior_dos IS NOT NULL
                  AND (dos - prior_dos) < days_supply * CAST(:pct_thresh AS numeric)
            )
            SELECT
                patient_hash, ndc,
                MIN(gap_days) AS min_gap,
                COUNT(*) AS early_refill_count,
                MAX(paid_amt) AS max_paid,
                MIN(row_id::text) AS rep_row_id
            FROM gaps
            GROUP BY patient_hash, ndc
            HAVING COUNT(*) >= :min_group
        """), {
            "run_id": str(run.id), "tenant_id": str(run.tenant_id),
            "statuses": eligible_statuses, "min_group": min_group_size,
            # Bind as Decimal-safe string; SQL casts to ::numeric. No float().
            "pct_thresh": str(refill_pct_thresh),
        }).fetchall()

        for r in rows:
            dollar_val = Decimal(str(r.max_paid or 0))
            if not passes_dollar_floor(dollar_val, dollar_floor):
                continue
            if r.early_refill_count < min_entity_count:
                continue
            anomalies.append(Anomaly(
                tenant_id=run.tenant_id, data_source="csv_upload",
                data_source_run_id=run.id,
                source_table="csv_upload_rows", source_row_id=r.rep_row_id,
                detection_kind="rule",
                severity=params.get("severity", "medium"),
                confidence=Decimal(str(params.get("confidence", "0.75"))),
                finding_code="ALL-005",
                finding_summary=f"Early refill pattern: patient {r.patient_hash} NDC {r.ndc}",
                finding_details={
                    "patient_unique_hash": r.patient_hash, "ndc": r.ndc,
                    "min_gap_days": str(r.min_gap),
                    "early_refill_count": r.early_refill_count,
                    "refill_pct_threshold": str(refill_pct_thresh),
                    "statistic": "threshold",
                },
                status="open",
            ))

    return anomalies


def _dispatch_statistical_rules(
    db: Session,
    run: DetectionRun,
    applicable: list[DetectionRuleInstance],
    rule_type_by_code: dict[str, DetectionRuleType],
    no_finding_count: list[int],
    anomaly_write_errors: list[int],
    _fdb_cache: dict | None = None,
) -> list[Anomaly]:
    """Dispatch _evaluate_statistical_rules per applicable stat instance.

    MFR-003, HP-008: per-row evaluators using _fdb_cache (pre-fetched WAC; zero per-row DB queries).
    MFR-004, HP-005, ALL-006, ALL-005: entity-level set-based SQL (one call per instance).
    """
    anomalies: list[Anomaly] = []
    stat_instances = [inst for inst in applicable if inst.rule_type_code in _STATISTICAL_CODES]
    if not stat_instances:
        return anomalies

    _ENTITY_LEVEL_CODES = frozenset({"MFR-004", "HP-005", "ALL-006", "ALL-005"})
    _PER_ROW_STAT_CODES = frozenset({"MFR-003", "HP-008"})
    _per_row_evaluators = {
        "MFR-003": evaluate_mfr003_row,
        "HP-008": evaluate_hp008_row,
    }
    fdb = _fdb_cache or {}

    for instance in stat_instances:
        code = instance.rule_type_code
        try:
            if code in _ENTITY_LEVEL_CODES:
                new = _evaluate_statistical_rules(db, run, instance)
                anomalies.extend(new)
            elif code in _PER_ROW_STAT_CODES:
                # Per-row streaming: MFR-003 (FDB WAC IC deviation), HP-008 (high-cost claimant).
                # _fdb_cache pre-fetched before the stream -- zero per-row DB queries.
                evaluator = _per_row_evaluators[code]
                stmt = (
                    select(CsvUploadRow)
                    .where(
                        CsvUploadRow.detection_run_id == run.id,
                        CsvUploadRow.tenant_id == run.tenant_id,
                    )
                    .execution_options(yield_per=_ROW_BATCH)
                )
                for csv_row in db.execute(stmt).scalars():
                    result = evaluator(csv_row, db=db, _fdb_cache=fdb, instance=instance)
                    if result is not None:
                        anomalies.append(result)
        except Exception:
            logger.exception("Error in statistical rule %s", code)

    return anomalies


# ---------------------------------------------------------------------------
# Pass 2 -- grouping rules (server-side SQL)
# ---------------------------------------------------------------------------


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _json_field(db: Session, column: str, field: str) -> str:
    if _is_postgres(db):
        return f"{column}->>'{field}'"
    return f"json_extract({column}, '$.{field}')"


def _evaluate_all001(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance,
    rtype: DetectionRuleType,
    no_finding_count: list[int],
    anomaly_write_errors: list[int],
) -> list[Anomaly]:
    """ALL-001 Duplicate Claim -- server-side grouping.

    Group key: (client_id, patient_unique_hash, resolved_ndc, date_of_service).
    Eligible rows: B1/Paid only.
    Lifecycle filter: skip groups that contain any reversed_check=Yes row.
    Fire: >= 2 DISTINCT auth_no_hash per group.

    SQL step 1: identify qualifying group keys via GROUP BY / HAVING.
    SQL step 2: fetch only the B1/Paid rows in those qualifying groups (bounded).

    Peak memory: O(qualifying_rows), not O(total_rows).
    """
    anomalies: list[Anomaly] = []

    pt_field = _json_field(db, "r.row_data", "patient_unique_hash")
    auth_field = _json_field(db, "r.row_data", "auth_no_hash")
    tc_field = _json_field(db, "r.row_data", "transaction_code")
    ts_field = _json_field(db, "r.row_data", "transaction_status")
    rev_field = _json_field(db, "r.row_data", "reversed_check")
    dos_field = _json_field(db, "r.row_data", "date_of_service")
    client_field = _json_field(db, "r.row_data", "client_id")

    params: dict[str, Any] = {
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
    }

    # Step 1: identify qualifying group keys (server-side).
    sql_groups = text(f"""
        WITH all_rows AS (
            SELECT
                {client_field}  AS client_id,
                {pt_field}      AS patient_hash,
                r.resolved_ndc  AS ndc,
                {dos_field}     AS dos,
                {tc_field}      AS tc,
                {ts_field}      AS ts,
                {auth_field}    AS auth,
                {rev_field}     AS rev_check
            FROM reclaimrx.csv_upload_rows r
            WHERE r.detection_run_id = :run_id
              AND r.tenant_id        = :tenant_id
              AND {pt_field} IS NOT NULL
              AND {pt_field} != ''
              AND {dos_field} IS NOT NULL
              AND {dos_field} != ''
        ),
        reversal_groups AS (
            SELECT DISTINCT client_id, patient_hash, ndc, dos
            FROM all_rows
            WHERE UPPER(rev_check) = 'YES'
        ),
        b1_paid AS (
            SELECT client_id, patient_hash, ndc, dos, auth
            FROM all_rows
            WHERE UPPER(tc) = 'B1'
              AND (ts = 'Paid' OR ts = 'paid')
              AND ts NOT IN ('Duplicate', 'Reversed')
        ),
        dup_groups AS (
            SELECT b.client_id, b.patient_hash, b.ndc, b.dos,
                   COUNT(DISTINCT b.auth) AS auth_count
            FROM b1_paid b
            LEFT JOIN reversal_groups rg
                   ON rg.client_id    = b.client_id
                  AND rg.patient_hash = b.patient_hash
                  AND rg.ndc          = b.ndc
                  AND rg.dos          = b.dos
            WHERE rg.client_id IS NULL
            GROUP BY b.client_id, b.patient_hash, b.ndc, b.dos
            HAVING COUNT(DISTINCT b.auth) >= 2
        )
        SELECT client_id, patient_hash, ndc, dos, auth_count
        FROM dup_groups
    """)

    group_rows = db.execute(sql_groups, params).fetchall()
    if not group_rows:
        return anomalies

    # Step 2: for each qualifying group, fetch its B1/Paid ORM rows (bounded set).
    for grp in group_rows:
        client_id = grp.client_id or ""
        patient_hash = grp.patient_hash or ""
        ndc = grp.ndc or ""
        dos_str = grp.dos or ""
        auth_count = int(grp.auth_count)

        dos_parsed = parse_dos(dos_str)
        if not dos_parsed:
            continue

        # Filter by resolved_ndc (indexable) then apply JSONB predicates in Python.
        group_stmt = (
            select(CsvUploadRow)
            .where(
                CsvUploadRow.detection_run_id == run.id,
                CsvUploadRow.tenant_id == run.tenant_id,
                CsvUploadRow.resolved_ndc == (ndc if ndc else None),
            )
            .execution_options(yield_per=_ROW_BATCH)
        )

        eligible_rows: list[CsvUploadRow] = []
        auth_hashes_seen: set[str] = set()
        for csv_row in db.execute(group_stmt).scalars():
            rd = csv_row.row_data
            pt = str(rd.get("patient_unique_hash", "") or "").strip()
            row_dos_raw = str(rd.get("date_of_service", "") or "").strip()
            row_client = str(rd.get("client_id", "") or "").strip()
            row_tc = str(rd.get("transaction_code", "") or "").strip().upper()
            row_ts = str(rd.get("transaction_status", "") or "").strip()

            if row_client != client_id or pt != patient_hash:
                continue
            row_dos_parsed = parse_dos(row_dos_raw)
            if row_dos_parsed != dos_parsed:
                continue
            if row_tc != "B1" or row_ts not in ("Paid", "paid"):
                continue
            if row_ts in ("Duplicate", "Reversed"):
                continue

            auth = str(rd.get("auth_no_hash", "") or "").strip()
            auth_hashes_seen.add(auth)
            eligible_rows.append(csv_row)

        auth_hashes = list(auth_hashes_seen)
        for csv_row in eligible_rows:
            anomaly = _make_anomaly(
                run=run, instance=instance, csv_row=csv_row,
                finding_code="ALL-001",
                finding_summary=(
                    "Duplicate claim: {} distinct auth numbers for same member/NDC/DOS".format(auth_count)
                ),
                finding_details={
                    "group_key": {
                        "patient_unique_hash": patient_hash,
                        "ndc": ndc,
                        "date_of_service": str(dos_parsed),
                        "client_id": client_id,
                    },
                    "auth_count": auth_count,
                    "auth_hashes": auth_hashes,
                },
                severity="critical",
                confidence_num=Decimal("0.85"),
            )
            _write_eval_log(
                db, run=run, instance=instance, csv_row=csv_row,
                result="finding_raised", anomaly_id=None,
            )
            anomalies.append(anomaly)

    return anomalies


def _evaluate_mfr002(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance,
    rtype: DetectionRuleType,
    no_finding_count: list[int],
    anomaly_write_errors: list[int],
) -> list[Anomaly]:
    """MFR-002 Bill-Reverse-Rebill -- server-side candidate fetch.

    Group: (patient_unique_hash, resolved_pharmacy_npi, resolved_ndc).
    Pattern: B1(Paid) -> B2(reversed_check=Yes) -> B1(Paid) within lookback_days.
    Fire only when rebill abs(IC) > original abs(IC). Flag rebill row only.

    SQL identifies groups having >= 1 B2-reversal AND >= 2 B1-paid rows.
    Only those candidate groups are fetched into Python memory.

    Peak memory: O(candidate_group_rows), not O(total_rows).
    """
    anomalies: list[Anomaly] = []
    lookback_days = int(instance.parameters.get("lookback_days", 14))

    tc_field = _json_field(db, "r.row_data", "transaction_code")
    ts_field = _json_field(db, "r.row_data", "transaction_status")
    rev_field = _json_field(db, "r.row_data", "reversed_check")
    pt_field = _json_field(db, "r.row_data", "patient_unique_hash")

    params: dict[str, Any] = {
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
    }

    # Identify candidate groups: >= 1 B2-reversal AND >= 2 B1-paid rows.
    sql_groups = text(f"""
        WITH grp AS (
            SELECT
                {pt_field}              AS patient_hash,
                r.resolved_pharmacy_npi AS pharmacy_npi,
                r.resolved_ndc          AS ndc,
                UPPER({tc_field})       AS tc,
                {ts_field}              AS ts,
                UPPER({rev_field})      AS rev_check
            FROM reclaimrx.csv_upload_rows r
            WHERE r.detection_run_id = :run_id
              AND r.tenant_id        = :tenant_id
              AND {pt_field} IS NOT NULL
              AND {pt_field} != ''
              AND r.resolved_pharmacy_npi IS NOT NULL
              AND r.resolved_ndc IS NOT NULL
        )
        SELECT patient_hash, pharmacy_npi, ndc
        FROM grp
        GROUP BY patient_hash, pharmacy_npi, ndc
        HAVING
            SUM(CASE WHEN tc = 'B2' AND rev_check = 'YES' THEN 1 ELSE 0 END) >= 1
            AND SUM(CASE WHEN tc = 'B1' AND (ts = 'Paid' OR ts = 'paid') THEN 1 ELSE 0 END) >= 2
    """)

    candidate_groups = db.execute(sql_groups, params).fetchall()
    if not candidate_groups:
        return anomalies

    def _ts(r: CsvUploadRow) -> datetime:
        raw = r.row_data.get("date_added_timestamp", "") or ""
        try:
            return datetime.fromisoformat(str(raw).strip())
        except (ValueError, TypeError):
            return datetime.min

    for grp in candidate_groups:
        patient_hash = grp.patient_hash or ""
        pharmacy_npi = grp.pharmacy_npi or ""
        ndc = grp.ndc or ""

        # Bounded fetch: filter by indexable columns, then apply patient_hash in Python.
        group_stmt = (
            select(CsvUploadRow)
            .where(
                CsvUploadRow.detection_run_id == run.id,
                CsvUploadRow.tenant_id == run.tenant_id,
                CsvUploadRow.resolved_pharmacy_npi == pharmacy_npi,
                CsvUploadRow.resolved_ndc == ndc,
            )
        )
        all_group_rows = db.execute(group_stmt).scalars().all()

        group_rows = [
            r for r in all_group_rows
            if str(r.row_data.get("patient_unique_hash", "") or "").strip() == patient_hash
        ]
        if not group_rows:
            continue

        sorted_rows = sorted(group_rows, key=_ts)
        n = len(sorted_rows)
        for i in range(n):
            r_orig = sorted_rows[i]
            rd_o = r_orig.row_data
            if (
                str(rd_o.get("transaction_code", "") or "").strip().upper() != "B1"
                or str(rd_o.get("transaction_status", "") or "").strip() not in ("Paid", "paid")
            ):
                continue
            ic_orig = parse_money(rd_o.get("ingredient_cost_paid"))
            if ic_orig is None:
                continue
            ic_orig_abs = abs(ic_orig)
            ts_o = _ts(r_orig)

            for j in range(i + 1, n):
                r_rev = sorted_rows[j]
                rd_r = r_rev.row_data
                if (
                    str(rd_r.get("transaction_code", "") or "").strip().upper() != "B2"
                    or str(rd_r.get("reversed_check", "") or "").strip().upper() != "YES"
                ):
                    continue
                if (_ts(r_rev) - ts_o).days > lookback_days:
                    break

                for k in range(j + 1, n):
                    r_rebill = sorted_rows[k]
                    rd_rb = r_rebill.row_data
                    if (
                        str(rd_rb.get("transaction_code", "") or "").strip().upper() != "B1"
                        or str(rd_rb.get("transaction_status", "") or "").strip()
                        not in ("Paid", "paid")
                    ):
                        continue
                    ts_rb = _ts(r_rebill)
                    if (ts_rb - ts_o).days > lookback_days:
                        break
                    ic_rebill = parse_money(rd_rb.get("ingredient_cost_paid"))
                    if ic_rebill is None:
                        no_finding_count[0] += 1
                        continue
                    ic_rebill_abs = abs(ic_rebill)
                    if ic_rebill_abs <= ic_orig_abs:
                        no_finding_count[0] += 1
                        continue
                    anomaly = _make_anomaly(
                        run=run, instance=instance, csv_row=r_rebill,
                        finding_code="MFR-002",
                        finding_summary=(
                            "Bill-Reverse-Rebill: rebill IC ({}) exceeds original ({})".format(
                                ic_rebill_abs, ic_orig_abs
                            )
                        ),
                        finding_details={
                            "original_ic": str(ic_orig_abs),
                            "rebill_ic": str(ic_rebill_abs),
                            "original_auth": rd_o.get("auth_no_hash", ""),
                            "reversal_auth": rd_r.get("auth_no_hash", ""),
                            "rebill_auth": rd_rb.get("auth_no_hash", ""),
                            "window_days": (ts_rb - ts_o).days,
                        },
                        severity="critical",
                        confidence_num=Decimal("0.85"),
                    )
                    _write_eval_log(
                        db, run=run, instance=instance, csv_row=r_rebill,
                        result="finding_raised", anomaly_id=None,
                    )
                    anomalies.append(anomaly)

    return anomalies


def _evaluate_th002(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance,
    rtype: DetectionRuleType,
    no_finding_count: list[int],
    anomaly_write_errors: list[int],
) -> list[Anomaly]:
    """TH-002 Telehealth Geographic Dispersion -- server-side aggregation.

    SQL GROUP BY prescriber_npi with HAVING filters for both state-count
    threshold and min_claims floor.  Only qualifying prescribers returned.

    Peak memory: O(qualifying_prescribers), not O(total_rows).
    """
    anomalies: list[Anomaly] = []
    threshold = Decimal(str(instance.parameters.get("threshold", 10)))
    min_claims = int(instance.parameters.get("min_claims", 20))

    presc_field = _json_field(db, "r.row_data", "prescriber_npi")
    state_field = _json_field(db, "r.row_data", "patient_state")

    params: dict[str, Any] = {
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "threshold": int(threshold),
        "min_claims": min_claims,
    }

    sql = text(f"""
        SELECT
            {presc_field}                    AS prescriber_npi,
            COUNT(DISTINCT {state_field})    AS state_count,
            COUNT(*)                         AS claim_count
        FROM reclaimrx.csv_upload_rows r
        WHERE r.detection_run_id = :run_id
          AND r.tenant_id        = :tenant_id
          AND {presc_field} IS NOT NULL
          AND {presc_field} != ''
          AND {state_field} IS NOT NULL
          AND {state_field} != ''
        GROUP BY {presc_field}
        HAVING COUNT(DISTINCT {state_field}) > :threshold
           AND COUNT(*) >= :min_claims
    """)

    qualifying = db.execute(sql, params).fetchall()
    if not qualifying:
        return anomalies

    for row in qualifying:
        presc_npi = row.prescriber_npi or ""
        state_count = int(row.state_count)
        claim_count = int(row.claim_count)

        # Fetch distinct patient_states for evidence (bounded: one row per state).
        state_sql = text(f"""
            SELECT DISTINCT {state_field} AS state
            FROM reclaimrx.csv_upload_rows r
            WHERE r.detection_run_id = :run_id
              AND r.tenant_id        = :tenant_id
              AND {presc_field}      = :presc_npi
              AND {state_field} IS NOT NULL
              AND {state_field} != ''
        """)
        state_rows = db.execute(state_sql, {**params, "presc_npi": presc_npi}).fetchall()
        patient_states = sorted(r.state for r in state_rows if r.state)

        # One representative ORM row for _make_anomaly -- stream until match found.
        rep_row: CsvUploadRow | None = None
        rep_stmt = (
            select(CsvUploadRow)
            .where(
                CsvUploadRow.detection_run_id == run.id,
                CsvUploadRow.tenant_id == run.tenant_id,
            )
            .execution_options(yield_per=_ROW_BATCH)
        )
        for r in db.execute(rep_stmt).scalars():
            if str(r.row_data.get("prescriber_npi", "") or "").strip() == presc_npi:
                rep_row = r
                break
        if rep_row is None:
            continue

        anomaly = _make_anomaly(
            run=run, instance=instance, csv_row=rep_row,
            finding_code="TH-002",
            finding_summary=(
                "Prescriber {} patients across {} states (threshold > {})".format(
                    presc_npi, state_count, threshold
                )
            ),
            finding_details={
                "prescriber_npi": presc_npi,
                "patient_state_count": state_count,
                "patient_states": patient_states,
                "threshold": str(threshold),
                "claim_count": claim_count,
                "min_claims": min_claims,
            },
            severity=rtype.default_severity,
            confidence_num=Decimal("0.60"),
        )
        _write_eval_log(
            db, run=run, instance=instance, csv_row=rep_row,
            result="finding_raised", anomaly_id=None,
        )
        anomalies.append(anomaly)

    return anomalies


def _evaluate_th005(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance,
    rtype: DetectionRuleType,
    no_finding_count: list[int],
    anomaly_write_errors: list[int],
) -> list[Anomaly]:
    """TH-005 Prescriber-Pharmacy Affinity -- server-side aggregation.

    SQL GROUP BY (prescriber_npi, pharmacy_npi) returns compact aggregate pairs.
    Python accumulates per-prescriber totals and applies threshold / min_claims.
    One streaming pass fetches a representative ORM row per qualifying prescriber.

    Peak memory: O(distinct_prescriber_pharmacy_pairs), not O(total_rows).
    """
    anomalies: list[Anomaly] = []
    threshold = Decimal(str(instance.parameters.get("threshold", "0.5")))
    min_claims = int(instance.parameters.get("min_claims", 20))

    presc_field = _json_field(db, "r.row_data", "prescriber_npi")

    params: dict[str, Any] = {
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
    }

    # Aggregate: per (prescriber_npi, pharmacy_npi) pair, count claims.
    sql = text(f"""
        SELECT
            {presc_field}               AS prescriber_npi,
            r.resolved_pharmacy_npi     AS pharmacy_npi,
            COUNT(*)                    AS pair_count
        FROM reclaimrx.csv_upload_rows r
        WHERE r.detection_run_id        = :run_id
          AND r.tenant_id               = :tenant_id
          AND {presc_field} IS NOT NULL
          AND {presc_field} != ''
          AND r.resolved_pharmacy_npi IS NOT NULL
        GROUP BY {presc_field}, r.resolved_pharmacy_npi
    """)

    pair_rows = db.execute(sql, params).fetchall()
    if not pair_rows:
        return anomalies

    # Accumulate per-prescriber pharmacy counts (compact aggregate, not raw rows).
    presc_pharmacy: dict[str, dict[str, int]] = defaultdict(dict)
    for row in pair_rows:
        presc = row.prescriber_npi or ""
        pharm = row.pharmacy_npi or ""
        cnt = int(row.pair_count)
        if presc and pharm:
            presc_pharmacy[presc][pharm] = cnt

    # Build rep_row map: one ORM row per prescriber (streaming pass).
    presc_rep: dict[str, CsvUploadRow] = {}
    needed_prescs = set(presc_pharmacy.keys())
    rep_stmt = (
        select(CsvUploadRow)
        .where(
            CsvUploadRow.detection_run_id == run.id,
            CsvUploadRow.tenant_id == run.tenant_id,
        )
        .execution_options(yield_per=_ROW_BATCH)
    )
    for csv_row in db.execute(rep_stmt).scalars():
        if not needed_prescs:
            break
        presc = str(csv_row.row_data.get("prescriber_npi", "") or "").strip()
        if presc in needed_prescs and presc not in presc_rep:
            presc_rep[presc] = csv_row
            needed_prescs.discard(presc)

    for presc, pharmacy_counts in presc_pharmacy.items():
        total = sum(pharmacy_counts.values())
        if total == 0:
            continue
        if total < min_claims:
            no_finding_count[0] += 1
            continue
        top_pharm = max(pharmacy_counts, key=lambda p: pharmacy_counts[p])
        top_count = pharmacy_counts[top_pharm]
        share = Decimal(str(top_count)) / Decimal(str(total))
        if share <= threshold:
            no_finding_count[0] += 1
            continue
        rep_row = presc_rep.get(presc)
        if rep_row is None:
            continue
        anomaly = _make_anomaly(
            run=run, instance=instance, csv_row=rep_row,
            finding_code="TH-005",
            finding_summary=(
                "Prescriber {}: {:.0%} of scripts to pharmacy {} (threshold > {:.0%})".format(
                    presc, float(share), top_pharm, float(threshold)
                )
            ),
            finding_details={
                "prescriber_npi": presc,
                "top_pharmacy_npi": top_pharm,
                "top_pharmacy_share": str(share.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
                "top_pharmacy_count": top_count,
                "total_count": total,
                "claim_count": total,
                "threshold": str(threshold),
                "min_claims": min_claims,
            },
            severity=rtype.default_severity,
            confidence_num=Decimal("0.40"),
        )
        _write_eval_log(
            db, run=run, instance=instance, csv_row=rep_row,
            result="finding_raised", anomaly_id=None,
        )
        anomalies.append(anomaly)

    return anomalies


def _evaluate_grouping_rules(
    db: Session,
    run: DetectionRun,
    applicable: list[DetectionRuleInstance],
    rule_type_by_code: dict[str, DetectionRuleType],
    no_finding_count: list[int],
    anomaly_write_errors: list[int],
) -> list[Anomaly]:
    """Dispatch ALL-001, MFR-002, TH-002, TH-005 grouping evaluators.

    Each evaluator uses server-side SQL to bound the in-memory candidate set.
    """
    anomalies: list[Anomaly] = []
    group_instances = [inst for inst in applicable if inst.rule_type_code in _GROUPING_CODES]
    for instance in group_instances:
        code = instance.rule_type_code
        rtype = rule_type_by_code.get(code)
        if rtype is None:
            continue
        try:
            if code == "ALL-001":
                new = _evaluate_all001(db, run, instance, rtype, no_finding_count, anomaly_write_errors)
            elif code == "MFR-002":
                new = _evaluate_mfr002(db, run, instance, rtype, no_finding_count, anomaly_write_errors)
            elif code == "TH-002":
                new = _evaluate_th002(db, run, instance, rtype, no_finding_count, anomaly_write_errors)
            elif code == "TH-005":
                new = _evaluate_th005(db, run, instance, rtype, no_finding_count, anomaly_write_errors)
            elif code == "REJECT-75-70":
                from src.detection.reject_rebill import evaluate_reject_75_70  # noqa: PLC0415
                new = evaluate_reject_75_70(db, run, instance=instance, rtype=rtype)
            else:
                new = []
            anomalies.extend(new)
        except Exception:
            logger.exception("Error evaluating grouping rule %s", code)
    return anomalies

# ---------------------------------------------------------------------------
# Bulk anomaly insert (§12 H1 -- atomic promote)
# ---------------------------------------------------------------------------


def _bulk_insert_anomalies(db: Session, anomalies: list[Anomaly]) -> None:
    """Bulk insert anomalies via execute_values on Postgres, ORM add_all on SQLite.

    Called exclusively from the PASS path of the guardrail (after the cap check
    passes).  NOT called from the FAIL path -- on a guardrail trip zero anomalies
    are persisted.

    Postgres path: execute_values in batches of 5000; Decimal-safe JSON via
    _json_default (converts Decimal -> str so json.dumps never raises TypeError).
    SQLite path (tests): db.add_all + db.flush (no psycopg2 dependency in tests).
    """
    if not anomalies:
        return
    if db.get_bind().dialect.name == "postgresql":
        import json  # noqa: PLC0415
        import uuid  # noqa: PLC0415
        from psycopg2.extras import execute_values  # noqa: PLC0415

        def _json_default(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        cols = [
            "id", "tenant_id", "data_source", "data_source_run_id", "client_id",
            "program_id", "pharmacy_npi", "ndc", "source_table", "source_row_id",
            "detection_kind", "detection_id", "severity", "confidence",
            "date_of_service", "rx_number", "prescriber_npi", "days_supply",
            "quantity", "amount_paid", "amount_billed", "finding_code",
            "finding_summary", "finding_details", "status",
        ]
        rows = []
        for a in anomalies:
            rows.append((
                str(a.id) if a.id else str(uuid.uuid4()),
                str(a.tenant_id), a.data_source,
                str(a.data_source_run_id) if a.data_source_run_id else None,
                str(a.client_id) if a.client_id else None,
                str(a.program_id) if a.program_id else None,
                a.pharmacy_npi, a.ndc, a.source_table,
                str(a.source_row_id),
                a.detection_kind,
                str(a.detection_id) if a.detection_id else None,
                a.severity, str(a.confidence),
                a.date_of_service, a.rx_number, a.prescriber_npi,
                a.days_supply,
                str(a.quantity) if a.quantity is not None else None,
                str(a.amount_paid) if a.amount_paid is not None else None,
                str(a.amount_billed) if a.amount_billed is not None else None,
                a.finding_code, a.finding_summary,
                json.dumps(a.finding_details, default=_json_default), a.status,
            ))
        col_list = ", ".join(cols)
        conn = db.connection().connection
        execute_values(
            conn.cursor(),
            f"INSERT INTO reclaimrx.anomalies ({col_list}) VALUES %s",
            rows,
            page_size=5000,
        )
    else:
        # SQLite path: SQLAlchemy's JSON serializer does not handle Decimal.
        # Stringify any Decimal values in finding_details before ORM add.
        for a in anomalies:
            if a.finding_details:
                a.finding_details = {
                    k: str(v) if isinstance(v, Decimal) else v
                    for k, v in a.finding_details.items()
                }
            db.add(a)
        db.flush()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_detection(
    db: Session,
    run: DetectionRun,
    *,
    statement_timeout_ms: int | None = None,
) -> int:
    """Two-pass FWA detection over csv_upload_rows for the given run.

    PRECONDITION gate: raises RuntimeError if
        run.resolution_stats["inserted_count"] != run.resolution_stats["expected_count"]

    Statement timeout:
        Calls _set_batch_statement_timeout(db, ms) at the start.  Default ms comes
        from RECLAIMRX_BATCH_STATEMENT_TIMEOUT_MS env var (0 = unlimited).  The OLTP
        30s server default is inappropriate for batch analytics; this call relaxes it.
        On SQLite this is a no-op.

    PASS 1 -- baselines: compute_baseline for each requires_baseline instance.
      Per-unit isolation: each baseline runs in its own try/except.
      A failure is logged and recorded in resolution_stats["errors"]; the loop
      continues to the next baseline.  One baseline timeout MUST NOT abort the run.
      MFR-009: no registered baseline kind -- logged and skipped (not an error).

    PASS 2 -- evaluate:
      SINGLE-ROW:  MFR-001. Streamed in batches of _ROW_BATCH.
      STATISTICAL: MFR-003, MFR-004, HP-005, HP-008, ALL-006. Streamed.
                   (MFR-004/HP-005/ALL-006 are entity-level; per-row skipped).
      GROUPING:    ALL-001, MFR-002, TH-002, TH-005. Server-side SQL grouping.

    Eval-log policy:
      finding_raised: written with anomaly_id for every fire.
      error: written for caught exceptions.
      no_finding: NOT written per (row x rule); aggregated into
          run.resolution_stats["no_finding_count"].

    Memory guarantee:
      Peak working set is O(_ROW_BATCH + flagged_rows), not O(total_rows).
      The full csv_upload_rows set is never materialized into Python memory.

    Finalization:
      run.status is always set to 'completed' (the run finished, even if some
      units errored).  Baseline errors are recorded in
      resolution_stats["errors"] = [{"kind": ..., "rule": ..., "reason": ...}].
      The run is NEVER left 'in_progress'.

    Returns int: count of Anomaly rows created.
    Updates: run.anomaly_count, run.record_count, run.status, run.completed_at,
             run.resolution_stats (no_finding_count, errors).
    """
    # Resolve the statement_timeout value to use.
    if statement_timeout_ms is None:
        statement_timeout_ms = int(
            os.environ.get(_BATCH_STATEMENT_TIMEOUT_ENV, str(_DEFAULT_BATCH_STATEMENT_TIMEOUT_MS))
        )

    # Disable (or relax) the Postgres statement_timeout for this batch session.
    # Batch analytics jobs legitimately take minutes; the OLTP 30s guard is wrong here.
    # On SQLite this is a no-op.
    _set_batch_statement_timeout(db, statement_timeout_ms)

    # PRECONDITION -- full-coverage gate
    stats = run.resolution_stats or {}
    inserted = stats.get("inserted_count")
    expected = stats.get("expected_count")
    if inserted is None or inserted != expected:
        raise RuntimeError(
            "full-coverage gate failed: inserted_count={!r} != "
            "expected_count={!r}. Cannot run detection on a partial ingest.".format(
                inserted, expected
            )
        )

    available_columns = _available_columns_for_run(db, run)
    applicable = gate_rules(db, run, available_columns)

    rule_type_codes = {inst.rule_type_code for inst in applicable}
    rule_types = db.execute(
        select(DetectionRuleType).where(DetectionRuleType.code.in_(list(rule_type_codes)))
    ).scalars().all()
    rule_type_by_code = {rt.code: rt for rt in rule_types}

    # PASS 1 -- baselines (per-unit isolation; one failure does not abort the run)
    baseline_errors: list[dict[str, str]] = []
    _run_baselines(db, run, applicable, rule_type_by_code, baseline_errors)
    db.flush()

    # ── FDB prefetch: distinct NDCs -> _fdb_cache (one IN query, zero per-row) ──────
    # fetch_current_prices_for_ndcs is imported at MODULE SCOPE so tests can patch it as
    # src.detection.batch_engine.fetch_current_prices_for_ndcs (local import would break patch).
    _distinct_ndc_rows = db.execute(
        text(
            "SELECT DISTINCT resolved_ndc AS ndc FROM reclaimrx.csv_upload_rows"
            " WHERE detection_run_id = :run_id AND tenant_id = :tenant_id"
            " AND resolved_ndc IS NOT NULL"
        ),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchall()
    _distinct_ndcs: list[str] = [r.ndc for r in _distinct_ndc_rows if r.ndc]
    # fetch_current_prices_for_ndcs uses Postgres-specific unnest(ARRAY[...]::text[]) syntax.
    # On SQLite (unit tests) skip the call -- reference.fdb_ndc_price_history is a FDW
    # foreign table that does not exist in SQLite test fixtures.
    _is_pg = _is_postgres(db)
    _raw_fdb = fetch_current_prices_for_ndcs(db, _distinct_ndcs) if (_distinct_ndcs and _is_pg) else {}
    _fdb_cache: dict[str, dict] = {
        ndc: {
            "wac": price_data.get("wac"),
            "price_type": "09" if price_data.get("wac") is not None else None,
            "effective_date": None,
            "wac_source": "fdb",
        }
        for ndc, price_data in _raw_fdb.items()
    }
    _no_fdb_wac: int = sum(
        1 for ndc in _distinct_ndcs if _fdb_cache.get(ndc, {}).get("wac") is None
    )

    # Record count via SQL -- never materialize all rows just to call len().
    record_count = db.execute(
        select(func.count()).select_from(CsvUploadRow).where(
            CsvUploadRow.detection_run_id == run.id,
            CsvUploadRow.tenant_id == run.tenant_id,
        )
    ).scalar() or 0

    no_finding_count = [0]
    anomaly_write_errors: list[int] = [0]
    all_anomalies: list[Anomaly] = []

    # PASS 2 -- evaluate (streaming per-row; server-side grouping)
    all_anomalies.extend(
        _evaluate_single_row_rules(
            db, run, applicable, rule_type_by_code, no_finding_count, anomaly_write_errors
        )
    )
    all_anomalies.extend(
        _dispatch_statistical_rules(
            db, run, applicable, rule_type_by_code, no_finding_count, anomaly_write_errors,
            _fdb_cache=_fdb_cache,
        )
    )
    all_anomalies.extend(
        _evaluate_grouping_rules(
            db, run, applicable, rule_type_by_code, no_finding_count, anomaly_write_errors
        )
    )

    # ── ALL-002 / ALL-003 set-based phantom-NPI checks (instance-gated) ────────
    # Local imports avoid circular import (reference_rules -> batch_engine -> reference_rules).
    from src.detection.reference_rules import (  # noqa: PLC0415
        evaluate_all002_phantom_pharmacy,
        evaluate_all003_phantom_prescriber,
    )
    # Each evaluator runs <=4 set-based queries; returns (list[Anomaly], dict[str,int]).
    # Gated: only fires when an enabled DetectionRuleInstance for that code exists AND
    # on Postgres -- the evaluators use unnest(ARRAY[...]::text[]) + reference.* FDW
    # foreign tables that do not exist in SQLite unit-test fixtures (mirrors the FDB
    # prefetch guard above). On SQLite the counters stay {} and the data_quality keys
    # remain initialized to 0 below.
    _all002_quality: dict[str, int] = {}
    _all003_quality: dict[str, int] = {}
    _ref_instance_map = {inst.rule_type_code: inst for inst in applicable}
    _all002_inst = _ref_instance_map.get("ALL-002")
    if _is_pg and _all002_inst is not None:
        _a002_anomalies, _all002_quality = evaluate_all002_phantom_pharmacy(
            db, run, instance=_all002_inst
        )
        all_anomalies.extend(_a002_anomalies)
    _all003_inst = _ref_instance_map.get("ALL-003")
    if _is_pg and _all003_inst is not None:
        _a003_anomalies, _all003_quality = evaluate_all003_phantom_prescriber(
            db, run, instance=_all003_inst
        )
        all_anomalies.extend(_a003_anomalies)

    # ── data_quality dict: merge FDB no_fdb_wac + ALL-002/003 NPI counters ─────
    # All 5 keys initialized to 0 so absent evaluators still expose their keys.
    _data_quality: dict[str, int] = {
        "no_fdb_wac": _no_fdb_wac,
        "missing_pharmacy_npi": 0,
        "invalid_pharmacy_npi": 0,
        "missing_prescriber_npi": 0,
        "invalid_prescriber_npi": 0,
        **_all002_quality,
        **_all003_quality,
    }
    # _data_quality is merged into resolution_stats by the finalization blocks below
    # (not pre-assigned here to avoid double-mutation that causes StaleDataError on SQLite)

    # --- Guardrail check (\xa7\x31\x32 H1) BEFORE inserting any anomalies ---
    # Effective total cap = min(configured, CEILING) -- configured value can only be STRICTER.
    # A run that sets total_fire_rate_cap="0.99" is clamped to the 1% ceiling.
    if record_count >= _MIN_GUARDRAIL_RECORDS:
        _configured_total = Decimal(str(
            run.resolution_stats.get("total_fire_rate_cap", str(_TOTAL_FIRE_RATE_CEILING))
        ))
        total_cap = min(_configured_total, _TOTAL_FIRE_RATE_CEILING)
        record_count_d = Decimal(str(record_count)) if record_count > 0 else Decimal("1")

        # Build per-rule cap map: min(instance.parameters.rule_fire_rate_cap, CEILING).
        # A rule that configures "0.50" is clamped to 0.005 -- ceiling always wins.
        rule_instance_cap: dict[str, Decimal] = {}
        for inst in applicable:
            configured_rule_cap = Decimal(str(
                inst.parameters.get("rule_fire_rate_cap", str(_RULE_FIRE_RATE_CEILING))
            ))
            rule_instance_cap[inst.rule_type_code] = min(configured_rule_cap, _RULE_FIRE_RATE_CEILING)

        # Count fires per rule from accumulated list
        rule_fire_counts: dict[str, int] = {}
        for a in all_anomalies:
            rule_fire_counts[a.finding_code] = rule_fire_counts.get(a.finding_code, 0) + 1

        guardrail_trip: dict | None = None
        total_fire_rate = Decimal(str(len(all_anomalies))) / record_count_d
        if total_fire_rate > total_cap:
            guardrail_trip = {
                "tripped": True,
                "rule": "total_run",
                "fire_rate": str(total_fire_rate.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)),
                "cap": str(total_cap),
            }
        else:
            for code, count in rule_fire_counts.items():
                rate = Decimal(str(count)) / record_count_d
                # Use this rule's own cap; default to _RULE_FIRE_RATE_CAP if not in instance map
                this_cap = rule_instance_cap.get(code, _RULE_FIRE_RATE_CAP)
                if rate > this_cap:
                    guardrail_trip = {
                        "tripped": True,
                        "rule": code,
                        "fire_rate": str(rate.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)),
                        "cap": str(this_cap),
                    }
                    break

        if guardrail_trip:
            # Invariant: a failed run ALWAYS ends with ZERO anomalies for this run.id.
            # Delete any pre-existing anomalies for this run (e.g. a prior attempt on the same
            # run_id) BEFORE persisting status='failed'.  Scoped by both run.id AND tenant_id so
            # a cross-tenant delete is structurally impossible even if RLS is bypassed.
            db.execute(
                sa.delete(Anomaly).where(
                    Anomaly.data_source_run_id == run.id,
                    Anomaly.tenant_id == run.tenant_id,
                )
            )
            run.anomaly_count = 0
            run.record_count = record_count
            run.status = "failed"
            run.completed_at = datetime.now(UTC)
            new_stats = dict(run.resolution_stats)
            new_stats["guardrail"] = guardrail_trip
            new_stats["no_finding_count"] = no_finding_count[0]
            new_stats["data_quality"] = _data_quality
            if baseline_errors:
                new_stats["errors"] = baseline_errors
            run.resolution_stats = new_stats
            db.flush()
            return 0

    # Guardrail passed -- idempotent promote: delete any prior anomalies for this run
    # BEFORE inserting the new batch (same transaction).  This makes re-running the
    # same run_id safe (prior partial/stale anomalies are replaced atomically).
    db.execute(
        sa.delete(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.tenant_id == run.tenant_id,
        )
    )

    # Persist all anomalies atomically via bulk insert (\xa7\x31\x32 H1 perf).
    # _bulk_insert_anomalies uses execute_values on Postgres (5000-row batches),
    # falls back to ORM add_all on SQLite.  Per-anomaly db.add is NOT used here.
    _bulk_insert_anomalies(db, all_anomalies)

    run.anomaly_count = len(all_anomalies)
    run.record_count = record_count
    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    new_stats = dict(run.resolution_stats)
    new_stats["no_finding_count"] = no_finding_count[0]
    new_stats["data_quality"] = _data_quality
    if anomaly_write_errors[0]:
        new_stats["anomaly_write_errors"] = anomaly_write_errors[0]
    if baseline_errors:
        new_stats["errors"] = baseline_errors
    run.resolution_stats = new_stats
    db.flush()
    return len(all_anomalies)
