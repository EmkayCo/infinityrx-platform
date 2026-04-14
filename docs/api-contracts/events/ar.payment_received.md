# Event Contract: `ar.payment_received`

**Schema version:** 1.0
**Status:** Active

---

## Description

A client has made a payment against an accounts-receivable record, reducing
the outstanding balance.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `ar_id` | `UUID` | yes | AR record receiving payment |
| `client_id` | `UUID` | yes | Client who made the payment |
| `amount` | `str (Decimal)` | yes | Payment amount received |
| `payment_date` | `str (ISO-8601 date)` | yes | Date payment was received |
| `outstanding_after` | `str (Decimal)` | yes | Remaining balance after this payment |
| `occurred_at` | `str (ISO-8601)` | yes | Event timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | `POST /ar-records/{id}/payment` processed |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | billing snapshot | Update AR aging metrics |

---

## Ordering Key Convention

**`ordering_key`:** `ar_id`

## Idempotency Key Convention

**`idempotency_key`:** `ar.payment_received:{ar_id}:{payment_date}`

---

## Example Payload

```json
{
  "event_type": "ar.payment_received",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "ar_id": "uuid",
  "client_id": "uuid",
  "amount": "50000.00",
  "payment_date": "2026-04-14",
  "outstanding_after": "0.00",
  "occurred_at": "2026-04-14T15:00:00Z"
}
```
