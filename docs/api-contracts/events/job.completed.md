# Event Contract: `job.completed`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A scheduled or on-demand job has completed successfully.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `job_id` | `UUID` | yes | Job definition identifier |
| `job_run_id` | `UUID` | yes | This specific run identifier |
| `job_type` | `str` | yes | Type/name of the job |
| `duration_seconds` | `int` | no | Execution duration |
| `items_processed` | `int` | no | Items successfully processed |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `core-platform` | Emits on job.completed |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** job_id — ensures job lifecycle events are ordered

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
    "event_id": "9d2aa293-e499-47d5-9b49-1503ca915574",
    "event_type": "job.completed",
    "schema_version": "1.0",
    "tenant_id": "44e46c7b-ecab-481e-90b1-204912307f69",
    "correlation_id": "3dfed9f4-86af-4029-94ad-bf7e85c96f3f",
    "source_module": "core-platform",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "job_id": "3a0ce76a-4bf7-43b7-b713-6a26053d7f95",
        "job_run_id": "9e2809b2-bb3a-4a41-ba4d-5e41f315f062",
        "job_type": "example_job_type",
        "duration_seconds": 1,
        "items_processed": 1
    }
}
```

---

<!-- populated as modules adopt this event -->
