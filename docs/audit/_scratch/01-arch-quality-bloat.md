# Architecture / Code Quality / Bloat — Audit Findings

Audit date: 2026-04-14. Codebase: 910 Python files, **115,931 LOC** (excluding `.venv`, `__pycache__`, `.claude/worktrees`). 25 module directories across 4 phases.

---

## Category 1: Architecture — score: 71/100

### Strengths

- **Shared library well-factored.** `shared/` contains canonical implementations for every cross-cutting concern: `shared/utils/money.py` (penny_allocate, ROUND_HALF_UP), `shared/events/` (EventBus ABC, EventEnvelope, RabbitMQ/InMemory implementations, idempotency, DLQ), `shared/db/` (tenant context, TenantScopedMixin, session factory), `shared/crypto/` (EncryptedString, PHIMixin), `shared/auth/` (JWT, MFA, sessions). No module-local duplication of money logic — `billing/src/utils/money.py` and `reclaimrx/src/utils/money.py` are thin re-exports with a docstring confirming they do not reimplement.
- **Module-per-schema migrations.** Every implemented module has its own `migrations/versions/` directory, consistent with the module-owns-schema rule.
- **Tenant isolation at ORM layer.** `TenantScopedMixin` is consistently applied on tenant-owned models in every implemented Phase 2–4 module (billing, reclaimrx, edi-compliance, medical-claims, dataiq, member-management, pharmacy-directory). `install_tenant_loader` is called in session factories for billing, payment-processing, reclaimrx, and drug-database.
- **EventEnvelope adoption.** 192 references to `idempotency_key`, `ordering_key`, `schema_version`, and `EventEnvelope` in production code. `shared/events/` provides idempotency, DLQ, and RabbitMQ/Azure Service Bus switching.
- **No circular imports.** Only two `from modules.` imports found in the entire codebase (both in `edi-compliance/src/main.py`, discussed below). Zero cross-module direct DB access found.
- **DLQ mounted.** All modules that have a `main.py` / `app.py` (core-platform, billing, edi-compliance, medical-claims, member-management, drug-database, dataiq, pharmacy-directory, prescriber-directory, ai-nlp) attempt to mount the DLQ router.

### Issues

#### CRITICAL

**C1-01: `edi-compliance/src/main.py:68–76` imports directly from another module's internals.**
```
from modules.core_platform.src.infrastructure.rate_limiter import RateLimitConfig, RateLimitMiddleware
from modules.core_platform.src.infrastructure.security_headers import SecurityHeadersMiddleware
```
This violates the "no direct module-to-module imports" principle and the Architecture rule that modules must communicate via APIs/events. If `core-platform` refactors its path, `edi-compliance` silently falls through the `except (ImportError, Exception): pass` catch and runs without security middleware. These classes should be in `shared/` or sourced from the module's own local copy.

**C1-02: `shared/auth/dependencies.py:110` imports from a specific module's internal shim.**
```
from modules.core_platform.src._shim.db import _current_tenant
```
A `shared/` library importing from a specific module's internal `_shim` is an inverted dependency. This creates a hard coupling: `shared` cannot be used without `core-platform`'s internal layout remaining stable. The `current_tenant_id` contextvar should be owned entirely by `shared.db.tenant_context`.

#### HIGH

**C1-03: `billing/src/events/publishers.py:15` and `edi-compliance/src/services/auto_posting.py:21` define local `EventBus` Protocol classes.**
The canonical `EventBus` ABC lives in `shared/events/bus.py`. Local Protocol definitions diverge and can accept arguments incompatible with the real bus (e.g., billing's `EventBus.publish` is sync; shared is async). Violates Architecture rule "MUST use `shared.events.bus.EventBus` ABC — no module-local `EventBus` protocols."

**C1-04: `SecurityHeadersMiddleware` and `RateLimitMiddleware` duplicated verbatim across 4+ modules.**
Files `core-platform/src/infrastructure/rate_limiter.py`, `medical-claims/src/infrastructure/rate_limiter.py`, and `member-management/src/infrastructure/rate_limiter.py` are byte-for-byte identical (MD5: `b764d7572c9e104ec8503adef4409700`). Same for `security_headers.py` (MD5: `62f842bf68f2729d18d0fe882d824dc1`). `pharmacy-directory` has a fourth variant. `prescriber-directory` has a fifth. This is 5 copies of the same middleware. Security rule mandates mounting these on every app; having 5 diverging implementations means a fix to one does not propagate. These belong in `shared/middleware/`.

**C1-05: `billing/src/main.py` and `reclaimrx` have no security middleware mounted.**
```
# billing/src/main.py — entire content:
app = FastAPI(title="InfinityRx Billing", ...)
app.include_router(router)
```
No `SecurityHeadersMiddleware`, no `RateLimitMiddleware`, no DLQ router. The security rule is explicit: "MUST mount SecurityHeadersMiddleware and RateLimitMiddleware on every production FastAPI app." `reclaimrx` has no `main.py` at all — its FastAPI app is only reachable from test fixtures, with no production entry point.

**C1-06: `prescriber-directory/src/db/session.py` missing `install_tenant_loader`.**
`prescriber-directory` creates its own session factory (`sessionmaker`) without calling `install_tenant_loader`, meaning all ORM queries against prescriber tables skip the tenant filter entirely. File: `modules/prescriber-directory/src/db/session.py:36`. Tenant isolation is NOT enforced at the DB layer for this module.

#### MEDIUM

**C1-07: Inconsistent application entry-point naming (`main.py` vs `app.py`).**
Some modules use `src/main.py` (core-platform, billing, edi-compliance, medical-claims, member-management, drug-database, dataiq, prescriber-directory), others use `src/app.py` (payment-processing, pharmacy-directory, ai-nlp), and two active modules (reclaimrx, reporting) have neither. Architecture rule requires `main.py` for every module that serves HTTP traffic.

**C1-08: Multiple modules have TODO-marked HTTP client stubs never wired up.**
`medical-claims/src/clients/member_management_client.py:3`, `medical-claims/src/clients/drug_database_client.py:3`, `medical-claims/src/clients/pharmacy_directory_client.py:3` — all three inter-module client files are TODO stubs that return hardcoded responses. The medical-claims module cannot actually communicate with member-management, drug-database, or pharmacy-directory. Principle 8 ("modules communicate via API calls") is unfulfilled.

#### LOW

**C1-09: Phase 4 "not yet implemented" modules have scaffold directories but no Python source.**
Modules `adjudication-engine`, `mtm-clinical`, `part-d-pde`, `plan-design`, `prior-authorization`, `program-config`, `rebate-management`, `rules-engine`, `switch-connectivity`, `testing-simulator`, `ebv-ebi-rtbc` each have `src/`, `tests/`, `migrations/`, and `tasks/` directories — all empty. These are harmless skeleton directories but add noise and should be confirmed intentional per the dead code rule.

### Recommendations

1. Move `rate_limiter.py` and `security_headers.py` to `shared/middleware/` and delete the 4+ local copies. Add integration test in each module's `create_app()` test.
2. Add `install_tenant_loader` to `prescriber-directory/src/db/session.py` immediately (HIGH security risk).
3. Move `_current_tenant` contextvar out of `modules.core_platform.src._shim.db` into `shared.db.tenant_context` so `shared/` has no dependency on any specific module.
4. Replace `billing/src/events/publishers.py:EventBus` Protocol and `edi-compliance/src/services/auto_posting.py:_EventBusProtocol` with imports from `shared.events.bus`.
5. Add `main.py` with full middleware stack to `billing` and `reclaimrx`.

---

## Category 2: Code Quality — score: 76/100

### Test Run Results

| Module | Passed | Failed | Errors | Notes |
|---|---|---|---|---|
| core-platform + shared | 780 | 0 | 0 | 1 skip (RabbitMQ broker unreachable) |
| billing | 299 | 0 | 0 | |
| reclaimrx | 226 | 0 | 0 | |
| edi-compliance | 754 | 0 | 0 | |
| payment-processing | 270 | **1** | 0 | Golden NACHA date mismatch (see below) |
| reporting | 362 | 0 | 0 | |
| medical-claims | 285 | 0 | 0 | |
| member-management | 310 | 0 | 0 | |
| pharmacy-directory | 109 | 0 | **89** | `ModuleNotFoundError: No module named 'aiosqlite'` |
| prescriber-directory | 202 | 0 | 0 | |

**FAILING TEST — payment-processing:**
`modules/payment-processing/tests/golden/test_golden_nacha.py::TestNachaGoldenMaster::test_nacha_output_matches_golden` — NACHA file contains today's date (2026-04-14) but golden file was snapshotted on 2026-04-13. The NACHA generator embeds the current date at generation time, making this test inherently date-sensitive. The golden file needs a date-neutral fixture or the golden master needs refreshing.

**89 ERRORS — pharmacy-directory:**
All errors in `modules/pharmacy-directory/tests/integration/test_upsert.py` fail at setup with `ModuleNotFoundError: No module named 'aiosqlite'`. The async test conftest requires `aiosqlite` which is not in `pyproject.toml`. This means 89 integration tests have never run in this environment — a coverage gap.

### Float / Money Violations

Only one **money-critical** float conversion found in production services:

- **HIGH:** `modules/edi-compliance/src/services/fhir_bridge.py:122` — `float(b.monetary_amount)` emitted into a FHIR `allowedMoney.value` JSON field. `monetary_amount` is a `Decimal`; converting to `float` risks precision loss in FHIR outbound payloads. Financial-precision rule explicitly forbids this.

Non-money float usages (acceptable for their purpose):
- `modules/reclaimrx/src/services/ml_scoring.py:41-48,82` — `float()` conversions for ML feature vector (numpy/sklearn require `float`). Acceptable: these are ML features, not monetary values. Comments in the file acknowledge this.
- `modules/dataiq/src/services/kpi.py:73` — `float(amount)` for `redis.hincrbyfloat`. Redis `HINCRBYFLOAT` only accepts floats; this is a Redis API constraint, not money storage. LOW risk.
- `modules/dataiq/src/services/geo_analytics.py:55-59`, `modules/pharmacy-directory/src/services/lookup.py:24-27`, `modules/pharmacy-directory/src/services/network.py:205-207` — `float()` for trigonometric lat/lng calculations. Correct and unavoidable.
- `modules/core-platform/src/infrastructure/rate_limiter.py:44-47` — `float` for token bucket capacity/rate. Not money.
- `modules/ai-nlp/src/services/rag_service.py:52,188` — `float` for ML similarity scores. Not money.

**Type annotation `float` in schemas:**
`modules/edi-compliance/src/api/compliance.py:36` — `acceptance_rate_pct: float` in a Pydantic response schema for a percentage. Not a money field; acceptable.
`modules/edi-compliance/src/services/denial_scoring.py:31,43,44` — `weight: float` and threshold constants for ML scoring. Not money; acceptable.

### Bare Exception Catches (non-noqa, non-pragma)

Broad `except Exception` without `noqa` or `pragma: no cover` in production code:

| File | Line | Context |
|---|---|---|
| `modules/payment-processing/src/_shim/db.py` | 66 | Engine teardown in shim — low risk |
| `modules/payment-processing/src/events/consumers.py` | 38 | Event consumer error handling — HIGH: exceptions swallowed silently |
| `modules/core-platform/src/audit/middleware.py` | 110, 211, 227 | Audit middleware — broad catches to prevent audit from breaking requests |
| `modules/core-platform/src/audit/middleware.py` | 132 | Broad catch with `exc` var — should be narrowed |
| `modules/medical-claims/src/api/routes/claims.py` | 88 | Request handler broad catch — should map to specific exceptions |
| `modules/medical-claims/src/jobs/asp_refresh_job.py` | 71 | Job error handling |
| `modules/medical-claims/src/events/consumers.py` | 50, 102 | Consumer broad catch |
| `modules/medical-claims/src/services/accumulator_service.py` | 70 | Silently discards accumulator errors — HIGH risk |
| `modules/medical-claims/src/services/detection_340b_service.py` | 40 | Broad except in detection service |
| `modules/edi-compliance/src/main.py` | 31, 42, 49 | lifespan startup/shutdown (acceptable) |
| `modules/edi-compliance/src/services/denial_scoring.py` | 83 | ML scoring fallback |
| `modules/edi-compliance/src/services/scrubbing.py` | 211, 228, 250 | Scrubbing rule evaluation — should narrow |
| `modules/drug-database/src/db/session.py` | 51 | DB teardown |
| `modules/billing/src/db/session.py` | 42 | DB teardown |
| `modules/prescriber-directory/src/db/session.py` | 54 | DB teardown |
| `modules/ai-nlp/src/services/rag_service.py` | 154 | RAG fallback |
| `modules/ai-nlp/src/events/consumers.py` | 73 | Consumer broad catch |
| `modules/prescriber-directory/src/services/nppes_upsert.py` | 201 | Upsert error handling |

**Most Severe:** `medical-claims/src/services/accumulator_service.py:70` — silently swallows accumulator update failures. This is a financial path: if accumulator update fails, claims may be adjudicated without correct accumulators.

### TODO/FIXME Catalog

All TODOs are in `modules/medical-claims/`:

| File | Line | Content |
|---|---|---|
| `medical-claims/src/clients/member_management_client.py` | 3, 33 | Replace stub with real HTTP calls to member-management |
| `medical-claims/src/clients/drug_database_client.py` | 3, 24, 32 | Replace stub with real HTTP calls to drug-database |
| `medical-claims/src/clients/pharmacy_directory_client.py` | 3, 27 | Replace stub with real HTTP calls to pharmacy-directory |
| `medical-claims/src/api/routes/claims.py` | 170 | Implement CSV/Excel parsing |
| `medical-claims/src/events/consumers.py` | 21, 29 | Wire `edi.837_received` consumer when EDI finalizes its contract |
| `medical-claims/src/services/claim_service.py` | 261 | Wire to real `edi.837_received` event schema |

No TODOs found in billing, reclaimrx, core-platform, or shared. All medical-claims TODOs represent incomplete inter-module integration work.

### Hardcoded Secrets

No hardcoded passwords, API keys, or secrets found in production code. All `password=` and `secret=` references are settings/env-var lookups.

### Regex Security (LESSON-004)

- `modules/medical-claims/src/utils/validators.py:30` uses `re.match(r"\A[JQC]\d{4}\Z", ...)` — the `\A` and `\Z` anchors are correct and immune to the LESSON-004 trailing-newline issue, even though `re.match` is used. Technically safe but stylistically inconsistent with the project norm of `re.fullmatch`.
- All other validation files (drug-database, pharmacy-directory, prescriber-directory) correctly use `re.fullmatch()` or `\A...\Z` per LESSON-004.
- `modules/edi-compliance/src/services/code_sets.py:68-71` uses `re.compile` with `^...$` anchors. These are used via `.match()` or `.search()` — not a security boundary (code set validation, not auth), but inconsistent.

### Type Hints Coverage

Spot-checked 5 service files:
- `modules/core-platform/src/auth/service.py` — full type annotations on all function signatures. GOOD.
- `modules/billing/src/services/ap.py`, `ar.py`, `budget.py` — full type annotations including `Decimal` return types. GOOD.
- `modules/reclaimrx/src/services/ml_scoring.py` — complete annotations; ML feature vectors use `float[]` intentionally. GOOD.
- `modules/edi-compliance/src/services/fhir_bridge.py` — annotated; the `float(b.monetary_amount)` violation at line 122 is in an otherwise typed function.

### Unused Imports (F401)

- **412 total F401 violations** across modules and shared (all auto-fixable per ruff).
- **82 violations in production `src/` code** across **55 unique files**.
- Notable production violations:
  - `modules/member-management/src/api/routes/eligibility.py`: 5 unused imports (`Response`, `JSONResponse`, `PlainTextResponse`, `EligibilityResponse`, `EligibilityStatus`)
  - `modules/edi-compliance/src/api/parse.py`, `modules/edi-compliance/src/x12/parsers/parse_271.py`, `parse_278.py`, `parse_834.py`, `parse_999.py`: multiple unused imports
  - `modules/medical-claims/src/api/routes/claims.py`, `denials.py`, `analytics.py`, `crosswalk.py`, `asp.py`: unused schema imports
  - `modules/drug-database/src/api/router.py`, `models/tables.py`: unused imports
- Remaining 330 violations are in test files (lower severity but should be fixed before next release).

---

## Category 3: Bloat — score: 77/100

### Metrics

| Metric | Value |
|---|---|
| Total Python LOC (excl. .venv, __pycache__, .claude) | **115,931** |
| Total Python files | **910** |
| Files > 500 lines | **16** |
| Empty Python files (0 bytes) | 0 (all __init__.py contain content or are package markers) |
| Committed __pycache__ / .pyc | **0** — .gitignore covers them; none tracked in git |
| Worktrees in .claude/ | 5 active worktrees (not in git, .gitignore covers them) |

### Files Over 500 Lines (production src only)

| File | Lines | Issue |
|---|---|---|
| `modules/reporting/src/services/report_library.py` | 1,082 | God class — 14 report types in one service |
| `modules/billing/src/api/router.py` | 970 | Monolithic router — 20+ endpoints in one file |
| `modules/billing/src/models/tables.py` | 819 | Large but model files tend to grow with columns |
| `modules/reclaimrx/src/models/tables.py` | 795 | Same |
| `modules/reclaimrx/src/services/detection_rule_seeder.py` | 769 | Seed data embedded in service file |
| `modules/reclaimrx/src/api/router.py` | 634 | Monolithic router |
| `modules/core-platform/src/auth/service.py` | 631 | Auth monolith — could be split by domain (user, role, mfa) |
| `modules/shared/db/models/core.py` | 508 | Core model file; reasonable for shared models |

Test files over 500 lines (expected for coverage completeness but worth noting):
- `medical-claims/tests/unit/test_coverage_boost.py`: 1,173 lines — likely a coverage-gap-plugger, not feature tests
- `reporting/tests/unit/test_services_coverage.py`: 756 lines

### Duplicated Infrastructure Code (CRITICAL BLOAT)

**`rate_limiter.py` — 4 identical copies (3 exact + 1 variant):**
- `modules/core-platform/src/infrastructure/rate_limiter.py` (175 lines)
- `modules/medical-claims/src/infrastructure/rate_limiter.py` (175 lines) — **byte-for-byte identical**
- `modules/member-management/src/infrastructure/rate_limiter.py` (175 lines) — **byte-for-byte identical**
- `modules/drug-database/src/infrastructure/rate_limiter.py` (84 lines) — partial variant
- `modules/prescriber-directory/src/middleware/rate_limiter.py` — different implementation
- `modules/pharmacy-directory/src/api/middleware.py` — combined middleware file

**`security_headers.py` — 3 identical copies + 2 variants:**
- `modules/core-platform/src/infrastructure/security_headers.py`
- `modules/medical-claims/src/infrastructure/security_headers.py` — **byte-for-byte identical**
- `modules/member-management/src/infrastructure/security_headers.py` — **byte-for-byte identical**
- `modules/prescriber-directory/src/middleware/security_headers.py` — variant
- `modules/pharmacy-directory/src/api/middleware.py` — combined with rate limiter

Conservatively, ~700 lines of duplicated middleware code. Correct fix: move to `shared/middleware/rate_limiter.py` and `shared/middleware/security_headers.py`.

### Redundant Module-Local Money Re-Export Files

`modules/billing/src/utils/money.py` (13 lines) and `modules/reclaimrx/src/utils/money.py` (50 lines, though it adds `three_tier_recovery`) exist solely as re-export shims. `billing/src/utils/money.py` is pure pass-through with no additional value — all callers could import from `shared.utils.money` directly. The `reclaimrx` file is borderline justified by `three_tier_recovery`.

### Dead/Stub Files

- **Phase 4 scaffold directories:** 11 modules (`adjudication-engine`, `mtm-clinical`, `part-d-pde`, `plan-design`, `prior-authorization`, `program-config`, `rebate-management`, `rules-engine`, `switch-connectivity`, `testing-simulator`, `ebv-ebi-rtbc`) each have `src/`, `tests/`, `migrations/`, `tasks/` directories that are entirely empty. These directories contain only a README.md. Per the dead code rule these should not exist until the phase is active. Estimated: 44 empty directories.
- **`modules/medical-claims/tests/unit/test_coverage_boost.py`** (1,173 lines): filename signals this was written specifically to inflate coverage numbers rather than to test behavior. This is an anti-pattern per the testing rules ("no dead code/stub files").

### Commented-Out Code

Low volume. Notable instances:
- `modules/core-platform/src/bank_holidays/api.py:52` — inline comment explaining overflow guard (documentation, not commented code)
- `modules/billing/tests/unit/test_routing.py:158` — inline calculation comment (acceptable)
- No significant blocks of commented-out production code found.

### Estimated Bloat Percentage

~8–10% of total LOC is bloat:
- ~700 lines: duplicated middleware (rate_limiter + security_headers)
- ~700 lines: `test_coverage_boost.py` coverage inflation test
- ~500 lines: test files with large unused import counts
- ~200 lines: scaffold empty directories (no code, but metadata)
- **Total removable: ~2,100–2,500 lines (~2%)**

Structural bloat (files/directories that complicate navigation without adding value):
- 44 empty Phase 4 scaffold directories
- 5 local copies of middleware that should be in shared

### Removable Items (specific paths)

| Path | Action | LOC Recovered |
|---|---|---|
| `modules/medical-claims/src/infrastructure/rate_limiter.py` | Delete; import from `shared/middleware/` | 175 |
| `modules/member-management/src/infrastructure/rate_limiter.py` | Delete; import from `shared/middleware/` | 175 |
| `modules/drug-database/src/infrastructure/rate_limiter.py` | Delete; import from `shared/middleware/` | 84 |
| `modules/medical-claims/src/infrastructure/security_headers.py` | Delete; import from `shared/middleware/` | 175 |
| `modules/member-management/src/infrastructure/security_headers.py` | Delete; import from `shared/middleware/` | 175 |
| `modules/billing/src/utils/money.py` | Delete; callers import `shared.utils.money` directly | 13 |
| Phase 4 empty `src/`, `tests/`, `migrations/`, `tasks/` dirs | Remove until phase is active | 44 dirs |
| `modules/medical-claims/tests/unit/test_coverage_boost.py` | Rewrite as behavior-named tests or delete | 1,173 |

### Recommendations

1. **Create `shared/middleware/rate_limiter.py` and `shared/middleware/security_headers.py`** and delete the 4–5 local copies. Saves ~700 LOC and ensures security fixes propagate everywhere.
2. **Remove empty Phase 4 scaffold directories** — per code-standards rule, if a module isn't being built, files should not exist.
3. **Delete `test_coverage_boost.py`** and rewrite as properly named behavioral tests.
4. **Run `uv run ruff check --fix --select F401`** on all modules to auto-fix 411 of 412 import violations.
5. **Add `aiosqlite` to `pyproject.toml`** to unblock 89 pharmacy-directory integration tests.
6. **Update the payment-processing golden NACHA test** to use a fixed date fixture instead of `datetime.today()`.
