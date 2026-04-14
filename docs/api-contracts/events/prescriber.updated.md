# Event Contract: `prescriber.updated`

**Schema version:** 1.0
**Status:** Active

---

## Description

A prescriber's record in the directory has been updated (e.g., address change, taxonomy update, status change from NPPES).

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `npi` | `str` | yes | 10-digit NPI |
| `changes` | `dict` | yes | Map of changed field names to new values |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `prescriber-directory` | On NPPES upsert with differing fields |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** NPI

---

## Idempotency Key Convention

**`idempotency_key`:** `prescriber:{npi}:updated`

---

## Example Payload

```json
{
    "event_type": "prescriber.updated",
    "schema_version": "1.0",
    "source_module": "prescriber-directory",
    "ordering_key": "1234567890",
    "idempotency_key": "prescriber:1234567890:updated",
    "payload": {
        "npi": "1234567890",
        "changes": {
            "practice_state": "TX",
            "practice_city": "DALLAS"
        }
    }
}
```
