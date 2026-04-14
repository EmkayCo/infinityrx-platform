# Event Contract: `dataiq.forecast_deviation`

**Schema version:** 1.0
**Status:** Active

## Description

Actual results have deviated significantly from the DataIQ forecast model
prediction, indicating the model may need recalibration.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `forecast_id` | `UUID` | yes | Forecast model ID |
| `metric_name` | `str` | yes | Metric being forecasted |
| `forecast_value` | `str (Decimal)` | yes | Forecasted value |
| `actual_value` | `str (Decimal)` | yes | Observed actual value |
| `deviation_pct` | `str (Decimal)` | yes | Percentage deviation |
| `occurred_at` | `str (ISO-8601)` | yes | Detection timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `dataiq` | Forecast reconciliation job finds significant deviation |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | dashboard | Flag forecast accuracy warning |

## Ordering Key Convention

**`ordering_key`:** `forecast_id`

## Idempotency Key Convention

**`idempotency_key`:** `dataiq.forecast_deviation:{forecast_id}:{occurred_at}`

## Example Payload

```json
{
  "event_type": "dataiq.forecast_deviation",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "forecast_id": "uuid",
  "metric_name": "monthly_claim_volume",
  "forecast_value": "85000",
  "actual_value": "112000",
  "deviation_pct": "31.76",
  "occurred_at": "2026-04-14T09:00:00Z"
}
```
