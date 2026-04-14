# Event Contract: `ai.confidence_low`

**Schema version:** 1.0
**Status:** Active

## Description

An AI-NLP extraction or generation result has a confidence score below the
configured threshold. The result requires human review before use.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `task_id` | `UUID` | yes | AI task that produced low-confidence result |
| `task_type` | `str` | yes | `extraction`, `classification`, `generation` |
| `confidence_score` | `str (Decimal)` | yes | Confidence score (0.00–1.00) |
| `minimum_threshold` | `str (Decimal)` | yes | Configured minimum threshold |
| `occurred_at` | `str (ISO-8601)` | yes | Event timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `ai-nlp` | AI pipeline result falls below confidence threshold |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | — | Route to human review queue |

## Ordering Key Convention

**`ordering_key`:** `task_id`

## Idempotency Key Convention

**`idempotency_key`:** `ai.confidence_low:{task_id}`

## Example Payload

```json
{
  "event_type": "ai.confidence_low",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "task_id": "uuid",
  "task_type": "extraction",
  "confidence_score": "0.61",
  "minimum_threshold": "0.85",
  "occurred_at": "2026-04-14T10:03:00Z"
}
```
