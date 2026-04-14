# Event Contract: `claim.classified`

**Schema version:** 1.0
**Status:** Active

---

## Description

The billing routing engine has applied a payment-route decision to an ingested
claim and determined whether it is excluded or a statement-only record.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `claim_id` | `UUID` | yes | Claim being classified |
| `payment_route` | `str or null` | no | Route code (ACH, CHECK, WIRE, CARD) or null if excluded |
| `is_excluded` | `bool` | yes | Whether claim is excluded from payment |
| `is_statement` | `bool` | yes | Whether claim is statement-only (no cash movement) |
| `occurred_at` | `str (ISO-8601)` | yes | Classification timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | After routing rule evaluation |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | — | — |

---

## Ordering Key Convention

**`ordering_key`:** `claim_id`

## Idempotency Key Convention

**`idempotency_key`:** `claim.classified:{claim_id}`

---

## Example Payload

```json
{
  "event_type": "claim.classified",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "claim_id": "uuid",
  "payment_route": "ACH",
  "is_excluded": false,
  "is_statement": false,
  "occurred_at": "2026-04-14T10:01:00Z"
}
```
