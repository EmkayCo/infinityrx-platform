# Event Contract: `claim.submitted`

**Schema version:** 1.0  
**Status:** Active

---

## Description

A pharmacy claim has been submitted for adjudication.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_id` | `UUID` | yes | Unique identifier for the claim |
| `member_id` | `UUID` | yes | Member submitting the claim |
| `pharmacy_npi` | `str` | yes | NPI of the dispensing pharmacy |
| `ndc` | `str` | yes | 11-digit National Drug Code |
| `date_of_service` | `str (ISO 8601 date)` | yes | Date the drug was dispensed |
| `quantity_dispensed` | `str (Decimal)` | yes | Quantity dispensed |
| `days_supply` | `int` | yes | Days supply of the dispensed drug |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `adjudication-engine` | Emits on claim.submitted |

## Consumers

<!-- populated as modules adopt this event -->
| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** claim_id — ensures status transitions for the same claim are ordered

Consumers must not assume messages arrive in order unless they share the same `ordering_key`.
The event bus shards queues by `hash(ordering_key) % N_SHARDS` (default N=8).

---

## Idempotency Key Convention

**`idempotency_key`:** str(event_id) — default (each submission is unique)

Consumers must use `idempotent_handler(store, consumer_name=..., ttl_seconds=86400)`
to prevent duplicate processing.  The idempotency key is scoped per consumer, so
multiple consumers can each process the same event independently.

---

## Example Payload

```json
{
    "event_id": "f7f824c0-324c-4e1a-b1c1-86ab1092f57f",
    "event_type": "claim.submitted",
    "schema_version": "1.0",
    "tenant_id": "fa4d23f4-107a-483b-9f1c-cfa0c1ce5d0a",
    "correlation_id": "61292e1b-b20e-4d73-90ee-fd7f0f06b7af",
    "source_module": "adjudication-engine",
    "idempotency_key": "example-key",
    "ordering_key": null,
    "timestamp": "2026-04-12T10:30:00Z",
    "payload": {
        "claim_id": "3abd24f0-9490-43f2-be3f-f21fe75d6670",
        "member_id": "be9505a5-9274-4615-b2c0-a8364f7422c7",
        "pharmacy_npi": "example_pharmacy_npi",
        "ndc": "example_ndc",
        "date_of_service": "2026-04-12",
        "quantity_dispensed": "99.99",
        "days_supply": 1
    }
}
```

---

<!-- populated as modules adopt this event -->
