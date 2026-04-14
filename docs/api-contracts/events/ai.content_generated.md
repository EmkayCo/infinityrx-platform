# Event Contract: `ai.content_generated`

**Schema version:** 1.0
**Status:** Active

## Description

The AI-NLP module has generated a content response (e.g., denial letter,
member communication, explanation of benefits narrative).

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `generation_id` | `UUID` | yes | Generation record ID |
| `content_type` | `str` | yes | `denial_letter`, `pa_notification`, `member_communication` |
| `word_count` | `int` | yes | Approximate word count of generated content |
| `model_version` | `str` | yes | AI model version used |
| `occurred_at` | `str (ISO-8601)` | yes | Generation timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `ai-nlp` | Content generation pipeline completes |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(notification service)* | — | Queue for delivery to member/provider |

## Ordering Key Convention

**`ordering_key`:** `generation_id`

## Idempotency Key Convention

**`idempotency_key`:** `ai.content_generated:{generation_id}`

## Example Payload

```json
{
  "event_type": "ai.content_generated",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "generation_id": "uuid",
  "content_type": "denial_letter",
  "word_count": 420,
  "model_version": "gpt-4.1-2026-04",
  "occurred_at": "2026-04-14T10:02:00Z"
}
```
