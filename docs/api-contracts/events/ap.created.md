# Event Contract: `ap.created`

**Schema version:** 1.0
**Status:** Active

## Description

An accounts-payable record has been created in the billing module for a
routed claim, initiating the payment life-cycle.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `ap_id` | `UUID` | yes | AP record ID |
| `claim_id` | `UUID` | yes | Source claim |
| `payment_route` | `str` | yes | Payment route for this AP record |
| `amount` | `str (Decimal)` | yes | AP amount |
| `occurred_at` | `str (ISO-8601)` | yes | AP creation timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Claim routed and AP record created |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reclaimrx` | `handle_ap_created` | Record AP creation in recovery context |

## Ordering Key Convention

**`ordering_key`:** `claim_id`

## Idempotency Key Convention

**`idempotency_key`:** `ap.created:{ap_id}`

## Example Payload

```json
{
  "event_type": "ap.created",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "ap_id": "uuid",
  "claim_id": "uuid",
  "payment_route": "ACH",
  "amount": "45.00",
  "occurred_at": "2026-04-14T10:00:00Z"
}
```
