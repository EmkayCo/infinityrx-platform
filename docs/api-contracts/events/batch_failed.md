# Event Contract: `batch.failed`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A billing batch has failed processing and requires investigation.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `batch_id` | `UUID` | yes | Batch that failed |
| `failure_reason` | `str` | yes | Human-readable failure description |
| `failed_at` | `str (ISO 8601)` | yes | Timestamp of failure |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Emits on batch.failed |

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

**`idempotency_key`:** str(event_id) — default

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "79510383-21a7-4bbf-9438-92b5b4c21c52",
    "event_type": "batch.failed",
    "schema_version": "1.0",
    "tenant_id": "4ec2c902-c5d1-49ce-8618-6ed376bb0bc8",
    "correlation_id": "8977c5c8-53f1-4b54-9803-476e49df704d",
    "source_module": "billing",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "batch_id": "a2d55550-37dd-492a-a072-c26ad635af43",
        "failure_reason": "example_failure_reason",
        "failed_at": "2026-04-12T10:30:00Z"
    }
}
```

---

<!-- populated as modules adopt this event -->
