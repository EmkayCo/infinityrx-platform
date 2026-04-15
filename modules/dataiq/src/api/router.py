"""DataIQ API router — all endpoints under /api/v1/dataiq/."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.session import get_session

from src.api.dependencies import TenantId
from src.api.schemas.metrics import (
    AnomalyResponse,
    BenchmarkCreateRequest,
    BenchmarkResponse,
    DataQualityScoreResponse,
    DecompositionResponse,
    InsightAlertResponse,
    InsightSummaryResponse,
    MetricDefinitionResponse,
    MetricHistoryResponse,
    MetricSnapshotResponse,
    NetworkAdequacyResponse,
    TopDrugResponse,
)
from src.models.tables import (
    Benchmark,
    DataQualityScore,
    InsightAlert,
    KpiRollup,
    MetricDefinition,
    MetricSnapshot,
    SPCAlert,
    TrendDecomposition,
)
from src.services.spc import calculate_control_limits, check_western_electric_rules
from src.services.geo_analytics import (
    MemberLocation,
    NetworkAdequacyResult,
    PharmacyLocation,
    calculate_network_adequacy,
)

log = logging.getLogger("dataiq.router")

router = APIRouter(prefix="/api/v1/dataiq", tags=["dataiq"])

_CORRELATION_ID_KEY = "svc_correlation_id"
_TENANT_ID_KEY = "svc_tenant_id"


def _corr() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_redis() -> Any:
    """Return an async Redis client from shared settings.

    Raises RedisConnectionError if the URL is not configured.
    """
    import redis.asyncio as redis_async  # noqa: PLC0415 — deferred import

    settings = get_settings()
    return redis_async.from_url(settings.REDIS_URL)


# ---------------------------------------------------------------------------
# Real-Time Metrics
# ---------------------------------------------------------------------------


@router.get("/metrics", response_model=list[MetricDefinitionResponse])
async def list_metrics(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List all metric definitions."""
    result = await db.execute(
        sa.select(MetricDefinition).order_by(MetricDefinition.metric_key)
    )
    rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "metric_key": row.metric_key,
            "name": row.name,
            "description": row.description,
            "category": row.category,
            "calculation_type": row.calculation_type,
            "spc_enabled": row.spc_enabled,
            "spc_window_days": row.spc_window_days,
            "spc_sigma_threshold": Decimal(str(row.spc_sigma_threshold)),
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/metrics/{metric_key}/current")
async def get_current_metric(
    metric_key: str,
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get current real-time value of a metric (from Redis, fallback to DB)."""
    correlation_id = _corr()

    # Attempt Redis read
    cached_value: str | None = None
    try:
        redis = await _get_redis()
        try:
            # Check most recent minute bucket key pattern
            now_ts = int(datetime.now(UTC).timestamp() // 60) * 60
            redis_key = f"tenant:{tenant_id}:kpi:{metric_key}:minute:{now_ts}"
            cached_value = await redis.get(redis_key)
        finally:
            await redis.aclose()
    except (RedisConnectionError, RedisError, OSError):
        log.warning(
            "Redis unavailable — falling back to DB for metric",
            extra={
                "svc_name": "dataiq",
                _CORRELATION_ID_KEY: correlation_id,
                _TENANT_ID_KEY: str(tenant_id),
            },
        )

    if cached_value is not None:
        return {
            "metric_key": metric_key,
            "tenant_id": str(tenant_id),
            "value": Decimal(str(cached_value)),
            "as_of": datetime.now(UTC).isoformat(),
            "source": "redis",
        }

    # Fallback: most recent KpiRollup row for this tenant+metric
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == metric_key,
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    value = Decimal(str(row.value)) if row is not None else None
    as_of = datetime.now(UTC).isoformat()

    return {
        "metric_key": metric_key,
        "tenant_id": str(tenant_id),
        "value": value,
        "as_of": as_of,
        "source": "db",
    }


@router.get("/metrics/{metric_key}/history", response_model=MetricHistoryResponse)
async def get_metric_history(
    metric_key: str,
    tenant_id: TenantId,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get historical metric values with SPC control bands."""
    result = await db.execute(
        sa.select(MetricSnapshot)
        .join(
            MetricDefinition,
            MetricSnapshot.metric_definition_id == MetricDefinition.id,
        )
        .where(
            MetricSnapshot.tenant_id == tenant_id,
            MetricDefinition.metric_key == metric_key,
            MetricSnapshot.snapshot_date >= start_date,
            MetricSnapshot.snapshot_date <= end_date,
        )
        .order_by(MetricSnapshot.snapshot_date.asc())
    )
    snapshots = result.scalars().all()

    snapshot_dicts = [
        {
            "id": s.id,
            "metric_key": metric_key,
            "snapshot_date": s.snapshot_date,
            "snapshot_hour": s.snapshot_hour,
            "value": Decimal(str(s.value)),
            "moving_average": Decimal(str(s.moving_average)) if s.moving_average is not None else None,
            "upper_control_limit": Decimal(str(s.upper_control_limit)) if s.upper_control_limit is not None else None,
            "lower_control_limit": Decimal(str(s.lower_control_limit)) if s.lower_control_limit is not None else None,
            "is_anomalous": s.is_anomalous,
        }
        for s in snapshots
    ]

    mean: Decimal | None = None
    ucl: Decimal | None = None
    lcl: Decimal | None = None

    if len(snapshots) >= 2:
        values = [Decimal(str(s.value)) for s in snapshots]
        sigma = Decimal("3")
        try:
            spc = calculate_control_limits(values, sigma_multiplier=sigma)
            mean = spc.mean
            ucl = spc.ucl
            lcl = spc.lcl
        except ValueError:
            pass

    return {
        "metric_key": metric_key,
        "snapshots": snapshot_dicts,
        "mean": mean,
        "ucl": ucl,
        "lcl": lcl,
    }


@router.get("/metrics/{metric_key}/anomalies", response_model=list[AnomalyResponse])
async def get_metric_anomalies(
    metric_key: str,
    tenant_id: TenantId,
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Get anomaly history for a metric (SPC alerts from DB)."""
    filters = [
        SPCAlert.tenant_id == tenant_id,
        SPCAlert.metric_key == metric_key,
    ]
    if start_date is not None:
        filters.append(sa.cast(SPCAlert.created_at, sa.Date) >= start_date)
    if end_date is not None:
        filters.append(sa.cast(SPCAlert.created_at, sa.Date) <= end_date)

    result = await db.execute(
        sa.select(SPCAlert)
        .where(*filters)
        .order_by(SPCAlert.created_at.desc())
        .limit(500)
    )
    alerts = result.scalars().all()

    return [
        {
            "metric_key": a.metric_key,
            "snapshot_date": a.created_at.date(),
            "value": Decimal(str(a.value)),
            "ucl": Decimal(str(a.ucl)),
            "lcl": Decimal(str(a.lcl)),
            "rule_violations": [a.description] if a.description else [],
        }
        for a in alerts
    ]


# ---------------------------------------------------------------------------
# Drug Trend Analytics
# ---------------------------------------------------------------------------


@router.get("/drug-trend/decomposition", response_model=list[DecompositionResponse])
async def get_drug_trend_decomposition(
    tenant_id: TenantId,
    start_period: date = Query(...),
    end_period: date = Query(...),
    drug_class: str | None = Query(default=None),
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Get spend change decomposition: utilization + price + mix effects."""
    period_pair = f"{start_period}/{end_period}"
    filters = [
        TrendDecomposition.tenant_id == tenant_id,
        TrendDecomposition.period_pair == period_pair,
    ]
    if drug_class is not None:
        filters.append(TrendDecomposition.drug_class == drug_class)

    result = await db.execute(
        sa.select(TrendDecomposition)
        .where(*filters)
        .order_by(TrendDecomposition.drug_class)
    )
    rows = result.scalars().all()

    return [
        {
            "period_pair": r.period_pair,
            "drug_class": r.drug_class,
            "utilization_effect": Decimal(str(r.utilization_effect)),
            "price_effect": Decimal(str(r.price_effect)),
            "mix_effect": Decimal(str(r.mix_effect)),
            "total_delta": Decimal(str(r.total_delta)),
            "old_spend": Decimal(str(r.old_spend)),
            "new_spend": Decimal(str(r.new_spend)),
        }
        for r in rows
    ]


@router.get("/drug-trend/top-drugs", response_model=list[TopDrugResponse])
async def get_top_drugs(
    tenant_id: TenantId,
    start_date: date = Query(...),
    end_date: date = Query(...),
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(default="spend"),
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Get top drugs by spend or volume from KPI rollup data."""
    # Aggregate KpiRollup by metric_key pattern matching drug NDC spend metrics
    metric_pattern = "drug_spend_%"
    if sort_by == "volume":
        metric_pattern = "drug_volume_%"

    start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
    end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())

    result = await db.execute(
        sa.select(
            KpiRollup.metric_key,
            sa.func.sum(KpiRollup.value).label("total_value"),
            sa.func.count(KpiRollup.id).label("count"),
        )
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key.like(metric_pattern),
            KpiRollup.bucket_ts >= start_ts,
            KpiRollup.bucket_ts <= end_ts,
        )
        .group_by(KpiRollup.metric_key)
        .order_by(sa.desc("total_value"))
        .limit(limit)
    )
    rows = result.all()

    return [
        {
            "ndc": row.metric_key.split("_", 2)[-1] if "_" in row.metric_key else row.metric_key,
            "drug_name": row.metric_key,
            "total_spend": Decimal(str(row.total_value)),
            "claim_count": int(row.count),
            "avg_cost_per_claim": (
                Decimal(str(row.total_value)) / Decimal(str(row.count))
                if row.count > 0
                else Decimal("0.00")
            ),
            "rank": idx + 1,
        }
        for idx, row in enumerate(rows)
    ]


@router.get("/drug-trend/spend")
async def get_drug_spend_trend(
    tenant_id: TenantId,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Drug spend trending over time from KPI rollups."""
    start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
    end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())

    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "total_drug_spend",
            KpiRollup.bucket_ts >= start_ts,
            KpiRollup.bucket_ts <= end_ts,
        )
        .order_by(KpiRollup.bucket_ts.asc())
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "granularity": r.granularity,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/drug-trend/glp1")
async def get_glp1_tracking(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """GLP-1 / weight-loss drug utilization and cost trending."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "glp1_spend",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(90)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "granularity": r.granularity,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/drug-trend/biosimilar")
async def get_biosimilar_adoption(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Biosimilar vs reference biologic adoption rates from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key.in_(["biosimilar_claim_count", "biologic_claim_count"]),
        )
        .order_by(KpiRollup.metric_key, KpiRollup.bucket_ts.desc())
        .limit(180)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "metric_key": r.metric_key,
                "bucket_ts": r.bucket_ts,
                "granularity": r.granularity,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/drug-trend/new-drugs")
async def get_new_drug_impact(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Newly launched drugs: adoption rate and spend impact from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "new_drug_spend",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(90)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "granularity": r.granularity,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/drug-trend/price-inflation")
async def get_price_inflation(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """NDC-level price change tracking from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "avg_drug_unit_cost",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(90)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "granularity": r.granularity,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Network Analytics
# ---------------------------------------------------------------------------


@router.get("/network/adequacy", response_model=NetworkAdequacyResponse)
async def get_network_adequacy(
    tenant_id: TenantId,
    radius_miles: Decimal = Query(default=Decimal("5")),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Network adequacy: % of members within radius of in-network pharmacy.

    Queries member and pharmacy location data from KPI rollup summary values,
    then computes adequacy using the geo_analytics service.
    """
    # Pull aggregated network adequacy counters from KPI rollups
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key.in_(["network_total_members", "network_covered_members"]),
            KpiRollup.granularity == "day",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(2)
    )
    rows = result.scalars().all()

    total_members_row = next(
        (r for r in rows if r.metric_key == "network_total_members"), None
    )
    covered_members_row = next(
        (r for r in rows if r.metric_key == "network_covered_members"), None
    )

    total_members = int(total_members_row.value) if total_members_row is not None else 0
    covered_members = int(covered_members_row.value) if covered_members_row is not None else 0

    if total_members > 0:
        pct = (
            Decimal(str(covered_members)) / Decimal(str(total_members)) * Decimal("100")
        ).quantize(Decimal("0.01"))
    else:
        pct = Decimal("0.00")

    # Supplement with haversine calculation if no rollup data: return zero-state
    if total_members == 0:
        adequacy = calculate_network_adequacy(
            members=[],
            pharmacies=[],
            radius_miles=radius_miles,
        )
        return {
            "total_members": adequacy.total_members,
            "covered_members": adequacy.covered_members,
            "pct_members_covered": adequacy.pct_members_covered,
            "radius_miles": radius_miles,
        }

    return {
        "total_members": total_members,
        "covered_members": covered_members,
        "pct_members_covered": pct,
        "radius_miles": radius_miles,
    }


@router.get("/network/scorecard")
async def get_network_scorecard(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Pharmacy performance scorecard from KPI rollup metrics."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key.like("pharmacy_%"),
        )
        .order_by(KpiRollup.metric_key, KpiRollup.bucket_ts.desc())
        .limit(200)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "metric_key": r.metric_key,
                "bucket_ts": r.bucket_ts,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/network/leakage")
async def get_network_leakage(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Out-of-network utilization analysis from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key.in_(["oon_claim_count", "oon_spend"]),
        )
        .order_by(KpiRollup.metric_key, KpiRollup.bucket_ts.desc())
        .limit(180)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "metric_key": r.metric_key,
                "bucket_ts": r.bucket_ts,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/network/cost-variation")
async def get_cost_variation(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Same-drug cost comparison across pharmacies from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "avg_cost_per_claim",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(90)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Member Analytics
# ---------------------------------------------------------------------------


@router.get("/member/adherence")
async def get_adherence_dashboard(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """PDC-based adherence dashboard from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "pdc_rate",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(90)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "granularity": r.granularity,
                "pdc_rate": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/member/high-cost")
async def get_high_cost_claimants(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Top 1% members by cost from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "high_cost_member_spend",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(90)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/member/polypharmacy")
async def get_polypharmacy_risk(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Members on 5+ concurrent medications from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "polypharmacy_member_count",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(90)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/member/therapy-gaps")
async def get_therapy_gaps(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Members who should be on a therapy but are not, from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "therapy_gap_member_count",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(90)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/member/opioid")
async def get_opioid_utilization(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Opioid MME tracking and CDC guideline compliance from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key.in_(["opioid_mme_avg", "opioid_high_dose_member_count"]),
        )
        .order_by(KpiRollup.metric_key, KpiRollup.bucket_ts.desc())
        .limit(180)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "metric_key": r.metric_key,
                "bucket_ts": r.bucket_ts,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Financial Analytics
# ---------------------------------------------------------------------------


@router.get("/financial/cost-drivers")
async def get_cost_drivers(
    tenant_id: TenantId,
    start_period: date = Query(...),
    end_period: date = Query(...),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Cost driver decomposition from stored trend decomposition rows."""
    period_pair = f"{start_period}/{end_period}"

    result = await db.execute(
        sa.select(TrendDecomposition)
        .where(
            TrendDecomposition.tenant_id == tenant_id,
            TrendDecomposition.period_pair == period_pair,
        )
        .order_by(TrendDecomposition.drug_class)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "period_pair": period_pair,
        "data": [
            {
                "drug_class": r.drug_class,
                "utilization_effect": Decimal(str(r.utilization_effect)),
                "price_effect": Decimal(str(r.price_effect)),
                "mix_effect": Decimal(str(r.mix_effect)),
                "total_delta": Decimal(str(r.total_delta)),
            }
            for r in rows
        ],
    }


@router.get("/financial/pmpm")
async def get_pmpm_trending(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Per member per month cost trending from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key == "pmpm_cost",
        )
        .order_by(KpiRollup.bucket_ts.desc())
        .limit(90)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "bucket_ts": r.bucket_ts,
                "granularity": r.granularity,
                "pmpm": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/financial/spread")
async def get_spread_analysis(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Plan paid vs pharmacy reimbursement spread from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key.in_(["plan_paid_total", "pharmacy_reimbursement_total"]),
        )
        .order_by(KpiRollup.metric_key, KpiRollup.bucket_ts.desc())
        .limit(180)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "metric_key": r.metric_key,
                "bucket_ts": r.bucket_ts,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


@router.get("/financial/profitability")
async def get_client_profitability(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Revenue vs cost per client from KPI rollups."""
    result = await db.execute(
        sa.select(KpiRollup)
        .where(
            KpiRollup.tenant_id == tenant_id,
            KpiRollup.metric_key.in_(["revenue_total", "cost_total"]),
        )
        .order_by(KpiRollup.metric_key, KpiRollup.bucket_ts.desc())
        .limit(180)
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "data": [
            {
                "metric_key": r.metric_key,
                "bucket_ts": r.bucket_ts,
                "value": Decimal(str(r.value)),
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------


@router.get("/data-quality", response_model=DataQualityScoreResponse)
async def get_data_quality(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Current (most recent) data quality score for the tenant."""
    result = await db.execute(
        sa.select(DataQualityScore)
        .where(DataQualityScore.tenant_id == tenant_id)
        .order_by(DataQualityScore.score_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()

    if row is None:
        today = date.today()
        return {
            "score_date": today,
            "overall_score": Decimal("100.00"),
            "volume_score": None,
            "completeness_score": None,
            "format_score": None,
            "timeliness_score": None,
            "consistency_score": None,
            "referential_score": None,
            "issues": None,
        }

    return {
        "score_date": row.score_date,
        "overall_score": Decimal(str(row.overall_score)),
        "volume_score": Decimal(str(row.volume_score)) if row.volume_score is not None else None,
        "completeness_score": Decimal(str(row.completeness_score)) if row.completeness_score is not None else None,
        "format_score": Decimal(str(row.format_score)) if row.format_score is not None else None,
        "timeliness_score": Decimal(str(row.timeliness_score)) if row.timeliness_score is not None else None,
        "consistency_score": Decimal(str(row.consistency_score)) if row.consistency_score is not None else None,
        "referential_score": Decimal(str(row.referential_score)) if row.referential_score is not None else None,
        "issues": row.issues,
    }


@router.get("/data-quality/history")
async def get_data_quality_history(
    tenant_id: TenantId,
    days: int = Query(default=90, ge=1, le=730),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Historical data quality scores for the tenant."""
    cutoff = sa.func.current_date() - days

    result = await db.execute(
        sa.select(DataQualityScore)
        .where(
            DataQualityScore.tenant_id == tenant_id,
            DataQualityScore.score_date >= cutoff,
        )
        .order_by(DataQualityScore.score_date.desc())
    )
    rows = result.scalars().all()

    return {
        "tenant_id": str(tenant_id),
        "scores": [
            {
                "score_date": r.score_date.isoformat(),
                "overall_score": Decimal(str(r.overall_score)),
                "volume_score": Decimal(str(r.volume_score)) if r.volume_score is not None else None,
                "completeness_score": Decimal(str(r.completeness_score)) if r.completeness_score is not None else None,
            }
            for r in rows
        ],
    }


@router.get("/data-quality/issues")
async def get_data_quality_issues(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Active data quality issues from the most recent score row."""
    result = await db.execute(
        sa.select(DataQualityScore)
        .where(DataQualityScore.tenant_id == tenant_id)
        .order_by(DataQualityScore.score_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()

    issues: list[dict[str, Any]] = []
    if row is not None and row.issues:
        raw = row.issues
        if isinstance(raw, list):
            issues = raw
        elif isinstance(raw, dict):
            issues = [raw]

    return {"tenant_id": str(tenant_id), "issues": issues}


# ---------------------------------------------------------------------------
# Benchmarking
# ---------------------------------------------------------------------------


@router.get("/benchmarks", response_model=list[BenchmarkResponse])
async def list_benchmarks(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List all active benchmarks for the tenant."""
    result = await db.execute(
        sa.select(Benchmark)
        .where(
            Benchmark.tenant_id == tenant_id,
            Benchmark.is_active.is_(True),
        )
        .order_by(Benchmark.name)
    )
    rows = result.scalars().all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "metric_key": r.metric_key,
            "benchmark_type": r.benchmark_type,
            "target_value": Decimal(str(r.target_value)) if r.target_value is not None else None,
            "warning_threshold": Decimal(str(r.warning_threshold)) if r.warning_threshold is not None else None,
            "critical_threshold": Decimal(str(r.critical_threshold)) if r.critical_threshold is not None else None,
            "is_active": r.is_active,
        }
        for r in rows
    ]


@router.post("/benchmarks", response_model=BenchmarkResponse, status_code=status.HTTP_201_CREATED)
async def create_benchmark(
    tenant_id: TenantId,
    body: BenchmarkCreateRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Create a new benchmark for the tenant."""
    new_id = uuid.uuid4()
    benchmark = Benchmark(
        id=new_id,
        tenant_id=tenant_id,
        name=body.name,
        metric_key=body.metric_key,
        benchmark_type=body.benchmark_type,
        target_value=body.target_value,
        warning_threshold=body.warning_threshold,
        critical_threshold=body.critical_threshold,
        comparison_operator=body.comparison_operator,
        is_active=True,
    )
    db.add(benchmark)
    await db.flush()
    await db.commit()

    return {
        "id": benchmark.id,
        "name": benchmark.name,
        "metric_key": benchmark.metric_key,
        "benchmark_type": benchmark.benchmark_type,
        "target_value": Decimal(str(benchmark.target_value)) if benchmark.target_value is not None else None,
        "warning_threshold": Decimal(str(benchmark.warning_threshold)) if benchmark.warning_threshold is not None else None,
        "critical_threshold": Decimal(str(benchmark.critical_threshold)) if benchmark.critical_threshold is not None else None,
        "is_active": benchmark.is_active,
    }


@router.put("/benchmarks/{benchmark_id}", response_model=BenchmarkResponse)
async def update_benchmark(
    benchmark_id: uuid.UUID,
    tenant_id: TenantId,
    body: BenchmarkCreateRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update an existing benchmark (tenant-scoped)."""
    result = await db.execute(
        sa.select(Benchmark).where(
            Benchmark.id == benchmark_id,
            Benchmark.tenant_id == tenant_id,
        )
    )
    benchmark = result.scalar_one_or_none()

    if benchmark is None:
        correlation_id = _corr()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "BENCHMARK_NOT_FOUND",
                    "message": "Benchmark not found or access denied",
                    "correlation_id": correlation_id,
                }
            },
        )

    benchmark.name = body.name
    benchmark.metric_key = body.metric_key
    benchmark.benchmark_type = body.benchmark_type
    benchmark.target_value = body.target_value
    benchmark.warning_threshold = body.warning_threshold
    benchmark.critical_threshold = body.critical_threshold
    benchmark.comparison_operator = body.comparison_operator
    await db.commit()

    return {
        "id": benchmark.id,
        "name": benchmark.name,
        "metric_key": benchmark.metric_key,
        "benchmark_type": benchmark.benchmark_type,
        "target_value": Decimal(str(benchmark.target_value)) if benchmark.target_value is not None else None,
        "warning_threshold": Decimal(str(benchmark.warning_threshold)) if benchmark.warning_threshold is not None else None,
        "critical_threshold": Decimal(str(benchmark.critical_threshold)) if benchmark.critical_threshold is not None else None,
        "is_active": benchmark.is_active,
    }


@router.get("/benchmarks/status")
async def get_benchmarks_status(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """All benchmarks with current green/yellow/red status vs latest KPI rollup."""
    bench_result = await db.execute(
        sa.select(Benchmark).where(
            Benchmark.tenant_id == tenant_id,
            Benchmark.is_active.is_(True),
        )
    )
    benchmarks = bench_result.scalars().all()

    output = []
    for b in benchmarks:
        # Fetch most recent rollup value for this metric
        kpi_result = await db.execute(
            sa.select(KpiRollup)
            .where(
                KpiRollup.tenant_id == tenant_id,
                KpiRollup.metric_key == b.metric_key,
            )
            .order_by(KpiRollup.bucket_ts.desc())
            .limit(1)
        )
        kpi_row = kpi_result.scalar_one_or_none()
        current_value = Decimal(str(kpi_row.value)) if kpi_row is not None else None

        benchmark_status = "unknown"
        if current_value is not None:
            target = Decimal(str(b.target_value)) if b.target_value is not None else None
            warn = Decimal(str(b.warning_threshold)) if b.warning_threshold is not None else None
            crit = Decimal(str(b.critical_threshold)) if b.critical_threshold is not None else None

            if crit is not None and current_value < crit:
                benchmark_status = "red"
            elif warn is not None and current_value < warn:
                benchmark_status = "yellow"
            elif target is not None and current_value >= target:
                benchmark_status = "green"
            else:
                benchmark_status = "yellow"

        output.append(
            {
                "id": str(b.id),
                "name": b.name,
                "metric_key": b.metric_key,
                "current_value": current_value,
                "target_value": Decimal(str(b.target_value)) if b.target_value is not None else None,
                "status": benchmark_status,
            }
        )

    return {"tenant_id": str(tenant_id), "benchmarks": output}


# ---------------------------------------------------------------------------
# Insight Alerts
# ---------------------------------------------------------------------------


@router.get("/insights", response_model=list[InsightAlertResponse])
async def list_insights(
    tenant_id: TenantId,
    unacknowledged_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List insight alerts for the tenant."""
    filters = [InsightAlert.tenant_id == tenant_id]
    if unacknowledged_only:
        filters.append(InsightAlert.acknowledged_at.is_(None))

    result = await db.execute(
        sa.select(InsightAlert)
        .where(*filters)
        .order_by(InsightAlert.created_at.desc())
        .limit(200)
    )
    alerts = result.scalars().all()

    return [
        {
            "id": a.id,
            "insight_type": a.insight_type,
            "severity": a.severity,
            "title": a.title,
            "description": a.description,
            "metric_key": a.metric_key,
            "metric_value": Decimal(str(a.metric_value)) if a.metric_value is not None else None,
            "threshold_value": Decimal(str(a.threshold_value)) if a.threshold_value is not None else None,
            "affected_entity_type": a.affected_entity_type,
            "affected_entity_name": a.affected_entity_name,
            "recommended_action": a.recommended_action,
            "acknowledged_at": a.acknowledged_at,
            "created_at": a.created_at,
        }
        for a in alerts
    ]


@router.put("/insights/{insight_id}/acknowledge")
async def acknowledge_insight(
    insight_id: uuid.UUID,
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Acknowledge an insight alert (tenant-scoped)."""
    result = await db.execute(
        sa.select(InsightAlert).where(
            InsightAlert.id == insight_id,
            InsightAlert.tenant_id == tenant_id,
        )
    )
    alert = result.scalar_one_or_none()

    if alert is None:
        correlation_id = _corr()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "INSIGHT_NOT_FOUND",
                    "message": "Insight alert not found or access denied",
                    "correlation_id": correlation_id,
                }
            },
        )

    alert.acknowledged_at = datetime.now(UTC)
    await db.commit()

    return {"id": str(insight_id), "acknowledged": True, "acknowledged_at": alert.acknowledged_at.isoformat()}


@router.get("/insights/summary", response_model=InsightSummaryResponse)
async def get_insights_summary(
    tenant_id: TenantId,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Summary counts of unacknowledged insight alerts by severity."""
    result = await db.execute(
        sa.select(
            InsightAlert.severity,
            sa.func.count(InsightAlert.id).label("cnt"),
        )
        .where(
            InsightAlert.tenant_id == tenant_id,
            InsightAlert.acknowledged_at.is_(None),
        )
        .group_by(InsightAlert.severity)
    )
    rows = result.all()

    counts: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
    for row in rows:
        if row.severity in counts:
            counts[row.severity] = int(row.cnt)

    total = sum(counts.values())

    return {
        "total_unacknowledged": total,
        "critical_count": counts["critical"],
        "warning_count": counts["warning"],
        "info_count": counts["info"],
    }
