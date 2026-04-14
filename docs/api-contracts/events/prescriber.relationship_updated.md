# Event Contract: `prescriber.relationship_updated`

**Schema version:** 1.0
**Status:** Active

---

## Description

A prescriber-pharmacy relationship volume record has been updated. Published when a `claim.ingested` event increments the claim count for a prescriber-pharmacy pair in a given period month.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prescriber_npi` | `str` | yes | 10-digit prescriber NPI |
| `pharmacy_npi` | `str` | yes | 10-digit pharmacy NPI |
| `period_month` | `str` | yes | YYYY-MM billing period |
| `claim_count` | `int` | yes | Updated total claim count for this pair/period |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `prescriber-directory` | After claim volume update for a prescriber-pharmacy pair |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | - | - |

---

## Ordering Key Convention

**`ordering_key`:** prescriber NPI

---

## Idempotency Key Convention

**`idempotency_key`:** `prescriber:{npi}:relationship_updated:{pharmacy_npi}:{period_month}`

---

## Example Payload

```json
{
    "event_type": "prescriber.relationship_updated",
    "schema_version": "1.0",
    "source_module": "prescriber-directory",
    "ordering_key": "1234567890",
    "idempotency_key": "prescriber:1234567890:relationship_updated:0987654321:2026-03",
    "payload": {
        "prescriber_npi": "1234567890",
        "pharmacy_npi": "0987654321",
        "period_month": "2026-03",
        "claim_count": 42
    }
}
```
