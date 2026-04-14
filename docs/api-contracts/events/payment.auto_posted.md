# Event Contract: `payment.auto_posted`

**Schema version:** 1.0
**Status:** Active

## Description

An 835 remittance advice has been automatically posted to the billing system,
matching the payment to outstanding AP records.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `batch_id` | `UUID` | yes | 835 batch processed |
| `matched_count` | `int` | yes | Number of claims matched |
| `unmatched_count` | `int` | yes | Number of claims unmatched |
| `total_posted` | `str (Decimal)` | yes | Total amount posted |
| `occurred_at` | `str (ISO-8601)` | yes | Posting completion timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `edi-compliance` | 835 auto-posting job completes |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | reconciliation | Mark AP records as settled |

## Ordering Key Convention

**`ordering_key`:** `batch_id`

## Idempotency Key Convention

**`idempotency_key`:** `payment.auto_posted:{batch_id}`

## Example Payload

```json
{
  "event_type": "payment.auto_posted",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "batch_id": "uuid",
  "matched_count": 1240,
  "unmatched_count": 8,
  "total_posted": "520000.00",
  "occurred_at": "2026-04-14T04:00:00Z"
}
```
