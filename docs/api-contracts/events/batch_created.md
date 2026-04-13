# Event Contract: `batch.created`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A billing batch has been created and is ready for review.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `batch_id` | `UUID` | yes | Unique batch identifier |
| `tenant_id` | `UUID` | yes | Tenant that owns this batch |
| `claim_count` | `int` | yes | Number of claims in the batch |
| `total_amount` | `str (Decimal)` | yes | Total plan payment amount |
| `period_start` | `str (ISO 8601 date)` | yes | Billing period start |
| `period_end` | `str (ISO 8601 date)` | yes | Billing period end |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Emits on batch.created |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** batch_id — all batch lifecycle events ordered per batch

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** payment_batch:{batch_id} — business-level dedup

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "891d1fc4-ae14-497a-9c72-7bda1d38f91d",
    "event_type": "batch.created",
    "schema_version": "1.0",
    "tenant_id": "5b806416-7ab8-4bd2-a6db-d1a9735e8812",
    "correlation_id": "bd93f814-2ce1-443a-94b2-3ff2ea79f6c3",
    "source_module": "billing",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "batch_id": "dca4ba52-8fdf-4eda-8a92-68964248060b",
        "tenant_id": "e9604f03-853d-4dae-b6e6-f007f648dfad",
        "claim_count": 1,
        "total_amount": "99.99",
        "period_start": "2026-04-12",
        "period_end": "2026-04-12"
    }
}
```

---

<!-- populated as modules adopt this event -->
