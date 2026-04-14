# Event Contract: `fwa.claim_blocked`

**Schema version:** 1.0
**Status:** Active

---

## Description

A claim has been blocked from payment due to a high-confidence FWA rule match.
The claim will not be routed until the block is cleared via investigation.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `claim_id` | `str or null` | no | Source claim ID |
| `auth_number` | `str` | yes | NCPDP authorization number |
| `rule_code` | `str` | yes | Rule that triggered the block |
| `reason` | `str` | yes | Human-readable block reason |
| `occurred_at` | `str (ISO-8601)` | yes | Block timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | High-confidence rule match with `block` action |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | routing hold | Do not route claim to payment |

---

## Ordering Key Convention

**`ordering_key`:** `claim_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.claim_blocked:{auth_number}:{rule_code}`

---

## Example Payload

```json
{
  "event_type": "fwa.claim_blocked",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "claim_id": "claim-uuid",
  "auth_number": "RX123456789",
  "rule_code": "OIG_EXCLUDED_PROVIDER",
  "reason": "Prescriber found on OIG exclusion list",
  "occurred_at": "2026-04-14T10:06:00Z"
}
```
