# Event Contract: `report.delivered`

**Schema version:** 1.0
**Status:** Active

## Description

A generated report has been successfully delivered to its configured destination
(email, SFTP, or portal download).

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `report_id` | `UUID` | yes | Report definition ID |
| `run_id` | `UUID` | yes | Report run that was delivered |
| `delivery_channel` | `str` | yes | `email`, `sftp`, `portal` |
| `recipient` | `str` | no | Delivery destination (email address or SFTP path) |
| `occurred_at` | `str (ISO-8601)` | yes | Delivery timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `reporting` | Report delivery succeeds |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | — | Audit delivery log |

## Ordering Key Convention

**`ordering_key`:** `run_id`

## Idempotency Key Convention

**`idempotency_key`:** `report.delivered:{run_id}:{delivery_channel}`

## Example Payload

```json
{
  "event_type": "report.delivered",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "report_id": "uuid",
  "run_id": "uuid",
  "delivery_channel": "email",
  "recipient": "finance@plan.com",
  "occurred_at": "2026-04-14T06:05:00Z"
}
```
