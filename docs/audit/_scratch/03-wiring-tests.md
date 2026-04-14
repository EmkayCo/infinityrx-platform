# Wiring / Test Quality — Audit Findings

**Audit Date:** 2026-04-14
**Auditor:** Audit Agent — Categories 5 and 9
**Source data:** Static analysis of all module `main.py`/`app.py` files, test directories, `.coverage` artifacts, `coverage.json`, and `pyproject.toml`.

---

## Category 5: Wiring — score: 52/100

### Scoring rationale

Ten modules are implemented with HTTP surfaces. Full LESSON-006-compliant wiring (SecurityHeaders + RateLimit + DLQ + AuditChain + TenantMW + shared events + consumers running) scores 10 points each. Partial credit is awarded proportionally. Critical misses (AuditMiddleware absent from every app; TenantIsolationMiddleware mounted nowhere except a test fixture; consumers defined but never subscribed at startup for 8 of 10 modules) cap the score.

---

### Wiring Map Table

| Module | main.py / app.py | SecHdrs | RateLimit | DLQ | AuditChain | TenantMW (middleware) | shared/ used | consumers running |
|---|---|---|---|---|---|---|---|---|
| core-platform | ✓ `create_app()` | ✓ | ✓ | ✓ | ✗ (AuditMiddleware exists but NOT in create_app) | ✗ (TenantIsolationMiddleware not in create_app) | ✓ | ✗ (no startup subscribe calls) |
| billing | ✗ bare `app=FastAPI()` — no `create_app()` | ✗ | ✗ | ✗ | ✗ | ✗ | partial (local `class EventBus(Protocol)` shadow in publishers.py) | ✗ |
| payment-processing | ✗ bare `app=FastAPI()` — no `create_app()` | ✗ | ✗ | ✗ | ✗ | ✗ | partial (shim; `install_tenant_loader` in `_shim/db.py` only) | ✗ (consumers.py exists, no subscribe) |
| reclaimrx | ✗ NO app entry point at all (no `main.py`, no `app.py`) | ✗ | ✗ | ✗ | ✗ | ✗ | partial (re-exports shared money; uses local `_shim` event bus) | ✗ (`CONSUMER_ROUTING` dict defined; never registered on bus) |
| reporting | ✗ NO app entry point at all | ✗ | ✗ | ✗ | ✗ | ✗ | partial | ✗ |
| ai-nlp | ✓ `create_app()` in app.py | ✓ | ✗ (missing RateLimitMiddleware) | ✗ (no DLQ router) | ✗ | ✗ | ✓ | ✗ (consumers.py exists; no startup subscribe) |
| dataiq | ✓ `create_app()` | ✗ (no SecurityHeadersMiddleware) | ✗ (no RateLimitMiddleware) | ✗ (no DLQ router) | ✗ | ✗ | ✓ | ✗ (consumers defined; no startup subscribe in create_app) |
| drug-database | ✓ `create_app()` | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ (`install_tenant_loader` in `db/session.py`) | ✗ |
| member-management | ✓ `create_app()` | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ (consumers defined; no startup subscribe) |
| pharmacy-directory | ✓ `create_app()` in app.py | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ ONLY (2 topics subscribed in lifespan: `fwa.credentialing_risk_elevated`, `fwa.pharmacy_risk_elevated`) |
| prescriber-directory | ✓ `create_app()` | ✓ | ✓ | ✗ (no DLQ router) | ✗ | ✗ | partial (publishers use shared EventEnvelope) | ✗ |
| medical-claims | ✓ `create_app()` | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ (consumers defined incl. TODO comment; no startup subscribe in main.py lifespan) |
| edi-compliance | ✓ `create_app()` | ✗ FRAGILE (try/except ImportError silently skips — wrong module path `modules.core_platform.src.infrastructure`) | ✗ FRAGILE | ✗ FRAGILE (same try/except pattern) | ✗ | ✗ | ✓ | ✗ |

---

### Critical Broken Chains

#### 1. AuditMiddleware — NEVER mounted on any production app (LESSON-006 repeat)
- `AuditMiddleware` exists at `modules/core-platform/src/audit/middleware.py` and has its own tests (`test_middleware.py`, `test_middleware_units.py`), but those tests build a **standalone** `FastAPI()` app, not through `create_app()`.
- `create_app()` in `modules/core-platform/src/main.py` mounts `RateLimitMiddleware` and `SecurityHeadersMiddleware` only. `AuditMiddleware` is absent.
- Impact: every mutating request silently skips audit logging on the production app. HIPAA §164.312(b) violation.
- Evidence: `modules/core-platform/src/main.py:166-167` (only two `add_middleware` calls); `modules/core-platform/tests/audit/test_middleware.py:39` uses `app = FastAPI()`.

#### 2. TenantIsolationMiddleware — defined but mounted NOWHERE
- Exists at `modules/core-platform/src/infrastructure/tenant_middleware.py:123`.
- Tested only via a standalone `app.add_middleware(TenantIsolationMiddleware, resolver=resolver)` in `tests/infrastructure/test_tenant_middleware.py:48`.
- Never imported or mounted in any module's `create_app()`.
- Evidence: `rg "TenantIsolationMiddleware" modules --include=*.py | grep -v test` returns only the class definition and `__init__.py` export.

#### 3. Event consumers — CONSUMER_ROUTING/handlers defined but never subscribed at bus startup (8 of 10 modules)
- **Only pharmacy-directory** calls `await bus.subscribe(...)` at startup (2 topics).
- `reclaimrx`: `CONSUMER_ROUTING` dict maps 8 topics to handlers (`modules/reclaimrx/src/events/consumers.py:109`) — never passed to any bus.
- `medical-claims`: handlers for `edi.837_received` and `claim.adjudicated` exist; `consumers.py:21` contains an explicit `# TODO: wire edi.837_received consumer` comment.
- `billing`, `dataiq`, `ai-nlp`, `member-management`, `reporting`: consumers defined; no startup wiring.
- Impact: all cross-module event-driven logic is dead code in production.

#### 4. billing — local `class EventBus(Protocol)` shadow
- `modules/billing/src/events/publishers.py:15` defines its own `EventBus` Protocol instead of using `shared.events.bus.EventBus`.
- Violates architecture rule: "MUST use `shared.events.bus.EventBus` ABC — no module-local `EventBus` protocols."
- Evidence: `modules/billing/src/events/publishers.py:15`.

#### 5. edi-compliance security middleware — silent no-op
- `create_app()` wraps middleware imports in `try/except (ImportError, Exception): pass`.
- The import path used is `modules.core_platform.src.infrastructure.rate_limiter` (underscores, not hyphens) — this will fail with `ModuleNotFoundError` in a correctly installed package environment.
- Result: SecurityHeadersMiddleware and RateLimitMiddleware silently absent from edi-compliance in production. No test catches this because the test creates a client from `create_app()` without verifying middleware is present.
- Evidence: `modules/edi-compliance/src/main.py:67-78`.

#### 6. reclaimrx and reporting — no HTTP app entry point
- Neither module has a `main.py` or `app.py`. No `FastAPI()` app instantiated. These modules cannot serve HTTP traffic and have no deployment artifact. If either is supposed to be a service (vs. a library), this is a gap.
- Evidence: `find modules/reclaimrx/src -name "*.py" | xargs grep -l "FastAPI"` returns zero results.

#### 7. billing and payment-processing — bare app, no `create_app()` factory
- Both use module-level `app = FastAPI(...)` with no factory pattern, making LESSON-006-compliant integration testing impossible without monkey-patching.
- Neither has SecurityHeaders, RateLimit, or DLQ mounted.
- Evidence: `modules/billing/src/main.py` (18 lines total); `modules/payment-processing/src/app.py` (20 lines total).

#### 8. Event chain: billing → reclaimrx — topics routed but not connected
- `billing` publishers emit `claim.ingested` and `claim.classified`; `reclaimrx` consumers subscribe to `claim.adjudicated` and `claim.reversed` — different topic names, and neither side is wired at startup anyway.
- No integration test verifies the full publish → subscribe → handler execution path for any cross-module event.

#### 9. Health checks — all return `{"status": "ok"}` with no dependency checks
- Except `core-platform` (which has a full `HealthRegistry` with DB/event-bus checks at `/health/detail`), every other module returns a static `{"status": "ok"}` with no liveness information about DB connectivity or event bus. Kubernetes readiness probes will receive a false positive even when the database is unreachable.

---

### Recommendations

1. **Mount `AuditMiddleware` in `core-platform/src/main.py:create_app()`** — add integration test that a POST request produces an audit row with non-empty `entry_hash`.
2. **Mount `TenantIsolationMiddleware` in every module's `create_app()`** — or document a deliberate decision to enforce tenant isolation at the DB layer only (and add a cross-tenant API test).
3. **Wire all `CONSUMER_ROUTING` maps at bus startup** — in each module's `lifespan()`, iterate `CONSUMER_ROUTING.items()` and call `await bus.subscribe(topic, handler)`.
4. **Refactor `billing` and `payment-processing` to `create_app()` factory pattern** — add integration tests asserting middleware presence.
5. **Fix edi-compliance middleware import path** — change `modules.core_platform.src.infrastructure.*` to the actual installed package path, or copy the middleware into the module; add an asserting wiring test.
6. **Replace billing's local `EventBus(Protocol)` with `shared.events.bus.EventBus`**.
7. **Add health endpoint dependency checks** to all modules (DB ping, event bus ping).
8. **Add a reclaimrx/reporting `create_app()` entry point** if either is intended to serve HTTP traffic.

---

## Category 9: Test Quality — score: 68/100

### Scoring rationale

Strong unit/integration coverage on implemented modules, good use of property-based tests in financial modules, golden master files for EDI/NACHA/billing, pytest.raises counts healthy. Penalties: no cross-module event bus integration tests (publish → actual consumer invocation); no concurrent access tests using `asyncio.gather`; edi-compliance 15% coverage (fail_under=99 gate is FAILING); core-platform partial coverage (62% on last run); member-management and reclaimrx/billing have no module-level `.coverage` artifact (evidence of tests not running under coverage).

---

### Coverage by Module

| Module | Last coverage | Source | Pass/Fail gate |
|---|---|---|---|
| core-platform | 62% (partial run: `auth/deps.py` missing 78%) | `modules/core-platform/.coverage` | FAIL (fail_under=95) |
| billing | unknown | no `.coverage` artifact found | unknown |
| payment-processing | 99% | `modules/payment-processing/.coverage` | PASS |
| reclaimrx | unknown | no `.coverage` artifact found | unknown |
| reporting | 97% | `modules/reporting/.coverage` | PASS |
| ai-nlp | 100% (worktree `agent-ac57501e`) | `.claude/worktrees/.coverage` | PASS |
| dataiq | unknown | no dedicated artifact | unknown |
| drug-database | unknown | no dedicated artifact | unknown |
| member-management | unknown | no dedicated artifact | unknown |
| pharmacy-directory | 100% | `modules/pharmacy-directory/.coverage` | PASS |
| prescriber-directory | unknown | no dedicated artifact | unknown |
| medical-claims | unknown | no dedicated artifact | unknown |
| edi-compliance | **15%** (1576 of 3230 statements uncovered) | `modules/edi-compliance/.coverage` | **HARD FAIL** (fail_under=99) |

**Root cause for edi-compliance 15%:** The x12 generators and parsers (`gen_278.py`, `gen_837d.py`, `gen_837i.py`, `gen_837p.py`, `gen_999.py`, `parse_271.py`, `parse_277.py`, `parse_278.py`, `parse_834.py`, `parse_999.py`, `validator.py`) are all at 0% coverage. Session 3 code (newly written) is not yet covered by tests. The module has 45 test files but they cover only the API layer and a subset of services.

**Root cause for core-platform 62%:** Only `auth/db_audit_sink.py` (100%) and `auth/deps.py` (22%) were measured — the coverage run was partial. Full module coverage measured in worktrees shows 98–100%.

---

### Test Type Breakdown (unit / integration / golden / property)

| Module | Total | Unit | Integration | Property | Golden |
|---|---|---|---|---|---|
| core-platform | 45 | 0 (flat layout) | 0 (flat layout) | 0 | 0 |
| billing | 15 | 12 | 1 | 1 | 1 |
| payment-processing | 20 | 14 | 4 | 1 | 1 |
| reclaimrx | 17 | 14 | 2 | 1 | 0 |
| reporting | 16 | 14 | 1 | 1 | 0 |
| ai-nlp | 11 | 10 | 1 | 0 | 0 |
| dataiq | 12 | 9 | 1 | 2 | 0 |
| drug-database | 13 | 9 | 4 | 0 | 0 |
| member-management | 16 | 15 | 1 | 0 | 0 |
| pharmacy-directory | 21 | 11 | 10 | 0 | 0 |
| prescriber-directory | 19 | 14 | 5 | 0 | 0 |
| medical-claims | 15 | 12 | 3 | 0 | 0 |
| edi-compliance | 45 | 41 | 3 | 0 | 1 (golden_master/) |

Note: core-platform tests use a flat layout (no `unit/` or `integration/` subdirs).

---

### Test Quality Gaps

#### G1. No end-to-end event bus integration tests (publish → consumer invocation)
- Zero tests verify the full cross-module flow: module A publishes an `EventEnvelope` to the real `InMemoryEventBus` → module B's consumer handler is invoked and produces the expected side effect.
- What exists: unit tests mock the bus and assert `bus.publish` was called; consumer unit tests pass a pre-built `EventEnvelope` directly to the handler function. The wire between them is untested.
- Affected: all modules with consumers (billing, reclaimrx, medical-claims, dataiq, ai-nlp, member-management, reporting, pharmacy-directory).

#### G2. No `asyncio.gather` / concurrent access tests
- No test exercises concurrent writes to the same accumulator, concurrent rate-limit counter updates, or concurrent session creation. Given 100M+ claims/year target, race conditions in accumulators and session limits are high-risk.
- `test_concurrent_limit_evicts_oldest` in `core-platform/tests/auth/sessions/test_session_service.py:231` tests sequential eviction logic, not true concurrency.

#### G3. edi-compliance — 0% coverage on all x12 generators/parsers/validator (15% total)
- 10 files completely uncovered. These are the core business logic of the module (X12 generation and parsing). The coverage gate is `fail_under=99` and the module is at 15%. This means the gate is currently **hard failing** and the Auto-Gate rule ("Any active code below 99% branch coverage → STOP") is breached.
- Evidence: `modules/edi-compliance/.coverage` report shows 0%/0%/0% on all x12 generator and parser files.

#### G4. member-management, reclaimrx, billing, dataiq — no `.coverage` files at module level
- Cannot verify these modules pass the Auto-Gate coverage threshold. Tests may run but coverage is not being measured or stored. The root `pyproject.toml` coverage `source` only includes `core-platform`, `billing`, `reclaimrx`, `ai-nlp`, and `member-management` — not `dataiq`, `drug-database`, `pharmacy-directory`, `prescriber-directory`, `medical-claims`, or `edi-compliance`.

#### G5. reporting — no golden master tests
- Reporting module generates financial outputs (Star Ratings PDC, Excel/PDF exports) but has no golden master test file. If the output format changes, there is no regression catch.

#### G6. member-management, pharmacy-directory, drug-database, medical-claims — no property-based tests
- Financial calculations (accumulator apply, spend allocation, ASP pricing, unified drug spend) have no property-based tests verifying invariants across arbitrary inputs (e.g., sum of splits equals total, Decimal precision preserved).

#### G7. edi-compliance — try/except pattern in create_app() makes wiring tests vacuous
- `test_main_branches.py::test_create_app_with_security_middleware_mocked` mocks the import rather than asserting the middleware is present and functional on responses (as LESSON-006 requires). The other `test_create_app_*` tests only check that `create_app()` returns a `FastAPI` instance and mounts `/health` — they do not assert HSTS headers on responses.

#### G8. Positive: cross-tenant isolation test coverage
- All 13 modules have cross-tenant test files. pharmacy-directory has 4 dedicated cross-tenant test files. This is a strong signal.

#### G9. Positive: `pytest.raises` error path coverage
- core-platform (36), member-management (37), reporting (32), edi-compliance (22), drug-database (21) all show substantial error path testing.

#### G10. Positive: financial property tests
- billing, payment-processing, reclaimrx, reporting all have `tests/property/test_financial_invariants.py` with Hypothesis-based tests for penny allocation and NACHA invariants.

---

### Summary Table: Test Quality by Dimension

| Dimension | Status |
|---|---|
| Unit test coverage — payment-processing, pharmacy-directory, prescriber-directory | PASS (99–100%) |
| Unit test coverage — edi-compliance | HARD FAIL (15%) |
| Unit test coverage — core-platform | PARTIAL (62% on partial run; 98% in worktree) |
| Integration tests through create_app() | PARTIAL (7 of 10 modules have at least one; billing/payment-processing/reclaimrx/reporting absent) |
| Golden master tests | PARTIAL (3 modules: edi-compliance, billing, payment-processing; reporting missing) |
| Property-based tests | PARTIAL (6 modules; member-management, medical-claims, drug-database, pharmacy-directory missing) |
| Cross-module event bus E2E tests | FAIL (0 exist across entire platform) |
| Concurrent access tests | FAIL (0 exist; only sequential session limit test) |
| Error path (`pytest.raises`) density | PASS (healthy counts in all modules) |
| Cross-tenant isolation tests | PASS (all 13 modules covered) |
