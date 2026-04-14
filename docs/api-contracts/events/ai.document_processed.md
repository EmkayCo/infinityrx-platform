# Event Contract: `ai.document_processed`

**Schema version:** 1.0
**Status:** Active

## Description

The AI-NLP module has completed processing a clinical or administrative document
(e.g., prior auth request, clinical note, EOB).

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `document_id` | `UUID` | yes | Document record ID |
| `document_type` | `str` | yes | `clinical_note`, `prior_auth`, `eob`, `fax` |
| `extraction_count` | `int` | yes | Number of entities extracted |
| `confidence_score` | `str (Decimal)` | yes | Overall extraction confidence (0.00–1.00) |
| `occurred_at` | `str (ISO-8601)` | yes | Processing completion timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `ai-nlp` | Document extraction pipeline completes |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(prior-authorization)* | — | Trigger PA determination with extracted criteria |

## Ordering Key Convention

**`ordering_key`:** `document_id`

## Idempotency Key Convention

**`idempotency_key`:** `ai.document_processed:{document_id}`

## Example Payload

```json
{
  "event_type": "ai.document_processed",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "document_id": "uuid",
  "document_type": "prior_auth",
  "extraction_count": 14,
  "confidence_score": "0.93",
  "occurred_at": "2026-04-14T10:00:00Z"
}
```
