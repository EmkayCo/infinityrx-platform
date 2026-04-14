# Event Bus Rules

## Publishing
- MUST use `EventEnvelope` for ALL events — never publish raw `(topic, dict)` payloads.
- MUST set `ordering_key` on every event (typically the entity ID — e.g., `batch_id`, `investigation_id`).
- MUST set `idempotency_key` on every event using business-level key (e.g., `payment_batch:{batch_id}:{action}`).
- MUST set `schema_version` on every event (start at `"1.0"`).
- MUST use dot-notation for event types: `claim.ingested`, `payment.settled`, `fwa.claim_flagged`.

## Consuming
- MUST wrap every consumer handler with `idempotent_handler` decorator.
- MUST handle unknown fields in payloads gracefully (forward compatibility).
- MUST NOT break on new `schema_version` values — ignore unknown fields.

## Reliability
- MUST mount DLQ router on production app — DLQ is useless if the API is unreachable.
- MUST monitor DLQ depth — alert when > 0 for > 15 minutes.
- MUST schedule cleanup of `processed_events` table (`DELETE WHERE processed_at < NOW() - INTERVAL '7 days'`).

## Contracts
- MUST document every event type in `docs/api-contracts/events/{event_type}.md`.
- MUST use dot-notation in both code AND documentation (not snake_case in docs and dot-notation in code).
