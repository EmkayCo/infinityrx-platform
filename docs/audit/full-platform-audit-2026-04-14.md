# InfinityRx Platform — Full Platform Audit

**Audit date:** 2026-04-14
**Scope:** 25 module directories, 13 PRDs (10,599 lines), 910 Python files, 115,931 LOC
**Method:** 7 parallel audit agents performing static analysis, targeted greps, module test runs, and code reading. No services were executed end-to-end; all integration findings are code-level wiring verifications.
**Stance:** Brutally honest. A 52 beats a false 90 on a system that moves $300M+/year.

---

## 1. Executive Summary

**Overall Score: 63/100** — average of 16 categories. "Builds pass, flows don't."

The platform has impressive breadth: 13 PRD-scoped modules with real implementations, strong financial-precision discipline in models, a well-factored `shared/` library, clean license/CVE posture, and healthy unit test coverage on most modules. The engineering primitives are largely correct. **What is broken is the wiring between them.**

LESSON-006 — the October 2025 finding that security/audit primitives were built in isolation but never mounted on production apps — has repeated itself at the **cross-module integration layer**. The audit middleware lives, hash chain works, `AuditMiddleware` is still not in `create_app()`. Billing's consumer handlers exist but no module (except pharmacy-directory) calls `bus.subscribe()` at startup. Five of six end-to-end business flows are broken at the wire level.

### Top 5 Critical Issues

| # | Finding | Impact | Evidence |
|---|---|---|---|
| C1 | **5 of 6 end-to-end flows broken.** ReclaimRx/AI-NLP/billing never call `bus.subscribe()` at startup — every `CONSUMER_ROUTING` dict is dead code in production. Topic mismatches (`payment_batch.generated` vs `.submitted`). Stub HTTP clients in medical-claims. | Platform cannot actually process a claim end-to-end. Category 13 score: 28/100. | `modules/reclaimrx/src/events/consumers.py:109`, `modules/billing/src/events/consumers.py` stubs, `modules/medical-claims/src/clients/drug_database_client.py:3` |
| C2 | **PHI not encrypted at rest in medical-claims.** `patient_member_id`, `rendering_provider_npi`, diagnosis codes stored as plaintext `String`. HIPAA §164.312(a)(2)(iv) violation. | A compromised backup exposes PHI in plaintext. Production blocker. | `modules/medical-claims/src/models/tables.py` |
| C3 | **No JWT authentication on medical-claims, prescriber-directory, edi-compliance routes.** Only `x-tenant-id` header UUID check. Any caller with a valid tenant UUID can read/write PHI and generate/parse X12. | Unauthenticated PHI/financial exposure. Production blocker. | `modules/medical-claims/src/api/routes/*.py`, `modules/prescriber-directory/src/api/dependencies.py`, `modules/edi-compliance/src/api/generate.py` |
| C4 | **LESSON-006 regression: `AuditMiddleware` and `TenantIsolationMiddleware` not mounted in any `create_app()`.** `core-platform/src/main.py:166-167` only adds RateLimit + SecurityHeaders. Tests for these middlewares build standalone `FastAPI()` apps, not through the factory. | Every mutating request skips audit logging. HIPAA §164.312(b). | `modules/core-platform/src/main.py:166`; `tests/audit/test_middleware.py:39` |
| C5 | **77+ sync `def` routes executing synchronous DB I/O in async FastAPI apps.** billing (77), reclaimrx (24), payment-processing (19), drug-database (16), prescriber-directory (17). Event-loop blocking is fatal at 100M claims/yr target. `statement_timeout` not set on any engine — runaway queries exhaust the pool. | Under load, the async advantage collapses into serialized serial execution. | `modules/billing/src/api/router.py`, `modules/reclaimrx/src/api/router.py`, `shared/db/engine.py` |

### Top 5 Strengths

1. **`shared/` library is well-factored.** Canonical `penny_allocate`, `EventEnvelope`, `TenantScopedMixin`, `install_tenant_loader`, `EncryptedString`, `PHIMixin`, `compute_entry_hash`, `DLQ`, `CircuitBreaker` all exist with tests. No module duplicates `penny_allocate`.
2. **Financial precision discipline in data models.** Zero `float`/`Float`/`REAL` columns on money fields across 12 modules. `Numeric(n,2)` used everywhere. `ROUND_HALF_UP` applied 150+ times. Property-based Hypothesis tests on penny-allocation invariants in 6 modules.
3. **MFA + audit hash chain now mounted and tested.** LESSON-006 is partially resolved: `SecurityHeadersMiddleware`, `RateLimitMiddleware`, DLQ router, `AuditService.log()` → `compute_entry_hash()`, and MFA challenge gate are all wired and integration-tested on core-platform.
4. **Clean CVE and license posture.** `pip-audit` 2026-04-14: zero vulnerabilities. No GPL/AGPL. `uv.lock` (1,694 lines) guarantees reproducible builds.
5. **Substantive EDI, X12, and financial implementations.** Full X12 generators/parsers for 835/837P/837I/837D/270/271/276/277/278/834/999, AS2+SFTP transport, NCPDP Batch 1.2, NACHA generator (fixed-width compliant), ACH return handling (80+ codes), 8-type fee engine, hash-chained journal, Star Ratings PDC, CAA transparency report — all real code, not stubs.

---

## 2. Scorecard

| # | Category | Score | Status |
|---|---|---|---|
| 1 | Architecture | 71/100 | 🟡 Solid foundation, 2 critical cross-module imports |
| 2 | Code Quality | 76/100 | 🟡 Tests pass; float violation in FHIR bridge; 18 broad catches |
| 3 | Bloat | 77/100 | 🟢 ~2% removable; duplicated middleware the biggest issue |
| 4 | Documentation | 58/100 | 🔴 CLAUDE.md stale; event catalog split-brain |
| 5 | Wiring | 52/100 | 🔴 LESSON-006 regressions; consumers not subscribed |
| 6 | PRD Compliance | 72/100 | 🟡 Weighted avg; ai-nlp 48% is the gap |
| 7 | Security | 64/100 | 🔴 3 modules unauthenticated; no CORS anywhere |
| 8 | Data Integrity | 77/100 | 🟢 5 `quantize()` missing `ROUND_HALF_UP`; no `ondelete=` |
| 9 | Test Quality | 68/100 | 🟡 edi-compliance 15%; no event-bus E2E tests |
| 10 | Team & Process | 72/100 | 🟡 No builder agents for Phase 3/4 built modules |
| 11 | Performance | 52/100 | 🔴 77+ sync routes; no `statement_timeout`; zero eager loading |
| 12 | Dependencies & Version Currency | 74/100 | 🟢 Clean CVE; Docker tags not digest-pinned |
| 13 | Cross-Module Integration | 28/100 | 🔴 5 of 6 flows broken |
| 14 | Resilience & DR | 52/100 | 🔴 No outbox; no Redis circuit breaker; no restore evidence |
| 15 | Regulatory & Compliance | 52/100 | 🔴 medical-claims PHI plaintext; no SOPs |
| 16 | Configuration & Environment | 62/100 | 🔴 3 modules bypass shared/config with hardcoded DB URLs; no Key Vault |
| | **OVERALL** | **63/100** | 🔴 **Not production-ready.** |

---

## 3. Per-Module PRD Compliance

Weighted average: **72/100** (weighted by PRD line count).

| Module | Score | PRD Lines | Status |
|---|---|---|---|
| payment-processing | 85 | 570 | 🟢 Strongest module — vendor adapters, OFAC, ACH returns all present |
| drug-database | 82 | 652 | 🟢 NDC/pricing/interactions complete; compound ingredients missing |
| reclaimrx | 80 | 1295 | 🟢 Detection rules + ML solid; competitive-gap features modeled but no service |
| medical-claims | 78 | 529 | 🟡 Full claim pipeline; NLP auto-coding is stub |
| member-management | 75 | 675 | 🟡 834/CSV, accumulators, 270/271 present; consent, COBRA tracking missing |
| edi-compliance | 75 | 712 | 🟡 X12 suite complete; X12 275 attachments and EDI RBAC missing |
| core-platform | 72 | 1383 | 🔴 **Auth/audit/notifications routers NOT mounted in main.py/api.py** — unreachable in production. Webhooks and feature flags entirely absent. |
| reporting | 72 | 684 | 🟡 Library + builder + Star/PDC present; scheduled delivery not wired |
| billing | 70 | 1380 | 🔴 Claims/NACHA/835/journal solid; 50-state compliance tables, accounting adapters, DIR fee, spread pricing all missing — "ships complete" PRD promise not met |
| pharmacy-directory | 70 | 622 | 🟡 Lookup + credentialing + PSAO present; accreditation, LDD, contract rate history missing |
| prescriber-directory | 65 | 499 | 🟡 NPPES + state rules present; DEA authority check, panel size, supervisory rels missing |
| dataiq | 62 | 690 | 🔴 Analytics endpoints exist; what-if, NL query, forecast, MTM, annotations, embedded analytics all missing from router |
| ai-nlp | 48 | 908 | 🔴 Only foundational RAG/extraction/guardrails built. 20+ advanced features missing: denial prediction, clinical criteria, FHIR PA, paper EOB→835, fax splitting, consensus scoring, self-correction loops. |

### Top PRD gaps by risk

1. **core-platform — routers not mounted.** `auth_api_router`, audit router, notifications router, bank_holidays router exist but are NOT included in `api.py` / `main.py`. These subsystems are unreachable in a running service.
2. **ai-nlp — 48%.** The module ships a foundation, not a product. Denial prediction, clinical criteria matching, FHIR PA (CMS-0057-F), paper EOB→835, NLP auto-coding, consensus scoring, self-correction loops, batch document processing, fax bundle splitting, model version pinning — all absent.
3. **billing — 50-state compliance tables absent.** Prompt-pay deadlines, escheatment rules, clawback limitation rules, DIR fee service, spread pricing tracking, accounting adapters (QB/NetSuite/Sage/Xero), rebate pass-through — none implemented despite PRD listing them as "ships complete."
4. **dataiq — analytics surface missing.** What-if scenarios, natural language query, forecast API, prescriber profiling, annotation system, MTM targeting, data export API all missing from router.
5. **reclaimrx competitive gaps.** PRD §10 lists cross-tenant intelligence, predictive risk, bias monitoring, adversarial adaptation — models partially exist but no service logic or API endpoints.

---

## 4. Critical Issues (Ranked by Severity)

### CRITICAL (fix before any production load)

| ID | Finding | Category | File / Evidence |
|---|---|---|---|
| CR-01 | 5 of 6 end-to-end flows broken: no `bus.subscribe()` calls at module startup except pharmacy-directory | 13 | `reclaimrx/src/events/consumers.py:109` (routing dict never activated) |
| CR-02 | medical-claims PHI columns (`patient_member_id`, `rendering_provider_npi`, diagnosis codes) stored plaintext — HIPAA §164.312(a)(2)(iv) violation | 15 | `modules/medical-claims/src/models/tables.py` |
| CR-03 | No JWT authentication on medical-claims, prescriber-directory, edi-compliance routes; only tenant-UUID header check | 7 | `medical-claims/src/api/routes/*.py`, `prescriber-directory/src/api/dependencies.py`, `edi-compliance/src/api/generate.py` |
| CR-04 | `AuditMiddleware` and `TenantIsolationMiddleware` defined and tested but **never mounted in any `create_app()`** — LESSON-006 regression | 5, 7 | `core-platform/src/main.py:166-167` |
| CR-05 | 77 sync `def` routes in billing (and 24 in reclaimrx, 19 in payment-processing, 16 in drug-database, 17 in prescriber-directory) run synchronous DB I/O on an async FastAPI event loop | 11 | `billing/src/api/router.py`, `reclaimrx/src/api/router.py` |
| CR-06 | `statement_timeout` not set on any SQLAlchemy engine — runaway queries exhaust the pool | 11 | `shared/db/engine.py` |
| CR-07 | `billing/src/main.py` is 18 lines: `app = FastAPI(...)` with zero middleware, zero DLQ router, no `create_app()` factory. `reclaimrx` has no HTTP entry point at all. | 1, 5, 7 | `modules/billing/src/main.py`, `modules/reclaimrx/src/` |
| CR-08 | `edi-compliance/src/main.py:68-76` imports security middleware from `modules.core_platform.src.infrastructure.*` (wrong path) wrapped in `try/except: pass` — middleware is a **silent no-op** in production | 1, 5, 7 | `modules/edi-compliance/src/main.py:68-76` |
| CR-09 | `prescriber-directory/src/db/session.py` creates its own `sessionmaker` without `install_tenant_loader`; `Prescriber` model has no `tenant_id` column — no tenant isolation fence at all | 1, 7 | `modules/prescriber-directory/src/db/session.py:36` |
| CR-10 | No Azure Key Vault integration anywhere. All secrets (`JWT_SECRET`, `ENCRYPTION_KEY_ACTIVE`) load from raw env vars. Production blocker for HIPAA deployment to AKS. | 16 | `shared/config.py` |
| CR-11 | billing and payment-processing financial consumers have no `idempotent_handler` wrapper — duplicate event delivery will double-post AP, AR, or NACHA submissions | 14 | `billing/src/events/consumers.py` (stubs), `payment-processing/src/events/consumers.py` |
| CR-12 | edi-compliance test coverage is **15%** against `fail_under = 99` gate. All X12 generators/parsers (gen_278/837d/837i/837p/999, parse_271/277/278/834/999, validator) at 0%. Auto-Gate rule is currently hard-failing. | 9 | `modules/edi-compliance/.coverage` |
| CR-13 | CLAUDE.md status table is materially wrong — 8 fully-built modules listed as "Not yet implemented." Every agent reading CLAUDE.md before starting work is misled. | 4 | `CLAUDE.md` |

### HIGH

| ID | Finding | Category |
|---|---|---|
| H-01 | `edi-compliance/src/services/fhir_bridge.py:122` converts `Decimal` monetary amount to `float` in FHIR `allowedMoney.value` — financial-precision rule violation | 2, 7 |
| H-02 | `billing/src/events/publishers.py:15` and `edi-compliance/src/services/auto_posting.py:21` define local `EventBus` Protocol instead of using `shared.events.bus.EventBus` — architecture rule violation | 1 |
| H-03 | `shared/auth/dependencies.py:110` imports `_current_tenant` from `modules.core_platform.src._shim.db` — a `shared/` library depending on a specific module's internal shim | 1 |
| H-04 | Event catalog has 29 published event types with no contract doc; 24 of 42 existing catalog files use old snake_case filenames violating ADR-003 | 4 |
| H-05 | 3 modules (drug-database, billing, prescriber-directory) bypass `shared/config.py` with hardcoded `localhost` DB URL fallbacks and module-local sync `psycopg2` session factories | 1, 11, 16 |
| H-06 | No HIPAA SOP documentation beyond `backup-restore.md` — no access-control, workforce, contingency, or breach-notification SOPs | 15 |
| H-07 | Daily audit chain integrity verification job not implemented. `verify_audit_chain()` exists but no scheduled runner calls it. | 15 |
| H-08 | BAA tracking (PRD `prd-edi-compliance.md` §3.20) not implemented | 15 |
| H-09 | Weekly restore evidence missing: `infrastructure/scripts/tests/restore_evidence/` directory does not exist; 72-hour restoration claim is documented but unproven | 14 |
| H-10 | `RedisChallengeStore` and `RedisRevokedTokenRepo` make raw Redis calls with no circuit breaker — a Redis outage will lock all users out of authentication | 14 |
| H-11 | No transactional outbox pattern. If the app crashes between DB write and `exchange.publish()`, financial events (payment_batch, claim.ingested) are permanently lost | 14 |
| H-12 | No optimistic locking (`version_id_col` or `with_for_update()`) on billing or payment-processing models — concurrent batch submission can double-submit | 14 |
| H-13 | Health endpoints in every module except core-platform return static `{"status":"ok"}` with no DB or event-bus dependency check — Kubernetes readiness probes will false-positive on DB outage | 5 |
| H-14 | `medical-claims/src/services/accumulator_service.py:70` silently swallows accumulator update failures via broad `except Exception` — financial path error suppression | 2 |
| H-15 | 89 pharmacy-directory integration tests error at setup: `ModuleNotFoundError: No module named 'aiosqlite'` — missing from `pyproject.toml` | 2, 9 |
| H-16 | payment-processing golden NACHA test (`test_nacha_output_matches_golden`) fails because the generator embeds today's date — golden fixture needs a frozen-time fixture | 2, 9 |

### MEDIUM

| ID | Finding | Category |
|---|---|---|
| M-01 | 5 `quantize()` calls in `medical-claims/src/api/routes/analytics.py` and `services/denial_service.py` use default `ROUND_HALF_EVEN` instead of `ROUND_HALF_UP` | 7, 8 |
| M-02 | `rate_limiter.py` duplicated byte-for-byte across 3 modules + 2 variants; `security_headers.py` duplicated 3 times + 2 variants — ~700 LOC of drift-prone duplicate middleware | 3 |
| M-03 | Zero `selectinload` / `joinedload` usage anywhere — every ORM relationship traversal is a potential N+1 | 11 |
| M-04 | Slow query logger installed only in core-platform; 7 other modules are blind to slow queries at application level | 11 |
| M-05 | No CORS configuration on any module — relies solely on browser same-origin for cross-origin protection | 7 |
| M-06 | OpenAPI `/docs` and `/redoc` exposed in production by default — no module disables or auth-gates them | 4, 7 |
| M-07 | No `ondelete=` specified on any ForeignKey in billing or medical-claims models — RESTRICT by default, intent undocumented | 8 |
| M-08 | `processed_events` cleanup job not implemented (event-bus rule: `DELETE WHERE processed_at < NOW() - INTERVAL '7 days'`) | 15 |
| M-09 | `prescriber-directory/src/api/router.py:352-356` fires 5 sequential `COUNT(*)` queries for stats endpoint — should be a single `CASE` aggregate | 11 |
| M-10 | 4 built Phase 2 modules (billing, payment-processing, reclaimrx, reporting) missing README.md | 4 |
| M-11 | No ERD / schema diagram anywhere in `docs/` or `infrastructure/` — hurts onboarding and compliance audits | 4 |
| M-12 | 412 unused imports (F401) across modules + shared; 82 in production `src/` across 55 files | 2, 3 |
| M-13 | 18 broad `except Exception` in production code without `# noqa` rationale | 2 |
| M-14 | `test_coverage_boost.py` (1,173 lines) in medical-claims — coverage-inflating tests not named after behaviors | 3 |
| M-15 | `infrastructure/k8s/` and `infrastructure/terraform/` are empty — no production deployment artifacts | 16 |
| M-16 | `shared/config.py` has no `ENVIRONMENT` field; no conditional dev/staging/prod behavior possible | 16 |
| M-17 | `reporting` has no golden-master tests for generated financial outputs | 9 |
| M-18 | Zero cross-module event-bus E2E tests (publish → actual consumer invocation) across the entire platform | 9 |
| M-19 | Zero concurrent-access tests using `asyncio.gather` — accumulators, rate limit counters, session creation all unverified under contention | 9 |
| M-20 | `prescriber-directory` uses only in-memory dict cache for taxonomy; no Redis cache on NPI lookups | 11 |
| M-21 | Docker images use floating tags (`postgres:17`, `redis:7.4`, `rabbitmq:4-management`); Dockerfile `FROM python:3.13-slim` also floats on patch | 12 |
| M-22 | `psycopg2-binary` is deprecated; still in production because 3 modules use sync sessions | 12 |

### LOW

- L-01 `coverage.json` (135KB) untracked at repo root — belongs in `.gitignore`
- L-02 `tier3-situational/` agent directory exists but is empty — violates dead-code rule
- L-03 Integer PK in drug-database reference table (`tables.py:154`) — rule violation but reference data
- L-04 Inconsistent `main.py` vs `app.py` naming across modules
- L-05 numpy pinned `>=1.26` but 2.4.4 installed — verify numpy 2.x compat
- L-06 Two overlapping `[dev]` dependency sections in `pyproject.toml`
- L-07 Python 3.14 (Oct 2025) not yet planned for adoption — `<3.14` cap still in pyproject
- L-08 Lessons numbered non-chronologically in `docs/lessons-learned.md`

---

## 5. Version Currency Report

| Software | Pinned | Installed | Latest Stable 2026-04 | Status |
|---|---|---|---|---|
| Python | `>=3.13,<3.14` | 3.13.13 | 3.14.4 | 🟡 Intentional cap, migration window needed |
| PostgreSQL | `postgres:17` | 17 | 17.x (18 GA'd Sept 2025) | 🟢 Acceptable |
| Redis | `redis:7.4` | 7.4.0 | 8.0 | 🟢 Acceptable |
| RabbitMQ | `rabbitmq:4-management` | 4.x | 4.x | 🟡 Floating tag |
| FastAPI | `>=0.115` | 0.135.3 | ~0.135 | 🟢 Current |
| SQLAlchemy | `>=2.0.36` | 2.0.49 | 2.0.x | 🟢 Current |
| Pydantic | `>=2.10` | 2.12.5 | 2.12.x | 🟢 Current |
| Alembic | `>=1.14` | 1.18.4 | 1.18.x | 🟢 Current |
| Uvicorn | `>=0.32` | 0.44.0 | ~0.44 | 🟢 Current |
| asyncpg | `>=0.30` | 0.31.0 | 0.31.x | 🟢 Current |
| cryptography | `>=44.0` | 46.0.7 | ~46 | 🟢 Current |
| aio-pika | `>=9.5` | 9.6.2 | ~9.6 | 🟢 Current |
| redis client | `>=5.2` | 7.4.0 | ~7.x | 🟢 Current |
| xgboost | `>=3.2.0` | 3.2.0 | 3.2.x | 🟢 Current |
| scikit-learn | `>=1.8.0` | 1.8.0 | 1.8.x | 🟢 Current |
| numpy | `>=1.26` | 2.4.4 | 2.x | 🟡 Major version drift — tighten bound to `>=2.0` |
| openai | `>=1.50` | 2.31.0 | 2.x | 🟢 Current |
| `psycopg2-binary` | `>=2.9.11` | 2.9.11 | psycopg3 preferred | 🔴 Deprecated; migrate to `asyncpg`/`psycopg` |
| Dockerfile base | `python:3.13-slim` | — | `python:3.13.13-slim` | 🟡 Pin to patch or digest |

**CVE scan (pip-audit):** ✅ Clean — zero vulnerabilities in 2026-04-14 run.

**License audit:** ✅ Clean — no GPL/AGPL. All dependencies MIT / BSD / Apache-2.0.

---

## 6. Bloat Report

| Metric | Value |
|---|---|
| Total Python LOC (prod + tests, excl venvs/caches) | 115,931 |
| Total Python files | 910 |
| Files > 500 lines | 16 |
| Estimated bloat % | ~2% (2,100–2,500 removable LOC) |
| Committed `__pycache__` / `.pyc` | 0 (covered by .gitignore) |

### Top removal candidates

| Path | Action | LOC |
|---|---|---|
| `medical-claims/tests/unit/test_coverage_boost.py` | Rewrite as behavior-named tests or delete | 1,173 |
| `medical-claims/src/infrastructure/rate_limiter.py` | Move to `shared/middleware/`, delete local copy | 175 |
| `medical-claims/src/infrastructure/security_headers.py` | Same | 175 |
| `member-management/src/infrastructure/rate_limiter.py` | Same | 175 |
| `member-management/src/infrastructure/security_headers.py` | Same | 175 |
| `drug-database/src/infrastructure/rate_limiter.py` | Same (smaller variant) | 84 |
| `billing/src/utils/money.py` | Delete shim; import `shared.utils.money` directly | 13 |
| Phase 4 empty scaffold directories (44 dirs across 11 modules) | Remove until phase is active | n/a |
| 412 unused imports auto-fixable by `ruff check --fix --select F401` | Run ruff auto-fix | — |

### Files >500 lines (prod src)

| File | Lines | Concern |
|---|---|---|
| `reporting/src/services/report_library.py` | 1,082 | God class — 14 report types in one file |
| `billing/src/api/router.py` | 970 | Monolithic router — 20+ endpoints |
| `billing/src/models/tables.py` | 819 | Acceptable for model files |
| `reclaimrx/src/models/tables.py` | 795 | Acceptable |
| `reclaimrx/src/services/detection_rule_seeder.py` | 769 | Seed data embedded in service file |
| `reclaimrx/src/api/router.py` | 634 | Monolithic router |
| `core-platform/src/auth/service.py` | 631 | Should split user/role/mfa |

---

## 7. Documentation Report

| Category | Status |
|---|---|
| CLAUDE.md current | 🔴 Status table lists 8 built modules as "Not yet implemented" |
| Module READMEs | 🟡 Missing in billing, payment-processing, reclaimrx, reporting |
| PRD coverage | 🟢 PRDs exist for all 13 built modules; match implementation intent |
| OpenAPI autogen | 🟡 Works but exposed in production by default |
| ADRs | 🟡 3 present (monorepo layout, shim pattern, event naming); async session / event bus dual-mode / encryption provider missing |
| ERD / schema diagrams | 🔴 None exist anywhere |
| Event catalog | 🔴 Split-brain: 29 published types undocumented; 24 files use snake_case filenames violating ADR-003 |
| `.env.example` | 🟢 Comprehensive for shared config; module-specific DB URLs missing |
| SOPs | 🔴 Only `backup-restore.md` exists; no access-control, workforce, contingency, breach SOPs |
| Deployment runbook | 🔴 `infrastructure/k8s/` and `infrastructure/terraform/` empty |
| lessons-learned.md | 🟢 8 entries, actively maintained, rules propagation working |
| CHANGELOG | 🔴 Missing |
| Inline comments on complex logic | 🟡 Good in `nacha.py`, sparse in `remittance_835.py`, absent in `journal.py` |

---

## 8. Dependency Report

- **CVE scan:** clean (pip-audit, 2026-04-14)
- **License audit:** clean (MIT/BSD/Apache only)
- **Heavyweight packages all used:** xgboost (reclaimrx ML scoring), networkx (reclaimrx graph analysis), scikit-learn (reclaimrx), pgvector (ai-nlp embeddings), openai (ai-nlp RAG). No dead weight.
- **Deprecated:** `psycopg2-binary` still present because 3 modules run sync sessions. Eliminate by migrating billing / drug-database / prescriber-directory to async.
- **Supply chain risk:** Docker images not digest-pinned. For a $300M/yr platform, pin to `postgres:17.4`, `redis:7.4.2`, `rabbitmq:4.0-management`, `python:3.13.13-slim` at minimum.
- **Duplicate dev deps:** `[project.optional-dependencies] dev` and `[dependency-groups] dev` both exist. Consolidate to one.
- **numpy:** pinned `>=1.26` but installed 2.4.4 — tighten to `>=2.0` and verify numpy-2 API compatibility across sklearn/xgboost consumers.
- **Python 3.14:** released Oct 2025. Currently capped `<3.14`. Plan a migration window.

---

## 9. Wiring Map — Module-to-Module Status

| Module | entry | SecHdrs | RateLimit | DLQ | AuditChain | TenantMW | shared/events | Consumers registered at startup |
|---|---|---|---|---|---|---|---|---|
| core-platform | ✓ `create_app()` | ✓ | ✓ | ✓ | ✗ AuditMiddleware NOT in create_app | ✗ | ✓ | ✗ |
| billing | ✗ bare `app=FastAPI()` | ✗ | ✗ | ✗ | ✗ | ✗ | partial (local `EventBus` Protocol) | ✗ (stub handlers) |
| payment-processing | ✗ bare `app=FastAPI()` | ✗ | ✗ | ✗ | ✗ | ✗ | partial (shim) | ✗ |
| reclaimrx | ✗ **no entry point** | ✗ | ✗ | ✗ | ✗ | ✗ | partial (`_shim/events.py`) | ✗ (routing dict unused) |
| reporting | ✗ **no entry point** | ✗ | ✗ | ✗ | ✗ | ✗ | partial | ✗ |
| ai-nlp | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| dataiq | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| drug-database | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ |
| member-management | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ |
| pharmacy-directory | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ (2 topics) |
| prescriber-directory | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | partial | ✗ |
| medical-claims | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ |
| edi-compliance | ✓ | ✗ silent no-op | ✗ silent no-op | ✗ silent no-op | ✗ | ✗ | ✓ | ✗ |

**Only 1 of 13 modules has any consumers actually running in production.**

---

## 10. Integration Flow Results

| Flow | Producer | Consumer | Status |
|---|---|---|---|
| 1 — Claim-to-Cash | PARTIAL (topic mismatch: `payment_batch.generated` vs `.submitted`) | STUB (handlers are no-ops; no `bus.subscribe()`) | 🔴 BROKEN |
| 2 — Claim-to-Flag | PARTIAL (`fwa.claim_flagged` published via `_shim`, not EventEnvelope) | DEAD (neither reclaimrx nor ai-nlp subscribes to any topic) | 🔴 BROKEN |
| 3 — Member-to-Eligibility | PARTIAL (834 parser duplicated in edi-compliance + member-mgmt) | STUB (enrollment upload route raises 404 immediately) | 🔴 BROKEN |
| 4 — Drug-to-Pricing | ✓ Drug DB REST API complete | STUB (`medical-claims/src/clients/drug_database_client.py` is a TODO stub; billing has no client at all) | 🔴 BROKEN |
| 5 — Document-to-Data | PARTIAL (single OpenAI extraction path works) | BROKEN (no dual-parser, no consensus engine; classify endpoint is a placeholder) | 🟡 PARTIAL |
| 6 — EDI Round-Trip | ✓ All components built (837 gen, validator, 835 parse, auto_post_835) | BROKEN (`/parse/835` endpoint never calls `auto_post_835()`; billing has no consumer for `payment.auto_posted`) | 🔴 BROKEN |

**Root cause common to 5 of 6 flows: consumers are defined but `bus.subscribe()` is never called at module startup.**

---

## 11. Resilience Report

| Control | Status | Severity |
|---|---|---|
| Transaction boundaries (billing / payment-processing) | 🔴 No `async with session.begin()` found | HIGH |
| Automated backup tooling | 🟢 `backup.sh`, `restore.sh`, `verify_backup.py`, `backup-restore.md` all present | — |
| Weekly restore evidence | 🔴 `infrastructure/scripts/tests/restore_evidence/` missing — 72h restoration claim unproven | HIGH |
| RTO/RPO defined | 🟡 Implicit only (4h RPO / 72h RTO) | MEDIUM |
| RabbitMQ down: events lost? | 🔴 No transactional outbox. Pre-publish window unprotected. | HIGH |
| Redis down: graceful degrade? | 🔴 No circuit breaker on Redis calls. MFA / token revocation will crash. | HIGH |
| Azure OpenAI unreachable: fallback? | 🔴 No spaCy fallback. `AiNlpEventConsumer.handle_fwa_claim_flagged()` silently swallows failures. | MEDIUM |
| `idempotent_handler` on financial consumers | 🔴 Missing on billing, payment-processing, reclaimrx, ai-nlp, edi-compliance. Present on dataiq (3 usages) and member-management (manual). | HIGH |
| Optimistic locking | 🔴 No `version_id_col` or `with_for_update()` in billing/payment-processing | HIGH |
| Data corruption detection | 🟢 Audit hash chain works; gap on financial-table checksums | MEDIUM |

---

## 12. Compliance Checklist

### HIPAA Security Rule

| Control | Status | Evidence |
|---|---|---|
| §164.312(a) Access controls | 🔴 PARTIAL | core-platform has auth+RBAC; medical-claims / prescriber-directory / edi-compliance have no JWT auth |
| §164.312(b) Audit controls (tamper-evident) | 🟢 PASS | `AuditService.log()` + `compute_entry_hash()` wired and tested |
| §164.312(c) Integrity controls | 🟡 PARTIAL | Hash chain covers audit log only; no integrity check on claim records |
| §164.312(e) Transmission security TLS 1.3 | ⚠️ NOT VERIFIED | Assumed at Azure infra layer; no code-level enforcement |
| §164.312(a)(2)(iv) Encryption at rest | 🔴 PARTIAL | member-management and pharmacy-directory use `EncryptedString`; **medical-claims PHI is plaintext** |
| MFA required (2026 rule) | 🟢 PASS | TOTP + MFA gate; SMS disallowed |
| Session timeout 15 min | 🟢 PASS | `SessionService` enforces inactivity |
| Concurrent session limit 5 | 🟢 PASS | `MAX_ACTIVE_SESSIONS = 5` |
| Daily audit chain verification job | 🔴 FAIL | `verify_audit_chain()` exists but no scheduled runner |
| Weekly restore test | 🔴 FAIL | Script exists, no scheduled CI job, no evidence files |
| PHI access audit logging | 🟢 PASS | `@phi_access` decorator + `phi_access_log` table |
| Minimum necessary (PHI masking) | 🟢 PASS | `MemberService._mask_phi()` implemented |
| HIPAA SOPs written | 🔴 FAIL | Only `backup-restore.md`; no access/workforce/contingency/breach SOPs |

### 2026 CAA (Consolidated Appropriations Act)

| Requirement | Status |
|---|---|
| 100% rebate pass-through tracking | 🔴 Not implemented (rebate-management is Phase 4) |
| Spread pricing prohibition reporting | 🔴 Not implemented |
| PBM transparency reporting | 🟡 `reporting/src/services/financial_service.py` has `generate_caa_transparency_report` — partial |

### CMS-0057-F (FHIR Prior Authorization API)

| Requirement | Status |
|---|---|
| FHIR R4 PA API endpoint | 🟡 PARTIAL — `fhir_bridge.py` has X12↔FHIR translation for 278/271 |
| HL7 Da Vinci PAS conformance | 🔴 Not verified |
| Dedicated FHIR REST endpoint | 🔴 Not found — X12 278 is exposed via generate/parse API only |
| Real-time PA decision API | 🔴 Not implemented |

### NCPDP / X12

| Standard | Status |
|---|---|
| NCPDP D.0 | 🟡 Batch 1.2 transport present; full D.0 adjudication not in edi-compliance (belongs to adjudication-engine, Phase 4) |
| X12 835, 837P/I/D, 270/271, 276/277, 278, 834, 999/TA1 | 🟢 All generators/parsers present |
| AS2 transport | 🟢 Present |

### SOC 2

| Control | Status |
|---|---|
| Access control documentation | 🟡 Code implemented, no written SOP |
| Change management SOP | 🟡 Git workflow in CLAUDE.md, no formal SOP |
| Monitoring / alerting | 🟡 Slow query logging in 1 of 8 modules; DLQ monitoring partial |
| Audit trail completeness | 🟢 Hash chain + PHI access decorator |

### Data Retention

| Item | Status |
|---|---|
| Retention periods in PRD | 🟢 7 years for claims |
| Tenant `data_retention_days` column | 🟢 Default 2555 (7 years) |
| Automated purge job | 🟡 `purge_expired_report_files` only; no general claims purge |
| `processed_events` cleanup | 🔴 Not implemented |

---

## 13. Deferred Items (TODO / FIXME / stub)

All active TODO/FIXME comments are in `modules/medical-claims/` and represent unfinished cross-module integration:

| File | Line | Content |
|---|---|---|
| `medical-claims/src/clients/member_management_client.py` | 3, 33 | Replace stub with real HTTP calls |
| `medical-claims/src/clients/drug_database_client.py` | 3, 24, 32 | Replace stub; currently regex-only NDC validator |
| `medical-claims/src/clients/pharmacy_directory_client.py` | 3, 27 | Replace stub |
| `medical-claims/src/api/routes/claims.py` | 170 | Implement CSV/Excel parsing |
| `medical-claims/src/events/consumers.py` | 21, 29 | Wire `edi.837_received` consumer when EDI finalizes contract |
| `medical-claims/src/services/claim_service.py` | 261 | Wire to real `edi.837_received` event schema |

Additionally from `modules/core-platform/tasks/todo.md`:

- `swap-revoked-repo-redis` — `InMemoryRevokedTokenRepo` still in use
- `replace-standin-models` — shim models (`auth/_models.py`, `auth/_db.py`) may still exist
- `sms.wire-provider` — `NoOpSmsDelivery` (no actual SMS sending)
- `shared.auth.integration-reconcile` — shim `AuditContext` / `current_user` not yet replaced

---

## 14. Recommendations (Prioritized)

### Tier A — Fix before any portal launch (production blockers)

1. **Encrypt medical-claims PHI columns** at rest with `EncryptedString` (HIPAA §164.312(a)(2)(iv)). Write a migration.
2. **Add JWT auth** (`Depends(get_current_user)`) to every medical-claims, prescriber-directory, and edi-compliance route. No PHI/EDI endpoint should accept a bare `x-tenant-id` header.
3. **Mount `AuditMiddleware` and `TenantIsolationMiddleware`** in `core-platform/src/main.py:create_app()`. Add an integration test that asserts a POST request produces an audit row with non-empty `entry_hash` through the top-level app.
4. **Add `install_tenant_loader` + `tenant_id` column to prescriber-directory**, or explicitly document and test the global-reference-table decision.
5. **Fix `edi-compliance/src/main.py` middleware imports**: remove `try/except ImportError`, use the correct module path, and add an integration test that asserts `Strict-Transport-Security` header on responses.
6. **Add a `create_app()` factory with full middleware stack** to `billing` and `payment-processing`. Give `reclaimrx` and `reporting` entry points (or document them as library-only).
7. **Wire consumers at module startup.** In every module's `lifespan()`, iterate `CONSUMER_ROUTING.items()` and call `await bus.subscribe(topic, idempotent_handler(handler))`. Add a cross-module integration test that publishes an event via the real `InMemoryEventBus` and verifies the consumer fires.
8. **Replace local `EventBus` Protocol / `_shim/events.py`** in billing and reclaimrx with `shared.events.EventEnvelope`. Reconcile topic names (`payment_batch.generated` vs `.submitted`).
9. **Integrate Azure Key Vault**: wire `SecretClient` into `shared/config.py` with vault-first, env-fallback. Production blocker for AKS deployment.
10. **Convert billing, reclaimrx, payment-processing, drug-database, prescriber-directory sync routes to `async def`** and replace module-local sync `psycopg2` sessions with `shared.db.session.get_session`. Eliminate `psycopg2-binary` from prod deps.
11. **Set `statement_timeout`** (30s) on every SQLAlchemy engine via `connect_args`.
12. **Restore the edi-compliance test gate** — module is at 15% against `fail_under = 99`. All X12 generators/parsers at 0% coverage.

### Tier B — Fix before production

13. Add `idempotent_handler` to billing, payment-processing, reclaimrx, ai-nlp consumers.
14. Add optimistic locking (`version_id_col` or `with_for_update()`) to billing / payment-processing mutation paths.
15. Implement transactional outbox pattern in `shared/events/` for crash-safe publish.
16. Add circuit breaker wrapper around `RedisChallengeStore` / `RedisRevokedTokenRepo`.
17. Wire daily audit-chain verification job and weekly restore-evidence job.
18. Add `ROUND_HALF_UP` to 5 `quantize()` calls in `medical-claims/analytics.py` and `denial_service.py`.
19. Fix `edi-compliance/services/fhir_bridge.py:122` — use `str(b.monetary_amount)` not `float()`.
20. Implement BAA tracking table (prd-edi-compliance.md §3.20).
21. Write HIPAA SOPs: access-control review, workforce training, contingency plan, device/media controls, breach notification.
22. Create top-level `infrastructure/terraform/` (AKS + Key Vault + PostgreSQL Flexible Server) and `infrastructure/k8s/` manifests. Pin Docker images to minor+patch or SHA digest.
23. Gate OpenAPI `/docs` behind `ENVIRONMENT != production`.
24. Add CORS middleware to all modules with explicit allow-list.
25. Implement `processed_events` cleanup job.
26. Update CLAUDE.md status table — 8 modules incorrectly marked "Not yet implemented."
27. Add README.md to billing, payment-processing, reclaimrx, reporting.
28. Write the 29 missing event contract docs and rename 24 snake_case catalog files to dot-notation.
29. Add `install_slow_query_logger` to every module's `create_app()`.
30. Add `aiosqlite` to `pyproject.toml` to unblock 89 pharmacy-directory integration tests.
31. Fix `payment-processing` golden NACHA test with a frozen-time fixture.

### Tier C — Fix before Phase 5

32. Close ai-nlp PRD gap (48 → 80+): denial prediction, clinical criteria matching, FHIR PA, consensus scoring, self-correction loops, paper EOB→835, fax splitting, batch document processing.
33. Close billing PRD gap (70 → 85): 50-state compliance tables, DIR fee, spread pricing, accounting adapters.
34. Close dataiq PRD gap (62 → 80): what-if, NL query, forecast API, MTM targeting, annotations, embedded analytics.
35. Close reclaimrx competitive gaps (§10): cross-tenant intelligence, predictive risk, bias monitoring, adversarial adaptation.
36. Close core-platform gaps: webhooks, feature flags, SSO/SAML/OIDC, break-glass, circuit breaker wiring. Mount the 4 unmounted routers (auth_api_router, audit, notifications, bank_holidays).
37. Move `rate_limiter.py` and `security_headers.py` to `shared/middleware/`. Delete 5 local copies (~700 LOC).
38. Move `_current_tenant` contextvar out of `modules.core_platform.src._shim.db` into `shared.db.tenant_context`.
39. Add `selectinload`/`joinedload` to every ORM relationship traversal; add query-counter pytest fixture; audit each service for N+1.
40. Add cross-module event-bus E2E tests (publish via real `InMemoryEventBus` → verify consumer side effect).
41. Add concurrent-access tests (`asyncio.gather`) on accumulator apply, session creation, rate-limit counters.
42. Add golden-master tests to reporting; property tests to member-management, pharmacy-directory, drug-database, medical-claims.
43. Implement X12 275 clinical attachments (edi-compliance) and EDI-specific RBAC.

### Tier D — Tech debt for ongoing maintenance

44. Delete `medical-claims/tests/unit/test_coverage_boost.py` (1,173 lines) and rewrite as behavior-named tests.
45. Run `uv run ruff check --fix --select F401` across all modules.
46. Narrow 18 broad `except Exception` in production code; add rationale comments where broad catch is intentional.
47. Remove 44 empty Phase 4 scaffold directories until those phases are active.
48. Add ERD / schema diagram (PlantUML or Mermaid) for core, billing, member schemas.
49. Add CHANGELOG.md distinguishing releases from build sessions.
50. Add ADRs for async session strategy, dual-mode event bus, encryption provider pattern.
51. Plan Python 3.14 migration window.
52. Tighten `numpy>=2.0` lower bound.
53. Consolidate duplicate `[dev]` dep sections in `pyproject.toml`.
54. Add `coverage.json` to `.gitignore`; delete or populate `tier3-situational/`.

---

## Final Note

The platform has **good bones**: the `shared/` library is right, the financial models are right, the audit primitives are right, and the test discipline on unit/integration is healthy. What is missing is the last mile — the integration layer that turns correct components into a correct system. LESSON-006 identified this exact pattern at the middleware level in 2026-04-13; the audit today finds the same pattern at the **event-bus and cross-module HTTP layer**. Until `bus.subscribe()` runs at startup and the inter-module HTTP clients become real, this is a collection of well-built modules, not a production PBM platform.

**Estimated effort to reach production-readiness** (Tier A + Tier B): 6–8 builder-weeks, concentrated on wiring rather than new features.

— *End of audit.*
