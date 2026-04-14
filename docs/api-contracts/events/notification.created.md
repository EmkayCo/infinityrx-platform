# Event Contract: `notification.created`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A notification has been created and is ready for delivery.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `notification_id` | `UUID` | yes | Unique notification identifier |
| `user_id` | `UUID` | yes | Recipient user |
| `notification_type` | `str` | yes | Type of notification |
| `severity` | `str` | yes | info | warning | critical |
| `title` | `str` | yes | Notification title |
| `message` | `str` | yes | Notification body |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `core-platform` | Emits on notification.created |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** None — notifications are independent

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** notification:{notification_id}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "8b3ed6c6-e687-45eb-97d1-144b5472bf71",
    "event_type": "notification.created",
    "schema_version": "1.0",
    "tenant_id": "633b71ed-222c-4622-9eca-fc2f2df9d022",
    "correlation_id": "32379601-a482-41a9-b14f-cc0e6b7078cd",
    "source_module": "core-platform",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "notification_id": "ae872a9d-7d11-4b87-8e2d-d7f8c18e19e0",
        "user_id": "a3497efc-bcea-4839-90b8-9e567d61225b",
        "notification_type": "example_notification_type",
        "severity": "example_severity",
        "title": "example_title",
        "message": "example_message"
    }
}
```

---

<!-- populated as modules adopt this event -->
