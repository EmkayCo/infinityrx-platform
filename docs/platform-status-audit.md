# InfinityRx Platform — Status Audit

**Date:** 2026-04-14
**Commit:** a64d9381b4edddc07146ddd6a35fe1998843a5ec (`main`)
**Scope:** Read-only reconnaissance across `modules/`, `portal/`, Postgres, Docker, and git.

---

## Module Status Table

Coverage percentages are not reported — no coverage run succeeded at the root (missing `openpyxl` on the project interpreter; per-module `uv run` invocations were used for test execution only). "API files" counts `.py` files under `src/api/` excluding `__init__.py`. "Migrations" counts Alembic version scripts under `migrations/versions/`.

| Module | Has Code | Has Tests | Test Count | Pass/Fail | API Files | Migrations |
|---|---|---|---|---|---|---|
| adjudication-engine | N | N | 0 | — | 0 | 0 |
| ai-nlp | Y | Y | 148 | **PASS** | 3 | 0 |
| billing | Y | Y | 171 | **PASS** | 8 | 1 |
| core-platform | Y | Y | 198 | **PASS** | 0¹ | 10 |
| dataiq | Y | Y | 150 | **PASS** | 3 | 0 |
| drug-database | Y | Y | 177 | **PASS** | 3 | 6² |
| ebv-ebi-rtbc | N | N | 0 | — | 0 | 0 |
| edi-compliance | Y | Y | 822 | **PASS** | 4 | 1 |
| medical-claims | Y | Y | 301 | **PASS** | 14 | 1 |
| medical-prescriber-directory | N | N | 0 | — | 0 | 0 |
| member-management | Y | Y | 174 | **PASS** | 8 | 0² |
| mtm-clinical | N | N | 0 | — | 0 | 0 |
| part-d-pde | N | N | 0 | — | 0 | 0 |
| payment-processing | Y | Y | 276 | **PASS** | 3 | 0 |
| pharmacy-directory | Y | Y | 198 | **PASS** | 3 | 4² |
| plan-design | N | N | 0 | — | 0 | 0 |
| prescriber-directory | Y | Y | 210 | **PASS** | 3 | 5² |
| prior-authorization | N | N | 0 | — | 0 | 0 |
| program-config | N | N | 0 | — | 0 | 0 |
| rebate-management | N | N | 0 | — | 0 | 0 |
| reclaimrx | Y | Y | 154 | **PASS** | 3 | 0 |
| reporting | Y | Y | 149 | **PASS** | 5 | 0 |
| rules-engine | N | N | 0 | — | 0 | 0 |
| switch-connectivity | N | N | 0 | — | 0 | 0 |
| testing-simulator | N | N | 0 | — | 0 | 0 |

¹ core-platform exposes routers through `src/auth/api/`, `src/audit/api.py`, etc.; no single top-level `src/api/` directory.
² Migration files detected outside `migrations/versions/` folder (see Database Status — schemas exist and are populated, so migrations have been applied or tables created directly).

**Total tests passing: 3,128 (0 failed, 0 errored).**

---

## Test Summary

Root-level `pytest` fails immediately:

```
modules/core-platform/src/audit/service.py:16: ModuleNotFoundError: No module named 'openpyxl'
```

`openpyxl>=3.1.5` IS declared in `pyproject.toml` — the failure is an interpreter/venv mismatch at the project root, not a code issue. The root `pyproject.toml` explicitly notes that each module must be run separately because every module uses the top-level `src.*` package name and would collide under the same collection:

```toml
testpaths = ["modules/core-platform/tests", "shared/tests", "tests"]
# NOTE: billing / payment-processing / reclaimrx / reporting / ai-nlp
# tests are NOT in the default testpaths... Each module is run separately:
#   uv run pytest modules/<name>/tests
```

Per-module run (`uv run pytest modules/<name>/tests --tb=no -q`):

| Module | Result |
|---|---|
| core-platform | 198 passed |
| billing | 171 passed |
| payment-processing | 276 passed in 1.93s |
| reclaimrx | 154 passed |
| reporting | 149 passed |
| ai-nlp | 148 passed |
| dataiq | 150 passed |
| drug-database | 177 passed in 0.80s |
| member-management | 174 passed |
| pharmacy-directory | 198 passed, 1 warning in 1.35s |
| prescriber-directory | 210 passed, 2 warnings in 0.68s |
| edi-compliance | 822 passed in 2.63s |
| medical-claims | 301 passed in 0.93s |
| **TOTAL** | **3,128 passed, 0 failed, 3 warnings** |

Total pytest runtime across all modules: ~15 seconds wall (most < 2s each). No skips, no errors, no xfails observed. The root note about the collision means there is no single-command "run all tests" entry point — CI or any aggregate run must iterate per module.

---

## Database Status

PostgreSQL 17 is running in `infinityrx-postgres` (healthy, 10 hours uptime). Database `infinityrx`, user `infinityrx`.

**29 schemas present** (one per module folder + `shared`, `core`, `public`):

```
adjudication, ai_nlp, billing, core, dataiq, drug_database, drug_db, ebv_ebi,
edi, edi_compliance, med_prescriber_dir, medical_claims, member_mgmt,
mtm_clinical, payment_proc, pharmacy_dir, plan_design, prescriber_dir,
prior_auth, program_config, public, rebate_mgmt, reclaimrx, reporting,
rules_engine, shared, switch_conn, testing_sim
```

**Only 5 schemas have actual tables** — the rest are empty placeholders created ahead of their modules:

| Schema | Tables | Notes |
|---|---|---|
| `core` | 19 | audit_log, users, tenants, sessions, roles, permissions, notifications, jobs, job_runs, files, bank_holidays, exclusion_list, exclusion_matches, processed_events, user_fido2_credentials, alembic_version, etc. |
| `drug_database` | 23 | drugs, drug_packages, drug_patents, drug_orange_book, rxnorm_concepts, rxnorm_ndc_crosswalk, NADAC/ASP pricing + history, REMS, shortages |
| `pharmacy_dir` | 15 | ncpdp_pharmacies + 13 auxiliary NCPDP detail tables, pharmacy_exclusion_xref |
| `prescriber_dir` | 16 | prescribers, nppes_prescriber_details, dea_registrations, medicare_opt_out, credential_alerts, practice_affiliations, etc. |
| `shared` | 4 | ingestion_runs, ingestion_schedules, oig_leie_exclusions, sam_exclusions |

**Note:** `drug_database` / `drug_db` and `edi` / `edi_compliance` both exist — likely legacy/current pairs. Worth reconciling.

**Alembic migration files on disk (3 modules):**
- `modules/billing/migrations/versions/0001_fk_ondelete_policies.py`
- `modules/edi-compliance/migrations/versions/0001_edi_baseline.py`
- `modules/medical-claims/migrations/versions/0001_encrypt_phi_columns.py`

**Schemas populated without Alembic files:** `core` (19 tables), `drug_database` (23), `pharmacy_dir` (15), `prescriber_dir` (16), `shared` (4). These modules are either creating tables via `Base.metadata.create_all()` at bootstrap, have migrations stored outside `versions/`, or use a non-Alembic mechanism. This is a gap against best-practice migration discipline.

---

## Portal Status

**Build:** `npm run build` on `portal/operator` **succeeded** (exit code 0). Next.js build emitted a dynamic-route table with 100+ entries and reported no errors.

**Pages:** 99 `page.tsx` files in `portal/operator/app/`.

**API routes:** 3 `route.ts` files (server-side proxies).

**React components:** 180 `.tsx` files across `portal/` (excluding `node_modules`/`.next`); 74 under `portal/{operator,shared}/components/`.

**Sidebar navigation** (from `portal/operator/components/layout/nav-config.ts`) — 12 top-level modules:

```
Dashboard | Programs | Claims | Accounting | ReclaimRx | Analytics |
Directories | Client Management | EDI | Network | Reporting | Admin
```

Each renders nested children; active path auto-expands. Sidebar uses `hasPermission` gating and `canSeeModule` filtering — permissive during dev.

**Other portals present:** `portal/client-portal`, `portal/medical-portal`, `portal/member-portal`, `portal/pharmacy-portal`, `portal/shared`. Build status not verified (audit only ran operator).

---

## Reference Data

All three critical reference tables are populated with production-scale seed data:

| Table | Row Count |
|---|---|
| `drug_database.drugs` | 112,869 |
| `pharmacy_dir.ncpdp_pharmacies` | 82,643 |
| `prescriber_dir.prescribers` | 34,984 |

`shared.sam_exclusions` and `shared.oig_leie_exclusions` tables exist (population not counted).

`member_management` schema exists as `member_mgmt` but has **0 tables** — member data is not yet persisted.

---

## Integration Status

**Event bus wiring** — 10 modules have `main.py` with FastAPI app:
`ai-nlp, billing, core-platform, dataiq, drug-database, edi-compliance, medical-claims, member-management, prescriber-directory, reclaimrx, reporting` (payment-processing and pharmacy-directory have event code but no `main.py` visible on this pass).

Modules with `src/events/` (publishers + consumers):
`ai-nlp, billing, dataiq, drug-database, medical-claims, member-management, payment-processing, pharmacy-directory, prescriber-directory, reclaimrx, reporting` (11 modules).

Subscribers wired into `main.py` lifespan (verified via grep):
- `modules/billing/src/main.py:56` — "subscribe consumers to the event bus with idempotency wrappers" (5 consumers per recent commit).
- `modules/reclaimrx/src/main.py:29` — "Loads all 8 reclaimrx CONSUMER_ROUTING handlers and subscribes them to" (recent commit 4eed418).

**API contracts** — 98 event contracts documented at `docs/api-contracts/events/`. Dot-notation observed (`claim.ingested`, `ar.payment_received`, `fwa.investigation_opened`, `dataiq.anomaly_detected`, etc.).

**Module READMEs** — 13 module READMEs present (`ai-nlp, billing, core-platform, dataiq, drug-database, edi-compliance, medical-claims, member-management, payment-processing, pharmacy-directory, prescriber-directory, reclaimrx, reporting`).

**Module PRDs** — all Phase 1–3 modules have PRDs in `docs/prd/`; portal PRDs present for operator/member/pharmacy/medical/client.

---

## Infrastructure

`docker ps -a`:

| Container | Status | Ports |
|---|---|---|
| infinityrx-postgres | Up 10 hours (healthy) | 5432 |
| infinityrx-redis | Up 10 hours (healthy) | 6379 |
| infinityrx-rabbitmq | Up 10 hours (healthy) | 5672, 15672 (mgmt) |

No other containers (no API services, no workers, no portal running in Docker). Backend services are run locally via `uv run` during development.

---

## Recent Git Activity

Last 20 commits (most recent first):

```
a64d938 docs(audit): add Wave 1 remediation status report
deea175 fix(core-platform): mount notifications, bank_holidays, audit query routers
0f6abb4 feat(member-management): real eligibility queries in _query_db
4eed418 feat(reclaimrx): subscribe 8 event consumers to bus via lifespan
d9a6319 feat(billing): implement 5 event consumers — AP/AR pipeline functional
c33ac8c fix: resolve test failures from date drift and Pydantic regex
8aae7e5 security: rotate committed secrets, document encryption key generation
2fe6cdc feat(gov-exclusion): bulk Medicaid BIN loader + coverage report
590fe82 feat(data): add South Central Medicaid BIN/PCN/Group reference data (10 states)
9a0a1ca data(medicaid): Northeast state Medicaid pharmacy BINs
85a514f data(medicaid): Southeast state Medicaid pharmacy BINs
47d1a6d data(medicaid): Midwest state Medicaid pharmacy BINs
4658fee data(medicaid): West + Territories state Medicaid pharmacy BINs
bde499c feat(gov-exclusion): CSV loader and 36-test suite for government exclusion
b7ec317 feat(gov-exclusion): operator portal government programs admin page
1d13bd9 feat(gov-exclusion): government programs API router wired into core-platform
c193792 feat(gov-exclusion): ORM model, lookup service, and federal program BIN seeds
0109b2b feat(gov-exclusion): add Alembic migration for shared.government_program_bins
8f788d8 fix(rxnorm-ingestion): commit per batch; rollback on batch error; SAVEPOINT crosswalks
8f55e45 fix(ingestion): refresh CMS dataset IDs, openFDA REMS query, Purple Book scraper
```

**Branches:** `main` (current), module/core-platform/{t1-infra-db, t2-auth-users, t3-events-audit-notif, t4-jobs-files-excl-health}, `claude/wonderful-mestorf`, and 8 `worktree-agent-*` branches (parallel-agent worktrees — historical artifacts).

**Uncommitted changes:** 21 files modified (no new commits needed on this audit pass), mostly operator-portal updates + core-platform auth seed changes + billing event refactor. `.gstack/`, module `uv.lock` files, and many untracked portal pages under `portal/operator/app/accounting/`, `admin/encryption/`, `analytics/*`, `clients/*`, `edi/page.tsx`, `network/` indicate live portal buildout in progress.

---

## Known Issues

- **TODO/FIXME/HACK comments:** 291 across `modules/` + `portal/` (`.py, .ts, .tsx`). Non-zero but manageable; CLAUDE.md requires linked tasks for each.
- **Root pytest broken:** `openpyxl` not resolvable in the root-run interpreter. Per-module `uv run` works fine. CI must iterate per module — there is no single green `pytest` at the repo root today.
- **Empty module directories still exist** for 11 Phase-4 modules (`adjudication-engine, ebv-ebi-rtbc, medical-prescriber-directory, mtm-clinical, part-d-pde, plan-design, prior-authorization, program-config, rebate-management, rules-engine, switch-connectivity, testing-simulator`). CLAUDE.md testing rule says "If a module isn't being built this phase, its files should not exist (only the folder structure)". Folder-only state satisfies the rule; empty schemas in Postgres for all 11 do not.
- **Schema divergence:** `drug_database` vs `drug_db`, `edi` vs `edi_compliance` — duplicate schemas that should be reconciled.
- **Migration discipline gap:** Only 3 modules have Alembic `versions/*.py` files, yet 5 schemas have populated tables. Four modules are creating tables without tracked migrations.
- **Empty backend services at runtime:** No backend API containers are running. Only Postgres, Redis, RabbitMQ are up. Any end-to-end test against the portal would need services manually started.
- **Worktree artifacts:** 8 `worktree-agent-*` branches linger from prior parallel-agent runs. Probably safe to prune after verifying they contain no orphan work.
- **13 critical audit findings (CR-01 … CR-13)** catalogued in `docs/audit/full-platform-audit-2026-04-14.md` (platform score 63/100). This status audit cross-references the CLAUDE.md table: several are in-flight (CR-01/CR-11 billing consumers wired, CR-13 table refreshed, 4eed418 handles reclaimrx subscriptions). PHI plaintext in medical-claims (CR-02) and JWT-auth gaps in medical-claims/edi-compliance (CR-03) remain open per CLAUDE.md table.

---

## Module-by-Module Detail

**ai-nlp (Phase 3, built).** 13 source files, 148 passing tests. API + events + consumers wired; Azure OpenAI integration, document intelligence, RAG chatbot, prompt templates, output guardrails per PRD. CLAUDE.md notes PRD coverage ~48% — 20+ advanced features (denial prediction, FHIR PA, fax splitting) not yet implemented.

**billing (Phase 2, in progress).** 25 source files, 171 passing tests, 1 Alembic migration (FK ON DELETE policies). AP/AR event consumers wired as of commit d9a6319 (5 consumers). Journal hash chain, NACHA, 835 exist; CLAUDE.md notes 50-state compliance tables and accounting adapters still missing.

**core-platform (Phase 1, built).** 73 source files, 198 passing tests, 10 migrations. Auth (MFA, FIDO2, sessions, API keys), audit hash chain, tenants, DLQ, notifications, jobs, files, exclusion lists, bank holidays — all now mounted on production app per commit deea175. 19 tables in `core` schema. Production-ready primitive layer.

**dataiq (Phase 3, built).** 13 source files, 150 passing tests. Analytics endpoints, dashboards; CLAUDE.md notes what-if, NL query, forecast, and MTM targeting missing from router.

**drug-database (Phase 3, built).** 34 source files, 177 passing tests. 112,869 drugs loaded, full RxNorm crosswalk, NADAC/ASP pricing + history, Orange/Purple Book, REMS, shortages. Production-scale reference data. Compound ingredients table missing per CLAUDE.md.

**edi-compliance (Phase 4, built).** 41 source files, 822 passing tests — the largest test surface. Full X12 (835/837/270/271/276/277/278/834/999), AS2+SFTP, NCPDP Batch 1.2, FHIR bridge. 1 Alembic migration (baseline). CLAUDE.md flags CR-03: no JWT auth on endpoints.

**medical-claims (Phase 4, built).** 33 source files, 301 passing tests. Full claim pipeline, CMS-1500/UB-04 generation, accumulator integration. 1 migration encrypting PHI columns. CLAUDE.md flags CR-02 (PHI still plaintext in parts) and CR-03 (no JWT auth).

**member-management (Phase 3, built).** 26 source files, 174 passing tests. 834/CSV ingestion, accumulators, 270/271 eligibility. Commit 0f6abb4 added real DB eligibility queries. Schema `member_mgmt` exists but empty — ingestion not yet run against real dataset. Consent and COBRA tracking missing.

**payment-processing (Phase 2, in progress).** 26 source files, 276 passing tests. NACHA submission, ACH return handling (80+ codes), vendor adapters, OFAC screening, business-day calendar. No migrations tracked; no FastAPI main.py detected in this pass.

**pharmacy-directory (Phase 3, built).** 28 source files, 198 passing tests. 82,643 pharmacies loaded, 15 tables including NCPDP detail tables, credentialing, PSAO. Accreditation, LDD, and contract rate history missing per CLAUDE.md.

**prescriber-directory (Phase 3, built).** 26 source files, 210 passing tests. 34,984 prescribers, NPPES details, DEA registrations, Medicare opt-out, Medicare Part D utilization, state prescribing rules. DEA authority check, panel size, supervisory relationships missing; no tenant isolation fence (CR-09) per CLAUDE.md.

**reclaimrx (Phase 2, in progress).** 22 source files, 154 passing tests. FWA detection, ML scoring, graph analysis, recovery estimation. Commit 4eed418 subscribed 8 consumers to the event bus via lifespan — closing CR-11 for this module.

**reporting (Phase 2, in progress).** 24 source files, 149 passing tests. Dashboards, Star Ratings PDC, Excel/PDF exports. Scheduled delivery not wired per CLAUDE.md. No migrations tracked.

**Unbuilt Phase-4 modules (folder-only):** `adjudication-engine, ebv-ebi-rtbc, medical-prescriber-directory, mtm-clinical, part-d-pde, plan-design, prior-authorization, program-config, rebate-management, rules-engine, switch-connectivity, testing-simulator`. Each has 0 code files, 0 tests, 0 migrations. Postgres schema stubs exist for all of them and should either be removed or tracked as placeholder-only.

---

**Bottom line:** 13 modules implemented with 3,128 passing tests. Core platform primitives are mounted. Operator portal builds cleanly with 99 pages routed. Reference data is at production scale (112k drugs, 82k pharmacies, 35k prescribers). Open risks: 13 critical audit findings per the existing remediation doc, root-level pytest broken, migration discipline inconsistent, 11 Phase-4 modules not started. No regressions vs. CLAUDE.md status table.
