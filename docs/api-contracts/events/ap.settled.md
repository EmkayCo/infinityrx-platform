# Event Contract: `ap.settled`

**Schema version:** 1.0
**Status:** Active

## Description

An accounts-payable record has been settled — the payment has cleared the
bank and funds have been disbursed.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `ap_id` | `UUID` | yes | AP record settled |
| `settlement_reference` | `str` | yes | Bank settlement reference |
| `settlement_date` | `str (ISO-8601 date)` | yes | Date funds cleared |
| `amount` | `str (Decimal)` | yes | Settled amount |
| `occurred_at` | `str (ISO-8601)` | yes | Settlement timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Settlement recorded for AP record |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reclaimrx` | `handle_ap_settled` | Update recovery status on settlement |

## Ordering Key Convention

**`ordering_key`:** `ap_id`

## Idempotency Key Convention

**`idempotency_key`:** `ap.settled:{ap_id}:{settlement_reference}`

## Example Payload

```json
{
  "event_type": "ap.settled",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "ap_id": "uuid",
  "settlement_reference": "SET-20260414-001",
  "settlement_date": "2026-04-14",
  "amount": "45.00",
  "occurred_at": "2026-04-14T16:00:00Z"
}
```
