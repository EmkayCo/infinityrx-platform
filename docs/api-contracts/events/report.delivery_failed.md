# Event Contract: `report.delivery_failed`

**Schema version:** 1.0
**Status:** Active

## Description

A report delivery attempt has failed after all retries. Manual intervention
is required to redeliver.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `report_id` | `UUID` | yes | Report definition ID |
| `run_id` | `UUID` | yes | Report run that failed delivery |
| `delivery_channel` | `str` | yes | Attempted delivery channel |
| `error_message` | `str` | yes | Reason for delivery failure |
| `occurred_at` | `str (ISO-8601)` | yes | Failure timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `reporting` | All delivery retries exhausted |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | — | Alert operations team |

## Ordering Key Convention

**`ordering_key`:** `run_id`

## Idempotency Key Convention

**`idempotency_key`:** `report.delivery_failed:{run_id}`

## Example Payload

```json
{
  "event_type": "report.delivery_failed",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "report_id": "uuid",
  "run_id": "uuid",
  "delivery_channel": "sftp",
  "error_message": "Connection refused: SFTP server unreachable",
  "occurred_at": "2026-04-14T06:10:00Z"
}
```
