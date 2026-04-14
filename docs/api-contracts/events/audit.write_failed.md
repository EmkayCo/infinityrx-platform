# Event Contract: `audit.write_failed`

**Schema version:** 1.0  
**Status:** Active

---

## Description

The audit log write failed; used to trigger alerts and remediation.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `original_action` | `str` | yes | The audit action that failed to write |
| `entity_type` | `str` | no | Entity type of the failed audit entry |
| `entity_id` | `str` | no | Entity ID of the failed audit entry |
| `error_message` | `str` | yes | Error that caused the write failure |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `core-platform` | Emits on audit.write_failed |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** None — alert events are independent

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
    "event_id": "ab85edda-c17c-47f4-a942-10f01f6e51ca",
    "event_type": "audit.write_failed",
    "schema_version": "1.0",
    "tenant_id": "36518277-d6c2-4981-a339-dfc492913e92",
    "correlation_id": "c733cd74-cb69-4b77-b5c7-4f2736c0d279",
    "source_module": "core-platform",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "original_action": "example_original_action",
        "entity_type": "example_entity_type",
        "entity_id": "example_entity_id",
        "error_message": "example_error_message"
    }
}
```

---

<!-- populated as modules adopt this event -->
