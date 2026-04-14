# Event Contract: `quality.measure_at_risk`

**Schema version:** 1.0
**Status:** Active

## Description

A CMS Star Rating PDC measure's adherence rate has fallen below the threshold
needed to maintain current star score with the current gap-closure pace.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `measure_code` | `str` | yes | CMS measure code (e.g., `CMC`, `RAS`, `SPC`) |
| `current_rate` | `str (Decimal)` | yes | Current PDC adherence rate (0.00–1.00) |
| `target_rate` | `str (Decimal)` | yes | Target rate to maintain star score |
| `gap_count` | `int` | yes | Number of members with adherence gap |
| `occurred_at` | `str (ISO-8601)` | yes | Alert generation timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `reporting` | Star Ratings job detects measure at risk |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | `handle_quality_measure_at_risk` | Auto-generate PDC gap report |

## Ordering Key Convention

**`ordering_key`:** `measure_code`

## Idempotency Key Convention

**`idempotency_key`:** `quality.measure_at_risk:{measure_code}:{occurred_at}`

## Example Payload

```json
{
  "event_type": "quality.measure_at_risk",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "measure_code": "CMC",
  "current_rate": "0.78",
  "target_rate": "0.82",
  "gap_count": 142,
  "occurred_at": "2026-04-14T08:00:00Z"
}
```
