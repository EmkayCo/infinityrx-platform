# Event Contract: `batch.released`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A billing batch has been approved and released for payment processing.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `batch_id` | `UUID` | yes | Batch that was released |
| `released_by` | `UUID` | yes | User who released the batch |
| `released_at` | `str (ISO 8601)` | yes | Timestamp of release |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Emits on batch.released |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** batch_id

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** batch_release:{batch_id}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "4de87d70-a3b7-45ac-bce9-360a07fc678a",
    "event_type": "batch.released",
    "schema_version": "1.0",
    "tenant_id": "0f579b26-0911-413f-9bc4-d0e547587fd7",
    "correlation_id": "eed983e9-85d6-4f50-8bc3-621d4f4dad9b",
    "source_module": "billing",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "batch_id": "7b069c4c-97b0-424c-97ca-89f133536eb3",
        "released_by": "b37f26ef-0430-4e8a-a2cb-1008ecfac85f",
        "released_at": "2026-04-12T10:30:00Z"
    }
}
```

---

<!-- populated as modules adopt this event -->
