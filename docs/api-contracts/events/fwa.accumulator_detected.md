# Event Contract: `fwa.accumulator_detected`

**Schema version:** 1.0
**Status:** Active

## Description

The FWA engine has detected a suspicious accumulator pattern, such as
abnormally fast benefit phase transitions or accumulator manipulation.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `member_id` | `UUID` | yes | Member with suspicious accumulator |
| `detection_type` | `str` | yes | `rapid_phase_change`, `duplicate_accumulation`, `reset_anomaly` |
| `accumulator_year` | `int` | yes | Benefit year |
| `occurred_at` | `str (ISO-8601)` | yes | Detection timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Accumulator pattern analysis detects anomaly |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `member-management` | (planned) | Flag member account for review |

## Ordering Key Convention

**`ordering_key`:** `member_id`

## Idempotency Key Convention

**`idempotency_key`:** `fwa.accumulator_detected:{member_id}:{detection_type}:{accumulator_year}`

## Example Payload

```json
{
  "event_type": "fwa.accumulator_detected",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "member_id": "uuid",
  "detection_type": "rapid_phase_change",
  "accumulator_year": 2026,
  "occurred_at": "2026-04-14T10:00:00Z"
}
```
