# Event Contract: `ai.document_routed`

**Schema version:** 1.0
**Status:** Active

## Description

A document (e.g., fax bundle) has been classified and routed to the
appropriate handling queue by the AI-NLP pipeline.

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenant_id` | `UUID` | yes | Tenant context |
| `document_id` | `UUID` | yes | Document record ID |
| `routing_destination` | `str` | yes | Queue or workflow destination |
| `document_class` | `str` | yes | Classified document type |
| `confidence_score` | `str (Decimal)` | yes | Classification confidence |
| `occurred_at` | `str (ISO-8601)` | yes | Routing timestamp |

## Publishers

| Module | Condition |
|--------|-----------|
| `ai-nlp` | Document classification and routing completes |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| *(none yet)* | — | Downstream queue processing |

## Ordering Key Convention

**`ordering_key`:** `document_id`

## Idempotency Key Convention

**`idempotency_key`:** `ai.document_routed:{document_id}`

## Example Payload

```json
{
  "event_type": "ai.document_routed",
  "schema_version": "1.0",
  "tenant_id": "uuid",
  "document_id": "uuid",
  "routing_destination": "prior_authorization_queue",
  "document_class": "prior_auth_request",
  "confidence_score": "0.97",
  "occurred_at": "2026-04-14T10:01:00Z"
}
```
