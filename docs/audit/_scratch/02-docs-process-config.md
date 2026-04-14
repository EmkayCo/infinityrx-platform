# Documentation / Process / Config — Audit Findings

Audit date: 2026-04-14  
Auditor: Category 4/10/16 sweep agent  
Scope: docs/, .claude/, infrastructure/, docker-compose.yml, pyproject.toml, shared/config.py, modules/*/src/db/session.py

---

## Category 4: Documentation — score: 58/100

### Sub-item findings

#### CLAUDE.md accuracy
**FAIL — High severity.**  
CLAUDE.md project status table lists 10+ modules as "Not yet implemented" that are in fact fully or substantially built:

| Module listed as "Not yet implemented" | Actual state |
|---|---|
| member-management | 36 .py files, fully built |
| pharmacy-directory | 27 .py files, fully built |
| prescriber-directory | 26 .py files, fully built |
| drug-database | 27 .py files, fully built |
| dataiq | 21 .py files, fully built |
| ai-nlp | 20 .py files, fully built |
| edi-compliance | 51 .py files, fully built (3 build sessions) |
| medical-claims | 43 .py files, fully built |

CLAUDE.md also claims 25 modules total but the status table has 25 rows. Module count is correct. The phase/status column is severely stale — at least 8 modules built after the last CLAUDE.md update.

File: `/Users/Dev/infinityrx-platform/CLAUDE.md`

#### Module-level README.md coverage
**PARTIAL — Medium severity.**  
4 of the actively-built (Phase 1/2) modules are missing README.md:
- `modules/billing/` — NO README (substantial src/, ~10 service files)
- `modules/payment-processing/` — NO README (substantial src/)
- `modules/reclaimrx/` — NO README (substantial src/)
- `modules/reporting/` — NO README (substantial src/)

All Phase 3/4 stub directories have placeholder README.md files (1-liner "not yet implemented") which satisfies the architecture rule letter but not its spirit.

Architecture rule: "MUST have README.md for every implemented module."
Violations: 4 built modules.

#### PRD coverage vs built features
**GOOD — no material gap on spot-check.**  
`prd-core-platform.md` describes tenants, users, MFA, sessions, audit, RBAC, API keys, notifications, jobs, files — all of these exist under `modules/core-platform/src/`. PRDs for edi-compliance and medical-claims exist (`docs/prd/prd-edi-compliance.md`, `docs/prd/prd-medical-claims.md`) and were created before those modules were built (commit `be7c999`). The blueprint doc (`docs/prd/InfinityRx_Blueprint_v2_FINAL.md`) is present.

Missing PRDs: no `prd-adjudication-engine.md`, `prd-rules-engine.md`, `prd-plan-design.md`, `prd-rebate-management.md`, `prd-prior-authorization.md`, `prd-program-config.md`, `prd-switch-connectivity.md`, `prd-testing-simulator.md`, `prd-mtm-clinical.md`, `prd-part-d-pde.md`, `prd-ebv-ebi-rtbc.md` — but those modules have no src/ implementation either, so the gap is acceptable for current phase.

#### API docs (OpenAPI/Swagger)
**ACCEPTABLE — but not production-hardened.**  
All modules that have `main.py` use FastAPI which auto-generates OpenAPI at `/docs`. No module explicitly disables `docs_url` or `redoc_url`. This means OpenAPI UIs are accessible in production by default, which is a security concern for a PHI/banking-grade system. Core-platform `create_app()` does not pass `openapi_url=None` or environment-gate the docs endpoint.

Files: `modules/core-platform/src/main.py:156`, and all other module main.py files.

Recommendation: Disable `/docs` and `/redoc` in production via `openapi_url=None` when `ENVIRONMENT=production`, or gate behind an internal auth check.

#### ADRs
**GOOD — substantive, 3 present.**  
Three ADRs exist, all accepted, all non-trivial:
- `ADR-001-monorepo-layout.md` — documents the monorepo + per-module FastAPI decision
- `ADR-002-shim-pattern.md` — documents the `_shim/` transitional pattern with retirement plan
- `ADR-003-event-naming.md` — documents dot-notation canonical form for event types

Gap: No ADR for the async SQLAlchemy session strategy, no ADR for the Azure vs RabbitMQ event bus dual-mode, no ADR for encryption provider pattern. These are significant architectural decisions with no documented rationale.

#### ERD / Schema diagrams
**MISSING — Medium severity.**  
No `.drawio`, `.puml`, `.mmd`, or `.erd` files found anywhere in `docs/` or `infrastructure/`. No visual schema documentation exists. For a platform with 25 modules across multiple PostgreSQL schemas, the absence of any ER diagram makes onboarding and compliance audits materially harder.

#### Event catalog coverage
**FAIL — High severity.**  
The event catalog at `docs/api-contracts/events/` has a major split-brain problem:

- **42 event contract files exist** in the catalog.
- **45 unique event types are published** in code.
- **29 events are published in code but have NO matching contract doc** (e.g., `ai.document_processed`, `ai.content_generated`, `ai.confidence_low`, `dataiq.*`, `drug.*`, `report.*`, `prefund.critical`, `quality.measure_at_risk`, `regulatory.deadline_approaching`, `member.cob_changed`, `member.merged`, `member.plan_changed`).
- **24 of 42 catalog files use old snake_case filenames** (`claim_submitted.md`, `payment_settled.md`, etc.) while ADR-003 mandates dot-notation (`claim.submitted`). The *content* of those files does use the correct dot-notation event type (e.g., `claim.submitted`) but the *filenames* violate the convention and create lookup confusion for tooling.
- **26 documented events** (the old snake_case ones + some with dot-notation) do not map to any currently published event type in code — either they cover billing/payment-processing/reclaimrx events where publishers haven't been wired, or they are orphaned from old naming.

This is a critical gap for a $300M+/yr system. Consumers cannot reliably implement against the catalog as-is.

#### Environment variable documentation
**GOOD.**  
`.env.example` is comprehensive and well-commented. It covers `DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`, `RABBITMQ_URL`, `JWT_SECRET` (with length hint), `STORAGE_PROVIDER`, `SMTP_HOST/PORT`, `OIG_EXCLUSION_URL`, `SAM_API_KEY`, `ENCRYPTION_KEY_ACTIVE`, and `MAX_UPLOAD_BYTES`. Comment included for how to generate the encryption key. `shared/config.py` has a module docstring explaining all fields and startup validation behavior.

Gap: Module-specific env vars (`DRUG_DB_DATABASE_URL`, `BILLING_DATABASE_URL`, `PRESCRIBER_DB_URL`) are not documented in `.env.example`. They only appear in the module's `session.py` fallback defaults.

#### Deployment runbook / SOPs
**GOOD — one SOP present, no runbook gaps for current phase.**  
`docs/sops/backup-restore.md` is substantive (72-hour HIPAA restore procedure, backup cadence table, encryption requirements, restore step-by-step). `infrastructure/scripts/backup.sh`, `restore.sh`, and `verify_backup.py` exist. No deployment runbook for AKS found — `infrastructure/k8s/` is empty, `infrastructure/terraform/` is empty. Terraform and K8s are referenced in CLAUDE.md but not present.

#### lessons-learned.md maintenance
**GOOD — actively maintained.**  
8 lessons present (LESSON-001 through LESSON-008). Dates range from 2026-04-13 (multiple on same day). All have severity ratings, root cause analysis, fix descriptions, and regression test anchors. Critical/high lessons are propagated to rules files (LESSON-001 → testing.md, LESSON-004 → security.md, LESSON-005 → code-standards.md, LESSON-006 → architecture.md). File is 293 lines — properly dense.

Note: Lessons are numbered non-sequentially in the file (008 first, then 006, 001, 002, 005, 004, 007, 003) suggesting they were added non-chronologically. Not a functional issue but slightly confusing to read.

#### CHANGELOG
**MISSING.**  
No `CHANGELOG.md` exists at the repo root or anywhere in `docs/`. Commit messages serve as the only changelog. For a compliance-audited $300M+/yr system, a formal changelog distinguishing releases from build sessions is expected.

#### Inline comments on complex business logic
**GOOD in financial services, SPARSE in journal.**  
- `billing/src/services/nacha.py`: 82 comment lines — well documented, explains NACHA record structure, field positions, and business rules inline.
- `billing/src/services/remittance_835.py`: 3 comment lines — very sparse for a complex HIPAA 005010X221A1 835 generator. Complex segment construction logic has no inline explanation.
- `billing/src/services/journal.py`: 0 inline comment lines (module docstring only). Append-only ledger semantics are documented in the docstring but the business logic within methods is uncommented.

### Missing docs (summary)
1. ERD / schema diagram — none exist
2. Event catalog incomplete: 29 published event types have no contract doc
3. Event catalog naming: 24 files use old snake_case filenames (should be dot-notation per ADR-003)
4. CLAUDE.md status table stale: 8+ built modules listed as "Not yet implemented"
5. 4 built Phase 2 modules missing README.md (billing, payment-processing, reclaimrx, reporting)
6. No CHANGELOG.md
7. Module-specific env vars not in `.env.example`
8. `remittance_835.py` lacks inline comments on complex segment logic
9. No ADRs for async session strategy, dual-mode event bus, or encryption provider

### Recommendations
1. **Immediately update CLAUDE.md** status table — 8 modules are fully built and marked "Not yet implemented." This misleads every agent that reads CLAUDE.md before starting work.
2. **Add dot-notation filenames** for all 24 old snake_case event contract files, and create contracts for the 29 undocumented event types.
3. **Add README.md** to billing, payment-processing, reclaimrx, reporting.
4. **Add ERD**: At minimum a PlantUML or Mermaid diagram covering the `core`, `billing`, and `member` schemas.
5. **Gate OpenAPI docs** behind `ENVIRONMENT != production` in all module `main.py` files.
6. **Create CHANGELOG.md** with high-level release/session history.
7. **Add module-specific env vars** to `.env.example` with inline comments.

---

## Category 10: Team & Process — score: 72/100

### Sub-item findings

#### Agent files — scoping and coverage
**PARTIAL — Medium severity.**  
Agent directory structure:
- `build-agents/`: 7 builder agents + 1 team-lead (8 total)
- `tier1-core/`: 2 QA sweep agents (qa-financial-data, qa-security-phi)
- `tier2-specialists/`: 7 domain specialists (340b, accumulator-maximizer, dba-postgresql, edi-standards, medicare-part-d, state-regulatory, workers-comp)
- `tier3-situational/`: EMPTY — directory exists but no agents

**Coverage gaps:**
- No builder agents for Phase 3 modules (member-management, pharmacy-directory, prescriber-directory, drug-database, dataiq, ai-nlp) — yet all 6 of these modules are fully built. Either they were built without dedicated builder agents (ad-hoc), or the agent files were used and then not committed.
- No builder agents for any Phase 4 modules (edi-compliance, medical-claims, adjudication-engine, etc.) — edi-compliance and medical-claims are fully built.
- `tier3-situational/` exists but is empty. Either it was planned but never populated, or agents were used and deleted.
- Only 2 QA agents for tier1-core — no QA agent for integration testing, performance, or tenant isolation verification.

Files: `/Users/Dev/infinityrx-platform/.claude/agents/build-agents/`, `.claude/agents/tier1-core/`, `.claude/agents/tier2-specialists/`, `.claude/agents/tier3-situational/`

#### Rules files completeness
**PASS.**  
CLAUDE.md specifies 11 rules files. All 11 are present:
- architecture.md, code-standards.md, error-handling.md, event-bus.md, financial-precision.md, hipaa-2026.md, performance.md, phi-compliance.md, security.md, tenant-isolation.md, testing.md

All are non-empty and substantive (confirmed by reading contents above).

#### Build status tracking
**PARTIAL — Medium severity.**  
No top-level `tasks/todo.md` or equivalent build tracking file. The only `todo.md` found is at `modules/core-platform/tasks/todo.md` (and duplicated across worktree snapshots). That file contains integration follow-up tasks specific to core-platform, including items like `swap-revoked-repo-redis` and `replace-standin-models` that reference in-memory placeholders still in production code.

No cross-module build tracking (kanban, task board, sprint tracker) exists. This is notable given 8 modules were built in concurrent sessions — coordination relied entirely on commit messages.

File: `/Users/Dev/infinityrx-platform/modules/core-platform/tasks/todo.md`

#### Orphaned / temp artifacts
**FAIL — Low severity.**  
`coverage.json` (135.2KB) is untracked at repo root (visible in git status). This is a coverage.py JSON export that was never added to `.gitignore`. It contains detailed per-file coverage data and should not be committed. The `.gitignore` covers `.coverage` (the binary) and `htmlcov/` but does NOT cover `coverage.json`.

No other temp artifacts found at root beyond `coverage.json`.

#### Commit message quality
**GOOD.**  
Last 20 commits are all descriptive with conventional commit format (`feat(module):`, `docs:`, `wiring:`). Session-based commits (e.g., "session 3 — 278 + 275 + 834 + 999/TA1 ack + FHIR bridge + NCPDP Batch 1.2") contain sufficient detail. No "fix", "update", "misc" placeholder messages found.

#### Core-platform open todos
**NOTE — Medium severity (not a process failure, but a risk).**  
`modules/core-platform/tasks/todo.md` contains several open integration tasks that may still be unresolved:
- `swap-revoked-repo-redis`: `InMemoryRevokedTokenRepo` still in use (Redis-backed impl not confirmed complete)
- `replace-standin-models`: shim models (`src/auth/_models.py`, `src/auth/_db.py`) may still exist
- `sms.wire-provider`: `NoOpSmsDelivery` (no actual SMS sending) still possibly wired
- `shared.auth.integration-reconcile`: shim `AuditContext` / `current_user` may not yet be replaced

These are known TODOs but lack links to a central task system, creating risk they get forgotten.

### Recommendations
1. **Add `coverage.json` to `.gitignore`** immediately — it is a 135KB build artifact with no business in the repo.
2. **Create builder agents for Phase 3/4 built modules** (member-management, pharmacy-directory, prescriber-directory, drug-database, dataiq, ai-nlp, edi-compliance, medical-claims) or document why ad-hoc builds were used without agents.
3. **Create a top-level `tasks/todo.md`** or move open core-platform integration tasks there. The current single-module task file will not scale to 25 modules.
4. **Populate `tier3-situational/`** or delete the empty directory (violates dead-code rule from code-standards.md).
5. **Audit open TODOs** in core-platform/tasks/todo.md — verify shims have been replaced or formally accept the tech debt with a linked task.

---

## Category 16: Configuration & Environment — score: 62/100

### Sub-item findings

#### Hardcoded connection strings
**FAIL — High severity.**  
Three modules contain hardcoded fallback database URLs in their `session.py` files:

1. `modules/drug-database/src/db/session.py:15`:
   ```python
   "postgresql+psycopg2://drug_db:drug_db@localhost:5432/infinityrx_drug_db"
   ```
   (fallback when `DRUG_DB_DATABASE_URL` not set)

2. `modules/billing/src/db/session.py:25`:
   ```python
   "postgresql+psycopg2://billing:billing@localhost:5432/infinityrx_billing"
   ```
   (fallback when `BILLING_DATABASE_URL` not set)

3. `modules/prescriber-directory/src/db/session.py:27`:
   ```python
   "postgresql+psycopg2://localhost/prescriber_directory"
   ```
   (fallback when `PRESCRIBER_DB_URL` not set)

These are developer convenience defaults, but the pattern is dangerous: a misconfigured deployment (missing env var) silently connects to localhost instead of failing fast. The shared `config.py` model (with pydantic `BaseSettings` and required fields) is the correct pattern, and it's used for core platform — but these 3 modules bypass it entirely with their own module-local session factories.

Additionally, `shared/events/factory.py:25` has:
```python
url = os.getenv("RABBITMQ_URL", "amqp://infinityrx:infinityrx_dev@localhost:5672/")
```
This is lower severity (dev credentials, not prod), but inconsistent with the shared `Settings` approach.

**Architecture rule violation:** "MUST use `shared.db.session` for database sessions — no module-local session factories." These three modules violate this rule.

#### Config startup validation
**GOOD for core platform, ABSENT for 3 modules.**  
`shared/config.py` uses `pydantic_settings.BaseSettings` with required fields (`DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`, `RABBITMQ_URL`, `JWT_SECRET`) — missing values raise a `ValidationError` at startup. `JWT_SECRET` has a `min_length=32` validator. This is correct.

However, the 3 modules with local session factories (drug-database, billing, prescriber-directory) bypass this: they read env vars directly with `os.environ.get(key, fallback_value)` — no startup validation, no fail-fast.

#### docker-compose.yml accuracy vs tech stack
**PASS.**  
- `postgres:17` — matches CLAUDE.md requirement
- `redis:7.4` — matches CLAUDE.md requirement
- `rabbitmq:4-management` — matches CLAUDE.md requirement
- Healthchecks present on all three services
- Postgres `log_min_duration_statement=1000` configured (matches performance rule for slow-query logging)
- Backup script referenced in docker-compose comments pointing to `infrastructure/scripts/backup.sh`

No issues found.

#### Feature flags per-tenant
**PARTIAL — Low severity.**  
The `core.tenants` table (per PRD) has an `enabled_features JSONB DEFAULT '{}'` column. However, no `feature_flag` or `get_tenant_feature()` utility was found in `shared/` or any module. The data model exists but no consumption pattern has been standardized. This is a "configuration over code" principle gap — if adding a per-tenant feature requires code changes, the architecture is wrong.

#### `.env` committed
**PASS — CRITICAL CHECK.**  
`git ls-files` shows `.env.example` is tracked (correct), but `.env`, `.env.local`, and `.env.*.local` are all in `.gitignore`. No actual `.env` or `.env.local` file is committed to the repository.

#### Separate configs for dev/staging/prod
**FAIL — Medium severity.**  
No `config/environments/` or equivalent directory exists. No `docker-compose.staging.yml`, `docker-compose.prod.yml`, or environment-specific override files. The codebase uses a single `docker-compose.yml` with dev credentials hardcoded (e.g., `POSTGRES_PASSWORD: infinityrx_dev`, `RABBITMQ_DEFAULT_PASS: infinityrx_dev`).

The `infrastructure/k8s/` directory is empty, and `infrastructure/terraform/` is empty. The platform has no production deployment artifacts. For a $300M+/yr system targeting AKS, this is a significant gap — but may be expected at this build phase.

`shared/config.py` does not have an `ENVIRONMENT` field (dev/staging/prod) — there's no way to conditionally change behavior based on environment.

#### Secrets management / Azure Key Vault
**FAIL — High severity.**  
No Azure Key Vault integration found. No references to `SecretClient`, `KEYVAULT_URL`, or `@microsoft/azure-keyvault-secrets` anywhere in the codebase. The `ENCRYPTION_KEY_ACTIVE` secret and `JWT_SECRET` are loaded purely from environment variables, with no vault-backed secret rotation mechanism. For a HIPAA-compliant system deploying to AKS, secrets must be in Key Vault (or equivalent), not raw env vars in deployment manifests.

`.env.example` comments mention "Encryption — 32-byte key, base64 encoded" with a generation command but no Key Vault reference.

This is a production-readiness blocker, not a dev workflow issue.

#### psycopg2 vs asyncpg
**NOTE — Low severity.**  
The module-local session factories (drug-database, billing, prescriber-directory) all use `psycopg2` (sync) while the shared `config.py` references `asyncpg` and `psycopg` (async). The performance rules state "MUST use async SQLAlchemy engine — never sync psycopg2 in API routes." All three of these modules use sync engines in their local `session.py` files.

### Missing configurations (summary)
1. 3 modules bypass `shared/config.py` with hardcoded fallback DB URLs (`drug-database`, `billing`, `prescriber-directory`)
2. No Azure Key Vault / secrets manager integration
3. No dev/staging/prod config separation
4. `ENVIRONMENT` field absent from `shared/config.py` (no env-conditional behavior)
5. No feature flag consumption utility despite data model support
6. `coverage.json` not in `.gitignore`
7. `infrastructure/k8s/` and `infrastructure/terraform/` are empty — no production deployment artifacts

### Recommendations
1. **Migrate drug-database, billing, prescriber-directory** to use `shared.db.session` (architecture rule) and add their DB URLs to `shared/config.py` as required fields. Eliminate all `os.environ.get(key, hardcoded_fallback)` patterns.
2. **Integrate Azure Key Vault**: Add `azure-keyvault-secrets` to dependencies, wire `SecretClient` into `shared/config.py` when `KEYVAULT_URL` is set (vault-first, env-fallback for dev). This is a production blocker.
3. **Add `ENVIRONMENT: Literal["development","staging","production"] = "development"`** to `shared/config.py` and use it to gate OpenAPI docs and apply production-hardening behavior.
4. **Add `coverage.json` to `.gitignore`.**
5. **Begin `infrastructure/terraform/`** with at minimum AKS, Key Vault, and PostgreSQL Flexible Server modules.
6. **Create `docker-compose.override.yml`** pattern for staging/prod credential management.

---

## Score Summary

| Category | Score | Key deficiencies |
|---|---|---|
| 4 — Documentation | 58/100 | CLAUDE.md stale (8 modules wrong status), event catalog 29-event gap + 24 wrong filenames, no ERD, 4 built modules missing README, no CHANGELOG |
| 10 — Team & Process | 72/100 | No builder agents for Phase 3/4 built modules, no top-level task tracker, orphaned coverage.json, tier3-situational empty |
| 16 — Configuration & Environment | 62/100 | 3 modules with hardcoded DB URLs + module-local session factories, no Key Vault, no env separation, no Terraform/K8s artifacts |

**Composite: 64/100**

**Blockers for production:**
- Key Vault integration absent (Cat 16)
- 3 modules use hardcoded DB connection strings bypassing shared config validation (Cat 16)
- Event catalog has 29 undocumented published event types (Cat 4 — contract consumers cannot implement)
- CLAUDE.md is materially wrong about build state (Cat 4 — misleads every agent)
