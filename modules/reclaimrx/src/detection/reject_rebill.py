"""Reject-75->70 fast-rebill rule evaluator.

LOCKED DECISION: group key = rx_number_hash (same-claim rebill).
Collision behavior: two prescriptions with the same rx_number_hash are treated
  as one group -- acceptable false-positive risk at current dataset volume.
  Documented in finding_details["group_key_collision_risk"].
Split behavior: one prescription generating multiple reject rows is correctly
  grouped under one rx_number_hash.

Buckets:
  le12h:   elapsed hours <= 12  (strongest signal)
  12_24h:  12 < elapsed hours <= 24
  >24h:    excluded (not flagged)

Implementation: ONE set-based SQL self-join -- no per-group loop / N+1.
  Returns all qualifying (reject-75, rebill-70) pairs in a single query.
  Python enforces "first qualifying r70 per r75" via seen_reject_ids set.
  One batched IN-clause ORM fetch for all rebill-row ORM objects.
  Total DB query count = O(1), not O(N groups).

Rule registry: REJECT-75-70 is registered via rule_type_registry.RULE_TYPE_CATALOG
  and register_rule_instances.  No dedicated migration for this rule type.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select as _sel
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.detection.batch_engine import _is_postgres, _json_field, _make_anomaly
from src.models.detection_run_models import (
    Anomaly,
    CsvUploadRow,
    DetectionRuleInstance,
    DetectionRuleType,
    DetectionRun,
)


class _StubInstance:
    """Lightweight stand-in for DetectionRuleInstance when none is provided.

    Avoids touching SQLAlchemy ORM machinery on an un-mapped object.
    """
    def __init__(self) -> None:
        self.id: Any = None
        self.rule_type_code: str = _FINDING_CODE
        self.parameters: dict[str, Any] = {}

_FINDING_CODE = "REJECT-75-70"
_REJECT_CODE_75 = "75"
_REJECT_CODE_70 = "70"


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def evaluate_reject_75_70(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance | None = None,
    rtype: DetectionRuleType | None = None,
) -> list[Anomaly]:
    """Evaluate Reject-75->70 fast-rebill rule via a single set-based self-join.

    Returns a list of Anomaly objects (NOT yet added to the session).
    """
    anomalies: list[Anomaly] = []

    rx_field_75 = _json_field(db, "r75.row_data", "rx_number_hash")
    rx_field_70 = _json_field(db, "r70.row_data", "rx_number_hash")
    rc_field_75 = _json_field(db, "r75.row_data", "reject_code")
    rc_field_70 = _json_field(db, "r70.row_data", "reject_code")
    ts_field_75 = _json_field(db, "r75.row_data", "date_added_timestamp")
    ts_field_70 = _json_field(db, "r70.row_data", "date_added_timestamp")

    params_q: dict[str, Any] = {
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "rc75": _REJECT_CODE_75,
        "rc70": _REJECT_CODE_70,
    }

    sql_pairs = text(f"""
        SELECT
            r75.id            AS reject_row_id,
            r70.id            AS rebill_row_id,
            {rx_field_75}     AS rx_hash,
            {ts_field_75}     AS reject_ts_raw,
            {ts_field_70}     AS rebill_ts_raw
        FROM reclaimrx.csv_upload_rows r75
        JOIN reclaimrx.csv_upload_rows r70
          ON r70.detection_run_id = r75.detection_run_id
         AND r70.tenant_id        = r75.tenant_id
         AND {rx_field_70}        = {rx_field_75}
         AND {rc_field_70}        = :rc70
         AND {ts_field_70}        IS NOT NULL
         AND {ts_field_75}        IS NOT NULL
        WHERE r75.detection_run_id = :run_id
          AND r75.tenant_id        = :tenant_id
          AND {rc_field_75}        = :rc75
          AND {rx_field_75}        IS NOT NULL
        ORDER BY r75.id ASC,
                 {ts_field_70} ASC
    """)

    pair_rows = db.execute(sql_pairs, params_q).fetchall()

    if not pair_rows:
        return anomalies

    rebill_ids = list({r.rebill_row_id for r in pair_rows})
    # Key by str(r.id) for cross-dialect safety:
    # SQLite SAVEPOINT fixture returns uuid.UUID from _UUIDString TypeDecorator,
    # but raw SQL tuple fields (rebill_row_id) are plain strings.
    # str()-normalising both sides makes the dict lookup portable.
    orm_rebill_rows: dict[str, CsvUploadRow] = {
        str(r.id): r
        for r in db.execute(
            _sel(CsvUploadRow).where(CsvUploadRow.id.in_(rebill_ids))
        ).scalars().all()
    }

    if instance is None:
        _inst: Any = _StubInstance()
    else:
        _inst = instance

    seen_reject_ids: set[Any] = set()
    for pr in pair_rows:
        if str(pr.reject_row_id) in seen_reject_ids:
            continue

        reject_ts = _parse_ts(pr.reject_ts_raw)
        rebill_ts = _parse_ts(pr.rebill_ts_raw)

        if reject_ts is None or rebill_ts is None or rebill_ts <= reject_ts:
            continue

        elapsed_h = (rebill_ts - reject_ts).total_seconds() / 3600.0
        if elapsed_h > 24.0:
            continue

        bucket = "le12h" if elapsed_h <= 12.0 else "12_24h"

        orm_row = orm_rebill_rows.get(str(pr.rebill_row_id))
        if orm_row is None:
            continue

        anomaly = _make_anomaly(
            run=run,
            instance=_inst,
            csv_row=orm_row,
            finding_code=_FINDING_CODE,
            finding_summary=(
                f"Reject 75->70 fast-rebill: rx_number_hash={pr.rx_hash}, "
                f"elapsed={elapsed_h:.1f}h, bucket={bucket}"
            ),
            finding_details={
                "rx_number_hash": pr.rx_hash,
                "reject_row_id": str(pr.reject_row_id),
                "rebill_row_id": str(pr.rebill_row_id),
                "reject_ts": reject_ts.isoformat(),
                "rebill_ts": rebill_ts.isoformat(),
                "elapsed_hours": str(round(elapsed_h, 2)),
                "bucket": bucket,
                "group_key_collision_risk": (
                    "rx_number_hash collision possible for distinct Rx at same pharmacy"
                ),
            },
            severity="high",
            confidence_num=Decimal("0.80"),
        )
        anomalies.append(anomaly)
        seen_reject_ids.add(str(pr.reject_row_id))

    return anomalies
