# Event Contract: `ar.written_off`

**Schema version:** 1.0
**Status:** Active

## Description

An accounts-receivable balance has been written off as uncollectible.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `ar_id` | `UUID` | yes | AR record written off |
| `client_id` | `UUID` | yes | Client whose balance was written off |
| `amount` | `str (Decimal)` | yes | Amount written off |
| `reason` | `str` | yes | Write-off reason |
| `occurred_at` | `str (ISO-8601)` | yes | Write-off timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | `POST /ar-records/{id}/write-off` |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | financial reporting | Record write-off in P&L |

## Ordering Key Convention

**`ordering_key`:** `ar_id`

## Idempotency Key Convention

**`idempotency_key`:** `ar.written_off:{ar_id}`

## Example Payload

```json
{
  "event_type": "ar.written_off",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "ar_id": "uuid",
  "client_id": "uuid",
  "amount": "875.00",
  "reason": "Client bankruptcy — Chapter 7",
  "occurred_at": "2026-04-14T12:00:00Z"
}
```
