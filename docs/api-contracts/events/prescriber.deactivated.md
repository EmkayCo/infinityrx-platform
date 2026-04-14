# Event Contract: `prescriber.deactivated`

**Schema version:** 1.0
**Status:** Active

---

## Description

A prescriber NPI has been deactivated (NPPES deactivation, voluntary surrender, or administrative action).

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `npi` | `str` | yes | 10-digit NPI |
| `reason` | `str` | yes | Reason for deactivation |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `prescriber-directory` | On NPI deactivation |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** NPI

---

## Idempotency Key Convention

**`idempotency_key`:** `prescriber:{npi}:deactivated`

---

## Example Payload

```json
{
    "event_type": "prescriber.deactivated",
    "schema_version": "1.0",
    "source_module": "prescriber-directory",
    "ordering_key": "1234567890",
    "idempotency_key": "prescriber:1234567890:deactivated",
    "payload": {
        "npi": "1234567890",
        "reason": "voluntary"
    }
}
```
