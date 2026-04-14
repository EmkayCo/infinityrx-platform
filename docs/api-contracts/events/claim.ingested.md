# Event Contract: `claim.ingested`

**Schema version:** 1.0
**Status:** Active

---

## Description

A pharmacy claim has been received by the billing module and accepted for
routing and AP record creation.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant that owns this claim |
| `claim_id` | `UUID` | yes | Internal claim identifier |
| `auth_number` | `str` | yes | NCPDP authorization number |
| `claim_type` | `str` | yes | Type of claim (e.g., `pharmacy`, `compound`) |
| `net_amount` | `str (Decimal)` | yes | Net reimbursement amount |
| `client_id` | `UUID` | yes | Plan sponsor / client |
| `program_id` | `UUID` | yes | Benefit program |
| `occurred_at` | `str (ISO-8601)` | yes | When the ingestion occurred |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Claim accepted and routed |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reclaimrx` | `handle_claim_adjudicated` | Evaluate for FWA |
| `reporting` | dashboard update | Increment claim count metrics |

---

## Ordering Key Convention

**`ordering_key`:** `claim_id`

## Idempotency Key Convention

**`idempotency_key`:** `claim.ingested:{claim_id}`

---

## Example Payload

```json
{
  "event_type": "claim.ingested",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "claim_id": "uuid",
  "auth_number": "123456789",
  "claim_type": "pharmacy",
  "net_amount": "45.00",
  "client_id": "uuid",
  "program_id": "uuid",
  "occurred_at": "2026-04-14T10:00:00Z"
}
```
