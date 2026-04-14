# Event Contract: `claim.reversed`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A previously adjudicated claim has been reversed.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_id` | `UUID` | yes | Claim that was reversed |
| `reversal_reason` | `str` | yes | Reason for the reversal |
| `original_paid_amount` | `str (Decimal)` | no | Original plan payment being reversed |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `adjudication-engine` | Emits on claim.reversed |

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
    "event_id": "c27e330d-458e-44e5-8ca7-dc4be48f630c",
    "event_type": "claim.reversed",
    "schema_version": "1.0",
    "tenant_id": "f8abc5c7-f231-445a-8bef-84ce98cdd860",
    "correlation_id": "7ba97f2f-8ce7-4c4f-8cec-4a61b3619c31",
    "source_module": "adjudication-engine",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "claim_id": "2f67daeb-cc67-4c46-b161-b1c61f172d9f",
        "reversal_reason": "example_reversal_reason",
        "original_paid_amount": "99.99"
    }
}
```

---

<!-- populated as modules adopt this event -->
