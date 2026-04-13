# Event Contract: `sftp.delivery_failed`

**Schema version:** 1.0  
**Status:** Active

---

## Description

An SFTP file delivery has failed after retries.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_id` | `UUID` | yes | File that failed to deliver |
| `destination_host` | `str` | yes | SFTP host that was unreachable |
| `attempt_count` | `int` | yes | Number of delivery attempts made |
| `error_message` | `str` | yes | Last error message |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `core-platform` | Emits on sftp.delivery_failed |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** None — delivery failures are independent alerts

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** sftp_delivery:{file_id}:{attempt}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "23d1832a-5a4a-4368-a5fd-07455dec1bae",
    "event_type": "sftp.delivery_failed",
    "schema_version": "1.0",
    "tenant_id": "5d803545-9d36-42eb-9a21-764a4fd3c0c5",
    "correlation_id": "84b4b774-5abe-4846-a98b-606e9c9f8204",
    "source_module": "core-platform",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "file_id": "6ee14bb0-bf3b-4845-8e5a-4f6362720517",
        "destination_host": "example_destination_host",
        "attempt_count": 1,
        "error_message": "example_error_message"
    }
}
```

---

<!-- populated as modules adopt this event -->
