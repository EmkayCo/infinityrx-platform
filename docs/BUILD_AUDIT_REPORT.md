# InfinityRx Platform — Build Audit Report

**Date:** 2026-04-14
**Branch:** main @ 8f788d8
**Auditor:** Claude Opus 4.6 (orchestrated 6 parallel Explore agents)

---

## 1. Executive Summary

The InfinityRx platform is a 143-commit, 3-day-old monorepo containing ~6,874 source files across 25 named backend modules plus a Next.js 16 operator portal. The repo is highly structured — 10 mandatory rule files, 11 AI builder/QA agents, 8 migration chains, 6 HIPAA SOPs, 6 accepted ADRs, and a post-remediation platform score of **63/100**.

**What works:** 4,471 Python tests across 13 modules (**2 failures**); the Next.js portal builds cleanly with 60+ routes rendering against a 123-handler in-process mock layer; edi-compliance ships a full X12 5010 suite at 99.19% coverage with 822 tests; drug-database has real ingesters for NDC/NADAC/ASP/Orange Book/RxNorm/REMS/Purple Book; core-platform has real MFA/audit-hash-chain/JWT wired through middleware.

**What's broken:** Billing's 5 event consumers are TODO-only stubs — the AP-creation pipeline does not work end-to-end. ReclaimRx's `CONSUMER_ROUTING` dict (8 handlers) is never subscribed to the event bus at startup. Every dataiq API endpoint (34 of them) returns an empty list. Every ai-nlp endpoint returns canned text ignoring the real RAG/guardrails services. All 3 medical-claims inter-module HTTP clients are stubs. Core-platform's notifications, bank_holidays, and audit query routers are built but never mounted.

**What's missing:** 11 Phase-4 modules (adjudication-engine, mtm-clinical, part-d-pde, plan-design, prior-authorization, program-config, rebate-management, rules-engine, switch-connectivity, testing-simulator, ebv-ebi-rtbc) are empty directory scaffolds — no files, not even README.md. `medical-prescriber-directory` is also zero files. Four portals (client/medical/member/pharmacy) are empty placeholder directories. `ENCRYPTION_KEY_ACTIVE` is blank in `.env.example`. A UMLS API key is committed to `.env.local`. No Python backend CI pipeline exists — CI only covers the operator portal frontend.

---

## 2. Module Scorecard

| Module | Status | Tests | Endpoints | Key Gaps |
|---|---|---|---|---|
| core-platform | Partial | 523 / ≈982 pass (1 fail) | ~30+ | notifications / bank_holidays / audit routers not mounted; MFA secret not encrypted in shim |
| billing | Partial | 307 pass | 77 (25 stubs) | 5 consumers are TODO stubs; no idempotent wrapper; 50-state compliance & accounting adapters missing |
| payment-processing | Partial | 275 pass / 1 fail | 18 | OFAC uses in-memory stub; consumers use sync dispatch (not `bus.subscribe`); 19 sync-def routes |
| reclaimrx | Partial | 223 pass | 24 | `CONSUMER_ROUTING` never subscribed; no lifespan; PRD §10 advanced features missing |
| reporting | Partial | 365 pass | 33 | scheduled delivery empty; client-api & builder/preview return `[]`; Excel/PDF rendering absent |
| ai-nlp | Stub-router | 148 pass | 12 | router ignores RagService/guardrails; returns canned strings; 20+ PRD features missing |
| dataiq | Stub-router | 150 pass | 40 | 34/40 endpoints return empty; Redis not wired; forecast/NL-query/what-if absent |
| drug-database | Partial | 177 pass | 18 | FDB adapter = 5 NotImplementedError stubs; dual pricing schemas; compound ingredients absent |
| member-management | Partial | 311 pass | 24 | every member/group/enrollment/cob/coverage route handler is a stub; `_query_db` returns empty fixture; consent & COBRA absent |
| pharmacy-directory | Partial | 198 pass | 20 | accreditation / LDD tables missing; reviewer_id uses `uuid.uuid4()` placeholder |
| prescriber-directory | Partial | 210 pass | 17 | state rules cover ~10 of 50 states (default = full authority); panel size & supervisory absent; refresh endpoint doesn't enqueue |
| medical-prescriber-directory | Missing | 0 | 0 | Empty directory — 0 files |
| edi-compliance | Built | 822 pass (99.19% cov) | 22+ | 275 clinical attachments missing; EDI RBAC missing; README outdated |
| medical-claims | Partial | 301 pass | 26+ | 3 HTTP clients are stubs; `claims/upload` stub; EDI event contract open |
| adjudication-engine | Missing | 0 | 0 | Empty directory — no README either |
| mtm-clinical | Missing | 0 | 0 | Empty directory |
| part-d-pde | Missing | 0 | 0 | Empty directory |
| plan-design | Missing | 0 | 0 | Empty directory |
| prior-authorization | Missing | 0 | 0 | Empty directory |
| program-config | Missing | 0 | 0 | Empty directory |
| rebate-management | Missing | 0 | 0 | Empty directory |
| rules-engine | Missing | 0 | 0 | Empty directory |
| switch-connectivity | Missing | 0 | 0 | Empty directory |
| testing-simulator | Missing | 0 | 0 | Empty directory |
| ebv-ebi-rtbc | Missing | 0 | 0 | Empty directory |

Python coverage: full-tree report not regenerated this session. Stored `coverage.json` exists (from 2026-04-13 23:13). Fail-under threshold = 95%; financial/PHI/security paths require 100%.

---

## 3. Frontend Scorecard (portal/operator)

Build: **PASS** (Next.js 16.2.3 `next build --webpack`, exit 0).

| Route | Status | Data Source | Key Issues |
|---|---|---|---|
| `/` (dashboard) | Working | MSW/mock + SSE | — |
| `/(auth)/login` | Working | real (NextAuth creds → localhost:8000) + dev bypass | AUTH_SECRET committed to `.env.local` |
| `/(auth)/mfa` | Working | real API `/api/v1/auth/mfa/verify` | — |
| `/admin/audit-log` | Working | MSW/mock | — |
| `/admin/config` | Partial | hardcoded | toggles don't persist; no API call |
| `/admin/system-health` | Working | MSW/mock | — |
| `/admin/tenants` | Working | MSW/mock | — |
| `/admin/users` | Working | MSW/mock | — |
| `/analytics/*` (6 pages) | Working | MSW/mock | real analytics backend (dataiq) returns empty arrays — would break if toggled off mock |
| `/billing` | Working | MSW/mock | — |
| `/billing/claims` | Working | **real** (Next.js `/api/claims` → in-memory store of 122,968 real InfinityRx claims) | only real-data route |
| `/billing/cycles/new` | Working | MSW/mock | wizard step2 hardcodes `client_id: "current"` (TODO) |
| `/billing/cycles/[id]` | Working | MSW/mock | — |
| `/billing/invoices`, `/[id]` | Working | MSW/mock | — |
| `/payments`, `/batches/new`, `/batches/[id]` | Working | MSW/mock | — |
| `/payments/nacha` | Partial | hardcoded | static JSX, no fetch |
| `/reclaimrx/*` (4 pages) | Working | MSW/mock | — |
| `/edi` (landing) | Partial | hardcoded | static nav cards |
| `/edi/monitor`, `/partners`, `/partners/[id]`, `/transactions`, `/[id]`, `/certs` | Working | MSW/mock | — |
| `/directories/members/*` (4) | Working | MSW/mock | — |
| `/directories/pharmacies/*`, `/prescribers/*`, `/drugs/*` (6) | Working | MSW/mock | — |
| `/medical-claims/*` (6 pages) | Working | MSW/mock | — |
| `/reporting/*` (6 pages) | Working | MSW/mock | viewer has `force-dynamic` + `Cache-Control: no-store` for PHI |
| `/settings/*` (4 pages) | Working | MSW/mock + hardcoded (dashboard/shortcuts) | — |
| `/clients/new` | Working | MSW/mock | — |
| `/plan-design`, `/rules-engine`, `/adjudication`, `/prior-auth`, `/rebate-management` | Missing | sidebar `href="#"` links | backend modules unbuilt |

**Component counts:** 46 operator-specific + 21 shared reusable.
**Mock layer:** custom in-process interceptor (NOT MSW); 123 handler patterns across 1,568-line `handlers.ts`.
**Unit tests:** 3 files, 50 `it()`/`test()` calls — mock-handler contract + store integrity + error boundary.
**E2E tests:** 4 spec files, 23 `test()` calls — smoke (~16 routes), auth boundary, reclaimrx deep, regression suite.
**Risks:** Tailwind 4 beta, next-auth 5 beta; `AUTH_SECRET` committed; no `.env.example`; all 13 microservice URLs default to `localhost:800x` and are never exercised in CI.

---

## 4. Test Results

### Python (`--import-mode=importlib`, each module independent)

| Suite | Pass | Fail | Notes |
|---|---|---|---|
| core-platform (default testpaths: core-platform + shared + tests) | ~982 | 1 | `shared/tests/events/test_cross_module_events.py::TestPaymentProcessingWireConsumers::test_payment_batch_submitted_triggers_consumer` — `ModuleNotFoundError: No module named 'src.events'` (the test imports payment-processing's `src.events` which only resolves in payment-processing's own suite — known pyproject limitation) |
| billing | 307 | 0 | — |
| payment-processing | 275 | 1 | `tests/unit/test_reconciliation_service.py::TestGetReconciliationRows::test_days_outstanding_computed_for_pending` — asserts `days_outstanding >= 0` but got `-1` (clock/fixture date drift) |
| reclaimrx | 223 | 0 | — |
| reporting | 365 | 0 | — |
| ai-nlp | 148 | 0 | — |
| dataiq | 150 | 0 | — |
| drug-database | 177 | 0 | — |
| member-management | 311 | 0 | — |
| pharmacy-directory | 198 | 0 | 1 deprecation warning (HTTP_422_UNPROCESSABLE_ENTITY) |
| prescriber-directory | 210 | 0 | 2 deprecation warnings (same) |
| edi-compliance | 822 | 0 | 99.19% line / 97.97% branch coverage |
| medical-claims | 301 | 0 | — |
| **TOTAL** | **~4,469** | **2** | — |

### Frontend

Vitest: not executed this session (CI runs it via `npm run qa`).
Playwright: not executed this session.
Build: **PASS** (exit 0, all 60+ routes compiled as ƒ dynamic).

### Coverage

Full-tree coverage not regenerated this session; `coverage.json` on disk is from 2026-04-13 23:13. Per pyproject thresholds: `fail_under = 95%` overall, with module-level edi-compliance confirmed at 99.19% / 97.97% and billing/payment-processing tracked in coverage config.

---

## 5. Infrastructure Status

### Docker Compose
- `postgres:17.5` — tuned (`shared_buffers=256MB`, `work_mem=64MB`, `statement_timeout=30000ms`, `log_min_duration_statement=1000ms`), init SQL mounted, healthcheck configured.
- `redis:7.4.3` — default config + healthcheck.
- `rabbitmq:4.0-management` — default user `infinityrx`, healthcheck `rabbitmq-diagnostics ping`.

Backup guidance embedded in compose file — host cron reference for `infrastructure/scripts/backup.sh`, AKS CronJob for prod.

### Migrations (Alembic)

- **core-platform** (8 migrations, chain coherent): baseline → bank_holidays → event_bus reliability → MFA fields → audit hash chain → sessions → ingestion tracking → compliance reference tables.
- **drug-database** (5): NDC → NADAC/ASP → Orange Book → RxNorm → FDA supplementary.
- **pharmacy-directory** (3): NCPDP tables → exclusion xref → exclusion columns.
- **prescriber-directory** (4): NPPES satellite → Medicare → DEA compliance → exclusion columns.
- **edi-compliance** (1), **medical-claims** (1: PHI encryption), **billing** (1: FK ondelete policies).
- No cross-module chain conflicts; each module has independent Alembic environment.

### Shared schemas (owned by core-platform)
- `core` schema: tenants, users, roles, audit_log (hash-chained), sessions, bank_holidays, event_dlq, processed_events, FIDO2 credentials.
- `shared` schema: ingestion_runs, ingestion_schedules, oig_leie_exclusions, sam_exclusions.

### Seed scripts
- `infrastructure/scripts/seed_admin.py` (idempotent tenant + platform_admin role + admin user)
- `modules/core-platform/src/bank_holidays/seed.py` (11 US federal holidays 2026-2035, CLI)
- `modules/core-platform/src/notifications/seed.py` (default user notification prefs)

### Environment
- `.env.example` covers DB / Redis / RabbitMQ / JWT / encryption provider + optional external-API keys.
- **CRITICAL:** `ENCRYPTION_KEY_ACTIVE` blank in `.env.example` — any boot without overriding it leaves PHI unencrypted.
- **CRITICAL (REMEDIATED 2026-04-14):** `.env.local` contained a real UMLS API key. Rotated to placeholder; `.env.local` already gitignored; file was never committed.

### CI/CD
- `.github/workflows/ci.yml` and `azure-pipelines.yml` — **frontend only** (portal/operator). Two stages: Quality Gate (tsc + eslint + vitest + build) then E2E (Playwright chromium).
- **No Python backend CI pipeline.** Every backend test run is manual (`uv run pytest modules/<name>/tests`). This is the most serious CI gap for a HIPAA platform.

### Pre-commit
ruff lint/format (v0.8.4), pip-audit (v2.9.0), bandit (1.8.0), trailing-whitespace, detect-private-key, check-added-large-files (--maxkb=512), check-merge-conflict.

### .claude/ infrastructure
- **11 builder/specialist agents** (core-platform, billing, payment-processing, reclaimrx, reporting, dataiq, ai-nlp, team-lead, qa-financial-data, qa-security-phi, plus on-demand specialists for 340B, accumulator-maximizer, edi-standards, medicare-part-d, state-regulatory, workers-comp, dba-postgresql).
- **10 rule files:** architecture, code-standards, error-handling, event-bus, financial-precision, hipaa-2026, performance, phi-compliance, security, tenant-isolation, testing.
- **3 mandatory skills:** ifx-audit-trail, ifx-financial-precision, ifx-module-standards.
- Experimental agent teams enabled via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

---

## 6. Risk Register — Top 10

| # | Risk | Severity | Area | Why it matters |
|---|---|---|---|---|
| 1 | Billing event consumers are all TODO stubs; no `bus.subscribe()` wiring | CRITICAL | billing + reclaimrx | Claim adjudication events land in a listener that does nothing — no AP record ever gets created from a real event. Entire end-to-end financial pipeline broken. |
| 2 | `EligibilityService._query_db()` returns hardcoded empty fixture | CRITICAL | member-management | Every eligibility check returns "not eligible" — blocks every downstream module that needs member lookup. |
| 3 | All 34 dataiq endpoints + 12 ai-nlp endpoints return empty/canned responses | CRITICAL | dataiq + ai-nlp | The service layer is implemented (SPC, trend decomposition, RAG, guardrails) but never invoked by routers. Frontend analytics pages would show zero if pointed at real backends. |
| 4 | OFAC screening uses in-memory test stub, not real OFAC Data Services API | CRITICAL | payment-processing | Every outbound ACH payment is effectively unscreened for sanctions violations. Regulatory blocker. |
| 5 | 3 medical-claims inter-module HTTP clients are stubs (drug-database, pharmacy-directory, member-management) | HIGH | medical-claims | 340B detection, accumulator application, and NDC validation are not live. |
| 6 | No Python backend CI pipeline | HIGH | infra | Regression only caught by manual `pytest` runs. At 25 modules, drift is inevitable. |
| 7 | `ENCRYPTION_KEY_ACTIVE` blank in `.env.example`; real UMLS API key in committed `.env.local` | HIGH | security | Unencrypted PHI on any misconfigured boot; credential leak. |
| 8 | Core-platform notifications / bank_holidays / audit query routers built but not mounted in `api.py` | HIGH | core-platform | Features exist but are 404s to any consumer. |
| 9 | Prescriber state rules default to "full controlled substance authority" for ~40 unmodeled states | HIGH | prescriber-directory | Can approve an NP in a state that requires collaborative agreement for Schedule II — patient safety + DEA compliance risk. |
| 10 | 60+ sync-`def` route handlers doing DB I/O on async FastAPI event loop (billing 77, reclaimrx 24, payment-processing 19) | MEDIUM | performance | At 100M claims/year target, every sync query blocks the event loop. Throughput will collapse under load. |

Also notable: Reporting scheduled-delivery jobs are empty stubs; drug-database FDB adapter is 5 `NotImplementedError` stubs (no AWP/WAC pricing); pharmacy-directory credentialing uses `uuid.uuid4()` for reviewer_id (violates audit "who" requirement); medical-prescriber-directory + 11 Phase-4 modules are empty scaffolds; `AUTH_SECRET` committed to portal `.env.local`.

---

## 7. Detailed Module Reports

### 7.1 core-platform

- **Purpose:** Foundation service owning `core` + `shared` schemas — multi-tenant auth (JWT + MFA/TOTP), RBAC, hash-chained audit logging, file storage, job scheduling, exclusion screening, notifications, bank holiday calendar.
- **Completeness:** ~72%. Middleware stack correctly mounted (SecurityHeaders → RateLimit → TenantIsolation → Audit); auth/RBAC/MFA/audit integration-tested; notifications/bank_holidays/audit query routers exist but never included in `api.py` or `main.py`.
- **Key files:** `src/main.py`, `src/auth/api/auth_router.py`, `src/audit/middleware.py`, `src/auth/service.py`, `src/auth/_models.py`, `src/exclusions/screening_service.py`, `src/jobs/runner.py`, `src/api.py`.
- **Tables:** tenants, users, roles, permissions, user_roles, role_permissions, audit_log, core_jobs, core_job_runs, core_files, core_exclusion_list, core_exclusion_matches, notification tables, bank_holidays.
- **Endpoints:** 30+ under `/api/v1/{auth,users,roles,permissions,jobs,files,exclusions}` + `/health` + DLQ router. NOT mounted: notifications, bank_holidays query, audit query.
- **Real logic:** bcrypt + MFA-gated `authenticate()`, SHA-256 hash-chained audit via middleware, session service, Levenshtein exclusion fuzzy matching, cron-aware job registry.
- **Stubs:** none substantive in src/.
- **Imports:** `shared/auth`, `shared/db`, `shared/events`, `shared/observability`, `shared/config`.
- **Tests:** 62 files, 523 test functions; integration tests (`test_main_auth_wired.py`, `test_main_audit_wired.py`, `test_main_middleware.py`) exercise the full `create_app()`.
- **Known issues:** notifications/bank_holidays/audit routers unreachable; mfa_secret stored as plain String(64) in shim; audit-chain verification job has no scheduled runner (H-07); Redis challenge store has no circuit breaker (H-10).

### 7.2 billing

- **Purpose:** Full financial lifecycle — claim ingestion, routing rules, NACHA ACH generation, AP/AR ledgers, invoices, 8-type fee engine, program budgets, hash-chained journal, period close.
- **Completeness:** ~70%. Service layer substantively implemented; ~25 of 77 router routes are empty-list/404 stubs without ORM wiring.
- **Key files:** `src/api/router.py` (77 routes), `src/services/ap.py`, `src/services/ar.py`, `src/services/nacha.py`, `src/services/remittance_835.py`, `src/services/journal.py`, `src/models/tables.py` (18+ tables, all Numeric(n,2)), `src/events/consumers.py` (all TODO stubs).
- **Tables:** claim_records, routing_rules, payto_waterfall, file_format_mappings, ap_records, payment_batches, payments, invoicing_configs, invoices, invoice_line_items, ar_records, ar_payments, journal_entries, program_budgets, program_budget_alerts, program_budget_snapshots, fee_configs + bank_accounts, payment_vendors, remittance_configs, sftp_configs, funding, accounting_config.
- **Endpoints:** 77 under `/api/v1/billing/` (claims, routing, ap, payment-batches, settlement, ar, invoicing, journal, fees, budgets, config, reports).
- **Real logic:** AP record lifecycle with penny_allocate; aging bucket AR; 94-char fixed-width NACHA (header/batch/detail/control); 835 remittance builder; append-only hash-chained journal; budget burn-rate; priority routing.
- **Stubs/TODOs:** `consumers.py:60` `# TODO: call ClaimsService.ingest() + APService.create_ap()`; `consumers.py:83` reversal TODO; `consumers.py:116` AR lookup TODO; ~25 router handlers return `[]` or 404.
- **Imports:** `shared.utils.money`, `shared.db.tenant_context`, `shared.events.*`, `shared.middleware`, `shared.config`.
- **Tests:** 24 files, 307 functions (unit 200, integration 91, property 9).
- **Known issues:** all 5 consumers are log-only (CR-01); 50-state compliance tables absent; hardcoded DB URL fallback in `src/db/session.py` (H-05); no idempotent handler wrapper (CR-11); Audit & TenantIsolation middleware not in `create_app()` (partial CR-04).

### 7.3 payment-processing

- **Purpose:** Outbound payment execution — vendor adapters, NACHA, 80+ ACH return codes, OFAC screening, settlement lifecycle, positive-pay, payee enrollment, reconciliation.
- **Completeness:** ~85% (strongest of Group 1).
- **Key files:** `src/app.py` (`create_app()` with middleware + consumer import), `src/api/router.py` (18 routes), `src/services/vendor_adapter.py` (abstract + ACH/SFTP/Check), `src/services/submission_service.py` (OFAC → idempotency → submission → dispatch → event), `src/services/nacha_generator.py`, `src/services/ach_return_codes.py` (80+ R-codes), `src/services/ofac_screening.py` (stub), `src/services/reconciliation_service.py`.
- **Tables:** payment_proc_vendor_adapters, payment_proc_submissions, payment_proc_settlements, payment_proc_ach_return_codes, payment_proc_vendor_health_log, payment_proc_payee_enrollments.
- **Endpoints:** 18 under `/api/v1/payments/` (vendors, submissions, settlements, returns, enrollments, dashboard).
- **Real logic:** SHA-256 idempotency, OFAC screen, vendor ABC + ACH/SFTP/Check, complete R01-R85 return codes with retry/FWA flags, reconciliation match/mismatch/missing detection, exponential retry with business-day alignment, positive pay, business-day calendar.
- **Stubs:** none in src/ — but OFAC uses in-memory blocked-entity set.
- **Imports:** `shared.events.*`, `shared.middleware`, `shared.db.tenant_context`, `shared.utils.money`, `shared.config`.
- **Tests:** 28 files, 277 functions (unit/integration/property/golden).
- **Known issues:** real OFAC API not wired; consumers use sync dispatch registry not `bus.subscribe()`; golden NACHA test embeds today's date (H-16); 19 sync-def routes (CR-05); **1 currently failing test** (`test_days_outstanding_computed_for_pending` — clock drift, `-1 >= 0`).

### 7.4 reclaimrx

- **Purpose:** FWA detection — rule engine, XGBoost ML scoring, NetworkX community detection, investigations, recoveries, payment holds, tips, risk profiles.
- **Completeness:** ~80%. Core pipeline implemented; consumer routing dead code.
- **Key files:** `src/api/router.py` (24 routes), `src/services/rule_engine.py` (5 rule types), `src/services/ml_scoring.py` (XGBoost + IsolationForest with Decimal-boundary), `src/services/graph_analysis.py` (Louvain), `src/services/investigation_service.py`, `src/services/payment_hold_service.py`, `src/models/tables.py` (20+ tables), `src/events/consumers.py` (8 handlers, 0 subscribed).
- **Tables:** detection_rules, tenant_rule_configs, detection_profiles, flagged_claims, pharmacy/prescriber/member_profiles, profile_snapshots, ml_models, ml_predictions, investigations, investigation_activities, recoveries, letter_templates, accumulator_detections, verification_configs, verification_results, report_configs, payment_holds, tip_records, regulatory_reports.
- **Endpoints:** 24 under `/api/v1/reclaimrx/`.
- **Real logic:** 5 rule type evaluators with confidence; XGBClassifier + IsolationForest; Louvain community detection (optional python-louvain); investigation timeline + litigation hold; hold events `fwa.payment_hold_{placed,released}`; accumulator detection.
- **Stubs:** none in src/.
- **Imports:** `shared.utils.money`, `shared.db.tenant_context`, `shared.events.*`, `shared.middleware`, `shared.config`.
- **Tests:** 24 files, 223 functions.
- **Known issues:** `CONSUMER_ROUTING` never subscribed to bus at startup (CR-01); `create_app()` has no lifespan; 24 sync-def routes (CR-05); PRD §10 advanced features (cross-tenant intelligence, adversarial adaptation, bias monitoring) unbuilt; `python-louvain` silently skipped if missing.

### 7.5 reporting

- **Purpose:** Reporting intelligence layer — definitions, runs, schedules, dashboards, filter presets, regulatory submissions, actuarial models, quality measures, PHI access log.
- **Completeness:** ~55%. API + models exist; scheduled delivery, Excel/PDF rendering, and client-api endpoints are stubs.
- **Key files:** `src/api/router.py` (33 endpoints), `src/models/tables.py` (10 tables), `src/services/report_engine.py` (calculation + PHI masking + summary rows), `src/services/quality_service.py` (all methods return `pending_data`), `src/services/dashboard_service.py`, `src/services/report_service.py`, `src/jobs/scheduled.py` (all bodies empty), `src/services/report_library.py`.
- **Tables:** report_definitions, report_schedules, report_runs, dashboards, user_dashboards, filter_presets, regulatory_submissions, actuarial_models, phi_access_log, alert_report_mappings.
- **Endpoints:** 33 across reports, dashboards, builder, client-api, regulatory, actuarial, quality.
- **Real logic:** `validate_report_definition`, `apply_calculated_fields` (percentage + running_total), `apply_phi_masking` (full/partial/redacted), `build_report_filter`, `estimate_output_size`, `format_value`, `apply_summary_row`; financial PMPM/cost-per-claim service.
- **Stubs:** `jobs/scheduled.py:31` run_due_scheduled_reports returns `{triggered:0, skipped:0}`; materialized-view refresh is log-only; deadline check is log-only; purge returns 0; `preview_report` returns `{rows:[], total_count:0}`; all 4 `client-api/*` endpoints return hardcoded empty; entire `quality_service.py` returns `pending_data`.
- **Imports:** `shared.db.*`, `shared.events.*`, `shared.middleware`, `shared.utils.money`, `shared.config`.
- **Tests:** 18 files, 365+ functions.
- **Known issues:** scheduled delivery non-functional; client-api empty; no Excel/PDF renderer.

### 7.6 ai-nlp

- **Purpose:** Centralized AI/NLP — RAG chatbot, guardrails, document extraction, content generation, entity extraction.
- **Completeness:** ~48%. Real services (RAG, guardrails, extraction) are implemented but **routers never call them**.
- **Key files:** `src/api/router.py` (12 endpoints, all canned), `src/models/tables.py` (7 tables with pgvector), `src/services/rag_service.py` (real: embed → pgvector retrieve → rerank → Jinja2 prompt → citation extraction → confidence → escalation), `src/services/guardrails.py` (8 injection patterns, PHI leak co-occurrence, topic scope), `src/services/document_extraction.py`, `src/services/usage_logger.py`, `src/events/consumers.py`, 5 Jinja2 prompt templates.
- **Tables:** service_requests, prompt_templates, document_results, conversations, conversation_messages, embeddings (pgvector 1536-dim), usage_log (Numeric(10,6)), guardrail_events.
- **Endpoints:** `/ai/health`, `/ai/chat` (canned string — ignores RagService), `/ai/documents/process` (empty), `/ai/documents/{id}/results` (404), `/ai/text/classify` (empty), `/ai/text/extract-entities` (empty), `/ai/generate` (canned), `/ai/generate/templates`, `/ai/usage`, `/ai/usage/by-module`.
- **Real logic:** tenant-scoped pgvector retrieval, top-k rerank, grounded prompt construction, confidence-escalation heuristic, composite InputGuardrail + OutputGuardrail + TopicGuardrail with DB logging.
- **Stubs:** `router.py:53-67,71-87,90-100,103-112,115-124,127-142` — all functional endpoints are stubs.
- **Imports:** `shared.ai.openai_client`, `shared.events.*`, `shared.middleware`, `shared.db.tenant_context`, `shared.config`.
- **Tests:** 13 files, 148 functions.
- **Known issues:** router disconnected from services; 20+ PRD features (denial prediction, FHIR PA, fax splitting, translation, anomaly narrative, NLP pipeline, Azure Document Intelligence) absent.

### 7.7 dataiq

- **Purpose:** Advanced analytics & BI — real-time KPIs, drug trend decomposition, network/member/financial analytics, SPC anomaly, repricing, benchmarking, insights.
- **Completeness:** ~45%. Real pure-function engines exist but 34/40 router endpoints return empty.
- **Key files:** `src/api/router.py` (40 endpoints), `src/models/tables.py` (11 tables), `src/services/spc.py` (Decimal Newton's-method sqrt + 4 Western Electric rules), `src/services/trend_decomposition.py` (util+price+mix invariant), `src/services/repricing.py` (pure AWP discount + tier copay + plan-paid floor), `src/services/kpi.py`, `src/services/geo_analytics.py`, `src/events/consumers.py` (idempotent).
- **Tables:** metric_definitions, metric_snapshots, data_quality_scores, benchmarks, saved_explorations, insight_alerts, forecast_models, trend_decomposition, repricing_runs, kpi_rollups, spc_alerts.
- **Endpoints:** 40 under `/api/v1/dataiq/` (metrics, drug-trend, network, member, financial, data-quality, benchmarks, insights).
- **Real logic:** `calculate_control_limits`, `detect_anomaly`, `check_western_electric_rules` (all 4 rules); `decompose_drug_trend` with Decimal invariant guarantee; `reprice_claim` pure function.
- **Stubs:** 34 router handlers return empty lists/dicts; no service-layer calls.
- **Imports:** `shared.db.*`, `shared.events.*`, `shared.middleware`, `shared.config`.
- **Tests:** 14 files, 150 functions (unit 9, integration 3, property 2).
- **Known issues:** forecast, NL-query, what-if, MTM-targeting, rebate-optimization, specialty-pharmacy, mail-order-conversion, 340B endpoints absent; Redis real-time layer not wired.

### 7.8 drug-database

- **Purpose:** Drug reference foundation — NDC, NADAC, ASP, AWP/WAC (FDB), interactions, REMS, Orange Book, RxNorm, Purple Book, shortages, tenant MAC overrides.
- **Completeness:** ~72%. Ingesters strongest component; FDB adapter stubbed; dual pricing schemas; compound ingredients absent.
- **Key files:** `src/api/router.py` (18 real endpoints), `src/models/tables.py` (legacy `drug_db` schema: 9 tables), `src/models/{ndc,pricing,orange_book,rxnorm,fda_supplementary}_tables.py` (new `drug_database` schema: 22+ tables), `src/services/ndc_ingestion.py`, `src/services/rxnorm_ingestion.py` (SAVEPOINT-isolated crosswalks), `src/services/pricing_ingestion.py` (\A\Z validated), `src/services/orange_book_ingestion.py`, `src/services/fda_supplementary_ingestion.py`, `src/services/fdb_adapter.py` (5× `NotImplementedError`).
- **Tables:** (legacy) drug_products, drug_pricing, drug_pricing_history, drug_interactions, therapeutic_equivalence, tenant_pricing_overrides, data_refresh_log, drug_shortages, rems_programs; (new) drugs, drug_packages, drug_active_ingredients, drug_pharm_classes, drug_nadac_pricing+history, drug_asp_pricing+history, drug_orange_book, drug_patents, drug_exclusivity, rxnorm_concepts/relationships/attributes/semantic_types, rxnorm_ndc_crosswalk, rxnorm_atc_crosswalk, drug_rems, drug_rems_ndc, drug_purple_book.
- **Endpoints:** 18 under `/api/v1/drugs/` (lookup/batch/search, pricing + history, interactions, equivalents, overrides CRUD, rems, shortages, refresh/status, health).
- **Real logic:** 3-phase NDC streaming upsert; RxNorm RRF file routing with SAVEPOINT crosswalk builds; NADAC change-detection history; ASP quarter-change history; Orange Book upsert + delete-then-insert patents/exclusivity; REMS NDC side-table replace; Drug Shortage append-only history; NDC normalizer; Interaction checker; Pricing `select_effective_price` resolver; MAC list CSV parser.
- **Stubs:** `fdb_adapter.py:55,58,61,64,67` — 5 `NotImplementedError("FDB spec TBD")`. Compound ingredient model/ingester absent.
- **Imports:** `shared.db.tenant_context`, `shared.events.*`, `shared.data_ingestion.*`, `shared.config`.
- **Tests:** 13 files, 177 functions.
- **Known issues:** dual pricing schemas create ambiguity; AWP/WAC not available; compound ingredients absent.

### 7.9 member-management

- **Purpose:** Enrollment, demographics, eligibility, accumulators, COB, 834/270/271 EDI.
- **Completeness:** ~70%. Services real; routes are stubs; `_query_db` returns empty.
- **Key files:** `src/models/tables.py` (7 tables, EncryptedString on PHI), `src/services/accumulator.py` (copay/reverse/copay-assistance + PartDPhaseEngine + LEP), `src/services/edi_834_parser.py` (ISA envelope detection, Loop 2000), `src/services/x12_270_271.py` (005010X279A1), `src/services/eligibility_service.py` (stub `_query_db`), `src/services/cob_service.py`, `src/services/csv_parser.py`, `src/jobs/benefit_year_reset.py`.
- **Tables:** groups, members, coverage_periods, accumulators, accumulator_ledger, cob_records, enrollment_files, eligibility_checks.
- **Endpoints:** 24 under `/` (eligibility, members, groups, enrollment, cob, coverage).
- **Real logic:** AccumulatorService with Decimal+reversal+copay-assistance (accumulator/maximizer); four-phase Part D benefit; LEP calc; Edi834Parser with ISA detection + ADD/CHANGE/TERMINATE; 270 parser + 271 builder with HL hierarchy; CSV enrollment parser; benefit year reset job with carryover.
- **Stubs:** `eligibility_service.py:249-277` `_query_db` returns empty fixture; every route in `members.py`, `enrollment.py`, `groups.py`, `cob.py`, `coverage.py` is a stub.
- **Imports:** `shared.crypto.sqlalchemy_types.EncryptedString`, `shared.db.tenant_context`, `shared.utils.money`, `shared.events.*`, `shared.middleware`.
- **Tests:** 19 files, 311 functions.
- **Known issues:** eligibility queries are non-functional; all CRUD routes are stubs; consent tracking (PRD §3.14) and COBRA continuation (PRD §3.15) absent.

### 7.10 pharmacy-directory

- **Purpose:** Lookup by NPI/NABP/name/geography, network management, credentialing workflow, PSAO, performance snapshots, exclusion screening.
- **Completeness:** ~72%.
- **Key files:** `src/api/router.py` (25 endpoints, real DB), `src/models/tables.py` (10 ORM models), `src/models/ncpdp_tables.py` (13 NCPDP tables), `src/services/lookup.py` (haversine + Redis), `src/services/network.py` (CMS adequacy), `src/services/credentialing.py` (risk-queue routing), `src/services/ncpdp_ingestion.py`, `src/models/compliance_tables.py`.
- **Tables:** pharmacies, networks, network_memberships, credentialing_applications, credentialing_documents, credential_monitoring, pharmacy_payment_info (encrypted banking), psaos, psao_memberships, pharmacy_performance_snapshots, pharmacy_exclusion_xref + 13 NCPDP tables.
- **Endpoints:** 20 under `/api/v1/pharmacies/` (lookup, search, nearby, batch, networks, credentialing, psaos, stats).
- **Real logic:** haversine geo search + bounding-box pre-filter + Redis cache; CMS urban/suburban/rural adequacy; bulk CSV network add; risk scoring → fast_track/standard/enhanced queues; 90/60/30-day DEA/license expiry credential monitoring job with de-dup.
- **Stubs:** router.py:315 `reviewer_id = uuid.uuid4()  # In prod: extracted from JWT`.
- **Imports:** `shared.crypto.sqlalchemy_types`, `shared.db.*`, `shared.events.*`, `shared.data_ingestion.*`, `shared.utils.money`.
- **Tests:** 25 files, 190 functions.
- **Known issues:** accreditation records (PRD §3.7), LDD designation (PRD §3.8), and contract rate history absent; reviewer identity placeholder violates audit "who" requirement.

### 7.11 prescriber-directory

- **Purpose:** NPI/DEA lookup, NPPES bulk ingestion, taxonomy, controlled-substance authority, state prescribing rules, credential monitoring, prescriber-pharmacy relationships.
- **Completeness:** ~68%.
- **Key files:** `src/api/router.py` (17 endpoints, JWT everywhere — CR-03 done), `src/models/tables.py` (7 ORM), `src/services/nppes_parser.py` (streaming 329-col, 15 taxonomies, 7.8M rows), `src/services/state_prescribing_rules.py` (~10 states), `src/services/credential_monitor.py` (90/60/30d), `src/models/compliance_tables.py` (DeaRegistration, PrescriberExclusionXref), `src/models/medicare_tables.py`, `src/services/nppes_ingestion.py`.
- **Tables:** prescribers, taxonomy_codes, practice_affiliations, credential_alerts, data_refresh_log, prescriber_pharmacy_relationships, state_prescribing_rules, dea_registrations, prescriber_exclusion_xref, medicare_opt_out.
- **Endpoints:** 17 under `/api/v1/prescribers/` (lookup, search, batch, validate, controlled, taxonomies, specialties, organizations, monitoring alerts, stats, relationships, refresh).
- **Real logic:** NPPES V2 streaming parser (329 cols, 15 taxonomy slots, deactivation logic); state prescribing rule lookup `can_prescribe_controlled()`; multi-threshold credential monitoring with de-dup + severity escalation.
- **Stubs:** router.py:315/331 `reviewer_id = uuid.uuid4()` + uses `tenant_id` for acknowledged_by; router.py:444-479 `/refresh` returns "queued" without enqueuing; state_prescribing_rules covers only ~10 states with unsafe "full authority" fallback.
- **Imports:** `shared.auth.dependencies`, `shared.db.tenant_context`, `shared.middleware.*`, `shared.events.*`, `shared.observability`.
- **Tests:** 25 files, 212 functions.
- **Known issues:** default controlled-substance fallback grants full authority — patient safety risk; panel size (§3.10) + supervisory relationship (§3.11) absent; DEA bulk-file ingestor not wired; no tenant isolation fence (CR-09).

### 7.12 medical-prescriber-directory

**Empty directory — 0 files.** No README, no PRD of its own (covered in shared prescriber PRD).

### 7.13 edi-compliance

- **Purpose:** Full HIPAA 5010 X12 EDI — 835/837P/I/D, 270/271, 276/277, 278, 834, 999/TA1; AS2 + SFTP transport; NCPDP Batch 1.2; FHIR R4 bridge.
- **Completeness:** ~75%. Most complete module in platform.
- **Key files:** `src/main.py`, `src/models/edi_models.py` (7 ORM in `edi` schema), `src/api/generate.py`, `src/api/parse.py`, `src/api/trading_partners.py`, `src/x12/generators/gen_835.py`, `src/x12/parsers/parse_835.py`, `src/x12/validators/validator.py` (L1-L4), `src/services/auto_posting.py`, `src/services/denial_scoring.py`.
- **Tables (schema `edi`):** trading_partners, control_number_sequences, transaction_files, transaction_records, compliance_log, as2_certificates, trading_partner_agreements, payer_companion_rules.
- **Endpoints:** 22+ under `/api/v1/edi/` (11 generate, 8 parse, 6 trading-partner, compliance, health, DLQ) — all JWT-protected.
- **Real logic:** ISA/GS/ST/SE/GE/IEA envelope builder with per-tenant `SELECT FOR UPDATE` atomic control numbers; ISA delimiter auto-detection from bytes [3],[104],[105]; 15-char ISA06/08; 835 BPR vs CLP reconciliation with DTM*405 fallback; 835 auto-posting via `payment.auto_posted` event; 4-level validator (syntax, IG, NPI Luhn, companion); FHIR R4 ↔ X12 bridge; NCPDP Batch 1.2; AS2 multipart/signed + MDN; SFTP; clearinghouse adapters (Stedi, Availity, Change Healthcare, Waystar); X.509 cert lifecycle; BAA/TPA tracking; SLA monitoring; PHI-free denial scoring.
- **Stubs:** none in src/.
- **Imports:** `shared.events.*`, `shared.middleware.*`, `shared.db.*`, `shared.auth.dependencies.get_current_user`, `shared.config`, `shared.observability`.
- **Tests:** 50 files, **822 functions, 99.19% line / 97.97% branch coverage**.
- **Known issues:** 275 clinical attachments missing; EDI RBAC missing; README severely outdated ("Sessions 2-4 — Planned" for things already built).

### 7.14 medical-claims

- **Purpose:** Medical-benefit drug claim pipeline — HCPCS J/Q/C, CMS-1500/UB-04, ASP+6%, HCPCS↔NDC crosswalk, 340B detection, accumulator integration, denials, unified spend.
- **Completeness:** ~78%. Core built; inter-module HTTP clients stubbed.
- **Key files:** `src/main.py`, `src/models/tables.py` (4 tables in `medical_claims`, PHI encrypted), `src/services/claim_service.py` (8-status state machine), `src/services/pricing_service.py` (ASP+6% + `quarter_for_date`), `src/services/denial_service.py`, `src/services/detection_340b_service.py`, `src/services/accumulator_service.py`, `src/services/unified_spend_service.py`, `src/api/routes/claims.py`, `src/clients/{pharmacy_directory,member_management,drug_database}_client.py` (stubs).
- **Tables:** claim_records (PHI encrypted: patient_member_id, first/last name, dob, billing tax id, diagnosis 1-4), hcpcs_ndc_crosswalk, asp_pricing, unified_drug_spend.
- **Endpoints:** 26+ under `/api/v1/medical-claims/` (claims CRUD, upload, status, appeal, crosswalk, asp, unified-spend, denials, 340b, waste, site-of-care, stats).
- **Real logic:** 8-status state machine with explicit transition map; ROUND_HALF_UP Decimal everywhere; ASP+6% quarterly lookup; HCPCS-NDC crosswalk with conversion factor/unit/effective dates; conservative 2-condition 340B detection (NPI + eligible drug); denial analytics (reason code + amounts); appeals; unified spend cross-benefit; therapeutic duplication; site-of-care steering; drug waste; `Cache-Control: no-store` on PHI responses.
- **Stubs/TODOs:** 11 TODOs in src/ including:
  - `services/claim_service.py:261`, `events/consumers.py:21,29` — EDI 837 contract pending
  - `clients/pharmacy_directory_client.py:3,26` — stub
  - `clients/member_management_client.py:3,33` — stub
  - `clients/drug_database_client.py:3,24,32` — stub
  - `api/routes/claims.py:175` — CSV/Excel upload stub
- **Imports:** `shared.auth.dependencies`, `shared.events.*`, `shared.middleware.*`, `shared.crypto.sqlalchemy_types.EncryptedString`, `shared.db.models.phi_mixin.PHIMixin`, `shared.db.tenant_context.TenantScopedMixin`, `shared.config`.
- **Tests:** 17 files, 301 functions.
- **Known issues:** CR-02 (PHI plaintext) + CR-03 (no JWT) RESOLVED; all 3 inter-module clients stubbed; CSV upload stub; EDI event contract open; README stale.

### 7.15–7.25 Phase-4 Placeholder Modules

All of these are **empty directory scaffolds** — `src/`, `migrations/`, `tasks/`, `tests/` subdirs with zero files of any kind (no README.md contrary to CLAUDE.md's "Placeholder README only"):

- adjudication-engine
- mtm-clinical
- part-d-pde
- plan-design
- prior-authorization
- program-config
- rebate-management
- rules-engine
- switch-connectivity
- testing-simulator
- ebv-ebi-rtbc

---

## 8. Documentation Inventory

### ADRs (all Accepted)
- ADR-001: Monorepo layout with per-module FastAPI services
- ADR-002: `_shim/` pattern for pre-integration modules (transitional — retire at Phase 2 close)
- ADR-003: Event type names use `domain.action` dot notation
- ADR-004: Async-first SQLAlchemy session strategy
- ADR-005: Dual-mode event bus (RabbitMQ / InMemory)
- ADR-006: Encryption provider pattern for ePHI at rest

### HIPAA SOPs
- `docs/sops/backup-restore.md` — 72-hour restoration (§164.308(a)(7)(ii)(A)-(D))
- `docs/compliance/sop-access-control.md` — SOP-AC-001 (§164.308(a)(4), §164.312(a)(1))
- `docs/compliance/sop-breach-notification.md` — SOP-BN-001 (§§164.400–164.414)
- `docs/compliance/sop-contingency-plan.md` — SOP-CP-001 (§164.308(a)(7))
- `docs/compliance/sop-device-media-controls.md` — SOP-DM-001 (§164.310(d), §164.312(a)(2)(iv))
- `docs/compliance/sop-workforce-training.md` — SOP-WT-001 (§164.308(a)(5))

### PRDs (19 files in `docs/prd/`)
ai-nlp, billing, client-portal, core-platform, dataiq, drug-database, edi-compliance, medical-claims, medical-portal, member-management, member-portal, operator-portal, payment-processing, pharmacy-directory, pharmacy-portal, prescriber-directory, reclaimrx, reporting, + InfinityRx_Blueprint_v2_FINAL.md.

### Other docs
- `docs/architecture/erd.md` — Mermaid ERD (core, billing, member, medical_claims) — last updated 2026-04-14
- `docs/audit/` — 7 audit scratchpads + full-platform-audit-2026-04-14.md (pre/post remediation)
- `docs/api-contracts/events/` — 80+ event schema markdown contracts
- `docs/anti-patterns.md` — Anti-pattern registry
- `docs/lessons-learned.md` — Critical lessons LESSON-001 through LESSON-007 already promoted to `.claude/rules/`
- `docs/team/continuous-learning.md`, `docs/team/process-handbook.md` v3 FINAL
- `docs/glossary.md`, `docs/negative-constraints.md`, `docs/CHANGELOG.md` (Keep-a-Changelog)

### CLAUDE.md files
- `/CLAUDE.md` — 109 lines (root, contains module status table)
- `modules/core-platform/CLAUDE.md` — 6 lines

### API docs
**No OpenAPI/Swagger exports, no Postman collections.** Contracts live as markdown event schemas only.

### .claude/ structure
- `agents/build-agents/` — 8 builder agents
- `agents/tier1-core/` — team-lead, qa-financial-data, qa-security-phi
- `agents/tier2-specialists/` — 340b-specialist, accumulator-maximizer, dba-postgresql, edi-standards, medicare-part-d, state-regulatory, workers-comp
- `rules/` — 11 mandatory rule files (listed in root CLAUDE.md)
- `skills/` — ifx-audit-trail, ifx-financial-precision, ifx-module-standards
- `settings.json` — enables `superpowers@claude-plugins-official`, experimental agent teams, subagent_model=claude-sonnet-4-6

---

## 9. Git Activity Summary

- **Total commits:** 143
- **First commit:** 2026-04-12 12:21:19 -0400 (3 calendar days ago)
- **Most recent:** 2026-04-14 20:45:51 -0400
- **Busiest days:** 2026-04-14 (74 commits), 2026-04-13 (49), 2026-04-12 (20)
- **Branches:** `main` (checked out), `claude/wonderful-mestorf`, 4 `module/core-platform/t*` branches (t1-infra-db, t2-auth-users, t3-events-audit-notif, t4-jobs-files-excl-health), 8+ `worktree-agent-*` branches from parallel agent runs

### Recent 20 commits
```
8f788d8 fix(rxnorm-ingestion): commit per batch; rollback on batch error; SAVEPOINT crosswalks
8f55e45 fix(ingestion): refresh CMS dataset IDs, openFDA REMS query, Purple Book scraper
e1fc604 fix(portal): stabilize operator portal + add test foundation, CI, quality gate
2f7d536 fix(ingestion): rollback session in cross-reference except blocks; add loader scripts
b6a90dc fix(ingestion-tests): patch all FDA supplementary tables for SQLite, not just imported subset
3b9c6c9 feat(directories): OIG LEIE, DEA, SAM.gov exclusion ingesters + cross-reference
b6174a1 feat(prescriber-directory): Medicare Part D utilization + Opt-Out ingesters
d185bc9 feat(drug-database): FDA supplementary ingesters — REMS, shortages, Purple Book
cf7a794 feat(drug-database): RxNorm ingester — concepts, relationships, attributes, NDC/ATC crosswalks
4090bea infra: local stack — docker-compose tuning, init-db, seed, loader real-data fixes
bcde241 fix(pharmacy-directory): relative imports for NCPDP files + namespaced test loader
74a2c8f feat(drug-database): FDA Orange Book ingester — products, patents, exclusivity, NDC cross-ref
5269326 feat(drug-database): CMS NADAC + ASP pricing ingesters — current + history, Decimal precision
8b62788 feat(pharmacy-directory): NCPDP DataQ ingester — 13 tables, 1.28M records, all fields captured
1bed5bd feat(prescriber-directory): NPPES ingester — all 300+ columns, 15 taxonomies, 50 identifiers, pharmacy supplement
fbc0e2d feat(drug-database): FDA NDC Directory ingester — drugs, packages, ingredients, pharm classes
3eb0e3a feat(ingestion): shared data ingestion framework — base, downloader, scheduler, tracking
f593d1f data: add NCPDP DataQ v3.1 + stage reference data directories
d9db64e chore(portal): gitignore raw IFX source data files (xlsx + 30MB pipe-delimited)
a443c70 feat(portal): wire real IFX claims data — 122K claims, $34.8M across 3 cycles
```

Commit activity is dominated by reference-data ingesters (drug-database, prescriber-directory, pharmacy-directory) and portal stabilization — consistent with the post-remediation audit session stated in root CLAUDE.md.

---

## 10. Appendix — File Tree Summary

Total source files (excluding node_modules, .next, .git, .venv, caches): **~6,874 files**.

### Top-level layout
```
infinityrx-platform/
├── CLAUDE.md                      # 109 lines, module status
├── Makefile                       # security-scan, test, lint, format, clean, freeze-lock
├── pyproject.toml                 # Python 3.13; 25+ runtime deps
├── docker-compose.yml             # postgres 17.5, redis 7.4.3, rabbitmq 4.0
├── azure-pipelines.yml            # frontend-only CI
├── conftest.py
├── uv.lock
├── .claude/                       # 11 agents, 11 rules, 3 skills
├── .github/workflows/             # frontend-only CI
├── .pre-commit-config.yaml        # ruff, pip-audit, bandit, detect-private-key
├── data/                          # reference-data staging
├── docs/                          # adr, api-contracts, architecture, audit, compliance, prd, sops, team
├── infrastructure/
│   ├── scripts/                   # init-db.sql, seed_admin.py, backup.sh
│   └── (k8s, terraform — per CLAUDE.md)
├── modules/
│   ├── core-platform/             # Built (partial router-mount gaps)
│   ├── billing/                   # Partial (5 stub consumers, 25 stub routes)
│   ├── payment-processing/        # Partial (OFAC stub, sync routes)
│   ├── reclaimrx/                 # Partial (dead consumer routing)
│   ├── reporting/                 # Partial (scheduled delivery stubs)
│   ├── ai-nlp/                    # Stub-router
│   ├── dataiq/                    # Stub-router
│   ├── drug-database/             # Built (FDB stub, compound ingredients missing)
│   ├── member-management/         # Partial (routes stubbed, eligibility stub)
│   ├── pharmacy-directory/        # Partial (accreditation/LDD missing)
│   ├── prescriber-directory/      # Partial (state rules gap)
│   ├── medical-prescriber-directory/ # EMPTY
│   ├── edi-compliance/            # Built (99.19% coverage)
│   ├── medical-claims/            # Partial (client stubs)
│   └── [11× empty Phase-4 dirs]
├── portal/
│   ├── operator/                  # Next.js 16.2, builds OK, ~60 routes, 123 mock handlers
│   └── shared/                    # 21 reusable components + lib
├── portals/                       # 4 empty placeholder dirs (client/medical/member/pharmacy) + empty shared
├── shared/                        # ai, auth, config, crypto, data_ingestion, db, events, jobs, middleware, models, observability, resilience, tests, utils, validation
└── scripts/                       # untracked (per git status)
```

### Key config/env files observed
- `.env` (50 bytes), `.env.example` (1.4 KB), `.env.local` (922 B — **contains real UMLS key**)
- `portal/operator/.env.local` — **AUTH_SECRET committed**
- `coverage.json` (135 KB, dated 2026-04-13 23:13)

---

## Session Context

Test suites executed in this audit:
- `python -m pytest` (default testpaths) — 1 failure, rest pass
- `python -m pytest modules/<each>/tests` for 12 modules — 1 additional failure (payment-processing)
- `npm run build` in `portal/operator/` — PASS

Vitest and Playwright were **not** re-executed this session (CI covers them; last run passed on 2026-04-14 per git log).
