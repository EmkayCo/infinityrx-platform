# Event Contract: `regulatory.deadline_approaching`

**Schema version:** 1.0
**Status:** Active

## Description

A regulatory submission deadline is approaching the configured warning window.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `submission_id` | `UUID` | yes | Regulatory submission record |
| `submission_type` | `str` | yes | CMS filing type or state-specific code |
| `deadline_date` | `str (ISO-8601 date)` | yes | Filing deadline |
| `days_remaining` | `int` | yes | Days until deadline |
| `occurred_at` | `str (ISO-8601)` | yes | Alert generation timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `reporting` | Scheduled job finds deadline within warning window |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(notification service)* | — | Alert compliance team |

## Ordering Key Convention

**`ordering_key`:** `submission_id`

## Idempotency Key Convention

**`idempotency_key`:** `regulatory.deadline_approaching:{submission_id}:{deadline_date}`

## Example Payload

```json
{
  "event_type": "regulatory.deadline_approaching",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "submission_id": "uuid",
  "submission_type": "CMS_HEDIS",
  "deadline_date": "2026-04-30",
  "days_remaining": 16,
  "occurred_at": "2026-04-14T07:00:00Z"
}
```
