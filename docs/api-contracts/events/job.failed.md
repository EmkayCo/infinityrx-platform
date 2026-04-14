# Event Contract: `job.failed`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A scheduled or on-demand job has failed.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `job_id` | `UUID` | yes | Job definition identifier |
| `job_run_id` | `UUID` | yes | This specific run identifier |
| `job_type` | `str` | yes | Type/name of the job |
| `error_message` | `str` | yes | Failure reason |
| `items_failed` | `int` | no | Number of items that failed |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `core-platform` | Emits on job.failed |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** job_id

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** job_run:{job_run_id}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "25f60fa3-6c41-4e8d-86c4-851a82d8bb83",
    "event_type": "job.failed",
    "schema_version": "1.0",
    "tenant_id": "be0d1d68-2545-4da6-aeb4-6c8a9fbe13f3",
    "correlation_id": "52838d9c-5db9-4a96-a5b9-28bc310af61b",
    "source_module": "core-platform",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "job_id": "a432b62f-104c-4d77-b57c-d2cdbdba8713",
        "job_run_id": "8c92f02b-8936-4b76-9ca2-94553d4f1070",
        "job_type": "example_job_type",
        "error_message": "example_error_message",
        "items_failed": 1
    }
}
```

---

<!-- populated as modules adopt this event -->
