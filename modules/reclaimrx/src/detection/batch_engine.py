"""Batch detection engine: applicability gate (Task 3.4) + two-pass detection (Task 3.5).

gate_rules(db, run, available_columns) -> list[DetectionRuleInstance]
    Loads enabled DetectionRuleInstance rows for run.tenant_id, joins DetectionRuleType,
    returns APPLICABLE subset; writes skipped_inapplicable log rows for non-applicable ones.

run_detection(db, run) -> int
    PRECONDITION: raises RuntimeError if inserted_count != expected_count.
    PASS 1 - baselines: compute_baseline for each requires_baseline instance.
    PASS 2 - single-row (MFR-001), statistical (MFR-003/4, HP-005/8, ALL-006),
             grouping (ALL-001, MFR-002, TH-002, TH-005).
    Returns count of Anomaly rows created.

MFR-008 deferred: needs statement-only-pharmacy reference data (dry-run fix).
TH-002/TH-005 min-volume floor: skip prescribers below min_claims (default 20)
    to prevent false-positive floods on low-volume prescribers.

CHECKs satisfied by skip rows:
  ck_reclaimrx_eval_log_result            - skipped_inapplicable is in the enum
  ck_reclaimrx_eval_log_per_claim_columns - skipped_inapplicable permits NULL source
  ck_reclaimrx_eval_log_error_iff_message - error_message NULL and result != error
  ck_reclaimrx_eval_log_anomaly_id_iff_finding - anomaly_id NULL and result != finding_raised
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.detection.baselines import compute_baseline
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

_BASELINE_KIND_MAP: dict[str, str] = {
    "MFR-004": "pharmacy_ndc_volume",
    "MFR-003": "pharmacy_own_rate_history",
    "HP-005":  "prescriber_peer_volume",
    "HP-008":  "member_cost",
    "ALL-006": "pharmacy_weekday_volume",
}

_SINGLE_ROW_CODES: frozenset[str] = frozenset({"MFR-001"})
_STATISTICAL_CODES: frozenset[str] = frozenset({"MFR-003", "MFR-004", "HP-005", "HP-008", "ALL-006"})
_GROUPING_CODES: frozenset[str] = frozenset({"ALL-001", "MFR-002", "TH-002", "TH-005"})
_ZERO = Decimal("0")


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
    return Anomaly(
        tenant_id=run.tenant_id,
        data_source="csv_upload",
        data_source_run_id=run.id,
        client_id=csv_row.resolved_client_id,
        program_id=csv_row.resolved_program_id,
        pharmacy_npi=csv_row.resolved_pharmacy_npi,
        ndc=csv_row.resolved_ndc,
        source_table="csv_upload_rows",
        source_row_id=csv_row.id,
        detection_kind="rule",
        detection_id=instance.id,
        severity=severity,
        confidence=confidence_num,
        date_of_service=dos_val,
        rx_number=rd.get("rx_number_hash"),
        prescriber_npi=rd.get("prescriber_npi") or None,
        days_supply=days_supply,
        quantity=quantity,
        amount_paid=amount_paid,
        amount_billed=amount_billed,
        finding_code=finding_code,
        finding_summary=finding_summary,
        finding_details=finding_details,
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
# Pass 1 - Baseline computation
# ---------------------------------------------------------------------------


def _run_baselines(
    db: Session,
    run: DetectionRun,
    applicable: list[DetectionRuleInstance],
    rule_type_by_code: dict[str, DetectionRuleType],
) -> None:
    """For each applicable instance whose type.requires_baseline, compute the baseline.

    MFR-009: no baseline kind registered -- logged and skipped.
    """
    for instance in applicable:
        rtype = rule_type_by_code.get(instance.rule_type_code)
        if rtype is None or not rtype.requires_baseline:
            continue
        code = instance.rule_type_code
        kind = _BASELINE_KIND_MAP.get(code)
        if kind is None:
            logger.info("No baseline kind registered for rule %s -- skipping baseline computation", code)
            continue
        try:
            n = compute_baseline(db, run, kind=kind)
            logger.debug("Baseline kind=%s rule=%s: %d rows written", kind, code, n)
        except Exception:
            logger.exception("Baseline computation failed for kind=%s rule=%s", kind, code)


# ---------------------------------------------------------------------------
# Pass 2 - single-row evaluation
# ---------------------------------------------------------------------------



def _evaluate_single_row_rules(
    db: Session,
    run: DetectionRun,
    applicable: list[DetectionRuleInstance],
    rule_type_by_code: dict[str, DetectionRuleType],
    csv_rows: list[CsvUploadRow],
    no_finding_count: list[int],
) -> list[Anomaly]:
    """Evaluate MFR-001 per csv_upload_row."""
    anomalies: list[Anomaly] = []
    single_instances = [inst for inst in applicable if inst.rule_type_code in _SINGLE_ROW_CODES]
    for instance in single_instances:
        code = instance.rule_type_code
        rtype = rule_type_by_code.get(code)
        if rtype is None:
            continue
        params = dict(instance.parameters)
        params["confidence_scoring"] = _build_confidence_scoring(params)
        for csv_row in csv_rows:
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
                db.add(anomaly)
                db.flush()
                _write_eval_log(db, run=run, instance=instance, csv_row=csv_row,
                                result="finding_raised", anomaly_id=anomaly.id)
                anomalies.append(anomaly)
            except Exception:
                logger.exception("Error evaluating rule %s on csv_row %s", code, csv_row.id)
                _write_eval_log(db, run=run, instance=instance, csv_row=csv_row,
                                result="error", error_message=f"Evaluation error for {code}")
    return anomalies


# ---------------------------------------------------------------------------
# Pass 2 - statistical evaluation
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
    applicable: list[DetectionRuleInstance],
    rule_type_by_code: dict[str, DetectionRuleType],
    csv_rows: list[CsvUploadRow],
    no_finding_count: list[int],
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    stat_instances = [inst for inst in applicable if inst.rule_type_code in _STATISTICAL_CODES]
    if not stat_instances:
        return anomalies
    for instance in stat_instances:
        code = instance.rule_type_code
        rtype = rule_type_by_code.get(code)
        if rtype is None:
            continue
        kind = _BASELINE_KIND_MAP.get(code)
        if kind is None:
            continue
        baseline_cache = _load_baseline_cache(db, run, kind)
        if not baseline_cache:
            logger.debug("No baseline cache for kind=%s; skipping statistical rule %s", kind, code)
            continue
        params = dict(instance.parameters)
        params["confidence_scoring"] = _build_confidence_scoring(params)
        for csv_row in csv_rows:
            rd = csv_row.row_data
            scope_key = _scope_key_for_row(code, rd, csv_row)
            if scope_key is None:
                no_finding_count[0] += 1
                continue
            baseline = baseline_cache.get(scope_key)
            if baseline is None:
                no_finding_count[0] += 1
                continue
            try:
                extra = _derive_statistical_metric(code, rd, baseline)
            except Exception:
                no_finding_count[0] += 1
                continue
            if not extra:
                no_finding_count[0] += 1
                continue
            fields: dict[str, Any] = {**rd, **extra}
            try:
                result = evaluate_threshold(fields, params)
                if not result.fired:
                    no_finding_count[0] += 1
                    continue
                confidence_num = _confidence_tier_to_num(result.confidence or "medium")
                anomaly = _make_anomaly(
                    run=run, instance=instance, csv_row=csv_row,
                    finding_code=code,
                    finding_summary=(
                        f"{rtype.name}: {params.get('field', '')} "
                        f"{params.get('operator', '')} {params.get('threshold', '')}"
                    ),
                    finding_details={**result.evidence, "scope_key": scope_key},
                    severity=result.severity or rtype.default_severity,
                    confidence_num=confidence_num,
                )
                db.add(anomaly)
                db.flush()
                _write_eval_log(db, run=run, instance=instance, csv_row=csv_row,
                                result="finding_raised", anomaly_id=anomaly.id)
                anomalies.append(anomaly)
            except Exception:
                logger.exception("Error in statistical rule %s on csv_row %s", code, csv_row.id)
                _write_eval_log(db, run=run, instance=instance, csv_row=csv_row,
                                result="error", error_message=f"Evaluation error for {code}")
    return anomalies



# ---------------------------------------------------------------------------
# Pass 2 -- grouping rules
# ---------------------------------------------------------------------------


def _evaluate_all001(
    db,
    run,
    instance,
    rtype,
    csv_rows,
    no_finding_count,
):
    """ALL-001 Duplicate Claim.

    Group key: (client_id, patient_unique_hash, resolved_ndc, date_of_service).
    Eligible rows: B1/Paid only; skip Duplicate/Reversed status rows.
    Lifecycle filter: skip groups containing any reversed_check=Yes row (BRB pattern).
    Fire: >= 2 DISTINCT auth_no_hash per group. One anomaly per row in group.
    """
    anomalies = []
    reversal_groups = set()
    eligible = {}

    for csv_row in csv_rows:
        rd = csv_row.row_data
        pt = str(rd.get("patient_unique_hash", "") or "").strip()
        ndc = str(csv_row.resolved_ndc or "")
        dos_raw = str(rd.get("date_of_service", "") or "").strip()
        client = str(rd.get("client_id", "") or "").strip()
        dos_parsed = parse_dos(dos_raw)
        if not pt or not dos_parsed:
            continue
        gk = (client, pt, ndc, dos_parsed)

        if str(rd.get("reversed_check", "") or "").strip().upper() == "YES":
            reversal_groups.add(gk)

        tc = str(rd.get("transaction_code", "") or "").strip().upper()
        ts = str(rd.get("transaction_status", "") or "").strip()
        if tc != "B1" or ts not in ("Paid", "paid"):
            continue
        if ts in ("Duplicate", "Reversed"):
            continue

        auth = str(rd.get("auth_no_hash", "") or "").strip()
        if gk not in eligible:
            eligible[gk] = {}
        if auth not in eligible[gk]:
            eligible[gk][auth] = []
        eligible[gk][auth].append(csv_row)

    for gk, auth_map in eligible.items():
        if gk in reversal_groups:
            for rows in auth_map.values():
                no_finding_count[0] += len(rows)
            continue
        if len(auth_map) < 2:
            for rows in auth_map.values():
                no_finding_count[0] += len(rows)
            continue
        auth_hashes = list(auth_map.keys())
        all_group_rows = [r for rows in auth_map.values() for r in rows]
        for csv_row in all_group_rows:
            anomaly = _make_anomaly(
                run=run, instance=instance, csv_row=csv_row,
                finding_code="ALL-001",
                finding_summary=(
                    "Duplicate claim: {} distinct auth numbers for same member/NDC/DOS".format(len(auth_hashes))
                ),
                finding_details={
                    "group_key": {
                        "patient_unique_hash": gk[1],
                        "ndc": gk[2],
                        "date_of_service": str(gk[3]),
                        "client_id": gk[0],
                    },
                    "auth_count": len(auth_hashes),
                    "auth_hashes": auth_hashes,
                },
                severity="critical",
                confidence_num=Decimal("0.85"),
            )
            db.add(anomaly)
            db.flush()
            _write_eval_log(
                db, run=run, instance=instance, csv_row=csv_row,
                result="finding_raised", anomaly_id=anomaly.id,
            )
            anomalies.append(anomaly)

    return anomalies


def _evaluate_mfr002(
    db,
    run,
    instance,
    rtype,
    csv_rows,
    no_finding_count,
):
    """MFR-002 Bill-Reverse-Rebill.

    Group: (patient_unique_hash, resolved_pharmacy_npi, resolved_ndc).
    Sort by date_added_timestamp.
    Pattern: B1(Paid) -> B2(reversed_check=Yes) -> B1(Paid) within lookback_days.
    Fire only when rebill abs(IC) > original abs(IC). Flag rebill row only.
    """
    anomalies = []
    lookback_days = int(instance.parameters.get("lookback_days", 14))
    groups = defaultdict(list)
    for csv_row in csv_rows:
        rd = csv_row.row_data
        pt = str(rd.get("patient_unique_hash", "") or "").strip()
        npi = str(csv_row.resolved_pharmacy_npi or "").strip()
        ndc = str(csv_row.resolved_ndc or "").strip()
        if pt and npi and ndc:
            groups[(pt, npi, ndc)].append(csv_row)

    def _ts(r):
        raw = r.row_data.get("date_added_timestamp", "") or ""
        try:
            return datetime.fromisoformat(str(raw).strip())
        except (ValueError, TypeError):
            return datetime.min

    for _gk, group_rows in groups.items():
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
                    db.add(anomaly)
                    db.flush()
                    _write_eval_log(
                        db, run=run, instance=instance, csv_row=r_rebill,
                        result="finding_raised", anomaly_id=anomaly.id,
                    )
                    anomalies.append(anomaly)
    return anomalies


def _evaluate_th002(
    db,
    run,
    instance,
    rtype,
    csv_rows,
    no_finding_count,
):
    """TH-002 Telehealth Geographic Dispersion.

    Group by prescriber_npi; count distinct patient_state values.
    Fire if count > threshold (default 10) AND total claim count >= min_claims
    (default 20).  A prescriber with 11 claims trivially spans 11 states —
    min_claims prevents false-positive floods on low-volume prescribers.
    min_claims is tenant-configurable via instance.parameters (Principle 12).
    """
    anomalies = []
    threshold = Decimal(str(instance.parameters.get("threshold", 10)))
    min_claims = int(instance.parameters.get("min_claims", 20))
    presc_states = defaultdict(dict)
    presc_claims = defaultdict(int)
    presc_rep = {}
    for csv_row in csv_rows:
        rd = csv_row.row_data
        presc = str(rd.get("prescriber_npi", "") or "").strip()
        state = str(rd.get("patient_state", "") or "").strip()
        if not presc or not state:
            continue
        presc_claims[presc] += 1
        if state not in presc_states[presc]:
            presc_states[presc][state] = csv_row
        if presc not in presc_rep:
            presc_rep[presc] = csv_row
    for presc, states_map in presc_states.items():
        claim_count = presc_claims[presc]
        if claim_count < min_claims:
            no_finding_count[0] += 1
            continue
        state_count = len(states_map)
        if Decimal(str(state_count)) <= threshold:
            no_finding_count[0] += 1
            continue
        rep_row = presc_rep[presc]
        anomaly = _make_anomaly(
            run=run, instance=instance, csv_row=rep_row,
            finding_code="TH-002",
            finding_summary=(
                "Prescriber {} patients across {} states (threshold > {})".format(
                    presc, state_count, threshold
                )
            ),
            finding_details={
                "prescriber_npi": presc,
                "patient_state_count": state_count,
                "patient_states": sorted(states_map.keys()),
                "threshold": str(threshold),
                "claim_count": claim_count,
                "min_claims": min_claims,
            },
            severity=rtype.default_severity,
            confidence_num=Decimal("0.60"),
        )
        db.add(anomaly)
        db.flush()
        _write_eval_log(
            db, run=run, instance=instance, csv_row=rep_row,
            result="finding_raised", anomaly_id=anomaly.id,
        )
        anomalies.append(anomaly)
    return anomalies


def _evaluate_th005(
    db,
    run,
    instance,
    rtype,
    csv_rows,
    no_finding_count,
):
    """TH-005 Prescriber-Pharmacy Affinity.

    Group by prescriber_npi; compute top pharmacy share.
    Fire when share > threshold (default 0.5) AND total claim count >= min_claims
    (default 20).  A prescriber with 1-2 claims trivially has 100% pharmacy share
    — min_claims prevents false-positive floods on low-volume prescribers.
    min_claims is tenant-configurable via instance.parameters (Principle 12).
    """
    anomalies = []
    threshold = Decimal(str(instance.parameters.get("threshold", "0.5")))
    min_claims = int(instance.parameters.get("min_claims", 20))
    presc_pharmacy = defaultdict(lambda: defaultdict(int))
    presc_rep = {}
    for csv_row in csv_rows:
        rd = csv_row.row_data
        presc = str(rd.get("prescriber_npi", "") or "").strip()
        pharm = str(csv_row.resolved_pharmacy_npi or "").strip()
        if not presc or not pharm:
            continue
        presc_pharmacy[presc][pharm] += 1
        if presc not in presc_rep:
            presc_rep[presc] = csv_row
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
        rep_row = presc_rep[presc]
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
        db.add(anomaly)
        db.flush()
        _write_eval_log(
            db, run=run, instance=instance, csv_row=rep_row,
            result="finding_raised", anomaly_id=anomaly.id,
        )
        anomalies.append(anomaly)
    return anomalies


def _evaluate_grouping_rules(
    db,
    run,
    applicable,
    rule_type_by_code,
    csv_rows,
    no_finding_count,
):
    """Dispatch ALL-001, MFR-002, TH-002, TH-005 grouping evaluators."""
    anomalies = []
    group_instances = [inst for inst in applicable if inst.rule_type_code in _GROUPING_CODES]
    for instance in group_instances:
        code = instance.rule_type_code
        rtype = rule_type_by_code.get(code)
        if rtype is None:
            continue
        try:
            if code == "ALL-001":
                new = _evaluate_all001(db, run, instance, rtype, csv_rows, no_finding_count)
            elif code == "MFR-002":
                new = _evaluate_mfr002(db, run, instance, rtype, csv_rows, no_finding_count)
            elif code == "TH-002":
                new = _evaluate_th002(db, run, instance, rtype, csv_rows, no_finding_count)
            elif code == "TH-005":
                new = _evaluate_th005(db, run, instance, rtype, csv_rows, no_finding_count)
            else:
                new = []
            anomalies.extend(new)
        except Exception:
            logger.exception("Error evaluating grouping rule %s", code)
    return anomalies


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_detection(db, run):
    """Two-pass FWA detection over csv_upload_rows for the given run.

    PRECONDITION gate: raises RuntimeError if
        run.resolution_stats["inserted_count"] != run.resolution_stats["expected_count"]

    PASS 1 -- baselines: compute_baseline for each requires_baseline instance.
      MFR-009: no registered baseline kind -- logged and skipped.

    PASS 2 -- evaluate:
      SINGLE-ROW:  MFR-001.
      STATISTICAL: MFR-003, MFR-004, HP-005, HP-008, ALL-006
                   (MFR-004/HP-005/ALL-006 are entity-level; per-row skipped).
      GROUPING:    ALL-001, MFR-002, TH-002, TH-005.

    Eval-log policy:
      finding_raised: written with anomaly_id for every fire.
      error: written for caught exceptions.
      no_finding: NOT written per (row x rule); aggregated into
          run.resolution_stats["no_finding_count"].

    Returns int: count of Anomaly rows created.
    Updates: run.anomaly_count, run.record_count, run.status, run.completed_at.
    """
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

    # PASS 1 -- baselines
    _run_baselines(db, run, applicable, rule_type_by_code)
    db.flush()

    csv_rows = db.execute(
        select(CsvUploadRow).where(
            CsvUploadRow.detection_run_id == run.id,
            CsvUploadRow.tenant_id == run.tenant_id,
        )
    ).scalars().all()
    record_count = len(csv_rows)

    no_finding_count = [0]
    all_anomalies = []

    # PASS 2 -- evaluate
    all_anomalies.extend(
        _evaluate_single_row_rules(
            db, run, applicable, rule_type_by_code, csv_rows, no_finding_count
        )
    )
    all_anomalies.extend(
        _evaluate_statistical_rules(
            db, run, applicable, rule_type_by_code, csv_rows, no_finding_count
        )
    )
    all_anomalies.extend(
        _evaluate_grouping_rules(
            db, run, applicable, rule_type_by_code, csv_rows, no_finding_count
        )
    )
    db.flush()

    # Update run stats.
    run.anomaly_count = len(all_anomalies)
    run.record_count = record_count
    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    new_stats = dict(run.resolution_stats)
    new_stats["no_finding_count"] = no_finding_count[0]
    run.resolution_stats = new_stats
    db.flush()

    return len(all_anomalies)
