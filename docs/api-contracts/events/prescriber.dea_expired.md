# Event Contract: `prescriber.dea_expired`

**Schema version:** 1.0
**Status:** Active

---

## Description

A prescriber's DEA registration has expired. Downstream systems (adjudication, prior-auth) should reject controlled substance prescriptions from this prescriber.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `npi` | `str` | yes | 10-digit NPI |
| `expiry_date` | `str` | yes | ISO 8601 date of DEA expiration |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `prescriber-directory` | Emitted by credential monitoring job when DEA is expired |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** NPI

---

## Idempotency Key Convention

**`idempotency_key`:** `prescriber:{npi}:dea_expired`

---

## Example Payload

```json
{
    "event_type": "prescriber.dea_expired",
    "schema_version": "1.0",
    "source_module": "prescriber-directory",
    "ordering_key": "1234567890",
    "idempotency_key": "prescriber:1234567890:dea_expired",
    "payload": {
        "npi": "1234567890",
        "expiry_date": "2026-03-01"
    }
}
```
