# Event Contract: `report.generated`

**Schema version:** 1.0
**Status:** Active

---

## Description

A report run has completed successfully and the output file is ready for
delivery or download.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `report_id` | `UUID` | yes | Report definition ID |
| `run_id` | `UUID` | yes | Report run ID |
| `report_name` | `str` | yes | Human-readable report name |
| `output_format` | `str` | yes | `excel`, `pdf`, `json`, `csv` |
| `row_count` | `int` | no | Number of records in the output |
| `occurred_at` | `str (ISO-8601)` | yes | Completion timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reporting` | `POST /reports/{id}/run` completes |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(notification service)* | — | Notify requesting user that report is ready |

---

## Ordering Key Convention

**`ordering_key`:** `report_id`

## Idempotency Key Convention

**`idempotency_key`:** `report.generated:{run_id}`

---

## Example Payload

```json
{
  "event_type": "report.generated",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "report_id": "uuid",
  "run_id": "uuid",
  "report_name": "Q1 2026 Billing Summary",
  "output_format": "excel",
  "row_count": 15420,
  "occurred_at": "2026-04-14T06:00:00Z"
}
```
