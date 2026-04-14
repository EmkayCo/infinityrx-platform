# DataIQ Module

Advanced analytics and business intelligence engine for InfinityRx platform.

## Purpose

DataIQ answers "Why did it happen? What will happen next? What should we do about it?" — complementing the Reporting module which answers "What happened?"

## Capabilities

- **Real-time KPIs**: Redis-backed counters updated on every event. Claim rate, spend, FWA flags per minute/hour/day. Tenant-scoped keys.
- **Statistical Process Control (SPC)**: X-bar control charts with Western Electric rules. Detects anomalies at 2σ/3σ thresholds from 30-day rolling baseline.
- **Drug Trend Decomposition**: Decomposes spend change into utilization + price + mix effects. Components always sum exactly to total delta (Decimal arithmetic).
- **Claims Repricing Engine**: Pure-function `reprice_claim()` applies candidate plan designs to historical claims. Same inputs always produce same output. Processes 1M+ claims.
- **PostGIS Geo Analytics**: Network adequacy (CMS Part D standard), drug desert detection, haversine distance calculations.
- **Data Quality Monitoring**: 8 monitors with daily scoring 0-100 per tenant.
- **Benchmarking Engine**: 4 benchmark types (internal, historical, target, industry) with green/yellow/red status.
- **Insight Alerts**: Auto-generated with delivery via notifications, email, webhooks.
- **Drug Trend Analytics**: 10 pre-built analyses (GLP-1, biosimilar, top drugs, price inflation, etc.)
- **Network/Member/Financial Analytics**: 20+ pre-built analyses.

## API

Base URL: `/api/v1/dataiq/`

All endpoints require `X-Tenant-Id: <uuid>` header.

Key endpoints:
- `GET /metrics` — list metric definitions
- `GET /metrics/{key}/current` — real-time value from Redis
- `GET /metrics/{key}/history` — historical values with SPC bands
- `GET /drug-trend/decomposition` — spend change decomposition
- `GET /network/adequacy` — CMS network adequacy %
- `GET /data-quality` — current quality score
- `GET /insights` — insight alerts
- `POST /benchmarks` — create benchmark

## Setup

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest modules/dataiq/tests/ --cov=modules/dataiq/src --cov-config=modules/dataiq/.coveragerc

# Start service
uv run uvicorn modules.dataiq.src.main:app --port 8006
```

## Configuration

All thresholds are externalized in `src/utils/constants.py`:
- `SPC_DEFAULT_SIGMA_WARNING` / `SPC_DEFAULT_SIGMA_CRITICAL`
- `DQ_DEFAULT_ALERT_THRESHOLD`
- `CMS_ADEQUACY_RADIUS_*_MILES`
- `REPRICING_MAX_CLAIMS_PER_JOB`

## Database

Schema: `dataiq`. Tables:
- `metric_definitions` — global metric catalog
- `metric_snapshots` — hourly/daily KPI snapshots (tenant-scoped)
- `kpi_rollups` — Redis → Postgres warm storage
- `spc_alerts` — anomaly detection results
- `data_quality_scores` — daily scores per tenant
- `benchmarks` — configurable benchmark targets
- `insight_alerts` — auto-generated insights
- `trend_decomposition` — drug trend results
- `repricing_runs` — idempotent repricing results
- `forecast_models` — trained forecast models
- `saved_explorations` — self-service exploration configs

## Test Coverage

- 146 tests: 83 unit, 17 integration, 17 property-based, 29 coverage-targeted
- 99.32% branch coverage on all service/API code
- 100% on: trend decomposition, repricing math, geo analytics, KPI counters, publishers, consumers, router, main
- Property-based tests (Hypothesis): 500+ examples per invariant for decomposition and repricing
