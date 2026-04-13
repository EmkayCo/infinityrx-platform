# Event Contract: `member.enrolled`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A new member has been enrolled in a benefit plan.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `member_id` | `UUID` | yes | Unique member identifier |
| `plan_id` | `UUID` | yes | Benefit plan the member enrolled in |
| `effective_date` | `str (ISO 8601 date)` | yes | Coverage effective date |
| `group_id` | `UUID` | no | Employer group if applicable |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `member-management` | Emits on member.enrolled |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** member_id — ensures enrollment/termination events are ordered

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** member_enroll:{member_id}:{effective_date}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "217bcecf-d2b6-419d-8646-ccb4e58aeb64",
    "event_type": "member.enrolled",
    "schema_version": "1.0",
    "tenant_id": "bd0bf94d-4e30-4e53-bd1f-d2ccc784ff88",
    "correlation_id": "07de9992-a6d2-40bf-9a9d-6329eb44df9e",
    "source_module": "member-management",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "member_id": "e343460f-c07e-4dcb-8950-868ded80ecaa",
        "plan_id": "4733bce7-33c7-4bf2-ae1b-57d108b83b95",
        "effective_date": "2026-04-12",
        "group_id": "30a37d1c-2817-41f6-9188-e9ce86cf4bc2"
    }
}
```

---

<!-- populated as modules adopt this event -->
