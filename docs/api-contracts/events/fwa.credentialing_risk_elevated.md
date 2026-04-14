# Event Contract: `fwa.credentialing_risk_elevated`

**Schema version:** 1.0
**Status:** Active

## Description

A pharmacy or prescriber's credentialing risk score has been elevated based
on FWA pattern detection during the credentialing review process.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `entity_type` | `str` | yes | `pharmacy` or `prescriber` |
| `entity_id` | `str` | yes | NPI or other entity identifier |
| `risk_factors` | `list[str]` | yes | Identified risk factor codes |
| `risk_score` | `int` | yes | Composite risk score 0–100 |
| `occurred_at` | `str (ISO-8601)` | yes | Detection timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Credentialing-phase FWA screening detects risk factors |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `pharmacy-directory` | (planned) | Escalate credentialing review |
| `prescriber-directory` | (planned) | Flag prescriber for enhanced review |

## Ordering Key Convention

**`ordering_key`:** `entity_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.credentialing_risk_elevated:{entity_type}:{entity_id}`

## Example Payload

```json
{
  "event_type": "fwa.credentialing_risk_elevated",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "entity_type": "pharmacy",
  "entity_id": "1234567890",
  "risk_factors": ["OIG_EXCLUSION_HISTORY", "PRIOR_TERMINATION"],
  "risk_score": 85,
  "occurred_at": "2026-04-14T10:00:00Z"
}
```
