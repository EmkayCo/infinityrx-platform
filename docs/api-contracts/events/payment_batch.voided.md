# Event Contract: `payment_batch.voided`

**Schema version:** 1.0
**Status:** Active

---

## Description

A payment batch has been voided before submission. Any NACHA file staging
for this batch should be discarded.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `batch_id` | `UUID` | yes | Batch being voided |
| `batch_number` | `str` | yes | Human-readable reference |
| `reason` | `str or null` | no | Void reason if provided |
| `occurred_at` | `str (ISO-8601)` | yes | Void timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Batch voided via `POST /payment-batches/{id}/void` |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `payment-processing` | hold logic | Cancel staged NACHA file if not yet submitted |

---

## Ordering Key Convention

**`ordering_key`:** `batch_id`

## Idempotency Key Convention

**`idempotency_key`:** `payment_batch.voided:{batch_id}`

---

## Example Payload

```json
{
  "event_type": "payment_batch.voided",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "batch_id": "uuid",
  "batch_number": "BATCH-2026-04-001",
  "reason": "Duplicate batch detected",
  "occurred_at": "2026-04-14T03:00:00Z"
}
```
