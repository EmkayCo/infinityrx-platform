Reading prompt from stdin...
OpenAI Codex v0.128.0 (research preview)
--------
workdir: C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 019e1a82-111b-7ab2-bc50-84885e3cb5c5
--------
user
# Codex B9.A mini-GATE-CLOSE R1 — Consult Prompt

**Wave:** B9 (FDB NDDF Plus 217-table extension)
**Phase:** B9.A (cross-cutting infra; pre-Tier-A work)
**Verdict requested:** GO / GO-WITH-FIXES / NO-GO
**Charter version:** v3.2 LOCKED
**Plan version:** v3.1 LOCKED

## What you are reviewing

B9.A laid the cross-cutting infrastructure that B9.B-G (113+66+16+1+2+19
= 217 tables) will consume. No FDB models have landed yet. The work
is contract / registry / preflight / lock-in — the SCAFFOLD that
makes B9.B-G's per-table work mechanical and gate-able.

## Commits in scope (9 commits on `develop`)

```
503cd7b B7.3: restore Phase 11A ground truth (ifx_prod_app regression repair)
9b19457 B9.A C1: TableSpec registry expansion — Tier + DeltaSemantics + 4 fields
e54425f B9.A C2: generated migration template for FDB tier batches
3ead3bd B9.A C3: ingester contract test template + N4/A4/T12 mitigations
33a2fb3 B9.A C4: FDB MTL config flag + loader registry + DB-level guard template
d6cefd8 B9.A C8: SQLite-backed DELTA_SEMANTICS simulator + A4 regression detector
2b1f2b9 B9.A C9: reference-DB write-path guard (env-var strict + SQL assertion)
c03e37a B9.A C10: FDW name-collision preflight script + test seam
60c6cc0 B9.A C11: setup_fdw.sh manifest-derived count + deterministic sort
9b61d6d B9.A C12+C13: Phase 09 compat baseline + module base profile lock-in
```

(C5-C7 are administrative — codex consults captured pre-session and
plan v-bump; no code.)

## Files added / modified

### New helpers + registries
- `modules/drug-database/scripts/gen_fdb_tier_migration.py` (C2)
- `modules/drug-database/drug_database/services/fdb_loader_registry.py` (C4)
- `modules/drug-database/drug_database/services/fdb_adapter.py` (C1 — Tier + DeltaSemantics enums + 4 TableSpec fields)
- `shared/db/write_path_guard.py` (C9)
- `infrastructure/scripts/preflight_b9_name_collision.py` (C10)
- `infrastructure/scripts/setup_fdw.sh` (C11 — manifest-derived count)
- `infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` (C4 — DB-level MTL guard)
- `shared/config.py` (C4 — `FDB_LOAD_MTL: bool = False`)

### New test surface (116 unit + 3 integration)
- `modules/drug-database/tests/_fdb_contract.py` (C3 — reusable contract helpers)
- `modules/drug-database/tests/_fdb_delta_semantics.py` (C8 — SQLite simulator)
- `modules/drug-database/tests/unit/test_fdb_adapter.py` (C1 — 24 tests)
- `modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py` (C2 — 12)
- `modules/drug-database/tests/unit/test_fdb_contract.py` (C3 — 22)
- `modules/drug-database/tests/unit/test_fdb_loader_registry.py` (C4 — 14)
- `modules/drug-database/tests/unit/test_fdb_delta_semantics.py` (C8 — 8)
- `modules/drug-database/tests/unit/test_module_base_profile.py` (C13 — 3)
- `modules/drug-database/tests/integration/test_phase09_compat_baseline.py` (C12 — 3 DB-skip)
- `shared/tests/db/test_write_path_guard.py` (C9 — 11)
- `shared/tests/db/test_preflight_b9_name_collision.py` (C10 — 16)
- `shared/tests/db/test_setup_fdw_manifest.py` (C11 — 9)

### Wave artifacts (Werkbench)
- `waves/B9/phase09_compat_baseline.md` (C12)
- `waves/B9/module_base_profile.md` (C13)
- `waves/B9/write_path_enforcement.md` (C9)
- `waves/B9/parse_warning_allowlist.md` (C3 — empty initial)
- `waves/B9/status.md` (C14 — ledger)

## Test result

```
cumulative B9.A: 116 unit pass + 3 integration skip
drug-database unit suite:        326 → 329 PASS, no regression
shared/tests/db (new files):     45/45 PASS in isolation
```

Pre-existing baseline failures (195, per `waves/B9/baseline.md`) are
out of B9 scope per charter §Out-of-scope.

## Charter SC coverage

See `waves/B9/status.md` → "Charter / SC mapping" section. All 10
charter SCs have an explicit B9.A status row. B9.A does not CLOSE
any SC by itself — it readies the scaffolding so B9.B-G can close
SC-1 through SC-10 incrementally with the same template.

## Areas to scrutinize

1. **`fdb_loader_registry.filter_loadable_specs`**: the load-bearing
   assertion that `loader_group="fdb_mtl"` is excluded under
   `FDB_LOAD_MTL=False` regardless of `only_groups`. Test
   `test_filter_only_groups_mtl_still_denied_under_default_flag`
   pins this. Is there a code path that bypasses this guard?

2. **`assert_delta_semantics_acd_cycle`**: the A4 mitigation.
   Verifies UPSERT correctness via simulated INSERT...ON CONFLICT DO
   UPDATE. The SQLite simulator at C8 reproduces the exact regression
   (DO NOTHING) and asserts the contract catches it
   (`test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing`).
   Is the abstract surface (`_fdb_contract.py:421-509`) tight enough
   that a B9.B per-table test cannot accidentally bypass it?

3. **`scan_for_collisions` in C10**: hard / soft / unknown-schema
   triage. Unknown schemas are treated as HARD (fail-safe). Is the
   `_OWNED_SCHEMAS` / `_HARD_COLLISION_SCHEMAS` frozenset coverage
   complete vs the current `infinityrx_reference` schema list (per
   `baseline.md`: core, drug_database, drug_db, pharmacy_dir,
   prescriber_dir, public, reference, shared)?

4. **`setup_fdw.sh` C11 floor 66**: replaces `-ne 66` with `-lt 66`.
   Is the floor protection equivalent? (Truncation to < 66 still
   fails; expansion >= 66 succeeds — which is the B9 growth path.)

5. **C9 strict env-var resolution**: `resolve_reference_db_url`
   removes the Phase 09 fallback chain. Phase 09's existing
   `scripts/load_fdb.py` is UNCHANGED (kept untracked / Phase 09
   modes use the legacy chain). B9.B-G tier loaders, when built,
   will import the strict resolver directly. Is this split (strict
   for B9, legacy for Phase 09) a reasonable backward-compat
   pattern, or should B9.A have also migrated Phase 09 to strict
   mode?

6. **Contract template `assert_no_parse_warnings`**: defaults to
   zero tolerance. Allowlist requires CONSULT-ROUND sign-off
   (documented in `parse_warning_allowlist.md`). Is the policy
   clear enough that a B9.B operator cannot quietly extend the
   allowlist without going through the gate?

7. **Module base profile C13**: the test asserts
   `len(DrugBase.metadata.tables) == 9` as an EQUALITY (not floor).
   The intent is to force the refactor decision when B9.B's first
   misplaced model bumps the count. Is this too brittle (might
   trip on unrelated drug-database PRs) or appropriately strict?

8. **MTL REVOKE template `fdb_mtl_revoke.sql.tmpl`**: substitution
   placeholders `{{SCHEMA}}`, `{{MTL_TABLES}}`, `{{APP_ROLES}}`,
   `{{APP_ROLES_QUOTED}}`. The verification block uses
   `{{APP_ROLES_QUOTED}}` which the docstring doesn't list. Is
   that a documentation gap, or a real bug?

## Verdict format

Return either:

- **GO** — B9.A closes; B9.B opens.
- **GO-WITH-FIXES** — list of HIGH / MEDIUM concerns; B9.A re-opens
  for a fix cycle, then re-consults.
- **NO-GO** — fundamental issue requires charter or plan revision.

For GO-WITH-FIXES, return concerns in the format:

```
| Severity | Area | Issue | Suggested fix |
```

codex
I’ll inspect the scoped commits and the specific guard/contract files before giving a gate verdict. The workspace is read-only, so this will be review-only: code and test evidence, no edits.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"filter_loadable_specs|FDB_LOAD_MTL|loader_group|assert_delta_semantics_acd_cycle|assert_no_parse_warnings|scan_for_collisions|_OWNED_SCHEMAS|_HARD_COLLISION_SCHEMAS|resolve_reference_db_url|APP_ROLES_QUOTED|DrugBase\\.metadata\\.tables|len\\(DrugBase\" modules shared infrastructure waves -S" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git log --oneline --decorate -12' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 636ms:
 M .claude/agents/tier1-core/qa-security-phi.md
 M .claude/rules/security.md
 M .claude/rules/testing.md
 M .claude/settings.json
 M .env.example
 M .github/workflows/backend-ci.yml
 M .gitignore
 D .gstack/qa-reports/portal-ux-audit-2026-04-14.md
 M CLAUDE.md
 M conftest.py
 D data/reference/ncpdp/NCPDP_v3.1_Monthly_Master_20240501.ZIP
 M docker-compose.yml
 M docs/api-contracts/events/claim.adjudicated.md
 M docs/lessons-learned.md
 M docs/prd/prd-edi-compliance.md
 M docs/prd/prd-switch-connectivity.md
 M infrastructure/docker/init-schemas.sql
 M infrastructure/scripts/backup.sh
 M infrastructure/scripts/init-multi-db.sql
 M infrastructure/scripts/restore.sh
 M infrastructure/scripts/run_migrations.sh
 M infrastructure/scripts/run_reference_loaders.sh
 M infrastructure/scripts/switch_env.sh
 M infrastructure/scripts/verify_backup.py
 M modules/adjudication-engine/pyproject.toml
 M modules/adjudication-engine/src/api/routes.py
 M modules/adjudication-engine/src/api/schemas.py
 M modules/adjudication-engine/src/events/publishers.py
 M modules/adjudication-engine/src/main.py
 M modules/adjudication-engine/src/models/tables.py
 M modules/adjudication-engine/src/services/adjudication_pipeline.py
 D modules/adjudication-engine/src/services/ncpdp_parser.py
 M modules/adjudication-engine/src/services/override_service.py
 M modules/adjudication-engine/tests/unit/test_adjudication.py
 D modules/adjudication-engine/tests/unit/test_ncpdp_parser.py
 M modules/ai-nlp/src/events/__init__.py
 M modules/ai-nlp/src/events/consumers.py
 M modules/ai-nlp/src/services/guardrails.py
 M modules/ai-nlp/src/services/usage_logger.py
 M modules/ai-nlp/tests/unit/test_prompt_templates.py
 M modules/billing/alembic/env.py
 M modules/billing/src/db/session.py
 M modules/billing/src/services/nacha.py
 M modules/billing/tests/golden/nacha_sample.txt
 M modules/billing/tests/unit/test_nacha_generator.py
 M modules/core-platform/alembic/env.py
 M modules/core-platform/src/__init__.py
 M modules/core-platform/src/_shim/config.py
 M modules/core-platform/src/api.py
 D modules/core-platform/src/exclusions/__init__.py
 D modules/core-platform/src/exclusions/api.py
 D modules/core-platform/src/exclusions/ingestion.py
 D modules/core-platform/src/exclusions/job_handler.py
 D modules/core-platform/src/exclusions/matching.py
 D modules/core-platform/src/exclusions/screening_service.py
 M modules/core-platform/src/government_programs/api.py
 M modules/core-platform/src/jobs/verify_audit_chain_job.py
 M modules/core-platform/src/main.py
 M modules/core-platform/src/models.py
 M modules/core-platform/tests/bank_holidays/conftest.py
 M modules/core-platform/tests/bank_holidays/test_api.py
 D modules/core-platform/tests/exclusions/__init__.py
 D modules/core-platform/tests/exclusions/test_api.py
 D modules/core-platform/tests/exclusions/test_ingestion.py
 D modules/core-platform/tests/exclusions/test_job_handler.py
 D modules/core-platform/tests/exclusions/test_matching.py
 D modules/core-platform/tests/exclusions/test_screening_service.py
 D modules/core-platform/tests/infrastructure/test_alembic_baseline.py
 M modules/drug-database/alembic/env.py
 M modules/drug-database/pyproject.toml
 M modules/drug-database/src/db/session.py
 M modules/drug-database/src/services/pricing.py
 M modules/drug-database/tests/conftest.py
 M modules/drug-database/tests/integration/test_api_endpoints.py
 M modules/drug-database/tests/integration/test_api_router_coverage.py
 M modules/drug-database/tests/integration/test_app_middleware.py
 M modules/drug-database/tests/integration/test_coverage_gaps_integration.py
 M modules/drug-database/tests/unit/test_coverage_gaps.py
 M modules/drug-database/tests/unit/test_drug_lookup_service.py
 M modules/drug-database/tests/unit/test_events_publishers.py
 M modules/drug-database/tests/unit/test_final_coverage_gaps.py
 M modules/drug-database/tests/unit/test_infrastructure.py
 M modules/drug-database/tests/unit/test_interaction_service.py
 M modules/drug-database/tests/unit/test_ndc_normalizer.py
 M modules/drug-database/tests/unit/test_parsers.py
 M modules/drug-database/tests/unit/test_pricing_service.py
 M modules/drug-database/uv.lock
 M modules/edi-compliance/src/api/generate.py
 D modules/edi-compliance/src/x12/generators/gen_835.py
 M modules/edi-compliance/src/x12/generators/schemas.py
 M modules/edi-compliance/tests/golden_master/generate_masters.py
 M modules/edi-compliance/tests/golden_master/test_golden_master.py
 M modules/edi-compliance/tests/integration/test_api_branches.py
 M modules/edi-compliance/tests/integration/test_app_integration.py
 M modules/edi-compliance/tests/integration/test_auth_required.py
 D modules/edi-compliance/tests/unit/test_835_generator.py
 M modules/edi-compliance/tests/unit/test_835_parser.py
 M modules/edi-compliance/tests/unit/test_auto_posting.py
 M modules/edi-compliance/tests/unit/test_auto_posting_branches.py
 M modules/edi-compliance/tests/unit/test_auto_posting_extra.py
 M modules/edi-compliance/tests/unit/test_coverage_final.py
 M modules/edi-compliance/tests/unit/test_envelope.py
 D modules/edi-compliance/tests/unit/test_gen_835_branches.py
 M modules/edi-compliance/tests/unit/test_generate_api_branches.py
 D modules/edi-compliance/tests/unit/test_schemas.py
 M modules/edi-compliance/tests/unit/test_validator.py
 M modules/edi-compliance/tests/unit/test_validator_branches.py
 M modules/edi-compliance/tests/unit/test_validator_extra.py
 M modules/medical-claims/src/main.py
 M modules/medical-claims/tests/integration/test_api_claims.py
 M modules/member-management/src/api/routes/enrollment.py
 M modules/payment-processing/alembic/env.py
 M modules/payment-processing/src/_shim/db.py
 M modules/payment-processing/src/services/business_day.py
 M modules/payment-processing/src/services/nacha_generator.py
 M modules/payment-processing/tests/golden/nacha_sample.golden
 M modules/payment-processing/tests/unit/test_nacha_generator.py
 M modules/pharmacy-directory/alembic/env.py
 D modules/pharmacy-directory/src/models/compliance_tables.py
 M modules/pharmacy-directory/src/models/ncpdp_tables.py
 M modules/plan-design/src/db/session.py
 M modules/prescriber-directory/alembic/env.py
 M modules/prescriber-directory/src/db/session.py
 M modules/prescriber-directory/src/models/compliance_tables.py
 M modules/prescriber-directory/src/models/tables.py
 M modules/prior-authorization/src/api/schemas.py
 M modules/program-config/src/models/tables.py
 M modules/rebate-management/src/db/session.py
 M modules/reclaimrx/README.md
 M modules/reclaimrx/conftest.py
 M modules/reclaimrx/src/_shim/db.py
 M modules/reclaimrx/src/api/router.py
 M modules/reclaimrx/src/api/schemas/schemas.py
 M modules/reclaimrx/src/events/consumers.py
 M modules/reclaimrx/src/jobs/scheduled.py
 M modules/reclaimrx/src/services/ml_scoring.py
 M modules/reclaimrx/src/services/rule_engine.py
 M modules/reclaimrx/tests/integration/test_api_endpoints.py
 M modules/reclaimrx/tests/integration/test_api_endpoints_extended.py
 M modules/reclaimrx/tests/integration/test_fwa_pipeline.py
 M modules/reclaimrx/tests/unit/test_consumers_and_jobs.py
 M modules/reclaimrx/tests/unit/test_rule_engine.py
 M modules/reporting/src/services/phi_controls.py
 M modules/reporting/tests/unit/test_phi_controls.py
 M modules/rules-engine/src/models/tables.py
 M modules/rules-engine/src/services/pipeline.py
 M modules/rules-engine/src/services/rule_types.py
 M modules/rules-engine/tests/unit/test_pipeline.py
 M modules/rules-engine/tests/unit/test_rule_types.py
 M portal/operator/__mocks__/lucide-react.ts
 M portal/operator/app/admin/config/page.tsx
 M portal/operator/components/layout/nav-config.ts
 M portal/operator/next-env.d.ts
 M portal/operator/scripts/quality-gate.sh
 M portal/shared/lib/constants.ts
 M pyproject.toml
 M scripts/load_ncpdp.py
 M scripts/load_new_sources.py
 M scripts/load_oig_leie.py
 M scripts/load_sam.py
 M shared/data_ingestion/common.py
 M shared/data_ingestion/downloader.py
 M shared/data_ingestion/sources/cms_asp.py
 M shared/data_ingestion/sources/cms_nadac.py
 M shared/data_ingestion/sources/fda_drug_shortages.py
 M shared/data_ingestion/sources/fda_ndc.py
 M shared/data_ingestion/sources/fda_orange_book.py
 M shared/data_ingestion/sources/fda_purple_book.py
 M shared/data_ingestion/sources/fda_rems.py
 M shared/data_ingestion/sources/oig_leie.py
 M shared/data_ingestion/sources/rxnorm.py
 M shared/data_ingestion/sources/sam_exclusions.py
 M shared/data_ingestion/tests/test_cms_asp.py
 M shared/data_ingestion/tests/test_cms_nadac.py
 M shared/data_ingestion/tests/test_cms_opt_out.py
 M shared/data_ingestion/tests/test_dea.py
 M shared/data_ingestion/tests/test_downloader.py
 M shared/data_ingestion/tests/test_fda_ndc_parser.py
 M shared/data_ingestion/tests/test_fda_rems.py
 M shared/data_ingestion/tests/test_orange_book.py
 M shared/data_ingestion/tests/test_rxnorm.py
 M shared/db/models/core.py
 M shared/db/models/oig_leie_exclusions.py
 M shared/db/models/sam_exclusions.py
 M shared/db/session.py
 M shared/db/tenant_context.py
 M shared/events/factory.py
 M shared/tests/db/conftest.py
 M shared/tests/db/test_bank_holidays_model.py
 M shared/tests/db/test_engine_and_session.py
 M shared/tests/events/conftest.py
 M shared/tests/events/test_cross_module_events.py
 M shared/tests/events/test_rabbitmq_integration.py
 M shared/tests/test_preflight.py
 D test-results/.last-run.json
 M uv.lock
?? " [conflicted].gitignore"
?? .claude/agents/discipline-suggester.md
?? .claude/rules/destructive-actions.md
?? .claude/rules/session-framework.md
?? .claude/rules/vendor-references.md
?? .context/
?? .graphify_python
?? .graphifyignore
?? .planning-ingest-manifest.yaml
?? .planning/
?? .scratch/
?? "AGENTS [conflicted].md"
?? AGENTS.md
?? README.md
?? data/reference/fdb/
?? docs/INDEX.md
?? docs/architecture/ai-nlp-migrations-plan.md
?? docs/architecture/cycle-close-flow.md
?? docs/architecture/environments.md
?? docs/architecture/exclusions-subsystem-audit.md
?? docs/architecture/flag-architecture.md
?? docs/architecture/maxacc-registry.md
?? docs/architecture/medical-edi-scaffolding.md
?? docs/architecture/modules.md
?? docs/architecture/money-discipline.md
?? docs/architecture/ncpdp-d0.md
?? docs/architecture/network-management.md
?? docs/architecture/payment-flow.md
?? docs/architecture/phase-a2-testing.md
?? docs/architecture/phase-c-reference-data-rules-plan-v2.md
?? docs/architecture/phase-c-reference-data-rules-plan.md
?? docs/architecture/reclaimrx-overview.md
?? docs/architecture/rls-pattern.md
?? docs/architecture/scheduler-wiring-plan.md
?? docs/architecture/system-overview.md
?? docs/audit/CLAUDE_archive_pre_wave_42.md
?? docs/audit/journal.txt
?? docs/audit/portal-ux-audit-2026-04-14.md
?? docs/audit/retired-modules.md
?? docs/audit/wave-0-tasks/
?? docs/audit/wave-26-ncpdp-core-am20-misreading.md
?? docs/audit/wave-26-ncpdp-core-layer1-repeating-groups.md
?? docs/audit/wave-26-phase-b-followups.md
?? docs/audit/wave-26-phase-c6-followups.md
?? docs/audit/wave-27-rule-registry-audit.md
?? docs/audit/wave-28-sub-wave-1-sam-already-shipped.md
?? docs/audit/wave-30-dataq-spec-vs-reversed.md
?? docs/audit/wave-31-observability-audit.md
?? docs/audit/wave-31-security-audit.md
?? docs/audit/wave-32-field-conformance.md
?? docs/audit/wave-32-final-summary.md
?? docs/audit/wave-32-ncpdp-spec-inventory.md
?? docs/audit/wave-32-reject-code-conformance.md
?? docs/audit/wave-32-repeating-group-conformance.md
?? docs/audit/wave-32-response-segment-conformance.md
?? docs/audit/wave-32-segment-conformance.md
?? docs/audit/wave-32-transaction-code-conformance.md
?? docs/audit/wave-33-relayhealth-conformance.md
?? docs/audit/wave-34-brd-extracts/
?? docs/audit/wave-34-brd-inventory.md
?? docs/audit/wave-34-brd-rule-catalog-v2.md
?? docs/audit/wave-34-final-summary.md
?? docs/audit/wave-34-platform-gap-analysis.md
?? docs/audit/wave-35-ifx-billing-audit.md
?? docs/audit/wave-41-5-final-summary.md
?? docs/audit/wave-41-5-module-inventory.md
?? docs/audit/wave-41-5-test-quality-review.md
?? docs/audit/wave-41-5b-aegis-audit.md
?? docs/audit/wave-41-5b-claudemem-initial.md
?? docs/audit/wave-41-5b-doc-scores.md
?? docs/audit/wave-41-5b-final-summary.md
?? docs/audit/wave-41-5b-graphify-initial.md
?? docs/audit/wave-41-5b-hookify-tuning.md
?? docs/audit/wave-41-5b-refactor-roadmap.md
?? docs/audit/wave-41-6-835-inventory.md
?? docs/audit/wave-41-6-architecture-investigation.md
?? docs/audit/wave-41-6-final-summary.md
?? docs/audit/wave-41-6-followups.md
?? docs/audit/wave-41-6-m2-paysync-835-fixes.md
?? docs/audit/wave-41-6-m2-redo.md
?? docs/audit/wave-41-6-m2-step2-resolution.md
?? docs/audit/wave-41-6-member-resolution-inventory.md
?? docs/audit/wave-41-6-nacha-inventory.md
?? docs/audit/wave-41-6-x12-835-pre-retirement.md
?? docs/audit/wave-41-7-ai-nlp-session-audit.md
?? docs/audit/wave-41-7-discipline-findings.md
?? docs/audit/wave-41-7-dlq-audit.md
?? docs/audit/wave-41-7-f1a-portal-admin-money.md
?? docs/audit/wave-41-7-f1b-portal-clients-money.md
?? docs/audit/wave-41-7-f1c-portal-components-money.md
?? docs/audit/wave-41-7-feature-flag-inventory.md
?? docs/audit/wave-41-7-final-summary.md
?? docs/audit/wave-41-7-followups.md
?? docs/audit/wave-41-7-j3c-phi-fields-completeness.md
?? docs/audit/wave-41-7-listener-perf.md
?? docs/audit/wave-41-7-m0a-codex-removal.md
?? docs/audit/wave-41-7-n-plus-1-audit.md
?? docs/audit/wave-41-7-phi-cache-inventory.md
?? docs/audit/wave-41-7-rubric-calibration.md
?? docs/audit/wave-41-7-stops/
?? docs/audit/wave-41-7-threshold-sweep.md
?? docs/audit/wave-41-7-utcnow-inventory.md
?? docs/audit/wave-41-7-werkbench-discipline-summary.md
?? docs/audit/wave-41-7-werkbench-final-summary.md
?? docs/audit/wave-41-7-werkbench-trial-summary.md
?? docs/audit/wave-41-8-backlog.md
?? docs/audit/wave-41-8-final-summary.md
?? docs/audit/wave-41-echo-spec-inventory.md
?? docs/audit/wave-b1-final-summary.md
?? "docs/audit/wave-history [conflicted].md"
?? docs/audit/wave-history.md
?? docs/audit/wave-transcript-catalog.md
?? docs/audits/
?? docs/decisions/
?? docs/discipline/
?? docs/known-issues.md
?? docs/prd/prd-ncpdp-core.md
?? docs/runbooks/
?? docs/sign-off/
?? docs/style/
?? docs/superpowers/
?? docs/test_payloads/
?? docs/testing.md
?? infrastructure/evidence/
?? infrastructure/scripts/lib/cleanup_tier1_ifx_prod_app_policies.sql
?? infrastructure/scripts/lib/cleanup_tier2_ifx_prod_app_grants.sql
?? infrastructure/scripts/lib/expected_reference_tables.txt
?? infrastructure/scripts/lib/psql_strict.sh
?? "infrastructure/scripts/run_reference_loaders (conflicted).sh"
?? "infrastructure/scripts/switch_env [conflicted].sh"
?? journal.txt
?? modules/adjudication-engine/README.md
?? modules/adjudication-engine/alembic.ini
?? modules/adjudication-engine/alembic/env.py
?? modules/adjudication-engine/alembic/script.py.mako
?? modules/adjudication-engine/alembic/versions/0001_adj_engine_baseline.py
?? modules/adjudication-engine/alembic/versions/0002_check_constraints.py
?? modules/adjudication-engine/alembic/versions/0004_claim_txn_flags.py
?? modules/adjudication-engine/alembic/versions/0005_claim_txn_amounts.py
?? modules/adjudication-engine/alembic/versions/0006_claim_txn_program_id.py
?? modules/adjudication-engine/alembic/versions/0009_claim_txn_program_id_not_null.py
?? modules/adjudication-engine/scheduler_test.db
?? modules/adjudication-engine/src/api/admin_routes.py
?? modules/adjudication-engine/src/api/config_routes.py
?? modules/adjudication-engine/src/api/health_scheduler.py
?? modules/adjudication-engine/src/api/network_mgmt_routes.py
?? modules/adjudication-engine/src/api/paysync_batch_routes.py
?? modules/adjudication-engine/src/api/paysync_close_routes.py
?? modules/adjudication-engine/src/api/paysync_invoicing_routes.py
?? modules/adjudication-engine/src/api/reclaimrx_routes.py
?? modules/adjudication-engine/src/members/
?? modules/adjudication-engine/src/scheduler.py
?? modules/adjudication-engine/src/services/accumulator_writer.py
?? modules/adjudication-engine/src/services/bin_routing.py
?? "modules/adjudication-engine/src/services/ncpdp_adapter (conflicted).py"
?? modules/adjudication-engine/src/services/ncpdp_adapter.py
?? modules/adjudication-engine/src/services/ncpdp_validation.py
?? modules/adjudication-engine/src/services/parsed_claim.py
?? modules/adjudication-engine/src/services/persistence.py
?? modules/adjudication-engine/src/services/pricing_enrichment.py
?? modules/adjudication-engine/src/services/rate_limiter.py
?? "modules/adjudication-engine/src/services/tcp_listener (conflicted).py"
?? modules/adjudication-engine/src/services/tcp_listener.py
?? modules/adjudication-engine/tests/integration/
?? modules/adjudication-engine/tests/load/
?? modules/adjudication-engine/tests/unit/test_bin_routing.py
?? modules/adjudication-engine/tests/unit/test_build_context_population.py
?? modules/adjudication-engine/tests/unit/test_hook_adapter_pass_message.py
?? modules/adjudication-engine/tests/unit/test_listener_metrics_tls.py
?? "modules/adjudication-engine/tests/unit/test_ncpdp_adapter (conflicted).py"
?? modules/adjudication-engine/tests/unit/test_ncpdp_adapter.py
?? modules/adjudication-engine/tests/unit/test_ncpdp_validation_bridge.py
?? modules/adjudication-engine/tests/unit/test_pricing_enrichment.py
?? modules/adjudication-engine/tests/unit/test_publisher_cob_fields.py
?? modules/adjudication-engine/tests/unit/test_publishers.py
?? modules/adjudication-engine/tests/unit/test_rate_limiter.py
?? modules/adjudication-engine/uv.lock
?? modules/ai-nlp/alembic.ini
?? modules/ai-nlp/alembic/env.py
?? modules/ai-nlp/alembic/script.py.mako
?? modules/ai-nlp/alembic/versions/0001_ai_nlp_baseline.py
?? modules/ai-nlp/alembic/versions/0002_partition_hot_tables.py
?? modules/ai-nlp/alembic/versions/0003_check_constraints.py
?? modules/ai-nlp/tests/integration/test_rls_tenant_isolation.py
?? modules/ai-nlp/tests/integration/test_schema_smoke.py
?? modules/ai-nlp/tests/integration/test_smoke_real_db.py
?? modules/billing/tests/integration/test_rls_tenant_isolation.py
?? modules/core-platform/alembic/versions/0015_widen_sam_exclusions_zip.py
?? modules/core-platform/alembic/versions/0016_drop_core_exclusion_tables.py
?? modules/core-platform/alembic/versions/0018_tenant_type_enum.py
?? modules/core-platform/alembic/versions/0019_tenant_type_backfill_not_null.py
?? modules/core-platform/tests/test_main_dlq_monitor.py
?? "modules/drug-database/README [conflicted].md"
?? modules/drug-database/alembic/versions/0008_fdb_pricing.py
?? modules/drug-database/drug_database/__init__.py
?? modules/drug-database/drug_database/api/
?? modules/drug-database/drug_database/db/
?? modules/drug-database/drug_database/events/
?? modules/drug-database/drug_database/infrastructure/
?? modules/drug-database/drug_database/jobs/
?? modules/drug-database/drug_database/main.py
?? modules/drug-database/drug_database/models/
?? modules/drug-database/drug_database/services/__init__.py
?? modules/drug-database/drug_database/services/composite_pricing.py
?? modules/drug-database/drug_database/services/drug_lookup.py
?? modules/drug-database/drug_database/services/fda_ndc_parser.py
?? modules/drug-database/drug_database/services/fda_supplementary_ingestion.py
?? modules/drug-database/drug_database/services/fdb_pricing.py
?? modules/drug-database/drug_database/services/fdb_pricing_ingester.py
?? modules/drug-database/drug_database/services/interactions.py
?? modules/drug-database/drug_database/services/mac_list.py
?? modules/drug-database/drug_database/services/nadac_parser.py
?? modules/drug-database/drug_database/services/pricing.py
?? modules/drug-database/drug_database/services/pricing_ingestion.py
?? modules/drug-database/drug_database/utils/
?? modules/drug-database/tests/integration/test_fdb_pricing_through_create_app.py
?? modules/drug-database/tests/unit/test_alembic_0008_fdb_pricing.py
?? modules/drug-database/tests/unit/test_bench_fdb_lookup_script.py
?? modules/drug-database/tests/unit/test_composite_pricing.py
?? modules/drug-database/tests/unit/test_fdb_pricing_ingester.py
?? modules/drug-database/tests/unit/test_fdb_pricing_models.py
?? modules/drug-database/tests/unit/test_fdb_pricing_service.py
?? modules/drug-database/tests/unit/test_nadac_pricing_lookup.py
?? modules/drug-database/tests/unit/test_pricing_snapshot_amendment.py
?? modules/ebv-ebi-rtbc/tests/test_main_middleware.py
?? modules/maxacc-registry/.gitignore
?? modules/maxacc-registry/README.md
?? modules/maxacc-registry/alembic.ini
?? modules/maxacc-registry/alembic/env.py
?? modules/maxacc-registry/alembic/script.py.mako
?? modules/maxacc-registry/alembic/versions/0002_vendor_pbm_seed.py
?? modules/maxacc-registry/conftest.py
?? modules/maxacc-registry/data_imports/
?? modules/maxacc-registry/pyproject.toml
?? modules/maxacc-registry/src/
?? modules/maxacc-registry/tests/
?? modules/member-management/tests/integration/test_upload_phi_scrub.py
?? modules/ncpdp-core/
?? modules/network-management/README.md
?? modules/network-management/alembic.ini
?? modules/network-management/alembic/env.py
?? modules/network-management/alembic/script.py.mako
?? modules/network-management/alembic/versions/0004_tenant_ach_payer_address.py
?? modules/network-management/pyproject.toml
?? modules/network-management/src/
?? modules/network-management/tests/
?? modules/paysync/README.md
?? modules/paysync/alembic.ini
?? modules/paysync/alembic/env.py
?? modules/paysync/alembic/script.py.mako
?? modules/paysync/pyproject.toml
?? modules/paysync/scripts/
?? modules/paysync/src/
?? modules/paysync/tests/
?? modules/pharmacy-directory/alembic/versions/0004_widen_exclusion_type.py
?? modules/pharmacy-directory/alembic/versions/0005_drop_pharmacy_excl_xref.py
?? modules/pharmacy-directory/alembic/versions/0006_uei_cage_columns.py
?? modules/pharmacy-directory/alembic/versions/0008_dataq_master_exclusion_cols.py
?? modules/pharmacy-directory/tests/unit/test_exclusion_columns.py
?? modules/prescriber-directory/alembic/versions/0006_widen_exclusion_type.py
?? modules/prescriber-directory/alembic/versions/0007_drop_prescriber_excl_xref.py
?? modules/prescriber-directory/tests/unit/test_exclusion_columns.py
?? modules/prior-authorization/tests/test_main_middleware.py
?? modules/program-config/alembic.ini
?? modules/program-config/alembic/env.py
?? modules/program-config/alembic/script.py.mako
?? modules/program-config/alembic/versions/0001_program_config_baseline.py
?? modules/program-config/alembic/versions/0002_check_constraints.py
?? modules/program-config/alembic/versions/0007_lifetime_accumulator_scope.py
?? modules/program-config/tests/integration/test_smoke_real_db.py
?? modules/reclaimrx/alembic.ini
?? modules/reclaimrx/alembic/env.py
?? modules/reclaimrx/alembic/script.py.mako
?? modules/reclaimrx/alembic/versions/0005_eval_log_runwide_skips.py
?? modules/reclaimrx/alembic/versions/0008_seed_ml_detector_placeholders.py
?? modules/reclaimrx/pyproject.toml
?? modules/reclaimrx/src/reclaimrx/
?? modules/reclaimrx/tests/integration/test_cob_event_payload_roundtrip.py
?? modules/reclaimrx/tests/unit/test_claim_context_cob_properties.py
?? modules/reclaimrx/tests/unit/test_m04_pricing_refactor.py
?? modules/reclaimrx/tests/wave42/
?? modules/reclaimrx/tests/wave43/
?? modules/reclaimrx/tests/wave44b/
?? modules/reclaimrx/uv.lock
?? modules/reporting/alembic.ini
?? modules/reporting/alembic/
?? modules/reporting/tests/integration/test_smoke_real_db.py
?? modules/rules-engine/alembic.ini
?? modules/rules-engine/alembic/env.py
?? modules/rules-engine/alembic/script.py.mako
?? modules/rules-engine/alembic/versions/0001_rules_engine_baseline.py
?? modules/rules-engine/alembic/versions/0002_check_constraints.py
?? modules/rules-engine/alembic/versions/0004_program_id_fk.py
?? modules/rules-engine/src/services/rule_cache.py
?? modules/rules-engine/src/services/rule_loader.py
?? modules/rules-engine/tests/integration/
?? modules/rules-engine/tests/unit/test_basic_ncpdp_rules.py
?? modules/rules-engine/tests/unit/test_bin_exclusion_rule.py
?? modules/rules-engine/tests/unit/test_pa_timer_rule.py
?? modules/rules-engine/tests/unit/test_pharmacy_exclusion_rule.py
?? modules/rules-engine/tests/unit/test_phase_c7_pre_a_claim_context.py
?? modules/rules-engine/tests/unit/test_prescriber_exclusion_rule.py
?? modules/rules-engine/tests/unit/test_rule_cache.py
?? modules/rules-engine/tests/unit/test_set_amount_pipeline.py
?? modules/rules-engine/tests/unit/test_tier1_completion_rules.py
?? modules/rules-engine/tests/unit/test_tier1_pricing_rules.py
?? modules/rules-engine/tests/unit/test_tier2_routing_rules.py
?? modules/rules-engine/tests/unit/test_tier4_tier6_rules.py
?? modules/rules-engine/tests/unit/test_upstream_claims_multi.py
?? modules/switch-connectivity/
?? portal/operator/app/admin/config/change-sets/
?? portal/operator/app/admin/network/
?? portal/operator/app/admin/paysync/
?? portal/operator/components/paysync/
?? portal/operator/tests/e2e/paysync-flows.spec.ts
?? portal/operator/tests/e2e/paysync-smoke.spec.ts
?? portal/operator/tests/unit/components/paysync/
?? portal/shared/lib/config-api.ts
?? portal/shared/lib/paysync-api.ts
?? scripts/audit_column_widths.py
?? scripts/bench_fdb_lookup.py
?? scripts/cleanup_test_tenant.py
?? scripts/graphify/
?? scripts/lint/
?? "scripts/load_cms_asp [conflicted].py"
?? "scripts/load_cms_nadac [conflicted].py"
?? "scripts/load_fda_ndc [conflicted].py"
?? "scripts/load_fda_rems [conflicted].py"
?? scripts/load_fdb.py
?? "scripts/load_hcpcs [conflicted].py"
?? "scripts/load_icd10 [conflicted].py"
?? "scripts/load_medicaid_bins [conflicted].py"
?? "scripts/load_nppes [conflicted].py"
?? "scripts/load_ofac [conflicted].py"
?? "scripts/load_oig_leie [conflicted].py"
?? "scripts/load_opt_out [conflicted].py"
?? "scripts/load_orange_book [conflicted].py"
?? "scripts/load_rxnorm [conflicted].py"
?? scripts/refresh_pharmacy_exclusions.py
?? scripts/refresh_prescriber_exclusions.py
?? scripts/regenerate_reject_codes.py
?? scripts/rerun_oig_cross_ref.py
?? scripts/seed_ifx_dev_tenant.py
?? scripts/smoke_test_b8.py
?? scripts/teardown_ifx_dev_tenant.py
?? shared/data_ingestion/data/
?? shared/data_ingestion/dataq_ncpdp/
?? shared/data_ingestion/ncpdp_roster.py
?? shared/data_ingestion/pharmacy_tin_uei.py
?? "shared/data_ingestion/tests/test_cms_opt_out [conflicted].py"
?? "shared/data_ingestion/tests/test_dea [conflicted].py"
?? "shared/data_ingestion/tests/test_fda_purple_book [conflicted].py"
?? "shared/data_ingestion/tests/test_fda_shortages [conflicted].py"
?? shared/data_ingestion/tests/test_load_sam_script.py
?? "shared/data_ingestion/tests/test_ofac_sdn [conflicted].py"
?? shared/db/rule_instance_seeding.py
?? shared/db/test_factories.py
?? shared/edi/
?? shared/events/dlq_repository.py
?? shared/events/jobs/dlq_depth_monitor.py
?? shared/events/jobs/tests/
?? shared/fdb/
?? shared/program_config_queries/
?? shared/test_harness/
?? shared/tests/data_ingestion/
?? shared/tests/db/test_phase_a_tenant.py
?? shared/tests/db/test_rls_session_sync.py
?? shared/tests/db/test_rule_instance_seeding.py
?? shared/tests/db/test_seed_as_admin.py
?? shared/tests/edi/
?? shared/tests/events/test_dlq_depth_monitor.py
?? shared/tests/events/test_dlq_repository.py
?? shared/tests/fdb/
?? shared/tests/program_config_queries/
?? shared/tests/test_harness/
?? shared/tests/utils/test_decimal_jsonb.py
?? shared/tests/utils/test_message_template.py
?? shared/tests/utils/test_metrics.py
?? shared/tests/utils/test_ncpdp_field_lookup.py
?? shared/tests/utils/test_phone_validation.py
?? shared/tests/utils/test_secret_box.py
?? shared/utils/decimal_jsonb.py
?? shared/utils/message_template.py
?? shared/utils/metrics.py
?? shared/utils/ncpdp_field_lookup.py
?? shared/utils/phone_validation.py
?? shared/utils/secret_box.py
?? tasks/ncpdp-core-todo.md
?? tasks/switch-connectivity-todo.md
?? tests/__init__.py
?? tests/hooks/
?? tests/integration/__init__.py
?? tests/integration/test_billing_smoke.py
?? tests/integration/test_core_platform_smoke.py
?? tests/integration/test_every_sql_parses.py
?? tests/integration/test_factories.py
?? tests/integration/test_fixture_works.py
?? tests/integration/test_payment_processing_smoke.py
?? tests/integration/test_validation_run_cli.py
?? tests/lint/
?? tests/repo/
?? tests/scripts/
?? tests/test_column_width_drift.py
?? tests/test_rls_applier.py
?? tests/test_sam_cross_ref.py
?? waves/
9b61d6d (HEAD -> develop) B9.A C12+C13: Phase 09 compat baseline + module base profile lock-in
60c6cc0 B9.A C11: setup_fdw.sh manifest-derived count + deterministic sort
c03e37a B9.A C10: FDW name-collision preflight script + test seam
2b1f2b9 B9.A C9: reference-DB write-path guard (env-var strict + SQL assertion)
d6cefd8 B9.A C8: SQLite-backed DELTA_SEMANTICS simulator + A4 regression detector
33a2fb3 B9.A C4: FDB MTL config flag + loader registry + DB-level guard template
3ead3bd B9.A C3: ingester contract test template + N4/A4/T12 mitigations
e54425f B9.A C2: generated migration template for FDB tier batches
9b19457 B9.A C1: TableSpec registry expansion — Tier + DeltaSemantics + 4 fields
503cd7b B7.3: restore Phase 11A ground truth (ifx_prod_app regression repair)
c740ca9 fix(tests): cms_opt_out mock URLs + pagination + src-namespace preload
a36a471 fix(tests): preload prescriber-directory src.models so test_dea stops skipping
warning: could not open directory '.claude/skills$skill/': No such file or directory

 succeeded in 975ms:
shared\config.py:132:    #   * loader registry filters out specs with loader_group="fdb_mtl"
shared\config.py:146:    FDB_LOAD_MTL: bool = False
infrastructure\scripts\lib\fdb_mtl_revoke.sql.tmpl:9:-- Layered with the app-side `filter_loadable_specs` in
infrastructure\scripts\lib\fdb_mtl_revoke.sql.tmpl:80:      AND grantee IN ({{APP_ROLES_QUOTED}});
infrastructure\scripts\preflight_b9_name_collision.py:37:Test seam: `scan_for_collisions` takes a `table_lister` callable so
infrastructure\scripts\preflight_b9_name_collision.py:108:_OWNED_SCHEMAS = frozenset({"drug_database"})
infrastructure\scripts\preflight_b9_name_collision.py:112:_HARD_COLLISION_SCHEMAS = frozenset({
infrastructure\scripts\preflight_b9_name_collision.py:123:def scan_for_collisions(
infrastructure\scripts\preflight_b9_name_collision.py:142:        if schema in _HARD_COLLISION_SCHEMAS:
infrastructure\scripts\preflight_b9_name_collision.py:144:        elif schema in _OWNED_SCHEMAS:
infrastructure\scripts\preflight_b9_name_collision.py:275:        from shared.db.write_path_guard import resolve_reference_db_url
infrastructure\scripts\preflight_b9_name_collision.py:276:        db_url = resolve_reference_db_url()
infrastructure\scripts\preflight_b9_name_collision.py:284:    hard, soft = scan_for_collisions(expected, table_lister=_lister)
shared\db\write_path_guard.py:22:    resolve_reference_db_url() -> str
shared\db\write_path_guard.py:46:def resolve_reference_db_url() -> str:
shared\db\write_path_guard.py:115:    "resolve_reference_db_url",
shared\tests\db\test_preflight_b9_name_collision.py:25:    scan_for_collisions,
shared\tests\db\test_preflight_b9_name_collision.py:85:# scan_for_collisions
shared\tests\db\test_preflight_b9_name_collision.py:92:    hard, soft = scan_for_collisions(expected, table_lister=lister)
shared\tests\db\test_preflight_b9_name_collision.py:102:    hard, soft = scan_for_collisions(expected, table_lister=lister)
shared\tests\db\test_preflight_b9_name_collision.py:114:    hard, soft = scan_for_collisions(expected, table_lister=lister)
shared\tests\db\test_preflight_b9_name_collision.py:126:    hard, soft = scan_for_collisions(expected, table_lister=lister)
shared\tests\db\test_preflight_b9_name_collision.py:135:    hard, soft = scan_for_collisions(expected, table_lister=lister)
shared\tests\db\test_preflight_b9_name_collision.py:147:    hard, soft = scan_for_collisions(expected, table_lister=lister)
shared\tests\db\test_preflight_b9_name_collision.py:159:    hard, _soft = scan_for_collisions(expected, table_lister=lister)
modules\drug-database\tests\_fdb_delta_semantics.py:3:C3 (`_fdb_contract.py::assert_delta_semantics_acd_cycle`) is the
modules\drug-database\tests\_fdb_delta_semantics.py:36:into `assert_delta_semantics_acd_cycle` and runs `teardown()` after.
modules\drug-database\tests\_fdb_contract.py:16:        assert_no_parse_warnings,
modules\drug-database\tests\_fdb_contract.py:18:        assert_delta_semantics_acd_cycle,
modules\drug-database\tests\_fdb_contract.py:24:        assert_no_parse_warnings(adapter, local_drop, rmiid1_med_spec)
modules\drug-database\tests\_fdb_contract.py:37:  * N4 (parse_table skip)        — assert_no_parse_warnings makes the
modules\drug-database\tests\_fdb_contract.py:41:  * A4 (delta correctness)       — assert_delta_semantics_acd_cycle
modules\drug-database\tests\_fdb_contract.py:86:    Used by ``assert_no_parse_warnings`` to assert that the silent-skip
modules\drug-database\tests\_fdb_contract.py:300:def assert_no_parse_warnings(
modules\drug-database\tests\_fdb_contract.py:416:def assert_delta_semantics_acd_cycle(
modules\drug-database\tests\_fdb_contract.py:542:    "assert_no_parse_warnings",
modules\drug-database\tests\_fdb_contract.py:544:    "assert_delta_semantics_acd_cycle",
modules\drug-database\tests\unit\test_module_base_profile.py:29:    actual = len(DrugBase.metadata.tables)
modules\drug-database\tests\unit\test_module_base_profile.py:31:        f"DrugBase.metadata.tables has {actual} entries; baseline is "
modules\drug-database\tests\unit\test_module_base_profile.py:69:    schemas = {tbl.schema for tbl in DrugBase.metadata.tables.values()}
modules\drug-database\tests\unit\test_infrastructure.py:33:    for table in DrugBase.metadata.tables.values():
modules\drug-database\tests\unit\test_gen_fdb_tier_migration.py:79:        loader_group="fdb_tier_a",
modules\drug-database\tests\unit\test_final_coverage_gaps.py:101:        for table in DrugBase.metadata.tables.values():
modules\drug-database\tests\unit\test_final_coverage_gaps.py:187:        for table in DrugBase.metadata.tables.values():
modules\drug-database\tests\unit\test_final_coverage_gaps.py:276:        for table in DrugBase.metadata.tables.values():
modules\drug-database\tests\unit\test_final_coverage_gaps.py:341:        for table in DrugBase.metadata.tables.values():
modules\drug-database\tests\unit\test_final_coverage_gaps.py:383:        for table in DrugBase.metadata.tables.values():
modules\drug-database\drug_database\services\fdb_loader_registry.py:3:The registry filters a list of `TableSpec`s by `loader_group` and
modules\drug-database\drug_database\services\fdb_loader_registry.py:4:applies the `FDB_LOAD_MTL` settings flag (charter v3.2 + ADVERSARIAL
modules\drug-database\drug_database\services\fdb_loader_registry.py:7:  loader_group="fdb_mtl"  +  FDB_LOAD_MTL=False (default) → EXCLUDED
modules\drug-database\drug_database\services\fdb_loader_registry.py:8:  loader_group="fdb_mtl"  +  FDB_LOAD_MTL=True            → INCLUDED
modules\drug-database\drug_database\services\fdb_loader_registry.py:9:  loader_group=<anything> +  any flag value               → INCLUDED
modules\drug-database\drug_database\services\fdb_loader_registry.py:14:`FDB_LOAD_MTL=True` and lands the corresponding GRANT migration
modules\drug-database\drug_database\services\fdb_loader_registry.py:25:Phase 09 backward-compat: loader_group is None for the 3 pre-B9
modules\drug-database\drug_database\services\fdb_loader_registry.py:38:def filter_loadable_specs(
modules\drug-database\drug_database\services\fdb_loader_registry.py:48:        fdb_load_mtl: settings.FDB_LOAD_MTL — False excludes MTL.
modules\drug-database\drug_database\services\fdb_loader_registry.py:50:            loader_group is in this list. None means "all groups
modules\drug-database\drug_database\services\fdb_loader_registry.py:55:        loader_group=None) are always included unless `only_groups`
modules\drug-database\drug_database\services\fdb_loader_registry.py:63:        # wants MTL, they must set FDB_LOAD_MTL=True. Anything else
modules\drug-database\drug_database\services\fdb_loader_registry.py:65:        if spec.loader_group == MTL_LOADER_GROUP and not fdb_load_mtl:
modules\drug-database\drug_database\services\fdb_loader_registry.py:68:            if spec.loader_group not in only_groups:
modules\drug-database\drug_database\services\fdb_loader_registry.py:81:    return [s for s in specs if s.loader_group == MTL_LOADER_GROUP]
modules\drug-database\drug_database\services\fdb_loader_registry.py:84:__all__ = ["filter_loadable_specs", "mtl_specs", "MTL_LOADER_GROUP"]
modules\drug-database\drug_database\services\fdb_adapter.py:225:      loader_group:       tier-loader registration label
modules\drug-database\drug_database\services\fdb_adapter.py:243:    loader_group: str | None = None
modules\drug-database\tests\unit\test_fdb_loader_registry.py:5:  1. The settings flag `FDB_LOAD_MTL` defaults to False. Flipping it
modules\drug-database\tests\unit\test_fdb_loader_registry.py:8:  2. The `filter_loadable_specs` helper excludes `loader_group="fdb_mtl"`
modules\drug-database\tests\unit\test_fdb_loader_registry.py:15:     `loader_group="fdb_mtl"`, or flips the default flag to True.
modules\drug-database\tests\unit\test_fdb_loader_registry.py:33:    filter_loadable_specs,
modules\drug-database\tests\unit\test_fdb_loader_registry.py:48:    # loader_group=None — Phase 09 backward-compat
modules\drug-database\tests\unit\test_fdb_loader_registry.py:56:    loader_group="fdb_tier_a",
modules\drug-database\tests\unit\test_fdb_loader_registry.py:64:    loader_group="fdb_tier_b",
modules\drug-database\tests\unit\test_fdb_loader_registry.py:72:    loader_group="fdb_tier_c",
modules\drug-database\tests\unit\test_fdb_loader_registry.py:80:    loader_group=MTL_LOADER_GROUP,
modules\drug-database\tests\unit\test_fdb_loader_registry.py:100:    monkeypatch.delenv("FDB_LOAD_MTL", raising=False)
modules\drug-database\tests\unit\test_fdb_loader_registry.py:104:    assert settings.FDB_LOAD_MTL is False
modules\drug-database\tests\unit\test_fdb_loader_registry.py:111:    monkeypatch.setenv("FDB_LOAD_MTL", "true")
modules\drug-database\tests\unit\test_fdb_loader_registry.py:116:        assert settings.FDB_LOAD_MTL is True
modules\drug-database\tests\unit\test_fdb_loader_registry.py:118:        monkeypatch.delenv("FDB_LOAD_MTL", raising=False)
modules\drug-database\tests\unit\test_fdb_loader_registry.py:123:# filter_loadable_specs
modules\drug-database\tests\unit\test_fdb_loader_registry.py:129:    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=False)
modules\drug-database\tests\unit\test_fdb_loader_registry.py:137:    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=True)
modules\drug-database\tests\unit\test_fdb_loader_registry.py:143:    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=True)
modules\drug-database\tests\unit\test_fdb_loader_registry.py:155:    out = filter_loadable_specs(
modules\drug-database\tests\unit\test_fdb_loader_registry.py:169:    out = filter_loadable_specs(
modules\drug-database\tests\unit\test_fdb_loader_registry.py:176:    out = filter_loadable_specs(
modules\drug-database\tests\unit\test_fdb_loader_registry.py:184:    """loader_group=None specs always load (Phase 09 backward-compat)."""
modules\drug-database\tests\unit\test_fdb_loader_registry.py:186:        out = filter_loadable_specs([_PHASE_09_SPEC], fdb_load_mtl=flag)
modules\drug-database\tests\unit\test_fdb_loader_registry.py:191:    assert filter_loadable_specs([], fdb_load_mtl=False) == []
modules\drug-database\tests\unit\test_fdb_loader_registry.py:216:    """Charter SC: under default `FDB_LOAD_MTL=False`, no MTL spec loads.
modules\drug-database\tests\unit\test_fdb_loader_registry.py:220:    B9.G: now load-bearing (19 MTL specs registered with loader_group=
modules\drug-database\tests\unit\test_fdb_loader_registry.py:229:    `loader_group="fdb_mtl"` label (which would silently bypass the
modules\drug-database\tests\unit\test_fdb_loader_registry.py:234:    # Tier.D must have loader_group=MTL_LOADER_GROUP, AND under default
modules\drug-database\tests\unit\test_fdb_loader_registry.py:238:        assert spec.loader_group == MTL_LOADER_GROUP, (
modules\drug-database\tests\unit\test_fdb_loader_registry.py:240:            f"loader_group='fdb_mtl' or they bypass the MTL guard."
modules\drug-database\tests\unit\test_fdb_loader_registry.py:243:    default_load = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=False)
modules\drug-database\tests\unit\test_fdb_loader_registry.py:246:        "Either FDB_LOAD_MTL default flipped to True (forbidden without an "
modules\drug-database\tests\unit\test_fdb_loader_registry.py:247:        "activation wave) or loader_group label is missing on a Tier D spec."
modules\drug-database\tests\unit\test_fdb_delta_semantics.py:27:from _fdb_contract import assert_delta_semantics_acd_cycle  # noqa: E402
modules\drug-database\tests\unit\test_fdb_delta_semantics.py:61:        assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_delta_semantics.py:98:            assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_delta_semantics.py:132:        assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_delta_semantics.py:168:        assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_delta_semantics.py:199:    assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_delta_semantics.py:222:    assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_contract.py:32:    assert_delta_semantics_acd_cycle,
modules\drug-database\tests\unit\test_fdb_contract.py:34:    assert_no_parse_warnings,
modules\drug-database\tests\unit\test_fdb_contract.py:291:    assert_no_parse_warnings(adapter, synthetic_drop, SIMPLE_SPEC)
modules\drug-database\tests\unit\test_fdb_contract.py:317:        assert_no_parse_warnings(adapter, drop, SIMPLE_SPEC)
modules\drug-database\tests\unit\test_fdb_contract.py:341:    assert_no_parse_warnings(
modules\drug-database\tests\unit\test_fdb_contract.py:454:    assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_contract.py:473:        assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_contract.py:494:    assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_contract.py:517:    assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_contract.py:544:    assert_delta_semantics_acd_cycle(
modules\drug-database\tests\unit\test_fdb_adapter.py:585:    NOT declare tier / record_counts_key / loader_group /
modules\drug-database\tests\unit\test_fdb_adapter.py:592:        assert spec.loader_group is None, spec.table_name
modules\drug-database\tests\unit\test_fdb_adapter.py:597:    """New B9 TableSpecs can declare tier + delta + loader_group + record_counts_key."""
modules\drug-database\tests\unit\test_fdb_adapter.py:604:        loader_group="fdb_tier_a",
modules\drug-database\tests\unit\test_fdb_adapter.py:609:    assert spec.loader_group == "fdb_tier_a"
modules\drug-database\tests\integration\test_coverage_gaps_integration.py:37:    for table in DrugBase.metadata.tables.values():
modules\drug-database\tests\integration\test_app_middleware.py:30:    for table in DrugBase.metadata.tables.values():
modules\drug-database\tests\integration\test_api_router_coverage.py:38:    for table in DrugBase.metadata.tables.values():
modules\drug-database\tests\integration\test_api_endpoints.py:49:    for table in DrugBase.metadata.tables.values():
modules\drug-database\tests\conftest.py:38:    for table in DrugBase.metadata.tables.values():
shared\tests\db\test_write_path_guard.py:15:    resolve_reference_db_url,
shared\tests\db\test_write_path_guard.py:20:# resolve_reference_db_url — strict, no fallback
shared\tests\db\test_write_path_guard.py:29:    url = resolve_reference_db_url()
shared\tests\db\test_write_path_guard.py:41:    url = resolve_reference_db_url()
shared\tests\db\test_write_path_guard.py:52:        resolve_reference_db_url()
shared\tests\db\test_write_path_guard.py:65:        resolve_reference_db_url()
shared\tests\db\test_write_path_guard.py:73:        resolve_reference_db_url()
shared\tests\db\test_write_path_guard.py:84:        resolve_reference_db_url()

codex
The branch is at the expected B9.A head, but the worktree is very dirty with many unrelated modifications and untracked files. I’m going to review the committed B9.A state and the live files where they match the scoped paths, then call out any risk that depends on unstaged drift.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/drug_database/services/fdb_loader_registry.py' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/tests/_fdb_contract.py' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'infrastructure/scripts/preflight_b9_name_collision.py' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'shared/db/write_path_guard.py' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 433ms:
"""B9.A C4 â€” FDB loader registry with MTL guard.

The registry filters a list of `TableSpec`s by `loader_group` and
applies the `FDB_LOAD_MTL` settings flag (charter v3.2 + ADVERSARIAL
A8 mitigation):

  loader_group="fdb_mtl"  +  FDB_LOAD_MTL=False (default) â†’ EXCLUDED
  loader_group="fdb_mtl"  +  FDB_LOAD_MTL=True            â†’ INCLUDED
  loader_group=<anything> +  any flag value               â†’ INCLUDED

MTL = Medical Test Lexicon. InfinityRx ships the 19 Tier D schemas
(B9.G) but does NOT subscribe to the clinical-screening tier â€” the
tables are empty by design until a future activation wave flips
`FDB_LOAD_MTL=True` and lands the corresponding GRANT migration
(`infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` is the
defense-in-depth backstop for the app-layer filter).

Why a registry helper exists:
  * App-layer enforcement is the FAST PATH â€” never even ask the DB
    to insert MTL rows under the default flag.
  * DB-layer REVOKE is the SLOW PATH â€” even if app code regresses
    and tries to write MTL, the DB rejects with permission error.
  * Both layers must agree. Disagreement is a bug, not a feature.

Phase 09 backward-compat: loader_group is None for the 3 pre-B9
TableSpecs (RNP3, RPRDPTD0, RNPTYPD0). Filter never excludes those.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from drug_database.services.fdb_adapter import TableSpec


MTL_LOADER_GROUP = "fdb_mtl"


def filter_loadable_specs(
    specs: Iterable[TableSpec],
    *,
    fdb_load_mtl: bool,
    only_groups: Sequence[str] | None = None,
) -> list[TableSpec]:
    """Return the subset of `specs` that should run in this load.

    Args:
        specs: full TableSpec catalog (or subset).
        fdb_load_mtl: settings.FDB_LOAD_MTL â€” False excludes MTL.
        only_groups: if given, restrict the output to specs whose
            loader_group is in this list. None means "all groups
            (subject to MTL guard)".

    Returns:
        Filtered list, preserving input order. Phase 09 specs (with
        loader_group=None) are always included unless `only_groups`
        is set, in which case they are included only when None is
        explicitly listed.
    """
    out: list[TableSpec] = []
    for spec in specs:
        # MTL guard FIRST â€” even an explicit `only_groups=["fdb_mtl"]`
        # is denied when the flag is False. If the operator really
        # wants MTL, they must set FDB_LOAD_MTL=True. Anything else
        # makes the flag a lie.
        if spec.loader_group == MTL_LOADER_GROUP and not fdb_load_mtl:
            continue
        if only_groups is not None:
            if spec.loader_group not in only_groups:
                continue
        out.append(spec)
    return out


def mtl_specs(specs: Iterable[TableSpec]) -> list[TableSpec]:
    """Return only the MTL-grouped specs from `specs`.

    Used by the lock-in test that asserts MTL is excluded under
    default flag, and by the future MTL-activation wave's grant
    migration to enumerate exactly which tables need GRANT restoration.
    """
    return [s for s in specs if s.loader_group == MTL_LOADER_GROUP]


__all__ = ["filter_loadable_specs", "mtl_specs", "MTL_LOADER_GROUP"]


 succeeded in 432ms:
"""B9.A C3 â€” Reusable contract-test template for FDB ingester tables.

Every B9 phase (B9.B Tier A, B9.C Tier B, B9.D Tier C, B9.E RNDC14,
B9.F pricing, B9.G MTL) lands new `TableSpec` entries plus their
SQLAlchemy models and ingester wiring. The contract test set asserted
on every one of those tables is identical in shape, varies only in
which spec + which model + which fixture.

This module is the SHARED IMPLEMENTATION of that shape. Per-tier test
modules import the helpers and call them with concrete inputs:

    from drug_database.tests._fdb_contract import (
        assert_schema_parity,
        assert_latin1_decode_smoke,
        assert_row_count_reconciles,
        assert_no_parse_warnings,
        assert_upd_transaction_codes,
        assert_delta_semantics_acd_cycle,
    )

    def test_rmiid1_med_contract(local_drop, rmiid1_med_spec, RmiidMedModel):
        adapter = FDBLocalDropAdapter(local_drop.parent.parent)
        assert_schema_parity(rmiid1_med_spec, RmiidMedModel)
        assert_no_parse_warnings(adapter, local_drop, rmiid1_med_spec)
        assert_latin1_decode_smoke(adapter, local_drop, rmiid1_med_spec)
        assert_row_count_reconciles(
            adapter, local_drop, rmiid1_med_spec,
            actual_row_count=loaded_count,
        )

The file is intentionally named with a leading underscore so pytest
discovery does NOT pick it up as a test module â€” it is a helper
library. The accompanying `test_fdb_contract.py` covers the helpers
themselves.

ADVERSARIAL R1 mitigations folded in:
  * N4 (parse_table skip)        â€” assert_no_parse_warnings makes the
                                    "skip on field-count mismatch"
                                    branch FAIL the contract unless
                                    explicitly allowlisted.
  * A4 (delta correctness)       â€” assert_delta_semantics_acd_cycle
                                    runs the A/C/D/re-A simulator per
                                    DeltaSemantics class. UNKNOWN +
                                    APPEND_ONLY take the replay-safety
                                    path; UPSERT classes get the full
                                    correctness check.
  * T12 (UPD A/C/D probe)        â€” assert_upd_transaction_codes opens
                                    the `.UPD` zip and verifies every
                                    row's leading field is A/C/D.

The PARSE-WARNING-FAILS-TEST POLICY (charter v3.x):
  Any `_log.warning(...)` emitted by `FDBLocalDropAdapter.parse_table`
  during a contract run fails the contract test for that table â€” UNLESS
  the warning's `ingest_*` log-record key+value pair appears in the
  allowlist at `Werkbench/projects/infinityrx-platform/waves/B9/parse_warning_allowlist.md`
  with a documented count impact. Empty initial allowlist; entries
  added only with codex sign-off.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    FDBAdapter,
    FDBDrop,
    TableSpec,
    Tier,
    _stream_pipe_rows,
)


# ---------------------------------------------------------------------------
# Warning capture
# ---------------------------------------------------------------------------


class _ParseWarningCollector(logging.Handler):
    """Captures WARNING-level records emitted by fdb_adapter during parse.

    Used by ``assert_no_parse_warnings`` to assert that the silent-skip
    branches in `FDBLocalDropAdapter.parse_table` are never reached
    during a contract run.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        self.records.append(record)


def _collect_parse_warnings(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    source: str = "DB",
) -> tuple[list[dict[str, Any]], list[logging.LogRecord]]:
    """Run parse_table to completion, returning rows + warnings emitted.

    Drains the iterator so no warnings are missed; for small synthetic
    fixtures this is cheap. For real Tier-A tables it is also fine
    (rows < 10K). RNP3-class tables should use a sampled wrapper.
    """
    collector = _ParseWarningCollector()
    fdb_logger = logging.getLogger("drug_database.services.fdb_adapter")
    fdb_logger.addHandler(collector)
    fdb_logger.setLevel(logging.WARNING)
    try:
        rows = list(adapter.parse_table(drop, spec, source=source))
    finally:
        fdb_logger.removeHandler(collector)
    return rows, collector.records


# ---------------------------------------------------------------------------
# Schema parity
# ---------------------------------------------------------------------------


def assert_schema_parity(spec: TableSpec, model_class: type) -> None:
    """Assert TableSpec.columns set == SQLAlchemy model column set.

    Drift in either direction is a contract violation:

    * Extra column in model     â†’ model writes a column the parser
                                  never populates (silent NULL).
    * Extra column in spec      â†’ parser yields a key the model can't
                                  persist (silent drop).

    The contract is set-equality. Column order is OUT OF SCOPE here
    â€” DDL byte-for-byte ordering is checked in alembic migration tests
    elsewhere; this assertion is about the named surface area only.

    `model_class` may be a SQLAlchemy declarative class (has __table__)
    or any object exposing a `columns` attribute whose entries have a
    `.name` attribute.
    """
    table = getattr(model_class, "__table__", None)
    if table is not None:
        model_cols = {col.name for col in table.columns}
    else:
        model_cols = {col.name for col in model_class.columns}

    spec_cols = set(spec.columns)

    # Allow universal provenance fields the model defines but the spec
    # never emits via columns (they come from parse_table.body, not
    # spec.coercers).
    PROVENANCE = {
        "id",
        "as_of_date",
        "drop_sequence",
        "transaction_code",
        "created_at",
        "updated_at",
        "tenant_id",
    }
    model_extras = model_cols - spec_cols - PROVENANCE
    spec_extras = spec_cols - model_cols

    assert not model_extras, (
        f"Schema parity FAIL for {spec.table_name}: model has columns "
        f"not in TableSpec: {sorted(model_extras)}"
    )
    assert not spec_extras, (
        f"Schema parity FAIL for {spec.table_name}: TableSpec has columns "
        f"not in model: {sorted(spec_extras)}"
    )


# ---------------------------------------------------------------------------
# latin-1 decode smoke
# ---------------------------------------------------------------------------


def assert_latin1_decode_smoke(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    sample_rows: int = 1000,
    source: str = "DB",
) -> None:
    """First `sample_rows` rows decode as latin-1 without UnicodeError.

    T1 mitigation: text-heavy Tier A/B tables ship operator-entered
    drug names that frequently contain windows-1252 superset bytes
    (e.g. micro symbol Âµ at 0xB5, en-dash at 0x96). UTF-8 would barf;
    latin-1 must not. Failure here means either (a) the file is NOT
    latin-1 (vendor regression) or (b) the byte stream has been
    mangled by an intermediate tool.

    Iterates via `_stream_pipe_rows` directly (bypassing TableSpec
    coercion) â€” pure encoding check. Failures raise UnicodeDecodeError
    from `_stream_pipe_rows` and fail the test by exception, not by
    assertion.
    """
    zip_path = drop.upd_zip_path if source == "UPD" else drop.db_zip_path
    rows_seen = 0
    for fields in _stream_pipe_rows(zip_path, spec.table_name):
        # Already decoded to str by _stream_pipe_rows â€” touching .encode
        # roundtrip-asserts the bytes were valid latin-1 (encode back
        # never raises for any str < U+0100 source).
        for f in fields:
            f.encode("latin-1")  # smoke; raises if non-latin-1 sneaked in
        rows_seen += 1
        if rows_seen >= sample_rows:
            break
    # No assertion on rows_seen â€” a small table with < sample_rows rows
    # is fine. The decode check ran on every available row.


# ---------------------------------------------------------------------------
# Row-count reconciliation
# ---------------------------------------------------------------------------


def _parse_record_counts(path: Path) -> dict[str, int]:
    """Parse FDB's RECORD_COUNTS.TXT into {table_name: row_count}.

    Format observed at `data/reference/fdb/TEL251759D/`:
      <table_name>=<count>
    one entry per CRLF line. Encoding is latin-1; numbers are decimal.
    Blank lines and `#` comment lines are tolerated.
    """
    out: dict[str, int] = {}
    text = path.read_text(encoding="latin-1")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        try:
            out[key] = int(val)
        except ValueError:
            continue
    return out


def assert_row_count_reconciles(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    actual_row_count: int,
    tolerance_pct: Decimal = Decimal("0.001"),
) -> None:
    """Assert `actual_row_count` is within tolerance of vendor manifest.

    SC-2 (RECORD_COUNTS reconciliation): for every loaded table,
    `actual_row_count` Ã· `expected_row_count` must be within
    Â±`tolerance_pct` (default 0.1%). Small lookups should be exact
    (tolerance hits when sentinel_filter drops a documented sentinel
    row class â€” e.g. RNP3 PRICE_TYPE='14').

    Lookup key: `spec.record_counts_key` if set, else `spec.table_name`.
    Missing key in RECORD_COUNTS.TXT is a contract violation â€” the
    caller must extend `record_counts_key` rather than silently skip.
    """
    counts = _parse_record_counts(drop.record_counts_path)
    key = spec.record_counts_key or spec.table_name
    assert key in counts, (
        f"RECORD_COUNTS.TXT has no entry for key {key!r} (spec "
        f"{spec.table_name!r}). Set record_counts_key on the TableSpec "
        f"to the manifest's key for this table."
    )
    expected = counts[key]
    if expected == 0:
        # Tables FDB ships with 0 rows: assert actual is also 0.
        assert actual_row_count == 0, (
            f"{spec.table_name} expected 0 rows per RECORD_COUNTS.TXT, "
            f"got {actual_row_count}"
        )
        return
    delta_pct = abs(Decimal(actual_row_count - expected) / Decimal(expected))
    assert delta_pct <= tolerance_pct, (
        f"{spec.table_name} row-count reconciliation FAIL: "
        f"actual={actual_row_count} expected={expected} "
        f"delta_pct={delta_pct} > tolerance={tolerance_pct}"
    )


# ---------------------------------------------------------------------------
# Parse-warning policy
# ---------------------------------------------------------------------------


def assert_no_parse_warnings(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    source: str = "DB",
    allowlist: Iterable[str] = (),
) -> None:
    """No silent-skip warnings emitted by parse_table for this table.

    Mitigation for ADVERSARIAL N4 (parse_table silently skips field-
    count errors). The parser's warning-log branches:

      * ``fdb_table_transaction_code_missing``
      * ``fdb_table_field_count_mismatch``
      * ``fdb_table_row_invalid``

    Any of these in a contract run is a fail. To accept a known-good
    skip class, add the warning's primary `extra` key+value to
    `Werkbench/projects/infinityrx-platform/waves/B9/parse_warning_allowlist.md`
    with documented count impact and CONSULT-ROUND sign-off, then pass
    the parsed allowlist as `allowlist=`.

    The allowlist matches against `record.message` (the first arg of
    `_log.warning`). Empty initial allowlist; entries are deliberate.
    """
    _rows, records = _collect_parse_warnings(adapter, drop, spec, source=source)
    allow = set(allowlist)
    offenders = [
        r for r in records
        if (r.getMessage() not in allow) and (r.msg not in allow)
    ]
    assert not offenders, (
        f"{spec.table_name}: parse_table emitted {len(offenders)} "
        f"unallowlisted warning(s): "
        f"{[r.getMessage() for r in offenders[:5]]}"
    )


# ---------------------------------------------------------------------------
# UPD transaction-code probe (T12)
# ---------------------------------------------------------------------------


def assert_upd_transaction_codes(
    adapter: FDBAdapter,
    drop: FDBDrop,
    spec: TableSpec,
    *,
    sample_rows: int = 1000,
) -> None:
    """Every row in the table's `.UPD` file begins with A, C, or D.

    T12 mitigation: weekly FDB UPD delta format is documented as A/C/D
    -prefixed across all 220 tables. ADVERSARIAL R1 flagged that tables
    failing this assumption must be routed to TRUNCATE+RELOAD rather
    than UPSERT, or the delta is silently wrong.

    `spec.has_transaction_code` MUST be True for this assertion to run
    (DB.zip rows have no prefix; UPD rows do). For tables loaded only
    from DB.zip â€” skip this probe in the caller.

    Sample-bounded: probes first `sample_rows` lines. For Tier A
    tables that is the entire file; for RNP3-class that is enough
    coverage to catch a format flip.
    """
    assert spec.has_transaction_code, (
        f"{spec.table_name}: assert_upd_transaction_codes called but "
        f"spec.has_transaction_code=False â€” caller should skip this probe."
    )

    rows_checked = 0
    bad: list[tuple[int, str]] = []
    for line_idx, fields in enumerate(
        _stream_pipe_rows(drop.upd_zip_path, spec.table_name)
    ):
        if not fields:
            bad.append((line_idx, "<empty row>"))
        elif fields[0] not in {"A", "C", "D"}:
            bad.append((line_idx, fields[0]))
        rows_checked += 1
        if rows_checked >= sample_rows:
            break

    assert not bad, (
        f"{spec.table_name}: UPD A/C/D probe FAIL â€” {len(bad)} rows in "
        f"first {rows_checked} have non-A/C/D leading field: "
        f"{bad[:5]} (sample). This table is likely TRUNCATE+RELOAD, "
        f"not UPSERT â€” re-classify delta_semantics."
    )


# ---------------------------------------------------------------------------
# Delta semantics simulation (A/C/D/re-A)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeltaSimulationResult:
    """Outcome of a single A/C/D/re-A simulation step."""

    step: str  # "A", "C", "D", "re-A"
    rows_in_table_after: int
    target_row_values_after: dict[str, Any] | None


# A callable that:
#   * accepts a row dict + transaction_code
#   * applies the corresponding INSERT / UPSERT / DELETE to a test DB
#   * returns (current row count, current row state for the target key)
DeltaSimulator = Callable[
    [dict[str, Any], str],
    tuple[int, dict[str, Any] | None],
]


def assert_delta_semantics_acd_cycle(
    spec: TableSpec,
    *,
    natural_key: dict[str, Any],
    initial_row: dict[str, Any],
    changed_values: dict[str, Any],
    simulator: DeltaSimulator,
) -> None:
    """Simulate A â†’ C â†’ D â†’ re-A and assert per-semantics correctness.

    ADVERSARIAL R1 A4 mitigation: an UPSERT-by-natural-key path running
    only a replay-safety test (load same row twice â†’ 0 new) gives a
    PASS even when a `C` with changed values is silently ignored
    because `ON CONFLICT DO NOTHING` swallows it.

    This helper drives the simulator through four explicit steps and
    asserts on `spec.delta_semantics`:

      APPEND_ONLY:
        A â†’ C â†’ D â†’ re-A â†’ expect 4 rows (history; D + re-A are NEW
        rows in history)
      UPSERT_BY_NATURAL_KEY:
        A     â†’ 1 row with initial_row
        C     â†’ 1 row with changed_values (NOT silently ignored)
        D     â†’ 0 rows (deletion applied)
        re-A  â†’ 1 row with initial_row
      UPSERT_WITH_EFFECTIVE_DATE:
        A     â†’ 1 row at eff_date_1
        C     â†’ 2 rows (closed eff_date_1 + new eff_date_2)
                Caller may pass `changed_values` containing the new
                effective_date; assertion is rows_after >= 2 + latest
                row matches changed_values.
        D     â†’ latest row marked terminated; caller-defined
        re-A   â†’ new row
      TRUNCATE_RELOAD:
        Simulator should ignore tx codes; only the final reloaded
        state matters. Helper just asserts the simulator returns the
        post-reload count without raising. Use a dedicated
        truncate-reload test elsewhere.
      UNKNOWN:
        Skip â€” Phase 09 backward-compat (treated as APPEND_ONLY by
        downstream).

    The simulator is the integration surface: caller wires it against
    SQLite (unit) or Postgres (integration). The helper is pure
    orchestration.
    """
    if spec.delta_semantics in {DeltaSemantics.UNKNOWN, DeltaSemantics.TRUNCATE_RELOAD}:
        # UNKNOWN: Phase 09 compat â€” no contract.
        # TRUNCATE_RELOAD: state-after-reload tested elsewhere.
        return

    row_a = {**natural_key, **initial_row}
    row_c = {**natural_key, **changed_values}
    row_d = dict(natural_key)
    row_re_a = {**natural_key, **initial_row}

    # Step A (initial add)
    count_after_a, state_after_a = simulator(row_a, "A")
    # Step C (change)
    count_after_c, state_after_c = simulator(row_c, "C")
    # Step D (delete)
    count_after_d, _state_after_d = simulator(row_d, "D")
    # Step re-A (add back same natural key with initial values)
    count_after_re_a, state_after_re_a = simulator(row_re_a, "A")

    if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
        # Each step adds a history row; D produces a tombstone row.
        assert count_after_a == 1, f"{spec.table_name}: A produced {count_after_a} rows; expected 1"
        assert count_after_c >= 2, f"{spec.table_name}: C did not append (count={count_after_c})"
        assert count_after_d >= 3, f"{spec.table_name}: D did not append (count={count_after_d})"
        assert count_after_re_a >= 4, f"{spec.table_name}: re-A did not append (count={count_after_re_a})"
        return

    if spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY:
        assert count_after_a == 1, f"{spec.table_name}: A produced {count_after_a} rows; expected 1"
        assert count_after_c == 1, (
            f"{spec.table_name}: C left {count_after_c} rows; expected 1 "
            f"(upsert collapses to one row per natural key)"
        )
        assert state_after_c is not None and all(
            state_after_c.get(k) == v for k, v in changed_values.items()
        ), (
            f"{spec.table_name}: C did not propagate changed_values â€” "
            f"likely ON CONFLICT DO NOTHING regression (state={state_after_c})"
        )
        assert count_after_d == 0, (
            f"{spec.table_name}: D left {count_after_d} rows; expected 0 "
            f"(delete must remove the row, not tombstone it)"
        )
        assert count_after_re_a == 1, (
            f"{spec.table_name}: re-A produced {count_after_re_a} rows; expected 1"
        )
        assert state_after_re_a is not None and all(
            state_after_re_a.get(k) == v for k, v in initial_row.items()
        ), (
            f"{spec.table_name}: re-A did not restore initial values "
            f"(state={state_after_re_a})"
        )
        return

    if spec.delta_semantics is DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE:
        assert count_after_a == 1, f"{spec.table_name}: A produced {count_after_a} rows; expected 1"
        assert count_after_c >= 2, (
            f"{spec.table_name}: C did not open a new effective-dated row "
            f"(count={count_after_c}); expected >= 2"
        )
        assert state_after_c is not None and all(
            state_after_c.get(k) == v for k, v in changed_values.items()
        ), (
            f"{spec.table_name}: C latest row does not match changed_values "
            f"(state={state_after_c})"
        )
        # D and re-A are caller-defined per table; no fixed assertion here.
        return

    raise AssertionError(
        f"{spec.table_name}: unhandled delta_semantics "
        f"{spec.delta_semantics!r} in contract template"
    )


__all__ = [
    "assert_schema_parity",
    "assert_latin1_decode_smoke",
    "assert_row_count_reconciles",
    "assert_no_parse_warnings",
    "assert_upd_transaction_codes",
    "assert_delta_semantics_acd_cycle",
    "DeltaSimulationResult",
    "DeltaSimulator",
]


 succeeded in 430ms:
"""B9.A C10 â€” FDW name-collision preflight.

Generates the expected B9 table names (217 tables across Tiers A/B/C/D
plus RNDC14 + pricing) and scans every schema in `infinityrx_reference`
for any pre-existing table with the same name. Any collision aborts
B9.B before a single migration runs.

Why this exists: B9.B-G land alembic migrations into the
`drug_database` schema. If any other schema (`reference`, `shared`,
`public`, or a leftover dev schema) already contains a table whose
name matches a B9 table, the migration succeeds but the FDW exposure
silently picks the wrong one â€” operator sees stale data and never
gets a hard error.

The collision check is namespace-aware:
  * Collision = (any_schema, name in B9-expected-list)
  * Same-schema-different-name: ignored.
  * Different-name-but-similar: ignored.
  * `drug_database.<b9_name>`: NOT a collision IF the table was
    created by a prior B9.B-G migration (alembic_version proves it).
    Conservative path: any pre-existing table in `drug_database`
    matching a B9 name is reported, operator confirms it is owned
    by B9 before continuing.

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python infrastructure/scripts/preflight_b9_name_collision.py
    python infrastructure/scripts/preflight_b9_name_collision.py \\
        --record-counts data/reference/fdb/TEL251759D/Current/RECORD_COUNTS.TXT \\
        --evidence-out waves/B9/preflight_collision_evidence.md

Exit codes:
    0  no collisions
    1  config error (missing env var, RECORD_COUNTS missing, etc.)
    2  collisions found â€” operator MUST resolve before B9.B

Test seam: `scan_for_collisions` takes a `table_lister` callable so
unit tests can inject a fake (set of (schema, name) tuples) without
needing Postgres. The default reads
`information_schema.tables WHERE table_type='BASE TABLE'`.
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

logger = logging.getLogger("preflight_b9")


# ---------------------------------------------------------------------------
# Name generation
# ---------------------------------------------------------------------------


def fdb_name_to_table_name(fdb_table_name: str) -> str:
    """Convert a RECORD_COUNTS.TXT key to the DB table name.

    Convention used by `gen_fdb_tier_migration.py` (B9.A C2):
      RFOO_BAR_BAZ  â†’  rfoo_bar_baz
      RNP3_NDC_PRICE â†’ rnp3_ndc_price

    The transformation is lower-case only â€” underscores are preserved
    byte-for-byte. No other normalization. Matches the
    `spec.table_name.lower()` call in `_create_table_block`.
    """
    return fdb_table_name.strip().lower()


def load_expected_names(record_counts_path: Path) -> list[str]:
    """Read RECORD_COUNTS.TXT and return the full list of expected DB table names.

    Format (matches `_fdb_contract.py::_parse_record_counts`):
      <KEY>=<count>
    one entry per CRLF line; blanks and `#` comments tolerated.

    Returns DB-shaped names (lower-cased). Order preserved from the
    file for reproducibility.
    """
    text = record_counts_path.read_text(encoding="latin-1")
    out: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, _val = line.partition("=")
        db_name = fdb_name_to_table_name(key)
        if db_name in seen:
            continue
        seen.add(db_name)
        out.append(db_name)
    return out


# ---------------------------------------------------------------------------
# Collision scan
# ---------------------------------------------------------------------------


# Schemas that are EXPECTED to contain B9-named tables after the
# migration runs. Pre-existing tables here are reported but operator
# may sign them off if they came from a prior B9 partial run.
_OWNED_SCHEMAS = frozenset({"drug_database"})

# Schemas that should NEVER contain B9-named tables. Any pre-existing
# match here is an immediate hard collision.
_HARD_COLLISION_SCHEMAS = frozenset({
    "reference",  # FDW-fronted; conflicts produce silent wrong-data
    "shared",
    "public",
    "drug_db",   # legacy schema name still present per Phase 11A
    "pharmacy_dir",
    "prescriber_dir",
    "core",
})


def scan_for_collisions(
    expected_names: Iterable[str],
    *,
    table_lister: Callable[[], set[tuple[str, str]]],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (hard_collisions, soft_collisions) lists of (schema, name) tuples.

    A hard collision aborts; a soft collision is reported and
    requires explicit operator sign-off before continuing.
    """
    existing = table_lister()
    expected_set = set(expected_names)

    hard: list[tuple[str, str]] = []
    soft: list[tuple[str, str]] = []

    for schema, name in existing:
        if name not in expected_set:
            continue
        if schema in _HARD_COLLISION_SCHEMAS:
            hard.append((schema, name))
        elif schema in _OWNED_SCHEMAS:
            soft.append((schema, name))
        else:
            # Unknown schema â€” treat as hard. Better a false alarm than
            # a silent collision in a schema we forgot to classify.
            hard.append((schema, name))

    # Stable ordering for evidence reproducibility
    return sorted(hard), sorted(soft)


# ---------------------------------------------------------------------------
# Postgres lister (default â€” replaced in tests)
# ---------------------------------------------------------------------------


def _postgres_table_lister(connection_string: str) -> set[tuple[str, str]]:
    """Read base tables from information_schema across all non-system schemas."""
    from sqlalchemy import create_engine, text
    engine = create_engine(connection_string)
    out: set[tuple[str, str]] = set()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_schema, table_name "
                "FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' "
                "AND table_schema NOT IN "
                "  ('pg_catalog', 'information_schema', 'pg_toast')"
            ))
            for schema, name in result.fetchall():
                out.add((schema, name))
    finally:
        engine.dispose()
    return out


# ---------------------------------------------------------------------------
# Evidence formatter
# ---------------------------------------------------------------------------


def format_evidence(
    expected_names: list[str],
    hard: list[tuple[str, str]],
    soft: list[tuple[str, str]],
) -> str:
    """Build the markdown evidence body operator commits under waves/B9/."""
    lines: list[str] = [
        "# B9.A C10 â€” FDW Name-Collision Preflight Evidence",
        "",
        f"Expected B9 table names: **{len(expected_names)}**",
        f"Hard collisions:         **{len(hard)}**",
        f"Soft collisions (owned-schema match): **{len(soft)}**",
        "",
    ]
    if hard:
        lines.append("## Hard collisions â€” MUST resolve before B9.B")
        lines.append("")
        lines.append("| Schema | Table |")
        lines.append("|---|---|")
        for schema, name in hard:
            lines.append(f"| `{schema}` | `{name}` |")
        lines.append("")
    if soft:
        lines.append("## Soft collisions â€” drug_database tables matching B9 names")
        lines.append("")
        lines.append(
            "These may be leftovers from a prior partial B9 run. "
            "Operator confirms via alembic_version + manual schema "
            "review before continuing."
        )
        lines.append("")
        lines.append("| Schema | Table |")
        lines.append("|---|---|")
        for schema, name in soft:
            lines.append(f"| `{schema}` | `{name}` |")
        lines.append("")
    if not hard and not soft:
        lines.append("**No collisions found.** B9.B clear to proceed.")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--record-counts",
        type=Path,
        default=None,
        help="Path to FDB RECORD_COUNTS.TXT (defaults to data/reference/fdb/TEL251759D/Current/).",
    )
    parser.add_argument(
        "--evidence-out",
        type=Path,
        default=None,
        help="Optional markdown output path (defaults to stdout-only).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
    )

    # --record-counts default
    if args.record_counts is None:
        repo_root = Path(__file__).resolve().parents[2]
        args.record_counts = (
            repo_root / "data" / "reference" / "fdb" / "TEL251759D"
            / "Current" / "RECORD_COUNTS.TXT"
        )
    if not args.record_counts.exists():
        logger.error(
            "RECORD_COUNTS.TXT not found at %s â€” pass --record-counts or "
            "verify the FDB drop is on disk.",
            args.record_counts,
        )
        return 1

    expected = load_expected_names(args.record_counts)
    logger.info("preflight_b9_expected_names count=%d", len(expected))

    # Resolve reference-DB URL via shared guard (strict â€” no fallback).
    try:
        # Avoid hard dependency in unit tests; import only at run time.
        from shared.db.write_path_guard import resolve_reference_db_url
        db_url = resolve_reference_db_url()
    except RuntimeError as e:
        logger.error("%s", e)
        return 1

    def _lister() -> set[tuple[str, str]]:
        return _postgres_table_lister(db_url)

    hard, soft = scan_for_collisions(expected, table_lister=_lister)
    evidence = format_evidence(expected, hard, soft)
    print(evidence)
    if args.evidence_out:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(evidence, encoding="utf-8")
        logger.info("preflight_b9_evidence_written path=%s", args.evidence_out)

    if hard:
        logger.error(
            "preflight_b9_hard_collisions count=%d â€” refusing to proceed",
            len(hard),
        )
        return 2
    if soft:
        logger.warning(
            "preflight_b9_soft_collisions count=%d â€” operator sign-off required",
            len(soft),
        )
    logger.info("preflight_b9_clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())


 succeeded in 438ms:
"""B9.A C9 â€” Write-path guard for FDB reference data loaders.

Charter (and `waves/B9/write_path_enforcement.md`) require: every B9
FDB loader writes to `infinityrx_reference` and ONLY to
`infinityrx_reference`. Phase 09 tolerated the legacy fallback chain
`DATABASE_URL_SYNC_REFERENCE â†’ DATABASE_URL_SYNC â†’ DATABASE_URL`; B9
removes the fallback and adds a SQL-level assertion that fires
before any INSERT/COPY/CREATE TABLE.

Why both an env-var rule AND a SQL assertion:

  * Env-var only:  Operator runs `switch_env.sh dev` (sets
    `DATABASE_URL_SYNC` to the dev DB) and the legacy loader silently
    writes Tier A FDB tables into `infinityrx_dev`. They show up in
    the application schema instead of the FDW-fronted reference DB.
    The mistake is invisible until weekly delta produces duplicates.
  * SQL assertion only: Belt without suspenders. The env-var rule
    catches the typo BEFORE the engine even connects.

Public surface:

    resolve_reference_db_url() -> str
        Reads DATABASE_URL_SYNC_REFERENCE strictly; no fallback.
        Raises RuntimeError with a fix-it hint if unset.

    assert_reference_db_write_path(connection_or_session, *,
                                   expected='infinityrx_reference',
                                   resolver=None) -> None
        Runs `SELECT current_database()` and asserts the result
        equals `expected`. Mismatch â†’ RuntimeError.

The `resolver` parameter is a test seam â€” pass a callable returning
the DB name to bypass the real SQL roundtrip in unit tests.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any


REFERENCE_DB_ENV_VAR = "DATABASE_URL_SYNC_REFERENCE"
REFERENCE_DB_EXPECTED_NAME = "infinityrx_reference"


def resolve_reference_db_url() -> str:
    """Return the reference-DB sync URL â€” strict, no fallback.

    Phase 09 allowed `DATABASE_URL_SYNC_REFERENCE â†’ DATABASE_URL_SYNC
    â†’ DATABASE_URL`. B9 removes the fallback to eliminate the silent-
    wrong-DB class of bugs. Operators must explicitly set the env var
    before running an FDB loader.

    Raises:
        RuntimeError: if the env var is unset or empty. Message
        includes the fix-it path so the operator does not have to dig.
    """
    url = os.environ.get(REFERENCE_DB_ENV_VAR, "").strip()
    if not url:
        raise RuntimeError(
            f"{REFERENCE_DB_ENV_VAR} is required for B9 FDB loaders. "
            f"Fix: `source infrastructure/scripts/switch_env.sh dev` "
            f"(or mock/prod) exports it to the reference DB URL. "
            f"Phase 09's URL fallback chain "
            f"(DATABASE_URL_SYNC â†’ DATABASE_URL) is REMOVED in B9 to "
            f"prevent writing FDB tables to the operational DB."
        )
    # async driver doesn't work for sync engine â€” same coercion the
    # legacy loader does, kept consistent with scripts/load_fdb.py.
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _default_db_resolver(connection: Any) -> str:
    """Postgres path: SELECT current_database()."""
    from sqlalchemy import text
    return str(connection.execute(text("SELECT current_database()")).scalar())


def assert_reference_db_write_path(
    connection: Any,
    *,
    expected: str = REFERENCE_DB_EXPECTED_NAME,
    resolver: Callable[[Any], str] | None = None,
) -> None:
    """Assert the open connection points at the reference database.

    Args:
        connection: SQLAlchemy Connection or Session (anything with
            `.execute(text(...))`).
        expected: database name the loader requires. Defaults to
            ``infinityrx_reference``.
        resolver: test seam â€” callable taking the connection and
            returning the current DB name. Default uses
            `SELECT current_database()`.

    Raises:
        RuntimeError: if actual != expected. Message names both so
            the operator immediately sees what they were pointed at.
    """
    actual = (resolver or _default_db_resolver)(connection)
    if actual != expected:
        raise RuntimeError(
            f"Reference-DB write-path guard FAILED: connection is bound "
            f"to database {actual!r}, expected {expected!r}. B9 FDB "
            f"loaders only write to the reference DB. Re-run "
            f"`switch_env.sh` so DATABASE_URL_SYNC_REFERENCE points at "
            f"{expected!r} and try again."
        )


__all__ = [
    "REFERENCE_DB_ENV_VAR",
    "REFERENCE_DB_EXPECTED_NAME",
    "assert_reference_db_write_path",
    "resolve_reference_db_url",
]


exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'infrastructure/scripts/setup_fdw.sh' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/tests/unit/test_module_base_profile.py' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'waves/B9/parse_warning_allowlist.md' -Raw; Get-Content -Path 'waves/B9/status.md' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 462ms:
#!/usr/bin/env bash
# setup_fdw.sh â€” Wave B7 (Phase 11A) FDW configuration.
#
# For each env DB (infinityrx_dev, infinityrx_mock):
#   1. Enable postgres_fdw extension
#   2. Idempotently create FDW server pointing at infinityrx_reference
#   3. Idempotently create user mapping (ifx_<env>_app â†’ ifx_ref_reader)
#   4. Pre-check for cross-source-schema table-name collisions in the
#      reference DB (would conflict on IMPORT INTO single `reference`)
#   5. IMPORT FOREIGN SCHEMA <src> ... INTO reference for each source
#      schema in infinityrx_reference (consolidates `shared`,
#      `drug_database`, `drug_db` into ONE local `reference` namespace
#      per Phase 11A LOCKED line 17, 20: "postgres_fdw â†’ reference.*
#      foreign tables")
#
# Modes:
#   (default)  Idempotent setup â€” safe to re-run; no destructive ops
#   --refresh  Same as default but only IMPORTs newly-added source tables
#              (FDW drift mitigation; uses LIMIT TO clause)
#   --reset    DESTRUCTIVE â€” DROP SERVER ... CASCADE then recreate.
#              Requires INFINITYRX_DESTRUCTIVE_OK=1 env var to proceed.
#   --dry-run  Print intended SQL; do not execute
#   --env dev|mock|both  Target one or both env DBs (default: both)

set -euo pipefail

# Source the shared psql strict helpers (provides psql_strict + docker_psql_strict)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/lib/psql_strict.sh"

# Local-dev mode flag: route SQL through `docker compose exec -T postgres psql`
# instead of host `psql` (host may not have the client installed).
IN_DOCKER=${IN_DOCKER:-1}

# Container-aware psql wrapper (supports superuser + per-env app roles).
# Connects via Postgres unix socket inside the container, so DATABASE_URL
# auth doesn't apply â€” just `-U <role> -d <db>`.
exec_psql_strict() {
  local user="$1" db="$2" sql="$3"
  if [ "$IN_DOCKER" = "1" ]; then
    docker_psql_strict "$user" "$db" "$sql"
  else
    psql_strict "postgresql://$user@localhost:5432/$db" "$sql"
  fi
}

exec_psql_run() {
  local user="$1" db="$2" sql="$3"
  if [ "$DRY_RUN" = "1" ]; then
    echo "DRY-RUN [$user@$db]: ${sql:0:300}..."
  elif [ "$IN_DOCKER" = "1" ]; then
    # </dev/null prevents docker compose exec -T from consuming the
    # caller's stdin â€” without it, a `while IFS= read; done <<< "$X"`
    # loop wrapping this call exits after the first iteration because
    # docker exec slurped the rest of the heredoc.
    docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$user" -d "$db" -c "$sql" </dev/null >/dev/null
  else
    psql -v ON_ERROR_STOP=1 "postgresql://$user@localhost:5432/$db" -c "$sql" >/dev/null
  fi
}

MODE="default"
TARGET_ENV="both"
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --refresh) MODE="refresh"; shift ;;
    --reset)   MODE="reset"; shift ;;
    --verify)  MODE="verify"; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --env)     TARGET_ENV="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ "$MODE" = "reset" ] && [ "${INFINITYRX_DESTRUCTIVE_OK:-0}" != "1" ]; then
  echo "ERROR: --reset is destructive (DROP SERVER ... CASCADE drops foreign tables)." >&2
  echo "Set INFINITYRX_DESTRUCTIVE_OK=1 to acknowledge per .claude/rules/destructive-actions.md" >&2
  exit 2
fi

case "$TARGET_ENV" in
  dev)  ENVS=(dev) ;;
  mock) ENVS=(mock) ;;
  both) ENVS=(dev mock) ;;
  *) echo "Unknown --env value: $TARGET_ENV (need dev|mock|both)" >&2; exit 2 ;;
esac

# â”€â”€ --verify mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Iterates every entry in expected_reference_tables.txt and confirms each
# foreign table is queryable via FDW in each target env DB.
# Foreign tables are mounted as reference.<table> regardless of source schema.
# PASS = query exits 0 (empty result is fine â€” FDW link is the contract).
# Uses exec_psql_strict (respects IN_DOCKER flag, same as Phase 1 path).
# Exit 0 if all tables pass; exit 1 if any fail.
#
# B9.A C11: manifest-derived count (replaces hard-coded `expected 66`).
# As B9.B-G grow the manifest 66 â†’ 264, the verify step grows with it â€”
# no edit to this script required. The MIN_MANIFEST_COUNT floor catches
# accidental truncation; the deterministic sort ensures stable output
# ordering for diff-based gate evidence.
MIN_MANIFEST_COUNT=66
if [ "$MODE" = "verify" ]; then
  LIB_DIR="$SCRIPT_DIR/lib"
  MANIFEST="$LIB_DIR/expected_reference_tables.txt"
  if [ ! -f "$MANIFEST" ]; then
    echo "FATAL: manifest not found: $MANIFEST" >&2
    exit 2
  fi

  # Build a deterministic sorted view of manifest entries (C11):
  # strip CR, drop blanks + comments, then sort lexicographically by
  # schema|table so the iteration order is reproducible across runs
  # and across operators with different filesystem behavior.
  MANIFEST_SORTED="$(
    awk '
      { sub(/\r$/, "") }
      /^[[:space:]]*$/ { next }
      /^[[:space:]]*#/ { next }
      { print }
    ' "$MANIFEST" | sort
  )"

  MANIFEST_COUNT=$(printf '%s\n' "$MANIFEST_SORTED" | grep -c .)
  # Floor â€” manifest must not shrink below the B7 baseline. As B9.B-G
  # land new tiers (179 â†’ 245 â†’ 261 â†’ 262 â†’ 264) operators can bump
  # this floor in the same commit that grows the manifest; the value
  # below is the B7-shipped baseline.
  if [ "$MANIFEST_COUNT" -lt "$MIN_MANIFEST_COUNT" ]; then
    echo "FATAL: manifest has ${MANIFEST_COUNT} data lines; below floor of ${MIN_MANIFEST_COUNT}. Manifest must not shrink â€” investigate before proceeding." >&2
    exit 2
  fi
  echo "  Manifest: ${MANIFEST_COUNT} entries (floor: ${MIN_MANIFEST_COUNT})"

  total_pass=0
  total_fail=0
  fail_details=()

  for env in "${ENVS[@]}"; do
    env_db="infinityrx_${env}"
    env_pass=0
    env_fail=0
    echo "â”€â”€ Verifying FDW foreign tables in ${env_db} â”€â”€"
    # B9.A C11: iterate the deterministic-sorted manifest view so output
    # ordering is reproducible across runs / operators / filesystems.
    while IFS='|' read -r schema table; do
      # Already stripped of blanks/comments by the awk pass above.
      [[ -z "$schema" || -z "$table" ]] && continue
      sql="SELECT 1 FROM reference.${table} LIMIT 1"
      # exec_psql_strict respects IN_DOCKER flag (docker compose exec -T or
      # host psql depending on IN_DOCKER setting), consistent with Phase 1 path.
      if exec_psql_strict "infinityrx" "${env_db}" "${sql}" >/dev/null 2>&1; then
        env_pass=$((env_pass + 1))
      else
        echo "  FAIL: ${env_db} :: reference.${table} (source schema: ${schema})" >&2
        fail_details+=("${env_db}::reference.${table}")
        env_fail=$((env_fail + 1))
      fi
    done <<< "$MANIFEST_SORTED"
    echo "  ${env_db}: ${env_pass} PASS, ${env_fail} FAIL"
    total_pass=$((total_pass + env_pass))
    total_fail=$((total_fail + env_fail))
  done

  echo
  echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
  echo "  setup_fdw.sh --verify complete"
  echo "  Total: ${total_pass} PASS, ${total_fail} FAIL"
  if [ "${#fail_details[@]}" -gt 0 ]; then
    echo "  Failed tables:"
    for item in "${fail_details[@]}"; do
      echo "    - ${item}"
    done
  fi
  echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
  exit $((total_fail > 0 ? 1 : 0))
fi
# â”€â”€ end --verify â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Reference DB connection â€” must be set in environment
: "${DATABASE_URL_SYNC_REFERENCE:?DATABASE_URL_SYNC_REFERENCE must be set}"

# Pre-check: cross-schema table-name collisions in reference DB.
# Pure-SQL query â€” no shell array construction (adversarial round 3 fix).
# Tables that exist in multiple schemas legitimately and are NOT
# reference data â€” exclude them from collision check + IMPORT.
# `alembic_version` is migration bookkeeping (one per module's alembic).
IGNORED_TABLES="('alembic_version','dataq_ingestion_runs','ingestion_schedules')"

# Schemas that exist in reference DB but should NOT be FDW-imported.
# `core` exists because core-platform alembic runs against reference DB
# for shared.ingestion_runs but also creates env-DB-shape tables
# (tenants, users, audit_log) with custom ENUM types. Those types are
# local to the reference DB and don't transfer through FDW. Reference
# data lives in shared / drug_database / drug_db / pharmacy_dir /
# prescriber_dir.
IGNORED_SCHEMAS="('core')"

echo "â”€â”€ Pre-check: cross-source-schema table-name collisions â”€â”€"
COLLISIONS=$(exec_psql_strict "ifx_reference_writer" "infinityrx_reference" "
  SELECT table_name || ' (' || string_agg(table_schema, ', ' ORDER BY table_schema) || ')' AS conflict
  FROM information_schema.tables
  WHERE table_schema NOT IN ('pg_catalog','information_schema','public')
    AND table_schema NOT LIKE 'pg_%'
    AND table_type = 'BASE TABLE'
    AND table_name NOT IN $IGNORED_TABLES
  GROUP BY table_name
  HAVING count(DISTINCT table_schema) > 1
  ORDER BY table_name") || exit 1

if [ -n "$COLLISIONS" ]; then
  echo "FATAL: table-name collisions across source schemas â€” IMPORT INTO reference would conflict:" >&2
  echo "$COLLISIONS" >&2
  echo "Resolution: rename source tables OR import into per-schema local namespaces (deviates from Phase 11A LOCKED)." >&2
  exit 1
fi
echo "  OK â€” no collisions"
echo

# Enumerate source schemas (one per line) from reference DB
SOURCE_SCHEMAS=$(exec_psql_strict "ifx_reference_writer" "infinityrx_reference" "
  SELECT schema_name FROM information_schema.schemata
  WHERE schema_name NOT IN ('pg_catalog','information_schema','public')
    AND schema_name NOT LIKE 'pg_%'
    AND schema_name NOT IN $IGNORED_SCHEMAS
  ORDER BY schema_name") || exit 1

if [ -z "$SOURCE_SCHEMAS" ]; then
  echo "FATAL: no source schemas found in reference DB; loaders did not create any schema." >&2
  exit 1
fi

for env in "${ENVS[@]}"; do
  echo "â”€â”€ Setting up FDW in infinityrx_${env} â”€â”€"
  ENV_DB="infinityrx_${env}"
  # Use superuser for FDW setup â€” CREATE EXTENSION requires it, and
  # the env app role doesn't have it.
  ENV_USER="infinityrx"

  # Optional --reset: destructive recreate
  if [ "$MODE" = "reset" ]; then
    echo "  --reset: DROP SERVER infinityrx_reference_srv CASCADE"
    exec_psql_run "$ENV_USER" "$ENV_DB" "DROP SERVER IF EXISTS infinityrx_reference_srv CASCADE"
  fi

  # 1. Extension
  exec_psql_run "$ENV_USER" "$ENV_DB" "CREATE EXTENSION IF NOT EXISTS postgres_fdw"

  # 2. Idempotent server (CREATE only if absent).
  # Use the docker service name 'postgres' as the FDW host since the
  # env DB connects to itself on the same cluster â€” postgres_fdw uses
  # postgres-the-service-name's resolution context inside the container.
  # Locally-running script outside the container would use 'localhost'.
  FDW_HOST="${FDW_HOST:-postgres}"
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_foreign_server WHERE srvname = 'infinityrx_reference_srv') THEN
        CREATE SERVER infinityrx_reference_srv
          FOREIGN DATA WRAPPER postgres_fdw
          OPTIONS (host '$FDW_HOST', port '5432', dbname 'infinityrx_reference');
      END IF;
    END \$\$"

  # 2b. ALTER SERVER for option drift (host/port/dbname)
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    ALTER SERVER infinityrx_reference_srv
      OPTIONS (SET host '$FDW_HOST', SET port '5432', SET dbname 'infinityrx_reference')"

  # 3. Idempotent user mapping for the env's app role (app code's role)
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    CREATE USER MAPPING IF NOT EXISTS FOR ifx_${env}_app
      SERVER infinityrx_reference_srv
      OPTIONS (user 'ifx_ref_reader', password 'ref_password')"
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    ALTER USER MAPPING FOR ifx_${env}_app
      SERVER infinityrx_reference_srv
      OPTIONS (SET user 'ifx_ref_reader', SET password 'ref_password')"

  # 3c. Also create a mapping for the superuser (infinityrx) since
  # IMPORT FOREIGN SCHEMA runs as the connected user, not as the app
  # role. The superuser needs its own mapping so this very script can
  # execute the IMPORT.
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    CREATE USER MAPPING IF NOT EXISTS FOR $ENV_USER
      SERVER infinityrx_reference_srv
      OPTIONS (user 'ifx_ref_reader', password 'ref_password')"
  exec_psql_run "$ENV_USER" "$ENV_DB" "
    ALTER USER MAPPING FOR $ENV_USER
      SERVER infinityrx_reference_srv
      OPTIONS (SET user 'ifx_ref_reader', SET password 'ref_password')"

  # 4. Local landing schema
  exec_psql_run "$ENV_USER" "$ENV_DB" "CREATE SCHEMA IF NOT EXISTS reference"
  exec_psql_run "$ENV_USER" "$ENV_DB" "GRANT USAGE ON SCHEMA reference TO ifx_${env}_app"

  # 5. IMPORT each source schema INTO local `reference`
  while IFS= read -r src_schema; do
    src_schema=${src_schema%$'\r'}
    [ -z "$src_schema" ] && continue
    if ! [[ "$src_schema" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
      echo "FATAL: invalid schema name '$src_schema' â€” refusing to IMPORT" >&2
      exit 1
    fi
    # Build comma-separated LIMIT TO list of all importable tables
    # (excludes IGNORED_TABLES â€” migration bookkeeping not reference data).
    IMPORT_TABLES=$(exec_psql_strict "ifx_reference_writer" "infinityrx_reference" "
      SELECT table_name FROM information_schema.tables
      WHERE table_schema = '${src_schema}' AND table_type = 'BASE TABLE'
        AND table_name NOT IN $IGNORED_TABLES
      ORDER BY table_name") || exit 1
    if [ -z "$IMPORT_TABLES" ]; then
      echo "  ${src_schema}: no importable tables (all excluded)"
      continue
    fi

    if [ "$MODE" = "refresh" ]; then
      # Diff: source tables - already-imported foreign tables
      NEW_TABLES=$(exec_psql_strict "$ENV_USER" "$ENV_DB" "
        WITH src AS (
          SELECT '${src_schema}' AS s, unnest(string_to_array('$(echo "$IMPORT_TABLES" | tr '\n' ',' | sed 's/,$//')', ',')) AS table_name
        ),
        existing AS (
          SELECT ftrelid::regclass::text AS qual_name FROM pg_foreign_table
        )
        SELECT s.table_name FROM src s
        WHERE 'reference.' || s.table_name NOT IN (SELECT qual_name FROM existing)") || exit 1
      if [ -z "$NEW_TABLES" ]; then
        echo "  ${src_schema}: no new tables to import"
        continue
      fi
      LIMIT_LIST=$(echo "$NEW_TABLES" | paste -sd, -)
    else
      LIMIT_LIST=$(echo "$IMPORT_TABLES" | paste -sd, -)
    fi
    # Use bash parameter expansion (no pipe) to avoid SIGPIPE under
    # `set -o pipefail` â€” head/cut exiting early would propagate as
    # script failure and break the loop after the first schema.
    LIMIT_PREVIEW="${LIMIT_LIST:0:100}"
    echo "  Importing from ${src_schema} (${LIMIT_PREVIEW}...)"
    exec_psql_run "$ENV_USER" "$ENV_DB" "
      IMPORT FOREIGN SCHEMA ${src_schema} LIMIT TO (${LIMIT_LIST})
        FROM SERVER infinityrx_reference_srv INTO reference"
  done <<< "$SOURCE_SCHEMAS"

  # 6. Grant SELECT on all imported foreign tables to the env app role.
  # IMPORT FOREIGN SCHEMA creates tables owned by the connecting superuser;
  # the app role needs explicit SELECT grants to query them.
  # GRANT USAGE on the schema (step 4) is not sufficient.
  exec_psql_run "$ENV_USER" "$ENV_DB" "GRANT SELECT ON ALL TABLES IN SCHEMA reference TO ifx_${env}_app"

  echo "  OK â€” FDW configured in infinityrx_${env}"
  echo
done

echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo "  setup_fdw.sh complete (mode=$MODE, dry_run=$DRY_RUN)"
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"


 succeeded in 497ms:
"""B9.A C13 â€” Lock-in test for the drug-database declarative base.

Captures the Phase 09 baseline (9 tables on DrugBase.metadata). B9.B's
first commit that pushes this beyond the threshold is the trigger to
refactor into tier-scoped bases per
`waves/B9/module_base_profile.md`.

The test is intentionally an EQUALITY assertion, not a `>=` floor:
the WHOLE POINT is to detect when a new tier silently piles onto
DrugBase and to force a refactor decision in the same commit.
"""
from __future__ import annotations

# Phase 09 baseline. When B9.B-G land FDB models, this number changes:
#   * EXPECTED outcome: stays at 9; new tier models live on a separate
#     FDBBase declarative base. The shared MetaData is what alembic
#     sees (per waves/B9/module_base_profile.md "Recommended pattern").
#   * UNEXPECTED outcome: number > 9 means a new tier piled onto
#     DrugBase. The test fails; the operator must either (a) split into
#     a sub-base (the documented pattern) or (b) consciously bump this
#     baseline if the new tables genuinely belong on DrugBase.
PHASE_09_DRUGBASE_TABLE_COUNT = 9


def test_drugbase_table_count_matches_phase_09_baseline() -> None:
    """Detects accidental B9 model attachment to DrugBase."""
    from drug_database.models.tables import DrugBase

    actual = len(DrugBase.metadata.tables)
    assert actual == PHASE_09_DRUGBASE_TABLE_COUNT, (
        f"DrugBase.metadata.tables has {actual} entries; baseline is "
        f"{PHASE_09_DRUGBASE_TABLE_COUNT}. If a B9.B-G commit added "
        f"models, route them to a tier-scoped FDBBase (see "
        f"waves/B9/module_base_profile.md). If the increase is "
        f"intentional, bump PHASE_09_DRUGBASE_TABLE_COUNT in this file "
        f"in the same commit with a rationale in the message."
    )


def test_drugbase_imports_without_circular_errors() -> None:
    """Regression detector for sub-base pattern landing.

    Once the tier-scoped FDBBase lands, this test catches the
    classic circular-import bug where `fdb.__init__` tries to import
    `tables.DrugBase` and `tables` tries to import `fdb.fdb_metadata`.
    A clean import here proves the import graph is acyclic.
    """
    import importlib

    # Force a fresh import to surface any side-effect ordering bugs.
    import drug_database.models.tables as tables_mod
    importlib.reload(tables_mod)
    assert hasattr(tables_mod, "DrugBase"), (
        "drug_database.models.tables no longer exports DrugBase â€” "
        "this is an unannounced breaking change."
    )


def test_drugbase_metadata_schema_is_drug_db() -> None:
    """Phase 09 schema invariant â€” DrugBase tables live in drug_db schema.

    When the tier-scoped pattern lands, the new FDBBase metadata uses
    `drug_database` schema (per the recon doc). The two schemas
    coexist in the same physical DB. This test pins the Phase 09
    side so a B9 refactor cannot accidentally move existing tables.
    """
    from drug_database.models.tables import DrugBase

    schemas = {tbl.schema for tbl in DrugBase.metadata.tables.values()}
    # Phase 09 uses 'drug_db'; the FDB pricing layer (already shipped
    # in Phase 09) uses 'drug_database'. Both are legitimate; assert
    # we are not picking up some THIRD schema unexpectedly.
    assert schemas <= {"drug_db", "drug_database"}, (
        f"DrugBase tables span unexpected schemas: {sorted(schemas)}; "
        f"expected subset of {{'drug_db', 'drug_database'}}."
    )


 succeeded in 498ms:
-- B9.A C4 â€” DB-level guard for FDB MTL (Medical Test Lexicon) tables.
--
-- Charter v3.2 + ADVERSARIAL A8 mitigation: even when MTL schemas
-- exist (B9.G lands them), the app roles MUST NOT be able to
-- INSERT / UPDATE / DELETE on them unless the future MTL-activation
-- wave explicitly restores the grants. This file is the SQL template
-- that B9.G's grant migration applies AFTER `CREATE TABLE ... mtl_*`.
--
-- Layered with the app-side `filter_loadable_specs` in
-- modules/drug-database/drug_database/services/fdb_loader_registry.py:
-- the app filter is the fast path; this REVOKE is the slow path that
-- catches any regression where the app filter mis-fires.
--
-- File extension `.sql.tmpl` (not `.sql`) signals this is NOT applied
-- by `alembic` or `run_migrations.sh` directly â€” B9.G generates the
-- concrete migration body from this template, substituting the
-- per-tier MTL table list captured by `fdb_loader_registry.mtl_specs(...)`.
--
-- Substitution placeholders (replace before applying):
--   {{SCHEMA}}      â†’ typically "drug_database"
--   {{MTL_TABLES}}  â†’ comma-separated table list, e.g.
--                     mtl_test_lex_master, mtl_test_lex_xref
--   {{APP_ROLES}}   â†’ ifx_dev_app, ifx_mock_app, IFX_APP_ROLE-from-env
--                     (B7.3 env-driven pattern â€” see migrations under
--                      modules/*/alembic/versions/)
--
-- Usage from a B9.G alembic migration:
--   op.execute(text(
--       Path("infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl")
--         .read_text(encoding="utf-8")
--         .replace("{{SCHEMA}}", "drug_database")
--         .replace("{{MTL_TABLES}}", ", ".join(mtl_table_names))
--         .replace("{{APP_ROLES}}", ", ".join(_APP_ROLES))
--   ))
--
-- Idempotent: re-running this script produces no error (REVOKE on
-- already-revoked privileges is a no-op in Postgres). SELECT is NOT
-- revoked â€” reads stay open for the app-layer filter to enforce its
-- own contract.

-- 1) Revoke writes on the MTL tables themselves
REVOKE INSERT, UPDATE, DELETE
    ON {{SCHEMA}}.{{MTL_TABLES}}
    FROM {{APP_ROLES}};

-- 2) Revoke USAGE on any per-table sequences (defense in depth â€” even
--    if a row INSERT slipped past somehow, the sequence advance would
--    fail). Postgres auto-creates sequences for SERIAL / IDENTITY
--    columns; this loop only matters if a future MTL model uses one.
DO $$
DECLARE
    seq_name text;
BEGIN
    FOR seq_name IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = '{{SCHEMA}}'
          AND c.relkind = 'S'
          AND c.relname LIKE 'mtl_%'
    LOOP
        EXECUTE format(
            'REVOKE USAGE, SELECT, UPDATE ON SEQUENCE {{SCHEMA}}.%I FROM {{APP_ROLES}}',
            seq_name
        );
    END LOOP;
END $$;

-- 3) Verification block â€” fails loudly if any app role still has
--    write privilege on an MTL table after the REVOKE.
DO $$
DECLARE
    bad_count int;
BEGIN
    SELECT count(*) INTO bad_count
    FROM information_schema.role_table_grants
    WHERE table_schema = '{{SCHEMA}}'
      AND table_name LIKE 'mtl_%'
      AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE')
      AND grantee IN ({{APP_ROLES_QUOTED}});

    IF bad_count > 0 THEN
        RAISE EXCEPTION
            'fdb_mtl_revoke: % residual write grants on mtl_* tables '
            'after REVOKE â€” guard FAILED. Inspect with: '
            'SELECT grantee, table_name, privilege_type '
            'FROM information_schema.role_table_grants '
            'WHERE table_schema = ''{{SCHEMA}}'' '
            'AND table_name LIKE ''mtl_%'' '
            'AND privilege_type IN (''INSERT'', ''UPDATE'', ''DELETE'');',
            bad_count;
    END IF;
END $$;


2026-05-12T04:46:56.958558Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.6 seconds
Output:
Get-Content : Cannot find path 'C:\Users\MK\Desktop\Code 
Projects\InfinityRx\infinityrx-platform\waves\B9\parse_warning_allowlist.md' because it does not exist.
At line:2 char:1
+ Get-Content -Path 'waves/B9/parse_warning_allowlist.md' -Raw; Get-Con ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\MK\Des...ng_allowlist.md:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 
Get-Content : Cannot find path 'C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B9\status.md' 
because it does not exist.
At line:2 char:63
+ ... rning_allowlist.md' -Raw; Get-Content -Path 'waves/B9/status.md' -Raw
+                               ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\MK\Des...es\B9\status.md:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 

 exited 1 in 620ms:
Get-Content : Cannot find path 'C:\Users\MK\Desktop\Code 
Projects\InfinityRx\infinityrx-platform\waves\B9\parse_warning_allowlist.md' because it does not exist.
At line:2 char:1
+ Get-Content -Path 'waves/B9/parse_warning_allowlist.md' -Raw; Get-Con ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\MK\Des...ng_allowlist.md:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 
Get-Content : Cannot find path 'C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B9\status.md' 
because it does not exist.
At line:2 char:63
+ ... rning_allowlist.md' -Raw; Get-Content -Path 'waves/B9/status.md' -Raw
+                               ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\MK\Des...es\B9\status.md:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 

codex
Most of the targeted code looks intentionally conservative. One mismatch already surfaced: the prompt lists `waves/B9/...` artifacts, but those paths are not present in this checkout, so I’ll verify whether they exist under a different root or only in the commits/artifact system.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg --files | rg "(''^|/)waves/B9/(status|parse_warning_allowlist|phase09_compat_baseline|module_base_profile|write_path_enforcement)'"\\.md"'$|parse_warning_allowlist|B9.A C10|phase09_compat_baseline"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show --name-status --oneline --decorate --stat 9b61d6d --' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show --name-status --oneline --decorate --stat 3ead3bd --' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
2026-05-12T04:47:05.789323Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git ls-tree -r --name-only HEAD | rg "''^waves/B9/|parse_warning_allowlist|status'"\\.md"'$"'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git ls-tree -r --name-only HEAD | rg "''^waves/B9/|parse_warning_allowlist|status'"\\.md"'$"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git ls-tree -r --name-only HEAD | rg "''^waves/B9/|parse_warning_allowlist|status'"\\.md"'$"'` rejected: blocked by policy
 succeeded in 454ms:
9b61d6d (HEAD -> develop) B9.A C12+C13: Phase 09 compat baseline + module base profile lock-in
A	modules/drug-database/tests/integration/test_phase09_compat_baseline.py
A	modules/drug-database/tests/unit/test_module_base_profile.py

 succeeded in 453ms:
3ead3bd B9.A C3: ingester contract test template + N4/A4/T12 mitigations
A	modules/drug-database/tests/_fdb_contract.py
A	modules/drug-database/tests/unit/test_fdb_contract.py

 succeeded in 528ms:
modules\drug-database\tests\integration\test_phase09_compat_baseline.py

2026-05-12T04:47:13.657767Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git ls-tree -r --name-only HEAD'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-ChildItem -Path 'waves' -Force -Recurse -Depth 2 | Select-Object FullName" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git ls-tree -r --name-only HEAD' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git ls-tree -r --name-only HEAD'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/tests/unit/test_fdb_contract.py' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/tests/unit/test_fdb_delta_semantics.py' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 450ms:

FullName                                                                                         
--------                                                                                         
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B7.2                      
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B8                        
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B8.1.1                    
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B7.2\evidence.md          
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B7.2\ship.md              
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B8\baseline.md            
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B8.1.1\codex-gate-close.md
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B8.1.1\evidence.md        
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\waves\B8.1.1\ship.md            



 succeeded in 411ms:
"""B9.A C3 â€” Unit tests for the FDB contract-test helpers.

The helpers in `tests/_fdb_contract.py` are the shared assertion shape
that every B9.B-G phase reuses. These tests cover the helpers
themselves against synthetic fixtures so that defects in the template
surface BEFORE B9.B starts wiring 113 Tier A tables through it.
"""
from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    FDBDrop,
    FDBLocalDropAdapter,
    TableSpec,
    Tier,
)
# Importing the helper from `tests._fdb_contract` collides when pytest
# also collects shared/tests/ in the same run (two `tests` packages).
# Insert the tests dir on sys.path so the helper is reachable directly.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _fdb_contract import (  # noqa: E402
    assert_delta_semantics_acd_cycle,
    assert_latin1_decode_smoke,
    assert_no_parse_warnings,
    assert_row_count_reconciles,
    assert_schema_parity,
    assert_upd_transaction_codes,
)


# ---------------------------------------------------------------------------
# Fixtures â€” synthetic FDB drop on disk
# ---------------------------------------------------------------------------


SIMPLE_SPEC = TableSpec(
    table_name="RFOO_TEST",
    columns=("id", "name"),
    coercers={"id": int, "name": str},
    tier=Tier.A,
    record_counts_key="RFOO",
    delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
)


def _write_zip(zip_path: Path, table_name: str, rows: list[str]) -> None:
    """Write a synthetic FDB-shaped zip with one pipe-delimited table.

    Body is latin-1, CRLF-terminated. Filename in the zip equals the
    literal table name (no extension), per FDB convention.
    """
    body = "\r\n".join(rows).encode("latin-1") + b"\r\n"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(table_name, body)


@pytest.fixture
def synthetic_drop(tmp_path: Path) -> FDBDrop:
    """A minimal but valid FDBDrop pointed at on-disk synthetic zips."""
    db_zip = tmp_path / "NDDF PLUS DB.zip"
    upd_zip = tmp_path / "NDDF PLUS UPD.zip"
    ddl_zip = tmp_path / "NDDF PLUS DDL.zip"
    highlights = tmp_path / "FDB_CLINICAL_HIGHLIGHTS.ZIP"
    record_counts = tmp_path / "RECORD_COUNTS.TXT"

    _write_zip(
        db_zip,
        "RFOO_TEST",
        ["1|alpha", "2|beta", "3|gamma"],
    )
    _write_zip(ddl_zip, "DDL_PLACEHOLDER", ["unused"])
    _write_zip(highlights, "HIGHLIGHTS_PLACEHOLDER", ["unused"])

    # UPD-shape: leading A/C/D prefix on each row.
    _write_zip(
        upd_zip,
        "RFOO_TEST",
        ["A|10|delta", "C|10|delta2", "D|10|"],
    )

    record_counts.write_text(
        "# synthetic record counts\nRFOO=3\nRBAR=0\n",
        encoding="latin-1",
    )

    return FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=db_zip,
        ddl_zip_path=ddl_zip,
        upd_zip_path=upd_zip,
        highlights_zip_path=highlights,
        record_counts_path=record_counts,
    )


@pytest.fixture
def adapter(tmp_path: Path) -> FDBLocalDropAdapter:
    return FDBLocalDropAdapter(tmp_path)


# ---------------------------------------------------------------------------
# Schema parity
# ---------------------------------------------------------------------------


@dataclass
class _FakeColumn:
    name: str


@dataclass
class _FakeModelMatches:
    """Stand-in model whose columns match SIMPLE_SPEC exactly."""

    columns = (_FakeColumn("id"), _FakeColumn("name"))


@dataclass
class _FakeModelExtraInSpec:
    """Model missing 'name' â€” spec has a column the model doesn't."""

    columns = (_FakeColumn("id"),)


@dataclass
class _FakeModelExtraInModel:
    """Model has an extra column not in spec; not a provenance name."""

    columns = (_FakeColumn("id"), _FakeColumn("name"), _FakeColumn("price"))


@dataclass
class _FakeModelProvenanceOnlyExtras:
    """Model adds provenance columns only â€” should NOT fail parity."""

    columns = (
        _FakeColumn("id"),
        _FakeColumn("name"),
        _FakeColumn("as_of_date"),
        _FakeColumn("drop_sequence"),
        _FakeColumn("transaction_code"),
        _FakeColumn("created_at"),
        _FakeColumn("tenant_id"),
    )


def test_schema_parity_matches() -> None:
    assert_schema_parity(SIMPLE_SPEC, _FakeModelMatches)


def test_schema_parity_provenance_extras_are_ignored() -> None:
    """Provenance columns added by parse_table are not parity violations."""
    assert_schema_parity(SIMPLE_SPEC, _FakeModelProvenanceOnlyExtras)


def test_schema_parity_fails_when_spec_has_extra_column() -> None:
    with pytest.raises(AssertionError, match="TableSpec has columns not in model"):
        assert_schema_parity(SIMPLE_SPEC, _FakeModelExtraInSpec)


def test_schema_parity_fails_when_model_has_extra_non_provenance_column() -> None:
    with pytest.raises(AssertionError, match="model has columns not in TableSpec"):
        assert_schema_parity(SIMPLE_SPEC, _FakeModelExtraInModel)


# ---------------------------------------------------------------------------
# latin-1 decode smoke
# ---------------------------------------------------------------------------


def test_latin1_decode_smoke_passes_on_valid_latin1(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    # All rows are pure ASCII (subset of latin-1) â€” passes.
    assert_latin1_decode_smoke(adapter, synthetic_drop, SIMPLE_SPEC, sample_rows=10)


def test_latin1_decode_smoke_handles_high_bytes(
    tmp_path: Path, adapter: FDBLocalDropAdapter
) -> None:
    """Bytes 0x80-0xFF are valid latin-1 (windows-1252 superset)."""
    db_zip = tmp_path / "NDDF PLUS DB.zip"
    # \xb5 = Âµ (micro sign); \x96 = en-dash in windows-1252.
    body = b"1|alpha\xb5\r\n2|beta\x96gamma\r\n"
    with zipfile.ZipFile(db_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("RFOO_TEST", body)

    drop = FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=db_zip,
        ddl_zip_path=tmp_path / "ddl.zip",
        upd_zip_path=tmp_path / "upd.zip",
        highlights_zip_path=tmp_path / "h.zip",
        record_counts_path=tmp_path / "rc.txt",
    )

    assert_latin1_decode_smoke(adapter, drop, SIMPLE_SPEC, sample_rows=10)


# ---------------------------------------------------------------------------
# Row-count reconciliation
# ---------------------------------------------------------------------------


def test_row_count_reconciles_exact_match(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    assert_row_count_reconciles(
        adapter, synthetic_drop, SIMPLE_SPEC, actual_row_count=3
    )


def test_row_count_reconciles_within_tolerance(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    # RECORD_COUNTS says 3; tolerance 33% (Decimal) accepts 2 or 4.
    assert_row_count_reconciles(
        adapter, synthetic_drop, SIMPLE_SPEC,
        actual_row_count=4, tolerance_pct=Decimal("0.34"),
    )


def test_row_count_reconcile_fails_outside_tolerance(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    with pytest.raises(AssertionError, match="row-count reconciliation FAIL"):
        assert_row_count_reconciles(
            adapter, synthetic_drop, SIMPLE_SPEC, actual_row_count=10
        )


def test_row_count_reconcile_fails_when_key_missing(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    """Spec whose record_counts_key isn't in the manifest must FAIL loudly."""
    missing_key_spec = TableSpec(
        table_name="RBAZ_NOT_IN_MANIFEST",
        columns=("id",),
        coercers={"id": int},
        tier=Tier.A,
        record_counts_key="RBAZ",  # not in synthetic RECORD_COUNTS.TXT
    )
    with pytest.raises(AssertionError, match="no entry for key"):
        assert_row_count_reconciles(
            adapter, synthetic_drop, missing_key_spec, actual_row_count=0
        )


def test_row_count_zero_expected_requires_actual_zero(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    rbar_spec = TableSpec(
        table_name="RBAR_TEST",
        columns=("id",),
        coercers={"id": int},
        tier=Tier.A,
        record_counts_key="RBAR",
    )
    # RBAR=0 in synthetic manifest. actual=0 passes.
    assert_row_count_reconciles(
        adapter, synthetic_drop, rbar_spec, actual_row_count=0
    )
    # actual=1 fails.
    with pytest.raises(AssertionError, match="expected 0 rows"):
        assert_row_count_reconciles(
            adapter, synthetic_drop, rbar_spec, actual_row_count=1
        )


# ---------------------------------------------------------------------------
# Parse-warning policy
# ---------------------------------------------------------------------------


def test_no_parse_warnings_on_clean_table(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    """Clean rows emit no parse_table warnings."""
    assert_no_parse_warnings(adapter, synthetic_drop, SIMPLE_SPEC)


def test_no_parse_warnings_FAILS_on_field_count_mismatch(
    tmp_path: Path, adapter: FDBLocalDropAdapter
) -> None:
    """A row with wrong field count must FAIL the contract, not silently skip."""
    db_zip = tmp_path / "NDDF PLUS DB.zip"
    _write_zip(
        db_zip,
        "RFOO_TEST",
        [
            "1|alpha",        # OK â€” 2 fields
            "2|beta|extra",   # BAD â€” 3 fields, expected 2
        ],
    )
    drop = FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=db_zip,
        ddl_zip_path=tmp_path / "ddl.zip",
        upd_zip_path=tmp_path / "upd.zip",
        highlights_zip_path=tmp_path / "h.zip",
        record_counts_path=tmp_path / "rc.txt",
    )
    with pytest.raises(AssertionError, match="unallowlisted warning"):
        assert_no_parse_warnings(adapter, drop, SIMPLE_SPEC)


def test_no_parse_warnings_allowlist_accepts_known_skip_class(
    tmp_path: Path, adapter: FDBLocalDropAdapter
) -> None:
    """An explicit allowlist entry suppresses the contract failure."""
    db_zip = tmp_path / "NDDF PLUS DB.zip"
    _write_zip(
        db_zip,
        "RFOO_TEST",
        ["1|alpha", "2|beta|extra"],
    )
    drop = FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=db_zip,
        ddl_zip_path=tmp_path / "ddl.zip",
        upd_zip_path=tmp_path / "upd.zip",
        highlights_zip_path=tmp_path / "h.zip",
        record_counts_path=tmp_path / "rc.txt",
    )
    # `_log.warning("ingest_field_count_mismatch", extra={...})` â€” msg is the
    # first positional arg of the log call. Allowlist matches against that.
    assert_no_parse_warnings(
        adapter, drop, SIMPLE_SPEC,
        allowlist={"fdb_table_field_count_mismatch"},
    )


# ---------------------------------------------------------------------------
# UPD A/C/D transaction-code probe (T12)
# ---------------------------------------------------------------------------


def test_upd_transaction_codes_pass_when_all_acd(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    """The synthetic UPD has A/C/D-prefixed rows â€” passes."""
    spec_with_tx = TableSpec(
        table_name="RFOO_TEST",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        has_transaction_code=True,
        tier=Tier.A,
        record_counts_key="RFOO",
    )
    assert_upd_transaction_codes(adapter, synthetic_drop, spec_with_tx)


def test_upd_transaction_codes_fail_on_non_acd_prefix(
    tmp_path: Path, adapter: FDBLocalDropAdapter
) -> None:
    """A non-A/C/D leading field must FAIL â€” table is TRUNCATE+RELOAD shape."""
    upd_zip = tmp_path / "NDDF PLUS UPD.zip"
    _write_zip(
        upd_zip,
        "RFOO_TEST",
        ["A|1|alpha", "X|2|beta"],  # X is not a valid tx code
    )
    drop = FDBDrop(
        drop_date=__import__("datetime").date(2026, 5, 6),
        license_code="TEL000000T",
        db_zip_path=tmp_path / "db.zip",
        ddl_zip_path=tmp_path / "ddl.zip",
        upd_zip_path=upd_zip,
        highlights_zip_path=tmp_path / "h.zip",
        record_counts_path=tmp_path / "rc.txt",
    )
    spec_with_tx = TableSpec(
        table_name="RFOO_TEST",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        has_transaction_code=True,
        tier=Tier.A,
    )
    with pytest.raises(AssertionError, match="UPD A/C/D probe FAIL"):
        assert_upd_transaction_codes(adapter, drop, spec_with_tx)


def test_upd_probe_refuses_to_run_on_non_upd_spec(
    adapter: FDBLocalDropAdapter, synthetic_drop: FDBDrop
) -> None:
    """Caller error: probing a DB-only spec is a programming bug, not a data bug."""
    with pytest.raises(AssertionError, match="caller should skip this probe"):
        assert_upd_transaction_codes(adapter, synthetic_drop, SIMPLE_SPEC)


# ---------------------------------------------------------------------------
# Delta semantics simulation (A/C/D/re-A)
# ---------------------------------------------------------------------------


class _InMemoryUpsertStore:
    """Trivial UPSERT_BY_NATURAL_KEY simulator backed by a dict."""

    def __init__(self, natural_key_fields: tuple[str, ...]) -> None:
        self._rows: dict[tuple, dict] = {}
        self._key = natural_key_fields

    def _key_of(self, row: dict) -> tuple:
        return tuple(row[k] for k in self._key)

    def __call__(self, row: dict, tx: str) -> tuple[int, dict | None]:
        k = self._key_of(row)
        if tx == "A":
            self._rows[k] = dict(row)
        elif tx == "C":
            # Real UPSERT path â€” overwrite.
            self._rows[k] = dict(row)
        elif tx == "D":
            self._rows.pop(k, None)
        return len(self._rows), dict(self._rows[k]) if k in self._rows else None


class _BrokenUpsertStore(_InMemoryUpsertStore):
    """Simulates the regression A4 guards against: ON CONFLICT DO NOTHING."""

    def __call__(self, row: dict, tx: str) -> tuple[int, dict | None]:
        k = self._key_of(row)
        if tx == "A":
            self._rows.setdefault(k, dict(row))  # NOTHING on conflict
        elif tx == "C":
            self._rows.setdefault(k, dict(row))  # BUG: C is silently dropped
        elif tx == "D":
            self._rows.pop(k, None)
        return len(self._rows), dict(self._rows[k]) if k in self._rows else None


def test_delta_semantics_upsert_by_natural_key_passes_correct_impl() -> None:
    spec = TableSpec(
        table_name="RFOO",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )
    sim = _InMemoryUpsertStore(natural_key_fields=("id",))
    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 42},
        initial_row={"name": "alpha"},
        changed_values={"name": "BETA"},
        simulator=sim,
    )


def test_delta_semantics_upsert_FAILS_on_silent_conflict_do_nothing() -> None:
    """A4 regression detector: C step is silently swallowed â†’ contract FAILS."""
    spec = TableSpec(
        table_name="RFOO",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )
    sim = _BrokenUpsertStore(natural_key_fields=("id",))
    with pytest.raises(AssertionError, match="did not propagate changed_values"):
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key={"id": 42},
            initial_row={"name": "alpha"},
            changed_values={"name": "BETA"},
            simulator=sim,
        )


def test_delta_semantics_unknown_is_skipped() -> None:
    """UNKNOWN preserves Phase 09 behavior â€” no contract."""
    spec = TableSpec(
        table_name="RFOO",
        columns=("id",),
        coercers={"id": int},
        delta_semantics=DeltaSemantics.UNKNOWN,
    )

    def _should_not_be_called(row, tx):  # pragma: no cover
        raise AssertionError("UNKNOWN delta_semantics should skip simulation")

    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 1},
        initial_row={},
        changed_values={},
        simulator=_should_not_be_called,
    )


def test_delta_semantics_append_only_expects_history_growth() -> None:
    spec = TableSpec(
        table_name="RNP3_NDC_PRICE",
        columns=("ndc_11", "price"),
        coercers={"ndc_11": str, "price": Decimal},
        delta_semantics=DeltaSemantics.APPEND_ONLY,
    )

    rows: list[dict] = []

    def append_sim(row: dict, tx: str) -> tuple[int, dict | None]:
        rows.append({**row, "_tx": tx})
        return len(rows), rows[-1]

    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"ndc_11": "00000000001"},
        initial_row={"price": Decimal("1.00")},
        changed_values={"price": Decimal("2.00")},
        simulator=append_sim,
    )
    assert len(rows) == 4  # A + C + D + re-A all appended


def test_delta_semantics_effective_date_expects_two_rows_after_C() -> None:
    spec = TableSpec(
        table_name="RFOO_EFFDATED",
        columns=("id", "value", "eff_date"),
        coercers={"id": int, "value": str, "eff_date": str},
        delta_semantics=DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
    )

    rows: list[dict] = []

    def eff_sim(row: dict, tx: str) -> tuple[int, dict | None]:
        if tx in {"A", "C"}:
            rows.append(dict(row))
        elif tx == "D":
            pass  # caller-defined; ignored here
        return len(rows), rows[-1] if rows else None

    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 1},
        initial_row={"value": "old", "eff_date": "20260101"},
        changed_values={"value": "new", "eff_date": "20260501"},
        simulator=eff_sim,
    )
    assert len(rows) >= 2


 succeeded in 421ms:
"""B9.A C8 â€” Tests for the SQLite-backed DELTA_SEMANTICS simulator.

Combines C3's abstract A/C/D/re-A driver with C8's concrete SQLite
INSERT/UPSERT/DELETE simulator. These tests prove the SAME contract
the per-tier integration tests will rely on:

  * UPSERT_BY_NATURAL_KEY with `DO UPDATE`     â†’ PASS
  * UPSERT_BY_NATURAL_KEY with `DO NOTHING`    â†’ FAIL loudly (A4)
  * APPEND_ONLY history table                  â†’ PASS (row count grows)
  * UPSERT_WITH_EFFECTIVE_DATE                 â†’ PASS
  * UNKNOWN / TRUNCATE_RELOAD                  â†’ skipped per template
"""
from __future__ import annotations

import pytest
from sqlalchemy import Engine, create_engine

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)
# See test_fdb_contract.py â€” same `tests` package-name collision fix.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _fdb_contract import assert_delta_semantics_acd_cycle  # noqa: E402
from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402


@pytest.fixture
def sqlite_engine() -> Engine:
    """Fresh in-memory SQLite per test â€” no cross-test bleed."""
    engine = create_engine("sqlite:///:memory:", future=True)
    return engine


# ---------------------------------------------------------------------------
# UPSERT_BY_NATURAL_KEY â€” correct INSERT...ON CONFLICT DO UPDATE
# ---------------------------------------------------------------------------


def test_upsert_by_natural_key_passes_with_real_sqlite_upsert(
    sqlite_engine: Engine,
) -> None:
    spec = TableSpec(
        table_name="upsert_ok",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        tier=Tier.A,
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )
    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name="upsert_ok",
        natural_key_columns=("id",),
        all_columns=("id", "name"),
        conflict_action="upsert",
    )
    try:
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key={"id": 1},
            initial_row={"name": "alpha"},
            changed_values={"name": "BETA"},
            simulator=sim,
        )
    finally:
        teardown()


def test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing(
    sqlite_engine: Engine,
) -> None:
    """A4 regression detector: ON CONFLICT DO NOTHING silently drops C.

    This is the WHOLE POINT of the C3+C8 contract. The test asserts
    that wiring a TableSpec marked UPSERT_BY_NATURAL_KEY through a
    DO NOTHING implementation fails the contract â€” proving the
    contract catches the bug it was designed to catch.
    """
    spec = TableSpec(
        table_name="upsert_broken",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        tier=Tier.A,
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )
    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name="upsert_broken",
        natural_key_columns=("id",),
        all_columns=("id", "name"),
        conflict_action="nothing",  # â† the regression
    )
    try:
        with pytest.raises(AssertionError, match="did not propagate changed_values"):
            assert_delta_semantics_acd_cycle(
                spec,
                natural_key={"id": 1},
                initial_row={"name": "alpha"},
                changed_values={"name": "BETA"},
                simulator=sim,
            )
    finally:
        teardown()


# ---------------------------------------------------------------------------
# APPEND_ONLY â€” every operation appends a row (no conflict resolution)
# ---------------------------------------------------------------------------


def test_append_only_passes_when_every_tx_grows_history(
    sqlite_engine: Engine,
) -> None:
    spec = TableSpec(
        table_name="history_table",
        columns=("entity_id", "value"),
        coercers={"entity_id": int, "value": str},
        tier=Tier.A,
        delta_semantics=DeltaSemantics.APPEND_ONLY,
    )
    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name="history_table",
        natural_key_columns=("entity_id",),
        all_columns=("entity_id", "value"),
        append_only=True,
    )
    try:
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key={"entity_id": 99},
            initial_row={"value": "v1"},
            changed_values={"value": "v2"},
            simulator=sim,
        )
    finally:
        teardown()


# ---------------------------------------------------------------------------
# UPSERT_WITH_EFFECTIVE_DATE â€” 2+ rows after C (closed-then-new)
# ---------------------------------------------------------------------------


def test_upsert_with_effective_date_passes_when_c_opens_new_row(
    sqlite_engine: Engine,
) -> None:
    spec = TableSpec(
        table_name="eff_dated",
        columns=("id", "value", "eff_date"),
        coercers={"id": int, "value": str, "eff_date": str},
        tier=Tier.A,
        delta_semantics=DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
    )
    # Effective-dated tables use (id, eff_date) as the conflict target
    # â€” two rows with the same `id` but different `eff_date` coexist.
    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name="eff_dated",
        natural_key_columns=("id", "eff_date"),
        all_columns=("id", "value", "eff_date"),
        conflict_action="upsert",
    )
    try:
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key={"id": 1, "eff_date": "20260101"},  # bound to step A's row
            initial_row={"value": "old"},
            # C carries a NEW eff_date â€” natural key shifts, new row appears.
            changed_values={"value": "new", "eff_date": "20260501"},
            simulator=sim,
        )
    finally:
        teardown()


# ---------------------------------------------------------------------------
# UNKNOWN / TRUNCATE_RELOAD â€” both skipped per template contract
# ---------------------------------------------------------------------------


def test_unknown_semantics_skips_simulation(sqlite_engine: Engine) -> None:
    spec = TableSpec(
        table_name="phase09_compat",
        columns=("id",),
        coercers={"id": int},
        delta_semantics=DeltaSemantics.UNKNOWN,
    )

    def explosive_simulator(row, tx):  # pragma: no cover
        raise AssertionError(
            "UNKNOWN delta_semantics simulator must not be invoked"
        )

    # No teardown needed â€” the simulator factory isn't called.
    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 1},
        initial_row={},
        changed_values={},
        simulator=explosive_simulator,
    )


def test_truncate_reload_semantics_skips_simulation(sqlite_engine: Engine) -> None:
    spec = TableSpec(
        table_name="bulk_reload",
        columns=("id",),
        coercers={"id": int},
        delta_semantics=DeltaSemantics.TRUNCATE_RELOAD,
    )

    def explosive_simulator(row, tx):  # pragma: no cover
        raise AssertionError(
            "TRUNCATE_RELOAD delta_semantics simulator must not be invoked "
            "(reload contract is tested by a dedicated integration test)"
        )

    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 1},
        initial_row={},
        changed_values={},
        simulator=explosive_simulator,
    )


# ---------------------------------------------------------------------------
# make_sqlite_simulator â€” input validation
# ---------------------------------------------------------------------------


def test_simulator_rejects_append_only_with_explicit_conflict_action(
    sqlite_engine: Engine,
) -> None:
    """Operator can't claim append_only + a conflict_action â€” surface the contradiction."""
    with pytest.raises(ValueError, match="mutually exclusive"):
        make_sqlite_simulator(
            sqlite_engine,
            table_name="bad",
            natural_key_columns=("id",),
            all_columns=("id",),
            append_only=True,
            conflict_action="nothing",
        )


def test_simulator_rejects_unknown_conflict_action(sqlite_engine: Engine) -> None:
    with pytest.raises(ValueError, match="conflict_action must be"):
        make_sqlite_simulator(
            sqlite_engine,
            table_name="bad",
            natural_key_columns=("id",),
            all_columns=("id",),
            conflict_action="weird",
        )


2026-05-12T04:47:22.832628Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'modules/drug-database/drug_database/services/fdb_adapter.py' -Pattern 'class TableSpec|tier|loader_group|delta_semantics|TABLE_SPECS|RNP3|SPEC' -Context 2,4"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'modules/drug-database/drug_database/services/fdb_adapter.py' -Pattern 'class TableSpec|tier|loader_group|delta_semantics|TABLE_SPECS|RNP3|SPEC' -Context 2,4" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'modules/drug-database/tests/unit/test_fdb_loader_registry.py' -Pattern 'test_filter_only_groups_mtl_still_denied|Tier.D|loader_group|test_mtl|DEFAULT|_ALL_SPECS' -Context 2,5" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl' -Pattern 'Substitution placeholders|APP_ROLES|APP_ROLES_QUOTED|Usage' -Context 2,4" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'modules/drug-database/drug_database/services/fdb_adapter.py' -Pattern 'class TableSpec|tier|loader_group|delta_semantics|TABLE_SPECS|RNP3|SPEC' -Context 2,4"` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'modules/drug-database/tests/unit/test_fdb_loader_registry.py' -Pattern 'test_filter_only_groups_mtl_still_denied|Tier.D|loader_group|test_mtl|DEFAULT|_ALL_SPECS' -Context 2,5"` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl' -Pattern 'Substitution placeholders|APP_ROLES|APP_ROLES_QUOTED|Usage' -Context 2,4"` rejected: blocked by policy
2026-05-12T04:47:22.833374Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'modules/drug-database/tests/unit/test_fdb_loader_registry.py' -Pattern 'test_filter_only_groups_mtl_still_denied|Tier.D|loader_group|test_mtl|DEFAULT|_ALL_SPECS' -Context 2,5"` rejected: blocked by policy
2026-05-12T04:47:22.834332Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl' -Pattern 'Substitution placeholders|APP_ROLES|APP_ROLES_QUOTED|Usage' -Context 2,4"` rejected: blocked by policy
2026-05-12T04:47:22.951459Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'infrastructure/scripts/preflight_b9_name_collision.py' -Pattern '_OWNED_SCHEMAS|_HARD_COLLISION_SCHEMAS|Unknown schema' -Context 0,14"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'infrastructure/scripts/preflight_b9_name_collision.py' -Pattern '_OWNED_SCHEMAS|_HARD_COLLISION_SCHEMAS|Unknown schema' -Context 0,14" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'infrastructure/scripts/preflight_b9_name_collision.py' -Pattern '_OWNED_SCHEMAS|_HARD_COLLISION_SCHEMAS|Unknown schema' -Context 0,14"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -C 3 "class TableSpec|tier|loader_group|delta_semantics|TABLE_SPECS|RNP3|SPEC" "modules/drug-database/drug_database/services/fdb_adapter.py"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n -C 3 \"test_filter_only_groups_mtl_still_denied|Tier\\.D|loader_group|test_mtl|DEFAULT|_ALL_SPECS\" \"modules/drug-database/tests/unit/test_fdb_loader_registry.py\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -C 3 "Substitution placeholders|APP_ROLES|APP_ROLES_QUOTED|Usage" "infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -C 6 "_OWNED_SCHEMAS|_HARD_COLLISION_SCHEMAS|Unknown schema" "infrastructure/scripts/preflight_b9_name_collision.py"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 391ms:
3-Phase 8 / Phase 09 implementation. Replaces the prior 5-method stub
4-interface (`fetch_feed`/`parse_feed`/`parse_pricing`/`parse_interactions`/
5-`parse_dosing`) with a generic `TableSpec`-driven surface — codex MF5
6:fix per SPEC §3.7.2 (`data/reference/fdb/README.md`, locked at codex
7-GO commit `9aa576b`).
8-
9-New shape:
--
19-  FDBLocalDropAdapter: file-system concrete adapter for operator-
20-  managed drops at `data/reference/fdb/TEL251759D/`.
21-
22:  Four TableSpec values for Phase 8: RNP3_NDC_PRICE (+ _UPD variant),
23-  RPRDPTD0_PRICE_TYPE_DESC, RNPTYPD0_NDC_PRICE_TYPE_DESC.
24-
25:  parse_rnp3() typed wrapper for the hot-path RNP3 caller (15.6M rows
26-  weekly) — preserves IDE autocomplete + type-checker support at the
27-  ingester's main loop.
28-
29:Why generic surface, not per-table abstractmethods (SPEC §3.7.2.2):
30-  * New tables become data (TableSpec values), not interface methods.
31-  * Single `test_parse_table_*` suite covers all tables.
32-  * Two-method MagicMock for tests vs. six-method.
--
36-  * LESSON-004 — date regex uses `re.fullmatch(r"\\A\\d{8}\\Z", ...)`.
37-  * LESSON-005 — log keys prefixed `ingest_*`.
38-  * financial-precision.md — Decimal coercer; never float.
39:  * surgical-changes.md — TableSpec values only as SPEC §3.7.2 lists
40-    them. Additional hardening helpers (`_str11` / `_decimal_16_5` /
41-    etc.) deferred until a downstream unit needs them.
42-"""
--
86-
87-    LESSON-004: `re.fullmatch` with `\\A\\d{8}\\Z` rejects trailing
88-    newlines and partial matches. Used as the canonical `effective_date`
89:    coercer for RNP3 + RPRDPP0 TableSpecs.
90-    """
91-    if not _FDB_DATE_RE.fullmatch(raw):
92-        raise ValueError(f"FDB date '{raw}' is not 8-digit YYYYMMDD")
--
143-
144-
145-class Tier(Enum):
146:    """B9 effort-classification tier per `recon.md` §3.
147-
148:    Phase 09 used a single tier implicitly (the 3 pricing-related
149-    TableSpecs were all hand-curated). B9 extends to 217 more tables
150-    classified by complexity:
151-
--
155-      D — MTL (medical test lexicon), schema-only, no data load (19 tables)
156-
157-    UNKNOWN is the backward-compat default for Phase 09 TableSpecs
158:    that pre-date the tier field. They behave as before.
159-    """
160-
161-    A = "A"
--
175-
176-    Per-table classification:
177-
178:      APPEND_ONLY                — immutable insert (pricing history; RNP3)
179-      UPSERT_BY_NATURAL_KEY      — most reference tables; ON CONFLICT DO UPDATE
180-      UPSERT_WITH_EFFECTIVE_DATE — time-bucketed; new row per (key, eff_date)
181-      TRUNCATE_RELOAD            — tables w/o stable natural key, full reload
--
193-
194-
195-@dataclass(frozen=True)
196:class TableSpec:
197-    """Schema + parse rules for one FDB table.
198-
199-    Drives `FDBAdapter.parse_table`. New tables in Phase C / Phase D
200-    become new TableSpec values — no FDBAdapter method needed for
201:    each one (SPEC §3.7.2.2).
202-
203-    Fields:
204-      table_name: filename inside the zip (no extension); equals the
205:                  literal FDB table name (e.g. ``RNP3_NDC_PRICE``).
206-      columns:    column order — must match the DDL byte-for-byte.
207-      coercers:   raw_str → typed value, per column. Coercer raising
208-                  ValueError / InvalidOperation / InvalidNDCError causes
--
210-      nullable:   columns where empty string → None (bypasses coercer).
211-      sentinel_filter: row filter applied AFTER coercion. Rows where
212-                  the predicate returns True are SKIPPED.
213:                  E.g. RNP3 PRICE_TYPE='14' (NOPRC).
214-      has_transaction_code: True for UPD-shape files where each row is
215-                  prefixed with A/C/D + delimiter. parse_table extracts
216-                  the prefix into ``transaction_code``.
--
218-
219-    B9 extension fields (additive; backward-compat defaults — Phase 09
220-    TableSpecs unchanged):
221:      tier:               effort-classification per `recon.md` §3.
222-      record_counts_key:  key for row-count reconciliation against
223-                          FDB's `RECORD_COUNTS.TXT` manifest.
224-                          Defaults to `table_name` if None.
225:      loader_group:       tier-loader registration label
226:                          (e.g., "fdb_tier_a" — loaders register by group).
227:                          Defaults to None (single-tier Phase 09 behavior).
228:      delta_semantics:    how weekly delta is applied — per codex
229-                          ADVERSARIAL A4 mitigation. UNKNOWN preserves
230-                          Phase 09 behavior (treated as APPEND_ONLY
231-                          downstream for backward-compat).
--
238-    sentinel_filter: Callable[[dict[str, Any]], bool] | None = None
239-    has_transaction_code: bool = False
240-    # B9 additive fields — defaults preserve Phase 09 behavior
241:    tier: Tier = Tier.UNKNOWN
242-    record_counts_key: str | None = None
243:    loader_group: str | None = None
244:    delta_semantics: DeltaSemantics = DeltaSemantics.UNKNOWN
245-
246-
247-# ---------------------------------------------------------------------------
--
278-        """Stream raw bytes for a single table file inside the chosen zip.
279-
280-        ``source`` ∈ {"DB", "UPD"} — picks which zip to open. Streaming
281:        generator — never materializes the full file in memory (RNP3
282-        is 673 MB uncompressed).
283-        """
284-
--
324-) -> Iterator[list[str]]:
325-    """Stream one row at a time from a table inside an FDB zip.
326-
327:    Verified format (SPEC §2.2):
328-      * pipe (|) delimiter
329-      * latin-1 encoding (Windows-1252 superset)
330-      * CRLF (\\r\\n) line terminator
--
335-    via TableSpec.coercers in `parse_table`.
336-
337-    Memory budget: peak is bounded by ``chunk_bytes`` + one row buffer.
338:    Default 2 MB chunk handles RNP3's 673 MB uncompressed body without
339-    materializing the file.
340-    """
341-    with zipfile.ZipFile(zip_path) as z:
--
528-                )
529-                continue
530-
531:            # Sentinel filter (e.g. RNP3 PRICE_TYPE='14' NOPRC).
532-            if spec.sentinel_filter and spec.sentinel_filter(row):
533-                rows_skipped_filter += 1
534-                continue
--
550-
551-
552-# ---------------------------------------------------------------------------
553:# Phase 8 TableSpec values (SPEC §3.7.2)
554-# ---------------------------------------------------------------------------
555-
556-
557:RNP3_NDC_PRICE = TableSpec(
558:    table_name="RNP3_NDC_PRICE",
559-    columns=("ndc", "price_type", "effective_date_raw", "price_raw"),
560-    coercers={
561-        "ndc": normalize_ndc,                  # → 11-digit normalized NDC
--
567-    has_transaction_code=False,                # DB.zip
568-)
569-
570:RNP3_NDC_PRICE_UPD = replace(RNP3_NDC_PRICE, has_transaction_code=True)
571-
572-
573-RPRDPTD0_PRICE_TYPE_DESC = TableSpec(
--
600-
601-
602-# ---------------------------------------------------------------------------
603:# Hot-path typed wrapper (SPEC §3.7.2.1)
604-# ---------------------------------------------------------------------------
605-
606-
607:class _RNP3Row(TypedDict):
608:    """Typed row shape for RNP3_NDC_PRICE consumers (hot path).
609-
610-    Field renames vs. raw TableSpec output:
611-      ndc → ndc_11   (matches schema column name)
--
627-    drop: FDBDrop,
628-    *,
629-    source: str = "DB",
630:) -> Iterator[_RNP3Row]:
631:    """Hot-path RNP3 wrapper — typed return for the ingester's main loop.
632-
633-    For all other tables, callers use ``adapter.parse_table(drop, spec)``
634-    directly and treat the returned dicts as ``Mapping[str, Any]``.
635-    """
636:    spec = RNP3_NDC_PRICE_UPD if source == "UPD" else RNP3_NDC_PRICE
637-    for row in adapter.parse_table(drop, spec, source=source):
638:        yield _RNP3Row(
639-            ndc_11=row["ndc"],
640-            price_type=row["price_type"],
641-            effective_date=row["effective_date_raw"],
--
651-    "FDBDrop",
652-    "FDBDropError",
653-    "FDBLocalDropAdapter",
654:    "RNP3_NDC_PRICE",
655:    "RNP3_NDC_PRICE_UPD",
656-    "RNPTYPD0_NDC_PRICE_TYPE_DESC",
657-    "RPRDPTD0_PRICE_TYPE_DESC",
658-    "TableSpec",

 succeeded in 389ms:
5-  1. The settings flag `FDB_LOAD_MTL` defaults to False. Flipping it
6-     to True is a deliberate operator action (future activation wave).
7-
8:  2. The `filter_loadable_specs` helper excludes `loader_group="fdb_mtl"`
9-     specs when `fdb_load_mtl=False`, regardless of any `only_groups`
10-     override. The flag is the gate; group selection is sub-filtering.
11-
12-  3. `test_fdb_mtl_zero_loadable_under_default_flag` is the trivially-
13-     true assertion that stays present from B9.A through B9.G — it
14-     fails the moment someone accidentally registers an MTL spec WITHOUT
15:     `loader_group="fdb_mtl"`, or flips the default flag to True.
16-
17-The DB-level REVOKE template at
18-`infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` is the
--
45-    columns=("ndc_11",),
46-    coercers={"ndc_11": str},
47-    delta_semantics=DeltaSemantics.APPEND_ONLY,
48:    # loader_group=None — Phase 09 backward-compat
49-)
50-
51-_TIER_A_SPEC = TableSpec(
--
53-    columns=("med_name_id",),
54-    coercers={"med_name_id": int},
55-    tier=Tier.A,
56:    loader_group="fdb_tier_a",
57-)
58-
59-_TIER_B_SPEC = TableSpec(
--
61-    columns=("ndc_9",),
62-    coercers={"ndc_9": str},
63-    tier=Tier.B,
64:    loader_group="fdb_tier_b",
65-)
66-
67-_TIER_C_SPEC = TableSpec(
--
69-    columns=("ndc_14",),
70-    coercers={"ndc_14": str},
71-    tier=Tier.C,
72:    loader_group="fdb_tier_c",
73-)
74-
75-_MTL_SPEC = TableSpec(
76-    table_name="MTL_TEST_LEX_MASTER",
77-    columns=("test_id",),
78-    coercers={"test_id": int},
79:    tier=Tier.D,
80:    loader_group=MTL_LOADER_GROUP,
81-)
82-
83:_ALL_SPECS = [
84-    _PHASE_09_SPEC,
85-    _TIER_A_SPEC,
86-    _TIER_B_SPEC,
--
126-
127-def test_filter_excludes_mtl_under_default_flag() -> None:
128-    """fdb_load_mtl=False → MTL specs are dropped."""
129:    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=False)
130-    table_names = [s.table_name for s in out]
131-    assert "MTL_TEST_LEX_MASTER" not in table_names
132-    assert "RNP3_NDC_PRICE" in table_names  # Phase 09 untouched
--
134-
135-
136-def test_filter_includes_mtl_when_flag_true() -> None:
137:    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=True)
138-    assert len(out) == 5
139-    assert any(s.table_name == "MTL_TEST_LEX_MASTER" for s in out)
140-
141-
142-def test_filter_preserves_input_order() -> None:
143:    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=True)
144-    assert [s.table_name for s in out] == [
145-        "RNP3_NDC_PRICE",
146-        "RMIID1_MED",
--
153-def test_filter_only_groups_restricts_to_requested_groups() -> None:
154-    """only_groups=['fdb_tier_a'] → only Tier A specs returned."""
155-    out = filter_loadable_specs(
156:        _ALL_SPECS, fdb_load_mtl=False, only_groups=["fdb_tier_a"]
157-    )
158-    assert len(out) == 1
159-    assert out[0].table_name == "RMIID1_MED"
160-
161-
162:def test_filter_only_groups_mtl_still_denied_under_default_flag() -> None:
163-    """Even an explicit only_groups=['fdb_mtl'] is denied if the flag is False.
164-
165-    This is the load-bearing assertion — the flag is the GATE; group
--
167-    ['fdb_mtl']` from a CLI typo, the flag still says no.
168-    """
169-    out = filter_loadable_specs(
170:        _ALL_SPECS, fdb_load_mtl=False, only_groups=[MTL_LOADER_GROUP]
171-    )
172-    assert out == []
173-
174-
175-def test_filter_only_groups_mtl_allowed_when_flag_true() -> None:
176-    out = filter_loadable_specs(
177:        _ALL_SPECS, fdb_load_mtl=True, only_groups=[MTL_LOADER_GROUP]
178-    )
179-    assert len(out) == 1
180-    assert out[0].table_name == "MTL_TEST_LEX_MASTER"
181-
182-
183-def test_filter_phase_09_specs_unaffected_by_flag() -> None:
184:    """loader_group=None specs always load (Phase 09 backward-compat)."""
185-    for flag in (True, False):
186-        out = filter_loadable_specs([_PHASE_09_SPEC], fdb_load_mtl=flag)
187-        assert out == [_PHASE_09_SPEC]
--
196-# ---------------------------------------------------------------------------
197-
198-
199:def test_mtl_specs_returns_only_mtl() -> None:
200:    out = mtl_specs(_ALL_SPECS)
201-    assert len(out) == 1
202-    assert out[0].table_name == "MTL_TEST_LEX_MASTER"
203-
204-
205:def test_mtl_specs_empty_when_no_mtl() -> None:
206-    """Mirrors B9.A reality: no MTL specs registered yet → empty."""
207-    assert mtl_specs([_PHASE_09_SPEC, _TIER_A_SPEC]) == []
208-
--
217-
218-    B9.A: trivially true (no MTL specs exist yet).
219-    B9.B-F: still trivially true (no MTL specs registered).
220:    B9.G: now load-bearing (19 MTL specs registered with loader_group=
221-          "fdb_mtl"; flag default False excludes them all).
222-    Future activation wave: this test is RELAXED in tandem with the
223-          flag flip — it does not change semantics, the registered
--
226-    The assertion holds at every gate by construction: the registry
227-    helper filters before any load. The test is here to catch the
228-    regression where a future PR adds an MTL spec WITHOUT the
229:    `loader_group="fdb_mtl"` label (which would silently bypass the
230-    flag and load on default).
231-    """
232:    # Use the full _ALL_SPECS to simulate what the real catalog will
233-    # eventually look like. The assertion: every spec whose tier is
234:    # Tier.D must have loader_group=MTL_LOADER_GROUP, AND under default
235-    # flag none of them appear in the filter output.
236:    tier_d_specs = [s for s in _ALL_SPECS if s.tier == Tier.D]
237-    for spec in tier_d_specs:
238:        assert spec.loader_group == MTL_LOADER_GROUP, (
239-            f"{spec.table_name}: Tier D specs MUST set "
240:            f"loader_group='fdb_mtl' or they bypass the MTL guard."
241-        )
242-
243:    default_load = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=False)
244:    assert not any(s.tier == Tier.D for s in default_load), (
245-        "Tier D / MTL specs appeared in the default load — MTL guard FAILED. "
246-        "Either FDB_LOAD_MTL default flipped to True (forbidden without an "
247:        "activation wave) or loader_group label is missing on a Tier D spec."
248-    )
249-
250-

 succeeded in 386ms:
102-# ---------------------------------------------------------------------------
103-
104-
105-# Schemas that are EXPECTED to contain B9-named tables after the
106-# migration runs. Pre-existing tables here are reported but operator
107-# may sign them off if they came from a prior B9 partial run.
108:_OWNED_SCHEMAS = frozenset({"drug_database"})
109-
110-# Schemas that should NEVER contain B9-named tables. Any pre-existing
111-# match here is an immediate hard collision.
112:_HARD_COLLISION_SCHEMAS = frozenset({
113-    "reference",  # FDW-fronted; conflicts produce silent wrong-data
114-    "shared",
115-    "public",
116-    "drug_db",   # legacy schema name still present per Phase 11A
117-    "pharmacy_dir",
118-    "prescriber_dir",
--
136-    hard: list[tuple[str, str]] = []
137-    soft: list[tuple[str, str]] = []
138-
139-    for schema, name in existing:
140-        if name not in expected_set:
141-            continue
142:        if schema in _HARD_COLLISION_SCHEMAS:
143-            hard.append((schema, name))
144:        elif schema in _OWNED_SCHEMAS:
145-            soft.append((schema, name))
146-        else:
147:            # Unknown schema — treat as hard. Better a false alarm than
148-            # a silent collision in a schema we forgot to classify.
149-            hard.append((schema, name))
150-
151-    # Stable ordering for evidence reproducibility
152-    return sorted(hard), sorted(soft)
153-

 succeeded in 395ms:
16--- concrete migration body from this template, substituting the
17--- per-tier MTL table list captured by `fdb_loader_registry.mtl_specs(...)`.
18---
19:-- Substitution placeholders (replace before applying):
20---   {{SCHEMA}}      → typically "drug_database"
21---   {{MTL_TABLES}}  → comma-separated table list, e.g.
22---                     mtl_test_lex_master, mtl_test_lex_xref
23:--   {{APP_ROLES}}   → ifx_dev_app, ifx_mock_app, IFX_APP_ROLE-from-env
24---                     (B7.3 env-driven pattern — see migrations under
25---                      modules/*/alembic/versions/)
26---
27:-- Usage from a B9.G alembic migration:
28---   op.execute(text(
29---       Path("infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl")
30---         .read_text(encoding="utf-8")
31---         .replace("{{SCHEMA}}", "drug_database")
32---         .replace("{{MTL_TABLES}}", ", ".join(mtl_table_names))
33:--         .replace("{{APP_ROLES}}", ", ".join(_APP_ROLES))
34---   ))
35---
36--- Idempotent: re-running this script produces no error (REVOKE on
--
41--- 1) Revoke writes on the MTL tables themselves
42-REVOKE INSERT, UPDATE, DELETE
43-    ON {{SCHEMA}}.{{MTL_TABLES}}
44:    FROM {{APP_ROLES}};
45-
46--- 2) Revoke USAGE on any per-table sequences (defense in depth — even
47---    if a row INSERT slipped past somehow, the sequence advance would
--
60-          AND c.relname LIKE 'mtl_%'
61-    LOOP
62-        EXECUTE format(
63:            'REVOKE USAGE, SELECT, UPDATE ON SEQUENCE {{SCHEMA}}.%I FROM {{APP_ROLES}}',
64-            seq_name
65-        );
66-    END LOOP;
--
77-    WHERE table_schema = '{{SCHEMA}}'
78-      AND table_name LIKE 'mtl_%'
79-      AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE')
80:      AND grantee IN ({{APP_ROLES_QUOTED}});
81-
82-    IF bad_count > 0 THEN
83-        RAISE EXCEPTION

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'shared/tests/db/test_setup_fdw_manifest.py' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'shared/tests/db/test_preflight_b9_name_collision.py' -Raw" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "fdb_mtl_revoke|APP_ROLES_QUOTED|MTL_TABLES|REVOKE INSERT" modules shared infrastructure tests waves -S' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "parse_warning_allowlist|write_path_enforcement|phase09_compat_baseline|module_base_profile|status.md|Charter / SC mapping" . -S' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 409ms:
"""B9.A C10 â€” Tests for the FDW name-collision preflight.

Covers the pure functions (no Postgres dependency) by injecting a
fake `table_lister`. The Postgres-backed lister is exercised in
B9.B integration when a live reference DB is available.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make `preflight_b9_name_collision.py` importable without packaging
# `infrastructure/scripts/` as a Python package.
_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[3] / "infrastructure" / "scripts"
)
sys.path.insert(0, str(_SCRIPTS_DIR))

from preflight_b9_name_collision import (  # noqa: E402
    fdb_name_to_table_name,
    format_evidence,
    load_expected_names,
    scan_for_collisions,
)


# ---------------------------------------------------------------------------
# fdb_name_to_table_name
# ---------------------------------------------------------------------------


def test_fdb_name_is_lowercased() -> None:
    assert fdb_name_to_table_name("RNP3_NDC_PRICE") == "rnp3_ndc_price"


def test_fdb_name_underscores_preserved() -> None:
    assert fdb_name_to_table_name("RPRDPTD0_PRICE_TYPE_DESC") == "rprdptd0_price_type_desc"


def test_fdb_name_whitespace_stripped() -> None:
    assert fdb_name_to_table_name("  RNDC14_NDC_MSTR  \r\n") == "rndc14_ndc_mstr"


# ---------------------------------------------------------------------------
# load_expected_names
# ---------------------------------------------------------------------------


def test_load_expected_names_parses_record_counts(tmp_path: Path) -> None:
    rc = tmp_path / "RECORD_COUNTS.TXT"
    rc.write_text(
        "# header\n"
        "RFOO=10\n"
        "RBAR=20\n"
        "\n"
        "RNP3_NDC_PRICE=15000000\n",
        encoding="latin-1",
    )
    names = load_expected_names(rc)
    assert names == ["rfoo", "rbar", "rnp3_ndc_price"]


def test_load_expected_names_dedupes_repeats(tmp_path: Path) -> None:
    """Same key on two lines â†’ one entry in the output."""
    rc = tmp_path / "RECORD_COUNTS.TXT"
    rc.write_text("RFOO=10\nRFOO=999\n", encoding="latin-1")
    assert load_expected_names(rc) == ["rfoo"]


def test_load_expected_names_skips_malformed_lines(tmp_path: Path) -> None:
    rc = tmp_path / "RECORD_COUNTS.TXT"
    rc.write_text(
        "RFOO=10\n"
        "this-line-has-no-equals-sign\n"
        "# comment\n"
        "RBAR=20\n",
        encoding="latin-1",
    )
    assert load_expected_names(rc) == ["rfoo", "rbar"]


# ---------------------------------------------------------------------------
# scan_for_collisions
# ---------------------------------------------------------------------------


def test_scan_returns_empty_when_no_collisions() -> None:
    expected = ["rfoo", "rbar"]
    lister = lambda: {("public", "users"), ("core", "tenants")}
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [] and soft == []


def test_scan_flags_hard_collision_in_reference_schema() -> None:
    expected = ["rfoo", "rbar"]
    lister = lambda: {
        ("reference", "rfoo"),     # â† hard
        ("public", "users"),       # unrelated
    }
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [("reference", "rfoo")]
    assert soft == []


def test_scan_flags_hard_collision_in_public_shared_drug_db() -> None:
    expected = ["rmiid1_med", "rndc14_ndc_mstr"]
    lister = lambda: {
        ("public", "rmiid1_med"),
        ("shared", "rndc14_ndc_mstr"),
        ("drug_db", "rmiid1_med"),
    }
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [
        ("drug_db", "rmiid1_med"),
        ("public", "rmiid1_med"),
        ("shared", "rndc14_ndc_mstr"),
    ]


def test_scan_flags_soft_collision_in_drug_database_schema() -> None:
    """drug_database is the OWNED schema â€” collisions there are soft."""
    expected = ["rnp3_ndc_price"]
    lister = lambda: {("drug_database", "rnp3_ndc_price")}
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == []
    assert soft == [("drug_database", "rnp3_ndc_price")]


def test_scan_unknown_schema_treated_as_hard() -> None:
    """Anything we forgot to classify is treated as hard â€” fail safe."""
    expected = ["rfoo"]
    lister = lambda: {("some_unclassified_schema", "rfoo")}
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [("some_unclassified_schema", "rfoo")]
    assert soft == []


def test_scan_ignores_tables_with_unmatched_names() -> None:
    """A table whose name isn't in expected_names is never a collision."""
    expected = ["rfoo"]
    lister = lambda: {
        ("reference", "rbar"),   # name not in expected
        ("public", "users"),
    }
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [] and soft == []


def test_scan_order_is_stable() -> None:
    """Evidence reproducibility â€” output sorted lexicographically."""
    expected = ["rfoo", "rbar", "rbaz"]
    lister = lambda: {
        ("public", "rfoo"),
        ("public", "rbaz"),
        ("reference", "rbar"),
    }
    hard, _soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [
        ("public", "rbaz"),
        ("public", "rfoo"),
        ("reference", "rbar"),
    ]


# ---------------------------------------------------------------------------
# format_evidence
# ---------------------------------------------------------------------------


def test_evidence_clean_state_documents_proceed() -> None:
    body = format_evidence(["rfoo", "rbar"], hard=[], soft=[])
    assert "Expected B9 table names: **2**" in body
    assert "Hard collisions:         **0**" in body
    assert "No collisions found" in body
    assert "B9.B clear to proceed" in body


def test_evidence_hard_section_appears_only_with_hard_collisions() -> None:
    body = format_evidence(
        ["rfoo"], hard=[("reference", "rfoo")], soft=[]
    )
    assert "## Hard collisions" in body
    assert "## Soft collisions" not in body
    assert "`reference`" in body
    assert "`rfoo`" in body


def test_evidence_soft_section_appears_only_with_soft_collisions() -> None:
    body = format_evidence(
        ["rnp3_ndc_price"], hard=[], soft=[("drug_database", "rnp3_ndc_price")]
    )
    assert "## Soft collisions" in body
    assert "## Hard collisions" not in body
    assert "alembic_version" in body


 succeeded in 410ms:
"""B9.A C11 â€” Tests for `setup_fdw.sh --verify` manifest invariants.

The bulk of `setup_fdw.sh` requires a live Postgres + FDW
configuration; those are integration tests. The pure manifest
invariants (file present, well-formed, count >= floor, lines parse
into schema|table tuples) are covered here without Postgres.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST = _REPO_ROOT / "infrastructure" / "scripts" / "lib" / "expected_reference_tables.txt"
_SETUP_FDW = _REPO_ROOT / "infrastructure" / "scripts" / "setup_fdw.sh"


def _parse_manifest_lines() -> list[tuple[str, str]]:
    """Same logic as the awk pass in setup_fdw.sh --verify."""
    out: list[tuple[str, str]] = []
    text = _MANIFEST.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.rstrip("\r").strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            continue
        # The manifest tolerates inline `# comment` after the table column
        # â€” strip it before splitting (some entries use `... # source`).
        # Match setup_fdw.sh treatment: take the FIRST `|`-split fields only.
        body = line.split("#", 1)[0].strip()
        if not body:
            continue
        parts = body.split("|", 1)
        if len(parts) != 2:
            continue
        schema, table = parts[0].strip(), parts[1].strip()
        if schema and table:
            out.append((schema, table))
    return out


# ---------------------------------------------------------------------------
# Manifest invariants (B9.A C11)
# ---------------------------------------------------------------------------


def test_manifest_file_exists() -> None:
    assert _MANIFEST.exists(), f"manifest missing at {_MANIFEST}"


def test_manifest_has_at_least_floor_entries() -> None:
    """B9.A C11 floor: 66 (B7 baseline). B9.B-G grows it; never shrinks."""
    entries = _parse_manifest_lines()
    assert len(entries) >= 66, (
        f"manifest has {len(entries)} entries; below B7 baseline floor of 66"
    )


def test_manifest_entries_have_schema_and_table() -> None:
    """Every line that survives the comment/blank filter is `schema|table`."""
    entries = _parse_manifest_lines()
    for schema, table in entries:
        assert schema and table, (
            f"empty schema or table in manifest: ({schema!r}, {table!r})"
        )


def test_manifest_schema_names_are_well_formed() -> None:
    """Schemas are lower-snake_case identifiers â€” no spaces, dots, hyphens."""
    pattern = re.compile(r"\A[a-z][a-z0-9_]*\Z")
    for schema, _table in _parse_manifest_lines():
        assert pattern.match(schema), (
            f"manifest schema {schema!r} is not a lower-snake_case identifier"
        )


def test_manifest_table_names_are_well_formed() -> None:
    """Tables follow the same naming rules."""
    pattern = re.compile(r"\A[a-z][a-z0-9_]*\Z")
    for _schema, table in _parse_manifest_lines():
        assert pattern.match(table), (
            f"manifest table {table!r} is not a lower-snake_case identifier"
        )


def test_manifest_has_no_duplicate_entries() -> None:
    """Duplicates would inflate the verify count and hide failures."""
    entries = _parse_manifest_lines()
    seen: set[tuple[str, str]] = set()
    dupes: list[tuple[str, str]] = []
    for entry in entries:
        if entry in seen:
            dupes.append(entry)
        seen.add(entry)
    assert not dupes, f"manifest contains duplicate entries: {dupes}"


# ---------------------------------------------------------------------------
# setup_fdw.sh invariants
# ---------------------------------------------------------------------------


def test_setup_fdw_no_hardcoded_expected_66_check() -> None:
    """C11 contract: the hard-coded `-ne 66` count assertion is gone."""
    body = _SETUP_FDW.read_text(encoding="utf-8")
    # Hard-coded equality check would look like: -ne 66
    # The C11 replacement uses -lt $MIN_MANIFEST_COUNT.
    assert "-ne 66" not in body, (
        "setup_fdw.sh still contains hard-coded `-ne 66` count assertion. "
        "Replace with MIN_MANIFEST_COUNT floor (C11)."
    )


def test_setup_fdw_uses_min_manifest_count_floor() -> None:
    """C11 contract: MIN_MANIFEST_COUNT variable is in use."""
    body = _SETUP_FDW.read_text(encoding="utf-8")
    assert "MIN_MANIFEST_COUNT=" in body
    assert "$MANIFEST_COUNT" in body and "MIN_MANIFEST_COUNT" in body


def test_setup_fdw_applies_deterministic_sort() -> None:
    """C11 contract: MANIFEST_SORTED is built and used as the iteration source."""
    body = _SETUP_FDW.read_text(encoding="utf-8")
    assert "MANIFEST_SORTED" in body
    # The sort pipeline appears once in the build step
    assert "| sort" in body
    # The iteration consumes the sorted view via heredoc, not the raw file
    assert '<<< "$MANIFEST_SORTED"' in body


 succeeded in 545ms:
infrastructure\scripts\lib\fdb_mtl_revoke.sql.tmpl:21:--   {{MTL_TABLES}}  → comma-separated table list, e.g.
infrastructure\scripts\lib\fdb_mtl_revoke.sql.tmpl:29:--       Path("infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl")
infrastructure\scripts\lib\fdb_mtl_revoke.sql.tmpl:32:--         .replace("{{MTL_TABLES}}", ", ".join(mtl_table_names))
infrastructure\scripts\lib\fdb_mtl_revoke.sql.tmpl:42:REVOKE INSERT, UPDATE, DELETE
infrastructure\scripts\lib\fdb_mtl_revoke.sql.tmpl:43:    ON {{SCHEMA}}.{{MTL_TABLES}}
infrastructure\scripts\lib\fdb_mtl_revoke.sql.tmpl:80:      AND grantee IN ({{APP_ROLES_QUOTED}});
infrastructure\scripts\lib\fdb_mtl_revoke.sql.tmpl:84:            'fdb_mtl_revoke: % residual write grants on mtl_* tables '
modules\drug-database\tests\unit\test_fdb_loader_registry.py:18:`infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` is the
modules\drug-database\tests\unit\test_fdb_loader_registry.py:255:    tmpl = repo_root / "infrastructure" / "scripts" / "lib" / "fdb_mtl_revoke.sql.tmpl"
modules\drug-database\tests\unit\test_fdb_loader_registry.py:259:    for placeholder in ("{{SCHEMA}}", "{{MTL_TABLES}}", "{{APP_ROLES}}"):
modules\drug-database\tests\unit\test_fdb_loader_registry.py:261:            f"{placeholder} missing from fdb_mtl_revoke.sql.tmpl — B9.G "
modules\drug-database\tests\unit\test_fdb_loader_registry.py:265:    assert "REVOKE INSERT, UPDATE, DELETE" in body
modules\drug-database\drug_database\services\fdb_loader_registry.py:15:(`infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` is the
shared\config.py:137:    #     infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl)

 succeeded in 1381ms:
.\shared\db\write_path_guard.py:3:Charter (and `waves/B9/write_path_enforcement.md`) require: every B9
.\modules\drug-database\tests\_fdb_contract.py:55:  allowlist at `Werkbench/projects/infinityrx-platform/waves/B9/parse_warning_allowlist.md`
.\modules\drug-database\tests\_fdb_contract.py:319:    `Werkbench/projects/infinityrx-platform/waves/B9/parse_warning_allowlist.md`
.\modules\drug-database\tests\unit\test_module_base_profile.py:6:`waves/B9/module_base_profile.md`.
.\modules\drug-database\tests\unit\test_module_base_profile.py:17:#     sees (per waves/B9/module_base_profile.md "Recommended pattern").
.\modules\drug-database\tests\unit\test_module_base_profile.py:34:        f"waves/B9/module_base_profile.md). If the increase is "
.\modules\drug-database\tests\integration\test_phase09_compat_baseline.py:3:LOCKED VALUES (see waves/B9/phase09_compat_baseline.md):
.\modules\drug-database\tests\integration\test_phase09_compat_baseline.py:25:# Hard-coded baseline numbers per waves/B9/phase09_compat_baseline.md.

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -Path 'modules/drug-database/tests/unit/test_fdb_loader_registry.py' -TotalCount 280" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 343ms:
"""B9.A C4 â€” Tests for the FDB loader registry + MTL guard.

These tests lock in two contracts:

  1. The settings flag `FDB_LOAD_MTL` defaults to False. Flipping it
     to True is a deliberate operator action (future activation wave).

  2. The `filter_loadable_specs` helper excludes `loader_group="fdb_mtl"`
     specs when `fdb_load_mtl=False`, regardless of any `only_groups`
     override. The flag is the gate; group selection is sub-filtering.

  3. `test_fdb_mtl_zero_loadable_under_default_flag` is the trivially-
     true assertion that stays present from B9.A through B9.G â€” it
     fails the moment someone accidentally registers an MTL spec WITHOUT
     `loader_group="fdb_mtl"`, or flips the default flag to True.

The DB-level REVOKE template at
`infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` is the
defense-in-depth backstop; it is not exercised here (B9.G's grant
migration test does that).
"""
from __future__ import annotations

import pytest

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)
from drug_database.services.fdb_loader_registry import (
    MTL_LOADER_GROUP,
    filter_loadable_specs,
    mtl_specs,
)


# ---------------------------------------------------------------------------
# Sample fixture specs covering all 4 tier groups
# ---------------------------------------------------------------------------


_PHASE_09_SPEC = TableSpec(
    table_name="RNP3_NDC_PRICE",
    columns=("ndc_11",),
    coercers={"ndc_11": str},
    delta_semantics=DeltaSemantics.APPEND_ONLY,
    # loader_group=None â€” Phase 09 backward-compat
)

_TIER_A_SPEC = TableSpec(
    table_name="RMIID1_MED",
    columns=("med_name_id",),
    coercers={"med_name_id": int},
    tier=Tier.A,
    loader_group="fdb_tier_a",
)

_TIER_B_SPEC = TableSpec(
    table_name="RNDC9_BAR",
    columns=("ndc_9",),
    coercers={"ndc_9": str},
    tier=Tier.B,
    loader_group="fdb_tier_b",
)

_TIER_C_SPEC = TableSpec(
    table_name="RNDC14_NDC_MSTR",
    columns=("ndc_14",),
    coercers={"ndc_14": str},
    tier=Tier.C,
    loader_group="fdb_tier_c",
)

_MTL_SPEC = TableSpec(
    table_name="MTL_TEST_LEX_MASTER",
    columns=("test_id",),
    coercers={"test_id": int},
    tier=Tier.D,
    loader_group=MTL_LOADER_GROUP,
)

_ALL_SPECS = [
    _PHASE_09_SPEC,
    _TIER_A_SPEC,
    _TIER_B_SPEC,
    _TIER_C_SPEC,
    _MTL_SPEC,
]


# ---------------------------------------------------------------------------
# Settings flag default
# ---------------------------------------------------------------------------


def test_fdb_load_mtl_setting_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """The settings flag defaults to False â€” opt-in only."""
    # Reset cache so we don't pick up a previously-loaded Settings.
    monkeypatch.delenv("FDB_LOAD_MTL", raising=False)
    from shared import config as cfg
    cfg.reset_settings_cache()
    settings = cfg.get_settings()
    assert settings.FDB_LOAD_MTL is False


def test_fdb_load_mtl_setting_accepts_explicit_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env var override â†’ True (smoke; activation wave flips this)."""
    monkeypatch.setenv("FDB_LOAD_MTL", "true")
    from shared import config as cfg
    cfg.reset_settings_cache()
    try:
        settings = cfg.get_settings()
        assert settings.FDB_LOAD_MTL is True
    finally:
        monkeypatch.delenv("FDB_LOAD_MTL", raising=False)
        cfg.reset_settings_cache()


# ---------------------------------------------------------------------------
# filter_loadable_specs
# ---------------------------------------------------------------------------


def test_filter_excludes_mtl_under_default_flag() -> None:
    """fdb_load_mtl=False â†’ MTL specs are dropped."""
    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=False)
    table_names = [s.table_name for s in out]
    assert "MTL_TEST_LEX_MASTER" not in table_names
    assert "RNP3_NDC_PRICE" in table_names  # Phase 09 untouched
    assert len(out) == 4  # all except MTL


def test_filter_includes_mtl_when_flag_true() -> None:
    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=True)
    assert len(out) == 5
    assert any(s.table_name == "MTL_TEST_LEX_MASTER" for s in out)


def test_filter_preserves_input_order() -> None:
    out = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=True)
    assert [s.table_name for s in out] == [
        "RNP3_NDC_PRICE",
        "RMIID1_MED",
        "RNDC9_BAR",
        "RNDC14_NDC_MSTR",
        "MTL_TEST_LEX_MASTER",
    ]


def test_filter_only_groups_restricts_to_requested_groups() -> None:
    """only_groups=['fdb_tier_a'] â†’ only Tier A specs returned."""
    out = filter_loadable_specs(
        _ALL_SPECS, fdb_load_mtl=False, only_groups=["fdb_tier_a"]
    )
    assert len(out) == 1
    assert out[0].table_name == "RMIID1_MED"


def test_filter_only_groups_mtl_still_denied_under_default_flag() -> None:
    """Even an explicit only_groups=['fdb_mtl'] is denied if the flag is False.

    This is the load-bearing assertion â€” the flag is the GATE; group
    selection is sub-filtering. If a future caller passes `only_groups=
    ['fdb_mtl']` from a CLI typo, the flag still says no.
    """
    out = filter_loadable_specs(
        _ALL_SPECS, fdb_load_mtl=False, only_groups=[MTL_LOADER_GROUP]
    )
    assert out == []


def test_filter_only_groups_mtl_allowed_when_flag_true() -> None:
    out = filter_loadable_specs(
        _ALL_SPECS, fdb_load_mtl=True, only_groups=[MTL_LOADER_GROUP]
    )
    assert len(out) == 1
    assert out[0].table_name == "MTL_TEST_LEX_MASTER"


def test_filter_phase_09_specs_unaffected_by_flag() -> None:
    """loader_group=None specs always load (Phase 09 backward-compat)."""
    for flag in (True, False):
        out = filter_loadable_specs([_PHASE_09_SPEC], fdb_load_mtl=flag)
        assert out == [_PHASE_09_SPEC]


def test_filter_empty_input_is_empty_output() -> None:
    assert filter_loadable_specs([], fdb_load_mtl=False) == []


# ---------------------------------------------------------------------------
# mtl_specs accessor
# ---------------------------------------------------------------------------


def test_mtl_specs_returns_only_mtl() -> None:
    out = mtl_specs(_ALL_SPECS)
    assert len(out) == 1
    assert out[0].table_name == "MTL_TEST_LEX_MASTER"


def test_mtl_specs_empty_when_no_mtl() -> None:
    """Mirrors B9.A reality: no MTL specs registered yet â†’ empty."""
    assert mtl_specs([_PHASE_09_SPEC, _TIER_A_SPEC]) == []


# ---------------------------------------------------------------------------
# Lock-in test â€” survives B9.A through B9.G
# ---------------------------------------------------------------------------


def test_fdb_mtl_zero_loadable_under_default_flag() -> None:
    """Charter SC: under default `FDB_LOAD_MTL=False`, no MTL spec loads.

    B9.A: trivially true (no MTL specs exist yet).
    B9.B-F: still trivially true (no MTL specs registered).
    B9.G: now load-bearing (19 MTL specs registered with loader_group=
          "fdb_mtl"; flag default False excludes them all).
    Future activation wave: this test is RELAXED in tandem with the
          flag flip â€” it does not change semantics, the registered
          specs simply graduate to loadable.

    The assertion holds at every gate by construction: the registry
    helper filters before any load. The test is here to catch the
    regression where a future PR adds an MTL spec WITHOUT the
    `loader_group="fdb_mtl"` label (which would silently bypass the
    flag and load on default).
    """
    # Use the full _ALL_SPECS to simulate what the real catalog will
    # eventually look like. The assertion: every spec whose tier is
    # Tier.D must have loader_group=MTL_LOADER_GROUP, AND under default
    # flag none of them appear in the filter output.
    tier_d_specs = [s for s in _ALL_SPECS if s.tier == Tier.D]
    for spec in tier_d_specs:
        assert spec.loader_group == MTL_LOADER_GROUP, (
            f"{spec.table_name}: Tier D specs MUST set "
            f"loader_group='fdb_mtl' or they bypass the MTL guard."
        )

    default_load = filter_loadable_specs(_ALL_SPECS, fdb_load_mtl=False)
    assert not any(s.tier == Tier.D for s in default_load), (
        "Tier D / MTL specs appeared in the default load â€” MTL guard FAILED. "
        "Either FDB_LOAD_MTL default flipped to True (forbidden without an "
        "activation wave) or loader_group label is missing on a Tier D spec."
    )


def test_revoke_sql_template_exists() -> None:
    """Defense-in-depth backstop file is present and references the placeholders."""
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[4]
    tmpl = repo_root / "infrastructure" / "scripts" / "lib" / "fdb_mtl_revoke.sql.tmpl"
    assert tmpl.exists(), f"MTL REVOKE template missing at {tmpl}"
    body = tmpl.read_text(encoding="utf-8")
    # Required placeholders the B9.G migration substitutes.
    for placeholder in ("{{SCHEMA}}", "{{MTL_TABLES}}", "{{APP_ROLES}}"):
        assert placeholder in body, (
            f"{placeholder} missing from fdb_mtl_revoke.sql.tmpl â€” B9.G "
            f"migration cannot substitute without it."
        )
    # Critical statements present.
    assert "REVOKE INSERT, UPDATE, DELETE" in body
    assert "RAISE EXCEPTION" in body  # verification block

codex
**Verdict: GO-WITH-FIXES**

| Severity | Area | Issue | Suggested fix |
|---|---|---|---|
| HIGH | MTL REVOKE template | [fdb_mtl_revoke.sql.tmpl](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:80>) uses `{{APP_ROLES_QUOTED}}`, but the documented substitution example only replaces `{{APP_ROLES}}`. A generated B9.G migration following the template docs will leave an unsubstituted placeholder and fail. Also, [line 43](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:43>) qualifies only the first table if `{{MTL_TABLES}}` is an unqualified comma list. | Add `{{APP_ROLES_QUOTED}}` to documented placeholders and usage, or derive it in the migration helper. Require `{{MTL_TABLES}}` to be schema-qualified per table, or change template generation to emit `{{SCHEMA}}.table1, {{SCHEMA}}.table2`. Add a unit test that renders the template with two tables/two roles and asserts no `{{...}}` remains. |
| HIGH | Gate artifacts | The prompt lists `waves/B9/status.md`, `parse_warning_allowlist.md`, `phase09_compat_baseline.md`, `module_base_profile.md`, and `write_path_enforcement.md`, but this checkout has no `waves/B9/` directory. Several code/test comments reference those files, so the governance evidence is not locally reviewable. | Commit or restore the `waves/B9/` artifacts before closing B9.A, especially `status.md` and the empty initial `parse_warning_allowlist.md`. |
| MEDIUM | Parse-warning allowlist policy | [assert_no_parse_warnings](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/tests/_fdb_contract.py:300>) defaults to zero tolerance, which is good, but the allowlist is just a free `Iterable[str]` parameter. Nothing enforces that callers load entries from the signed-off artifact, and the artifact is absent in this checkout. | Add a small allowlist loader/parser tied to `waves/B9/parse_warning_allowlist.md`, and make per-table tests use that path rather than inline sets. Add a lock-in test that the file exists and starts empty. |
| MEDIUM | Delta contract coverage | [assert_delta_semantics_acd_cycle](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/tests/_fdb_contract.py:416>) is tight for `UPSERT_BY_NATURAL_KEY` and catches the `DO NOTHING` regression. The remaining bypass risk is omission: a B9.B table can land without a per-table contract invoking it. | In B9.B, add a registry-vs-contract coverage test proving every new non-`UNKNOWN`/non-`TRUNCATE_RELOAD` `TableSpec` is represented in the delta contract suite. |

Notes on the scrutinized areas:

`filter_loadable_specs` itself is sound: MTL exclusion runs before `only_groups`, so `only_groups=["fdb_mtl"]` cannot bypass `FDB_LOAD_MTL=False`.

`scan_for_collisions` covers the listed schemas: `core`, `drug_database`, `drug_db`, `pharmacy_dir`, `prescriber_dir`, `public`, `reference`, `shared`; unknown schemas fail hard.

`setup_fdw.sh` moving from equality `66` to floor `>=66` is the right growth-path behavior.

The strict B9 resolver split from unchanged Phase 09 legacy loading is reasonable backward compatibility.

C13 equality on `DrugBase.metadata.tables == 9` is intentionally strict and appropriate for this gate.
tokens used
89,910
**Verdict: GO-WITH-FIXES**

| Severity | Area | Issue | Suggested fix |
|---|---|---|---|
| HIGH | MTL REVOKE template | [fdb_mtl_revoke.sql.tmpl](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:80>) uses `{{APP_ROLES_QUOTED}}`, but the documented substitution example only replaces `{{APP_ROLES}}`. A generated B9.G migration following the template docs will leave an unsubstituted placeholder and fail. Also, [line 43](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:43>) qualifies only the first table if `{{MTL_TABLES}}` is an unqualified comma list. | Add `{{APP_ROLES_QUOTED}}` to documented placeholders and usage, or derive it in the migration helper. Require `{{MTL_TABLES}}` to be schema-qualified per table, or change template generation to emit `{{SCHEMA}}.table1, {{SCHEMA}}.table2`. Add a unit test that renders the template with two tables/two roles and asserts no `{{...}}` remains. |
| HIGH | Gate artifacts | The prompt lists `waves/B9/status.md`, `parse_warning_allowlist.md`, `phase09_compat_baseline.md`, `module_base_profile.md`, and `write_path_enforcement.md`, but this checkout has no `waves/B9/` directory. Several code/test comments reference those files, so the governance evidence is not locally reviewable. | Commit or restore the `waves/B9/` artifacts before closing B9.A, especially `status.md` and the empty initial `parse_warning_allowlist.md`. |
| MEDIUM | Parse-warning allowlist policy | [assert_no_parse_warnings](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/tests/_fdb_contract.py:300>) defaults to zero tolerance, which is good, but the allowlist is just a free `Iterable[str]` parameter. Nothing enforces that callers load entries from the signed-off artifact, and the artifact is absent in this checkout. | Add a small allowlist loader/parser tied to `waves/B9/parse_warning_allowlist.md`, and make per-table tests use that path rather than inline sets. Add a lock-in test that the file exists and starts empty. |
| MEDIUM | Delta contract coverage | [assert_delta_semantics_acd_cycle](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/tests/_fdb_contract.py:416>) is tight for `UPSERT_BY_NATURAL_KEY` and catches the `DO NOTHING` regression. The remaining bypass risk is omission: a B9.B table can land without a per-table contract invoking it. | In B9.B, add a registry-vs-contract coverage test proving every new non-`UNKNOWN`/non-`TRUNCATE_RELOAD` `TableSpec` is represented in the delta contract suite. |

Notes on the scrutinized areas:

`filter_loadable_specs` itself is sound: MTL exclusion runs before `only_groups`, so `only_groups=["fdb_mtl"]` cannot bypass `FDB_LOAD_MTL=False`.

`scan_for_collisions` covers the listed schemas: `core`, `drug_database`, `drug_db`, `pharmacy_dir`, `prescriber_dir`, `public`, `reference`, `shared`; unknown schemas fail hard.

`setup_fdw.sh` moving from equality `66` to floor `>=66` is the right growth-path behavior.

The strict B9 resolver split from unchanged Phase 09 legacy loading is reasonable backward compatibility.

C13 equality on `DrugBase.metadata.tables == 9` is intentionally strict and appropriate for this gate.
