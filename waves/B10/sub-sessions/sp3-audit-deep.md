# SP-3 Deep Audit Sub-Session Ledger

**Date:** 2026-05-18  
**Session type:** Read-only deep audit (no code written)  
**Output:** `waves/B10/SP-3-audit-deep.md`

## What was done

1. Read spec `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md` in full (737 lines).
2. Located codex reviews at `docs/superpowers/codex-sp3-spec-review-r1.md` through `r5.md`. Confirmed `codex-sp3-plan-a-review-r1.md` does NOT exist (no Plan A was written yet — only the spec was reviewed).
3. Read `modules/reclaimrx/src/models/tables.py` in full (796 lines) — documented all 20 ORM classes.
4. Read `shared/events/types.py` in full — documented EventEnvelope field names (event_type, timestamp — NOT type/emitted_at as Plan A would have used).
5. Read `modules/reclaimrx/src/_shim/auth.py` in full — confirmed CurrentUser is a dataclass; `user.get("roles")` would fail.
6. Read `modules/reclaimrx/src/api/router.py` in full (635 lines) — inventoried 24 existing routes; identified 13+ missing SP-3 endpoints.
7. Walked `packages/contract/src/` tree — real layout is `src/impls/<domain>/` with 4 files per domain, NOT the assumed clients/schemas/impls/cache split.
8. Read `shared/events/dlq.py` and `shared/events/idempotency.py` in full.
9. Read `modules/reclaimrx/src/main.py` in full — confirmed 3/6 D14 bindings mounted, 3 missing.
10. Confirmed `shared/scheduling/` does NOT exist; APScheduler not installed; scheduling primitive is `shared/data_ingestion/scheduler.py` (asyncio + croniter).
11. Read `modules/reclaimrx/src/services/payment_hold_service.py` — confirmed all 3 idempotency cases unimplemented; no outbox; `is_active` bool used instead of status string.
12. Read `modules/reclaimrx/src/events/consumers.py` (690 lines) — 8 consumers verified.
13. Read `modules/reclaimrx/src/services/graph_analysis.py` — `FraudNetworkAnalyzer` exists but no GraphRun persistence.
14. Read `modules/reclaimrx/src/jobs/scheduled.py` — all job implementations are stubs.
15. Searched for deterministic hash primitives — `zlib.crc32` recommended; Python `hash()` confirmed PYTHONHASHSEED-randomized (must not use).

## Key findings for Plan A writers

- `PaymentHold` uses `is_active` bool (NOT `status` string) — the 3-case idempotency in spec §7.2 requires a status-string model change.
- `released_by`, `released_at`, `release_reason` already exist on PaymentHold (codex BLOCK 1 confirmed).
- All 6 SP-3 new tables (FraudRing, GraphRun, AccumulatorAnomaly, ThresholdConfig, ThresholdConfigAudit, OutboxEvent) are ABSENT.
- Investigation model must be significantly extended (11+ new columns including severity, source, outcome_label, etc.).
- Contract layer goes in `packages/contract/src/impls/reclaimrx/` (4 files), not separate clients/schemas dirs.
- APScheduler: not installed; use `asyncio.create_task` + croniter pattern from `shared/data_ingestion/scheduler.py`.
- Advisory lock hash: use `zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF`.
- 3/6 D14 bindings already in create_app (SecurityHeaders, RateLimit, DLQ router). Missing: processed_events cleanup scheduler, DLQ depth monitor, audit hash-chain daily job.

## Cross-link

Full audit: `waves/B10/SP-3-audit-deep.md`
