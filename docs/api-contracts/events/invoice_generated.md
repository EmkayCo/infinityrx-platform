# Event Contract: `invoice.generated`

**Schema version:** 1.0  
**Status:** Active

---

## Description

An invoice has been generated for a client/employer group.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `invoice_id` | `UUID` | yes | Unique invoice identifier |
| `client_id` | `UUID` | yes | Client/employer group being invoiced |
| `amount_due` | `str (Decimal)` | yes | Total amount due |
| `due_date` | `str (ISO 8601 date)` | yes | Payment due date |
| `period_start` | `str (ISO 8601 date)` | yes | Billing period start |
| `period_end` | `str (ISO 8601 date)` | yes | Billing period end |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Emits on invoice.generated |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** invoice_id

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** invoice:{invoice_id}

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "c771275a-b64a-4a5d-af64-85b4e648049b",
    "event_type": "invoice.generated",
    "schema_version": "1.0",
    "tenant_id": "da04d21f-3a02-4126-a362-07fe3f7609d2",
    "correlation_id": "0e220fb1-66a6-4d3f-8f1a-ac172266675f",
    "source_module": "billing",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "invoice_id": "6f51fa37-23b9-4f8d-b7a8-247970aa77a8",
        "client_id": "bf57c4b3-5804-49e4-b117-b82fd5a56e1e",
        "amount_due": "99.99",
        "due_date": "2026-04-12",
        "period_start": "2026-04-12",
        "period_end": "2026-04-12"
    }
}
```

---

<!-- populated as modules adopt this event -->
