# Event Contract: `dataiq.anomaly_detected`

**Schema version:** 1.0
**Status:** Active

## Description

DataIQ has detected a statistical anomaly in a tracked metric that warrants
investigation.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `anomaly_id` | `UUID` | yes | Anomaly record ID |
| `metric_name` | `str` | yes | Metric where anomaly was detected |
| `observed_value` | `str (Decimal)` | yes | Observed metric value |
| `expected_range_low` | `str (Decimal)` | yes | Lower bound of expected range |
| `expected_range_high` | `str (Decimal)` | yes | Upper bound of expected range |
| `sigma` | `str (Decimal)` | yes | Standard deviations from mean |
| `occurred_at` | `str (ISO-8601)` | yes | Detection timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `dataiq` | Anomaly detection job fires |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reclaimrx` | correlation | Cross-reference with FWA patterns |

## Ordering Key Convention

**`ordering_key`:** `anomaly_id`

## Idempotency Key Convention

**`idempotency_key`:** `dataiq.anomaly_detected:{anomaly_id}`

## Example Payload

```json
{
  "event_type": "dataiq.anomaly_detected",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "anomaly_id": "uuid",
  "metric_name": "pharmacy_dispense_rate",
  "observed_value": "4.2",
  "expected_range_low": "0.8",
  "expected_range_high": "1.4",
  "sigma": "8.1",
  "occurred_at": "2026-04-14T07:00:00Z"
}
```
