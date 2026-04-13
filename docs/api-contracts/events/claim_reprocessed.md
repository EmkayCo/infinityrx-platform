# Event Contract: `claim.reprocessed`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A claim has been reprocessed, typically after a correction or rule change.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_id` | `UUID` | yes | Claim that was reprocessed |
| `original_disposition` | `str` | yes | Disposition before reprocessing |
| `new_disposition` | `str` | yes | Disposition after reprocessing |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `adjudication-engine` | Emits on claim.reprocessed |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** claim_id

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
    "event_id": "dc01e088-0142-4d9b-8c82-a4ca6182181f",
    "event_type": "claim.reprocessed",
    "schema_version": "1.0",
    "tenant_id": "37d32c55-a439-4992-87db-011708769bcf",
    "correlation_id": "69e407d3-e91c-4df7-8f2d-628ec0f7c5fd",
    "source_module": "adjudication-engine",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "claim_id": "67412b33-291f-4463-8b40-e34ad39a52f8",
        "original_disposition": "example_original_disposition",
        "new_disposition": "example_new_disposition"
    }
}
```

---

<!-- populated as modules adopt this event -->
