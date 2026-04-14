"""Real-time KPI Redis counter service.

Keys: tenant:{tenant_id}:kpi:{metric}:{granularity}:{bucket_ts}
Tenant scoping is MANDATORY — no tenant-unscoped keys.
Increment via INCRBY/HINCRBYFLOAT from event consumers, never from API handlers.
TTL: 25 hours on raw buckets.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import StrEnum
from typing import Any

_TTL_SECONDS = 25 * 3600


class KPIGranularity(StrEnum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


def build_kpi_key(
    tenant_id: uuid.UUID,
    metric: str,
    granularity: KPIGranularity,
    bucket_ts: int,
) -> str:
    """Build a Redis key for a KPI counter.

    Format: tenant:{tenant_id}:kpi:{metric}:{granularity}:{bucket_ts}
    """
    return f"tenant:{tenant_id}:kpi:{metric}:{granularity.value}:{bucket_ts}"


async def increment_counter(
    redis: Any,
    tenant_id: uuid.UUID,
    metric: str,
    bucket_ts: int,
    amount: int = 1,
    granularity: KPIGranularity = KPIGranularity.MINUTE,
) -> int:
    """Increment an integer KPI counter atomically.

    Uses INCRBY (never SET) to prevent race conditions.
    Sets TTL on first write (25 hours).
    """
    key = build_kpi_key(tenant_id, metric, granularity, bucket_ts)
    new_val: int = await redis.incrby(key, amount)
    await redis.expire(key, _TTL_SECONDS)
    return new_val


async def increment_financial_counter(
    redis: Any,
    tenant_id: uuid.UUID,
    metric: str,
    bucket_ts: int,
    amount: Decimal,
    granularity: KPIGranularity = KPIGranularity.MINUTE,
) -> None:
    """Increment a financial (Decimal) KPI counter using hash field.

    Stores as hash field to support Decimal amounts via HINCRBYFLOAT.
    The field key is the bucket_ts so one Redis hash holds all buckets
    for a given metric+granularity.
    """
    hash_key = f"tenant:{tenant_id}:kpi:{metric}:{granularity.value}:financial"
    field = str(bucket_ts)
    await redis.hincrbyfloat(hash_key, field, float(amount))
    await redis.expire(hash_key, _TTL_SECONDS)
