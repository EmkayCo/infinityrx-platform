"""Population-separated baseline computation for CSV-based FWA detection.

Task 3.3 - Baseline cache population.

compute_baseline(db, run, *, kind, window_days=90, min_sample_count=5) -> int

Supported kinds (aggregate-subtraction, no O(n^2) subqueries -- MED-003):
  prescriber_peer_volume  (HP-005) - peer-exclusion, leave-one-prescriber-out
  pharmacy_ndc_volume     (MFR-004) - peer-exclusion, leave-one-pharmacy-out
  member_cost             (HP-008) - population mean/stddev (see note)
  pharmacy_weekday_volume (ALL-006) - per pharmacy weekday claim fraction
  pharmacy_own_rate_history (MFR-003) - own IC/WAC rate (NOT peer comparison)

Aggregate-subtraction pattern (MED-003):
  For peer-exclusion on ENTITY-LEVEL values (HP-005, MFR-004):
    measured_value = claim count per entity
    SQL: GROUP BY (group_key, entity_id) -> entity_n per entity
    Python: per group:
      group_entity_count = number of entities
      group_sum          = SUM(entity_n)      (total rows in group)
      group_sumsq        = SUM(entity_n^2)
    Per entity leave-one-out:
      peer_entity_count = group_entity_count - 1
      peer_sum          = group_sum - entity_n
      peer_mean         = peer_sum / peer_entity_count
      peer_var          = (group_sumsq - entity_n^2) / peer_entity_count
                          - peer_mean^2   (guarded >= 0)
      peer_std          = sqrt(peer_var)
    Peer sample_count reported as peer_entity_count (number of peer entities).

Dialect portability:
  _json_field / _is_weekend_expr select SQLite vs Postgres SQL fragments.

Financial precision:
  SQL CAST(... AS REAL) inside aggregates only.  Python wraps results in
  Decimal(str(...)) before writing to Numeric(20, 8) DB columns.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.detection_run_models import BaselineCache, CsvUploadRow, DetectionRun  # noqa: F401

_DATA_SOURCE = "csv_upload"
_ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# Dialect helpers
# ---------------------------------------------------------------------------


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _json_field(db: Session, column: str, field: str) -> str:
    if _is_postgres(db):
        return f"{column}->>'{field}'"
    return f"json_extract({column}, '$.{field}')"


def _is_weekend_expr(db: Session, date_col: str) -> str:
    if _is_postgres(db):
        return f"EXTRACT(DOW FROM CAST({date_col} AS DATE)) IN (0, 6)"
    # SQLite strftime: 0=Sunday, 6=Saturday
    return f"strftime('%w', {date_col}) IN ('0', '6')"


# ---------------------------------------------------------------------------
# Group totals helper
# ---------------------------------------------------------------------------


def _group_totals_from_entities(
    entity_rows: list,
    group_key_attr: str,
    entity_count_attr: str,
) -> dict[str, tuple[int, Decimal, Decimal]]:
    """Accumulate entity-level (group_key, entity_n) into group totals.

    Returns: {group_key: (group_entity_count, group_sum, group_sumsq)}
      group_entity_count = number of distinct entities in this group
      group_sum          = SUM(entity_n)    -- total rows in group
      group_sumsq        = SUM(entity_n^2)  -- sum of squares of entity counts

    This is O(entities).  No correlated subqueries.
    """
    totals: dict[str, list] = {}
    for e in entity_rows:
        gk = getattr(e, group_key_attr)
        en = int(getattr(e, entity_count_attr))
        en_d = Decimal(str(en))
        if gk not in totals:
            totals[gk] = [0, _ZERO, _ZERO]
        totals[gk][0] += 1             # group_entity_count
        totals[gk][1] += en_d          # group_sum (SUM of entity_n)
        totals[gk][2] += en_d * en_d   # group_sumsq = SUM(entity_n^2)
    return {k: (v[0], v[1], v[2]) for k, v in totals.items()}


# ---------------------------------------------------------------------------
# Aggregate-subtraction leave-one-entity-out
# ---------------------------------------------------------------------------


def _peer_stats_entity(
    group_entity_count: int,
    group_sum: Decimal,
    group_sumsq: Decimal,
    entity_n: int,
) -> tuple[int, Decimal | None, Decimal | None]:
    """Leave-one-entity-out (peer_entity_count, peer_mean, peer_std).

    peer_entity_count = group_entity_count - 1
    peer_sum          = group_sum - entity_n
    peer_mean         = peer_sum / peer_entity_count
    peer_var          = (group_sumsq - entity_n^2) / peer_entity_count
                        - peer_mean^2   (guarded >= 0)
    peer_std          = sqrt(peer_var)

    sample_count stored in the cache row = peer_entity_count (number of peer
    prescribers/pharmacies, not peer rows), so downstream rules can apply
    "number of comparators" logic.
    """
    peer_entity_count = group_entity_count - 1
    if peer_entity_count <= 0:
        return peer_entity_count, None, None

    en_d = Decimal(str(entity_n))
    peer_sum = group_sum - en_d
    peer_mean = peer_sum / Decimal(str(peer_entity_count))

    peer_sumsq_diff = group_sumsq - en_d * en_d
    peer_var = peer_sumsq_diff / Decimal(str(peer_entity_count)) - peer_mean * peer_mean
    if peer_var < _ZERO:
        peer_var = _ZERO
    peer_std = Decimal(str(math.sqrt(float(peer_var))))
    return peer_entity_count, peer_mean, peer_std


# ---------------------------------------------------------------------------
# DB write helpers
# ---------------------------------------------------------------------------


def _write_row(
    db: Session,
    run: DetectionRun,
    *,
    baseline_kind: str,
    scope_key: str,
    window_days: int,
    mean: Decimal | None,
    stddev: Decimal | None,
    sample_count: int,
    extra: dict[str, Any],
) -> BaselineCache:
    row = BaselineCache(
        tenant_id=run.tenant_id,
        baseline_kind=baseline_kind,
        scope_key=scope_key,
        window_days=window_days,
        data_source=_DATA_SOURCE,
        mean=mean,
        stddev=stddev,
        sample_count=sample_count,
        extra=extra,
        computed_at=datetime.now(UTC),
        ttl_seconds=86400,
    )
    db.add(row)
    db.flush()
    return row


def _base_extra(
    *,
    exclusion: str,
    peer_count: int | None,
    window_days: int,
    min_sample_count: int,
    included_current_run: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "exclusion": exclusion,
        "window_days": window_days,
        "data_source": _DATA_SOURCE,
        "min_sample_count": min_sample_count,
        "included_current_run": included_current_run,
    }
    if peer_count is not None:
        d["peer_count"] = peer_count
    d.update(kwargs)
    return d


# ---------------------------------------------------------------------------
# prescriber_peer_volume  (HP-005)
# ---------------------------------------------------------------------------


def _compute_prescriber_peer_volume(
    db: Session, run: DetectionRun, *, window_days: int, min_sample_count: int
) -> int:
    """Per (ndc), leave-one-prescriber-out peer mean claim count.

    Entity value = claim count for (ndc, prescriber) pair.
    min_sample_count compares against peer_entity_count (number of peer
    prescribers), not peer row count.
    """
    presc_field = _json_field(db, "r.row_data", "prescriber_npi")
    params = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}

    sql_entity = text(f"""
        SELECT
            r.resolved_ndc AS ndc,
            {presc_field}  AS prescriber_npi,
            COUNT(*)       AS entity_n
        FROM csv_upload_rows r
        WHERE r.detection_run_id = :run_id
          AND r.tenant_id = :tenant_id
          AND r.resolved_ndc IS NOT NULL
          AND {presc_field} IS NOT NULL
          AND {presc_field} != ''
        GROUP BY r.resolved_ndc, {presc_field}
    """)

    entity_rows = db.execute(sql_entity, params).fetchall()
    groups = _group_totals_from_entities(entity_rows, "ndc", "entity_n")

    written = 0
    for e in entity_rows:
        ndc, presc = e.ndc, e.prescriber_npi
        if ndc not in groups:
            continue
        en = int(e.entity_n)
        gec, gs, gss = groups[ndc]
        peer_ec, peer_mean, peer_std = _peer_stats_entity(gec, gs, gss, en)
        if peer_ec < min_sample_count:
            continue
        _write_row(
            db, run,
            baseline_kind="prescriber_peer_volume",
            scope_key=f"ndc={ndc}|prescriber_npi={presc}",
            window_days=window_days,
            mean=peer_mean,
            stddev=peer_std,
            sample_count=peer_ec,
            extra=_base_extra(
                exclusion="leave_entity_out",
                peer_count=peer_ec,
                window_days=window_days,
                min_sample_count=min_sample_count,
            ),
        )
        written += 1
    return written


# ---------------------------------------------------------------------------
# pharmacy_ndc_volume  (MFR-004)
# ---------------------------------------------------------------------------


def _compute_pharmacy_ndc_volume(
    db: Session, run: DetectionRun, *, window_days: int, min_sample_count: int
) -> int:
    """Per (ndc), leave-one-pharmacy-out peer mean claim count.

    Same pattern as prescriber_peer_volume.  min_sample_count vs peer pharmacy
    count (entities), not peer row count.
    """
    params = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}

    sql_entity = text("""
        SELECT
            r.resolved_ndc          AS ndc,
            r.resolved_pharmacy_npi AS pharmacy_npi,
            COUNT(*)                AS entity_n
        FROM csv_upload_rows r
        WHERE r.detection_run_id = :run_id
          AND r.tenant_id = :tenant_id
          AND r.resolved_ndc IS NOT NULL
          AND r.resolved_pharmacy_npi IS NOT NULL
        GROUP BY r.resolved_ndc, r.resolved_pharmacy_npi
    """)

    entity_rows = db.execute(sql_entity, params).fetchall()
    groups = _group_totals_from_entities(entity_rows, "ndc", "entity_n")

    written = 0
    for e in entity_rows:
        ndc, npi = e.ndc, e.pharmacy_npi
        if ndc not in groups:
            continue
        en = int(e.entity_n)
        gec, gs, gss = groups[ndc]
        peer_ec, peer_mean, peer_std = _peer_stats_entity(gec, gs, gss, en)
        if peer_ec < min_sample_count:
            continue
        _write_row(
            db, run,
            baseline_kind="pharmacy_ndc_volume",
            scope_key=f"ndc={ndc}|pharmacy_npi={npi}",
            window_days=window_days,
            mean=peer_mean,
            stddev=peer_std,
            sample_count=peer_ec,
            extra=_base_extra(
                exclusion="leave_entity_out",
                peer_count=peer_ec,
                window_days=window_days,
                min_sample_count=min_sample_count,
            ),
        )
        written += 1
    return written


# ---------------------------------------------------------------------------
# member_cost  (HP-008)
# ---------------------------------------------------------------------------


def _compute_member_cost(
    db: Session, run: DetectionRun, *, window_days: int, min_sample_count: int
) -> int:
    """Population mean/stddev of total_paid_amt across the run.

    Peer-exclusion deliberately NOT applied: with large member N the population
    mean is more stable than any leave-one-out estimate.  Downstream rule uses
    z-score against this baseline.  One row per run (scope_key='run').
    """
    total_paid_field = _json_field(db, "r.row_data", "total_paid_amt")
    params = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}

    sql = text(f"""
        SELECT
            COUNT(*) AS n,
            SUM(CAST({total_paid_field} AS REAL)) AS s,
            SUM(
                CAST({total_paid_field} AS REAL) *
                CAST({total_paid_field} AS REAL)
            ) AS ss
        FROM csv_upload_rows r
        WHERE r.detection_run_id = :run_id
          AND r.tenant_id = :tenant_id
          AND {total_paid_field} IS NOT NULL
          AND {total_paid_field} != ''
    """)

    row = db.execute(sql, params).fetchone()
    if row is None or row.n is None or int(row.n) < min_sample_count:
        return 0

    n = int(row.n)
    s = Decimal(str(row.s))
    ss = Decimal(str(row.ss))
    mean = s / Decimal(str(n))
    var = ss / Decimal(str(n)) - mean * mean
    if var < _ZERO:
        var = _ZERO
    stddev = Decimal(str(math.sqrt(float(var))))

    _write_row(
        db, run,
        baseline_kind="member_cost",
        scope_key="run",
        window_days=window_days,
        mean=mean,
        stddev=stddev,
        sample_count=n,
        extra=_base_extra(
            exclusion="population",
            peer_count=None,
            window_days=window_days,
            min_sample_count=min_sample_count,
            note=(
                "Peer-exclusion not applied: large member N. "
                "Use stddev for z-score comparison per HP-008."
            ),
        ),
    )
    return 1


# ---------------------------------------------------------------------------
# pharmacy_weekday_volume  (ALL-006)
# ---------------------------------------------------------------------------


def _compute_pharmacy_weekday_volume(
    db: Session, run: DetectionRun, *, window_days: int, min_sample_count: int
) -> int:
    """Per pharmacy, fraction of claims on weekdays (Mon-Fri).

    mean = weekday_count / total_count  (Decimal in [0, 1]).
    scope_key: f"pharmacy_npi={npi}".
    min_sample_count compared to total claim count for this pharmacy.
    """
    dos_field = _json_field(db, "r.row_data", "date_of_service")
    weekend_expr = _is_weekend_expr(db, dos_field)
    params = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}

    sql = text(f"""
        SELECT
            r.resolved_pharmacy_npi AS pharmacy_npi,
            COUNT(*) AS total_count,
            SUM(CASE WHEN {weekend_expr} THEN 1 ELSE 0 END) AS weekend_count
        FROM csv_upload_rows r
        WHERE r.detection_run_id = :run_id
          AND r.tenant_id = :tenant_id
          AND r.resolved_pharmacy_npi IS NOT NULL
          AND {dos_field} IS NOT NULL
          AND {dos_field} != ''
        GROUP BY r.resolved_pharmacy_npi
    """)

    rows = db.execute(sql, params).fetchall()
    written = 0
    for r in rows:
        total = int(r.total_count)
        if total < min_sample_count:
            continue
        weekend = int(r.weekend_count) if r.weekend_count is not None else 0
        weekday = total - weekend
        weekday_rate = Decimal(str(weekday)) / Decimal(str(total))
        _write_row(
            db, run,
            baseline_kind="pharmacy_weekday_volume",
            scope_key=f"pharmacy_npi={r.pharmacy_npi}",
            window_days=window_days,
            mean=weekday_rate,
            stddev=None,
            sample_count=total,
            extra=_base_extra(
                exclusion="leave_entity_out",
                peer_count=total,
                window_days=window_days,
                min_sample_count=min_sample_count,
                weekday_count=weekday,
                weekend_count=weekend,
                total_count=total,
            ),
        )
        written += 1
    return written


# ---------------------------------------------------------------------------
# pharmacy_own_rate_history  (MFR-003)
# ---------------------------------------------------------------------------


def _compute_pharmacy_own_rate_history(
    db: Session, run: DetectionRun, *, window_days: int, min_sample_count: int
) -> int:
    """Per (pharmacy_npi, ndc), the pharmacy's own historical IC/WAC rate.

    mean   = AVG(ingredient_cost_paid / extended_wac) across own rows.
    stddev = population stddev of per-row ratios.
    scope_key: f"ndc={ndc}|pharmacy_npi={npi}".
    exclusion='own_prior_period' -- NOT peer comparison.
    Rows with extended_wac = 0 excluded.
    min_sample_count compared to row count for this (pharmacy, ndc) pair.
    """
    ic_field = _json_field(db, "r.row_data", "ingredient_cost_paid")
    wac_field = _json_field(db, "r.row_data", "extended_wac")
    params = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}

    sql = text(f"""
        SELECT
            r.resolved_pharmacy_npi AS pharmacy_npi,
            r.resolved_ndc          AS ndc,
            COUNT(*) AS n,
            SUM(
                CAST({ic_field} AS REAL) / CAST({wac_field} AS REAL)
            ) AS sum_ratio,
            SUM(
                (CAST({ic_field} AS REAL) / CAST({wac_field} AS REAL)) *
                (CAST({ic_field} AS REAL) / CAST({wac_field} AS REAL))
            ) AS sum_ratio_sq
        FROM csv_upload_rows r
        WHERE r.detection_run_id = :run_id
          AND r.tenant_id = :tenant_id
          AND r.resolved_pharmacy_npi IS NOT NULL
          AND r.resolved_ndc IS NOT NULL
          AND {ic_field} IS NOT NULL
          AND {ic_field} != ''
          AND {wac_field} IS NOT NULL
          AND {wac_field} != ''
          AND CAST({wac_field} AS REAL) != 0
        GROUP BY r.resolved_pharmacy_npi, r.resolved_ndc
    """)

    rows = db.execute(sql, params).fetchall()
    written = 0
    for r in rows:
        n = int(r.n)
        if n < min_sample_count:
            continue
        s = Decimal(str(r.sum_ratio))
        ss = Decimal(str(r.sum_ratio_sq))
        mean = s / Decimal(str(n))
        var = ss / Decimal(str(n)) - mean * mean
        if var < _ZERO:
            var = _ZERO
        stddev = Decimal(str(math.sqrt(float(var))))
        _write_row(
            db, run,
            baseline_kind="pharmacy_own_rate_history",
            scope_key=f"ndc={r.ndc}|pharmacy_npi={r.pharmacy_npi}",
            window_days=window_days,
            mean=mean,
            stddev=stddev,
            sample_count=n,
            extra=_base_extra(
                exclusion="own_prior_period",
                peer_count=None,
                window_days=window_days,
                min_sample_count=min_sample_count,
                rate_metric="ingredient_cost_paid / extended_wac",
            ),
        )
        written += 1
    return written


# ---------------------------------------------------------------------------
# Dispatch table and public API
# ---------------------------------------------------------------------------


_HANDLERS = {
    "prescriber_peer_volume": _compute_prescriber_peer_volume,
    "pharmacy_ndc_volume": _compute_pharmacy_ndc_volume,
    "member_cost": _compute_member_cost,
    "pharmacy_weekday_volume": _compute_pharmacy_weekday_volume,
    "pharmacy_own_rate_history": _compute_pharmacy_own_rate_history,
}


def compute_baseline(
    db: Session,
    run: DetectionRun,
    *,
    kind: str,
    window_days: int = 90,
    min_sample_count: int = 5,
) -> int:
    """Compute baseline statistics for the given kind and persist to baseline_cache.

    Parameters
    ----------
    db               : Synchronous SQLAlchemy Session.
    run              : DetectionRun whose CsvUploadRow records supply the data.
    kind             : Baseline kind string (one of the supported kinds).
    window_days      : Lookback window label stored on each cache row.
    min_sample_count : Minimum peer entity count (HP-005, MFR-004) or row count
                       (MFR-003, ALL-006) required to write a row.

    Returns
    -------
    int -- number of BaselineCache rows written.

    Raises
    ------
    ValueError for unknown kind.
    """
    handler = _HANDLERS.get(kind)
    if handler is None:
        supported = ", ".join(sorted(_HANDLERS))
        raise ValueError(
            f"unknown baseline kind {kind!r}. Supported: {supported}"
        )
    return handler(db, run, window_days=window_days, min_sample_count=min_sample_count)
