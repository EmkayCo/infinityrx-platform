# Event Contract: `budget.alert_fired`

**Schema version:** 1.0
**Status:** Active

---

## Description

A program budget threshold has been crossed, triggering an alert notification.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `program_budget_id` | `UUID` | yes | Budget record that fired |
| `program_id` | `UUID` | yes | Associated program |
| `alert_type` | `str` | yes | Threshold type (e.g., `pct_75`, `pct_90`, `pct_100`) |
| `severity` | `str` | yes | `warning`, `critical` |
| `message` | `str` | yes | Human-readable alert description |
| `occurred_at` | `str (ISO-8601)` | yes | Alert timestamp |

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | Budget utilization crosses a configured threshold |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | auto-report trigger | Generate budget summary report |
| *(notification service)* | — | Send alert to configured recipients |

---

## Ordering Key Convention

**`ordering_key`:** `program_budget_id`

## Idempotency Key Convention

**`idempotency_key`:** `budget.alert_fired:{program_budget_id}:{alert_type}`

---

## Example Payload

```json
{
  "event_type": "budget.alert_fired",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "program_budget_id": "uuid",
  "program_id": "uuid",
  "alert_type": "pct_90",
  "severity": "critical",
  "message": "Program PGMX has consumed 90% of Q2 budget",
  "occurred_at": "2026-04-14T09:00:00Z"
}
```
