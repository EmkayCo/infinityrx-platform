# Event Contract: `payment.return_suspicious`

**Schema version:** 1.0
**Status:** Active

---

## Description

An ACH return code has been received that matches a suspicious-return pattern
(e.g., R10 — customer advises not authorized, or high-volume R03/R04). This
event triggers FWA correlation analysis.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `str` | yes | Tenant context |
| `billing_payment_id` | `str` | yes | Payment that was returned |
| `submission_id` | `str` | yes | Originating submission |
| `return_code` | `str` | yes | NACHA return code (e.g., `R10`) |
| `amount` | `str (Decimal)` | yes | Returned amount |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `payment-processing` | Return code matched against suspicious-return pattern list |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reclaimrx` | `handle_payment_return_suspicious` | Correlate with pharmacy FWA profile |

---

## Ordering Key Convention

**`ordering_key`:** `billing_payment_id`

## Idempotency Key Convention

**`idempotency_key`:** `payment.return_suspicious:{billing_payment_id}:{return_code}`

---

## Example Payload

```json
{
  "event_type": "payment.return_suspicious",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "billing_payment_id": "pay-uuid",
  "submission_id": "sub-uuid",
  "return_code": "R10",
  "amount": "4200.00"
}
```
