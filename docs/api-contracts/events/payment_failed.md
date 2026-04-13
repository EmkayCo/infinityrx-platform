# Event Contract: `payment.failed`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A payment attempt has failed before settlement.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `payment_id` | `UUID` | yes | Payment that failed |
| `failure_reason` | `str` | yes | Failure description |
| `failed_at` | `str (ISO 8601)` | yes | Failure timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `payment-processing` | Emits on payment.failed |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** payment_batch_id

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** str(event_id) — default

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "6a7b8830-d7ce-47dc-a9fc-3aff77554132",
    "event_type": "payment.failed",
    "schema_version": "1.0",
    "tenant_id": "9eb3022b-2edf-43d1-9f3d-1094448db3e1",
    "correlation_id": "17f5c9d9-0b97-4f1c-8e25-15a0c310b8be",
    "source_module": "payment-processing",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "payment_id": "99185727-7390-43d7-bd0c-da1d3c8568ba",
        "failure_reason": "example_failure_reason",
        "failed_at": "2026-04-12T10:30:00Z"
    }
}
```

---

<!-- populated as modules adopt this event -->
