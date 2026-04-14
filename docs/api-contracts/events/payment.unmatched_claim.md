# Event Contract: `payment.unmatched_claim`

**Schema version:** 1.0
**Status:** Active

## Description

An 835 remittance advice contains a claim that could not be matched to any
outstanding AP record. Requires manual reconciliation.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `batch_id` | `UUID` | yes | 835 batch containing the claim |
| `auth_number` | `str` | yes | Unmatched authorization number |
| `amount` | `str (Decimal)` | yes | Claim amount in remittance |
| `occurred_at` | `str (ISO-8601)` | yes | Detection timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `edi-compliance` | 835 auto-posting fails to match a claim line |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | unmatched payment queue | Add to manual reconciliation queue |

## Ordering Key Convention

**`ordering_key`:** `auth_number`

## Idempotency Key Convention

**`idempotency_key`:** `payment.unmatched_claim:{batch_id}:{auth_number}`

## Example Payload

```json
{
  "event_type": "payment.unmatched_claim",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "batch_id": "uuid",
  "auth_number": "RX123456789",
  "amount": "42.50",
  "occurred_at": "2026-04-14T04:05:00Z"
}
```
