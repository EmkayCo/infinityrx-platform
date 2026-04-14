# Event Contract: `fwa.payment_hold_released`

**Schema version:** 1.0
**Status:** Active

---

## Description

An FWA payment hold has been released, allowing the payment batch to proceed
to submission.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `payment_batch_id` | `UUID` | yes | Batch being released |
| `investigation_id` | `str` | yes | Investigation that placed the hold |
| `released_by` | `str` | no | User or process that released the hold |
| `occurred_at` | `str (ISO-8601)` | yes | Release timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | `DELETE /holds/{id}` with reason |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `payment-processing` | `handle_fwa_hold_released` | Allow NACHA submission for batch |

---

## Ordering Key Convention

**`ordering_key`:** `payment_batch_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.payment_hold_released:{payment_batch_id}:{investigation_id}`

---

## Example Payload

```json
{
  "event_type": "fwa.payment_hold_released",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "payment_batch_id": "uuid",
  "investigation_id": "inv-uuid",
  "released_by": "investigator@plan.com",
  "occurred_at": "2026-04-14T15:30:00Z"
}
```
