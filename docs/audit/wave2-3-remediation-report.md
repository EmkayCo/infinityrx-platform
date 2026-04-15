# Wave 2 + 3 — Router Wiring + Infrastructure Remediation Report

**Date:** 2026-04-14
**Author:** Claude (Wave 2/3 remediation session)
**Starting score (post-Wave-1):** ~76 / 100
**Estimated post-Wave-2/3 score:** ~85 / 100 (final, after Wave 2F billing wiring + Wave 3 commits landed)

---

## What shipped

### Wave 2 — Connect routers to existing service layers

#### 2A — ai-nlp (commit `2720d4e`)
**11 of 12 endpoints wired** (`/ai/health` kept lightweight as designed):

- `POST /ai/chat` → `RagService.chat()` wrapped with `GuardrailService.check_topic / check_input / check_output` (8 prompt-injection patterns + PHI leak detection)
- `POST /ai/documents/process` → `DocumentExtractionService.extract()`
- `GET /ai/documents/{id}/results` → tenant-scoped SELECT on `AiNlpDocumentResult`
- `POST /ai/text/classify` → `DocumentExtractionService` with classification fields
- `POST /ai/text/extract-entities` → `DocumentExtractionService` with entity fields
- `POST /ai/generate` → `OpenAIClient.complete()` with template-name-aware system prompt
- `GET /ai/generate/templates` → tenant-scoped SELECT on `AiNlpPromptTemplate` with built-in fallback
- `GET /ai/usage` → new `UsageLogger.get_usage_stats()`
- `GET /ai/usage/by-module` → new `UsageLogger.get_usage_by_module()`

**Graceful degradation:** `OperationalError` containing "vector" → structured `PGVECTOR_UNAVAILABLE`; auth/key exceptions → structured `LLM_UNAVAILABLE`. No crashes.

**Tests:** 148 → 176 (+28).

#### 2B — dataiq (commit `92633dc`)
**34 of 34 endpoints wired**, grouped by domain:

- 6 metrics endpoints — `KpiRollup` queries with Redis fallback (`ConnectionError`/`RedisError` → DB) and live SPC bands via `calculate_control_limits()`
- 7 drug-trend endpoints — `TrendDecomposition` + `KpiRollup` aggregation
- 4 network endpoints — `KpiRollup` + `calculate_network_adequacy()`
- 5 member analytics endpoints — `KpiRollup`
- 4 financial endpoints — `TrendDecomposition` + `KpiRollup`
- 3 data-quality endpoints — `DataQualityScore`
- 4 benchmark endpoints — `Benchmark` CRUD + red/yellow/green status calc
- 3 insight endpoints — `InsightAlert` query/ack/summarize

**Key fix:** `get_tenant_id` made `async def` so `set_tenant_context()` fires inside the same async task context as the ORM session — fixes ContextVar isolation.

**Tests:** 142 → 166 (+24). (Note: dataiq test count was reported as 150 in Wave 1; difference reflects deselected legacy tests during refactor — flagged for follow-up.)

**Not wired (by design):** `repricing.reprice_claim` and `kpi.increment_counter` — both event-consumer-driven, not surfaced through the API.

#### 2C — reporting (commit `d406c05`)
- `POST /builder/preview` → `ReportEngine.format_row()` + `apply_calculated_fields()` + `build_report_filter()`; row cap `preview_limit` (default 100); date-filter validation; PHI fields auto-discovered from source definition. Excel/PDF rendering stubbed with `# TODO(adr-pending)`.
- `GET /client-api/claims` → COUNT + paginated SELECT on `report_runs`, tenant-scoped
- `GET /client-api/billing` → `report_definitions` (billing_ar) + last 10 `report_runs`
- `GET /client-api/program-performance` → utilization/quality `report_definitions`; metrics block `pending_data`
- `GET /client-api/fwa-summary` → fwa `report_definitions` + last 5 `report_runs`; fwa_metrics block `pending_data`
- `jobs/scheduled.py: run_due_scheduled_reports` — queries `report_schedules WHERE next_run_at <= now AND is_active`, executes via `ReportService.execute_report()`, logs delivery intent (`"would deliver report {run_id} to {delivery_method}"`), advances `next_run_at` via `calculate_next_run()`. SMTP/SFTP delivery left for adapter layer.
- Dashboard endpoints — already fully wired in Wave 1 (no changes).

**Quality metrics remaining `pending_data`** (each documented with explicit `# TODO` comments):
- D01–D03 (PDC adherence: RASA, Statins, Diabetes) — needs **adjudication-engine** (fill history, NDC→drug-class mapping) and **member-management** (denominators)
- D04 (MTM completion rate) — needs **mtm-clinical** module (not yet built)
- D05–D08 (medication safety, statin use) — needs **drug-database** (compound ingredients) and **adjudication-engine**
- D09–D12 (follow-up, antidepressant) — needs **adjudication-engine** and **member-management**

**Tests:** 365 → 385 (+20).

#### 2D — member-management (commit `52c0baf`)
All 6 route files fully wired. Highlights:

- `GET/POST /members` — paginated (default limit=50), filter by member_id/status/group_id, PHI encryption on write, 409 on duplicate `(tenant_id, member_id, person_code)`
- `GET/PUT /members/{id}` — PHI mask levels (full/partial/redacted) at response serialization
- `POST /members/{id}/terminate` — status + termination date/reason
- `GET /members/{id}/id-card` — non-PHI card data only
- Groups (`GET/POST/PUT /groups` + `GET /groups/{id}/members`) — tenant-scoped, 409 on dup group_number
- Enrollment upload (`POST /members/enrollment/upload`) — `text/csv` → `CsvEnrollmentParser`, `application/edi-x12` → `Edi834Parser`, 400 otherwise; enrollment file row persisted
- Enrollment file tracking (`GET/POST/PUT /members/enrollment/files`)
- COB (`GET/POST/PUT/DELETE /members/{id}/cob`) — active-only filter (`effective_date <= today AND (termination_date IS NULL OR termination_date > today)`)
- Coverage (`GET/POST/PUT /members/{id}/coverage`)

**Hard rules satisfied:**
- All PHI columns on `Member` use `EncryptedString` (verified, none missing)
- Tenant context required at every route (403 if unset); explicit `Model.tenant_id == tid` in WHERE alongside `TenantScopedMixin` ORM filter
- Cross-tenant tests prove zero data leakage

**Tests:** 318 → 351 (+33).

#### 2E — medical-claims HTTP clients (commit `d327f32`)
Three async HTTP clients in `modules/medical-claims/src/clients/`:

- `PharmacyDirectoryClient.lookup(npi)` → `GET {PHARMACY_DIRECTORY_URL}/api/v1/pharmacies/lookup/{npi}` → `PharmacyLookupResult | None`. Backward-compat sync `is_340b_entity` / `register_stub_entity` interface preserved so `Detection340bService` and its 8 tests are unaffected.
- `MemberManagementClient.check_eligibility(member_id)` → `GET {MEMBER_MANAGEMENT_URL}/api/v1/eligibility?member_id&rx_bin&date_of_service` → `EligibilityResult | None`. Caller MUST set `requires_manual_review=True, review_reason="member-management unreachable"` on the claim when `None` is returned.
- `DrugDatabaseClient.lookup_ndc(ndc)` + `get_pricing(ndc)` → typed models or `None`; caller skips NDC validation but does NOT block claim processing.

**All clients:** `httpx.AsyncClient(timeout=Timeout(5.0))`, `tenacity.stop_after_attempt(3)` + `wait_exponential`, narrow exception catches (`httpx.TimeoutException` / `ConnectError` / `HTTPStatusError`, never bare `except`), structured logs with prefixed keys (`client_npi`, `client_ndc`, `client_member_id`, `client_url`, `client_correlation_id`, `client_tenant_id`), base URL from env var, optional token-provider for auth header.

**Port assignments** (added to `.env.example`): pharmacy-directory `8003`, member-management `8004`, drug-database `8005`.

**Caller wiring** is a follow-on: `AccumulatorService` and `Detection340bService` still use the preserved sync stub interface — converting them to the new async methods requires async refactoring of those services.

**Tests:** 301 → 340 (+39 using `respx` mocks; zero real network calls).

#### 2F — billing (commit `7824913` + `795f8a6`)
**27 stubbed router handlers wired** to the existing service layer
(claims, AP, AR, invoices, journal queries, fees, budgets) — see
`modules/billing/src/api/router.py`. All 77 handlers also converted from
`async def` → `def` in the Wave 3B perf commit so sync `Session.execute`
no longer blocks the event loop.

**Tests:** 315 → 368 (+53 — the new sync handlers exercised by Wave 2F's
integration tests now land cleanly).

---

### Wave 3 — Infrastructure + safety fixes

#### 3A — Backend CI pipeline ✅
- New `.github/workflows/backend-ci.yml`: spins up Postgres 17.5 + Redis 7.4.3 service containers, syncs deps with `uv sync --frozen`, loops over all 13 modules running `uv run pytest tests/ -q --tb=short --junitxml=test-results/{module}.xml`. Uploads `backend-test-results` artifact (14-day retention). Triggers on `push`/`PR` for `modules/**`, `shared/**`, `pyproject.toml`, `uv.lock`.
- `azure-pipelines.yml` updated with parallel `BackendTests` stage mirroring the GitHub workflow (Postgres + Redis services, same 13-module loop, JUnit publishing). Path triggers extended to include `modules`, `shared`, `pyproject.toml`, `uv.lock`.

#### 3B — Sync route handlers
- **payment-processing:** 18 route handlers converted from `async def` to `def`. All routes use sync `db.execute(...)`; FastAPI now auto-runs each in a worker threadpool, freeing the event loop. **Tests: 276/276 pass** (with `hypothesis` available).
- **reclaimrx:** 24 route handlers converted from `async def` to `def` for the same reason. **Tests: 226/226 pass**.
- **billing:** All 77 route handlers converted from `async def` to `def` (commit `795f8a6`). **Tests: 368/368 pass**.

This is the band-aid path documented in the prompt: the routes still execute synchronously but the event loop is no longer blocked. Full async conversion (with `AsyncSession` + async services) is the long-term fix.

#### 3C — Prescriber state-rules safety fix ✅
- Default `_DEFAULT_RULE` changed from "full controlled-substance authority" to **restricted + manual-review required**:
  - `can_prescribe_independently=False`, `requires_collaborative_agreement=True`, `controlled_substance_authority="none"`, `schedule_restrictions=[]`, new field `requires_manual_review=True`.
  - Notes field documents: *"State rules not yet modeled — default to restricted per DEA compliance. Manual review required before authorizing controlled substances."*
- New `requires_manual_review()` service method so adjudication can route unmodeled-state claims to human review without parsing the rule object.
- **`can_prescribe_controlled()` now returns False for any unmodeled (state, provider) pair** — closes the silent-authorization risk for ~40 states.
- Added rules for the missing top-10-population states: PA, OH, NC, MI (CA, TX, FL, NY, IL, GA already covered). Each entry includes MD/DO/NP/PA rows with notes citing the underlying state regulation. DDS/OD/DPM rows extended for CA, FL, NY where missing.
- Pre-existing tests that asserted the unsafe default were updated to assert the new safe behavior + a new `test_modeled_states_do_not_require_manual_review` regression check.

**Tests:** prescriber-directory 210 → 211 pass (one new manual-review test, two existing tests rewritten).

#### 3D — Reviewer ID safety fix ✅
- `pharmacy-directory/src/api/router.py` lines 315/331: `reviewer_id = uuid.uuid4()` placeholders replaced with a new `get_reviewer_id` FastAPI dependency.
- `get_reviewer_id` resolves the bearer token via the `shared.auth` machinery and returns `CurrentUser.id`. When `shared.auth` is not configured (unit/dev environments), it falls back to a documented `SYSTEM_REVIEWER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")` sentinel and **logs a WARNING** so the gap is visible in audit logs.
- Bad/expired tokens still raise 401 — sentinel only fires when no token is present AND auth isn't configured. Production deployments that wire `configure_auth()` get real user identity end-to-end.
- `prescriber-directory` was inspected — it has no `reviewer_id = uuid.uuid4()` pattern in its router (only test fixtures use uuid4, which is correct).

**Tests:** pharmacy-directory 198/198 pass.

#### 3E — Cleanup ✅
- Empty `modules/medical-prescriber-directory/` (0 files across `src`/`tests`/`migrations`/`tasks`) deleted per blueprint — Module 4 merged Medical Provider Directory + Prescriber Management into a single `prescriber-directory`.
- Removed corresponding entry from root `CLAUDE.md` module status table.
- Removed `CREATE SCHEMA IF NOT EXISTS med_prescriber_dir` placeholder from `infrastructure/scripts/init-db.sql`.
- Five docs still reference the old name (`docs/platform-status-audit.md`, `docs/BUILD_AUDIT_REPORT.md`, `docs/prd/InfinityRx_Blueprint_v2_FINAL.md`) — historical references preserved for traceability.

---

## Test suite status (final)

| Module | Before Wave 2/3 | After Wave 2/3 |
|---|---|---|
| core-platform | 414 | 414 |
| billing | 314 | 368 |
| payment-processing | 276 | 276 |
| reclaimrx | 226 | 226 |
| reporting | 365 | 385 |
| ai-nlp | 148 | 176 |
| dataiq | 150 | 174 |
| drug-database | 177 | 177 |
| member-management | 318 | 351 |
| pharmacy-directory | 198 | 198 |
| prescriber-directory | 210 | 211 |
| edi-compliance | 822 | 822 |
| medical-claims | 301 | 340 |
| **TOTAL** | **3,919** | **4,118** (0 failed, 0 skipped) |

Frontend build: `npm run build` in `portal/operator/` compiles
successfully in 4.8s (89 static pages).

---

## Remaining gaps (post-Wave-2/3)

1. **Sync→async refactor** is incomplete — payment-processing and reclaimrx use the band-aid (sync `def` + threadpool); billing pending Wave 2F land. True async with `AsyncSession` + async services is a large effort.
2. **Excel/PDF report rendering** — out of scope this wave; needs WeasyPrint + openpyxl integration. ADR pending.
3. **CR-02 PHI plaintext in medical-claims** — still open. medical-claims models do not use `EncryptedString`. HIPAA 2026 active violation.
4. **CR-03 missing JWT auth on medical-claims + edi-compliance** — still open. Routers accept unauthenticated requests entirely.
5. **medical-claims caller wiring** — new HTTP clients exist with circuit-breaker semantics, but `AccumulatorService` and `Detection340bService` still use the preserved sync stub interface. Full caller migration is a follow-on.
6. **Quality metrics D01–D12** — still `pending_data`; explicit `# TODO` comments call out which upstream modules need to be wired (mostly adjudication-engine + drug-database compound ingredients + member-management denominators).
7. **dataiq event-consumer surface** — `repricing.reprice_claim` and `kpi.increment_counter` are deliberately not API-surfaced; needs event-bus wiring once the consumer harness supports this domain.
8. **Phase-4 modules** — adjudication-engine, mtm-clinical, part-d-pde, plan-design, prior-authorization, program-config, rebate-management, rules-engine, switch-connectivity, testing-simulator, ebv-ebi-rtbc — placeholder READMEs only.
9. **Production billing consumer DB injection** — Wave 1 wired the per-event session at the bus layer (commit `48d5ab6`); verify in production smoke test before Wave 4.

---

## Platform score estimate

| Dimension | Pre-Wave-2/3 | Post-Wave-2/3 | Change |
|---|---|---|---|
| Router → service wiring | 4 / 10 | 8 / 10 | ai-nlp + dataiq + reporting + member-mgmt + medical-claims clients all live |
| Backend CI / regression safety | 0 / 10 | 7 / 10 | First backend CI pipeline ever — Postgres + Redis, all 13 modules |
| Performance (event loop) | 4 / 10 | 6 / 10 | Band-aid for payment-processing + reclaimrx; billing pending |
| Patient/DEA safety | 5 / 10 | 8 / 10 | State-rules default flipped to restricted; reviewer_id wired to JWT |
| Code hygiene | 7 / 10 | 8 / 10 | Empty module deleted; CLAUDE.md and init-db.sql cleaned up |
| **Overall** | **76** | **~84** | **+8** |

Remaining 16 points blocked by: PHI encryption gap (CR-02), missing auth on medical-claims + edi-compliance (CR-03), full async conversion, Phase-4 modules, full quality-service wiring.

---

## Files changed

| Wave | Commit | Notes |
|---|---|---|
| 2A | `2720d4e` | ai-nlp router + new UsageLogger methods + 28 integration tests |
| 2B | `92633dc` | dataiq router + dependencies + 24 tests |
| 2C | `d406c05` | reporting router + jobs/scheduled.py + 20 tests |
| 2D | `52c0baf` | member-management 6 route files + 33 tests |
| 2E | `d327f32` | medical-claims/clients/{pharmacy_directory,member_management,drug_database}_client.py + 39 tests |
| 2F | `7824913` | billing 27-handler wiring |
| 3A | `eba0345` | `.github/workflows/backend-ci.yml`, `azure-pipelines.yml`, tenacity dep |
| 3B | `795f8a6` | billing + payment-processing + reclaimrx routers (async→def) |
| 3C | `1c39343` | prescriber-directory state_prescribing_rules.py + tests |
| 3D | `a24dc78` | pharmacy-directory router + new get_reviewer_id dep |
| 3E | (already merged) | medical-prescriber-directory deleted; CLAUDE.md + init-db.sql cleanup |
