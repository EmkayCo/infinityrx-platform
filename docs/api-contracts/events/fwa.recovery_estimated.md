# Event Contract: `recovery.estimated`

**Schema version:** 1.0  
**Status:** Active

---

## Description

An estimated recovery amount has been calculated for an anomaly.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `anomaly_id` | `UUID` | yes | Anomaly this estimate is for |
| `estimated_amount` | `str (Decimal)` | yes | Estimated recoverable amount |
| `methodology` | `str` | yes | How the estimate was calculated |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Emits on recovery.estimated |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** anomaly_id

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** recovery:{anomaly_id}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "c92fad95-d0fc-447f-9f63-1cd952320546",
    "event_type": "recovery.estimated",
    "schema_version": "1.0",
    "tenant_id": "aeef2d51-68b3-4945-a21c-54f64a55b614",
    "correlation_id": "b0d28146-c160-452b-8304-7b2422dabaaf",
    "source_module": "reclaimrx",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "anomaly_id": "eecb9ef4-5df3-4dac-a42e-4b32c7ffac7c",
        "estimated_amount": "99.99",
        "methodology": "example_methodology"
    }
}
```

---

<!-- populated as modules adopt this event -->
