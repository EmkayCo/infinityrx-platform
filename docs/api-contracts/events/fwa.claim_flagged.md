# Event Contract: `fwa.claim_flagged`

**Schema version:** 1.0
**Status:** Active

---

## Description

The FWA detection engine has flagged a claim as potentially fraudulent, wasteful,
or abusive based on rule evaluation or ML scoring.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `flagged_claim_id` | `str` | yes | Internal flagged-claim record ID |
| `claim_id` | `str or null` | no | Source claim ID if available |
| `rule_code` | `str` | yes | FWA rule or model code that triggered |
| `severity` | `str` | yes | `low`, `medium`, `high`, `critical` |
| `risk_score` | `int` | yes | Composite risk score 0–100 |
| `pharmacy_npi` | `str` | yes | NPI of dispensing pharmacy |
| `action_taken` | `str` | yes | `flagged`, `held`, `blocked` |
| `occurred_at` | `str (ISO-8601)` | yes | Detection timestamp |
| `correlation_id` | `str or null` | no | Tracing correlation ID |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Rule or ML model detects FWA pattern |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | `handle_fwa_claim_flagged` | Increment FWA dashboard metrics |
| `billing` | (planned) hold routing | Block payment if severity = critical |

---

## Ordering Key Convention

**`ordering_key`:** `claim_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.claim_flagged:{flagged_claim_id}`

---

## Example Payload

```json
{
  "event_type": "fwa.claim_flagged",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "flagged_claim_id": "fc-uuid",
  "claim_id": "claim-uuid",
  "rule_code": "EXCESSIVE_QUANTITY",
  "severity": "high",
  "risk_score": 78,
  "pharmacy_npi": "1234567890",
  "action_taken": "flagged",
  "occurred_at": "2026-04-14T10:05:00Z",
  "correlation_id": "corr-uuid"
}
```
