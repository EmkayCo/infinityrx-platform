# Event Contract: `drug.refresh_completed`

**Schema version:** 1.0
**Status:** Active

## Description

The drug database has completed a scheduled data refresh from the external
drug data vendor.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `refresh_id` | `UUID` | yes | Refresh job ID |
| `records_updated` | `int` | yes | Number of records updated |
| `records_added` | `int` | yes | Number of new records added |
| `occurred_at` | `str (ISO-8601)` | yes | Refresh completion timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `drug-database` | Data refresh job completes |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(adjudication-engine)* | — | Invalidate NDC lookup cache |

## Ordering Key Convention

**`ordering_key`:** `refresh_id`

## Idempotency Key Convention

**`idempotency_key`:** `drug.refresh_completed:{refresh_id}`

## Example Payload

```json
{
  "event_type": "drug.refresh_completed",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "refresh_id": "uuid",
  "records_updated": 4812,
  "records_added": 37,
  "occurred_at": "2026-04-14T03:00:00Z"
}
```
