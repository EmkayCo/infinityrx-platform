# Event Contract: `member.eligibility_changed`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A member's eligibility details have changed (plan, copay tier, etc.).

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `member_id` | `UUID` | yes | Member whose eligibility changed |
| `changed_fields` | `list[str]` | yes | Names of fields that changed |
| `effective_date` | `str (ISO 8601 date)` | yes | Date change takes effect |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `member-management` | Emits on member.eligibility_changed |

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

**`idempotency_key`:** str(event_id) — default (each change is distinct)

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "5c363cdc-2885-40f7-89c9-9d202c3827f7",
    "event_type": "member.eligibility_changed",
    "schema_version": "1.0",
    "tenant_id": "83980c30-5418-4448-8056-04bf8e655707",
    "correlation_id": "86c53fea-4392-4c66-bd1a-03b0c9d7e59d",
    "source_module": "member-management",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "member_id": "6dddaddc-b89b-47a0-b85d-a3a29fef7240",
        "changed_fields": [],
        "effective_date": "2026-04-12"
    }
}
```

---

<!-- populated as modules adopt this event -->
