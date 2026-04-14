# Event Contract: `fwa.payment_hold_placed`

**Schema version:** 1.0
**Status:** Active

---

## Description

An FWA investigation has placed a payment hold on a payment batch, preventing
submission until the hold is released or the investigation is resolved.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `payment_batch_id` | `UUID` | yes | Batch being held |
| `investigation_id` | `str` | yes | Investigation that triggered the hold |
| `reason` | `str` | yes | Hold reason |
| `occurred_at` | `str (ISO-8601)` | yes | Hold placement timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | `POST /holds` accepted for a payment batch |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `payment-processing` | `handle_fwa_hold_placed` | Prevent NACHA submission for held batch |

---

## Ordering Key Convention

**`ordering_key`:** `payment_batch_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.payment_hold_placed:{payment_batch_id}:{investigation_id}`

---

## Example Payload

```json
{
  "event_type": "fwa.payment_hold_placed",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "payment_batch_id": "uuid",
  "investigation_id": "inv-uuid",
  "reason": "Pharmacy under active FWA investigation",
  "occurred_at": "2026-04-14T10:30:00Z"
}
```
