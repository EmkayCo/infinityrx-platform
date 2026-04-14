# ADR-003: Event type names use `domain.action` dot notation

**Status:** Accepted
**Date:** 2026-04-13

## Context

The audit found that `docs/api-contracts/events/` documents event
types in `snake_case` (e.g., `payment_settled`, `claim_ingested`),
but the actual publishers in `modules/*/src/events/publishers.py`
emit `dot.case` (`payment.settled`, `claim.ingested`, `fwa.claim_flagged`,
`report.generated`). None of the 12 actively-published event types
match any of the 24 documented contracts. Contracts and code are
decoupled.

## Decision

**Canonical form:** `<domain>.<action>` where `domain` and `action`
are both `snake_case`. Examples:
- `payment.settled`
- `claim.ingested`
- `fwa.suspicious_community_detected`
- `report.generated`
- `regulatory.deadline_approaching`

**Reasoning:**
- The dot is the natural routing-key separator in RabbitMQ and the
  Azure Service Bus topic filter syntax.
- The dot cleanly groups events by domain for subscription — a
  consumer can subscribe to `payment.*` to get every event in the
  payment domain without enumerating.
- `snake_case` within each segment matches Python identifier
  conventions and the existing JSON payload keys.

## Migration

1. Rename `docs/api-contracts/events/payment_settled.md` → `payment.settled.md`
   and update the file header. Repeat for every existing contract.
2. `grep -rn "bus.publish(\"" modules/*/src` — for every hit, confirm
   the string literal matches the ADR-003 format. `@build-agents/*`
   agents are responsible for enforcing this on new events.
3. Add a CI check that fails if any event_type string has a hyphen,
   space, or starts/ends with a dot.

## Alternatives considered

- **`snake_case` only** (`payment_settled`): rejected because it
  loses the routing-key structure.
- **`CamelCase`** (`PaymentSettled`): rejected because it breaks
  string-identity comparisons that already exist across the codebase.
- **Namespaced with module** (`billing.payment.settled`): rejected
  because the module that publishes is not always the module that
  owns the concept — e.g., `fwa.claim_flagged` is published by
  reclaimrx but the concept belongs to the claim domain.
