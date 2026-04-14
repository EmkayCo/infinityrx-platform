# Event Contract: `prescriber.created`

**Schema version:** 1.0
**Status:** Active

---

## Description

A new prescriber NPI record has been registered in the prescriber directory.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `npi` | `str` | yes | 10-digit NPI |
| `entity_type` | `str` | yes | 1 = individual, 2 = organization |
| `display_name` | `str` | yes | Human-readable display name |
| `primary_taxonomy_code` | `str` | no | NUCC taxonomy code |
| `primary_specialty` | `str` | no | Simplified specialty label |
| `practice_state` | `str` | no | Two-letter state code |
| `status` | `str` | yes | active \| inactive \| deactivated |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `prescriber-directory` | On new NPI upsert (INSERT) |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** NPI (prescriber NPI string)

Guarantees ordered delivery of all events for a given prescriber.

---

## Idempotency Key Convention

**`idempotency_key`:** `prescriber:{npi}:created`

---

## Example Payload

```json
{
    "event_type": "prescriber.created",
    "schema_version": "1.0",
    "tenant_id": "a5235573-3f59-45f4-acf7-79da6e8c1d4c",
    "source_module": "prescriber-directory",
    "ordering_key": "1234567890",
    "idempotency_key": "prescriber:1234567890:created",
    "payload": {
        "npi": "1234567890",
        "entity_type": "1",
        "display_name": "JOHN SMITH MD",
        "primary_taxonomy_code": "207Q00000X",
        "primary_specialty": "family medicine",
        "practice_state": "IL",
        "status": "active"
    }
}
```
