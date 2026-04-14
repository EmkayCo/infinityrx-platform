"""DataIQ module constants — no magic numbers in service code."""

from __future__ import annotations

from decimal import Decimal

# Redis TTL for raw KPI buckets (25 hours — keeps one full day for rollup)
REDIS_KPI_TTL_SECONDS: int = 25 * 3600

# SPC defaults (externalized — never hardcoded in service logic)
SPC_DEFAULT_WINDOW_DAYS: int = 30
SPC_DEFAULT_SIGMA_WARNING: Decimal = Decimal("2")
SPC_DEFAULT_SIGMA_CRITICAL: Decimal = Decimal("3")
SPC_MIN_BASELINE_SAMPLES: int = 2

# Data quality thresholds (configurable per tenant; these are defaults)
DQ_DEFAULT_ALERT_THRESHOLD: Decimal = Decimal("95.00")
DQ_VOLUME_ALERT_LOW_PCT: Decimal = Decimal("0.50")
DQ_VOLUME_ALERT_HIGH_PCT: Decimal = Decimal("2.00")
DQ_NULL_RATE_THRESHOLD: Decimal = Decimal("0.05")
DQ_INVALID_RATE_THRESHOLD: Decimal = Decimal("0.01")
DQ_DUPLICATE_RATE_THRESHOLD: Decimal = Decimal("0.001")

# Network adequacy (CMS Part D standards)
CMS_ADEQUACY_RADIUS_URBAN_MILES: Decimal = Decimal("2")
CMS_ADEQUACY_RADIUS_SUBURBAN_MILES: Decimal = Decimal("5")
CMS_ADEQUACY_RADIUS_RURAL_MILES: Decimal = Decimal("15")
CMS_DRUG_DESERT_THRESHOLD_PER_10K: Decimal = Decimal("1")

# Repricing
REPRICING_MAX_CLAIMS_PER_JOB: int = 1_000_000
REPRICING_CHUNK_SIZE: int = 10_000

# Forecast
FORECAST_MIN_HISTORY_MONTHS: int = 3
FORECAST_MIN_HISTORY_FOR_SEASONAL: int = 12
FORECAST_DEFAULT_HORIZON_MONTHS: int = 12
FORECAST_DEFAULT_CONFIDENCE_INTERVAL: Decimal = Decimal("0.95")

# Benchmark status thresholds
BENCHMARK_WARNING_WITHIN_PCT: Decimal = Decimal("0.05")

# Retention (days)
METRIC_SNAPSHOT_RETENTION_DAYS: int = 3 * 365
DQ_SCORE_RETENTION_DAYS: int = 2 * 365
INSIGHT_ALERT_RETENTION_DAYS: int = 365
REPRICING_RUN_RETENTION_DAYS: int = 90
