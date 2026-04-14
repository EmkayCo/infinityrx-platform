# Event Contract: `billing.journal_entries`

**Schema version:** 1.0
**Status:** Active

## Description

A batch of hash-chained journal entries has been written to the billing
financial ledger. Published to allow downstream reporting to maintain
synchronized financial snapshots.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `period` | `str` | yes | Accounting period (e.g., `2026-04`) |
| `entry_count` | `int` | yes | Number of journal entries in batch |
| `total_debit` | `str (Decimal)` | yes | Total debit amount |
| `total_credit` | `str (Decimal)` | yes | Total credit amount |
| `occurred_at` | `str (ISO-8601)` | yes | Batch write timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Journal entries flushed to ledger |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | `handle_billing_journal_entry` | Update financial reporting snapshots |

## Ordering Key Convention

**`ordering_key`:** `tenant_id`

## Idempotency Key Convention

**`idempotency_key`:** `billing.journal_entries:{period}:{occurred_at}`

## Example Payload

```json
{
  "event_type": "billing.journal_entries",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "period": "2026-04",
  "entry_count": 1248,
  "total_debit": "525000.00",
  "total_credit": "525000.00",
  "occurred_at": "2026-04-14T23:59:59Z"
}
```
