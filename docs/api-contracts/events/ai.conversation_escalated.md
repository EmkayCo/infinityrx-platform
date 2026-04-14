# Event Contract: `ai.conversation_escalated`

**Schema version:** 1.0
**Status:** Active

## Description

An AI chatbot or conversational assistant session has been escalated to a
human agent because the AI could not resolve the user's query.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `session_id` | `UUID` | yes | Conversational session ID |
| `escalation_reason` | `str` | yes | Why escalation was triggered |
| `turn_count` | `int` | yes | Number of turns before escalation |
| `occurred_at` | `str (ISO-8601)` | yes | Escalation timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `ai-nlp` | Guardrail triggers human handoff or confidence threshold exceeded |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | — | Route to human agent queue |

## Ordering Key Convention

**`ordering_key`:** `session_id`

## Idempotency Key Convention

**`idempotency_key`:** `ai.conversation_escalated:{session_id}`

## Example Payload

```json
{
  "event_type": "ai.conversation_escalated",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "session_id": "uuid",
  "escalation_reason": "User requested human agent",
  "turn_count": 7,
  "occurred_at": "2026-04-14T10:15:00Z"
}
```
