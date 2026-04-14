# Event Contract: `prefund.critical`

**Schema version:** 1.0
**Status:** Active

## Description

A prefunding account balance has dropped to a critical level that may prevent
timely payment disbursement.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `account_id` | `UUID` | yes | Prefund account ID |
| `current_balance` | `str (Decimal)` | yes | Current balance |
| `minimum_required` | `str (Decimal)` | yes | Minimum balance required for next cycle |
| `shortfall` | `str (Decimal)` | yes | Amount below minimum |
| `occurred_at` | `str (ISO-8601)` | yes | Alert generation timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `reporting` | Prefund balance monitoring job detects critical shortfall |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | `handle_prefund_critical` | Auto-generate prefund alert report |

## Ordering Key Convention

**`ordering_key`:** `account_id`

## Idempotency Key Convention

**`idempotency_key`:** `prefund.critical:{account_id}:{occurred_at}`

## Example Payload

```json
{
  "event_type": "prefund.critical",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "account_id": "uuid",
  "current_balance": "50000.00",
  "minimum_required": "250000.00",
  "shortfall": "200000.00",
  "occurred_at": "2026-04-14T06:00:00Z"
}
```
