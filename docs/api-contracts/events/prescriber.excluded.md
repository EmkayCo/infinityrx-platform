# Event Contract: `prescriber.excluded`

**Schema version:** 1.0
**Status:** Active

---

## Description

A prescriber has been marked as excluded based on an OIG, SAM, or OFAC match. All active relationships with this prescriber should be terminated.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `npi` | `str` | yes | 10-digit NPI |
| `exclusion_type` | `str` | yes | OIG \| SAM \| OFAC |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `prescriber-directory` | On `exclusion.match_found` consumer marking prescriber excluded |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** NPI

---

## Idempotency Key Convention

**`idempotency_key`:** `prescriber:{npi}:excluded`

---

## Example Payload

```json
{
    "event_type": "prescriber.excluded",
    "schema_version": "1.0",
    "source_module": "prescriber-directory",
    "ordering_key": "1234567890",
    "idempotency_key": "prescriber:1234567890:excluded",
    "payload": {
        "npi": "1234567890",
        "exclusion_type": "OIG"
    }
}
```
