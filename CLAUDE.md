# InfinityRx Enterprise Platform

## CRITICAL LESSONS LEARNED
- **LESSON-001:** SQLAlchemy test sessions need SAVEPOINT-based rollback, not TRUNCATE. Use the nested transaction fixture pattern in `.claude/rules/testing.md`.
- **LESSON-004:** `re.match(r"^\d{6}$")` accepts trailing newlines. Use `\A...\Z` anchors or `re.fullmatch()` for ALL security-sensitive regex validation.
- **LESSON-005:** `logger.extra={"module": ...}` collides with `LogRecord.module` built-in attribute. Use service/subsystem-prefixed keys instead.
- **LESSON-007:** `PG_UUID(as_uuid=True)` returns floats under SQLite SAVEPOINT sessions. Use `_UUIDString` TypeDecorator (VARCHAR 36) in test conftest fixtures for any model with UUID columns. See `.claude/rules/testing.md`.
- **AUDIT FINDING:** Built primitives must be MOUNTED on production apps — hash chain, MFA gate, security headers, rate limiter all existed but were never wired into live request paths. Every middleware/router primitive needs an integration test through `create_app()`.

## Rules Files
All builders MUST read these rules files before starting work:
- `.claude/rules/security.md`
- `.claude/rules/financial-precision.md`
- `.claude/rules/phi-compliance.md`
- `.claude/rules/tenant-isolation.md`
- `.claude/rules/event-bus.md`
- `.claude/rules/hipaa-2026.md`
- `.claude/rules/architecture.md`
- `.claude/rules/performance.md`
- `.claude/rules/code-standards.md`
- `.claude/rules/error-handling.md`
- `.claude/rules/testing.md`

## Agent Files
Builder agents are in `.claude/agents/build-agents/`. Each builder reads their agent file + all rules files + their module's PRD before starting work.
QA sweep agents are in `.claude/agents/tier1-core/` and MUST run at the end of every build session touching their scope.
Domain specialists are in `.claude/agents/tier2-specialists/` and are called on-demand as subagents when their triggers fire.

## Project Status

| Module | Phase | Status | Notes |
|---|---|---|---|
| core-platform | 1 | Built | Auth, MFA, audit hash chain, tenants, sessions, API keys, DLQ, middleware — security/audit primitives mounted; notifications + bank-holidays + audit query routers wired (W1) |
| billing | 2 | Built | AP/AR, journal hash chain, NACHA, 835; event consumers persist real records with per-delivery DB session (W1); 27 router handlers wired to service layer (W2F); all 77 handlers run sync def → threadpool (W3B). 50-state compliance tables still gap |
| payment-processing | 2 | Built | Vendor adapters, ACH returns (80+ codes), OFAC DB-backed screening with fuzzy match + audit alerts, business-day calendar; sync handlers run in threadpool (W3B) |
| reclaimrx | 2 | Built | FWA detection pipeline LIVE: 8 event consumers run rule engine + XGBoost ML scoring + payment holds + auto-opened investigations. Per-delivery DB session via wire_consumers (production-ready). Graph analysis batch job + accumulator detection still gap |
| reporting | 2 | Built | Dashboards, report preview, client-api wired; scheduled-job skeleton (W2C). Excel/PDF rendering deferred |
| ai-nlp | 3 | Built | RAG, extraction, guardrails, NLP pipeline; 12 router endpoints wired to RagService/guardrails/extraction/usage_logger (W2A). 20+ advanced features (denial prediction, FHIR PA, fax splitting) still gap |
| dataiq | 3 | Built | Analytics endpoints, dashboards; 34 router endpoints wired to SPC/trend/repricing/KPI/geo (W2B). what-if, NL query, forecast still gap |
| drug-database | 3 | Built | NDC/pricing/drug interactions complete; compound ingredients missing |
| member-management | 3 | Built | 834/CSV ingestion, accumulators, 270/271; real CRUD on members/groups/enrollment/cob/coverage (W2D); EligibilityService._query_db real ORM queries (W1). Consent and COBRA tracking still gap |
| pharmacy-directory | 3 | Built | Lookup, credentialing, PSAO; reviewer_id resolved from JWT identity, audit-trail repaired (W3D). Accreditation, LDD, contract rate history still gap |
| prescriber-directory | 3 | Built | NPPES, state rules with safe restricted-default for unmodeled states + 10 populous states (W3C). No tenant isolation fence (CR-09 still open) |
| adjudication-engine | 4 | Not started | Placeholder README only |
| edi-compliance | 4 | Built | Full X12 suite (835/837/270/271/276/277/278/834/999), AS2+SFTP, NCPDP Batch 1.2, FHIR bridge. JWT auth via router-level Depends on all 4 route files (CR-03 RESOLVED). Test coverage ~15% still gap (CR-12) |
| medical-claims | 4 | Built | Full claim pipeline, CMS-1500/UB-04, accumulator integration; httpx + tenacity HTTP clients with circuit-breaker fallback. PHI encrypted via EncryptedString verified (CR-02 RESOLVED). JWT auth via router-level Depends(get_current_user) on all 7 route files (CR-03 RESOLVED) |
| mtm-clinical | 4 | Not started | Placeholder README only |
| part-d-pde | 4 | Not started | Placeholder README only |
| plan-design | 4 | Not started | Placeholder README only |
| prior-authorization | 4 | Not started | Placeholder README only |
| program-config | 4 | Not started | Placeholder README only |
| rebate-management | 4 | Not started | Placeholder README only |
| rules-engine | 4 | Not started | Placeholder README only |
| switch-connectivity | 4 | Not started | Placeholder README only |
| testing-simulator | 4 | Not started | Placeholder README only |
| ebv-ebi-rtbc | 4 | Not started | Placeholder README only |

## Session Remediation (2026-04-14)

Audit-remediation session conducted 2026-04-14 by 4 parallel teammates (Teammate 1: wiring, Teammate 2: events, Teammate 3: models/tests, Teammate 4: docs). Findings catalogued in `docs/audit/full-platform-audit-2026-04-14.md`. Overall starting platform score: **63/100**.

**Wave 1 (CR-01 through CR-13)** — `docs/audit/wave1-remediation-report.md` — addressed: secret rotation, billing event consumers persisting real records, reclaimrx 8 consumers subscribed, eligibility _query_db real queries, core-platform notifications + bank-holidays + audit query routers mounted. Wave 1 score: **76/100**.

**Wave 2 + 3** — `docs/audit/wave2-3-remediation-report.md` — wired 100+ stubbed router endpoints across ai-nlp/dataiq/reporting/member-management/medical-claims/billing; backend CI pipeline (Postgres + Redis services, all 13 modules); sync def + threadpool perf band-aid; prescriber state-rules safe default + 10 populous states; pharmacy-directory reviewer_id resolved from JWT; medical-prescriber-directory removed. Test totals: **3,919 → 4,118 passing, 0 failing**. Wave 2/3 score: **~85/100**.

**Production Hardening (this session)** — `docs/audit/production-hardening-report.md` — wired 8 reclaimrx event consumers to real FWA detection engine (rule evaluation, XGBoost ML scoring, payment holds, auto-opened investigations) with 8 integration tests; replaced OFAC in-memory stub with DB-backed SDN screening + rapidfuzz matching + audit alerts; verified CR-02 PHI encryption in medical-claims (6 regression tests); verified CR-03 JWT auth via router-level dependencies on medical-claims + edi-compliance (8 auth tests); scoped demo environment scaffold (6 fictional manufacturers, 11 programs, 10 drugs, 1,000-claim generator with FWA patterns, portal demo banner). Test totals: **4,118 → 4,133 passing, 0 failing per-module**. Score: **~90/100**.

Still open: full async session migration, Phase-4 placeholder modules, demo scaling to 250K claims + billing pipeline run, graph analysis batch job, accumulator detection consumer wiring.

## System
Multi-module PBM ecosystem. Multi-tenant, API-first. Build local, deploy to Azure.
100M+ claims/year capacity. Tens of billions of dollars. Zero error tolerance.
ZERO reference to any third-party PBM vendor anywhere in code, docs, or comments.

## Principles
1. Decimal with ROUND_HALF_UP for all money. No floats. Ever.
2. Cannot lose data on crash. Transaction boundaries everywhere.
3. No silent failures. Structured error responses.
4. All actions auditable (who/what/when/where/before/after).
5. All outputs reproducible. Deterministic on identical inputs.
6. YAGNI. Minimum code to satisfy the requirement.
7. Each module is a separate FastAPI service with its own API and schema.
8. Modules communicate via API calls and event bus messages. No direct DB access between modules.
9. Full NCPDP D.0 standard. Build for the standard, not current files.
10. Every screen is operable by a non-technical user.
11. TDD is non-negotiable for all core business logic.
12. Configuration over code. If adding a client requires code changes, architecture is wrong.
13. Fully built with best-practice defaults, then configurable per tenant.

## Tech Stack
Backend: Python 3.13 + FastAPI | Frontend: Next.js 16.2 + React 19.2 + TypeScript + Tailwind + shadcn/ui
Database: PostgreSQL 17 + Redis 7.4 | Events: RabbitMQ (local) / Azure Service Bus (prod)
AI: Azure OpenAI (GPT-4.1), scikit-learn, XGBoost | Infra: Docker, Terraform, AKS

## Database Rules
Each module owns its own PostgreSQL schema. Migrations namespaced per module.
Shared schema (auth, audit, tenants) owned by core-platform, locked after Phase 1.
No cross-schema direct queries. Use API calls between modules.

## Git Strategy
Main branch protected. Module branches: `module/{name}`. Feature branches: `module/{name}/{feature}`.
Worktrees for parallel agents. Integration Coordinator merges at gates.

## References
`docs/glossary.md` | `docs/negative-constraints.md` | `docs/api-contracts/` | `docs/prd/` | `docs/anti-patterns.md`

## Continuous Learning
Before starting any task, read `docs/lessons-learned.md` for recent discoveries.
When you hit a non-obvious bug (>5 min to debug), add a LESSON entry per `docs/team/continuous-learning.md`.
Critical/high severity lessons MUST update the relevant `.claude/rules/` file in the same commit.
Never silently fix a bug — always document what you learned.

## Auto-Gate
All tests pass 100% AND coverage meets thresholds (100% on financial, PHI, security, and auth paths; 99% branch coverage on all other active code) AND no dead code/stub files → proceed automatically.
Any active code below 99% branch coverage, OR financial/PHI/security/auth paths below 100%, OR dead code found → STOP, fix before proceeding.
Any test failure → STOP, fix before proceeding.
