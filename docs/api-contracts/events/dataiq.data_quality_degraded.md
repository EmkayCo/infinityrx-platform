# Event Contract: `dataiq.data_quality_degraded`

**Schema version:** 1.0
**Status:** Active

## Description

A data quality score for a tracked data source or feed has dropped below
the acceptable threshold.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `data_source` | `str` | yes | Data source or feed name |
| `quality_score` | `str (Decimal)` | yes | Current quality score (0.00–1.00) |
| `threshold` | `str (Decimal)` | yes | Minimum acceptable score |
| `failed_checks` | `list[str]` | yes | Names of failed quality checks |
| `occurred_at` | `str (ISO-8601)` | yes | Detection timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `dataiq` | Data quality monitoring job detects degradation |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | alert | Notify data operations team |

## Ordering Key Convention

**`ordering_key`:** `data_source`

## Idempotency Key Convention

**`idempotency_key`:** `dataiq.data_quality_degraded:{data_source}:{occurred_at}`

## Example Payload

```json
{
  "event_type": "dataiq.data_quality_degraded",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "data_source": "pharmacy_claims_feed",
  "quality_score": "0.72",
  "threshold": "0.95",
  "failed_checks": ["null_ndc_rate", "duplicate_auth_numbers"],
  "occurred_at": "2026-04-14T05:00:00Z"
}
```
