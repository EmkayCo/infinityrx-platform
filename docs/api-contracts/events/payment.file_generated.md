# Event Contract: `payment.file_generated`

**Schema version:** 1.0
**Status:** Active

---

## Description

A NACHA ACH file or check file has been generated and staged for SFTP
delivery to the clearinghouse.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `str` | yes | Tenant context |
| `submission_id` | `str` | yes | Submission record ID |
| `billing_payment_batch_id` | `str` | yes | Originating billing batch |
| `payment_count` | `int` | yes | Number of payment entries in file |
| `total_amount` | `str (Decimal)` | yes | Total dollar amount in file |
| `file_format` | `str or null` | no | `NACHA`, `CHECK`, etc. |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `payment-processing` | File written to staging area |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | (planned) | Update batch status to `file_generated` |

---

## Ordering Key Convention

**`ordering_key`:** `submission_id`

## Idempotency Key Convention

**`idempotency_key`:** `payment.file_generated:{submission_id}`

---

## Example Payload

```json
{
  "event_type": "payment.file_generated",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "submission_id": "sub-uuid",
  "billing_payment_batch_id": "batch-uuid",
  "payment_count": 842,
  "total_amount": "125000.00",
  "file_format": "NACHA"
}
```
