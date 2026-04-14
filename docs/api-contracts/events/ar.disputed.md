# Event Contract: `ar.disputed`

**Schema version:** 1.0
**Status:** Active

## Description

A client has disputed an accounts-receivable record, placing it on hold
pending resolution.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `ar_id` | `UUID` | yes | AR record being disputed |
| `client_id` | `UUID` | yes | Client raising the dispute |
| `dispute_reason` | `str` | yes | Reason for dispute |
| `amount_disputed` | `str (Decimal)` | yes | Amount under dispute |
| `occurred_at` | `str (ISO-8601)` | yes | Dispute timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | `POST /ar-records/{id}/dispute` |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | AR aging | Exclude disputed amount from collections |

## Ordering Key Convention

**`ordering_key`:** `ar_id`

## Idempotency Key Convention

**`idempotency_key`:** `ar.disputed:{ar_id}`

## Example Payload

```json
{
  "event_type": "ar.disputed",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "ar_id": "uuid",
  "client_id": "uuid",
  "dispute_reason": "Incorrect fee calculation",
  "amount_disputed": "1250.00",
  "occurred_at": "2026-04-14T11:00:00Z"
}
```
