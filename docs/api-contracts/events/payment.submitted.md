# Event Contract: `payment.submitted`

**Schema version:** 1.0
**Status:** Active

---

## Description

A payment submission has been accepted by the clearinghouse vendor.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `str` | yes | Tenant context |
| `submission_id` | `str` | yes | Submission record ID |
| `billing_payment_batch_id` | `str` | yes | Originating billing batch |
| `vendor_reference` | `str or null` | no | Clearinghouse confirmation reference |
| `total_amount` | `str (Decimal)` | yes | Submitted total |
| `payment_count` | `int` | yes | Number of payments submitted |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `payment-processing` | Vendor API confirms submission accepted |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | status update | Update batch status to `submitted` |

---

## Ordering Key Convention

**`ordering_key`:** `submission_id`

## Idempotency Key Convention

**`idempotency_key`:** `payment.submitted:{submission_id}`

---

## Example Payload

```json
{
  "event_type": "payment.submitted",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "submission_id": "sub-uuid",
  "billing_payment_batch_id": "batch-uuid",
  "vendor_reference": "CLH-REF-20260414",
  "total_amount": "125000.00",
  "payment_count": 842
}
```
