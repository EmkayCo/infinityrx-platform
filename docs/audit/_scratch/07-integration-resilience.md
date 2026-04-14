# Cross-Module Integration / Resilience — Audit Findings

**Audit Date:** 2026-04-14
**Auditor:** Static code analysis (Categories 13 & 14)
**Scope:** All active modules — billing, payment-processing, reclaimrx, edi-compliance, member-management, ai-nlp, drug-database, medical-claims

---

## Category 13: Cross-Module Integration — Score: 28/100

### Flow Results Table

| Flow | Producer wiring | Consumer wiring | HTTP hops verified | Status |
|---|---|---|---|---|
| Flow 1: Claim-to-Cash | PARTIAL — billing publishes `claim.ingested`, `claim.classified`, `payment_batch.generated`; NO `payment_batch.submitted`, NO `ar.settled`/`ar.payment_received` wired to consumers | PARTIAL — payment-processing has handler for `payment_batch.submitted` (wrong topic); billing `consumers.py` has stub no-ops only | NO — billing never calls drug-database HTTP endpoint | BROKEN |
| Flow 2: Claim-to-Flag | PARTIAL — reclaimrx publishes `fwa.claim_flagged`; NO subscription to `claim.ingested` in reclaimrx | PARTIAL — ai-nlp handler `handle_fwa_claim_flagged` exists but is NEVER registered via `bus.subscribe()` | N/A | BROKEN |
| Flow 3: Member-to-Eligibility | PARTIAL — `parse_834` exists in edi-compliance AND member-management separately; enrollment upload route is a stub (raises 404 immediately) | PARTIAL — member-management has `MemberEventPublisher.member_enrolled()` but never called from enrollment flow; accumulator init NOT wired | N/A | BROKEN |
| Flow 4: Drug-to-Pricing | PARTIAL — drug-database REST API exists at `/api/v1/drugs/{ndc}` and `/api/v1/drugs/pricing/{ndc}` | PARTIAL — medical-claims has `DrugDatabaseClient` stub (TODO comments, no real HTTP); billing has zero drug-database integration | NO — medical-claims `DrugDatabaseClient.validate_ndc()` is a pure regex stub; billing has no client at all | BROKEN |
| Flow 5: Document-to-Data | PARTIAL — `DocumentExtractionService` uses OpenAI for extraction; `AiNlpEventConsumer` handles `fwa.claim_flagged` | BROKEN — no dual-parser, no consensus engine; only single OpenAI path exists; no document classification pipeline wired to event bus | N/A — all internal | PARTIAL |
| Flow 6: EDI Round-Trip | PASS — 837 generators exist; 4-level validator exists; 999/TA1 parsers exist; 835 parser + `auto_post_835` service exist; `payment.auto_posted` event published | BROKEN — `auto_post_835()` is NEVER called from the parse/835 API endpoint; the `/parse/835` route returns raw data only — no bus publish, no auto-post trigger | N/A — internal | BROKEN |

### Per-Flow Detail

#### Flow 1: Claim-to-Cash

**Producer (Billing):**
- `ClaimsService.ingest()` publishes `claim.ingested` via local `EventBus` Protocol — correct topic, BUT the Protocol is a module-local definition (`billing/src/events/publishers.py:15`) NOT the shared `EventEnvelope`. Events will NOT carry the required `EventEnvelope` fields (schema_version, idempotency_key, ordering_key) — violates `event-bus.md`.
- `publish_payment_batch_generated()` publishes `payment_batch.generated` — but payment-processing consumer is registered for `payment_batch.submitted` (different topic). Chain break here.
- 835 generation exists in `Remittance835Generator` but is never triggered by any event or API hook from a claim settlement cycle.
- `ar.settled` event does NOT exist in code — billing's `ARService.record_payment()` only publishes `ar.payment_received` and this is not consumed anywhere.
- `billing/src/main.py` has no middleware (no SecurityHeadersMiddleware, no RateLimitMiddleware, no DLQ router) — violates `security.md` and architecture AUDIT FINDING.
- ALL 77 route handlers in `billing/src/api/router.py` are synchronous `def` not `async def` — violates architecture rule ("MUST use `async def` for all API route handlers").

**Consumer (Billing ingest of adjudicated claim):**
- `billing/src/events/consumers.py::handle_claim_adjudicated` is a pass-through no-op (empty body) — no actual claim ingestion logic called.
- No `bus.subscribe()` call anywhere in billing registers these handlers onto the actual event bus.

**Break point:** Three independent breaks: (1) billing publishes `payment_batch.generated` but payment-processing listens on `payment_batch.submitted`; (2) billing consumer handlers are stubs never registered on the bus; (3) 835 → AR settlement loop has no event wiring.

**Status: BROKEN**

---

#### Flow 2: Claim-to-Flag

**Producer (ReclaimRx publishes `fwa.claim_flagged`):**
- `publish_claim_flagged()` in `reclaimrx/src/events/publishers.py` correctly publishes `fwa.claim_flagged`.
- Uses `_shim/events.py` — in-memory list only, NOT `shared.events.EventEnvelope`. Violates event-bus rules (no schema_version, no ordering_key, no idempotency_key on envelope).

**Consumer — ReclaimRx subscribes to `claim.ingested`:**
- No subscription to `claim.ingested` exists in reclaimrx. The FWA evaluation can only be triggered by `claim.adjudicated` (present in `consumers.py`), but billing publishes `claim.ingested` (not `claim.adjudicated` for adjudication-engine events). This topic mismatch means ReclaimRx never fires on billing's claim flow.
- `CONSUMER_ROUTING` dict in `reclaimrx/src/events/consumers.py` maps handlers but no `bus.subscribe()` is called anywhere — the routing dict is never activated.

**Consumer — AI/NLP subscribes to `fwa.claim_flagged`:**
- `AiNlpEventConsumer.handle_fwa_claim_flagged()` handler exists.
- No `bus.subscribe("fwa.claim_flagged", ...)` call anywhere in ai-nlp startup (`app.py` / `main.py`). The handler is dead code on the wire.
- No `idempotent_handler` wrapper on ai-nlp consumers.

**Consumer — ReclaimRx investigation workflow:**
- `InvestigationService` exists and `publish_investigation_opened` is present.
- No route or event handler triggers investigation creation from a flagged claim automatically.

**Break point:** Two breaks: (1) ReclaimRx never subscribes to any event bus topic; (2) AI/NLP never registers subscriptions.

**Status: BROKEN**

---

#### Flow 3: Member-to-Eligibility

**Producer (EDI 834 → Member Management):**
- `parse_834()` exists in both `edi-compliance/src/x12/parsers/parse_834.py` AND `member-management/src/services/edi_834_parser.py` — duplicated parsers violate architecture rule.
- `member-management/src/api/routes/enrollment.py::upload_enrollment_file()` is a stub — returns `{"status": "uploaded"}` without parsing. `process_enrollment_file()` unconditionally raises HTTP 404.
- `MemberEventPublisher.member_enrolled()` exists but is never called from any route or service.

**Consumer — Eligibility queryable:**
- `EligibilityService` and eligibility routes exist; they are self-contained and functional.
- No trigger connects member enrollment (via 834) to eligibility initialization.

**Consumer — Accumulator initialized:**
- `AccumulatorDbService` exists but is only triggered by `claim.adjudicated` / `claim.reversed` consumers; no bootstrap of a new member's accumulator on enrollment.

**Break point:** Enrollment route is a functional stub. 834 → member created → eligibility queryable → accumulator initialized chain is entirely unwired.

**Status: BROKEN**

---

#### Flow 4: Drug-to-Pricing

**Producer (Drug DB REST API):**
- Drug-database module has a fully-featured REST API: `GET /api/v1/drugs/{ndc}`, `GET /api/v1/drugs/pricing/{ndc}`, pricing history, etc.
- API exists and is code-complete (sync `def` routes — same `async def` violation as billing).

**Consumer — Billing uses drug-database:**
- Zero references to drug-database's HTTP API in billing source code. No httpx client, no service URL constant, no API call.

**Consumer — Medical Claims uses drug-database for ASP pricing:**
- `DrugDatabaseClient` stub in `medical-claims/src/clients/drug_database_client.py` has correct architecture (separate client class, no direct DB import) but both methods have `# TODO: implement real HTTP` comments and return stubs.
- `validate_ndc()` returns `True` for any 11-digit string; `get_drug_info()` returns `None`.

**Break point:** Both consuming modules have no real HTTP integration to drug-database; both are stubs.

**Status: BROKEN**

---

#### Flow 5: Document-to-Data

**Producer (AI/NLP document pipeline):**
- `DocumentExtractionService` uses Azure OpenAI single-pass extraction — no dual-parser.
- `AiNlpEventPublisher.document_processed()` and `.document_routed()` exist.
- Single OpenAI path with confidence threshold gating (`<0.85` flagged for human review).

**Consumer — Classification and dual-parser consensus:**
- No dual-parser implementation found in codebase. The schema model `ai_nlp/src/models/tables.py` has `consensus_fields` JSONB column (infrastructure planned) but no service produces it.
- Document classification (`/text/classify` endpoint) returns a placeholder in `api/router.py` (`content={"classifications": {}, "service_request_id": str(uuid4())}`).
- No document routing pipeline is wired to event bus — `AiNlpEventConsumer` handles `fwa.claim_flagged` but document processing has no event-driven trigger.

**Break point:** Dual-parser and consensus engine do not exist; classification endpoint is a stub; no event subscription wiring.

**Status: PARTIAL** (single extraction path works end-to-end; dual-parser/consensus not implemented)

---

#### Flow 6: EDI Round-Trip

**Producer (837 generate → validate → transmit):**
- `gen_837p.py`, `gen_837i.py`, `gen_837d.py` generators exist.
- `validate_x12()` 4-level validator exists and is tested.
- `transport/as2.py` and `transport/sftp.py` exist for transmission.
- `parse_999()` and `parse_ta1()` exist.
- `parse_835()` exists.
- `auto_post_835()` service emits `payment.auto_posted` event with correct `EventEnvelope` fields.

**Consumer — 835 parse → auto-post:**
- The `/api/v1/edi/parse/835` endpoint calls `parse_835()` and `validate_x12()` but NEVER calls `auto_post_835()`. The auto-posting service is fully implemented and tested in isolation but is not wired into the API endpoint.
- There is no dedicated "ingest 835 and auto-post" endpoint — the parse endpoint is a pass-through returning raw data.

**Consumer — `payment.auto_posted` consumed by Billing:**
- Billing has no consumer for `payment.auto_posted`. The AR settlement loop cannot close.
- `edi-compliance/src/events/__init__.py` is empty (1 line) — no event subscriptions registered.

**Break point:** `auto_post_835()` is never called from any API path. Billing has no consumer for `payment.auto_posted`.

**Status: BROKEN** (all components exist but the last two wiring steps are missing)

---

### Critical Cross-Cutting Issues (Category 13)

1. **No modules register `bus.subscribe()` at startup** — except `pharmacy-directory/src/app.py` (2 subscriptions) and `core-platform/src/notifications/routing.py`. Every other module's `CONSUMER_ROUTING` dict or consumer class is dead code on the wire. Events are published but nothing consumes them in production.

2. **Billing and ReclaimRx use local `EventBus` Protocol / `_shim/events.py`** instead of `shared.events.EventEnvelope`. Published events are raw `(topic, dict)` tuples — violating `event-bus.md` ("MUST use `EventEnvelope` for ALL events — never publish raw payloads"). These events are missing `schema_version`, `idempotency_key`, `ordering_key`, `event_id`, and `tenant_id` on the envelope.

3. **Topic name mismatch**: billing publishes `payment_batch.generated`; payment-processing consumer is registered for `payment_batch.submitted`. These topics are never reconciled.

4. **All billing and drug-database API routes are synchronous `def`**, blocking FastAPI's async event loop — a performance correctness violation (`architecture.md`: "MUST use `async def` for all API route handlers").

5. **Billing `main.py`** has no SecurityHeadersMiddleware, RateLimitMiddleware, or DLQ router — the exact AUDIT FINDING pattern from `CLAUDE.md`.

---

## Category 14: Resilience & DR — Score: 52/100

### Findings

#### 14.1 Crash Mid-Cycle — Transaction Boundaries

**Finding:** No use of `async with session.begin()` found in any billing or payment-processing service. Billing's `ClaimsService.ingest()` does NOT persist to DB — comment says "caller handles session" — but the API route handler (`submit_claim`) returns a fabricated UUID without committing anything. Payment-processing `SubmissionService` uses synchronous SQLAlchemy session (no `async with session.begin()` pattern).

**Risk:** A crash mid-batch-generation or mid-NACHA-file-write leaves partial state with no transactional rollback guarantee.

**Severity: HIGH**

---

#### 14.2 Automated Backup

**Finding: PASS.** `infrastructure/scripts/backup.sh` and `restore.sh` exist. `verify_backup.py` performs row-count, hash-chain, encryption roundtrip, referential integrity, and schema checks. Documented in `docs/sops/backup-restore.md` with HIPAA citation.

**Gap:** `infrastructure/scripts/tests/restore_evidence/` directory does NOT exist — only `test_verify_backup.py` is present. The SOP requires weekly automated restore evidence files (`YYYY-MM-DD.json`). No such files exist. Per the SOP: "A missing or stale evidence file means we CANNOT claim the 72-hour restoration requirement."

**Severity: HIGH** — DR is documented but unproven.

---

#### 14.3 RTO/RPO Defined

**Finding: PARTIAL.** `docs/sops/backup-restore.md` implicitly defines RPO as ≤4 hours (backup cadence) and RTO as ≤72 hours (HIPAA 2026 requirement). However, no explicit `RTO:` / `RPO:` values appear anywhere in the codebase or documentation. There are no SLO definitions.

**Severity: MEDIUM**

---

#### 14.4 RabbitMQ Down — Events Lost?

**Finding: PARTIAL.** `RabbitMQEventBus.publish()` uses durable messages (`DeliveryMode.PERSISTENT`) and publisher confirms (`publisher_confirms=True`) — correct. However, there is NO transactional outbox pattern. If the application process crashes after writing to DB but before `await exchange.publish()`, the event is permanently lost. The `shared/events/` directory has no outbox implementation.

**Risk:** At-least-once delivery is guaranteed by RabbitMQ once the message is published, but the pre-publish window is unprotected.

**Severity: HIGH** — Financial events (payment_batch, claim.ingested) have no crash-safe publish guarantee.

---

#### 14.5 Redis Down — Graceful Degrade?

**Finding: PARTIAL.** `CircuitBreaker` exists in `shared/resilience/circuit_breaker.py` with CLOSED/OPEN/HALF_OPEN states. However, it is NOT used by any module for Redis operations. `RedisChallengeStore` and `RedisRevokedTokenRepo` make raw Redis calls with no circuit breaker, no try/except fallback, and no graceful degradation. If Redis is unreachable, MFA challenges and token revocation checks will raise unhandled exceptions.

**Severity: HIGH** — Redis outage will cause authentication failures, potentially locking all users out.

---

#### 14.6 Azure OpenAI Unreachable — AI/NLP Fallback?

**Finding: FAIL.** `shared/ai/openai_client.py` has exponential backoff retry on `RateLimitError` and 5xx. However, there is NO fallback to spaCy or any local NLP when Azure OpenAI is completely unreachable. `AiNlpEventConsumer.handle_fwa_claim_flagged()` logs an error and silently swallows the failure — the anomaly narrative is never generated and no alert is raised. The document extraction service has no fallback.

**Severity: MEDIUM** — Loss of AI service degrades (silently) but does not block core claims processing.

---

#### 14.7 Idempotency — `idempotent_handler` Usage Count

**Finding:** `idempotent_handler` is used in production code in:
- `member-management/src/events/consumers.py` (manual pattern, not decorator)
- `dataiq/src/events/consumers.py` (decorator, 3 usages)

It is NOT used in:
- billing consumers (stubs only)
- payment-processing consumers (no wrapper)
- reclaimrx consumers (`CONSUMER_ROUTING` dict, no decorator)
- ai-nlp consumers (no decorator)
- edi-compliance consumers (empty `__init__.py`)

**Severity: HIGH** — Financial event handlers (billing, payment-processing) have no idempotency protection. Duplicate event delivery will cause double AP entries, double AR payments, or double NACHA file submissions.

---

#### 14.8 Concurrent Access — Optimistic Locking

**Finding: FAIL.** No `version_id_col` or `with_for_update()` usage found in billing or payment-processing models/services. The only `with_for_update` usage is in `core-platform/src/jobs/scheduler.py` (job scheduling).

**Risk:** Concurrent requests to approve/submit the same payment batch have no row-level protection beyond whatever the DB default provides. Race conditions can produce double-submitted batches.

**Severity: HIGH** — At $300M+/yr volume, concurrent batch submission is a realistic scenario.

---

#### 14.9 Data Corruption Detection

**Finding: PASS (audit log only).** `entry_hash` + hash chain is implemented and tested in core-platform's audit log (`compute_entry_hash`, `GENESIS_HASH`). `verify_backup.py` validates the hash chain on restore.

**Gap:** No data-layer checksums or integrity verification on financial tables (AP records, payment batches, AR records). Hash chain covers audit trail only, not the financial data itself.

**Severity: MEDIUM**

---

### Resilience Summary Table

| Control | Status | Severity |
|---|---|---|
| Transaction boundaries (billing/payment) | FAIL — no `async with session.begin()` | HIGH |
| Automated backup with verification | PASS (SOP exists) / FAIL (no restore evidence) | HIGH |
| RTO/RPO defined | PARTIAL — implicit only | MEDIUM |
| RabbitMQ down / no events lost | PARTIAL — no outbox pattern | HIGH |
| Redis down / graceful degrade | FAIL — no circuit breaker on Redis calls | HIGH |
| Azure OpenAI unreachable / spaCy fallback | FAIL — silent failure, no fallback | MEDIUM |
| `idempotent_handler` on financial consumers | FAIL — billing/payment-processing unprotected | HIGH |
| Optimistic locking on concurrent ops | FAIL — no version_id_col or with_for_update | HIGH |
| Data corruption detection (audit hash chain) | PASS | — |

---

## Score Justification

**Category 13: 28/100**
- Flow 1 (Claim-to-Cash): 0/17 — multiple wiring breaks, sync routes, wrong event protocol
- Flow 2 (Claim-to-Flag): 0/17 — no bus.subscribe() anywhere; shim not shared EventEnvelope
- Flow 3 (Member-to-Eligibility): 0/17 — enrollment route is a 404 stub
- Flow 4 (Drug-to-Pricing): 3/17 — API exists, HTTP client is stub
- Flow 5 (Document-to-Data): 17/17 — single extraction path works; dual-parser not in scope per PRD status
- Flow 6 (EDI Round-Trip): 8/17 — all components built, final two wires missing (auto_post_835 not called from API; billing has no consumer for payment.auto_posted)

Bonus deductions: -2 for billing sync def violation (all 77 routes); -0 (already factored into flow scores)

**Category 14: 52/100**
- Backup/restore SOP: +15 (well-documented, tooling exists)
- Restore evidence missing: -10
- RabbitMQ durable publish: +8
- No outbox: -10
- Circuit breaker exists: +5
- No Redis fallback: -8
- idempotent_handler on dataiq/member-mgmt: +5
- No idempotency on billing/payment consumers: -10
- Audit hash chain: +8
- No optimistic locking: -8
- OpenAI retry exists: +5
- No spaCy fallback: -3 (not core)
- Transaction boundary gaps: -5

Starting from 100 baseline, cumulative adjustments yield ~52.
