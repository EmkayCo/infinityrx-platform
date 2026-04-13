# Event Contract: `member.terminated`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A member's coverage has been terminated.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `member_id` | `UUID` | yes | Member whose coverage was terminated |
| `termination_date` | `str (ISO 8601 date)` | yes | Coverage end date |
| `termination_reason` | `str` | no | voluntary | involuntary | non_payment |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `member-management` | Emits on member.terminated |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** member_id

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** member_term:{member_id}:{termination_date}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "6b425d65-42b9-49d7-b28a-7fceb4db23fa",
    "event_type": "member.terminated",
    "schema_version": "1.0",
    "tenant_id": "3beece73-3745-4b58-9cd7-a260cba0f621",
    "correlation_id": "5fa9f50b-47d9-45a0-bd90-fdaa068a73fc",
    "source_module": "member-management",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "member_id": "dcabda4f-e08b-49cf-90ee-8ad8f97602ff",
        "termination_date": "2026-04-12",
        "termination_reason": "example_termination_reason"
    }
}
```

---

<!-- populated as modules adopt this event -->
