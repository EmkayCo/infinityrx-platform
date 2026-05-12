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
session id: 019e1a8c-2bc6-7891-9361-8a21194e40dd
--------
user
# Codex B9.A mini-GATE-CLOSE R2 — Verification Pass

**Wave:** B9 (FDB NDDF Plus 217-table extension)
**Phase:** B9.A close (verification of R1 GO-WITH-FIXES absorption)
**Verdict requested:** GO / GO-WITH-FIXES / NO-GO
**Round 1 result:** GO-WITH-FIXES (2 HIGH + 2 MEDIUM) — see
`waves/B9/codex-gate-close-r1-result.md`

## What changed since R1

One absorption commit on `develop` — `33e858b`:

```
B9.A GATE-CLOSE R1 absorption — HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
```

Fixes applied:

### F1 — MTL REVOKE template (HIGH 1)
File: `infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl`
- Documented `{{APP_ROLES_QUOTED}}` placeholder (was used at line 80
  but undocumented in the header).
- Removed broken schema-prefix-broadcast assumption from the REVOKE
  clause. Was: `ON {{SCHEMA}}.{{MTL_TABLES}}` (qualified only the
  first table). Now: `ON {{MTL_TABLES}}` with the migration helper
  responsible for emitting fully-qualified `drug_database.mtl_x`
  entries per table.
- Header now contains a reference Python substitution body for the
  B9.G migration helper.
- New test `modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py`
  (6 tests) renders the template with realistic inputs and asserts:
  * No `{{...}}` placeholder survives a full substitution
  * Every table appears schema-qualified (catches the line-43 bug)
  * Verification block uses quoted role literals
  * REVOKE statement appears exactly once

### F2 — Wave artifacts in repo (HIGH 2)
Mirrored the following from Werkbench into `waves/B9/`:
- `status.md` (the ledger)
- `parse_warning_allowlist.md` (empty initial — only the policy table)
- `phase09_compat_baseline.md`
- `module_base_profile.md`
- `write_path_enforcement.md`

Pattern matches existing `waves/B7.2/`, `waves/B8/`, etc.

### F3 — Parse-warning allowlist enforcement (MEDIUM 1)
File: `modules/drug-database/tests/_fdb_contract.py`
- Added `load_parse_warning_allowlist(path=None)` that reads
  `waves/B9/parse_warning_allowlist.md` and returns ONLY entries
  inside the "Approved allowlist entries" section (regex section-
  anchored — surrounding doc text and policy tables ignored).
- 4 new tests:
  * `test_allowlist_loader_returns_empty_on_repo_initial` — empty
    initial state is a contract (B9.A C3 ships empty)
  * `test_allowlist_loader_parses_approved_table_rows` — happy path
    + section-anchoring assertion (rows in "Process for adding"
    section are NOT returned)
  * `test_allowlist_loader_handles_missing_approved_section` —
    file without the section → empty set, no error
  * `test_allowlist_loader_raises_on_missing_file` — empty file
    MUST exist per B9.A ship contract

### F4 — Delta-contract coverage assertion (MEDIUM 2)
Explicitly deferred to B9.B per codex's own remediation language:
"In B9.B, add a registry-vs-contract coverage test...". Documented
as a B9.B pre-opening obligation in `waves/B9/status.md` →
"B9.B pre-opening obligation (F4)".

## Test result after absorption

```
B9.A cumulative tests:  116 → 129 PASS (+13: 6 MTL render + 4 allowlist + 3 prior reconciliation)
drug-database unit:      326 → 332 PASS, no regression
integration:             3 skipped (live-DB only, expected)
```

## Areas to verify in R2

1. **F1**: does the new MTL template substitution recipe correctly
   substitute all four placeholders in `_render`
   (`modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py`)?
   Is the no-`{{...}}`-survives assertion the right invariant?
2. **F2**: are the in-repo `waves/B9/` artifacts complete enough
   that a future operator can reconstruct B9.A close from this
   checkout alone (no Werkbench dependency)?
3. **F3**: is the regex anchoring on "Approved allowlist entries"
   robust to operator edits of the surrounding markdown (e.g.,
   renaming the H2)? If renamed, the loader returns empty — is
   that the right failure mode, or should it raise?
4. **F4 deferral**: is the status-ledger row + B9.B pre-opening
   obligation sufficient documentation for the deferral, or should
   a stub test land in B9.A now with `pytest.mark.xfail(reason=...)`?

## Verdict format

GO — B9.A closes; B9.B opens.
GO-WITH-FIXES — list residual HIGH / MEDIUM concerns.
NO-GO — fundamental issue.

For GO-WITH-FIXES, return concerns as:
| Severity | Area | Issue | Suggested fix |

codex
I’ll verify the absorption against the repository state directly: read the R1 result, inspect commit `33e858b`, check the new template/tests/artifacts, and run focused tests if the read-only sandbox allows execution.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show --stat --oneline --decorate --no-renames 33e858b' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw waves/B9/codex-gate-close-r1-result.md' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 422ms:
33e858b (HEAD -> develop) B9.A GATE-CLOSE R1 absorption — HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
 infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl |  65 +++++++---
 modules/drug-database/tests/_fdb_contract.py       |  68 ++++++++++
 .../drug-database/tests/unit/test_fdb_contract.py  |  61 +++++++++
 .../tests/unit/test_fdb_mtl_revoke_template.py     | 130 +++++++++++++++++++
 waves/B9/module_base_profile.md                    | 124 ++++++++++++++++++
 waves/B9/parse_warning_allowlist.md                |  64 ++++++++++
 waves/B9/phase09_compat_baseline.md                |  94 ++++++++++++++
 waves/B9/status.md                                 | 139 +++++++++++++++++++++
 waves/B9/write_path_enforcement.md                 |  78 ++++++++++++
 9 files changed, 808 insertions(+), 15 deletions(-)

2026-05-12T04:57:41.780996Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.5 seconds
Output:
Get-Content : Cannot find path 'C:\Users\MK\Desktop\Code 
Projects\InfinityRx\infinityrx-platform\waves\B9\codex-gate-close-r1-result.md' because it does not exist.
At line:2 char:1
+ Get-Content -Raw waves/B9/codex-gate-close-r1-result.md
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\MK\Des...se-r1-result.md:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 

 exited 1 in 477ms:
Get-Content : Cannot find path 'C:\Users\MK\Desktop\Code 
Projects\InfinityRx\infinityrx-platform\waves\B9\codex-gate-close-r1-result.md' because it does not exist.
At line:2 char:1
+ Get-Content -Raw waves/B9/codex-gate-close-r1-result.md
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (C:\Users\MK\Des...se-r1-result.md:String) [Get-Content], ItemNotFoundEx 
   ception
    + FullyQualifiedErrorId : PathNotFound,Microsoft.PowerShell.Commands.GetContentCommand
 

 succeeded in 464ms:
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
?? waves/B7.2/
?? waves/B8.1.1/
?? waves/B8/
?? waves/B9/codex-gate-close-r2-prompt.md
?? waves/B9/codex-gate-close-r2-result.md
warning: could not open directory '.claude/skills$skill/': No such file or directory

codex
The checkout has a very dirty tree, but `33e858b` is at `HEAD -> develop`, so I’m treating unrelated unstaged/untracked work as out of scope. The R1 result file named in the prompt is not present at `waves/B9/codex-gate-close-r1-result.md`; I’ll rely on the prompt’s R1 summary and verify the actual R2 artifacts.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw modules/drug-database/tests/_fdb_contract.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw modules/drug-database/tests/unit/test_fdb_contract.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 394ms:
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
-- Substitution placeholders (ALL FOUR must be replaced before applying):
--   {{SCHEMA}}            â†’ typically "drug_database"
--   {{MTL_TABLES}}        â†’ COMMA-SEPARATED SCHEMA-QUALIFIED table list.
--                           Caller is responsible for prefixing each table
--                           with the schema (NOT just bare names) so the
--                           REVOKE statement applies to every table, not
--                           just the first. Example value:
--                             drug_database.mtl_test_lex_master,
--                             drug_database.mtl_test_lex_xref
--                           (Previous versions of this template implied
--                           `{{SCHEMA}}.{{MTL_TABLES}}` would broadcast
--                           the prefix â€” Postgres syntax does NOT do that.
--                           Codex GATE-CLOSE R1 HIGH 1 fix.)
--   {{APP_ROLES}}         â†’ comma-separated role names (unquoted), used
--                           in REVOKE ... FROM <roles>. Example value:
--                             ifx_dev_app, ifx_mock_app, ifx_app_role_from_env
--                           (B7.3 env-driven pattern â€” see migrations
--                            under modules/*/alembic/versions/)
--   {{APP_ROLES_QUOTED}}  â†’ SAME role list as {{APP_ROLES}} but with each
--                           name wrapped in SQL string literals (single
--                           quotes) for the information_schema lookup in
--                           the verification block. Example value:
--                             'ifx_dev_app', 'ifx_mock_app', 'ifx_app_role_from_env'
--                           (information_schema.role_table_grants.grantee
--                            is text; needs quoted literals, not unquoted
--                            identifiers.)
--
-- Reference Python substitution body for the B9.G migration helper:
--
--   roles = ("ifx_dev_app", "ifx_mock_app", os.environ.get("IFX_APP_ROLE", "ifx_dev_app"))
--   schema = "drug_database"
--   tables_qualified = ", ".join(f"{schema}.{t}" for t in mtl_table_names)
--   roles_unquoted   = ", ".join(roles)
--   roles_quoted     = ", ".join(f"'{r}'" for r in roles)
--   body = (
--       Path("infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl")
--         .read_text(encoding="utf-8")
--         .replace("{{SCHEMA}}", schema)
--         .replace("{{MTL_TABLES}}", tables_qualified)
--         .replace("{{APP_ROLES}}", roles_unquoted)
--         .replace("{{APP_ROLES_QUOTED}}", roles_quoted)
--   )
--   op.execute(text(body))
--
-- A unit test (see modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py)
-- renders the template with two tables / two roles and asserts ZERO
-- `{{...}}` placeholders survive â€” the migration cannot ship with an
-- unsubstituted token.
--
-- Idempotent: re-running this script produces no error (REVOKE on
-- already-revoked privileges is a no-op in Postgres). SELECT is NOT
-- revoked â€” reads stay open for the app-layer filter to enforce its
-- own contract.

-- 1) Revoke writes on the MTL tables themselves.
-- {{MTL_TABLES}} is already a schema-qualified comma list â€” DO NOT prefix
-- with {{SCHEMA}}. here (Postgres won't broadcast the prefix across the
-- comma list; only the first table would be qualified).
REVOKE INSERT, UPDATE, DELETE
    ON {{MTL_TABLES}}
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


 succeeded in 443ms:
"""B9.A C4 (post-gate-close F1) â€” Render-time tests for fdb_mtl_revoke.sql.tmpl.

Codex B9.A GATE-CLOSE R1 HIGH 1 fix: the template uses FOUR
placeholders ({{SCHEMA}}, {{MTL_TABLES}}, {{APP_ROLES}},
{{APP_ROLES_QUOTED}}). The B9.G migration helper must substitute
all four â€” leaving any one un-substituted ships a broken migration.

These tests render the template with realistic inputs and assert:
  1. No `{{...}}` token survives the substitution.
  2. The REVOKE statement names every table in the input list (the
     codex bug â€” only the first table was being qualified â€” would
     manifest as exactly ONE table appearing in the output).
  3. The verification-block grantee list uses QUOTED role literals
     (information_schema.role_table_grants.grantee is text).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[4]
    / "infrastructure" / "scripts" / "lib" / "fdb_mtl_revoke.sql.tmpl"
)


def _render(
    *,
    schema: str,
    tables: tuple[str, ...],
    roles: tuple[str, ...],
) -> str:
    """Mirror the substitution recipe documented in the template header."""
    body = _TEMPLATE_PATH.read_text(encoding="utf-8")
    tables_qualified = ", ".join(f"{schema}.{t}" for t in tables)
    roles_unquoted = ", ".join(roles)
    roles_quoted = ", ".join(f"'{r}'" for r in roles)
    return (
        body
        .replace("{{SCHEMA}}", schema)
        .replace("{{MTL_TABLES}}", tables_qualified)
        .replace("{{APP_ROLES}}", roles_unquoted)
        .replace("{{APP_ROLES_QUOTED}}", roles_quoted)
    )


# ---------------------------------------------------------------------------
# Render contract
# ---------------------------------------------------------------------------


def test_template_file_exists() -> None:
    assert _TEMPLATE_PATH.exists(), f"template missing at {_TEMPLATE_PATH}"


def test_full_render_leaves_no_placeholders() -> None:
    """Any {{...}} token after substitution would ship a broken migration."""
    rendered = _render(
        schema="drug_database",
        tables=("mtl_test_lex_master", "mtl_test_lex_xref"),
        roles=("ifx_dev_app", "ifx_mock_app", "ifx_prod_app"),
    )
    leftover = re.findall(r"\{\{[A-Za-z_]+\}\}", rendered)
    assert not leftover, (
        f"Template has un-substituted placeholders: {leftover}. "
        f"All four ({{SCHEMA}}, {{MTL_TABLES}}, {{APP_ROLES}}, "
        f"{{APP_ROLES_QUOTED}}) must be replaced."
    )


def test_revoke_statement_names_every_table() -> None:
    """Codex HIGH 1: previous template was `ON {{SCHEMA}}.{{MTL_TABLES}}` â€” only the first table was qualified."""
    rendered = _render(
        schema="drug_database",
        tables=("mtl_alpha", "mtl_beta", "mtl_gamma"),
        roles=("ifx_dev_app",),
    )
    # Every table appears schema-qualified in the REVOKE clause.
    for table in ("mtl_alpha", "mtl_beta", "mtl_gamma"):
        assert f"drug_database.{table}" in rendered, (
            f"Table {table!r} missing from rendered REVOKE â€” schema "
            f"prefix was not broadcast across the comma list."
        )
    # Sanity: the REVOKE keyword appears once (single statement, not three).
    assert rendered.count("REVOKE INSERT, UPDATE, DELETE") == 1


def test_verification_block_uses_quoted_role_literals() -> None:
    """information_schema.role_table_grants.grantee is text â€” needs 'role' not role."""
    rendered = _render(
        schema="drug_database",
        tables=("mtl_x",),
        roles=("ifx_dev_app", "ifx_mock_app"),
    )
    # Quoted form appears in the IN (...) clause of the verification block.
    assert "'ifx_dev_app'" in rendered
    assert "'ifx_mock_app'" in rendered
    # Plus, the REVOKE clause uses the UNQUOTED form (identifiers, not literals).
    revoke_block = rendered.split("-- 2)")[0]
    assert "FROM ifx_dev_app, ifx_mock_app" in revoke_block


def test_render_with_single_table_and_single_role() -> None:
    """Minimum-size render â€” degenerate cases must still substitute cleanly."""
    rendered = _render(
        schema="drug_database",
        tables=("mtl_only",),
        roles=("ifx_dev_app",),
    )
    assert "drug_database.mtl_only" in rendered
    assert "FROM ifx_dev_app" in rendered
    assert "'ifx_dev_app'" in rendered
    leftover = re.findall(r"\{\{[A-Za-z_]+\}\}", rendered)
    assert not leftover


def test_template_still_carries_critical_statements() -> None:
    """Sanity â€” F1 cleanup didn't accidentally drop the REVOKE / verification."""
    body = _TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "REVOKE INSERT, UPDATE, DELETE" in body
    assert "RAISE EXCEPTION" in body  # verification block
    assert "information_schema.role_table_grants" in body
    # All four placeholders documented somewhere in the template header.
    for placeholder in (
        "{{SCHEMA}}", "{{MTL_TABLES}}", "{{APP_ROLES}}", "{{APP_ROLES_QUOTED}}"
    ):
        assert placeholder in body, f"{placeholder} disappeared from template"


 succeeded in 442ms:
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
    load_parse_warning_allowlist,
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


# ---------------------------------------------------------------------------
# Parse-warning allowlist loader (codex GATE-CLOSE R1 MEDIUM 1)
# ---------------------------------------------------------------------------


def test_allowlist_loader_returns_empty_on_repo_initial() -> None:
    """B9.A C3 ships the file empty. B9.B+ may add signed-off entries."""
    entries = load_parse_warning_allowlist()
    # Empty initial state â€” no approved entries at B9.A close.
    # If an entry appears here outside a consult-round, that's a process
    # violation; the test fails and forces the question.
    assert entries == frozenset(), (
        f"Expected empty initial allowlist (B9.A C3 state); got: "
        f"{sorted(entries)}. Each entry must have a CONSULT-ROUND "
        f"sign-off documented in parse_warning_allowlist.md."
    )


def test_allowlist_loader_parses_approved_table_rows(tmp_path) -> None:
    """Approved table rows yield message strings; surrounding doc text is ignored."""
    fixture = tmp_path / "parse_warning_allowlist.md"
    fixture.write_text(
        "# header\n"
        "Some intro text.\n\n"
        "## Approved allowlist entries\n\n"
        "| Message | Table(s) | %impact | Rationale | Consult sign-off |\n"
        "|---|---|---|---|---|\n"
        "| `fdb_table_field_count_mismatch` | RNP3 | 0.02% | sentinel | R7 |\n"
        "| `fdb_table_row_invalid` | RBAR | 0.001% | NDC fmt | R8 |\n\n"
        "## Process for adding an entry\n"
        "(unrelated section)\n"
        "| `not_a_real_entry` | x | y | z | w |\n",
        encoding="utf-8",
    )
    entries = load_parse_warning_allowlist(path=fixture)
    assert entries == frozenset({
        "fdb_table_field_count_mismatch",
        "fdb_table_row_invalid",
    })
    # Verify section anchoring â€” entries from the "Process" section
    # are NOT returned.
    assert "not_a_real_entry" not in entries


def test_allowlist_loader_handles_missing_approved_section(tmp_path) -> None:
    """File without the approved-entries section â†’ empty set, not error."""
    fixture = tmp_path / "parse_warning_allowlist.md"
    fixture.write_text(
        "# Just a policy doc with no approval section\n", encoding="utf-8"
    )
    assert load_parse_warning_allowlist(path=fixture) == frozenset()


def test_allowlist_loader_raises_on_missing_file(tmp_path) -> None:
    """Empty initial file MUST exist â€” every B9.B+ wave ships it."""
    nonexistent = tmp_path / "absent.md"
    with pytest.raises(FileNotFoundError, match="allowlist missing"):
        load_parse_warning_allowlist(path=nonexistent)


 succeeded in 444ms:
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
import re
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


# Repo path to the signed-off allowlist artifact. Per the parse-warning
# policy (charter v3.x + codex GATE-CLOSE R1 MEDIUM 1), every per-tier
# wrapper SHOULD source its allowlist from this file rather than inline
# sets. See `load_parse_warning_allowlist` below.
_PARSE_WARNING_ALLOWLIST_PATH = (
    Path(__file__).resolve().parents[3]
    / "waves" / "B9" / "parse_warning_allowlist.md"
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


def load_parse_warning_allowlist(
    path: Path | None = None,
) -> frozenset[str]:
    """Load approved parse-warning messages from the signed-off artifact.

    The artifact at `waves/B9/parse_warning_allowlist.md` is the SINGLE
    SOURCE OF TRUTH for which `_log.warning` messages are accepted as
    known-good silent-skip behavior. Per-tier wrappers should pass the
    output of this loader into `assert_no_parse_warnings(allowlist=...)`
    instead of building inline sets.

    Approved entries live in a markdown table whose first column is the
    quoted message-string the parser emits. Lines outside the approved
    table â€” header text, rationale, process docs â€” are ignored. The
    loader is intentionally LENIENT about the surrounding markdown so
    operators can edit the doc freely; it is STRICT about what counts as
    an entry (must be a row whose first column is a backtick-quoted
    string, inside the "Approved allowlist entries" section).

    Args:
        path: override location (defaults to the in-repo artifact).

    Returns:
        Frozenset of message strings. Empty initial state (B9.A) means
        the contract default of zero tolerance still applies.

    Raises:
        FileNotFoundError: artifact missing â€” every B9.B+ wave must
        ship this file with at least the empty-initial header.
    """
    target = path or _PARSE_WARNING_ALLOWLIST_PATH
    if not target.exists():
        raise FileNotFoundError(
            f"Parse-warning allowlist missing at {target}. The empty "
            f"initial file ships in B9.A C3; restore it from "
            f"Werkbench/projects/infinityrx-platform/waves/B9/."
        )
    body = target.read_text(encoding="utf-8")
    # Look only inside the "Approved allowlist entries" section, terminated by
    # the next markdown H2. Lines outside that block (header text, process
    # docs, the THREE-MESSAGE class-table) are excluded by section anchoring.
    approved_block = re.search(
        r"##\s+Approved allowlist entries\s*\n(.*?)(?=\n##\s|\Z)",
        body,
        flags=re.DOTALL,
    )
    if approved_block is None:
        return frozenset()
    block = approved_block.group(1)
    # Match `| `<message>` |` style rows. Skip the header row + separator.
    entries: set[str] = set()
    for row in re.finditer(r"^\|\s*`([^`]+)`\s*\|", block, flags=re.MULTILINE):
        entries.add(row.group(1))
    return frozenset(entries)


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
    "load_parse_warning_allowlist",
    "DeltaSimulationResult",
    "DeltaSimulator",
]


codex
The core code paths line up with the claimed changes so far. I’m checking the wave artifacts and the F4 deferral wording now, since the remaining gate risk is mostly whether future phases can reconstruct the close state and whether the deferred coverage obligation is easy to miss.
2026-05-12T04:58:04.394087Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-ChildItem waves/B9 | Select-Object -ExpandProperty Name | Sort-Object'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-ChildItem waves/B9 | Select-Object -ExpandProperty Name | Sort-Object' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-ChildItem waves/B9 | Select-Object -ExpandProperty Name | Sort-Object'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw waves/B9/status.md' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw waves/B9/parse_warning_allowlist.md' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw waves/B9/module_base_profile.md' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw waves/B9/phase09_compat_baseline.md' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw waves/B9/write_path_enforcement.md' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 551ms:
# Wave B9 â€” Status Ledger

Single source of truth for B9 wave progress. Memory entries point at
this file; do not duplicate state in `~/.claude/.../memory/*.md`.

**Charter:** v3.2 LOCKED (`waves/B9/charter.md`)
**Plan:** v3.1 LOCKED (`waves/B9/plan.md`)
**Baseline:** captured 2026-05-11 (`waves/B9/baseline.md`)
**Codex consult artifacts:** SPEC R1/R2/R3, PLAN R1/R2, ADVERSARIAL R1/R2

---

## Phase ledger

| Phase | Scope | Status | Commit range | Notes |
|---|---|---|---|---|
| B9.A | Infra + contracts | **IN PROGRESS â€” gate-close pending** | `503cd7b..9b61d6d` (9 commits) | C0-C14 below |
| B9.B | Tier A â€” 113 simple lookups | NOT STARTED | â€” | Blocked on B9.A gate-close |
| B9.C | Tier B â€” 66 NDC/GCN joins | NOT STARTED | â€” | Blocked on B9.B |
| B9.D | Tier C non-RNDC14 â€” 16 complex | NOT STARTED | â€” | Blocked on B9.C |
| B9.E | RNDC14 standalone | NOT STARTED | â€” | Blocked on B9.D |
| B9.F | Pricing big â€” RNP2 + RPRDPP0 | NOT STARTED | â€” | Blocked on B9.E |
| B9.G | MTL schema-only â€” 19 Tier D | NOT STARTED | â€” | Blocked on B9.F |
| B9.H | Cross-cutting cleanup + final gate | NOT STARTED | â€” | Blocked on B9.G |

---

## B9.A commits ledger

| C# | Scope | Commit | Test count (cumulative) |
|---|---|---|---|
| C0  | Baseline + invariants captured | (pre-session; `baseline.md` only) | â€” |
| C1  | TableSpec registry expansion (Tier + DeltaSemantics + 4 fields) | `9b19457` | 24 (24) |
| C2  | Generated migration template (gen_fdb_tier_migration.py) | `e54425f` | 12 (36) |
| C3  | Ingester contract test template (N4/A4/T12 mitigations) | `3ead3bd` | 22 (58) |
| C4  | MTL config flag + loader registry + DB REVOKE template | `33a2fb3` | 14 (72) |
| C5  | Codex PLAN R1 consult (captured pre-session) | (Werkbench: `codex-plan-consult-r1.md`) | â€” |
| C6  | Codex ADVERSARIAL R1 consult (captured pre-session) | (Werkbench: `codex-adversarial-r1.md`) | â€” |
| C7  | Plan v-bump â†’ v3.1 LOCKED (captured pre-session) | (Werkbench: `plan.md`) | â€” |
| C8  | SQLite-backed DELTA_SEMANTICS simulator + A4 detector | `d6cefd8` | 8 (80) |
| C9  | Reference-DB write-path guard (env-strict + SQL assert) | `2b1f2b9` | 11 (91) |
| C10 | FDW name-collision preflight script | `c03e37a` | 16 (107) |
| C11 | setup_fdw.sh manifest-derived count + deterministic sort | `60c6cc0` | 9 (116) |
| C12 | Phase 09 compat baseline (markdown + opt-in DB test) | `9b61d6d` | 3 (119, 3 DB-skip) |
| C13 | Module base profile + lock-in test | `9b61d6d` | 3 (122) |
| C14 | This ledger (no code) | (this commit) | â€” |

**Cumulative B9.A new unit tests: 116 pass; 3 integration tests skip without live DB.**

---

## Codex GATE-CLOSE R1 â€” verdict & absorption

**Verdict:** GO-WITH-FIXES (2 HIGH + 2 MEDIUM)
**Round:** R1 (2026-05-12)
**Artifacts:**
- `waves/B9/codex-gate-close-r1-prompt.md`
- `waves/B9/codex-gate-close-r1-result.md` (Werkbench)

**Absorbed in same session as gate-close:**

| Sev | Concern | Fix commit / location |
|---|---|---|
| HIGH | MTL REVOKE template `{{APP_ROLES_QUOTED}}` undocumented; `{{MTL_TABLES}}` schema-prefix bug | F1 â€” `infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` (docs + SQL line 43 fix) + new test `tests/unit/test_fdb_mtl_revoke_template.py` (6 tests, no-placeholder-survives assertion) |
| HIGH | Wave artifacts not in repo checkout (only Werkbench) | F2 â€” mirrored `waves/B9/{status,parse_warning_allowlist,phase09_compat_baseline,module_base_profile,write_path_enforcement}.md` into repo |
| MEDIUM | Parse-warning allowlist policy unenforced (free `Iterable[str]`) | F3 â€” `load_parse_warning_allowlist()` helper in `_fdb_contract.py` + 4 tests; the helper reads `waves/B9/parse_warning_allowlist.md` and returns only entries inside the "Approved" table block, section-anchored |
| MEDIUM | Delta-contract bypass risk (B9.B-G omitted from contract) | **F4 â€” deferred to B9.B opening.** Codex's own suggested fix specifies: "In B9.B, add a registry-vs-contract coverage test proving every new non-UNKNOWN/non-TRUNCATE_RELOAD TableSpec is represented in the delta contract suite." This is a B9.B C1-class commit. |

**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
spec lands, add `test_delta_contract_coverage` to assert
`{spec.table_name for spec in registry if spec.delta_semantics in
{UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}}
== {spec covered by a contract-test wrapper}`. Failing this test
forces a contract wiring per new spec.

---

## B9.A mini-GATE-CLOSE checklist (charter SC-9)

Per `waves/B9/plan.md:116-127`:

- [x] All cross-cutting infra commits unit-tested green (116/116 pass)
- [x] Pytest collection node-IDs captured at baseline (waves/B9/baseline.md)
- [x] `setup_fdw.sh --verify` still passes (132 PASS, 0 FAIL â€” captured post-B7.3)
- [x] Phase 09 compatibility baseline established (`phase09_compat_baseline.md`)
- [x] Write-path enforcement verified (write_path_guard tests 11/11 + smoke exit-1)
- [x] FDW name-collision preflight script in place + 16/16 tests pass
- [x] DB-level MTL guard template emitted (`fdb_mtl_revoke.sql.tmpl`)
- [x] Module-level base design profiled + lock-in test green
- [x] Codex PLAN R1+R2 + ADVERSARIAL R1+R2 verdicts captured + addressed
- [ ] Codex B9.A mini-GATE-CLOSE consult dispatched + verdict captured
- [ ] Memory updated: `project_b9a_implemented.md` written + MEMORY.md index updated

Open items above are completed in the same session as B9.A wave close.

---

## Charter / SC mapping

| SC | Charter requirement | B9.A status |
|---|---|---|
| SC-1 | 217 tables have models + migrations + ingester | **+0** (B9.B-G lands actual tables) |
| SC-2 | RECORD_COUNTS reconciliation (within Â±0.1%) | Contract template ready (C3); per-table assertions land B9.B+ |
| SC-3 | DELTA_SEMANTICS per table | Enum + contract (C1+C3+C8) ready; per-table assignment B9.B+ |
| SC-4 | Phase 09 untouched (row counts, query latency) | Baseline locked (C12); test runs every gate |
| SC-5 | Generated migration shape (idempotent up+down+up) | Generator + tests (C2) ready |
| SC-6 | FDW verify count grows additively | Manifest-derived count (C11) ready; floor 66 |
| SC-7 | Weekly delta idempotent per tier | Idempotency contract (C3+C8) ready |
| SC-8 | Test strategy (contract + parity + reconciliation + sampled behavioral) | Contract template (C3+C8) ready |
| SC-9 | Per-phase mini-GATE-CLOSE | This file is the ledger; per-phase entries appear B9.B+ |
| SC-10 | MTL excluded from default load + FDW | Config flag + registry + REVOKE template (C4) ready |

---

## Known deferrals from baseline

Per `waves/B9/baseline.md`:

1. **195 pre-existing test failures** â€” out of B9 scope per charter
   Â§Out-of-scope row 3 ("134 pre-existing test failures (forensic wave)").
   The +61 vs prior memory was resolved by B7.3 (commit `503cd7b`).
2. **tests/integration collection error** â€” pre-existing plugin
   registration conflict; forensic wave fixes.
3. **Second-run flake snapshot** â€” DEFERRED to next Docker-up session.

---

## Update protocol

This file is updated:

* When a B9.A C# commit lands â€” append the commit row.
* When a phase enters / exits / blocks â€” update the phase ledger row.
* When a charter SC moves status â€” update the SC mapping row.
* At every mini-GATE-CLOSE â€” append the per-phase evidence section.

Memory entries (`~/.claude/.../memory/project_b9_*.md`) reference
this file via a pointer (`see status.md row X`). They do NOT
duplicate state â€” that creates two-source-of-truth drift.


 succeeded in 579ms:
# B9 Parse-Warning Allowlist (initial: EMPTY)

**Owner:** B9 wave team
**Audit gate:** every B9.B-G mini-GATE-CLOSE re-reads this file; any
entry must reference a CONSULT-ROUND sign-off + documented count
impact + the contract test that proves the impact is bounded.

This file is the SINGLE SOURCE OF TRUTH for which `parse_table`
warning classes are accepted as known-good silent-skip behavior in
the B9 contract tests. Per `modules/drug-database/tests/_fdb_contract.py`
the helper `assert_no_parse_warnings()` defaults to ZERO tolerance â€”
ANY `_log.warning(...)` from `FDBLocalDropAdapter.parse_table` fails
the contract for that table.

To allowlist a warning, the wave operator runs:

```python
assert_no_parse_warnings(
    adapter, drop, spec,
    allowlist={"ingest_field_count_mismatch"},  # for example
)
```

The allowlist value is the FIRST positional arg to `_log.warning`
(message string), NOT the `extra` dict. Three known message classes
the parser can emit:

| Message string | Branch | Count impact |
|---|---|---|
| `fdb_table_transaction_code_missing` | UPD row's leading field is not A/C/D | drops the row from the load |
| `fdb_table_field_count_mismatch` | row's pipe-split field count != len(spec.columns) | drops the row |
| `fdb_table_row_invalid` | coercer raised ValueError / InvalidOperation / InvalidNDCError | drops the row |

## Approved allowlist entries

(none)

## Process for adding an entry

1. Identify the warning class via `caplog` or by running
   `assert_no_parse_warnings` and capturing the failure message.
2. Reproduce the warning locally and confirm the affected row class
   is data-shape-stable across at least 4 weekly drops (vendor isn't
   thrashing).
3. Write a short rationale ("PRICE_TYPE='14' NOPRC sentinel â€” 0.02%
   of RNP3 rows, documented in Â§4.4").
4. Add an entry to the table below with the rationale, the affected
   table(s), the rough %impact, and the link to the CONSULT-ROUND
   transcript that approved it.
5. Update the per-table contract test wrapper to pass the entry in
   the `allowlist=` set.

| Message | Table(s) | %impact | Rationale | Consult sign-off |
|---|---|---|---|---|

(empty â€” no entries approved as of B9.A C3)

## ADVERSARIAL N4 reminder

The N4 attack: parser silently skips field-count errors. The
contract test is what makes that branch loud. **Allowlisting is
NOT a free pass** â€” every entry expands the surface where the
parser can silently drop rows. Treat additions as a recorded
decision, not a routine extension.


 succeeded in 592ms:
# B9.A C12 â€” Phase 09 Compatibility Baseline

**Captured:** 2026-05-11 22:55 EDT (Docker-resumed, post-B7.3)
**Source:** `waves/B9/baseline.md` invariant set (re-asserted after B7.3 closure)
**Database:** `infinityrx_reference` on `infinityrx-postgres` container
**FDB drop:** `data/reference/fdb/TEL251759D/06MAY2026.TEL251759D/`

This file LOCKS the Phase 09 row counts + query latency that every
B9.B-G mini-GATE-CLOSE asserts unchanged (within documented tolerance).
A regression in any of these is a hard stop â€” B9 must not have
disturbed pricing data while extending the reference schema.

## Locked baseline values

### Row counts

| Table | Row count | Source |
|---|---|---|
| `drug_database.fdb_ndc_price_history` | **15,635,770** | Phase 09 close; re-asserted 2026-05-11 |
| `drug_database.fdb_price_type_desc`   | **23** | Phase 09 close; re-asserted 2026-05-11 |
| `drug_database.fdb_ndc_price_type_desc` | (TBD â€” capture next Docker session) | RNPTYPD0_NDC_PRICE_TYPE_DESC |

Tolerance: **exact match** for `fdb_price_type_desc` (static reference,
23 rows defined by spec). Weekly delta growth allowed for
`fdb_ndc_price_history` â€” separately tracked in the weekly delta
ledger; mini-GATE-CLOSE asserts row count **>= baseline** and that
the (NDC, price_type, effective_date, as_of_date) primary surface
is unchanged for any sampled NDC from baseline.

### Query latency

Representative NDC lookup query:

```sql
SELECT ndc_11, price_type FROM drug_database.fdb_ndc_price_history
WHERE ndc_11 = '00781153910' LIMIT 5;
```

Captured timing: **2.116 ms** (index hit; result was 0 rows â€” that
NDC is not in the dataset, but the planner still uses the
`(ndc_11, ...)` covering index). Mini-GATE-CLOSE asserts the same
shape: index hit + < 50 ms even for 0-row results. A regression to
sequential scan would be visible as latency jumping into the
hundreds-of-milliseconds range.

### Default-mode behavior

`load_fdb.py --mode fdb_weekly --dry-run` on the same drop returns:
- price_type_desc_inserted = 0 (already current)
- rnp3_inserted = 0 (already current â€” last weekly applied)
- rnp3_duplicate_skipped = 15,635,770 (idempotency proven)
- rnp3_invalid_skipped = 0

This is the IDEMPOTENCY signal: a re-run of the same drop produces
0 net new rows. Mini-GATE-CLOSE for B9.B-G re-runs this and asserts
all four counters unchanged.

## How mini-GATE-CLOSE re-asserts this

Each B9.B-G phase close runs:

```bash
source infrastructure/scripts/switch_env.sh dev
psql infinityrx_reference -tc \
  "SELECT count(*) FROM drug_database.fdb_ndc_price_history"
psql infinityrx_reference -tc \
  "SELECT count(*) FROM drug_database.fdb_price_type_desc"
time psql infinityrx_reference -c \
  "SELECT ndc_11, price_type FROM drug_database.fdb_ndc_price_history
   WHERE ndc_11 = '00781153910' LIMIT 5"
```

Outputs are diffed against this file. Any drift fails the mini-GATE.

## When this baseline is updated

Never silently. Three legitimate triggers:

1. **Weekly delta runs against the canonical drop.** Updates the
   `fdb_ndc_price_history` row count and the delta ledger entry.
   Baseline number stays as the lower bound; new captures appear
   alongside as ledger rows.
2. **FDB schema migration (vendor side).** Future drop adds a
   column. Baseline values stay; new assertion rows append.
3. **Recovery rebase.** Operator-triggered `fdb_rebase` repopulates.
   The new row count IS the new baseline; this file is updated in
   the same commit that runs the rebase.

## Test-side enforcement

`modules/drug-database/tests/integration/test_phase09_compat_baseline.py`
(added by B9.A C12) re-asserts the row counts against a live Postgres
when Docker is up; skipped otherwise. The markdown is the
operator-readable contract; the test is the CI gate.


 succeeded in 606ms:
# B9 Write-Path Enforcement Policy

**Charter section:** Â§SPEC-locked reference-DB invariants
**Plan reference:** C9 (`waves/B9/plan.md:109`)
**Code:** `shared/db/write_path_guard.py`, `scripts/load_fdb.py`
**Status:** ACTIVE â€” B9.A C9 onward

## The rule

B9 FDB loaders write reference tables (Tier A/B/C/RNDC14/pricing/MTL)
to `infinityrx_reference` and ONLY to `infinityrx_reference`. The
loader refuses to start unless BOTH conditions hold:

1. **Env-var:** `DATABASE_URL_SYNC_REFERENCE` is set to a Postgres
   URL pointing at the reference DB. Phase 09's fallback chain
   (`DATABASE_URL_SYNC_REFERENCE â†’ DATABASE_URL_SYNC â†’ DATABASE_URL`)
   is REMOVED in B9 strict mode. No fallback. Operator must export
   the variable explicitly via `switch_env.sh`.

2. **SQL assertion:** before the first write, the loader issues
   `SELECT current_database()` against the open connection. If the
   result is not `infinityrx_reference`, the loader RuntimeErrors
   with a message naming both the actual + expected DBs and the
   `switch_env.sh` fix-it path.

## Why both layers

Either layer alone is insufficient:

- **Env-var only.** Operator runs `switch_env.sh dev` (correctly sets
  `DATABASE_URL_SYNC_REFERENCE` to point at the reference DB on the
  dev cluster). They later edit their shell to point at a different
  Postgres cluster for an unrelated task â€” `DATABASE_URL_SYNC_REFERENCE`
  is still set but now resolves to the WRONG cluster's reference DB.
  The env-var rule alone passes; the SQL assertion catches it.
- **SQL assertion only.** Belt without suspenders. The env-var rule
  catches the typo BEFORE the engine even connects, saving a
  Postgres connection per failed attempt and giving a faster error.

## Phase 09 backward compatibility

The Phase 09 modes `fdb_initial / fdb_weekly / fdb_rebase` keep the
LEGACY fallback chain to avoid breaking existing operator runbooks
(commit `7e9e1ff` introduced the chain; operators have it in their
shell history). B9 loaders opt IN via:

```bash
python scripts/load_fdb.py --mode fdb_tier_a --require-reference-db
```

The `--require-reference-db` flag is set automatically by every B9.B-G
tier loader wrapper. Operators running Phase 09 modes by hand do not
need to know about the flag.

## Failure modes

| Failure | Exit code | Operator action |
|---|---|---|
| `DATABASE_URL_SYNC_REFERENCE` unset | 1 | `source infrastructure/scripts/switch_env.sh dev` |
| Env var set, but Postgres reports current_database() != 'infinityrx_reference' | 3 | Inspect `switch_env.sh`; confirm `DATABASE_URL_SYNC_REFERENCE` was exported to the reference DB URL, not the operational one. |
| FDB drop root missing | 2 | Verify `data/reference/fdb/TEL251759D/` exists or set `FDB_DROP_ROOT`. |

## Test seam

`assert_reference_db_write_path` accepts an injected `resolver=`
callable. Unit tests pass a lambda to bypass the real SQL roundtrip
without needing Postgres. Production callers leave `resolver=None` and
the default `SELECT current_database()` path runs.

Covered by `shared/tests/db/test_write_path_guard.py` (12 tests),
exit-code paths exercised by `scripts/load_fdb.py` integration.

## When to relax this rule

Never silently. If a future wave genuinely needs to write FDB-shaped
tables to an operational DB (e.g., a tenant-specific override schema),
the change is a new wave with a charter that explicitly names the
exception, NOT a quiet edit to the env-var resolver.


 succeeded in 609ms:
# B9.A C13 â€” Module-Level Declarative Base / Metadata Profile

**Captured:** 2026-05-12 (B9.A C13)
**Platform:** Windows 11, Python 3.13.x, SQLAlchemy 2.x
**Source:** `modules/drug-database/drug_database/models/tables.py`

## Why this profile exists

B9.B-G plan to land **217 new SQLAlchemy models** in
`modules/drug-database/drug_database/models/fdb/...`. The question
this profile answers: should every test importing `DrugBase` pay the
cost of loading all 217, or do we split the metadata so per-tier
imports are cheap?

## Phase 09 baseline (pre-B9)

| Metric | Value |
|---|---|
| `import drug_database.models.tables` cold time | **331 ms** |
| `len(DrugBase.metadata.tables)` | **9** |
| Per-table amortized cost | ~37 ms |

Note: the 331 ms includes SQLAlchemy itself warming up (~250 ms), so
the per-table cost on the cold-import path is closer to ~10 ms; later
table imports against the same loaded SQLAlchemy are sub-millisecond.

## Projected post-B9 (if everything lands on DrugBase)

| Scenario | Tables in DrugBase.metadata | Projected cold-import time |
|---|---|---|
| Phase 09 (today) | 9 | 331 ms |
| After B9.B (+113 Tier A) | 122 | ~1.5 s |
| After B9.C (+66 Tier B) | 188 | ~2.2 s |
| After B9.G (+220 total) | 229 | ~2.6 s |

The 8Ã— growth in import time would be paid by EVERY test in the
drug-database module that imports `DrugBase` â€” including unit tests
that only care about NDC normalization or pricing decimal logic and
have no need for FDB Tier A lookup models.

## Recommended pattern: tier-scoped sub-bases

**Single shared `MetaData(schema="drug_database")` instance**, fanned
out across tier-specific declarative bases:

```python
# modules/drug-database/drug_database/models/fdb/__init__.py
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# One MetaData â†’ all tables share the same schema namespace
# (drug_database) for alembic / FDW purposes.
fdb_metadata = MetaData(schema="drug_database")


class FDBBase(DeclarativeBase):
    """Common base for any cross-tier FDB model â€” pricing, RNDC14."""
    metadata = fdb_metadata


# Per-tier submodule re-exposes the same base:
# modules/drug-database/drug_database/models/fdb/tier_a/__init__.py
#   from drug_database.models.fdb import FDBBase as TierABase
# Tests that only need Tier A:
#   from drug_database.models.fdb.tier_a import TierABase
# Tests that don't need FDB at all:
#   import nothing from .fdb â€” DrugBase stays at 9 tables
```

### Why one MetaData, not four

Alembic generates one migration per `MetaData` it sees. Splitting the
metadata would require coordinating migration revision chains across
4 metadata objects â€” strictly worse than the current single-chain
setup. The READ-side cost is what we are optimizing, not the
WRITE-side migration generation.

### Why per-tier BASES with one METADATA

A SQLAlchemy declarative base is the IMPORT seam â€” importing the
base imports every class declared against it (Python module
initialization side-effect). Per-tier bases let a test importer say
"I only need Tier A models" and pay only the Tier A cost. The
underlying metadata is shared so alembic still sees one schema.

## Alembic env.py implications

`modules/drug-database/alembic/env.py` must explicitly import the
SHARED metadata when running migration autogen / upgrade. Either:

```python
from drug_database.models.fdb import fdb_metadata
target_metadata = fdb_metadata
```

OR keep Phase 09's `DrugBase.metadata` pointer and ensure the Phase
09 `DrugBase` re-exposes `fdb_metadata` (cleaner â€” preserves
backward compat for the alembic config).

## B9.A C13 lock-in test

`modules/drug-database/tests/unit/test_module_base_profile.py`
asserts:

1. `len(DrugBase.metadata.tables) == 9` â€” the Phase 09 surface.
   B9.B-G's first commit lifts this number IF the new tier was
   attached to DrugBase; that's the trigger to refactor to
   tier-scoped bases.
2. `DrugBase` imports without circular-import errors (regression
   detector for the sub-base pattern when it lands).

The test does NOT measure wall-clock import time â€” too noisy for
CI. The table-count assertion is the load-bearing canary.

## When to flip to tier-scoped bases

**Trigger:** the first B9.B commit that would push
`len(DrugBase.metadata.tables) > 12`. Refactor in the same commit:
move new tier models into `drug_database/models/fdb/tier_a/`,
update alembic env to point at the shared metadata, update the
lock-in test threshold.

**Not before then.** Premature refactor for a future need violates
Karpathy #3 (Surgical Changes). The lock-in test is the alarm.


exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\\.{{MTL_TABLES}}\" waves/B9 infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl modules/drug-database/tests" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg --files waves/B9' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show --name-only --format= 33e858b' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 399ms:
waves/B9\write_path_enforcement.md
waves/B9\status.md
waves/B9\phase09_compat_baseline.md
waves/B9\parse_warning_allowlist.md
waves/B9\module_base_profile.md
waves/B9\codex-gate-close-r2-result.md
waves/B9\codex-gate-close-r2-prompt.md

 exited 1 in 401ms:
rg: regex parse error:
    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
                                                                                                       ^
error: repetition operator missing expression

2026-05-12T04:58:11.647532Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.4 seconds
Output:
rg: regex parse error:
    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
                                                                                                       ^
error: repetition operator missing expression

 succeeded in 404ms:
infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl
modules/drug-database/tests/_fdb_contract.py
modules/drug-database/tests/unit/test_fdb_contract.py
modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py
waves/B9/module_base_profile.md
waves/B9/parse_warning_allowlist.md
waves/B9/phase09_compat_baseline.md
waves/B9/status.md
waves/B9/write_path_enforcement.md

codex
One material gap is emerging: `waves/B9/status.md` now exists, but it still points to repo-local `charter.md`, `plan.md`, `baseline.md`, and R1 artifacts that are not present under `waves/B9/`. That matters for the “reconstruct from checkout alone” criterion, so I’m checking focused tests before assigning severity.
2026-05-12T04:58:26.218206Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest -p no:cacheprovider modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py modules/drug-database/tests/unit/test_fdb_contract.py -q'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest -p no:cacheprovider modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py modules/drug-database/tests/unit/test_fdb_contract.py -q' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest -p no:cacheprovider modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py modules/drug-database/tests/unit/test_fdb_contract.py -q'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -F "waves/B9/charter.md" waves/B9/status.md; rg -n -F "waves/B9/plan.md" waves/B9/status.md; rg -n -F "waves/B9/baseline.md" waves/B9/status.md; rg -n -F "codex-gate-close-r1-result.md" waves/B9/status.md waves/B9' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -F "{{APP_ROLES_QUOTED}}" infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py; rg -n -F "ON {{MTL_TABLES}}" infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl; rg -n -F "ON {{SCHEMA}}.{{MTL_TABLES}}" infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
2026-05-12T04:58:26.968550Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.6 seconds
Output:
infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:37:--   {{APP_ROLES_QUOTED}}  → SAME role list as {{APP_ROLES}} but with each
infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:59:--         .replace("{{APP_ROLES_QUOTED}}", roles_quoted)
infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:115:      AND grantee IN ({{APP_ROLES_QUOTED}});
modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py:5:{{APP_ROLES_QUOTED}}). The B9.G migration helper must substitute
modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py:46:        .replace("{{APP_ROLES_QUOTED}}", roles_quoted)
modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py:70:        f"{{APP_ROLES_QUOTED}}) must be replaced."
modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py:128:        "{{SCHEMA}}", "{{MTL_TABLES}}", "{{APP_ROLES}}", "{{APP_ROLES_QUOTED}}"
78:    ON {{MTL_TABLES}}

 exited 1 in 623ms:
infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:37:--   {{APP_ROLES_QUOTED}}  → SAME role list as {{APP_ROLES}} but with each
infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:59:--         .replace("{{APP_ROLES_QUOTED}}", roles_quoted)
infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl:115:      AND grantee IN ({{APP_ROLES_QUOTED}});
modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py:5:{{APP_ROLES_QUOTED}}). The B9.G migration helper must substitute
modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py:46:        .replace("{{APP_ROLES_QUOTED}}", roles_quoted)
modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py:70:        f"{{APP_ROLES_QUOTED}}) must be replaced."
modules/drug-database/tests/unit/test_fdb_mtl_revoke_template.py:128:        "{{SCHEMA}}", "{{MTL_TABLES}}", "{{APP_ROLES}}", "{{APP_ROLES_QUOTED}}"
78:    ON {{MTL_TABLES}}

 succeeded in 1028ms:
6:**Charter:** v3.2 LOCKED (`waves/B9/charter.md`)
7:**Plan:** v3.1 LOCKED (`waves/B9/plan.md`)
80:Per `waves/B9/plan.md:116-127`:
8:**Baseline:** captured 2026-05-11 (`waves/B9/baseline.md`)
83:- [x] Pytest collection node-IDs captured at baseline (waves/B9/baseline.md)
117:Per `waves/B9/baseline.md`:
waves/B9/status.md:58:- `waves/B9/codex-gate-close-r1-result.md` (Werkbench)
waves/B9\codex-gate-close-r2-prompt.md:7:`waves/B9/codex-gate-close-r1-result.md`
waves/B9\status.md:58:- `waves/B9/codex-gate-close-r1-result.md` (Werkbench)
waves/B9\codex-gate-close-r2-result.md:20:`waves/B9/codex-gate-close-r1-result.md`
waves/B9\codex-gate-close-r2-result.md:122:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Raw waves/B9/codex-gate-close-r1-result.md' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-gate-close-r2-result.md:142:Projects\InfinityRx\infinityrx-platform\waves\B9\codex-gate-close-r1-result.md' because it does not exist.
waves/B9\codex-gate-close-r2-result.md:144:+ Get-Content -Raw waves/B9/codex-gate-close-r1-result.md
waves/B9\codex-gate-close-r2-result.md:153:Projects\InfinityRx\infinityrx-platform\waves\B9\codex-gate-close-r1-result.md' because it does not exist.
waves/B9\codex-gate-close-r2-result.md:155:+ Get-Content -Raw waves/B9/codex-gate-close-r1-result.md
waves/B9\codex-gate-close-r2-result.md:772:The checkout has a very dirty tree, but `33e858b` is at `HEAD -> develop`, so I’m treating unrelated unstaged/untracked work as out of scope. The R1 result file named in the prompt is not present at `waves/B9/codex-gate-close-r1-result.md`; I’ll rely on the prompt’s R1 summary and verify the actual R2 artifacts.
waves/B9\codex-gate-close-r2-result.md:2353:- `waves/B9/codex-gate-close-r1-result.md` (Werkbench)
waves/B9\codex-gate-close-r2-result.md:2857:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -F "waves/B9/charter.md" waves/B9/status.md; rg -n -F "waves/B9/plan.md" waves/B9/status.md; rg -n -F "waves/B9/baseline.md" waves/B9/status.md; rg -n -F "codex-gate-close-r1-result.md" waves/B9/status.md waves/B9' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform

codex
GO-WITH-FIXES

| Severity | Area | Issue | Suggested fix |
|---|---|---|---|
| HIGH | F2 artifacts | The repo still cannot reconstruct B9.A close from checkout alone. [status.md](</C:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/waves/B9/status.md:6>) references `waves/B9/charter.md`, `plan.md`, and `baseline.md`, but those files are absent. It also references `waves/B9/codex-gate-close-r1-result.md` as a Werkbench artifact at [status.md](</C:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/waves/B9/status.md:58>), and that file is not present in-repo. This means F2 only partially absorbed the R1 HIGH. | Mirror at least `charter.md`, `plan.md`, `baseline.md`, `codex-gate-close-r1-prompt.md`, and `codex-gate-close-r1-result.md` into `waves/B9/`, or revise `status.md` so every required close artifact points to an actual in-repo path. |

F1 looks acceptable: the template documents all four placeholders, uses `ON {{MTL_TABLES}}`, and the render test’s “no `{{...}}` survives” invariant is the right migration-safety check.

F3 is acceptable as a conservative failure mode. If the approved section is renamed, the loader returns an empty allowlist; that may cause false failures, but it does not silently permit parse drops.

F4 deferral is acceptable. I would not add an `xfail` stub in B9.A; the status-ledger pre-opening obligation is explicit enough, assuming B9.B treats it as a first commit gate.

I could not run the focused pytest command because the current tool policy blocked execution, so this verdict is based on repository inspection.
tokens used
44,336
GO-WITH-FIXES

| Severity | Area | Issue | Suggested fix |
|---|---|---|---|
| HIGH | F2 artifacts | The repo still cannot reconstruct B9.A close from checkout alone. [status.md](</C:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/waves/B9/status.md:6>) references `waves/B9/charter.md`, `plan.md`, and `baseline.md`, but those files are absent. It also references `waves/B9/codex-gate-close-r1-result.md` as a Werkbench artifact at [status.md](</C:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/waves/B9/status.md:58>), and that file is not present in-repo. This means F2 only partially absorbed the R1 HIGH. | Mirror at least `charter.md`, `plan.md`, `baseline.md`, `codex-gate-close-r1-prompt.md`, and `codex-gate-close-r1-result.md` into `waves/B9/`, or revise `status.md` so every required close artifact points to an actual in-repo path. |

F1 looks acceptable: the template documents all four placeholders, uses `ON {{MTL_TABLES}}`, and the render test’s “no `{{...}}` survives” invariant is the right migration-safety check.

F3 is acceptable as a conservative failure mode. If the approved section is renamed, the loader returns an empty allowlist; that may cause false failures, but it does not silently permit parse drops.

F4 deferral is acceptable. I would not add an `xfail` stub in B9.A; the status-ledger pre-opening obligation is explicit enough, assuming B9.B treats it as a first commit gate.

I could not run the focused pytest command because the current tool policy blocked execution, so this verdict is based on repository inspection.
