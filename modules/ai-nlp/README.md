# Module: ai-nlp — AI/NLP Layer

Separate FastAPI service. Owns the `ai_nlp` PostgreSQL schema.
Communicates with other modules via API calls and event bus — no cross-schema queries.

See root `CLAUDE.md` for platform principles. Module PRD: `docs/prd/prd-ai-nlp.md`.

## Purpose

Centralized AI/NLP service layer consumed by all other modules. No module implements its own AI logic.

Capabilities:
- Document Intelligence (OCR, extraction, classification — 8 pre-built document types)
- Text Understanding (NLP classification, entity extraction, summarization)
- Content Generation (7 pre-built templates — PA letters, audit demand, member comms)
- Conversational AI (RAG-based chatbot for 4 portal types)
- Intelligent Document Routing (auto-classify and route uploaded documents)
- Anomaly Narrative Generation (human-readable explanations for ReclaimRx flags)
- LLM Provider Fallback (Azure OpenAI primary, configurable secondary)

## Setup

```bash
# Environment variables required:
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_GPT41=<deployment-name>
AZURE_OPENAI_DEPLOYMENT_GPT41_MINI=<mini-deployment-name>
```

## API Overview

All endpoints under `/api/v1/ai/`. Require `x-tenant-id: <uuid>` header.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | RAG-based chatbot (pharmacy, member, client, medical portals) |
| POST | `/documents/process` | Extract fields from a document |
| GET | `/documents/{id}/results` | Get extraction results |
| POST | `/text/classify` | Classify text (document type, sentiment, urgency) |
| POST | `/text/extract-entities` | Extract named entities |
| POST | `/generate` | Generate content from template |
| GET | `/generate/templates` | List available templates |
| GET | `/usage` | Usage and cost summary |
| GET | `/usage/by-module` | Usage breakdown by requesting module |
| GET | `/health` | Health check |

## Key Architecture Decisions

- **All OpenAI calls** go through `shared/ai/openai_client.py` — single chokepoint for retry, PHI scrubbing, cost logging
- **PHI never sent to OpenAI** unless `phi_access_level=full` is explicitly set
- **Cost logged as Decimal** (never float) to `ai_nlp.usage_log`
- **Low-confidence extractions (<0.85)** flagged for human review, never auto-applied
- **Chatbot answers always include sources[]** — ungrounded answers escalate
- **Vector queries always filter by tenant_id** — cross-tenant retrieval impossible
- **SecurityHeadersMiddleware mounted** on `create_app()` — all responses get HSTS, CSP, etc.
- **Cache-Control: no-store** on all endpoints returning member/claim context
- **Prompt templates** in `src/prompts/*.jinja` — version-controlled, never inline strings

## Configuration

- `temperature=0` for all extraction/classification tasks
- `temperature=0.1` for content generation (deterministic drafts)
- Confidence threshold: `0.85` for human review trigger
- Chatbot escalation: 2 consecutive low-confidence responses

## Running Tests

```bash
python3.13 -m pytest modules/ai-nlp/tests/ shared/tests/ai/ --cov=modules/ai-nlp/src --cov=shared/ai --cov-branch
```

Current: **166 tests, 99.76% branch coverage**
