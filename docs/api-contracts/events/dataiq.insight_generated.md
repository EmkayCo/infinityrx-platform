# Event Contract: `dataiq.insight_generated`

**Schema version:** 1.0
**Status:** Active

## Description

The DataIQ analytics engine has generated a new insight from trend analysis
or anomaly detection.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `insight_id` | `UUID` | yes | Insight record ID |
| `insight_type` | `str` | yes | `trend`, `anomaly`, `forecast`, `benchmark` |
| `domain` | `str` | yes | Domain area (e.g., `claims`, `pharmacy`, `drug`) |
| `severity` | `str` | yes | `info`, `warning`, `critical` |
| `occurred_at` | `str (ISO-8601)` | yes | Insight generation timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `dataiq` | Analytics job produces actionable insight |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | dashboard | Surface insight in analytics dashboard |

## Ordering Key Convention

**`ordering_key`:** `insight_id`

## Idempotency Key Convention

**`idempotency_key`:** `dataiq.insight_generated:{insight_id}`

## Example Payload

```json
{
  "event_type": "dataiq.insight_generated",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "insight_id": "uuid",
  "insight_type": "anomaly",
  "domain": "pharmacy",
  "severity": "warning",
  "occurred_at": "2026-04-14T06:00:00Z"
}
```
