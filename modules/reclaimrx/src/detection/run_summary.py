"""Detection-run summary report (Task 4.1).

build_summary(db, run) -> dict
    Read-only aggregation for a DetectionRun.  Returns a structured dict
    covering row counts, rule applicability, anomaly breakdowns, top entities,
    and total dollars at risk.

    dollars_at_risk uses anomalies.amount_paid as the program-exposure field
    (what was actually paid out, not merely billed), matching the "program
    exposure" definition from the PRD.  SA aggregate sums are wrapped in
    Decimal(str(...)) per the financial-precision invariant.

format_summary(summary) -> str
    CLI-friendly multi-line rendering of the summary dict.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.detection_run_models import (
    Anomaly,
    DetectionRuleEvaluationLog,
    DetectionRuleInstance,
    DetectionRuleType,
    DetectionRun,
)

_ZERO = Decimal("0")
_DEFAULT_TOP_N = 10


def _count_anomalies_for_run(db: Session, run: DetectionRun) -> int:
    result = db.execute(
        select(func.count()).select_from(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.tenant_id == run.tenant_id,
        )
    ).scalar()
    return int(result) if result is not None else 0


def _by_finding_code(db: Session, run: DetectionRun) -> dict[str, int]:
    rows = db.execute(
        select(Anomaly.finding_code, func.count().label("cnt"))
        .where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.tenant_id == run.tenant_id,
        )
        .group_by(Anomaly.finding_code)
    ).all()
    return {code: int(cnt) for code, cnt in rows}


def _by_severity(db: Session, run: DetectionRun) -> dict[str, int]:
    rows = db.execute(
        select(Anomaly.severity, func.count().label("cnt"))
        .where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.tenant_id == run.tenant_id,
        )
        .group_by(Anomaly.severity)
    ).all()
    return {sev: int(cnt) for sev, cnt in rows}


def _by_family(db: Session, run: DetectionRun) -> dict[str, int]:
    """Group anomalies by detection_rule_types.family via join through rule instances.

    Anomaly.detection_id == DetectionRuleInstance.id (when detection_kind == 'rule').
    DetectionRuleInstance.rule_type_code -> DetectionRuleType.code -> .family.
    """
    rows = db.execute(
        select(DetectionRuleType.family, func.count().label("cnt"))
        .select_from(Anomaly)
        .join(
            DetectionRuleInstance,
            Anomaly.detection_id == DetectionRuleInstance.id,
        )
        .join(
            DetectionRuleType,
            DetectionRuleInstance.rule_type_code == DetectionRuleType.code,
        )
        .where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.tenant_id == run.tenant_id,
            Anomaly.detection_kind == "rule",
            Anomaly.detection_id.isnot(None),
        )
        .group_by(DetectionRuleType.family)
    ).all()
    return {family: int(cnt) for family, cnt in rows}


def _dollars_at_risk(db: Session, run: DetectionRun) -> Decimal:
    """Sum of anomalies.amount_paid (program exposure).

    SA returns float for func.sum() aggregates.  Wrap in Decimal(str(...))
    per the financial-precision invariant.  Returns Decimal("0") when there
    are no anomalies or all amount_paid values are NULL.
    """
    result = db.execute(
        select(func.sum(Anomaly.amount_paid)).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.tenant_id == run.tenant_id,
            Anomaly.amount_paid.isnot(None),
        )
    ).scalar()
    if result is None:
        return _ZERO
    return Decimal(str(result))


def _top_pharmacies(db: Session, run: DetectionRun, top_n: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Anomaly.pharmacy_npi, func.count().label("cnt"))
        .where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.tenant_id == run.tenant_id,
            Anomaly.pharmacy_npi.isnot(None),
        )
        .group_by(Anomaly.pharmacy_npi)
        .order_by(func.count().desc())
        .limit(top_n)
    ).all()
    return [{"pharmacy_npi": npi, "anomaly_count": int(cnt)} for npi, cnt in rows]


def _top_prescribers(db: Session, run: DetectionRun, top_n: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Anomaly.prescriber_npi, func.count().label("cnt"))
        .where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.tenant_id == run.tenant_id,
            Anomaly.prescriber_npi.isnot(None),
        )
        .group_by(Anomaly.prescriber_npi)
        .order_by(func.count().desc())
        .limit(top_n)
    ).all()
    return [{"prescriber_npi": npi, "anomaly_count": int(cnt)} for npi, cnt in rows]


def _rule_counts(db: Session, run: DetectionRun) -> dict[str, int]:
    """Count eval-log rows by applicability for this run.

    applied  = rows where evaluation_result != 'skipped_inapplicable'
    skipped  = rows where evaluation_result == 'skipped_inapplicable'
    """
    rows = db.execute(
        select(
            DetectionRuleEvaluationLog.evaluation_result,
            func.count().label("cnt"),
        )
        .where(DetectionRuleEvaluationLog.detection_run_id == run.id)
        .group_by(DetectionRuleEvaluationLog.evaluation_result)
    ).all()
    skipped = 0
    applied = 0
    for result, cnt in rows:
        if result == "skipped_inapplicable":
            skipped += int(cnt)
        else:
            applied += int(cnt)
    return {"applied": applied, "skipped": skipped}


def build_summary(db: Session, run: DetectionRun, top_n: int = _DEFAULT_TOP_N) -> dict[str, Any]:
    """Aggregate a read-only summary for a DetectionRun.

    Parameters
    ----------
    db:
        SQLAlchemy Session (read-only queries only; no mutations).
    run:
        The DetectionRun ORM object to summarise.
    top_n:
        How many top pharmacies / prescribers to include (default 10).

    dollars_at_risk uses anomalies.amount_paid (program exposure -- what was
    paid out, not merely billed).  SA func.sum() returns float; wrapped in
    Decimal(str(...)) per the financial-precision invariant.
    """
    stats: dict[str, Any] = run.resolution_stats or {}

    total = _count_anomalies_for_run(db, run)
    rule_stats = _rule_counts(db, run)

    return {
        "rows": {
            "expected_count": stats.get("expected_count"),
            "inserted_count": stats.get("inserted_count"),
            "declared": stats.get("declared"),
            "unmapped": stats.get("unmapped"),
        },
        "rules": {
            "applied": rule_stats["applied"],
            "skipped": rule_stats["skipped"],
        },
        "anomalies": {
            "total": total,
            "by_finding_code": _by_finding_code(db, run),
            "by_family": _by_family(db, run),
            "by_severity": _by_severity(db, run),
        },
        "top_entities": {
            "pharmacies": _top_pharmacies(db, run, top_n),
            "prescribers": _top_prescribers(db, run, top_n),
        },
        "dollars_at_risk": _dollars_at_risk(db, run),
        "run_meta": {
            "run_label": run.run_label,
            "status": run.status,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "source_sha256": run.source_sha256,
        },
    }


def format_summary(summary: dict[str, Any]) -> str:
    """Render a build_summary dict as a human-readable multi-line string."""
    meta = summary.get("run_meta", {})
    rows = summary.get("rows", {})
    rules = summary.get("rules", {})
    anomalies = summary.get("anomalies", {})
    top = summary.get("top_entities", {})
    dollars = summary.get("dollars_at_risk", _ZERO)

    lines: list[str] = [
        "=" * 60,
        f"Detection Run: {meta.get('run_label', 'unknown')}",
        f"  Status      : {meta.get('status', '')}",
        f"  Started     : {meta.get('started_at', '')}",
        f"  Completed   : {meta.get('completed_at', '')}",
        f"  Source SHA  : {meta.get('source_sha256', '')}",
        "-" * 60,
        "Row Counts",
        f"  Expected    : {rows.get('expected_count')}",
        f"  Inserted    : {rows.get('inserted_count')}",
        f"  Declared    : {rows.get('declared')}",
        f"  Unmapped    : {rows.get('unmapped')}",
        "-" * 60,
        "Rules",
        f"  Applied     : {rules.get('applied', 0)}",
        f"  Skipped     : {rules.get('skipped', 0)}",
        "-" * 60,
        f"Anomalies (total: {anomalies.get('total', 0)})",
    ]

    by_code = anomalies.get("by_finding_code", {})
    if by_code:
        lines.append("  By finding code:")
        for code, cnt in sorted(by_code.items()):
            lines.append(f"    {code:<20} {cnt:>6}")
    else:
        lines.append("  By finding code: (none)")

    by_fam = anomalies.get("by_family", {})
    if by_fam:
        lines.append("  By family:")
        for fam, cnt in sorted(by_fam.items()):
            lines.append(f"    {fam:<20} {cnt:>6}")

    by_sev = anomalies.get("by_severity", {})
    if by_sev:
        lines.append("  By severity:")
        for sev, cnt in sorted(by_sev.items()):
            lines.append(f"    {sev:<20} {cnt:>6}")

    lines.append("-" * 60)
    lines.append(f"Dollars at Risk (amount_paid): ${dollars:,.2f}")

    pharmacies = top.get("pharmacies", [])
    if pharmacies:
        lines.append("-" * 60)
        lines.append("Top Pharmacies (by anomaly count):")
        for entry in pharmacies:
            lines.append(f"  NPI {entry['pharmacy_npi']:<12}  {entry['anomaly_count']:>5} anomalies")

    prescribers = top.get("prescribers", [])
    if prescribers:
        lines.append("-" * 60)
        lines.append("Top Prescribers (by anomaly count):")
        for entry in prescribers:
            lines.append(f"  NPI {entry['prescriber_npi']:<12}  {entry['anomaly_count']:>5} anomalies")

    lines.append("=" * 60)
    return "\n".join(lines)