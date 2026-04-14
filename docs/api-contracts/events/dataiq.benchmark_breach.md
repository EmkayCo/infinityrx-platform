# Event Contract: `dataiq.benchmark_breach`

**Schema version:** 1.0
**Status:** Active

## Description

A tracked KPI has breached a configured performance benchmark threshold.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `benchmark_id` | `UUID` | yes | Benchmark configuration ID |
| `kpi_name` | `str` | yes | KPI that breached |
| `current_value` | `str (Decimal)` | yes | Current KPI value |
| `threshold_value` | `str (Decimal)` | yes | Threshold that was breached |
| `direction` | `str` | yes | `above` or `below` |
| `occurred_at` | `str (ISO-8601)` | yes | Breach timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `dataiq` | KPI monitoring job detects threshold breach |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | alert | Trigger breach notification report |

## Ordering Key Convention

**`ordering_key`:** `benchmark_id`

## Idempotency Key Convention

**`idempotency_key`:** `dataiq.benchmark_breach:{benchmark_id}:{occurred_at}`

## Example Payload

```json
{
  "event_type": "dataiq.benchmark_breach",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "benchmark_id": "uuid",
  "kpi_name": "generic_dispensing_rate",
  "current_value": "0.71",
  "threshold_value": "0.80",
  "direction": "below",
  "occurred_at": "2026-04-14T08:00:00Z"
}
```
