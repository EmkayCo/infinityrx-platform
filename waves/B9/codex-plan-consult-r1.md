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
session id: 019e187b-a4e9-73c0-be17-cac47a202eb9
--------
user
You are codex acting as the PLAN GATE reviewer for the InfinityRx platform's Wave B9, round 1.

## Context

Wave B9 = "FDB NDDF Plus 220-table extension". SPEC v3 is locked (you previously approved at SPEC R2 GO-WITH-FIXES → owner applied the stale-D4-row cleanup → v3 LOCKED). The next gate is PLAN v1. The owner drafted `plan.md` v1 (380 lines). Your job in PLAN R1 is to verify whether the plan is sound, complete, and ready for ADVERSARIAL review + execute, OR whether it needs revision.

## Artifacts to read

1. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md` — SPEC v3 LOCKED (115 lines)
2. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\plan.md` — PLAN v1 DRAFT, the document you are reviewing (~380 lines)
3. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\recon.md` — scope ground truth (328 lines)
4. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\codex-spec-consult-r2.md` — your SPEC R2 verdict (for continuity)
5. (For pattern reference) `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\InfinityRx\waves\B8\plan.md` — B8 plan v2 (the project's established PLAN format)

## What to verify (PLAN gate criteria)

**Plan-level:**
1. **Goal-backward coverage** — every charter SC (SC-1..SC-11) maps to at least one verification artifact in the plan's "Goal-backward verification" table.
2. **Threat model completeness** — every charter risk (R1..R7) has a corresponding plan threat (T1..T11) with a mitigation.
3. **Phase boundaries respect SPEC-locked granularity** — per-phase batched migrations; RNDC14 standalone; no 1-per-table; no single mega-migration.
4. **Mini-GATE-CLOSE criteria are concrete, not vague** — each phase B9.B..B9.G has measurable gate criteria (counts, test outcomes, perf numbers), not just "looks good."
5. **D2 perf gate (charter SC-4) is real** — B9.F's perf gate has timed dry-run + EXPLAIN ANALYZE + storage budget + weekly delta timing, all documented.
6. **MTL guards (charter SC-5) are triple-layered** — schema-only migration + loader-registry exclusion + integration test asserting zero rows.
7. **Pre-execute invariants are testable** — every invariant in "Pre-execute invariants" has a way to check it at B9.A C0.

**Plan-shape:**
8. **Session sizing realistic** — Tier A 113 tables / 10 sessions = ~12 tables/session; Tier B 66 / 12 = ~5.5/session. Are these defensible given the per-table work?
9. **Commit chains executable** — each phase's commit shape can be performed in the named session count without overflow.
10. **Codex iteration plan is complete** — every gate the SPEC requires has a corresponding consult row.

**Plan-errata (the owner surfaced 3 — verify and find more):**
11. **FDW final count 283 vs 284** — which is right? Recompute from recon's table counts and reconcile.
12. **Migration batching: 5 vs 6 vs 9-10** — which migration shape is best for review tractability without hitting the 1-per-table anti-pattern?
13. **Loader modes: `--mode fdb_weekly` vs `--mode fdb_initial`** — does the existing loader support both, or does B9.A need to add `fdb_weekly`?

**Charter-level (re-verify SPEC R2 verdict still holds against this plan):**
14. **Per-phase gates honored** — the plan's mini-GATE-CLOSE rows match SPEC v3's locked phase boundary table.
15. **Effort math** — plan's session count (B9.A=3 + B=10 + C=12 + D=4 + E=2 + F=4 + G=3 + H=4 = 42) vs charter's 39. Is the 3-session delta justified or scope creep?

**Vendor-name sanity check:**
16. Grep plan + charter + recon for any banned PBM/vendor names (per `.claude/rules/vendor-references.md`).

## Verdict format (match this exactly)

```
## PLAN R1 GATE VERDICT

<GO | GO-WITH-FIXES | NO-GO>

## Plan-level verification

| # | Criterion | Verdict | Evidence / notes |
|---|---|---|---|
| 1 | Goal-backward coverage of all SCs | YES / PARTIAL / NO | <ref> |
| 2 | Threat model completeness | YES / PARTIAL / NO | <ref> |
| 3 | Phase boundaries respect SPEC-locked granularity | YES / PARTIAL / NO | <ref> |
| 4 | Mini-GATE-CLOSE criteria concrete | YES / PARTIAL / NO | <ref> |
| 5 | D2 perf gate real | YES / PARTIAL / NO | <ref> |
| 6 | MTL guards triple-layered | YES / PARTIAL / NO | <ref> |
| 7 | Pre-execute invariants testable | YES / PARTIAL / NO | <ref> |
| 8 | Session sizing realistic | YES / DEFENSIBLE-BUT-RISKY / UNREALISTIC | <ref> |
| 9 | Commit chains executable | YES / PARTIAL / NO | <ref> |
| 10 | Codex iteration plan complete | YES / PARTIAL / NO | <ref> |

## Errata verification

| Erratum | Resolution | Evidence |
|---|---|---|
| FDW count 283 vs 284 | <which is right + why> | <recon table refs> |
| Migration batching shape | <recommended shape> | <reasoning> |
| Loader modes | <verify or add> | <evidence> |

## Charter-vs-plan consistency

| # | Question | Answer |
|---|---|---|
| 14 | Per-phase gates honored | YES / NO |
| 15 | Effort math reconciled | YES / NO + explanation |

## Vendor-name sanity check

<PASS / FAIL with evidence>

## New concerns (any HIGH/MEDIUM/LOW issues beyond the above)

<list with severity, or "None">

## Final verdict + next action

<one paragraph: if GO → proceed to codex ADVERSARIAL consult; if GO-WITH-FIXES → list required plan v2 changes; if NO-GO → explain structural problem>
```

Be rigorous. Mark PARTIAL or NO if any criterion is incomplete. Do not GO unless every criterion verifies, errata are resolved, and the vendor-name check passes.
codex
I’ll read the B9 artifacts and the vendor-reference rule first, then cross-check the plan against the charter and recon counts. Since this is a gate review, I’ll keep edits out of scope and return the requested verdict format only after verifying the cited files.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath '.claude\\rules\\vendor-references.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\InfinityRx\\waves\\B8\\plan.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-spec-consult-r2.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 465ms:
# Vendor Reference Rule â€” Clarification

The rule "ZERO reference to any third-party PBM vendor anywhere in
code, docs, or comments" is preserved in full force. This document
clarifies its scope.

## Scope â€” who the rule targets (PROHIBITED)

Companies that adjudicate pharmacy claims on behalf of payers and could
be confused with InfinityRx's market position:

- Express Scripts, ESI, Evernorth
- CVS Caremark, Caremark
- OptumRx (the PBM subsidiary specifically; distinct from Optum parent)
- Prime Therapeutics
- MedImpact
- Navitus
- MagellanRx
- Humana Pharmacy Solutions
- Any other competing PBM

## Out of scope â€” cleared for use (CLEARED)

Infrastructure vendors InfinityRx consumes. The following may appear
in code, configuration, documentation, error messages, logs, comments,
and test data where they refer to specific integration surfaces:

### Claim switches / pharmacy clearinghouses
- Relay Health, CoverMyMeds, McKesson (as parent)
- Change Healthcare, eRx Network
- RxSense
- Surescripts

### Payment networks
- Echo, CheckIssuing

### Accounting / financial
- QuickBooks, SaaSant, Intuit
- NACHA (standard, not a vendor)

### Cloud / infrastructure
- Azure, AWS, Microsoft, Google Cloud Platform

### Standards bodies
- NCPDP, ANSI, CMS, HHS, FDA

## Applying the rule

When in doubt:
- Does this name identify a company that adjudicates pharmacy claims
  as a PBM? â†’ PROHIBITED.
- Does this name identify infrastructure InfinityRx consumes to
  operate as a PBM? â†’ CLEARED.

If genuinely unclear, escalate to the project owner before committing.

 succeeded in 478ms:
# Wave B9 â€” FDB NDDF Plus 220-table extension (full scope)

**Status:** SPEC v3 LOCKED â€” codex SPEC R2 GO-WITH-FIXES (5/6 verified; D4 effort row stale-text cleanup applied per `codex-spec-consult-r2.md`). Ready for PLAN v1.
**Recon:** `recon.md` (2026-05-11) â€” verified scope and effort
**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
**Authority:** Project owner locked 4 scope decisions 2026-05-11 (this document captures them)

---

## Goal

Extend FDB NDDF Plus ingest from current **3 tables â†’ all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.

## Locked decisions (2026-05-11)

| # | Decision | Rationale |
|---|---|---|
| D1 | **RNDC14 = full 68-column ingest** | Future-proof; avoids N+1 schema-extension waves as consumers surface column needs. |
| D2 | **RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE = include + load by default** | Reverses Phase 09 `fdb_load_product_prices=False` deferral. +1.16 GB storage required; needs disk + Postgres performance verification at C0. |
| D3 | **Medical Test Lexicon (MTL) = schema-only, no data load** | Honors "clinical screening NOT subscribed" memory while landing table structure for future activation. 19 tables, 103 KB raw. If licensing changes, flip a config flag. |
| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4â€“5 months with multitasking. |

## Workstreams (recon-validated effort)

| W | Scope | Tables | Effort (recon line 14 + sections 6/7) |
|---|---|---|---|
| W1 | Tier A â€” simple lookups (â‰¤5 columns, generic ingester) | 113 | ~10 sessions |
| W2 | Tier B â€” NDC/GCN-keyed joins | 66 | ~12 sessions |
| W3 | Tier C â€” complex/large + RNDC14 full + RNP2 + RPRDPP0 + perf gate | 19 | ~10 sessions (8 baseline + ~2 D2 perf gate) |
| W4 | Tier D â€” MTL schema-only (no data load) | 19 | ~3 sessions |
| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |

**Total: ~39 sessions** (recon's A+B+C estimate is 34; +3 Tier D + ~2 D2 perf gate = 39). With codex review cadence already baked into per-phase budget. **Charter v1's 100-session figure was a misread; v2 corrects to recon's actual numbers.** Wall-clock at 3 sessions/week: ~13 weeks (~3 months).

## Out of scope (deferred)

- Clinical screening DATA ingest (only schema lands per D3)
- B8.2 followups (build_response docstring already shipped `1c28e44`)
- 134 pre-existing test failures (forensic wave)
- Phase 4 forward feature work

## Phased execution + per-phase closure gates (HIGH #1 codex fix)

B9 ships incrementally **with mandatory per-phase closure gates** â€” each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.

| Phase | Sub-scope | Sessions | Closure gate |
|---|---|---|---|
| B9.A | Charter v2 + plan v1 + codex SPEC R2 / PLAN / ADVERSARIAL | 2-3 | Plan v1 locked |
| B9.B | Tier A â€” 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** â€” evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests |
| B9.D | Tier C non-RNDC14 â€” 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** â€” column-by-column model review |
| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** â€” perf test results + EXPLAIN ANALYZE + storage budget verification |
| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** â€” integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
| B9.H | Manifest extension (66 â†’ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** â€” full cross-tier consult |

## Success criteria

| SC | Description |
|---|---|
| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
| SC-5 | MTL schema lands but **runtime/loader guards** prevent data load: `fdb_load_mtl=False` default; MTL tables excluded from default loader registry; integration test asserts **zero MTL rows** after default `load_fdb.py --mode fdb_weekly`. Alembic migration itself is NOT config-gated (per codex SPEC R1 #4). |
| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
| SC-7 | Weekly delta ingest path idempotent across all 220 tables (ON CONFLICT DO NOTHING or UPSERT per table; verified by re-running) |
| SC-8 | **Test coverage strategy** (per codex SPEC R1 #6): contract coverage for every `TableSpec`; schema/model parity for every table; row-count reconciliation for every loaded table; sampled behavioral tests per tier; dedicated Tier C tests for RNDC14 / RNP2 / RPRDPP0 / weekly delta. **No bespoke per-table behavioral tests** for the 217 tables â€” too heavy. |
| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
| SC-11 | Evidence + ship + memory + wave-history + B9 phased-progress dashboard |

## SPEC-locked migration granularity (codex SPEC R1 #5 fix)

**Migration granularity is SPEC-locked**, not deferred to plan:
- **NO** one-table-per-migration (213 migrations would be unmaintainable)
- **NO** single 217-table migration (atomicity ruined; review intractable)
- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) â€” 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE

## Risks

| # | Risk | Mit |
|---|---|---|
| R1 | 217 alembic migrations is unwieldy for review | SPEC-locked above to ~6 per-phase batched migrations + RNDC14 standalone. |
| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
| R3 | RNDC14 68 columns include latin-1 quirks (mixed-case names, accented chars, NULL sentinels) | Per-column normalization pass in ingester; latin-1 â†’ UTF-8 with replacement strategy documented |
| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
| R6 | 6-month wall-clock invites scope drift / charter decay | Phased execution table is contract; each phase has explicit closure gate |
| R7 | MTL schema accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via integration test; CI gate denies MTL data on default flag |

## Discipline

- **codex SPEC consult:** 1-3 rounds against this charter (full discipline restored given scope size)
- **codex PLAN consult:** 1-2 rounds against plan v1
- **ADVERSARIAL:** 2-3 rounds (large surface, novel scope, $11.96+ codex cost expected)
- **codex GATE-CLOSE:** 1-2 rounds at wave close (and possibly per-phase mini-closes)

## Estimated wall-clock (v2 corrected)

**~39 sessions Ã— 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong â€” corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)

## Note on scope vs recon recommendation

The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.

---

## Resume next session

1. `/werkbench`
2. Read this charter
3. Codex SPEC consult round 1 (against this v1)
4. Iterate to GO; then plan v1

 succeeded in 495ms:
# Wave B8 â€” Execution Plan v2

**Charter:** `charter.md` v3 (SPEC GO; v3 absorbed all SPEC round-2 concerns)
**Codex PLAN consult:** round 1 GO-WITH-FIXES (8 concerns); plan v2 absorbs all 8 + expanded scope per user decision 2026-05-10
**User decision 2026-05-10:** F1 expanded scope to **full sweep** (all ~30 cross-module + script + shared/data_ingestion consumers)
**Branch:** `develop`
**Estimated duration:** 5-7 hours wall-clock (revised from v1's 3-5h after scope expansion)
**Commit chain:** 7 atomic commits (C0-C6)

---

## Audit summary (final, post-expansion)

### Inside `modules/drug-database/` (intra-module â€” F1 sweeps in C1)
- 115 occurrences of `from src.X` / `import src.X` across 38 files (verified via `^\s*(from|import)\s+src(\.|$|\s+import)`)
- conftest.py: `from src.models.tables import DrugBase`
- alembic/env.py: 4 `src.*` imports
- All test files use intra-module `from src.X` patterns

### Outside `modules/drug-database/` (cross-module / scripts / shared â€” F1 sweeps in C2)

| Category | File | Lines | Symbol(s) |
|---|---|---|---|
| Cross-module | `modules/adjudication-engine/src/services/pricing_enrichment.py` | 112, 115, **118** | composite_pricing, fdb_pricing, **pricing.NadacPricingLookup** (codex caught the missing line 118) |
| Scripts | `scripts/load_fdb.py` | 88, 89 | fdb_adapter, fdb_pricing_ingester |
| Scripts | `scripts/load_nppes.py` | 122 | nppes_ingestion.load_nppes_satellite_tables |
| Scripts | `scripts/bench_nppes_satellite.py` | 122 | nppes_ingestion.load_nppes_satellite_tables |
| shared/data_ingestion sources | `cms_asp.py` | 459 | pricing_ingestion.ASPIngestionService |
| shared/data_ingestion sources | `cms_nadac.py` | 332 | pricing_ingestion.NADACIngestionService |
| shared/data_ingestion sources | `dea_registrations.py` | 185, 192 | compliance_tables.DeaRegistration |
| shared/data_ingestion sources | `fda_purple_book.py` | 338 | fda_supplementary_ingestion.* |
| shared/data_ingestion sources | `fda_rems.py` | 323 | fda_supplementary_ingestion.* |
| shared/data_ingestion sources | `fda_orange_book.py` | 509 | orange_book_tables.* |
| shared/data_ingestion sources | `ncpdp_dataq.py` | 488 | ncpdp_tables.* |
| shared/data_ingestion sources | `nppes.py` | 433, 456 | nppes_upsert, nppes_ingestion |
| shared/data_ingestion sources | `fda_ndc.py` | 552 | ndc_tables.* |
| shared/data_ingestion sources | `fda_drug_shortages.py` | 336 | fda_supplementary_ingestion.* |
| shared/data_ingestion sources | `rxnorm.py` | 439 | rxnorm_tables.* |
| shared/data_ingestion tests | `test_fda_shortages.py` | 73, 407, 443, 488 | fda_supplementary_tables, fda_supplementary_ingestion |
| shared/data_ingestion tests | `test_cms_nadac.py` | 70, 76 | pricing_tables, pricing_ingestion.NADACIngestionService |
| shared/data_ingestion tests | `test_fda_rems.py` | 76 | fda_supplementary_tables |
| shared/data_ingestion tests | `test_cms_asp.py` | 64, 70 | pricing_tables, pricing_ingestion.ASPIngestionService |
| shared/data_ingestion tests | `test_fda_purple_book.py` | 74, 394, 420 | fda_supplementary_tables, fda_supplementary_ingestion |
| shared/data_ingestion tests | `test_dea.py` | 144, 221 | compliance_tables.DeaRegistration, tables.PrescriberBase (comments at 55, 61, 675 are doc strings â€” NOT touched) |
| shared/data_ingestion tests | `test_rxnorm.py` | 80 | rxnorm_tables |
| shared/data_ingestion tests | `test_fda_ndc_parser.py` | 69 | ndc_tables |
| shared/data_ingestion tests | `test_cms_opt_out.py` | 119, 124 | medicare_tables, tables.Prescriber |
| shared/data_ingestion tests | `test_orange_book.py` | 83, 84 | ndc_tables, orange_book_tables |

**Total cross-module hits to update: ~30 lines across ~25 files**

**EXPLICITLY OUT OF F1 (must NOT be touched by C2 sed):**
- `shared/tests/events/test_cross_module_events.py:280` â€” `from src.events import wire_consumers` (this is **reclaimrx**'s src.events, NOT drug-database)
- All `from src.*` inside `modules/reclaimrx/`, `modules/adjudication-engine/`, `modules/billing/`, `modules/paysync/`, etc. â€” those are intra-module to their own packages

---

## Pre-execute invariants (must hold before C0)

1. Working tree clean of unrelated changes (the 7 pre-existing infrastructure/scripts/*.sh modifications + AGENTS.md + uv.lock NOT in any B8 commit).
2. `develop@9cc0c7e` is HEAD.
3. Codex CLI 0.128.0 available.
4. Local Postgres optional for SC-7 (publish capture is in-memory-bus based per codex concern #7).

---

## Codex PLAN concerns folded into v2

| # | Codex concern | v2 resolution |
|---|---|---|
| 1 | HIGH C1 sed too narrow (indented imports) | C1 uses `^\s*(from|import)\s+src(\.|\s+import)` regex (whitespace-aware); also handles `from src import X` form |
| 2 | HIGH C4 missing line 118 | Audit table above lists line 118 (NadacPricingLookup); C2 (renamed from C4) covers all 3 lines |
| 3 | HIGH setuptools subpackage discovery | C1 uses `[tool.setuptools.packages.find]` with `where = ["."]` and `include = ["drug_database*"]` |
| 4 | MEDIUM adjudication-engine dep path | adjudication-engine relies on sys.path manipulation (same as today); explicit decision: do NOT add editable dep â€” `python -c "from drug_database..."` works because pricing_enrichment.py runs after `_get_factory()` setup which has `modules/drug-database` on sys.path. Verified at C3 by running adjudication-engine tests. |
| 5 | MEDIUM C1+C2 not independently safe | Plan v2 merges C1 (rename + sed inside drug-database) + setuptools/coverage config + alembic + conftest into a single atomic commit |
| 6 | MEDIUM C7 missing txn_id | C5 (renamed F2 step) captures `txn = persist_claim_transaction(...)` and includes `svc_txn_id` in publish failure log |
| 7 | MEDIUM C8 skip can waive SC-7 | C6 publish-capture uses `set_event_bus(InMemoryEventBus())` in test fixture; capture assertion is non-skippable. Only the optional "real Postgres" variant is skippable. |
| 8 | LOW C0 audit count | C0 asserts the 30 known hits across the audited files (per audit table above), zero additional hits |

---

## Commit chain (7 commits)

### C0 â€” Pre-execute baseline + audit verification

**Actions (no commit; produces baseline.md only):**

1. Run repo-wide audit:
   ```bash
   grep -rnE "^\s*(from|import)\s+src(\.|$|\s+import)" --include='*.py' \
     modules/ scripts/ shared/ portal/ \
     | grep -v 'modules/drug-database/' \
     | grep -v 'modules/reclaimrx/' \
     | grep -v 'modules/adjudication-engine/' \
     | grep -v 'modules/billing/' \
     | grep -v 'modules/paysync/' \
     | grep -v 'modules/' # ... etc â€” exclude all module-internal hits
   ```
   Validate against audit table above.

2. Capture baseline test counts (suite, pass, fail, skip, xfail, duration):
   ```bash
   cd modules/drug-database && uv run pytest -q --tb=no 2>&1 | tee /tmp/b8-baseline-drug-database.txt | tail -10
   cd modules/adjudication-engine && uv run pytest -q --tb=no 2>&1 | tee /tmp/b8-baseline-adj.txt | tail -10
   cd modules/reclaimrx && uv run pytest -q --tb=no 2>&1 | tee /tmp/b8-baseline-reclaim.txt | tail -10
   cd shared/data_ingestion && uv run pytest -q --tb=no 2>&1 | tee /tmp/b8-baseline-shared-di.txt | tail -10
   ```

3. Write `waves/B8/baseline.md` with all 4 baselines.

**Gate:** baseline captured; final B8 state must match-or-improve at C3, C4, C6.

---

### C1 â€” drug-database **full atomic** rename + sed + packaging + alembic + conftest

**One commit covers:**
1. `git mv modules/drug-database/src modules/drug-database/drug_database`
2. Whitespace-aware sed across `modules/drug-database/`:
   ```bash
   find modules/drug-database -name '*.py' -print0 | xargs -0 sed -i -E \
     -e 's/^(\s*)from src\./\1from drug_database./g' \
     -e 's/^(\s*)from src import /\1from drug_database import /g' \
     -e 's/^(\s*)import src\./\1import drug_database./g' \
     -e 's/^(\s*)import src(\s*$|\s+as )/\1import drug_database\2/g'
   ```
3. Update `modules/drug-database/conftest.py` (caught by sed step 2 if `from src.X`)
4. Update `modules/drug-database/alembic/env.py` (caught by sed step 2)
5. Update `modules/drug-database/pyproject.toml`:
   - `[tool.coverage.run] source = ["src"]` â†’ `["drug_database"]`
   - `[tool.coverage.run] omit = ["src/db/session.py", ...]` â†’ `["drug_database/db/session.py", ...]`
   - Add (replacing whatever package config exists or absent):
     ```toml
     [tool.setuptools.packages.find]
     where = ["."]
     include = ["drug_database*"]
     ```

**Verification (in-commit, before commit):**
- `grep -rnE "^\s*(from|import)\s+src(\.|\s+import)" modules/drug-database/ --include='*.py'` returns ZERO hits
- `cd modules/drug-database && uv sync` succeeds
- `cd modules/drug-database && python -c "from drug_database.services.composite_pricing import CompositePricingLookup"` succeeds
- `cd <repo-root> && python -c "import sys; sys.path.insert(0, 'modules/drug-database'); from drug_database.services.composite_pricing import CompositePricingLookup"` succeeds
- `cd modules/drug-database && uv run pytest -q` pass-count â‰¥ baseline

**Commit:** `refactor(drug-database/p11b): F1 C1 rename src/ -> drug_database/ atomic â€” sed + setuptools + alembic + conftest`

---

### C2 â€” Cross-module + scripts + shared/data_ingestion sed sweep

**Files (per audit table above â€” 25 files):**
- `modules/adjudication-engine/src/services/pricing_enrichment.py` (lines 112, 115, **118** â€” drop type:ignore shim on all 3)
- `scripts/load_fdb.py`, `scripts/load_nppes.py`, `scripts/bench_nppes_satellite.py`
- `shared/data_ingestion/sources/{cms_asp,cms_nadac,dea_registrations,fda_purple_book,fda_rems,fda_orange_book,ncpdp_dataq,nppes,fda_ndc,fda_drug_shortages,rxnorm}.py`
- `shared/data_ingestion/tests/{test_fda_shortages,test_cms_nadac,test_fda_rems,test_cms_asp,test_fda_purple_book,test_dea,test_rxnorm,test_fda_ndc_parser,test_cms_opt_out,test_orange_book}.py`

**Method:** scoped whitespace-aware sed on each file individually OR a per-file list passed to xargs:

```bash
sed -i -E \
  -e 's/^(\s*)from src\.(services|models|api|db|utils)\./\1from drug_database.\2./g' \
  -e 's/^(\s*)from src\.(services|models)\.([a-z_]+) import/\1from drug_database.\2.\3 import/g' \
  modules/adjudication-engine/src/services/pricing_enrichment.py \
  scripts/load_fdb.py scripts/load_nppes.py scripts/bench_nppes_satellite.py \
  shared/data_ingestion/sources/{cms_asp,cms_nadac,dea_registrations,fda_purple_book,fda_rems,fda_orange_book,ncpdp_dataq,nppes,fda_ndc,fda_drug_shortages,rxnorm}.py \
  shared/data_ingestion/tests/{test_fda_shortages,test_cms_nadac,test_fda_rems,test_cms_asp,test_fda_purple_book,test_dea,test_rxnorm,test_fda_ndc_parser,test_cms_opt_out,test_orange_book}.py
```

Plus separate edit on `pricing_enrichment.py` to remove `# type: ignore[import-not-found]` from the 3 import statements.

**Critical safety check (non-touched files):**
- `shared/tests/events/test_cross_module_events.py` MUST remain unchanged (its `from src.events` is reclaimrx)
- All other `modules/*/src/` files MUST remain unchanged

**Verification:**
- `grep -rnE "from src\.(services\.(composite_pricing|fdb_|nppes_|pricing|fda_supplementary|pricing_ingestion)|models\.(ndc|fda_supplementary|orange_book|rxnorm|medicare|compliance|pricing|ncpdp)_?tables|models\.tables.*Prescriber|models\.tables.*PrescriberBase)" modules/ scripts/ shared/` returns zero hits
- `grep -n "type: ignore\[import-not-found\]" modules/adjudication-engine/src/services/pricing_enrichment.py` returns zero hits
- `python -c "from drug_database.services.composite_pricing import CompositePricingLookup"` works from repo root (with no sys.path injection â€” adjudication-engine will inject it at runtime)

**Commit:** `refactor(adjudication-engine+scripts+shared-data-ingestion/p11b): F1 C2 cross-module imports drug_database.* (drop src.* shim, 25 files / 30 lines)`

---

### C3 â€” F1 verification: all 4 test suites green (SC-3, SC-4, SC-5)

**Actions:**
- `cd modules/drug-database && uv run pytest -q` â†’ pass-count â‰¥ baseline
- `cd modules/adjudication-engine && uv run pytest -q` â†’ pass-count â‰¥ baseline
- `cd modules/reclaimrx && uv run pytest -q` â†’ pass-count â‰¥ baseline (sanity â€” should be unchanged)
- `cd shared/data_ingestion && uv run pytest -q` â†’ pass-count â‰¥ baseline

**On failure:** triage. If sed missed an import, surgical fix in C3 with separate commit. If logic broken, STOP and escalate.

**Commit:** none unless triage edits land. If triage edits required â†’ `fix(drug-database+shared-data-ingestion/p11b): F1 C3 post-rename test repairs`

---

### C4 â€” F2 (a): tcp_listener publish wiring (mirror admin_routes exactly with txn_id)

**File:** `modules/adjudication-engine/src/services/tcp_listener.py`

**Reference:** `modules/adjudication-engine/src/api/admin_routes.py:413-486`

**Surgical insertion:** between line 499 (end of persist `with` block) and line 500 (`finally: current_tenant_id.set(None)`).

**Imports to add at module top:**
- `from shared.events.factory import get_event_bus`
- `from .pricing_enrichment import enrich_pricing`

**Persist block update (capture txn for txn_id parity per codex concern #6):**

```python
            with self._session_factory() as sess, sess.begin():
                apply_accumulator_for_claim(
                    sess, tenant_id=tenant_id, program_id=program_id,
                    parsed=parsed, result=result,
                )
                txn = persist_claim_transaction(
                    sess, tenant_id=tenant_id, program_id=program_id,
                    parsed=parsed, result=result,
                )
                txn_id = str(txn.id)

            # Publish AFTER durable persistence â€” mirrors admin_routes.py:413-486.
            # Failure logged, never rolls back persistence.
            try:
                _cob = getattr(parsed, "cob", None)
                _cob_dv = (
                    str(_cob.other_payer_amount_paid)
                    if _cob is not None and _cob.other_payer_amount_paid is not None
                    else None
                )
                _cob_nq = (
                    str(_cob.other_payer_patient_responsibility_amount)
                    if _cob is not None and _cob.other_payer_patient_responsibility_amount is not None
                    else None
                )
                _pricing = await enrich_pricing(
                    ndc=parsed.claim.ndc,
                    date_of_service=parsed.header.date_of_service,
                )
                envelope = build_claim_adjudicated_event(
                    tenant_id=tenant_id,
                    correlation_id=uuid.uuid4(),
                    claim_id=result.claim_id,
                    member_id=result.member_id,
                    drug_ndc=parsed.claim.ndc,
                    status=result.status,
                    ingredient_cost=str(result.ingredient_cost),
                    dispensing_fee=str(result.dispensing_fee),
                    patient_pay=str(result.patient_pay),
                    plan_pay=str(result.plan_pay),
                    total_amount=str(result.total_amount),
                    pricing_model_used=result.pricing_model_used or "",
                    accumulator_detected=result.accumulator_detected,
                    override_applied=result.override_applied,
                    transaction_type=parsed.header.transaction_code,
                    pharmacy_npi=parsed.header.service_provider_id,
                    date_of_service=parsed.header.date_of_service,
                    other_payer_amount_paid=_cob_dv,
                    other_payer_patient_responsibility_amount=_cob_nq,
                    nadac_per_unit=_pricing["nadac_per_unit"],
                    wac_per_unit=_pricing["wac_per_unit"],
                    awp_per_unit=_pricing["awp_per_unit"],
                    awp_basis=_pricing["awp_basis"],
                )
                bus = get_event_bus()
                await bus.publish(envelope)
                logger.info(
                    "ncpdp_listener.claim_adjudicated.published",
                    extra={
                        "svc_claim_id": result.claim_id,
                        "svc_tenant_id": str(tenant_id),
                        "svc_event_type": envelope.event_type,
                    },
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "ncpdp_listener.claim_adjudicated.publish_failed",
                    extra={
                        "svc_claim_id": result.claim_id,
                        "svc_tenant_id": str(tenant_id),
                        "svc_txn_id": txn_id,
                    },
                )
```

**Verification:**
- `_process` is `async def` (line 391 confirmed) â€” `await` legal
- adjudication-engine tests still green
- mypy passes

**Commit:** `feat(adjudication-engine/p11b): F2 C4 publish claim.adjudicated from tcp_listener (mirrors admin_routes with txn_id)`

---

### C5 â€” F2 (b): integration test through `_handle_connection` with InMemoryEventBus capture

**File:** `modules/adjudication-engine/tests/integration/test_tcp_listener_publish.py` (NEW)

**Per codex concern #7:** publish capture is **non-skippable**. Uses `set_event_bus(InMemoryEventBus())` so no DB or external bus required.

**Test design (publish-capture variant, NEVER skipped):**
1. `set_event_bus(InMemoryEventBus())` in fixture
2. Set env: `IFX_NCPDP_LISTEN_TENANT_ID`, `IFX_NCPDP_LISTEN_PROGRAM_ID`, `FDB_PRICING_ENRICHMENT_ENABLED=false` (default-dict path â€” no FDB DB needed)
3. Construct `NcpdpTcpListener` with **in-memory SQLite** session_factory (matching the existing test fixture pattern in tests/integration/)
4. Construct minimal NCPDP B1 wire payload bytes
5. Call `await listener._handle_connection(reader, writer)` directly with constructed `asyncio.StreamReader`/`StreamWriter` pair
6. Assert: response bytes parse as valid NCPDP B1 response
7. Assert: `InMemoryEventBus.published` contains exactly one envelope with `event_type == "claim.adjudicated"`
8. Assert: envelope payload has `nadac_per_unit=None`, `wac_per_unit=None`, `awp_per_unit=None`, `awp_basis="NONE"` (default-dict path)
9. Assert: envelope `tenant_id` matches env-override

**Optional second test (real-Postgres variant â€” IS skippable):**
- Same flow but `FDB_PRICING_ENRICHMENT_ENABLED=true` + real `DATABASE_URL_SYNC` reachable
- `@pytest.mark.skipif(not os.environ.get("DATABASE_URL_SYNC"), reason="real DB required")`
- Asserts FDB pricing fields populated with real values

**Verification:**
- New test passes locally (publish-capture variant always runs)
- adjudication-engine pass-count = baseline + 1 (or +2 if both variants run)

**Commit:** `test(adjudication-engine/p11b): F2 C5 integration test â€” tcp_listener publishes claim.adjudicated via InMemoryEventBus capture`

---

### C6 â€” Documentation + memory + ship artifacts

**Files:**
1. `modules/drug-database/README.md` â€” "Package layout" section: post-B8 the package is `drug_database/` (was `src/`); cross-module consumers `from drug_database.X import ...`
2. `~/.claude/projects/.../memory/project_phase11a_decision.md` â€” append "11B IMPLEMENTED 2026-05-10" status block
3. `~/.claude/projects/.../memory/project_phase11b_implemented.md` â€” NEW canonical record
4. `~/.claude/projects/.../memory/MEMORY.md` â€” add "Phase 11B IMPLEMENTED â€” wave B8" line
5. `waves/B8/evidence.md` â€” defects fixed mid-wave, codex iteration summary, baseline-vs-final test comparison
6. `waves/B8/ship.md` â€” commit hash chain, final state, residuals
7. `docs/audit/wave-history.md` â€” add B8 row

**Commit:** `docs(p11b/p11b-close): F1+F2 IMPLEMENTED â€” README + memory + wave-history`

---

## Goal-backward verification (per SC)

| SC | Verified by | Commit |
|---|---|---|
| SC-1 | `python -c "from drug_database.services.composite_pricing ..."` from `modules/drug-database/` AND repo root | C1 |
| SC-2 | grep zero hits for `from src.services.(composite_pricing|fdb_|nppes_|pricing|fda_supplementary|pricing_ingestion)` repo-wide outside drug-database | C2 |
| SC-3 | drug-database pytest pass-count â‰¥ baseline | C3 |
| SC-4 | adjudication-engine pytest pass-count â‰¥ baseline | C3 |
| SC-5 | reclaimrx pytest pass-count â‰¥ baseline | C3 |
| SC-5b (NEW) | shared/data_ingestion pytest pass-count â‰¥ baseline (added per scope expansion) | C3 |
| SC-6 | tcp_listener.py:_process calls `build_claim_adjudicated_event` + `bus.publish` after `persist_claim_transaction` returns `txn`, in try/except capturing `txn_id`, inside set_tenant_context | C4 |
| SC-7 | New integration test passes; InMemoryEventBus captures published envelope with FDB fields (None-default values acceptable) | C5 |
| SC-8 | Codex GATE-CLOSE consult result | post-C5 |
| SC-9 | evidence.md + ship.md + memory entries land | C6 |

---

## Threat model

| # | Failure mode | Detection | Recovery |
|---|---|---|---|
| T1 | Sed regex misses an indented or multi-line import | C1 verification grep returns hits | Add additional sed pass; re-verify |
| T2 | Sed regex over-matches (e.g., a string literal `"from src.X"`) | drug-database test suite fails on import-time | Manual fix the false positive; pytest collection error pinpoints |
| T3 | setuptools `packages.find` doesn't pick up subpackages | `uv sync` succeeds but `from drug_database.services.X` fails | Fall back to explicit packages list with all subpackages enumerated |
| T4 | adjudication-engine tests fail because cross-module path setup differs in test vs runtime | C3 catches | Add sys.path injection in adjudication-engine conftest; OR add `[tool.uv.workspace]` member |
| T5 | shared/data_ingestion tests fail because they have OWN sys.path conftest that assumed `src.X` | C3 catches | Update each affected conftest |
| T6 | F2 publish blocks TCP response | Integration test asserts timing if needed (not currently in scope) | Existing try/except already non-blocking |
| T7 | InMemoryEventBus not properly reset between tests | Test pollution / flaky failures | Use pytest fixture scope=function with bus reset in teardown |
| T8 | `_handle_connection` requires a real socket pair, not a writable mock | TypeError at test time | Use `asyncio.start_server` on `127.0.0.1:0` in fixture, then `asyncio.open_connection` from test |
| T9 | sed touches `shared/tests/events/test_cross_module_events.py` (which references reclaimrx's src.events) | C2 over-match safety check | C2 is scoped to explicit file list, not wildcard â€” that file is NOT in the list |

---

## Codex iteration plan

| Gate | Round budget | Status |
|---|---|---|
| SPEC | 2 rounds | DONE â€” round 2 GO-WITH-FIXES, all 5 concerns absorbed in charter v3 |
| PLAN | â‰¤2 rounds | round 1 DONE â€” GO-WITH-FIXES, 8 concerns absorbed in plan v2; round 2 OPTIONAL â€” proceeding without if no NO-GO |
| ADVERSARIAL | â‰¤2 rounds | TBD post-plan-v2 |
| GATE-CLOSE | 1 round | TBD post-execute |

---

## Out of plan (reaffirmed deferrals)

- B7.1 backlog (NPPES monthly, C9 parity, ifx_prod_app)
- B9 (FDB NDDF Plus 220-table)
- Loader CLI rc propagation
- `core` schema cleanup
- Refactoring `from src.X` patterns inside reclaimrx, billing, paysync (those are intra-module)
- Reorganizing drug-database internal subdirectory layout

 succeeded in 495ms:
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
session id: 019e1874-cc66-7ea2-a9cb-a191aef7c85a
--------
user
You are codex acting as the SPEC GATE reviewer for the InfinityRx platform's Wave B9 charter, round 2.

## Context

Wave B9 = "FDB NDDF Plus 220-table extension". Recon was completed 2026-05-11 (`recon.md`). Charter v1 was dispatched for SPEC R1. You returned **GO-WITH-FIXES** with 6 substantive concerns (1 HIGH effort model, 2 HIGH process gates, 3 MEDIUM SPEC tightenings, 1 LOW vendor-name pass). The owner produced charter v2 which claims to absorb all 6 concerns. Your job in R2 is to verify whether v2 actually addresses each concern, and either issue **GO** (proceed to PLAN), **GO-WITH-FIXES** (one more revision needed), or **NO-GO** (structural problem).

## Artifacts (read these from disk)

1. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\recon.md` â€” scope ground truth (328 lines)
2. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md` â€” charter v2, the document you are reviewing (115 lines)
3. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\codex-spec-consult-r1.md` â€” your R1 verdict that v2 is responding to (120 lines)

## R1 concerns to verify in v2 (use these as your checklist)

| # | Sev | R1 concern | What v2 must show |
|---|---|---|---|
| 1 | HIGH | Single final GATE-CLOSE too late for 220 tables | Per-phase mini-GATE-CLOSE gates between B9.B..B9.G with explicit closure criteria |
| 2 | HIGH | D2 reversal needs real perf gate, not just disk check | C0 perf gate with timed full-load dry run for RNP2 + RPRDPP0, EXPLAIN ANALYZE, weekly delta timing |
| 3 | HIGH | Effort model contradicts recon (100 vs 34/39 sessions) | Charter explains the number consistent with recon's A+B+C+D estimate; no unexplained inflation |
| 4 | MED | MTL schema-only â€” DO NOT config-gate Alembic; guard at loader+config | Schema migration unconditional; runtime/loader/config guards prevent data load; CI test asserts zero MTL rows |
| 5 | MED | Migration granularity must be SPEC-locked, not deferred to plan | No 1-per-table, no 1-mega; per-phase batched migrations specified; RNDC14 standalone |
| 6 | MED | SC-8 test strategy underspecified | Contract + parity + reconciliation + sampled behavioral + dedicated Tier C tests; no 217 bespoke per-table tests |

## Verdict format (match this exactly)

```
## SPEC R2 GATE VERDICT

<GO | GO-WITH-FIXES | NO-GO>

## R1 concern verification

| # | R1 fix | Verified in v2? | Evidence (charter line ref) | Notes |
|---|---|---|---|---|
| 1 | Per-phase gates | YES / PARTIAL / NO | <line refs> | <short> |
| 2 | D2 perf gate | YES / PARTIAL / NO | <line refs> | <short> |
| 3 | Effort model | YES / PARTIAL / NO | <line refs> | <short> |
| 4 | MTL guards | YES / PARTIAL / NO | <line refs> | <short> |
| 5 | Migration granularity | YES / PARTIAL / NO | <line refs> | <short> |
| 6 | Test strategy | YES / PARTIAL / NO | <line refs> | <short> |

## New concerns surfaced in v2 (if any)

<list with severity, or "None">

## Vendor-name sanity check

<PASS / FAIL with grep evidence>

## Final verdict + next action

<one paragraph: if GO â†’ proceed to PLAN v1 codex consult; if GO-WITH-FIXES â†’ list required fixes; if NO-GO â†’ explain structural problem>
```

Be rigorous. If a fix is incomplete or papered-over, mark PARTIAL and require revision. Do not GO unless all 6 fixes are verifiable at specific charter line refs and vendor-name check passes.
codex
Iâ€™ll review the three wave artifacts directly and compare charter v2 against the R1 checklist. Iâ€™ll also run a vendor-name grep over the B9 docs so the verdict is grounded in exact line references.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING charter.md' }" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$dir='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9'; if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" "'$dir } else { Get-ChildItem -LiteralPath $dir -File | Select-String -Pattern '"'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-spec-consult-r1.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING codex-spec-consult-r1.md' }" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING recon.md' }" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING charter.md' }"` rejected: blocked by policy
2026-05-11T19:13:02.640884Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING charter.md' }"` rejected: blocked by policy
2026-05-11T19:13:02.641476Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-spec-consult-r1.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING codex-spec-consult-r1.md' }"` rejected: blocked by policy
2026-05-11T19:13:02.641827Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$dir='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9'; if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" "'$dir } else { Get-ChildItem -LiteralPath $dir -File | Select-String -Pattern '"'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$dir='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9'; if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" "'$dir } else { Get-ChildItem -LiteralPath $dir -File | Select-String -Pattern '"'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-spec-consult-r1.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING codex-spec-consult-r1.md' }"` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING recon.md' }"` rejected: blocked by policy
2026-05-11T19:13:02.642113Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; if (Test-Path -LiteralPath "'$p) { $i=0; Get-Content -LiteralPath $p | ForEach-Object { $i++; '"'{0,4}: {1}' -f "'$i, $_ } } else { '"'MISSING recon.md' }"` rejected: blocked by policy
codex
The first read attempt was rejected by the local command policy, likely because of the absolute path quoting pattern. Iâ€™m going to retry with simpler PowerShell commands from the B9 directory so I can still produce the requested line-specific review.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command Get-Location in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 322ms:

Path                                                            
----                                                            
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform



exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-ChildItem -Name' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 succeeded in 326ms:
charter.md
codex-spec-consult-r1.md
codex-spec-consult-r2.md
recon.md

2026-05-11T19:13:19.725691Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\recon.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\recon.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\charter.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\recon.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\charter.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
2026-05-11T19:13:19.726471Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\charter.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
2026-05-11T19:13:19.732365Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\codex-spec-consult-r1.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\codex-spec-consult-r1.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=0; Get-Content .'"\\codex-spec-consult-r1.md | ForEach-Object { "'$i++; '"'{0,4}: {1}' -f "'$i, $_ }'` rejected: blocked by policy
2026-05-11T19:13:19.767559Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" . } else { Get-ChildItem -File | Select-String -Pattern 'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" . } else { Get-ChildItem -File | Select-String -Pattern 'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "if (Get-Command rg -ErrorAction SilentlyContinue) { rg -n -i \"First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14\" . } else { Get-ChildItem -File | Select-String -Pattern 'First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14' -CaseSensitive:"'$false }'` rejected: blocked by policy
codex
Listing the directory works, but the policy is rejecting compound PowerShell pipelines. I have the artifacts present, so Iâ€™ll switch to very simple reads/searches and add line numbers from the file content manually.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content charter.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 succeeded in 332ms:
# Wave B9 Ã¢â‚¬â€ FDB NDDF Plus 220-table extension (full scope)

**Status:** SPEC v2 (codex SPEC R1 GO-WITH-FIXES Ã¢â€ â€™ 6 substantive concerns absorbed; R2 to confirm)
**Recon:** `recon.md` (2026-05-11) Ã¢â‚¬â€ verified scope and effort
**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
**Authority:** Project owner locked 4 scope decisions 2026-05-11 (this document captures them)

---

## Goal

Extend FDB NDDF Plus ingest from current **3 tables Ã¢â€ â€™ all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.

## Locked decisions (2026-05-11)

| # | Decision | Rationale |
|---|---|---|
| D1 | **RNDC14 = full 68-column ingest** | Future-proof; avoids N+1 schema-extension waves as consumers surface column needs. |
| D2 | **RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE = include + load by default** | Reverses Phase 09 `fdb_load_product_prices=False` deferral. +1.16 GB storage required; needs disk + Postgres performance verification at C0. |
| D3 | **Medical Test Lexicon (MTL) = schema-only, no data load** | Honors "clinical screening NOT subscribed" memory while landing table structure for future activation. 19 tables, 103 KB raw. If licensing changes, flip a config flag. |
| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~34 four-hour sessions elapsed; ~6 months wall-clock. |

## Workstreams (recon-validated effort)

| W | Scope | Tables | Effort (recon line 14 + sections 6/7) |
|---|---|---|---|
| W1 | Tier A Ã¢â‚¬â€ simple lookups (Ã¢â€°Â¤5 columns, generic ingester) | 113 | ~10 sessions |
| W2 | Tier B Ã¢â‚¬â€ NDC/GCN-keyed joins | 66 | ~12 sessions |
| W3 | Tier C Ã¢â‚¬â€ complex/large + RNDC14 full + RNP2 + RPRDPP0 + perf gate | 19 | ~10 sessions (8 baseline + ~2 D2 perf gate) |
| W4 | Tier D Ã¢â‚¬â€ MTL schema-only (no data load) | 19 | ~3 sessions |
| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |

**Total: ~39 sessions** (recon's A+B+C estimate is 34; +3 Tier D + ~2 D2 perf gate = 39). With codex review cadence already baked into per-phase budget. **Charter v1's 100-session figure was a misread; v2 corrects to recon's actual numbers.** Wall-clock at 3 sessions/week: ~13 weeks (~3 months).

## Out of scope (deferred)

- Clinical screening DATA ingest (only schema lands per D3)
- B8.2 followups (build_response docstring already shipped `1c28e44`)
- 134 pre-existing test failures (forensic wave)
- Phase 4 forward feature work

## Phased execution + per-phase closure gates (HIGH #1 codex fix)

B9 ships incrementally **with mandatory per-phase closure gates** Ã¢â‚¬â€ each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.

| Phase | Sub-scope | Sessions | Closure gate |
|---|---|---|---|
| B9.A | Charter v2 + plan v1 + codex SPEC R2 / PLAN / ADVERSARIAL | 2-3 | Plan v1 locked |
| B9.B | Tier A Ã¢â‚¬â€ 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** Ã¢â‚¬â€ evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
| B9.C | Tier B Ã¢â‚¬â€ 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** Ã¢â‚¬â€ same scope + per-tier sampled behavioral tests |
| B9.D | Tier C non-RNDC14 Ã¢â‚¬â€ 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** Ã¢â‚¬â€ column-by-column model review |
| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** Ã¢â‚¬â€ perf test results + EXPLAIN ANALYZE + storage budget verification |
| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** Ã¢â‚¬â€ integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
| B9.H | Manifest extension (66 Ã¢â€ â€™ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** Ã¢â‚¬â€ full cross-tier consult |

## Success criteria

| SC | Description |
|---|---|
| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Ã‚Â± documented tolerance (MTL excluded Ã¢â‚¬â€ schema-only) |
| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
| SC-5 | MTL schema lands but **runtime/loader guards** prevent data load: `fdb_load_mtl=False` default; MTL tables excluded from default loader registry; integration test asserts **zero MTL rows** after default `load_fdb.py --mode fdb_weekly`. Alembic migration itself is NOT config-gated (per codex SPEC R1 #4). |
| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
| SC-7 | Weekly delta ingest path idempotent across all 220 tables (ON CONFLICT DO NOTHING or UPSERT per table; verified by re-running) |
| SC-8 | **Test coverage strategy** (per codex SPEC R1 #6): contract coverage for every `TableSpec`; schema/model parity for every table; row-count reconciliation for every loaded table; sampled behavioral tests per tier; dedicated Tier C tests for RNDC14 / RNP2 / RPRDPP0 / weekly delta. **No bespoke per-table behavioral tests** for the 217 tables Ã¢â‚¬â€ too heavy. |
| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
| SC-11 | Evidence + ship + memory + wave-history + B9 phased-progress dashboard |

## SPEC-locked migration granularity (codex SPEC R1 #5 fix)

**Migration granularity is SPEC-locked**, not deferred to plan:
- **NO** one-table-per-migration (213 migrations would be unmaintainable)
- **NO** single 217-table migration (atomicity ruined; review intractable)
- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) Ã¢â‚¬â€ 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE

## Risks

| # | Risk | Mit |
|---|---|---|
| R1 | 217 alembic migrations is unwieldy for review | SPEC-locked above to ~6 per-phase batched migrations + RNDC14 standalone. |
| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
| R3 | RNDC14 68 columns include latin-1 quirks (mixed-case names, accented chars, NULL sentinels) | Per-column normalization pass in ingester; latin-1 Ã¢â€ â€™ UTF-8 with replacement strategy documented |
| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
| R6 | 6-month wall-clock invites scope drift / charter decay | Phased execution table is contract; each phase has explicit closure gate |
| R7 | MTL schema accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via integration test; CI gate denies MTL data on default flag |

## Discipline

- **codex SPEC consult:** 1-3 rounds against this charter (full discipline restored given scope size)
- **codex PLAN consult:** 1-2 rounds against plan v1
- **ADVERSARIAL:** 2-3 rounds (large surface, novel scope, $11.96+ codex cost expected)
- **codex GATE-CLOSE:** 1-2 rounds at wave close (and possibly per-phase mini-closes)

## Estimated wall-clock (v2 corrected)

**~39 sessions Ãƒâ€” 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong Ã¢â‚¬â€ corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)

## Note on scope vs recon recommendation

The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification Ã¢â‚¬â€ preserving B7-style checkpoint cadence inside the single B9 milestone.

---

## Resume next session

1. `/werkbench`
2. Read this charter
3. Codex SPEC consult round 1 (against this v1)
4. Iterate to GO; then plan v1

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -i "First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14|100-session|34|39|mini-GATE|GATE-CLOSE|EXPLAIN ANALYZE|bespoke|migration" charter.md codex-spec-consult-r1.md recon.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
 succeeded in 738ms:
charter.md:1:# Wave B9 â€” FDB NDDF Plus 220-table extension (full scope)
charter.md:5:**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
charter.md:12:Extend FDB NDDF Plus ingest from current **3 tables â†’ all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.
charter.md:18:| D1 | **RNDC14 = full 68-column ingest** | Future-proof; avoids N+1 schema-extension waves as consumers surface column needs. |
charter.md:19:| D2 | **RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE = include + load by default** | Reverses Phase 09 `fdb_load_product_prices=False` deferral. +1.16 GB storage required; needs disk + Postgres performance verification at C0. |
charter.md:20:| D3 | **Medical Test Lexicon (MTL) = schema-only, no data load** | Honors "clinical screening NOT subscribed" memory while landing table structure for future activation. 19 tables, 103 KB raw. If licensing changes, flip a config flag. |
charter.md:21:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~34 four-hour sessions elapsed; ~6 months wall-clock. |
charter.md:29:| W3 | Tier C â€” complex/large + RNDC14 full + RNP2 + RPRDPP0 + perf gate | 19 | ~10 sessions (8 baseline + ~2 D2 perf gate) |
charter.md:30:| W4 | Tier D â€” MTL schema-only (no data load) | 19 | ~3 sessions |
charter.md:33:**Total: ~39 sessions** (recon's A+B+C estimate is 34; +3 Tier D + ~2 D2 perf gate = 39). With codex review cadence already baked into per-phase budget. **Charter v1's 100-session figure was a misread; v2 corrects to recon's actual numbers.** Wall-clock at 3 sessions/week: ~13 weeks (~3 months).
charter.md:39:- 134 pre-existing test failures (forensic wave)
charter.md:44:B9 ships incrementally **with mandatory per-phase closure gates** â€” each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
charter.md:49:| B9.B | Tier A â€” 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** â€” evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
charter.md:50:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests |
charter.md:51:| B9.D | Tier C non-RNDC14 â€” 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
charter.md:52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** â€” column-by-column model review |
charter.md:53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** â€” perf test results + EXPLAIN ANALYZE + storage budget verification |
charter.md:54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** â€” integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
charter.md:55:| B9.H | Manifest extension (66 â†’ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** â€” full cross-tier consult |
charter.md:61:| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
charter.md:63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
charter.md:64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
charter.md:65:| SC-5 | MTL schema lands but **runtime/loader guards** prevent data load: `fdb_load_mtl=False` default; MTL tables excluded from default loader registry; integration test asserts **zero MTL rows** after default `load_fdb.py --mode fdb_weekly`. Alembic migration itself is NOT config-gated (per codex SPEC R1 #4). |
charter.md:68:| SC-8 | **Test coverage strategy** (per codex SPEC R1 #6): contract coverage for every `TableSpec`; schema/model parity for every table; row-count reconciliation for every loaded table; sampled behavioral tests per tier; dedicated Tier C tests for RNDC14 / RNP2 / RPRDPP0 / weekly delta. **No bespoke per-table behavioral tests** for the 217 tables â€” too heavy. |
charter.md:69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
charter.md:70:| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
charter.md:73:## SPEC-locked migration granularity (codex SPEC R1 #5 fix)
charter.md:75:**Migration granularity is SPEC-locked**, not deferred to plan:
charter.md:76:- **NO** one-table-per-migration (213 migrations would be unmaintainable)
charter.md:77:- **NO** single 217-table migration (atomicity ruined; review intractable)
charter.md:78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
charter.md:79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) â€” 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
charter.md:85:| R1 | 217 alembic migrations is unwieldy for review | SPEC-locked above to ~6 per-phase batched migrations + RNDC14 standalone. |
charter.md:86:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
charter.md:87:| R3 | RNDC14 68 columns include latin-1 quirks (mixed-case names, accented chars, NULL sentinels) | Per-column normalization pass in ingester; latin-1 â†’ UTF-8 with replacement strategy documented |
charter.md:88:| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
charter.md:91:| R7 | MTL schema accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via integration test; CI gate denies MTL data on default flag |
charter.md:98:- **codex GATE-CLOSE:** 1-2 rounds at wave close (and possibly per-phase mini-closes)
charter.md:102:**~39 sessions Ã— 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong â€” corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
codex-spec-consult-r1.md:4:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:53:| B9.F | Tier D â€” MTL 
codex-spec-consult-r1.md:8:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:55:| Codex GATE-CLOSE | 
codex-spec-consult-r1.md:11:currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
codex-spec-consult-r1.md:12:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:64:| SC-4 | RNP2 + 
codex-spec-consult-r1.md:13:RPRDPP0 ingest succeeds end-to-end; storage stays within disk budget; query performance acceptable on indexed columns |
codex-spec-consult-r1.md:17:ingest path: re-running `load_fdb.py --mode fdb_weekly` is idempotent across all 220 tables (ON CONFLICT DO NOTHING or 
codex-spec-consult-r1.md:20:migrations is unwieldy for review | Plan v1 decides: 1-per-tier OR batched migration (e.g., 1 migration per 25 
codex-spec-consult-r1.md:22:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:77:| R2 | RNP2 + RPRDPP0 
codex-spec-consult-r1.md:25:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:82:| R7 | MTL schema 
codex-spec-consult-r1.md:26:accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via 
codex-spec-consult-r1.md:27:integration test; CI gate denies MTL data on default flag |
codex-spec-consult-r1.md:41:1. **HIGH â€” B9 is too large for a single final GATE-CLOSE.**  
codex-spec-consult-r1.md:42:   D4 can remain â€œsingle B9 milestone,â€ but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
codex-spec-consult-r1.md:45:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. â€œDisk free + pg_stat_user_tables monitoringâ€ is not enough for reversing the Phase 09 1.16 GB deferral.
codex-spec-consult-r1.md:48:   The charter says reconâ€™s 34-session estimate was â€œTier A only,â€ but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
codex-spec-consult-r1.md:50:4. **MEDIUM â€” MTL schema-only needs stronger wording, but not config-gated Alembic.**  
codex-spec-consult-r1.md:51:   Schema migrations should not be config-gated if landing schema is the explicit decision. The guard should be in loader registration and runtime config: MTL tables excluded from default load scopes, `fdb_load_mtl=False` default, explicit opt-in required, and integration tests assert zero MTL rows after default `load_fdb.py --mode fdb_weekly`.
codex-spec-consult-r1.md:53:5. **MEDIUM â€” Migration granularity should be constrained at SPEC.**  
codex-spec-consult-r1.md:54:   Deferring entirely to plan v1 is too loose. SPEC should mandate no one-table-per-migration and no single 217-table migration. Recommended: per phase/batch migrations, with RNDC14 dedicated or isolated inside Tier C due to 68-column review complexity.
codex-spec-consult-r1.md:57:   Do not require bespoke per-table tests for 217 tables. Do require generated/contract coverage for every `TableSpec`, schema/model parity for every table, row-count reconciliation for every loaded table, sampled behavioral tests per tier, and dedicated Tier C tests for RNDC14/pricing/weekly delta.
codex-spec-consult-r1.md:64:The 7-phase split is the right internal shape if D4 remains locked. Tiering by complexity is coherent, and B9.E correctly isolates RNDC14 plus the two large pricing tables.
codex-spec-consult-r1.md:66:D1 is cleanly stated. Full RNDC14 ingest avoids repeated schema churn.
codex-spec-consult-r1.md:68:D3â€™s licensing boundary is directionally right: MTL schema can land while data load remains disabled.
codex-spec-consult-r1.md:76:Revise charter v2 before PLAN. Required fixes: correct the recon/session-count contradiction, add a D2 performance gate, make per-phase closure gates mandatory, strengthen MTL loader safeguards, and lock migration granularity constraints at SPEC level. After that, proceed to PLAN v1.
codex-spec-consult-r1.md:85:1. **HIGH â€” B9 is too large for a single final GATE-CLOSE.**  
codex-spec-consult-r1.md:86:   D4 can remain â€œsingle B9 milestone,â€ but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
codex-spec-consult-r1.md:89:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. â€œDisk free + pg_stat_user_tables monitoringâ€ is not enough for reversing the Phase 09 1.16 GB deferral.
codex-spec-consult-r1.md:92:   The charter says reconâ€™s 34-session estimate was â€œTier A only,â€ but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
codex-spec-consult-r1.md:94:4. **MEDIUM â€” MTL schema-only needs stronger wording, but not config-gated Alembic.**  
codex-spec-consult-r1.md:95:   Schema migrations should not be config-gated if landing schema is the explicit decision. The guard should be in loader registration and runtime config: MTL tables excluded from default load scopes, `fdb_load_mtl=False` default, explicit opt-in required, and integration tests assert zero MTL rows after default `load_fdb.py --mode fdb_weekly`.
codex-spec-consult-r1.md:97:5. **MEDIUM â€” Migration granularity should be constrained at SPEC.**  
codex-spec-consult-r1.md:98:   Deferring entirely to plan v1 is too loose. SPEC should mandate no one-table-per-migration and no single 217-table migration. Recommended: per phase/batch migrations, with RNDC14 dedicated or isolated inside Tier C due to 68-column review complexity.
codex-spec-consult-r1.md:101:   Do not require bespoke per-table tests for 217 tables. Do require generated/contract coverage for every `TableSpec`, schema/model parity for every table, row-count reconciliation for every loaded table, sampled behavioral tests per tier, and dedicated Tier C tests for RNDC14/pricing/weekly delta.
codex-spec-consult-r1.md:108:The 7-phase split is the right internal shape if D4 remains locked. Tiering by complexity is coherent, and B9.E correctly isolates RNDC14 plus the two large pricing tables.
codex-spec-consult-r1.md:110:D1 is cleanly stated. Full RNDC14 ingest avoids repeated schema churn.
codex-spec-consult-r1.md:112:D3â€™s licensing boundary is directionally right: MTL schema can land while data load remains disabled.
codex-spec-consult-r1.md:120:Revise charter v2 before PLAN. Required fixes: correct the recon/session-count contradiction, add a D2 performance gate, make per-phase closure gates mandatory, strengthen MTL loader safeguards, and lock migration granularity constraints at SPEC level. After that, proceed to PLAN v1.
recon.md:5:**Goal:** Scope FDB NDDF Plus 220-table extension beyond the 3-table Phase 09 baseline
recon.md:11:- The FDB drop contains exactly **220 data tables** in `NDDF Plus DB/NDDF PLUS DB.zip`, all with matching ANSI DDL. The current ingester covers **3 tables** (RNP3\_NDC\_PRICE, RPRDPTD0\_PRICE\_TYPE\_DESC, RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC) mapped to **2 DB tables** (`fdb_ndc_price_history`, `fdb_price_type_desc`). Gap: **217 tables**.
recon.md:12:- Tables span six FDB modules: NDDF BASICS 3.0 (98 tables), MEDNAMES 3.0 (63), ETC 1.0 (16), TALL MAN PLUS 2.0 (15), XRF 1.0 (9), MTL 1.0 (19). MTL (Medical Test Lexicon) is the only module without a clear adjudication use case â€” treat as a product decision.
recon.md:13:- The generic `TableSpec`-driven adapter (`FDBLocalDropAdapter.parse_table`) already works for any pipe-delimited FDB table. The ingest architecture is **extension-ready**: new tables become new `TableSpec` constants + SQLAlchemy models + a migration, no adapter surgery required.
recon.md:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
recon.md:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion â€” this is a one-time setup change, not per-deployment.
recon.md:16:- Two Tier C tables dominate storage risk: `RNP2_NDC_PRICE` (595 MB uncompressed, 13.2M rows) and `RPRDPP0_PRODUCT_PRICE` (561 MB). Both are pricing variants already noted in the Phase 09 ingester as deferred. Ingesting them requires an explicit go/no-go decision before B9.2.
recon.md:17:- The `RNDC14_NDC_MSTR` table (68 columns, 183 MB, ~501K rows) is the platform's most valuable single gap target â€” it is the canonical FDB NDC master containing labeler, brand name, GCDF, route, DEA schedule, packaging, and product status fields that adjudication, formulary, and reclaimrx all need.
recon.md:21:## Section 1 â€” FDB drop inventory
recon.md:23:**Drop location:** `data/reference/fdb/TEL251759D/`
recon.md:34:FDB_CLINICAL_HIGHLIGHTS.ZIP        <- clinical screening, NOT subscribed
recon.md:35:NDDF Plus DB/NDDF PLUS DB.zip      <- 220 data table files (pipe-delimited, latin-1)
recon.md:36:NDDF Plus DDL/NDDF PLUS DDL.zip    <- 46 DDL files (ANSI, Oracle, SQL Server, Sybase)
recon.md:37:NDDF Plus UPD/NDDF PLUS UPD.zip    <- weekly delta (A/C/D prefixed rows)
recon.md:38:NDDF_PRODUCT_INFO.TXT              <- single-line YYYYMMDD data cutoff date
recon.md:44:- ANSI DDL `CREATE TABLE` statements: **220** (+ 1 meta: `NDDF_PRODUCT_INFO`)
recon.md:48:**FDB module breakdown:**
recon.md:52:| NDDF BASICS 3.0 / Generic Formulation and Ingredient | 50 | GCN, GCNSEQNO, HIC, strength, route, dosage form |
recon.md:53:| NDDF BASICS 3.0 / Packaged Product | 30 | NDC master, FDA application, OBC, labeler |
recon.md:54:| NDDF BASICS 3.0 / Pricing | 11 | RNP2, RNP3, RPRDPP0, price attr |
recon.md:55:| NDDF BASICS 3.0 / Miscellaneous Therapeutic Class | 7 | AHFS, ATC, HIC therapeutic class |
recon.md:56:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
recon.md:57:| NDDF ETC 1.0 | 16 | Enhanced Therapeutic Classification hierarchy |
recon.md:58:| NDDF XRF 1.0 | 9 | Clinical quantity crossrefs, script QQ |
recon.md:60:| NDDF MTL 1.0 | 19 | Medical Test Lexicon â€” separate domain |
recon.md:66:| RNDC14\_NDC\_MSTR | 68 | 183 MB | NDC, labeler, GCN, brand, DEA, packaging |
recon.md:67:| RNP2\_NDC\_PRICE | 4 | 595 MB | NDC, price\_type, effective\_date, price |
recon.md:68:| RPRDPP0\_PRODUCT\_PRICE | 7 | 561 MB | product, price\_type, effective\_date, price, currency |
recon.md:70:| RETCTBL0\_ETC\_ID | 12 | 348 KB | ETC\_ID, name, leaf flag, parent, hierarchy level |
recon.md:71:| RMTLLAB0\_LAB\_ID | 5 | 6 KB | LAB\_ID, description, analyte, specimen, type |
recon.md:74:**RECORD\_COUNTS.TXT:** Present, contains row count for every table name in the drop (verified counts align with zip). Example: `RNPALL|013213617` (all pricing rows), `RNDC14_NDC_MSTR` implied by `RNDCALL|000501107`.
recon.md:80:**Python files covering FDB:**
recon.md:84:| `modules/drug-database/drug_database/services/fdb_adapter.py` | Generic adapter + 4 TableSpec constants |
recon.md:85:| `modules/drug-database/drug_database/services/fdb_pricing.py` | Point-in-time pricing lookup (SWP/SWD/WAC) |
recon.md:86:| `modules/drug-database/drug_database/services/fdb_pricing_ingester.py` | Orchestration: price\_type\_desc + RNP3 ingest |
recon.md:87:| `modules/drug-database/drug_database/models/fdb_pricing_tables.py` | 2 ORM models |
recon.md:88:| `modules/drug-database/alembic/versions/0008_fdb_pricing.py` | 1 migration covering 2 tables |
recon.md:89:| `scripts/load_fdb.py` | CLI entry point (registered in run\_reference\_loaders.sh) |
recon.md:91:**Currently ingested FDB tables â†’ DB tables:**
recon.md:93:| FDB Table | DB Table | Notes |
recon.md:95:| RNP3\_NDC\_PRICE | `drug_database.fdb_ndc_price_history` | 13.2M rows; append-only, A/C/D UPD semantics |
recon.md:96:| RPRDPTD0\_PRICE\_TYPE\_DESC | `drug_database.fdb_price_type_desc` | 20 rows; modern catalog |
recon.md:97:| RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC | `drug_database.fdb_price_type_desc` | 21 rows; legacy codes with synthetic IDs |
recon.md:99:**Coverage gap: 217 of 220 FDB tables have no DB mapping.**
recon.md:103:| FDB Table | Cols | Rows (RECORD\_COUNTS) | Business value |
recon.md:105:| RNDC14\_NDC\_MSTR | 68 | ~501K | NDC master â€” labeler, brand, GCN, route, DEA, packaging |
recon.md:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
recon.md:123:- **Tier C** â€” Complex tables: > 8 columns, or large pricing tables (> 50 MB), or key structural masters (RNDC14 at 68 cols). Require careful column mapping, money-path review (financial-precision.md), or parent-key join design with existing ingested tables.
recon.md:124:- **Tier D** â€” Medical Test Lexicon (MTL 1.0). 19 tables covering lab analytes, panels, specimen IDs. Structurally simple (most are tiny) but the business question â€” do adjudication rules need lab linkage? â€” must be answered before ingest design begins.
recon.md:130:| C â€” Complex/large | 19 | 90 min | 28.5h | RNDC14 (68 cols), two 500 MB+ pricing tables, ETC master |
recon.md:131:| D â€” MTL (product decision) | 19 | 30 min | 9.5h | Small tables, pending go/no-go |
recon.md:138:| RNDC14\_NDC\_MSTR | 68 | 183 MB | Highest value; complex column mapping |
recon.md:139:| RNP2\_NDC\_PRICE | 4 | 595 MB | Pricing variant; go/no-go needed (Phase 09 deferred) |
recon.md:140:| RPRDPP0\_PRODUCT\_PRICE | 7 | 561 MB | Product-level pricing; Phase 09 deferred |
recon.md:141:| RPRD0\_PRODUCT | 7 | 32 MB | Product master; load before RNDC14 |
recon.md:147:| RETCTBL0\_ETC\_ID | 12 | 348 KB | ETC hierarchy master |
recon.md:166:| A â€” One big migration | All 217 tables in `0009_fdb_full.py` | REJECTED â€” one migration failure blocks everything; impossible to review |
recon.md:167:| B â€” One migration per tier | 4 migrations (0009â€“0012) | Reasonable for small projects; still 66+ models per migration |
recon.md:168:| C â€” One migration per table | 217 migrations | Too many migration files; untenable maintenance |
recon.md:169:| D â€” Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
recon.md:171:**Recommendation: Option D â€” Tiered phasing with batch migrations.**
recon.md:173:- `0009_fdb_tier_a.py` â€” 113 Tier A tables (all small; one migration is reviewable because models are uniform 2â€“5-col descriptors)
recon.md:174:- `0010_fdb_tier_b.py` â€” 66 Tier B tables (NDC/GCN-keyed)
recon.md:175:- `0011_fdb_tier_c.py` â€” 19 Tier C tables (but RNDC14 should be its own migration `0011a` given 68-col complexity)
recon.md:176:- `0012_fdb_tier_d.py` â€” 19 MTL tables (only if product go decision is made)
recon.md:179:- Each migration maps to a sub-wave gate. If B9.2 fails QA, B9.1 is already in prod.
recon.md:180:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
recon.md:181:- Tier C needs its own slot because `RNDC14_NDC_MSTR` at 68 columns is a significant schema decision that may require discussion about which columns to retain vs. drop (storage vs. value tradeoff).
recon.md:193:| F â€” Per-table service | One `fdb_<table>_ingester.py` per table, matching Phase 09 pattern | Appropriate for Tier C tables with complex logic |
recon.md:199:The existing `TableSpec` dataclass + `FDBLocalDropAdapter.parse_table` already provides a generic parse-any-table capability. The only missing piece is:
recon.md:200:1. A `TableSpec` registry (a Python dict: `table_name â†’ TableSpec`) in `fdb_adapter.py`
recon.md:201:2. A generic `FDBBulkIngester` that iterates the registry, calling `parse_table` + bulk upsert for each
recon.md:208:- `RNDC14_NDC_MSTR` (68 cols): requires explicit column-selection decision, NDC normalization, money column handling (price-related fields), and a dedicated EXPLAIN ANALYZE runbook
recon.md:209:- `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`: pricing tables need go/no-go decision and Decimal handling audit (financial-precision.md)
recon.md:212:**For Tier D (MTL):**
recon.md:213:MTL tables are tiny (total uncompressed: ~103 KB). If the product decision is "yes", they fit cleanly into the generic ingester. If "no", skip entirely. No architectural complexity.
recon.md:239:- B9.4 (Tier D, MTL â€” if go): ~3 sessions
recon.md:241:**Total: ~34 sessions** (excluding Tier D). This is a multi-month effort at 2â€“3 sessions/week.
recon.md:249:**Risk 1 â€” RNDC14\_NDC\_MSTR column explosion (HIGH)**
recon.md:250:The NDC master has 68 columns, many of which are FDB-internal flags with unclear business relevance. Without column curation, the DB table will be bloated and the ORM model unwieldy. Risk: table design gets revisited post-ingest, requiring a costly migration. Mitigation: Before B9.3, produce a column-by-column triage (keep / drop / defer) based on adjudication, formulary, and reclaimrx requirements.
recon.md:253:`RNP2_NDC_PRICE` (595 MB, 13.2M rows legacy pricing) and `RPRDPP0_PRODUCT_PRICE` (561 MB) were explicitly deferred in Phase 09 (`fdb_load_product_prices=False` config flag). Loading both adds ~1.1 GB uncompressed to the reference DB weekly. Risk: storage growth and ingest window extension. Mitigation: Decide at B9.3 charter whether these are in scope. If yes, add dedicated EXPLAIN ANALYZE runbook.
recon.md:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
recon.md:259:Current FDB ingest: RNP3 (13.2M rows) takes ~minutes. Adding 217 tables including NDC master (501K rows), ETC NDC mapping (616K rows), and MedName tables adds significant volume to the weekly UPD cycle. The UPD zip must also be verified to contain all tables (not just pricing). Mitigation: Profile UPD zip contents against DB zip contents. Validate that `NDDF Plus UPD/` has a matching file for each table before committing to weekly ingest for all 220.
recon.md:262:The current adapter only reads from UPD for RNP3 (pricing). Some FDB reference tables (e.g., description tables) may ship full-replacement in UPD rather than A/C/D delta. Mitigation: Inspect the UPD zip structure early in B9.1. If some tables are full-replacement (no A/C/D prefix), the ingester must detect this and use TRUNCATE+INSERT rather than ON CONFLICT DO NOTHING.
recon.md:265:The existing adapter handles latin-1 decoding for RNP3 (numeric-heavy). Text-heavy tables (drug names, descriptions, brand names) are more likely to have characters in the latin-1 extended range (0x80â€“0xFF). Mitigation: Audit the first 1000 rows of text-column tables (RMIID1\_MED, RNDC14\_NDC\_MSTR brand fields) for decoding failures before schema finalization.
recon.md:268:At 217 new models, the per-test `create_all()` time in SQLite fixtures will grow. Currently 2 FDB models; adding 217 means each test session creates 219 tables. Risk: slow CI. Mitigation: Split the `FDBPricingBase` into module-level declarative bases (`FDBBasicsBase`, `FDBMedNamesBase`, etc.) so tests only create\_all for the module under test. Plan this in B9.0 before any model files are written.
recon.md:276:- Charter v1: column triage for RNDC14, pricing table go/no-go decision, MTL go/no-go decision
recon.md:277:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) â€” implementation-ready spec
recon.md:284:- Implement `FDBBulkIngester` generic infrastructure (~200 lines)
recon.md:285:- Add 113 `TableSpec` entries to registry in `fdb_adapter.py`
recon.md:286:- One alembic migration `0009_fdb_tier_a.py`
recon.md:287:- 113 ORM model classes in `fdb_lookup_tables.py` (batched by module)
recon.md:295:- Migration `0010_fdb_tier_b.py`
recon.md:296:- ORM models in `fdb_link_tables.py`
recon.md:298:- Integration test: verify NDC join correctness against existing `fdb_ndc_price_history`
recon.md:304:- Pre-work: RNDC14 column triage document (owner sign-off required before coding)
recon.md:305:- Pricing table go/no-go confirmation (RNP2, RPRDPP0)
recon.md:306:- One migration per Tier C table (or `0011_fdb_tier_c.py` + `0011a_fdb_ndc_master.py` for RNDC14 separately)
recon.md:308:- EXPLAIN ANALYZE runbook for RNDC14 and any table > 10M rows
recon.md:312:### B9.4 â€” Tier D: MTL (19 tables) â€” CONDITIONAL on product decision
recon.md:315:- All 19 MTL tables are tiny (total 103 KB) â€” one session if go decision is made
recon.md:316:- Migration `0012_fdb_tier_d.py`, generic ingester handles all 19
recon.md:322:1. **RNDC14\_NDC\_MSTR column triage**: Which of the 68 columns does InfinityRx actually need? Full 68-column ingest vs. curated subset has significant implications for model maintainability and storage. Required before B9.3 begins.
recon.md:324:2. **Pricing table go/no-go (RNP2 + RPRDPP0)**: Both were explicitly deferred in Phase 09. RNP2 is the legacy pricing file (overlaps with RNP3 data); RPRDPP0 is product-level pricing (vs. RNP3's NDC-level). Decision needed: are either of these required for adjudication accuracy, or is RNP3 sufficient?
recon.md:326:3. **MTL go/no-go**: Does any planned adjudication rule or reclaimrx detection require lab test linkage (NDDF MTL 1.0)? If yes, B9.4 is in scope. If no, all 19 MTL tables are permanently skipped.
recon.md:328:4. **Wave boundary â€” is B9 one wave or two?**: 34 sessions is 3â€“4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.

codex
## SPEC R2 GATE VERDICT

GO-WITH-FIXES

## R1 concern verification

| # | R1 fix | Verified in v2? | Evidence (charter line ref) | Notes |
|---|---|---|---|---|
| 1 | Per-phase gates | YES | charter.md:44, 49-55, 69, 106 | Mandatory mini-GATE-CLOSE gates are specified for B9.B..B9.G with evidence, reconciliation, migration review, FDW verify, test baseline comparison, and phase-specific criteria. |
| 2 | D2 perf gate | YES | charter.md:19, 53, 64, 86 | C0/B9.F now requires timed full-load dry run, `EXPLAIN ANALYZE`, FDW/Postgres verify, storage budget verification, and weekly delta timing. |
| 3 | Effort model | PARTIAL | charter.md:21, 33, 102, 106 | The 100-session error is corrected to ~39 sessions at lines 33 and 102, consistent with recon. But D4 still says â€œ~34 four-hour sessions elapsed; ~6 months wall-clockâ€ at line 21, which conflicts with the corrected 13-week / 4-5 month framing and uses â€œelapsedâ€ incorrectly. |
| 4 | MTL guards | YES | charter.md:20, 54, 65, 91 | Schema-only is preserved; Alembic is explicitly not config-gated; loader/runtime guards and zero-row integration/CI checks are required. |
| 5 | Migration granularity | YES | charter.md:73-79, 85 | SPEC locks no one-table-per-migration, no single mega-migration, per-phase batched migrations, and standalone RNDC14. |
| 6 | Test strategy | YES | charter.md:49-54, 64-69 | Contract, parity, reconciliation, sampled behavioral, and dedicated Tier C tests are specified; bespoke per-table behavioral tests are explicitly rejected. |

## New concerns surfaced in v2 (if any)

- LOW/MEDIUM â€” Stale D4 effort/wall-clock text remains at charter.md:21. It conflicts with the corrected effort model at charter.md:33 and charter.md:102. This is likely a copy-forward artifact, but SPEC should not advance with contradictory schedule language in a locked decision row.

## Vendor-name sanity check

PASS. Grep evidence shows consistent use of `FDB` / `NDDF Plus` / `NDDF`; no `FirstDataBank` casing issue surfaced in the checked B9 docs. Relevant lines include charter.md:1, charter.md:12, recon.md:5, recon.md:11, recon.md:21, recon.md:35-36.

## Final verdict + next action

GO-WITH-FIXES. v2 substantively addresses R1 concerns #1, #2, #4, #5, and #6. The only blocker is the stale D4 row at charter.md:21: replace â€œ~34 four-hour sessions elapsed; ~6 months wall-clockâ€ with language consistent with the corrected model, e.g. â€œ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4-5 months with multitasking.â€ After that cleanup, proceed to PLAN v1 codex consult.
tokens used
28,617
## SPEC R2 GATE VERDICT

GO-WITH-FIXES

## R1 concern verification

| # | R1 fix | Verified in v2? | Evidence (charter line ref) | Notes |
|---|---|---|---|---|
| 1 | Per-phase gates | YES | charter.md:44, 49-55, 69, 106 | Mandatory mini-GATE-CLOSE gates are specified for B9.B..B9.G with evidence, reconciliation, migration review, FDW verify, test baseline comparison, and phase-specific criteria. |
| 2 | D2 perf gate | YES | charter.md:19, 53, 64, 86 | C0/B9.F now requires timed full-load dry run, `EXPLAIN ANALYZE`, FDW/Postgres verify, storage budget verification, and weekly delta timing. |
| 3 | Effort model | PARTIAL | charter.md:21, 33, 102, 106 | The 100-session error is corrected to ~39 sessions at lines 33 and 102, consistent with recon. But D4 still says â€œ~34 four-hour sessions elapsed; ~6 months wall-clockâ€ at line 21, which conflicts with the corrected 13-week / 4-5 month framing and uses â€œelapsedâ€ incorrectly. |
| 4 | MTL guards | YES | charter.md:20, 54, 65, 91 | Schema-only is preserved; Alembic is explicitly not config-gated; loader/runtime guards and zero-row integration/CI checks are required. |
| 5 | Migration granularity | YES | charter.md:73-79, 85 | SPEC locks no one-table-per-migration, no single mega-migration, per-phase batched migrations, and standalone RNDC14. |
| 6 | Test strategy | YES | charter.md:49-54, 64-69 | Contract, parity, reconciliation, sampled behavioral, and dedicated Tier C tests are specified; bespoke per-table behavioral tests are explicitly rejected. |

## New concerns surfaced in v2 (if any)

- LOW/MEDIUM â€” Stale D4 effort/wall-clock text remains at charter.md:21. It conflicts with the corrected effort model at charter.md:33 and charter.md:102. This is likely a copy-forward artifact, but SPEC should not advance with contradictory schedule language in a locked decision row.

## Vendor-name sanity check

PASS. Grep evidence shows consistent use of `FDB` / `NDDF Plus` / `NDDF`; no `FirstDataBank` casing issue surfaced in the checked B9 docs. Relevant lines include charter.md:1, charter.md:12, recon.md:5, recon.md:11, recon.md:21, recon.md:35-36.

## Final verdict + next action

GO-WITH-FIXES. v2 substantively addresses R1 concerns #1, #2, #4, #5, and #6. The only blocker is the stale D4 row at charter.md:21: replace â€œ~34 four-hour sessions elapsed; ~6 months wall-clockâ€ with language consistent with the corrected model, e.g. â€œ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4-5 months with multitasking.â€ After that cleanup, proceed to PLAN v1 codex consult.

 succeeded in 494ms:
# Wave B9 â€” Execution Plan v1

**Status:** PLAN v1 DRAFT â€” pending codex PLAN consult + codex ADVERSARIAL consult.
**Predecessor:** `charter.md` v3 LOCKED (SPEC R2 GO-WITH-FIXES, stale D4 row corrected).
**Recon ground truth:** `recon.md` (2026-05-11) â€” 217 gap tables, 6 FDB modules, 4 effort tiers.
**Scope:** All 217 currently-missing FDB NDDF Plus tables (3 already covered) reach the platform as ingested or schema-only across phases B9.A â†’ B9.H.

---

## How to read this plan

PLAN v1 is the WHEN/HOW that bridges charter v3 (WHAT) to executable commits. It locks:

1. **Cross-cutting infrastructure** all phases depend on (B9.A deliverables).
2. **Per-phase scope, deliverables, success-criteria mapping, gate criteria, est sessions, commit shape** for B9.B..B9.H.
3. **Per-phase batched migration plan** (SPEC-locked at charter v3 Â§SPEC-locked migration granularity).
4. **D2 perf gate** specifics (charter SC-4).
5. **MTL loader/runtime guards** (charter SC-5; Alembic NOT config-gated).
6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
7. **Threat model + risks** synthesised from recon Â§7 and charter Â§risks.

What PLAN v1 deliberately does NOT lock:

- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
- The exact `RECORD_COUNTS.TXT` tolerance numbers (per-table; published in each phase evidence doc).
- The text of each ingester contract test (template-driven; B9.A produces the template).

---

## Pre-execute invariants (must hold before B9.A C0)

Before any B9 commit lands:

1. **B8.2 closure absorbed** â€” `1c28e44` build_response docstring shipped on develop. (Memory `project_phase11b_implemented.md`.)
2. **B7.2 Phase 11A COMPLETE** â€” `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
3. **Reference DB topology stable** â€” `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
4. **Disk budget verified** â€” `df -h` shows â‰¥ 5 GB free on the reference DB volume to absorb D2's +1.16 GB (RNP2 + RPRDPP0) plus indexes plus working space. Captured at B9.A C0.
5. **`fdb_load_product_prices` config flag still in code** â€” Phase 09 deferral flag location identified; B9.F will flip default to `True` and document.
6. **134 pre-existing test failures baseline frozen** â€” `pytest --collect-only` count captured at B9.A C0; B9 must not regress count, must not "fix" them (charter `Out of scope` row 3). Forensic wave handles these later.
7. **FDB drop manifest reachable** â€” `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon Â§1.5 verified â€” re-verify at C0).
8. **`charter.md` v3 + `recon.md` checked into Werkbench/projects/infinityrx-platform/waves/B9/** at the moment B9.A starts (commit reference required in B9.A C0 evidence).
9. **Codex consult ledger ready** â€” `codex-plan-consult-r1.md` slot reserved; `codex-adversarial-r1.md` slot reserved.

If any invariant fails, B9.A C0 stops and reports â€” do not paper over.

---

## Phased commit chain

B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).

### B9.A â€” Charter v3 close + Plan v1 close + infrastructure scaffolding (2-3 sessions)

**Scope:** This meta-phase. Lock charter v3 (DONE), draft PLAN v1 (DONE â€” this doc), pass codex PLAN consult, pass codex ADVERSARIAL consult, and ship the cross-cutting infrastructure all subsequent phases consume.

**Cross-cutting infrastructure delivered in B9.A (NOT per-tier):**

- **`TableSpec` registry expansion path** â€” adds a `TIER`, `RECORD_COUNTS_KEY`, and `LOADER_GROUP` field to existing `TableSpec` so generic ingester can: (a) tier-filter, (b) row-count reconcile, (c) loader-register by tier. Backward-compatible default values mean existing FDB pricing TableSpecs still work.
- **Generated migration template** â€” script in `modules/drug-database/scripts/gen_fdb_tier_migration.py` consumes a `TableSpec` list + tier label and emits an idempotent Alembic migration file. Single-tier batched migrations are produced by this template (charter Â§SPEC-locked migration granularity).
- **Ingester contract test template** â€” `modules/drug-database/tests/_fdb_contract.py` reusable test pattern: schema-parity assertion, latin-1 decode smoke, row-count reconciliation skeleton, ON CONFLICT idempotency. Each phase wires concrete `TableSpec` lists into this template.
- **MTL loader guard** â€” `fdb_load_mtl=False` config flag added to settings; loader registry default-excludes MTL; integration test `test_fdb_mtl_zero_rows_under_default` asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly`. Test added in B9.A so it stays green through every later phase (no MTL data loads exist yet, so the assertion is trivial-true until B9.G; the test stays present after B9.G).
- **`setup_fdw.sh --verify` manifest expansion mechanism** â€” `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Per-phase the line count rises (66 â†’ 179 after B9.B â†’ 245 after B9.C â†’ 264 after B9.D â†’ 265 after B9.E â†’ 267 after B9.F â†’ 267 after B9.G schema-only â€” MTL counted â†’ 283 after B9.H final verify). B9.H reconciles the final count to 283.
- **`pytest --collect-only` baseline marker** â€” committed to `waves/B9/baseline.md` at C0; every phase mini-GATE-CLOSE re-runs and asserts count unchanged.

**B9.A commits:**

| C | Scope | Files touched |
|---|---|---|
| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
| C1 | `TableSpec` registry expansion (additive fields, backward-compat) | `modules/drug-database/src/.../fdb/specs.py` (or equivalent), unit tests |
| C2 | Generated migration template | `modules/drug-database/scripts/gen_fdb_tier_migration.py`, scripts test |
| C3 | Ingester contract test template | `modules/drug-database/tests/_fdb_contract.py` |
| C4 | MTL config flag + zero-row CI test (passes trivially today) | `shared/config/...`, `modules/drug-database/tests/test_fdb_mtl_zero_rows_under_default.py` |
| C5 | Codex PLAN consult dispatched, verdict captured | `waves/B9/codex-plan-consult-r1.md` |
| C6 | Codex ADVERSARIAL consult dispatched, verdict captured | `waves/B9/codex-adversarial-r1.md` |
| C7 | Apply consult fixes; v1 â†’ v2 plan if needed; tag PLAN LOCKED | `plan.md` v-bump |

**B9.A mini-GATE-CLOSE criteria (charter SC-9):**

- Contract template + migration template + MTL guard all unit-tested green.
- `pytest --collect-only` count unchanged vs. C0 baseline.
- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
- Codex PLAN consult returns GO or GO-WITH-FIXES (fixes applied + re-consult if FIXES); codex ADVERSARIAL returns no HIGH-severity unaddressed objections.
- Memory updated: `project_b9_plan_v1_locked.md`.

---

### B9.B â€” Tier A: 113 simple lookup tables (â‰¤ 5 columns, generic ingester) (10 sessions)

**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier â€” short tables (mostly < 10K rows, all â‰¤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.

**Per-session shape (10 sessions = ~12 tables/session):**

- 12 new `TableSpec` definitions per session
- 1 batched alembic migration per 25 tables (4 migrations total across B9.B: `0009_fdb_tier_a_part1`..`0009d_fdb_tier_a_part4`) â€” alternative: a single `0009_fdb_tier_a.py` if review is tractable; codex PLAN consult decides
- 12 contract-test wirings per session (each table gets the parity + decode + count + idempotency test set)
- 1 partial loader registry update per session (incremental)

**Deliverables:**

- 113 SQLAlchemy models in `modules/drug-database/src/.../fdb/models/tier_a/`
- 113 `TableSpec` entries in `specs.py`
- 1-4 alembic migrations (`0009_fdb_tier_a*`)
- Contract test coverage = 113 tables (template-driven)
- Loader-orchestration entry: `--mode fdb_tier_a` loads only Tier A
- `setup_fdw.sh` foreign-table count: 66 â†’ 179

**Success criteria (charter mapping):**

- SC-1 (217 tables have models + migrations + ingester) â€” partial: +113
- SC-2 (RECORD_COUNTS reconciliation) â€” every loaded Tier A table: actual Ã· expected within Â±0.1% tolerance (small lookups should be exact)
- SC-6 (FDW verify) â€” partial: 179/179 PASS after B9.B
- SC-7 (weekly idempotency) â€” verified for Tier A only at B9.B mini-GATE-CLOSE
- SC-8 (test strategy) â€” contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
- SC-9 (mini-GATE-CLOSE) â€” see below

**B9.B mini-GATE-CLOSE criteria:**

- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` Â± documented tolerance
- `setup_fdw.sh --verify` 179/179 PASS both env DBs
- All Tier A contract tests green
- Sampled behavioral tests: 10 randomly-picked Tier A tables exercise non-trivial query (FK join, where-clause, sort)
- Migration apply + reverse + apply: clean
- Weekly delta path: `load_fdb.py --mode fdb_tier_a` re-run produces 0 new rows (idempotent)
- `pytest --collect-only` count unchanged vs B9.A C0 baseline Â± 113 new contract tests (counted in baseline)
- Codex mini-GATE-CLOSE consult: GO

**Risk:** 113 tables Ã— ~12/session is aggressive. Mitigation: each session targets contiguous functional groups (e.g., all NDDF BASICS lookups one session; all ETC lookups another) to keep review cohesion. If a session lands fewer tables, the next absorbs the overflow â€” total session count flexes within the charter's 10-session band.

---

### B9.C â€” Tier B: 66 NDC/GCN-keyed joins (12 sessions)

**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.

**Per-session shape (12 sessions = ~5.5 tables/session â€” slower than Tier A because of join-design + FK-target verification per table):**

- 5-6 new `TableSpec` definitions per session
- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
- Contract tests extended with FK-integrity assertion: row's foreign keys must resolve to a target table row (or be NULL where the FK is nullable)
- 1 batched alembic migration per ~25 tables (3 migrations: `0010_fdb_tier_b_part1`..`0010c_fdb_tier_b_part3`)

**Deliverables:**

- 66 SQLAlchemy models in `modules/drug-database/src/.../fdb/models/tier_b/`
- 66 `TableSpec` entries
- 3 alembic migrations (`0010_fdb_tier_b*`)
- Contract test coverage = 66 tables + FK-integrity assertions
- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
- FDW foreign-table count: 179 â†’ 245

**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.

**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.

---

### B9.D â€” Tier C non-RNDC14: 17 complex/large tables (4 sessions)

**Scope:** All 19 Tier C tables EXCEPT the three special-handled ones (RNDC14, RNP2, RPRDPP0). That leaves 17 tables. Complex tables here are > 8 columns or > 50 MB. Includes ETC master, product master (RPRD0_PRODUCT â€” load before RNDC14), GCN master, etc.

**Per-session shape (4 sessions = ~4-5 tables/session):**

- 4-5 new `TableSpec` definitions per session
- Each Tier C table gets explicit column-curation note (which columns kept, which dropped, why) in a per-table block in `waves/B9/tier_c_curation.md`
- Money columns (if any) flagged for `Decimal` typing review per `.claude/rules/financial-precision.md`
- 1 batched alembic migration: `0011_fdb_tier_c_no_rndc14.py`

**Deliverables:**

- 17 SQLAlchemy models in `modules/drug-database/src/.../fdb/models/tier_c/`
- 17 `TableSpec` entries
- 1 alembic migration (`0011_fdb_tier_c_no_rndc14.py`)
- Contract tests + column-curation note + money-path audit
- FDW foreign-table count: 245 â†’ 262
- Tier C dedicated behavioral tests for the 3-4 highest-value tables (ETC master, RPRD0_PRODUCT)

**Success criteria:** SC-1 (partial: cum 196/217), SC-2, SC-6 (262/262), SC-7, SC-8 (dedicated Tier C tests), SC-9.

**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.

---

### B9.E â€” RNDC14 dedicated migration (2 sessions)

**Scope:** RNDC14_NDC_MSTR alone â€” the canonical FDB NDC master, 68 columns, 183 MB, ~501K rows. Highest single-table value in the wave.

**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" â€” no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).

**Per-session shape (2 sessions):**

- Session 1: SQLAlchemy model with all 68 columns, type-mapped (numeric â†’ Decimal where money-relevant; integers where ID; text where descriptor); migration `0012_fdb_rndc14_ndc_mstr.py`; full contract test set
- Session 2: NDC normalization audit (handle 9/10/11-digit NDC inputs and store canonical 11-digit); behavioral tests (FK from existing tables that reference NDC); EXPLAIN ANALYZE runbook addition for high-volume NDC lookups against this table

**Deliverables:**

- 1 SQLAlchemy model (68 cols)
- 1 alembic migration (`0012_fdb_rndc14_ndc_mstr.py`)
- Contract test + behavioral test + EXPLAIN ANALYZE runbook entry
- `tier_c_curation.md` updated with RNDC14 entry (no columns dropped per D1)
- FDW foreign-table count: 262 â†’ 263

**Success criteria:** SC-1 (cum 197/217), SC-3 (RNDC14 all 68 cols), SC-2, SC-6 (263/263), SC-7, SC-8 (dedicated RNDC14 tests), SC-9.

**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.

---

### B9.F â€” RNP2 + RPRDPP0 + C0 perf gate (4 sessions)

**Scope:** The two large pricing tables explicitly deferred in Phase 09, reversed per charter D2. RNP2_NDC_PRICE (595 MB, 13.2M rows) and RPRDPP0_PRODUCT_PRICE (561 MB). +1.16 GB storage. Includes the **D2 performance gate** (charter SC-4) â€” not just disk verification.

**Per-session shape (4 sessions):**

- Session 1: SQLAlchemy models for RNP2 + RPRDPP0; migration `0013_fdb_pricing_big.py`; flip `fdb_load_product_prices=True` default
- Session 2: Timed full-load dry run for both tables; capture wall-clock + final row count + Postgres index build time; capture `df -h` before/after
- Session 3: EXPLAIN ANALYZE on representative query patterns â€” NDC + price_type + effective_date join, ROW_NUMBER OVER PARTITION BY pattern matching `fdb_ndc_price_history` pattern (re-use `docs/runbooks/fdb_lookup_perf.md` patterns); index design + creation
- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` â†’ 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline

**Deliverables:**

- 2 SQLAlchemy models (RNP2 + RPRDPP0)
- 1 alembic migration (`0013_fdb_pricing_big.py`)
- Contract tests + dedicated behavioral tests for both
- Performance evidence in `waves/B9/perf_b9f.md`: timed dry-run, EXPLAIN ANALYZE, storage delta, weekly delta timing
- Default flag flip: `fdb_load_product_prices=True`
- FDW foreign-table count: 263 â†’ 265

**Success criteria:** SC-1 (cum 199/217), SC-4 (D2 perf gate met: timed dry-run + EXPLAIN ANALYZE + storage budget + weekly delta timing all documented), SC-2, SC-6 (265/265), SC-7, SC-8 (RNP2 + RPRDPP0 dedicated behavioral), SC-9.

**B9.F mini-GATE-CLOSE criteria â€” DRACONIAN per charter SC-4:**

- Timed full-load wall-clock recorded for both tables (acceptance: documented, not "fast enough")
- `EXPLAIN ANALYZE` output captured for at least 3 query patterns per table (NDC lookup, price_type filter, effective_date range)
- Storage delta vs. C0 baseline: â‰¤ +1.4 GB total (1.16 GB raw + index headroom)
- FDW + Postgres verify after indexes built: completes within 5 min
- Weekly delta re-run: 0 new rows, timing recorded
- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps

---

### B9.G â€” Tier D MTL schema-only + loader-registration safeguards (3 sessions)

**Scope:** 19 MTL (Medical Test Lexicon) tables. Schema lands; data does NOT load. Per charter D3 + SC-5.

**Per-session shape (3 sessions):**

- Session 1: 19 SQLAlchemy models in `tier_d/`; migration `0014_fdb_mtl_schema.py` (un-gated, lands schema); 19 contract tests asserting tables exist + are queryable + are EMPTY
- Session 2: Loader registry: explicit exclusion of MTL from `--mode fdb_initial` and `--mode fdb_weekly`; opt-in mode `--mode fdb_mtl_data` exists but requires `fdb_load_mtl=True` config flag (charter SC-5 wording)
- Session 3: Integration test `test_fdb_mtl_zero_rows_under_default` (from B9.A C4) now exercises the live MTL tables â€” must continue to assert zero rows after default load. Documentation: `docs/runbooks/fdb-mtl-opt-in.md` explains how to enable IF licensing changes.

**Deliverables:**

- 19 SQLAlchemy models
- 1 alembic migration (`0014_fdb_mtl_schema.py`)
- Loader-registration exclusion of MTL from default modes
- Opt-in mode `--mode fdb_mtl_data` gated on flag
- 19 contract tests asserting table exists + empty
- Updated integration test asserting zero MTL rows after default load
- Runbook `docs/runbooks/fdb-mtl-opt-in.md`
- FDW foreign-table count: 265 â†’ 284 (MTL tables ARE in FDW even though data isn't loaded â€” they exist as foreign-table entries pointing at empty reference tables)

**Note on FDW count:** 284 not 283. Recon's target was 283 across 220 - 3 already covered tables = wait, re-checking â€” actually B9.A's expansion path showed 283 final count. Let me re-derive: 66 (current) + 113 (B9.B) + 66 (B9.C) + 17 (B9.D) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = 284. **The 283 figure in the charter is wrong by 1; B9.H reconciles to the true 284.** This is a charter erratum to surface to codex PLAN consult.

**Success criteria:** SC-1 (cum 218/217 â€” overshoots by 1 due to schema-only MTL â€” re-examine after PLAN consult), SC-5 (MTL zero-row test green), SC-6 (284/284 â€” pending erratum), SC-9.

**B9.G mini-GATE-CLOSE criteria:**

- `0014_fdb_mtl_schema.py` apply + reverse + apply: clean
- Integration test `test_fdb_mtl_zero_rows_under_default` green after live load attempt with default flag
- Opt-in flag flip + `--mode fdb_mtl_data` invocation succeeds (validated, then rolled back)
- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)

---

### B9.H â€” Manifest extension + final closeout (4 sessions)

**Scope:** Reconcile `infrastructure/scripts/lib/expected_reference_tables.txt` to the true final count, run final FDW verify, produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.

**Per-session shape (4 sessions):**

- Session 1: Manifest expansion â€” `expected_reference_tables.txt` final count reconciled (charter said 283; PLAN derives 284; reconcile via codex PLAN consult before B9.H). Update Werkbench inventory + glossary if new tables/concepts warrant.
- Session 2: Final `setup_fdw.sh --verify` 284/284 in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables; published in `waves/B9/evidence.md`
- Session 3: Cross-tier behavioral suite: NDC lookup goes RNDC14 â†’ RPRD0_PRODUCT â†’ tier-A descriptors â†’ pricing (RNP3, RNP2, RPRDPP0); verifies the wave's value-creation chain
- Session 4: B9 ship artifacts (`waves/B9/ship.md`); memory entry; wave-history index update; codex final GATE-CLOSE consult; PR creation if any of the FDB schema work was branched

**Deliverables:**

- Reconciled `expected_reference_tables.txt`
- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
- `waves/B9/ship.md`
- Cross-tier behavioral test suite
- Memory: `project_b9_implemented.md` and MEMORY.md index line
- `docs/audit/wave-history.md` entry
- Codex final GATE-CLOSE verdict in `waves/B9/codex-gate-close.md`

**Success criteria â€” ALL SC-1..SC-11:**

- SC-1: 217 tables have models + migrations + ingester (verified via `pg_class` count + alembic history scan)
- SC-2: RECORD_COUNTS reconciled per table (or documented tolerance / exclusion for MTL)
- SC-3: RNDC14 ingest covers all 68 columns
- SC-4: D2 perf gate evidence present
- SC-5: MTL zero-row test green
- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
- SC-7: Weekly delta idempotent across all 220 tables (verified at B9.H by running `--mode fdb_weekly` â†’ 0 new rows in all 217 + already-covered 3)
- SC-8: Test strategy executed (contract + parity + reconciliation + sampled behavioral + dedicated Tier C)
- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
- SC-10: Final B9 GATE-CLOSE GO or GO-WITH-FIXES (FIXES applied iteratively until GO)
- SC-11: Evidence + ship + memory + wave-history all present

**B9 final GATE-CLOSE criteria:** codex final consult returns GO. Charter SC-10 escalates only if codex returns GO-WITH-FIXES three times in a row without convergence; that triggers an architectural pause.

---

## Goal-backward verification (per SC)

Every SC has at least one test or evidence artifact that proves it.

| SC | Verification artifact | Phase landing |
|---|---|---|
| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == 220; `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
| SC-4 | `waves/B9/perf_b9f.md`: timed dry-run, EXPLAIN ANALYZE, storage delta, weekly delta timing | B9.F |
| SC-5 | `test_fdb_mtl_zero_rows_under_default` green; opt-in mode reviewed in codex consult | B9.G |
| SC-6 | `setup_fdw.sh --verify` output 284/284 in dev + mock (or 283/283 if reconciled to charter count) | B9.H Session 2 |
| SC-7 | `load_fdb.py --mode fdb_weekly` re-run logs zero new rows across all 220 tables | B9.H Session 4 |
| SC-8 | Test counts per category in evidence.md: 217 contract tests + 220 schema-parity + 217 row-count assertions + N sampled behavioral + dedicated Tier C suite | B9.H Session 2 |
| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
| SC-10 | `waves/B9/codex-gate-close.md` with GO verdict | B9.H Session 4 |
| SC-11 | `evidence.md`, `ship.md`, memory file, `wave-history.md` line all present and pointing at the right commits | B9.H Session 4 |

---

## Threat model

| T | Threat | Likelihood | Severity | Mitigation |
|---|---|---|---|---|
| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon Â§7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
| T3 | RNP2 + RPRDPP0 ingest exhausts dev disk (charter R2) | LOW | HIGH | C0 disk check (â‰¥ 5 GB free); B9.F session 2 timed dry-run captures real consumption; abort + escalate if > +1.4 GB |
| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
| T5 | MTL accidentally loads data despite guards (charter R7) | LOW | HIGH | Triple-layer guard: schema-only migration âœ“, loader-registry default exclusion âœ“, integration test asserts zero rows âœ“; B9.G codex consult specifically reviews the guard chain |
| T6 | RNDC14 68-column model has wrong type for one or more columns (NUMERIC vs Decimal vs Integer vs Text confusion) | MED | MED | B9.E session 1 produces type-mapping table from DDL `.txt` definitions; session 2 codex column-by-column review |
| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
| T10 | Test count baseline drifts (134 pre-existing failures become 135 or 200) | MED | MED | B9.A C0 captures `pytest --collect-only` count; each phase mini-GATE-CLOSE asserts count unchanged Â± new contract tests |
| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |

---

## Codex iteration plan

| Round | Phase | Dispatch trigger | Verdict file |
|---|---|---|---|
| SPEC R1 | B9.A | Charter v1 dispatched 2026-05-11 | `codex-spec-consult-r1.md` â€” GO-WITH-FIXES |
| SPEC R2 | B9.A | Charter v2 dispatched 2026-05-11 | `codex-spec-consult-r2.md` â€” GO-WITH-FIXES â†’ cleanup applied â†’ v3 LOCKED |
| **PLAN R1** | **B9.A** | **This plan v1 dispatched next** | **`codex-plan-consult-r1.md` â€” pending** |
| ADVERSARIAL R1 | B9.A | After PLAN R1 GO or GO-WITH-FIXES + fix | `codex-adversarial-r1.md` |
| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 17 ingested | `codex-mini-gate-close-D.md` |
| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
| GATE-CLOSE | B9.H | Wave shipping artifacts assembled | `codex-gate-close.md` |

**Total codex consults projected:** 11 (2 SPEC done + 9 remaining).

---

## Out of plan (deferred â€” explicitly NOT in scope for B9)

- Phase 4 portal feature work (forward feature work; charter Â§Out of scope)
- 134 pre-existing test failures (forensic wave handles these; charter Â§Out of scope)
- B8.2 followups (already shipped commit `1c28e44`; charter Â§Out of scope)
- MTL data ingest (schema only; flip flag in a later wave IF licensing changes)
- RNDC14 column-curation (charter D1 locks full 68-col; no triage)
- Splitting B9 into multiple wave labels (charter D4 locks single milestone)
- New external data sources beyond NDDF Plus (FDB Atomic, FDB MedKnowledge: separate waves)
- Clinical screening data (NOT subscribed per memory `project_fdb_nddf_plus_dataset.md`)
- Reference DB replication to Azure (deferred per memory `project_phase11a_decision.md`)

---

## Known errata to surface to codex PLAN consult

1. **FDW final count: 283 vs 284.** Charter says 283; PLAN's tier-additive derivation gives 284 (66 + 113 + 66 + 17 + 1 + 2 + 19 = 284). The charter figure may have netted the 3 already-covered FDB pricing tables differently. Codex PLAN consult should reconcile before B9.B opens.
2. **Migration count: 5 vs 6.** Charter says "0009..0014" (6 migrations); PLAN sub-counts Tier A and Tier B each into ~3-4 part files, which inflates the migration count to 9-10. Codex PLAN consult should rule on batching shape: single big file per tier OR per-25 part files.
3. **Loader-orchestration modes: existing vs new.** Charter implies `--mode fdb_weekly` exists; recon shows existing loader has `--mode fdb_initial` only. PLAN assumes both exist; B9.A C4 must verify or add `--mode fdb_weekly`.

---

## Status reporting cadence

Per session-framework rules (`.claude/rules/session-framework.md`):

- Each B9.X session lands its own evidence row in `waves/B9/sessions.md` (created at B9.A)
- At each mini-GATE-CLOSE: full sign-off sheet committed
- Memory updates after each phase closes
- B9.H final ship: full memory + wave-history entry

**End of PLAN v1.**

 succeeded in 484ms:
# Wave B9 â€” Recon report (2026-05-11)

**Author:** recon-agent
**Status:** RECON COMPLETE
**Goal:** Scope FDB NDDF Plus 220-table extension beyond the 3-table Phase 09 baseline

---

## Executive summary

- The FDB drop contains exactly **220 data tables** in `NDDF Plus DB/NDDF PLUS DB.zip`, all with matching ANSI DDL. The current ingester covers **3 tables** (RNP3\_NDC\_PRICE, RPRDPTD0\_PRICE\_TYPE\_DESC, RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC) mapped to **2 DB tables** (`fdb_ndc_price_history`, `fdb_price_type_desc`). Gap: **217 tables**.
- Tables span six FDB modules: NDDF BASICS 3.0 (98 tables), MEDNAMES 3.0 (63), ETC 1.0 (16), TALL MAN PLUS 2.0 (15), XRF 1.0 (9), MTL 1.0 (19). MTL (Medical Test Lexicon) is the only module without a clear adjudication use case â€” treat as a product decision.
- The generic `TableSpec`-driven adapter (`FDBLocalDropAdapter.parse_table`) already works for any pipe-delimited FDB table. The ingest architecture is **extension-ready**: new tables become new `TableSpec` constants + SQLAlchemy models + a migration, no adapter surgery required.
- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion â€” this is a one-time setup change, not per-deployment.
- Two Tier C tables dominate storage risk: `RNP2_NDC_PRICE` (595 MB uncompressed, 13.2M rows) and `RPRDPP0_PRODUCT_PRICE` (561 MB). Both are pricing variants already noted in the Phase 09 ingester as deferred. Ingesting them requires an explicit go/no-go decision before B9.2.
- The `RNDC14_NDC_MSTR` table (68 columns, 183 MB, ~501K rows) is the platform's most valuable single gap target â€” it is the canonical FDB NDC master containing labeler, brand name, GCDF, route, DEA schedule, packaging, and product status fields that adjudication, formulary, and reclaimrx all need.

---

## Section 1 â€” FDB drop inventory

**Drop location:** `data/reference/fdb/TEL251759D/`

**Weekly subdirectories found:**
```
06MAY2026.TEL251759D/    (Current@ symlink target)
29APR2026.TEL251759D/
```

**Current/ directory layout:**
```
Copyright.txt
FDB_CLINICAL_HIGHLIGHTS.ZIP        <- clinical screening, NOT subscribed
NDDF Plus DB/NDDF PLUS DB.zip      <- 220 data table files (pipe-delimited, latin-1)
NDDF Plus DDL/NDDF PLUS DDL.zip    <- 46 DDL files (ANSI, Oracle, SQL Server, Sybase)
NDDF Plus UPD/NDDF PLUS UPD.zip    <- weekly delta (A/C/D prefixed rows)
NDDF_PRODUCT_INFO.TXT              <- single-line YYYYMMDD data cutoff date
RECORD_COUNTS.TXT                  <- table name -> row count manifest
```

**Table count:**
- DB zip entries: **220**
- ANSI DDL `CREATE TABLE` statements: **220** (+ 1 meta: `NDDF_PRODUCT_INFO`)
- Tables in DB zip but not in DDL: **0**
- Tables in DDL but not in DB zip: **0**

**FDB module breakdown:**

| Module | Tables | Notes |
|---|---|---|
| NDDF BASICS 3.0 / Generic Formulation and Ingredient | 50 | GCN, GCNSEQNO, HIC, strength, route, dosage form |
| NDDF BASICS 3.0 / Packaged Product | 30 | NDC master, FDA application, OBC, labeler |
| NDDF BASICS 3.0 / Pricing | 11 | RNP2, RNP3, RPRDPP0, price attr |
| NDDF BASICS 3.0 / Miscellaneous Therapeutic Class | 7 | AHFS, ATC, HIC therapeutic class |
| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
| NDDF ETC 1.0 | 16 | Enhanced Therapeutic Classification hierarchy |
| NDDF XRF 1.0 | 9 | Clinical quantity crossrefs, script QQ |
| TALL MAN PLUS 2.0 | 15 | Look-alike/sound-alike confusion groups |
| NDDF MTL 1.0 | 19 | Medical Test Lexicon â€” separate domain |

**Sample file profiles:**

| Table | Cols | Uncompressed | First-field sample |
|---|---|---|---|
| RNDC14\_NDC\_MSTR | 68 | 183 MB | NDC, labeler, GCN, brand, DEA, packaging |
| RNP2\_NDC\_PRICE | 4 | 595 MB | NDC, price\_type, effective\_date, price |
| RPRDPP0\_PRODUCT\_PRICE | 7 | 561 MB | product, price\_type, effective\_date, price, currency |
| RGCNSEQ4\_GCNSEQNO\_MSTR | 13 | 2.3 MB | GCN\_SEQNO, HIC3, HICL\_SEQNO, GCDF, GCRT, STR |
| RETCTBL0\_ETC\_ID | 12 | 348 KB | ETC\_ID, name, leaf flag, parent, hierarchy level |
| RMTLLAB0\_LAB\_ID | 5 | 6 KB | LAB\_ID, description, analyte, specimen, type |
| RTMDFID1\_TM\_ROUTED\_DF\_MED | 4 | 209 KB | MED\_ID, source, confusion\_flag, tall-man name |

**RECORD\_COUNTS.TXT:** Present, contains row count for every table name in the drop (verified counts align with zip). Example: `RNPALL|013213617` (all pricing rows), `RNDC14_NDC_MSTR` implied by `RNDCALL|000501107`.

---

## Section 2 â€” Current ingester coverage

**Python files covering FDB:**

| File | Role |
|---|---|
| `modules/drug-database/drug_database/services/fdb_adapter.py` | Generic adapter + 4 TableSpec constants |
| `modules/drug-database/drug_database/services/fdb_pricing.py` | Point-in-time pricing lookup (SWP/SWD/WAC) |
| `modules/drug-database/drug_database/services/fdb_pricing_ingester.py` | Orchestration: price\_type\_desc + RNP3 ingest |
| `modules/drug-database/drug_database/models/fdb_pricing_tables.py` | 2 ORM models |
| `modules/drug-database/alembic/versions/0008_fdb_pricing.py` | 1 migration covering 2 tables |
| `scripts/load_fdb.py` | CLI entry point (registered in run\_reference\_loaders.sh) |

**Currently ingested FDB tables â†’ DB tables:**

| FDB Table | DB Table | Notes |
|---|---|---|
| RNP3\_NDC\_PRICE | `drug_database.fdb_ndc_price_history` | 13.2M rows; append-only, A/C/D UPD semantics |
| RPRDPTD0\_PRICE\_TYPE\_DESC | `drug_database.fdb_price_type_desc` | 20 rows; modern catalog |
| RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC | `drug_database.fdb_price_type_desc` | 21 rows; legacy codes with synthetic IDs |

**Coverage gap: 217 of 220 FDB tables have no DB mapping.**

Key high-value uncovered tables:

| FDB Table | Cols | Rows (RECORD\_COUNTS) | Business value |
|---|---|---|---|
| RNDC14\_NDC\_MSTR | 68 | ~501K | NDC master â€” labeler, brand, GCN, route, DEA, packaging |
| RPRD0\_PRODUCT | 7 | 503K | Product master (GCN-level above NDC) |
| RGCNSEQ4\_GCNSEQNO\_MSTR | 13 | 38K | GCN master â€” therapeutic class, dosage form, gender |
| RETCTBL0\_ETC\_ID | 12 | 3.3K | ETC classification hierarchy |
| RETCNDC0\_ETC\_NDC | 4 | 616K | NDC â†’ ETC classification mapping |
| RMIID1\_MED | 20 | 114K | MedID master â€” routed-drug-level attributes |
| RTMDFID1\_TM\_ROUTED\_DF\_MED | 4 | 3.9K | Tall Man lettering â€” look-alike/sound-alike |
| RGCNSTR0\_INGREDIENT\_STRENGTH | 15 | 66K | Active ingredient strengths per GCN |

**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.

---

## Section 3 â€” Classification (effort tiers)

Classification criteria:
- **Tier A** â€” Pure reference/description tables. Typically code â†’ description, â‰¤ 5 columns, < 2 MB uncompressed, name suffix `D0`â€“`D9` pattern or a small static lookup. No NDC normalization, no join design, no money columns.
- **Tier B** â€” NDC-keyed, GCN-keyed, or MedID-keyed link/crossref tables. Simple join design. May include NDC normalization (re-use existing `normalize_ndc`). 2â€“7 columns typical.
- **Tier C** â€” Complex tables: > 8 columns, or large pricing tables (> 50 MB), or key structural masters (RNDC14 at 68 cols). Require careful column mapping, money-path review (financial-precision.md), or parent-key join design with existing ingested tables.
- **Tier D** â€” Medical Test Lexicon (MTL 1.0). 19 tables covering lab analytes, panels, specimen IDs. Structurally simple (most are tiny) but the business question â€” do adjudication rules need lab linkage? â€” must be answered before ingest design begins.

| Tier | Count | Effort/table | Total effort | Notes |
|---|---|---|---|---|
| A â€” Simple lookups | 113 | 20 min | 37.7h | Generic ingester handles most; 1 TableSpec + 1 model + 1 test |
| B â€” NDC/GCN-keyed joins | 66 | 40 min | 44.0h | NDC normalization, join design, larger test fixtures |
| C â€” Complex/large | 19 | 90 min | 28.5h | RNDC14 (68 cols), two 500 MB+ pricing tables, ETC master |
| D â€” MTL (product decision) | 19 | 30 min | 9.5h | Small tables, pending go/no-go |
| **Total** | **217** | â€” | **119.7h raw** | ~156h with codex review overhead (30%) |

**Tier C table inventory (all 19):**

| Table | Cols | Uncompressed | Decision risk |
|---|---|---|---|
| RNDC14\_NDC\_MSTR | 68 | 183 MB | Highest value; complex column mapping |
| RNP2\_NDC\_PRICE | 4 | 595 MB | Pricing variant; go/no-go needed (Phase 09 deferred) |
| RPRDPP0\_PRODUCT\_PRICE | 7 | 561 MB | Product-level pricing; Phase 09 deferred |
| RPRD0\_PRODUCT | 7 | 32 MB | Product master; load before RNDC14 |
| RMIID1\_MED | 20 | 13 MB | MedID master (MEDNAMES module) |
| RGCNSTR0\_INGREDIENT\_STRENGTH | 15 | 11 MB | Per-ingredient strength data |
| RPEINS0\_NDC\_STR\_LINK | 18 | 10 MB | NDC strength link |
| RETCNDH0\_ETC\_NDC\_HIST | 7 | 30 MB | ETC NDC history (large row count) |
| RETCMDH0\_ETC\_MEDID\_HIST | 7 | 7 MB | ETC MedID history |
| RETCTBL0\_ETC\_ID | 12 | 348 KB | ETC hierarchy master |
| RPEIGS0\_GCNSEQNO\_STR\_LINK | 20 | 2 MB | GCN strength link |
| RPEIMS0\_MED\_STR\_LINK | 20 | 4 MB | MedID strength link |
| RGCNSEQ4\_GCNSEQNO\_MSTR | 13 | 2.3 MB | GCN master |
| RPEIRM0\_RT\_MSTR | 13 | 18 KB | Route master |
| RMEDNGH0\_NDC\_GEN\_MEDID\_HIST | 12 | 931 KB | NDC generic MedID history |
| RMEDNMH0\_NDC\_MEDID\_HIST | 12 | 925 KB | NDC MedID history |
| RNDCDR0\_NDC\_DELETION\_REASON | 16 | 303 KB | NDC deletion tracking |
| RPEIUM0\_UOM\_MSTR | 27 | 104 KB | Unit-of-measure master |
| RETCGCH0\_ETC\_GCNSEQNO\_HIST | 7 | 1.9 MB | ETC GCN history |

---

## Section 4 â€” Schema strategy

**Options considered:**

| Option | Description | Verdict |
|---|---|---|
| A â€” One big migration | All 217 tables in `0009_fdb_full.py` | REJECTED â€” one migration failure blocks everything; impossible to review |
| B â€” One migration per tier | 4 migrations (0009â€“0012) | Reasonable for small projects; still 66+ models per migration |
| C â€” One migration per table | 217 migrations | Too many migration files; untenable maintenance |
| D â€” Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |

**Recommendation: Option D â€” Tiered phasing with batch migrations.**

- `0009_fdb_tier_a.py` â€” 113 Tier A tables (all small; one migration is reviewable because models are uniform 2â€“5-col descriptors)
- `0010_fdb_tier_b.py` â€” 66 Tier B tables (NDC/GCN-keyed)
- `0011_fdb_tier_c.py` â€” 19 Tier C tables (but RNDC14 should be its own migration `0011a` given 68-col complexity)
- `0012_fdb_tier_d.py` â€” 19 MTL tables (only if product go decision is made)

**Rationale:**
- Each migration maps to a sub-wave gate. If B9.2 fails QA, B9.1 is already in prod.
- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
- Tier C needs its own slot because `RNDC14_NDC_MSTR` at 68 columns is a significant schema decision that may require discussion about which columns to retain vs. drop (storage vs. value tradeoff).
- Postgres locks table briefly on `ADD COLUMN`; avoid mixing 68-col table alterations with bulk small-table creates in one transaction.

---

## Section 5 â€” Ingester strategy

**Options considered:**

| Option | Description | Verdict |
|---|---|---|
| E â€” Generic table-driven ingester | Config file (YAML/dict) maps table names â†’ TableSpec; one ingester loops all tables | RECOMMENDED for Tier A and B |
| F â€” Per-table service | One `fdb_<table>_ingester.py` per table, matching Phase 09 pattern | Appropriate for Tier C tables with complex logic |
| G â€” Hybrid | Generic ingester for A+B; per-table for C+D | RECOMMENDED overall |

**Recommendation: Option G â€” Hybrid.**

**For Tier A + B (179 tables):**
The existing `TableSpec` dataclass + `FDBLocalDropAdapter.parse_table` already provides a generic parse-any-table capability. The only missing piece is:
1. A `TableSpec` registry (a Python dict: `table_name â†’ TableSpec`) in `fdb_adapter.py`
2. A generic `FDBBulkIngester` that iterates the registry, calling `parse_table` + bulk upsert for each
3. One `ON CONFLICT DO NOTHING` upsert per table (same pattern as `_flush_rnp3_batch`)

This avoids writing 179 separate Python service classes. The bulk ingester adds roughly 200 lines of new code vs. ~17,900 lines if every table got its own service.

**For Tier C (19 tables):**
Complex tables need per-table logic:
- `RNDC14_NDC_MSTR` (68 cols): requires explicit column-selection decision, NDC normalization, money column handling (price-related fields), and a dedicated EXPLAIN ANALYZE runbook
- `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`: pricing tables need go/no-go decision and Decimal handling audit (financial-precision.md)
- Other Tier C tables can share a thin wrapper around the generic ingester with overridden coercers

**For Tier D (MTL):**
MTL tables are tiny (total uncompressed: ~103 KB). If the product decision is "yes", they fit cleanly into the generic ingester. If "no", skip entirely. No architectural complexity.

**Key architectural constraint:** The generic ingester must still use `ON CONFLICT DO NOTHING` for idempotency â€” same as the existing RNP3 ingester. Weekly re-ingest must be safe to re-run.

---

## Section 6 â€” Effort estimate

| Component | Effort |
|---|---|
| Tier A: 113 tables Ã— 20 min | 37.7h |
| Tier B: 66 tables Ã— 40 min | 44.0h |
| Tier C: 19 tables Ã— 90 min | 28.5h |
| Tier D: 19 tables Ã— 30 min (if go) | 9.5h |
| Generic ingester + TableSpec registry (new infrastructure) | 8h |
| FDW manifest expansion (setup_fdw.sh + testing) | 4h |
| Codex review cadence: SPEC â†’ PLAN â†’ ADVERSARIAL, 1â€“2 rounds per sub-wave | 16h |
| Integration testing (load against real zip, verify row counts vs RECORD\_COUNTS.TXT) | 8h |
| **Subtotal (A+B+C + infra + reviews)** | **~147h** |
| **Add Tier D if go** | **+9.5h** |

**Session count:** Assuming 4h productive per session:
- B9.0 (planning, charter, generic ingester design): 1 session
- B9.1 (Tier A, 113 tables): ~10 sessions
- B9.2 (Tier B, 66 tables): ~12 sessions
- B9.3 (Tier C, 19 tables): ~8 sessions
- B9.4 (Tier D, MTL â€” if go): ~3 sessions

**Total: ~34 sessions** (excluding Tier D). This is a multi-month effort at 2â€“3 sessions/week.

**Realistic wall-clock:** 3â€“4 months for B9.1 through B9.3. Consider whether B9 is actually two waves (B9 = Tier A+B; B10 = Tier C) for milestone hygiene.

---

## Section 7 â€” Risk catalog

**Risk 1 â€” RNDC14\_NDC\_MSTR column explosion (HIGH)**
The NDC master has 68 columns, many of which are FDB-internal flags with unclear business relevance. Without column curation, the DB table will be bloated and the ORM model unwieldy. Risk: table design gets revisited post-ingest, requiring a costly migration. Mitigation: Before B9.3, produce a column-by-column triage (keep / drop / defer) based on adjudication, formulary, and reclaimrx requirements.

**Risk 2 â€” Two 500 MB+ pricing tables require explicit go/no-go (HIGH)**
`RNP2_NDC_PRICE` (595 MB, 13.2M rows legacy pricing) and `RPRDPP0_PRODUCT_PRICE` (561 MB) were explicitly deferred in Phase 09 (`fdb_load_product_prices=False` config flag). Loading both adds ~1.1 GB uncompressed to the reference DB weekly. Risk: storage growth and ingest window extension. Mitigation: Decide at B9.3 charter whether these are in scope. If yes, add dedicated EXPLAIN ANALYZE runbook.

**Risk 3 â€” FDW LIMIT TO list maintenance drift (MEDIUM)**
`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.

**Risk 4 â€” Weekly ingest window growth (MEDIUM)**
Current FDB ingest: RNP3 (13.2M rows) takes ~minutes. Adding 217 tables including NDC master (501K rows), ETC NDC mapping (616K rows), and MedName tables adds significant volume to the weekly UPD cycle. The UPD zip must also be verified to contain all tables (not just pricing). Mitigation: Profile UPD zip contents against DB zip contents. Validate that `NDDF Plus UPD/` has a matching file for each table before committing to weekly ingest for all 220.

**Risk 5 â€” UPD zip may not contain all tables (MEDIUM)**
The current adapter only reads from UPD for RNP3 (pricing). Some FDB reference tables (e.g., description tables) may ship full-replacement in UPD rather than A/C/D delta. Mitigation: Inspect the UPD zip structure early in B9.1. If some tables are full-replacement (no A/C/D prefix), the ingester must detect this and use TRUNCATE+INSERT rather than ON CONFLICT DO NOTHING.

**Risk 6 â€” latin-1 encoding edge cases in text columns (LOW-MEDIUM)**
The existing adapter handles latin-1 decoding for RNP3 (numeric-heavy). Text-heavy tables (drug names, descriptions, brand names) are more likely to have characters in the latin-1 extended range (0x80â€“0xFF). Mitigation: Audit the first 1000 rows of text-column tables (RMIID1\_MED, RNDC14\_NDC\_MSTR brand fields) for decoding failures before schema finalization.

**Risk 7 â€” SQLite test fixture scaling (LOW-MEDIUM)**
At 217 new models, the per-test `create_all()` time in SQLite fixtures will grow. Currently 2 FDB models; adding 217 means each test session creates 219 tables. Risk: slow CI. Mitigation: Split the `FDBPricingBase` into module-level declarative bases (`FDBBasicsBase`, `FDBMedNamesBase`, etc.) so tests only create\_all for the module under test. Plan this in B9.0 before any model files are written.

---

## Section 8 â€” Recommended phased plan

### B9.0 â€” Planning and infrastructure (1 session)

- Charter v1: column triage for RNDC14, pricing table go/no-go decision, MTL go/no-go decision
- Design the `FDBBulkIngester` (generic ingester for Tier A+B) â€” implementation-ready spec
- Design the SQLAlchemy base-splitting strategy (avoid 219-table create\_all in every test)
- Audit UPD zip structure: verify which tables ship as delta vs. full-replacement
- Update `run_reference_loaders.sh` to accept `--scope tier_a|tier_b|tier_c|all`

### B9.1 â€” Tier A: 113 simple lookup tables (target ~10 sessions)

- Implement `FDBBulkIngester` generic infrastructure (~200 lines)
- Add 113 `TableSpec` entries to registry in `fdb_adapter.py`
- One alembic migration `0009_fdb_tier_a.py`
- 113 ORM model classes in `fdb_lookup_tables.py` (batched by module)
- Integration test: load against real DB zip, verify row counts vs RECORD\_COUNTS.TXT for all 113 tables
- FDW manifest update: add 113 table names to `setup_fdw.sh` LIMIT TO list
- Gate: 100% tests pass, row counts match RECORD\_COUNTS.TXT within 1%

### B9.2 â€” Tier B: 66 NDC/GCN-keyed tables (target ~12 sessions)

- 66 `TableSpec` entries with NDC normalization where applicable
- Migration `0010_fdb_tier_b.py`
- ORM models in `fdb_link_tables.py`
- Cross-tenant isolation tests (reference data is global â€” confirm no TenantScopedMixin needed, LESSON-011)
- Integration test: verify NDC join correctness against existing `fdb_ndc_price_history`
- FDW manifest update: +66 entries
- Gate: same as B9.1

### B9.3 â€” Tier C: 19 complex tables (target ~8 sessions)

- Pre-work: RNDC14 column triage document (owner sign-off required before coding)
- Pricing table go/no-go confirmation (RNP2, RPRDPP0)
- One migration per Tier C table (or `0011_fdb_tier_c.py` + `0011a_fdb_ndc_master.py` for RNDC14 separately)
- Per-table services where logic warrants (money columns â†’ Decimal audit)
- EXPLAIN ANALYZE runbook for RNDC14 and any table > 10M rows
- FDW manifest update: +19 entries
- Gate: same as B9.1 plus financial-precision check on any Numeric columns

### B9.4 â€” Tier D: MTL (19 tables) â€” CONDITIONAL on product decision

- Only proceed if adjudication/reclaimrx team confirms lab linkage is in scope
- All 19 MTL tables are tiny (total 103 KB) â€” one session if go decision is made
- Migration `0012_fdb_tier_d.py`, generic ingester handles all 19

---

## Open decisions for charter v1

1. **RNDC14\_NDC\_MSTR column triage**: Which of the 68 columns does InfinityRx actually need? Full 68-column ingest vs. curated subset has significant implications for model maintainability and storage. Required before B9.3 begins.

2. **Pricing table go/no-go (RNP2 + RPRDPP0)**: Both were explicitly deferred in Phase 09. RNP2 is the legacy pricing file (overlaps with RNP3 data); RPRDPP0 is product-level pricing (vs. RNP3's NDC-level). Decision needed: are either of these required for adjudication accuracy, or is RNP3 sufficient?

3. **MTL go/no-go**: Does any planned adjudication rule or reclaimrx detection require lab test linkage (NDDF MTL 1.0)? If yes, B9.4 is in scope. If no, all 19 MTL tables are permanently skipped.

4. **Wave boundary â€” is B9 one wave or two?**: 34 sessions is 3â€“4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.

codex
I’ve got the artifacts loaded. The main reconciliation points are already visible: the plan itself flags the 283/284 contradiction, and there are internal count inconsistencies around Tier C/MTL that need to be separated from the charter’s locked 217-gap math. I’m checking the loader mode claim against the repo now rather than relying on the plan’s note.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "mode|fdb_initial|fdb_weekly|argparse|load_fdb" scripts modules shared -g "*.py" -g "*.sh"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"Express Scripts|ESI|Evernorth|CVS Caremark|Caremark|OptumRx|Prime Therapeutics|MedImpact|Navitus|MagellanRx|Humana Pharmacy Solutions\" 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md' 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md' 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"SC-|R[1-7] \\||T[0-9]+|B9\\.[A-H]|FDW|283|284|fdb_weekly|fdb_initial|001[0-9]|migration|mini-GATE|Goal-backward|Threat model|Pre-execute|D2|MTL|RNP2|RPRDPP0|RNDC14|setup_fdw|collect-only|RECORD_COUNTS|session\" 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"SC-|R[1-7] \\||B9\\.[A-H]|FDW|283|284|fdb_weekly|migration|mini-GATE|D2|MTL|RNP2|RPRDPP0|RNDC14|39 sessions|SPEC-locked\" 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"220|217|113|66|19|MTL|FDW|currently|Current|RNP3|RPRDPTD0|RNPTYPD0|LIMIT TO|Tier classification|Tier C table inventory|Total|Migration|Recommendation|fdb_initial|fdb_weekly|mode\" 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 450ms:
6:**Scope:** All 217 currently-missing FDB NDDF Plus tables (3 already covered) reach the platform as ingested or schema-only across phases B9.A → B9.H.
14:1. **Cross-cutting infrastructure** all phases depend on (B9.A deliverables).
15:2. **Per-phase scope, deliverables, success-criteria mapping, gate criteria, est sessions, commit shape** for B9.B..B9.H.
16:3. **Per-phase batched migration plan** (SPEC-locked at charter v3 §SPEC-locked migration granularity).
17:4. **D2 perf gate** specifics (charter SC-4).
18:5. **MTL loader/runtime guards** (charter SC-5; Alembic NOT config-gated).
19:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
20:7. **Threat model + risks** synthesised from recon §7 and charter §risks.
24:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
25:- The exact `RECORD_COUNTS.TXT` tolerance numbers (per-table; published in each phase evidence doc).
26:- The text of each ingester contract test (template-driven; B9.A produces the template).
30:## Pre-execute invariants (must hold before B9.A C0)
35:2. **B7.2 Phase 11A COMPLETE** — `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
36:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
37:4. **Disk budget verified** — `df -h` shows ≥ 5 GB free on the reference DB volume to absorb D2's +1.16 GB (RNP2 + RPRDPP0) plus indexes plus working space. Captured at B9.A C0.
38:5. **`fdb_load_product_prices` config flag still in code** — Phase 09 deferral flag location identified; B9.F will flip default to `True` and document.
39:6. **134 pre-existing test failures baseline frozen** — `pytest --collect-only` count captured at B9.A C0; B9 must not regress count, must not "fix" them (charter `Out of scope` row 3). Forensic wave handles these later.
40:7. **FDB drop manifest reachable** — `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon §1.5 verified — re-verify at C0).
41:8. **`charter.md` v3 + `recon.md` checked into Werkbench/projects/infinityrx-platform/waves/B9/** at the moment B9.A starts (commit reference required in B9.A C0 evidence).
44:If any invariant fails, B9.A C0 stops and reports — do not paper over.
50:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
52:### B9.A — Charter v3 close + Plan v1 close + infrastructure scaffolding (2-3 sessions)
56:**Cross-cutting infrastructure delivered in B9.A (NOT per-tier):**
58:- **`TableSpec` registry expansion path** — adds a `TIER`, `RECORD_COUNTS_KEY`, and `LOADER_GROUP` field to existing `TableSpec` so generic ingester can: (a) tier-filter, (b) row-count reconcile, (c) loader-register by tier. Backward-compatible default values mean existing FDB pricing TableSpecs still work.
59:- **Generated migration template** — script in `modules/drug-database/scripts/gen_fdb_tier_migration.py` consumes a `TableSpec` list + tier label and emits an idempotent Alembic migration file. Single-tier batched migrations are produced by this template (charter §SPEC-locked migration granularity).
61:- **MTL loader guard** — `fdb_load_mtl=False` config flag added to settings; loader registry default-excludes MTL; integration test `test_fdb_mtl_zero_rows_under_default` asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly`. Test added in B9.A so it stays green through every later phase (no MTL data loads exist yet, so the assertion is trivial-true until B9.G; the test stays present after B9.G).
62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Per-phase the line count rises (66 → 179 after B9.B → 245 after B9.C → 264 after B9.D → 265 after B9.E → 267 after B9.F → 267 after B9.G schema-only — MTL counted → 283 after B9.H final verify). B9.H reconciles the final count to 283.
63:- **`pytest --collect-only` baseline marker** — committed to `waves/B9/baseline.md` at C0; every phase mini-GATE-CLOSE re-runs and asserts count unchanged.
65:**B9.A commits:**
69:| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
71:| C2 | Generated migration template | `modules/drug-database/scripts/gen_fdb_tier_migration.py`, scripts test |
73:| C4 | MTL config flag + zero-row CI test (passes trivially today) | `shared/config/...`, `modules/drug-database/tests/test_fdb_mtl_zero_rows_under_default.py` |
78:**B9.A mini-GATE-CLOSE criteria (charter SC-9):**
80:- Contract template + migration template + MTL guard all unit-tested green.
81:- `pytest --collect-only` count unchanged vs. C0 baseline.
82:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
88:### B9.B — Tier A: 113 simple lookup tables (≤ 5 columns, generic ingester) (10 sessions)
92:**Per-session shape (10 sessions = ~12 tables/session):**
94:- 12 new `TableSpec` definitions per session
95:- 1 batched alembic migration per 25 tables (4 migrations total across B9.B: `0009_fdb_tier_a_part1`..`0009d_fdb_tier_a_part4`) — alternative: a single `0009_fdb_tier_a.py` if review is tractable; codex PLAN consult decides
96:- 12 contract-test wirings per session (each table gets the parity + decode + count + idempotency test set)
97:- 1 partial loader registry update per session (incremental)
103:- 1-4 alembic migrations (`0009_fdb_tier_a*`)
106:- `setup_fdw.sh` foreign-table count: 66 → 179
110:- SC-1 (217 tables have models + migrations + ingester) — partial: +113
111:- SC-2 (RECORD_COUNTS reconciliation) — every loaded Tier A table: actual ÷ expected within ±0.1% tolerance (small lookups should be exact)
112:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
113:- SC-7 (weekly idempotency) — verified for Tier A only at B9.B mini-GATE-CLOSE
114:- SC-8 (test strategy) — contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
115:- SC-9 (mini-GATE-CLOSE) — see below
117:**B9.B mini-GATE-CLOSE criteria:**
119:- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` ± documented tolerance
120:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
125:- `pytest --collect-only` count unchanged vs B9.A C0 baseline ± 113 new contract tests (counted in baseline)
126:- Codex mini-GATE-CLOSE consult: GO
128:**Risk:** 113 tables × ~12/session is aggressive. Mitigation: each session targets contiguous functional groups (e.g., all NDDF BASICS lookups one session; all ETC lookups another) to keep review cohesion. If a session lands fewer tables, the next absorbs the overflow — total session count flexes within the charter's 10-session band.
132:### B9.C — Tier B: 66 NDC/GCN-keyed joins (12 sessions)
134:**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.
136:**Per-session shape (12 sessions = ~5.5 tables/session — slower than Tier A because of join-design + FK-target verification per table):**
138:- 5-6 new `TableSpec` definitions per session
139:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
141:- 1 batched alembic migration per ~25 tables (3 migrations: `0010_fdb_tier_b_part1`..`0010c_fdb_tier_b_part3`)
147:- 3 alembic migrations (`0010_fdb_tier_b*`)
150:- FDW foreign-table count: 179 → 245
152:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
154:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
158:### B9.D — Tier C non-RNDC14: 17 complex/large tables (4 sessions)
160:**Scope:** All 19 Tier C tables EXCEPT the three special-handled ones (RNDC14, RNP2, RPRDPP0). That leaves 17 tables. Complex tables here are > 8 columns or > 50 MB. Includes ETC master, product master (RPRD0_PRODUCT — load before RNDC14), GCN master, etc.
162:**Per-session shape (4 sessions = ~4-5 tables/session):**
164:- 4-5 new `TableSpec` definitions per session
167:- 1 batched alembic migration: `0011_fdb_tier_c_no_rndc14.py`
173:- 1 alembic migration (`0011_fdb_tier_c_no_rndc14.py`)
175:- FDW foreign-table count: 245 → 262
178:**Success criteria:** SC-1 (partial: cum 196/217), SC-2, SC-6 (262/262), SC-7, SC-8 (dedicated Tier C tests), SC-9.
180:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
184:### B9.E — RNDC14 dedicated migration (2 sessions)
186:**Scope:** RNDC14_NDC_MSTR alone — the canonical FDB NDC master, 68 columns, 183 MB, ~501K rows. Highest single-table value in the wave.
188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
190:**Per-session shape (2 sessions):**
192:- Session 1: SQLAlchemy model with all 68 columns, type-mapped (numeric → Decimal where money-relevant; integers where ID; text where descriptor); migration `0012_fdb_rndc14_ndc_mstr.py`; full contract test set
198:- 1 alembic migration (`0012_fdb_rndc14_ndc_mstr.py`)
200:- `tier_c_curation.md` updated with RNDC14 entry (no columns dropped per D1)
201:- FDW foreign-table count: 262 → 263
203:**Success criteria:** SC-1 (cum 197/217), SC-3 (RNDC14 all 68 cols), SC-2, SC-6 (263/263), SC-7, SC-8 (dedicated RNDC14 tests), SC-9.
205:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
209:### B9.F — RNP2 + RPRDPP0 + C0 perf gate (4 sessions)
211:**Scope:** The two large pricing tables explicitly deferred in Phase 09, reversed per charter D2. RNP2_NDC_PRICE (595 MB, 13.2M rows) and RPRDPP0_PRODUCT_PRICE (561 MB). +1.16 GB storage. Includes the **D2 performance gate** (charter SC-4) — not just disk verification.
213:**Per-session shape (4 sessions):**
215:- Session 1: SQLAlchemy models for RNP2 + RPRDPP0; migration `0013_fdb_pricing_big.py`; flip `fdb_load_product_prices=True` default
218:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline
222:- 2 SQLAlchemy models (RNP2 + RPRDPP0)
223:- 1 alembic migration (`0013_fdb_pricing_big.py`)
227:- FDW foreign-table count: 263 → 265
229:**Success criteria:** SC-1 (cum 199/217), SC-4 (D2 perf gate met: timed dry-run + EXPLAIN ANALYZE + storage budget + weekly delta timing all documented), SC-2, SC-6 (265/265), SC-7, SC-8 (RNP2 + RPRDPP0 dedicated behavioral), SC-9.
231:**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4:**
236:- FDW + Postgres verify after indexes built: completes within 5 min
238:- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps
242:### B9.G — Tier D MTL schema-only + loader-registration safeguards (3 sessions)
244:**Scope:** 19 MTL (Medical Test Lexicon) tables. Schema lands; data does NOT load. Per charter D3 + SC-5.
246:**Per-session shape (3 sessions):**
248:- Session 1: 19 SQLAlchemy models in `tier_d/`; migration `0014_fdb_mtl_schema.py` (un-gated, lands schema); 19 contract tests asserting tables exist + are queryable + are EMPTY
249:- Session 2: Loader registry: explicit exclusion of MTL from `--mode fdb_initial` and `--mode fdb_weekly`; opt-in mode `--mode fdb_mtl_data` exists but requires `fdb_load_mtl=True` config flag (charter SC-5 wording)
250:- Session 3: Integration test `test_fdb_mtl_zero_rows_under_default` (from B9.A C4) now exercises the live MTL tables — must continue to assert zero rows after default load. Documentation: `docs/runbooks/fdb-mtl-opt-in.md` explains how to enable IF licensing changes.
255:- 1 alembic migration (`0014_fdb_mtl_schema.py`)
256:- Loader-registration exclusion of MTL from default modes
259:- Updated integration test asserting zero MTL rows after default load
261:- FDW foreign-table count: 265 → 284 (MTL tables ARE in FDW even though data isn't loaded — they exist as foreign-table entries pointing at empty reference tables)
263:**Note on FDW count:** 284 not 283. Recon's target was 283 across 220 - 3 already covered tables = wait, re-checking — actually B9.A's expansion path showed 283 final count. Let me re-derive: 66 (current) + 113 (B9.B) + 66 (B9.C) + 17 (B9.D) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = 284. **The 283 figure in the charter is wrong by 1; B9.H reconciles to the true 284.** This is a charter erratum to surface to codex PLAN consult.
265:**Success criteria:** SC-1 (cum 218/217 — overshoots by 1 due to schema-only MTL — re-examine after PLAN consult), SC-5 (MTL zero-row test green), SC-6 (284/284 — pending erratum), SC-9.
267:**B9.G mini-GATE-CLOSE criteria:**
269:- `0014_fdb_mtl_schema.py` apply + reverse + apply: clean
272:- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)
276:### B9.H — Manifest extension + final closeout (4 sessions)
278:**Scope:** Reconcile `infrastructure/scripts/lib/expected_reference_tables.txt` to the true final count, run final FDW verify, produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
280:**Per-session shape (4 sessions):**
282:- Session 1: Manifest expansion — `expected_reference_tables.txt` final count reconciled (charter said 283; PLAN derives 284; reconcile via codex PLAN consult before B9.H). Update Werkbench inventory + glossary if new tables/concepts warrant.
283:- Session 2: Final `setup_fdw.sh --verify` 284/284 in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables; published in `waves/B9/evidence.md`
284:- Session 3: Cross-tier behavioral suite: NDC lookup goes RNDC14 → RPRD0_PRODUCT → tier-A descriptors → pricing (RNP3, RNP2, RPRDPP0); verifies the wave's value-creation chain
290:- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
297:**Success criteria — ALL SC-1..SC-11:**
299:- SC-1: 217 tables have models + migrations + ingester (verified via `pg_class` count + alembic history scan)
300:- SC-2: RECORD_COUNTS reconciled per table (or documented tolerance / exclusion for MTL)
301:- SC-3: RNDC14 ingest covers all 68 columns
302:- SC-4: D2 perf gate evidence present
303:- SC-5: MTL zero-row test green
304:- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
305:- SC-7: Weekly delta idempotent across all 220 tables (verified at B9.H by running `--mode fdb_weekly` → 0 new rows in all 217 + already-covered 3)
306:- SC-8: Test strategy executed (contract + parity + reconciliation + sampled behavioral + dedicated Tier C)
307:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
308:- SC-10: Final B9 GATE-CLOSE GO or GO-WITH-FIXES (FIXES applied iteratively until GO)
309:- SC-11: Evidence + ship + memory + wave-history all present
311:**B9 final GATE-CLOSE criteria:** codex final consult returns GO. Charter SC-10 escalates only if codex returns GO-WITH-FIXES three times in a row without convergence; that triggers an architectural pause.
315:## Goal-backward verification (per SC)
321:| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == 220; `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
322:| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
323:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
324:| SC-4 | `waves/B9/perf_b9f.md`: timed dry-run, EXPLAIN ANALYZE, storage delta, weekly delta timing | B9.F |
325:| SC-5 | `test_fdb_mtl_zero_rows_under_default` green; opt-in mode reviewed in codex consult | B9.G |
326:| SC-6 | `setup_fdw.sh --verify` output 284/284 in dev + mock (or 283/283 if reconciled to charter count) | B9.H Session 2 |
327:| SC-7 | `load_fdb.py --mode fdb_weekly` re-run logs zero new rows across all 220 tables | B9.H Session 4 |
328:| SC-8 | Test counts per category in evidence.md: 217 contract tests + 220 schema-parity + 217 row-count assertions + N sampled behavioral + dedicated Tier C suite | B9.H Session 2 |
329:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
330:| SC-10 | `waves/B9/codex-gate-close.md` with GO verdict | B9.H Session 4 |
331:| SC-11 | `evidence.md`, `ship.md`, memory file, `wave-history.md` line all present and pointing at the right commits | B9.H Session 4 |
335:## Threat model
339:| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon §7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
340:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
341:| T3 | RNP2 + RPRDPP0 ingest exhausts dev disk (charter R2) | LOW | HIGH | C0 disk check (≥ 5 GB free); B9.F session 2 timed dry-run captures real consumption; abort + escalate if > +1.4 GB |
342:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
343:| T5 | MTL accidentally loads data despite guards (charter R7) | LOW | HIGH | Triple-layer guard: schema-only migration ✓, loader-registry default exclusion ✓, integration test asserts zero rows ✓; B9.G codex consult specifically reviews the guard chain |
344:| T6 | RNDC14 68-column model has wrong type for one or more columns (NUMERIC vs Decimal vs Integer vs Text confusion) | MED | MED | B9.E session 1 produces type-mapping table from DDL `.txt` definitions; session 2 codex column-by-column review |
345:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
346:| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
347:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
348:| T10 | Test count baseline drifts (134 pre-existing failures become 135 or 200) | MED | MED | B9.A C0 captures `pytest --collect-only` count; each phase mini-GATE-CLOSE asserts count unchanged ± new contract tests |
349:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
357:| SPEC R1 | B9.A | Charter v1 dispatched 2026-05-11 | `codex-spec-consult-r1.md` — GO-WITH-FIXES |
358:| SPEC R2 | B9.A | Charter v2 dispatched 2026-05-11 | `codex-spec-consult-r2.md` — GO-WITH-FIXES → cleanup applied → v3 LOCKED |
359:| **PLAN R1** | **B9.A** | **This plan v1 dispatched next** | **`codex-plan-consult-r1.md` — pending** |
360:| ADVERSARIAL R1 | B9.A | After PLAN R1 GO or GO-WITH-FIXES + fix | `codex-adversarial-r1.md` |
361:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
362:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
363:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 17 ingested | `codex-mini-gate-close-D.md` |
364:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
365:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
366:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
367:| GATE-CLOSE | B9.H | Wave shipping artifacts assembled | `codex-gate-close.md` |
378:- MTL data ingest (schema only; flip flag in a later wave IF licensing changes)
379:- RNDC14 column-curation (charter D1 locks full 68-col; no triage)
389:1. **FDW final count: 283 vs 284.** Charter says 283; PLAN's tier-additive derivation gives 284 (66 + 113 + 66 + 17 + 1 + 2 + 19 = 284). The charter figure may have netted the 3 already-covered FDB pricing tables differently. Codex PLAN consult should reconcile before B9.B opens.
390:2. **Migration count: 5 vs 6.** Charter says "0009..0014" (6 migrations); PLAN sub-counts Tier A and Tier B each into ~3-4 part files, which inflates the migration count to 9-10. Codex PLAN consult should rule on batching shape: single big file per tier OR per-25 part files.
391:3. **Loader-orchestration modes: existing vs new.** Charter implies `--mode fdb_weekly` exists; recon shows existing loader has `--mode fdb_initial` only. PLAN assumes both exist; B9.A C4 must verify or add `--mode fdb_weekly`.
397:Per session-framework rules (`.claude/rules/session-framework.md`):
399:- Each B9.X session lands its own evidence row in `waves/B9/sessions.md` (created at B9.A)
400:- At each mini-GATE-CLOSE: full sign-off sheet committed
402:- B9.H final ship: full memory + wave-history entry

 exited 1 in 458ms:
2026-05-11T19:20:51.055348Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.5 seconds
Output:

 succeeded in 448ms:
5:**Goal:** Scope FDB NDDF Plus 220-table extension beyond the 3-table Phase 09 baseline
11:- The FDB drop contains exactly **220 data tables** in `NDDF Plus DB/NDDF PLUS DB.zip`, all with matching ANSI DDL. The current ingester covers **3 tables** (RNP3\_NDC\_PRICE, RPRDPTD0\_PRICE\_TYPE\_DESC, RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC) mapped to **2 DB tables** (`fdb_ndc_price_history`, `fdb_price_type_desc`). Gap: **217 tables**.
12:- Tables span six FDB modules: NDDF BASICS 3.0 (98 tables), MEDNAMES 3.0 (63), ETC 1.0 (16), TALL MAN PLUS 2.0 (15), XRF 1.0 (9), MTL 1.0 (19). MTL (Medical Test Lexicon) is the only module without a clear adjudication use case — treat as a product decision.
13:- The generic `TableSpec`-driven adapter (`FDBLocalDropAdapter.parse_table`) already works for any pipe-delimited FDB table. The ingest architecture is **extension-ready**: new tables become new `TableSpec` constants + SQLAlchemy models + a migration, no adapter surgery required.
14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
27:06MAY2026.TEL251759D/    (Current@ symlink target)
31:**Current/ directory layout:**
35:NDDF Plus DB/NDDF PLUS DB.zip      <- 220 data table files (pipe-delimited, latin-1)
43:- DB zip entries: **220**
44:- ANSI DDL `CREATE TABLE` statements: **220** (+ 1 meta: `NDDF_PRODUCT_INFO`)
54:| NDDF BASICS 3.0 / Pricing | 11 | RNP2, RNP3, RPRDPP0, price attr |
60:| NDDF MTL 1.0 | 19 | Medical Test Lexicon — separate domain |
71:| RMTLLAB0\_LAB\_ID | 5 | 6 KB | LAB\_ID, description, analyte, specimen, type |
78:## Section 2 — Current ingester coverage
86:| `modules/drug-database/drug_database/services/fdb_pricing_ingester.py` | Orchestration: price\_type\_desc + RNP3 ingest |
87:| `modules/drug-database/drug_database/models/fdb_pricing_tables.py` | 2 ORM models |
91:**Currently ingested FDB tables → DB tables:**
95:| RNP3\_NDC\_PRICE | `drug_database.fdb_ndc_price_history` | 13.2M rows; append-only, A/C/D UPD semantics |
96:| RPRDPTD0\_PRICE\_TYPE\_DESC | `drug_database.fdb_price_type_desc` | 20 rows; modern catalog |
97:| RNPTYPD0\_NDC\_PRICE\_TYPE\_DESC | `drug_database.fdb_price_type_desc` | 21 rows; legacy codes with synthetic IDs |
99:**Coverage gap: 217 of 220 FDB tables have no DB mapping.**
112:| RGCNSTR0\_INGREDIENT\_STRENGTH | 15 | 66K | Active ingredient strengths per GCN |
114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
124:- **Tier D** — Medical Test Lexicon (MTL 1.0). 19 tables covering lab analytes, panels, specimen IDs. Structurally simple (most are tiny) but the business question — do adjudication rules need lab linkage? — must be answered before ingest design begins.
126:| Tier | Count | Effort/table | Total effort | Notes |
128:| A — Simple lookups | 113 | 20 min | 37.7h | Generic ingester handles most; 1 TableSpec + 1 model + 1 test |
129:| B — NDC/GCN-keyed joins | 66 | 40 min | 44.0h | NDC normalization, join design, larger test fixtures |
130:| C — Complex/large | 19 | 90 min | 28.5h | RNDC14 (68 cols), two 500 MB+ pricing tables, ETC master |
131:| D — MTL (product decision) | 19 | 30 min | 9.5h | Small tables, pending go/no-go |
132:| **Total** | **217** | — | **119.7h raw** | ~156h with codex review overhead (30%) |
134:**Tier C table inventory (all 19):**
166:| A — One big migration | All 217 tables in `0009_fdb_full.py` | REJECTED — one migration failure blocks everything; impossible to review |
167:| B — One migration per tier | 4 migrations (0009–0012) | Reasonable for small projects; still 66+ models per migration |
168:| C — One migration per table | 217 migrations | Too many migration files; untenable maintenance |
171:**Recommendation: Option D — Tiered phasing with batch migrations.**
173:- `0009_fdb_tier_a.py` — 113 Tier A tables (all small; one migration is reviewable because models are uniform 2–5-col descriptors)
174:- `0010_fdb_tier_b.py` — 66 Tier B tables (NDC/GCN-keyed)
175:- `0011_fdb_tier_c.py` — 19 Tier C tables (but RNDC14 should be its own migration `0011a` given 68-col complexity)
176:- `0012_fdb_tier_d.py` — 19 MTL tables (only if product go decision is made)
180:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
196:**Recommendation: Option G — Hybrid.**
206:**For Tier C (19 tables):**
212:**For Tier D (MTL):**
213:MTL tables are tiny (total uncompressed: ~103 KB). If the product decision is "yes", they fit cleanly into the generic ingester. If "no", skip entirely. No architectural complexity.
215:**Key architectural constraint:** The generic ingester must still use `ON CONFLICT DO NOTHING` for idempotency — same as the existing RNP3 ingester. Weekly re-ingest must be safe to re-run.
223:| Tier A: 113 tables × 20 min | 37.7h |
224:| Tier B: 66 tables × 40 min | 44.0h |
225:| Tier C: 19 tables × 90 min | 28.5h |
226:| Tier D: 19 tables × 30 min (if go) | 9.5h |
228:| FDW manifest expansion (setup_fdw.sh + testing) | 4h |
236:- B9.1 (Tier A, 113 tables): ~10 sessions
237:- B9.2 (Tier B, 66 tables): ~12 sessions
238:- B9.3 (Tier C, 19 tables): ~8 sessions
239:- B9.4 (Tier D, MTL — if go): ~3 sessions
241:**Total: ~34 sessions** (excluding Tier D). This is a multi-month effort at 2–3 sessions/week.
250:The NDC master has 68 columns, many of which are FDB-internal flags with unclear business relevance. Without column curation, the DB table will be bloated and the ORM model unwieldy. Risk: table design gets revisited post-ingest, requiring a costly migration. Mitigation: Before B9.3, produce a column-by-column triage (keep / drop / defer) based on adjudication, formulary, and reclaimrx requirements.
255:**Risk 3 — FDW LIMIT TO list maintenance drift (MEDIUM)**
256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
259:Current FDB ingest: RNP3 (13.2M rows) takes ~minutes. Adding 217 tables including NDC master (501K rows), ETC NDC mapping (616K rows), and MedName tables adds significant volume to the weekly UPD cycle. The UPD zip must also be verified to contain all tables (not just pricing). Mitigation: Profile UPD zip contents against DB zip contents. Validate that `NDDF Plus UPD/` has a matching file for each table before committing to weekly ingest for all 220.
262:The current adapter only reads from UPD for RNP3 (pricing). Some FDB reference tables (e.g., description tables) may ship full-replacement in UPD rather than A/C/D delta. Mitigation: Inspect the UPD zip structure early in B9.1. If some tables are full-replacement (no A/C/D prefix), the ingester must detect this and use TRUNCATE+INSERT rather than ON CONFLICT DO NOTHING.
265:The existing adapter handles latin-1 decoding for RNP3 (numeric-heavy). Text-heavy tables (drug names, descriptions, brand names) are more likely to have characters in the latin-1 extended range (0x80–0xFF). Mitigation: Audit the first 1000 rows of text-column tables (RMIID1\_MED, RNDC14\_NDC\_MSTR brand fields) for decoding failures before schema finalization.
268:At 217 new models, the per-test `create_all()` time in SQLite fixtures will grow. Currently 2 FDB models; adding 217 means each test session creates 219 tables. Risk: slow CI. Mitigation: Split the `FDBPricingBase` into module-level declarative bases (`FDBBasicsBase`, `FDBMedNamesBase`, etc.) so tests only create\_all for the module under test. Plan this in B9.0 before any model files are written.
276:- Charter v1: column triage for RNDC14, pricing table go/no-go decision, MTL go/no-go decision
278:- Design the SQLAlchemy base-splitting strategy (avoid 219-table create\_all in every test)
282:### B9.1 — Tier A: 113 simple lookup tables (target ~10 sessions)
285:- Add 113 `TableSpec` entries to registry in `fdb_adapter.py`
287:- 113 ORM model classes in `fdb_lookup_tables.py` (batched by module)
288:- Integration test: load against real DB zip, verify row counts vs RECORD\_COUNTS.TXT for all 113 tables
289:- FDW manifest update: add 113 table names to `setup_fdw.sh` LIMIT TO list
292:### B9.2 — Tier B: 66 NDC/GCN-keyed tables (target ~12 sessions)
294:- 66 `TableSpec` entries with NDC normalization where applicable
295:- Migration `0010_fdb_tier_b.py`
296:- ORM models in `fdb_link_tables.py`
299:- FDW manifest update: +66 entries
302:### B9.3 — Tier C: 19 complex tables (target ~8 sessions)
309:- FDW manifest update: +19 entries
312:### B9.4 — Tier D: MTL (19 tables) — CONDITIONAL on product decision
315:- All 19 MTL tables are tiny (total 103 KB) — one session if go decision is made
316:- Migration `0012_fdb_tier_d.py`, generic ingester handles all 19
322:1. **RNDC14\_NDC\_MSTR column triage**: Which of the 68 columns does InfinityRx actually need? Full 68-column ingest vs. curated subset has significant implications for model maintainability and storage. Required before B9.3 begins.
324:2. **Pricing table go/no-go (RNP2 + RPRDPP0)**: Both were explicitly deferred in Phase 09. RNP2 is the legacy pricing file (overlaps with RNP3 data); RPRDPP0 is product-level pricing (vs. RNP3's NDC-level). Decision needed: are either of these required for adjudication accuracy, or is RNP3 sufficient?
326:3. **MTL go/no-go**: Does any planned adjudication rule or reclaimrx detection require lab test linkage (NDDF MTL 1.0)? If yes, B9.4 is in scope. If no, all 19 MTL tables are permanently skipped.
328:4. **Wave boundary — is B9 one wave or two?**: 34 sessions is 3–4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.

 succeeded in 460ms:
18:| D1 | **RNDC14 = full 68-column ingest** | Future-proof; avoids N+1 schema-extension waves as consumers surface column needs. |
19:| D2 | **RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE = include + load by default** | Reverses Phase 09 `fdb_load_product_prices=False` deferral. +1.16 GB storage required; needs disk + Postgres performance verification at C0. |
20:| D3 | **Medical Test Lexicon (MTL) = schema-only, no data load** | Honors "clinical screening NOT subscribed" memory while landing table structure for future activation. 19 tables, 103 KB raw. If licensing changes, flip a config flag. |
29:| W3 | Tier C — complex/large + RNDC14 full + RNP2 + RPRDPP0 + perf gate | 19 | ~10 sessions (8 baseline + ~2 D2 perf gate) |
30:| W4 | Tier D — MTL schema-only (no data load) | 19 | ~3 sessions |
31:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
33:**Total: ~39 sessions** (recon's A+B+C estimate is 34; +3 Tier D + ~2 D2 perf gate = 39). With codex review cadence already baked into per-phase budget. **Charter v1's 100-session figure was a misread; v2 corrects to recon's actual numbers.** Wall-clock at 3 sessions/week: ~13 weeks (~3 months).
44:B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
48:| B9.A | Charter v2 + plan v1 + codex SPEC R2 / PLAN / ADVERSARIAL | 2-3 | Plan v1 locked |
49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
51:| B9.D | Tier C non-RNDC14 — 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** — column-by-column model review |
53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** — perf test results + EXPLAIN ANALYZE + storage budget verification |
54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** — integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
55:| B9.H | Manifest extension (66 → 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** — full cross-tier consult |
61:| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
65:| SC-5 | MTL schema lands but **runtime/loader guards** prevent data load: `fdb_load_mtl=False` default; MTL tables excluded from default loader registry; integration test asserts **zero MTL rows** after default `load_fdb.py --mode fdb_weekly`. Alembic migration itself is NOT config-gated (per codex SPEC R1 #4). |
66:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
67:| SC-7 | Weekly delta ingest path idempotent across all 220 tables (ON CONFLICT DO NOTHING or UPSERT per table; verified by re-running) |
68:| SC-8 | **Test coverage strategy** (per codex SPEC R1 #6): contract coverage for every `TableSpec`; schema/model parity for every table; row-count reconciliation for every loaded table; sampled behavioral tests per tier; dedicated Tier C tests for RNDC14 / RNP2 / RPRDPP0 / weekly delta. **No bespoke per-table behavioral tests** for the 217 tables — too heavy. |
69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
70:| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
71:| SC-11 | Evidence + ship + memory + wave-history + B9 phased-progress dashboard |
73:## SPEC-locked migration granularity (codex SPEC R1 #5 fix)
75:**Migration granularity is SPEC-locked**, not deferred to plan:
76:- **NO** one-table-per-migration (213 migrations would be unmaintainable)
77:- **NO** single 217-table migration (atomicity ruined; review intractable)
78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
85:| R1 | 217 alembic migrations is unwieldy for review | SPEC-locked above to ~6 per-phase batched migrations + RNDC14 standalone. |
86:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
87:| R3 | RNDC14 68 columns include latin-1 quirks (mixed-case names, accented chars, NULL sentinels) | Per-column normalization pass in ingester; latin-1 → UTF-8 with replacement strategy documented |
88:| R4 | FDB weekly delta breaks because some tables ship NEW columns | Schema version detection + drift logging; halt ingest on unrecognized column |
89:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
90:| R6 | 6-month wall-clock invites scope drift / charter decay | Phased execution table is contract; each phase has explicit closure gate |
91:| R7 | MTL schema accidentally activates (data ingest fires when it shouldn't) | Config flag `fdb_load_mtl=False` enforced via integration test; CI gate denies MTL data on default flag |
102:**~39 sessions × 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong — corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.

 succeeded in 539ms:
shared\config.py:64:    model_config = SettingsConfigDict(
shared\config.py:133:    @field_validator("CORS_ALLOW_ORIGINS", mode="before")
shared\ai\openai_client.py:40:def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
shared\ai\openai_client.py:41:    rates = _COST_PER_1K.get(model, _DEFAULT_COST)
shared\ai\openai_client.py:87:    model_config = {"env_prefix": "AZURE_OPENAI_", "extra": "ignore"}
shared\ai\openai_client.py:98:    model: str
shared\ai\openai_client.py:114:    model: str = "gpt-4.1"
shared\ai\openai_client.py:124:    model: str
shared\ai\openai_client.py:155:    def _resolve_deployment(self, model: str) -> str:
shared\ai\openai_client.py:156:        if "mini" in model:
shared\ai\openai_client.py:173:        deployment = self._resolve_deployment(request.model)
shared\ai\openai_client.py:179:                    model=deployment,
shared\ai\openai_client.py:188:                cost = _estimate_cost(request.model, prompt_tokens, completion_tokens)
shared\ai\openai_client.py:192:                    model=request.model,
shared\ai\openai_client.py:202:                    model=raw.model,
shared\events\dlq.py:22:from shared.db.models.events import EventDLQEntry
shared\crypto\sqlalchemy_types.py:27::func:`~shared.crypto.aes.decrypt` primitives directly in your model layer.
shared\events\bus.py:6:Publishing modes
shared\events\bus.py:20:   See ``shared.events.outbox`` for the OutboxEntry model and OutboxRelay.
shared\events\dlq_sink.py:12:    from shared.db.models.events import EventDLQEntry
shared\events\dlq_repository.py:31:from shared.db.models.events import EventDLQEntry
shared\events\in_memory_bus.py:40:            envelope = envelope.model_copy(update={"correlation_id": ctx_cid})
shared\db\test_factories.py:157:        "model_used": "gpt-4.1",
shared\db\test_factories.py:166:               input_type, model_used, status)
shared\db\test_factories.py:169:                    %(model_used)s, %(status)s)
shared\db\test_factories.py:245:        "model_used": "text-embedding-3-small",
shared\db\test_factories.py:254:               embedding, model_used)
shared\db\test_factories.py:257:                    %(model_used)s)
shared\db\tenant_context.py:18:3. Any ORM model inheriting from :class:`TenantScopedMixin` is filtered.
shared\db\tenant_context.py:85:# Mixin applied to tenant-scoped ORM models
shared\db\tenant_context.py:91:    """Mixin that marks a model as tenant-scoped and declares ``tenant_id``."""
shared\db\tenant_context.py:129:    model without an active tenant context and without the exempt flag.
shared\db\tenant_context.py:147:        return  # Query touches only non-tenant-scoped models — safe.
shared\auth\dependencies.py:3:The shared layer does not know about SQLAlchemy models; instead it takes a
shared\events\rabbitmq_bus.py:38:from shared.db.models.events import EventDLQEntry
shared\events\rabbitmq_bus.py:196:            envelope = envelope.model_copy(update={"correlation_id": ctx_cid})
shared\events\rabbitmq_bus.py:209:            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
shared\data_ingestion\__init__.py:11:    from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\events\outbox.py:67:    """Declarative base for outbox-only models."""
shared\events\types.py:41:    model_config = ConfigDict(frozen=True)
shared\events\types.py:59:    def model_post_init(self, __context: Any) -> None:
scripts\setup_demo.py:28:import argparse
scripts\setup_demo.py:339:    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
shared\utils\secret_box.py:9:- Banking has its own threat model: no AAD-by-default, no string
shared\utils\secret_box.py:116:    key / truncation. Callers must NOT distinguish failure modes
modules\core-platform\tests\test_main_auth_wired.py:24:from src.auth._models import Base as AuthBase
modules\core-platform\tests\test_main_auth_wired.py:25:from src.auth._models import Tenant, User
modules\core-platform\tests\test_main_auth_wired.py:36:    ``src.auth._models.Base`` — a different declarative base than the
shared\db\models\__init__.py:1:"""Aggregated import site for all shared ORM models.
shared\db\models\__init__.py:3:Importing this package ensures every model class is registered on
shared\db\models\__init__.py:8:from shared.db.models import core as core  # noqa: F401
shared\db\models\__init__.py:9:from shared.db.models.bank_holidays import BankHoliday  # noqa: F401
shared\db\models\__init__.py:10:from shared.db.models.events import EventDLQEntry, ProcessedEvent  # noqa: F401
shared\db\models\__init__.py:11:from shared.db.models.sessions import UserSession  # noqa: F401
shared\utils\phone_validation.py:23:Strict mode (``strict=True``): raise ``PhoneValidationError`` on
shared\utils\phone_validation.py:43:    """Raised in strict mode when a phone value can't be coerced
shared\db\models\sessions.py:1:"""ORM model for ``core.sessions``.
modules\core-platform\tests\auth\test_tenant_isolation.py:12:    from src.auth._models import User
modules\core-platform\tests\auth\test_seed_system_roles.py:7:from src.auth._models import Permission, Role, RolePermission
shared\db\models\sam_exclusions.py:1:"""ORM model for SAM.gov federal exclusion list.
scripts\load_sam.py:14:(empty → seed, non-empty → delta). Override with --mode.
scripts\load_sam.py:40:import argparse
scripts\load_sam.py:118:    mode: str
scripts\load_sam.py:286:def _resolve_mode(cli_mode: str | None) -> str:
scripts\load_sam.py:287:    if cli_mode:
scripts\load_sam.py:288:        return cli_mode
scripts\load_sam.py:290:        log.info("auto-mode: table empty → seed")
scripts\load_sam.py:292:    log.info("auto-mode: table populated → delta")
scripts\load_sam.py:296:def _resolve_since(mode: str, cli_since: date | None) -> date | None:
scripts\load_sam.py:297:    if mode == "seed":
scripts\load_sam.py:299:    if mode == "backfill":
scripts\load_sam.py:301:            raise SystemExit("--mode backfill requires --since YYYY-MM-DD")
scripts\load_sam.py:309:            "delta mode but no state file at data/reference/sam_exclusions/.last_run. "
scripts\load_sam.py:310:            "Run --mode seed first, or pass --since YYYY-MM-DD, or use --mode backfill."
scripts\load_sam.py:321:def load(mode: str, since: date | None, api_key: str) -> LoadResult:
scripts\load_sam.py:324:    return _load_from_file(mode, since, extract_path)
scripts\load_sam.py:327:def _load_from_file(mode: str, since: date | None, extract_path: Path) -> LoadResult:
scripts\load_sam.py:435:        mode=mode,
scripts\load_sam.py:538:    No download, no upsert. Used by --mode cross-ref-only. Applies active
scripts\load_sam.py:597:    parser = argparse.ArgumentParser(description="Load SAM.gov exclusions (Wave 8).")
scripts\load_sam.py:599:        "--mode",
scripts\load_sam.py:602:        help="Load mode. Default: auto (seed if table empty, else delta). "
scripts\load_sam.py:625:    # cross-ref-only mode doesn't need SAM_API_KEY or a source-of-truth
scripts\load_sam.py:626:    # mode resolution — it just runs UPDATE against whatever's already in
scripts\load_sam.py:628:    if args.mode == "cross-ref-only":
scripts\load_sam.py:629:        log.info("starting: mode=cross-ref-only")
scripts\load_sam.py:637:    mode = _resolve_mode(args.mode)
scripts\load_sam.py:638:    since = _resolve_since(mode, args.since)
scripts\load_sam.py:640:    run_id = _create_run(mode)
scripts\load_sam.py:643:    log.info("starting: mode=%s since=%s", mode, since)
scripts\load_sam.py:645:        result = load(mode, since, api_key)
shared\db\models\phi_mixin.py:13:    from shared.db.models.phi_mixin import PHIMixin
shared\db\models\phi_mixin.py:23:Why a mixin vs per-column ``EncryptedString`` on the model directly?
modules\core-platform\tests\auth\test_roles_api.py:9:from src.auth._models import Role
modules\core-platform\alembic\env.py:29:from shared.db.models import core as _core_models  # noqa: E402,F401
modules\core-platform\alembic\env.py:100:if context.is_offline_mode():
shared\db\models\oig_leie_exclusions.py:1:"""ORM model for the OIG LEIE federal exclusion list.
scripts\load_rxnorm.py:31:import argparse
scripts\load_rxnorm.py:153:    parser = argparse.ArgumentParser(description="Load RxNorm")
shared\db\models\ofac_sdn.py:1:"""ORM models for OFAC SDN (Specially Designated Nationals) reference tables.
modules\core-platform\tests\auth\test_misc_coverage.py:11:from src.auth._models import GUID, Role
scripts\load_rxnorm [conflicted].py:31:import argparse
scripts\load_rxnorm [conflicted].py:157:    parser = argparse.ArgumentParser(description="Load RxNorm")
modules\core-platform\tests\auth\test_mfa_login_gate.py:21:from src.auth._models import Tenant, User
scripts\load_orange_book.py:25:import argparse
scripts\load_orange_book.py:152:    parser = argparse.ArgumentParser(description="Load FDA Orange Book")
shared\db\models\icd10_cm_codes.py:1:"""ORM model for the CMS ICD-10-CM diagnosis code set.
shared\utils\decimal_jsonb.py:100:    Strict mode (default) raises DecimalJSONBError on:
shared\utils\decimal_jsonb.py:107:    Lenient mode (``strict=False``) attempts ``Decimal(str(v))``
scripts\load_orange_book [conflicted].py:25:import argparse
scripts\load_orange_book [conflicted].py:156:    parser = argparse.ArgumentParser(description="Load FDA Orange Book")
shared\db\models\hcpcs_codes.py:1:"""ORM model for the CMS HCPCS Level II code set.
modules\core-platform\tests\notifications\test_service.py:12:from src.notifications.models import NotificationPreference
modules\core-platform\tests\notifications\test_service.py:285:    from src.notifications.models import Notification as _N
shared\db\models\events.py:1:"""ORM models for event bus reliability tables.
modules\core-platform\tests\notifications\test_routing.py:9:from src.notifications.models import Notification
shared\db\models\core.py:1:"""ORM models for the ``core`` schema.
modules\core-platform\tests\auth\sessions\test_session_service.py:19:from src.auth._models import Base, Tenant, User
modules\core-platform\tests\auth\sessions\test_session_service.py:20:from src.auth.sessions.models import Session_ as SessionRow
modules\core-platform\tests\notifications\test_api.py:13:from src.notifications.models import Notification, NotificationPreference
shared\db\models\bank_holidays.py:1:"""ORM model for the ``core.bank_holidays`` table.
scripts\load_nppes.py:4:  download -> scrape CMS index for the chosen mode
scripts\load_nppes.py:6:  load     -> nppes_upsert + satellite services (csv modes)
scripts\load_nppes.py:7:              OR batched UPDATE prescribers.status (deactivation mode)
scripts\load_nppes.py:11:    python scripts/load_nppes.py [--mode weekly|monthly|deactivation]
scripts\load_nppes.py:15:    --mode      which CMS file to fetch (default: weekly)
scripts\load_nppes.py:21:                (weekly mode only, using the bundled synthetic sample.)
scripts\load_nppes.py:23:                (weekly mode only.)
scripts\load_nppes.py:31:import argparse
scripts\load_nppes.py:185:async def _run(mode: str, sample: bool) -> None:
scripts\load_nppes.py:196:        ingester = NppesIngester(db_session=session, mode=mode)  # type: ignore[arg-type]
scripts\load_nppes.py:199:            if mode != "weekly":
scripts\load_nppes.py:200:                logger.error("--sample is only supported with --mode weekly")
scripts\load_nppes.py:206:            logger.info("Starting NPPES pipeline (mode=%s)...", mode)
scripts\load_nppes.py:236:    parser = argparse.ArgumentParser(description="Load CMS NPPES data")
scripts\load_nppes.py:238:        "--mode",
scripts\load_nppes.py:275:             "(weekly mode only).",
scripts\load_nppes.py:287:        asyncio.run(_run(mode=args.mode, sample=args.sample))
modules\core-platform\alembic\versions\0015_widen_sam_exclusions_zip.py:19:No other columns changed by this migration. The SQLAlchemy model at
modules\core-platform\alembic\versions\0015_widen_sam_exclusions_zip.py:20:shared/db/models/sam_exclusions.py had drifted from the DB
modules\core-platform\alembic\versions\0015_widen_sam_exclusions_zip.py:22:in the model file in the same commit, but the DB widths themselves
modules\core-platform\tests\auth\conftest.py:17:from src.auth._models import Base, Tenant, User
scripts\load_nppes [conflicted].py:4:  download -> scrape CMS index for the chosen mode
scripts\load_nppes [conflicted].py:6:  load     -> nppes_upsert + satellite services (csv modes)
scripts\load_nppes [conflicted].py:7:              OR batched UPDATE prescribers.status (deactivation mode)
scripts\load_nppes [conflicted].py:11:    python scripts/load_nppes.py [--mode weekly|monthly|deactivation]
scripts\load_nppes [conflicted].py:15:    --mode      which CMS file to fetch (default: weekly)
scripts\load_nppes [conflicted].py:21:                (weekly mode only, using the bundled synthetic sample.)
scripts\load_nppes [conflicted].py:23:                (weekly mode only.)
scripts\load_nppes [conflicted].py:31:import argparse
scripts\load_nppes [conflicted].py:185:async def _run(mode: str, sample: bool) -> None:
scripts\load_nppes [conflicted].py:196:        ingester = NppesIngester(db_session=session, mode=mode)  # type: ignore[arg-type]
scripts\load_nppes [conflicted].py:199:            if mode != "weekly":
scripts\load_nppes [conflicted].py:200:                logger.error("--sample is only supported with --mode weekly")
scripts\load_nppes [conflicted].py:206:            logger.info("Starting NPPES pipeline (mode=%s)...", mode)
scripts\load_nppes [conflicted].py:236:    parser = argparse.ArgumentParser(description="Load CMS NPPES data")
scripts\load_nppes [conflicted].py:238:        "--mode",
scripts\load_nppes [conflicted].py:275:             "(weekly mode only).",
scripts\load_nppes [conflicted].py:287:        asyncio.run(_run(mode=args.mode, sample=args.sample))
shared\db\base.py:25:    """Project-wide ORM base. All models inherit from this class."""
shared\tests\validation\test_types.py:38:def test_npi_valid_via_model():
shared\tests\validation\test_types.py:58:def test_npi_model_rejects_invalid():
shared\tests\validation\test_types.py:187:def test_date_model_valid():
shared\tests\validation\test_types.py:192:def test_date_model_rejects_invalid():
scripts\load_new_sources.py:21:import argparse
scripts\load_new_sources.py:111:    parser = argparse.ArgumentParser()
modules\core-platform\alembic\versions\0011_gpb_id_to_uuid.py:4:as VARCHAR(36) with `gen_random_uuid()::text` default, but the ORM model
modules\core-platform\alembic\versions\0011_gpb_id_to_uuid.py:5:at shared/models/gov_exclusion_tables.py declares it as
modules\core-platform\alembic\versions\0011_gpb_id_to_uuid.py:6:`PG_UUID(as_uuid=True)`. Any ORM upsert through the model (e.g. from
scripts\load_ncpdp.py:29:import argparse
scripts\load_ncpdp.py:128:    parser = argparse.ArgumentParser(description=__doc__)
modules\edi-compliance\tests\unit\test_validator.py:92:        test_mode=True,
modules\edi-compliance\tests\unit\test_validator.py:129:        test_mode=True,
modules\core-platform\tests\jobs\test_scheduler.py:18:from src.models import Job, JobRun
modules\edi-compliance\tests\unit\test_trading_partners_api.py:37:        self.test_mode = True
modules\edi-compliance\tests\unit\test_trading_partners_api.py:142:                "test_mode": True,
modules\edi-compliance\tests\unit\test_trading_partners_api.py:181:        test_mode=False,
scripts\load_icd10.py:16:import argparse
scripts\load_icd10.py:92:    parser = argparse.ArgumentParser(description=__doc__)
scripts\load_icd10 [conflicted].py:16:import argparse
scripts\load_icd10 [conflicted].py:96:    parser = argparse.ArgumentParser(description=__doc__)
modules\core-platform\tests\auth\api_keys\test_api_key_service.py:18:from src.auth._models import Base, Tenant, User
modules\core-platform\tests\auth\api_keys\test_api_key_service.py:19:from src.auth.api_keys.models import ApiKey
modules\core-platform\tests\auth\api_keys\test_api_key_service.py:260:        assert hasattr(k, "key_hash")  # hash is on model but raw key isn't returned
scripts\load_hcpcs.py:18:import argparse
scripts\load_hcpcs.py:97:    parser = argparse.ArgumentParser(description=__doc__)
shared\tests\utils\test_phone_validation.py:14:# Lenient mode (default)
shared\tests\utils\test_phone_validation.py:76:# Strict mode
scripts\load_hcpcs [conflicted].py:18:import argparse
scripts\load_hcpcs [conflicted].py:101:    parser = argparse.ArgumentParser(description=__doc__)
scripts\load_fdb.py:5:`fdb_ndc_price_history`. Three modes per SPEC §4.7:
scripts\load_fdb.py:7:  --mode fdb_initial   one-time full DB.zip baseline (~15.6M rows)
scripts\load_fdb.py:8:  --mode fdb_weekly    routine UPD.zip application (typical ~10k-100k)
scripts\load_fdb.py:9:  --mode fdb_rebase    operator-triggered DB.zip re-baseline (recovery)
scripts\load_fdb.py:18:    python scripts/load_fdb.py --mode fdb_weekly
scripts\load_fdb.py:19:    python scripts/load_fdb.py --mode fdb_initial --dry-run
scripts\load_fdb.py:27:import argparse
scripts\load_fdb.py:43:logger = logging.getLogger("load_fdb")
scripts\load_fdb.py:66:    parser = argparse.ArgumentParser(description=__doc__)
scripts\load_fdb.py:68:        "--mode",
scripts\load_fdb.py:69:        choices=["fdb_initial", "fdb_weekly", "fdb_rebase"],
scripts\load_fdb.py:71:        help="ingestion mode (SPEC §4.7)",
scripts\load_fdb.py:108:        result = ingester.run(mode=args.mode, dry_run=args.dry_run)
scripts\load_fdb.py:114:        "fdb_ingest_summary mode=%s drop_date=%s "
scripts\load_fdb.py:118:        result.mode,
shared\tests\data_ingestion\dataq_ncpdp\test_parser.py:5:date parsing, flag parsing, CRLF vs LF, strict mode).
shared\tests\data_ingestion\dataq_ncpdp\test_parser.py:124:def test_malformed_date_lenient_mode_is_none(tmp_path):
shared\tests\data_ingestion\dataq_ncpdp\test_parser.py:131:def test_malformed_date_strict_mode_raises(tmp_path):
shared\tests\data_ingestion\dataq_ncpdp\test_parser.py:139:    """02/30/2020 isn't a valid date. Lenient mode returns None."""
shared\tests\utils\test_decimal_jsonb.py:98:    """Strict mode rejects values that don't match -?DDD.DD."""
shared\tests\utils\test_decimal_jsonb.py:123:    """Lenient mode reads historical rows that pre-date the strict
modules\reclaimrx\tests\wave44b\unit\test_refinement_rules.py:83:        "mode_count": 2,
modules\reclaimrx\tests\wave44b\unit\test_refinement_rules.py:188:            mode_count=3,
modules\core-platform\tests\audit\test_service_hash_chain.py:13:from src.audit.models import AuditLog
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:49:    meta = det.model_metadata()
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:84:    artifact_dir = tmp_dir / "test_model"
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:86:    joblib.dump(clf, artifact_dir / "model.joblib")
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:90:        json.dump({"model_type": "random_forest", "roc_auc": 0.9}, f)
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:97:        model_artifact_path=str(tmp_path / "nonexistent"),
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:107:        model_artifact_path=str(artifact_dir),
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:119:        model_artifact_path=str(artifact_dir),
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:127:    assert result.model_version == "2"
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:134:        model_artifact_path=str(artifact_dir),
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:150:        model_artifact_path=str(tmp_path / "absent"),
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:157:def test_sklearn_detector_model_metadata_after_load(tmp_path):
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:161:        model_artifact_path=str(artifact_dir),
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:166:    meta = det.model_metadata()
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:167:    assert meta.get("model_type") == "random_forest"
modules\reclaimrx\tests\wave44b\unit\test_ml_framework.py:185:    pred = MLPrediction(score=Decimal("0.75"), model_version="1")
modules\billing\tests\unit\test_tenant_loader_wired.py:5:billing model that inherits ``TenantScopedMixin`` would silently fall
scripts\load_fda_ndc.py:26:import argparse
scripts\load_fda_ndc.py:138:    parser = argparse.ArgumentParser(description="Load FDA NDC Directory")
modules\core-platform\tests\audit\test_middleware_units.py:47:    from src.audit.models import AuditLog
modules\core-platform\tests\audit\test_middleware_units.py:257:    from src.audit.models import AuditLog
modules\core-platform\tests\audit\test_middleware_units.py:285:    from src.audit.models import AuditLog
scripts\load_fda_ndc [conflicted].py:26:import argparse
scripts\load_fda_ndc [conflicted].py:142:    parser = argparse.ArgumentParser(description="Load FDA NDC Directory")
modules\core-platform\tests\audit\test_middleware.py:15:from src.audit.models import AuditLog
scripts\load_cms_nadac.py:22:import argparse
scripts\load_cms_nadac.py:123:    parser = argparse.ArgumentParser(description="Load CMS NADAC pricing data")
scripts\load_cms_nadac [conflicted].py:22:import argparse
scripts\load_cms_nadac [conflicted].py:127:    parser = argparse.ArgumentParser(description="Load CMS NADAC pricing data")
modules\edi-compliance\tests\unit\test_gen_999_ta1.py:86:    def test_production_mode(self):
modules\edi-compliance\tests\unit\test_gen_999_ta1.py:87:        result = generate_999(_req999(test_mode=False), now=_FIXED_NOW)
modules\edi-compliance\tests\unit\test_gen_999_ta1.py:179:    def test_production_mode(self):
modules\edi-compliance\tests\unit\test_gen_999_ta1.py:180:        result = generate_ta1(_reqta1(test_mode=False), now=_FIXED_NOW)
shared\tests\test_harness\test_scheduled_changes.py:76:    # The harness issues ORM SELECTs against tenant-scoped models
modules\edi-compliance\tests\unit\test_gen_837i.py:44:        test_mode=True,
modules\edi-compliance\tests\unit\test_gen_837i.py:155:    def test_production_mode(self):
modules\edi-compliance\tests\unit\test_gen_837i.py:156:        req = _base_req(test_mode=False)
scripts\load_cms_asp.py:23:import argparse
scripts\load_cms_asp.py:131:    parser = argparse.ArgumentParser(description="Load CMS ASP pricing")
modules\core-platform\tests\audit\test_api.py:14:from src.audit.models import AuditLog
modules\edi-compliance\tests\unit\test_gen_837d.py:43:        test_mode=True,
modules\edi-compliance\tests\unit\test_gen_837d.py:125:    def test_production_mode(self):
modules\edi-compliance\tests\unit\test_gen_837d.py:126:        req = _base_req(test_mode=False)
scripts\load_cms_asp [conflicted].py:23:import argparse
scripts\load_cms_asp [conflicted].py:135:    parser = argparse.ArgumentParser(description="Load CMS ASP pricing")
shared\tests\crypto\test_sqlalchemy_types.py:41:# Minimal SQLAlchemy models for testing (in-memory SQLite)
shared\tests\test_config.py:31:        "model_config",
shared\tests\test_config.py:32:        {**config_mod.Settings.model_config, "env_file": None},
shared\tests\test_config.py:41:    # Reset the Settings.model_config env_file to None via a fresh class eval.
modules\edi-compliance\tests\unit\test_gen_278.py:114:    def test_production_mode(self):
modules\edi-compliance\tests\unit\test_gen_278.py:115:        result = generate_278(_base_req(test_mode=False), now=_FIXED_NOW)
modules\edi-compliance\tests\unit\test_gen_271_276_277.py:109:    def test_production_mode(self):
modules\edi-compliance\tests\unit\test_gen_271_276_277.py:110:        result = generate_271(self._req(test_mode=False), now=_FIXED_NOW)
modules\edi-compliance\tests\unit\test_gen_271_276_277.py:192:    def test_production_mode(self):
modules\edi-compliance\tests\unit\test_gen_271_276_277.py:193:        result = generate_276(self._req(test_mode=False), now=_FIXED_NOW)
modules\edi-compliance\tests\unit\test_gen_271_276_277.py:294:    def test_production_mode(self):
modules\edi-compliance\tests\unit\test_gen_271_276_277.py:295:        result = generate_277(self._req(test_mode=False), now=_FIXED_NOW)
modules\edi-compliance\tests\unit\test_generate_api_branches.py:58:                "test_mode": True,
modules\switch-connectivity\tests\integration\test_pipeline_stages_1_to_5.py:83:    Stage 3 runs in NotImplementedError stub-passthrough mode (Session 7
scripts\lint\check_module_boundaries.py:9:import argparse
scripts\lint\check_module_boundaries.py:84:    parser = argparse.ArgumentParser(
modules\edi-compliance\tests\unit\test_envelope_branches.py:15:def test_build_isa_test_mode():
modules\edi-compliance\tests\unit\test_envelope_branches.py:16:    """build_isa with test_mode=True uses ISA15=T."""
modules\edi-compliance\tests\unit\test_envelope_branches.py:24:        test_mode=True,
modules\edi-compliance\tests\unit\test_envelope_branches.py:31:def test_build_isa_production_mode():
modules\edi-compliance\tests\unit\test_envelope_branches.py:32:    """build_isa with test_mode=False uses ISA15=P."""
modules\edi-compliance\tests\unit\test_envelope_branches.py:40:        test_mode=False,
modules\reclaimrx\tests\wave44b\integration\test_ml_schema_and_training.py:276:        model_type="xgboost",
modules\reclaimrx\tests\wave44b\integration\test_ml_schema_and_training.py:281:    assert (tmp_path / "artifacts" / detector_name / "model.joblib").exists()
modules\reclaimrx\tests\wave44b\integration\test_ml_schema_and_training.py:324:        model_artifact_path=str(tmp_path / name),
modules\reclaimrx\tests\wave44b\integration\test_ml_schema_and_training.py:338:    joblib.dump(clf, art / "model.joblib")
modules\core-platform\src\_shim\db.py:24:    """Declarative base shared by all core-platform models."""
scripts\graphify\sessionstart_hook.sh:2:# graphify SessionStart hook: 30-min debounced reminder to run /graphify --mode deep --update
scripts\graphify\sessionstart_hook.sh:10:#     agent to run "/graphify --mode deep --update <scope>".
scripts\graphify\sessionstart_hook.sh:53:Run /graphify --mode deep --update $SCOPE
shared\data_ingestion\tests\test_state_medicaid_loader.py:58:from shared.models.gov_exclusion_tables import GovernmentProgramBin
shared\data_ingestion\tests\test_state_medicaid_loader.py:139:        join_transaction_mode="create_savepoint",
modules\reclaimrx\tests\wave44b\integration\test_baseline_extensions.py:273:def test_pharmacy_ndc_nq_distribution_extended_computes_mode_count(
modules\reclaimrx\tests\wave44b\integration\test_baseline_extensions.py:281:    # 3 distinct cost values → mode_count=3
modules\reclaimrx\tests\wave44b\integration\test_baseline_extensions.py:293:    assert result.get("mode_count", 0) == 3
shared\data_ingestion\tests\test_scheduler.py:25:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_scheduler.py:459:# DEFAULT_SCHEDULES — NPPES mode coverage (Wave 11 commit 5)
shared\data_ingestion\tests\test_scheduler.py:463:def test_default_schedules_has_all_three_nppes_modes() -> None:
shared\data_ingestion\tests\test_scheduler.py:480:def test_default_schedules_nppes_modes_do_not_collide() -> None:
scripts\cleanup_test_tenant.py:17:import argparse
scripts\cleanup_test_tenant.py:33:    parser = argparse.ArgumentParser(description=__doc__)
shared\data_ingestion\tests\test_sam_exclusions.py:44:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_sam_exclusions.py:51:from shared.db.models.sam_exclusions import SamExclusion
shared\data_ingestion\tests\test_sam_exclusions.py:145:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_sam_exclusions.py:231:        """All expected SAM ORM columns must exist on the model."""
shared\data_ingestion\tests\test_sam_exclusions.py:232:        model_cols = {col.key for col in SamExclusion.__table__.columns}
shared\data_ingestion\tests\test_sam_exclusions.py:241:        missing = expected - model_cols
shared\data_ingestion\tests\test_sam_exclusions.py:242:        assert not missing, f"SAM ORM model missing columns: {missing}"
modules\core-platform\tests\conftest.py:6:- T3 (audit/notifications) model registration + tenant/user ID fixtures
modules\core-platform\tests\conftest.py:39:# --- T3: register audit + notification models on the shim Base so
modules\core-platform\tests\conftest.py:41:from src.audit import models as _audit_models  # noqa: F401,E402
modules\core-platform\tests\conftest.py:42:from src.notifications import models as _notif_models  # noqa: F401,E402
scripts\bench_nppes_satellite.py:14:  3. Call ``load_nppes_satellite_tables(db, tmp_csv, use_copy=<mode>)``.
scripts\bench_nppes_satellite.py:30:import argparse
scripts\bench_nppes_satellite.py:162:    parser = argparse.ArgumentParser(description=__doc__)
modules\edi-compliance\tests\unit\test_compliance_api.py:151:def test_trading_partner_response_model():
modules\edi-compliance\tests\unit\test_compliance_api.py:164:        test_mode=True,
modules\edi-compliance\tests\unit\test_compliance_api.py:171:def test_trading_partner_create_model():
modules\edi-compliance\tests\unit\test_compliance_api.py:182:        test_mode=False,
scripts\bench_fdb_lookup.py:30:import argparse
scripts\bench_fdb_lookup.py:186:def _build_parser() -> argparse.ArgumentParser:
scripts\bench_fdb_lookup.py:187:    parser = argparse.ArgumentParser(
shared\data_ingestion\tests\test_rxnorm.py:13:  - test_no_source_fields_dropped               — all 53 fields in model columns
shared\data_ingestion\tests\test_rxnorm.py:68:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_rxnorm.py:80:from drug_database.models.rxnorm_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_rxnorm.py:248:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_rxnorm.py:319:# 2. No source fields dropped — all 53 column names exist in ORM models
shared\data_ingestion\tests\test_rxnorm.py:325:        """All 18+16+13+6=53 RRF field names appear as columns in models."""
modules\switch-connectivity\tests\integration\fixtures\valid_d0_payloads.py:15:mode.  This is correct for pipeline-orchestration tests that don't intend to
modules\switch-connectivity\tests\integration\fixtures\valid_d0_payloads.py:169:    """Context manager that keeps stage 3 in its NotImplementedError passthrough mode.
scripts\audit_column_widths.py:3:Supersedes the regex-based v1 which missed any model that used
scripts\audit_column_widths.py:7:``dataiq`` models (33 uses).
scripts\audit_column_widths.py:9:v2 parses each model file with ``ast.parse()`` and resolves SQLAlchemy
scripts\audit_column_widths.py:17:  * Detects ``MODEL_NARROWER`` (model's ``String(N)`` < DB's VARCHAR)
scripts\audit_column_widths.py:18:  * Detects ``MODEL_WIDER`` (model's ``String(N)`` > DB's VARCHAR)
scripts\audit_column_widths.py:20:  * Reports ``UNPARSED`` for model columns the scanner can't resolve
scripts\audit_column_widths.py:39:parse, the model probably uses a pattern the scanner doesn't recognize.
scripts\audit_column_widths.py:81:        "DESIGN QUESTION: model 500, DB 255 — real DEA names can exceed 255",
scripts\audit_column_widths.py:87:# the model side.
scripts\audit_column_widths.py:129:# AST model scanner
scripts\audit_column_widths.py:274:def _scan_model_file(path: Path) -> list[_Decl]:
scripts\audit_column_widths.py:343:def model_columns() -> tuple[
scripts\audit_column_widths.py:365:            for decl in _scan_model_file(path):
scripts\audit_column_widths.py:386:    model_len: int | None
scripts\audit_column_widths.py:392:def _find_model_column(
scripts\audit_column_widths.py:406:    mdl, unparsed = model_columns()
scripts\audit_column_widths.py:411:        hit = _find_model_column(mdl, schema, table, col)
scripts\audit_column_widths.py:448:        mdl = f"String({f.model_len})" if f.model_len is not None else "—"
scripts\audit_column_widths.py:449:        loc = f"{f.file}:{f.line}" if f.file else "(not found in any model)"
scripts\audit_column_widths.py:453:            f"DB {db} vs model {mdl} at {loc}"
scripts\audit_column_widths.py:477:    no_model = sum(1 for f in findings if f.classification == "NO_MODEL")
scripts\audit_column_widths.py:480:          f"{no_model} NO_MODEL; {unparsed} UNPARSED")
modules\edi-compliance\tests\unit\test_baa_tracking.py:23:import src.models.edi_models  # noqa: F401 — register tables on Base.metadata
modules\edi-compliance\tests\unit\test_baa_tracking.py:24:from src.models.edi_models import TradingPartner
modules\edi-compliance\tests\unit\test_baa_tracking.py:142:        test_mode=False,
shared\data_ingestion\tests\test_orange_book.py:70:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_orange_book.py:83:from drug_database.models.ndc_tables import Drug, NDCBase, SCHEMA as NDC_SCHEMA  # type: ignore[import]
shared\data_ingestion\tests\test_orange_book.py:84:from drug_database.models.orange_book_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_orange_book.py:219:        join_transaction_mode="create_savepoint",
scripts\apply_rls.py:42:CLI modes
scripts\apply_rls.py:64:import argparse
scripts\apply_rls.py:475:    parser = argparse.ArgumentParser(description="Apply RLS policies based on table introspection.")
scripts\apply_rls.py:477:    mode = parser.add_mutually_exclusive_group()
scripts\apply_rls.py:478:    mode.add_argument("--status", action="store_true", help="Print current RLS state per table.")
scripts\apply_rls.py:479:    mode.add_argument("--dry-run", action="store_true", help="Print SQL that would apply (default).")
scripts\apply_rls.py:480:    mode.add_argument("--diff", action="store_true",
scripts\apply_rls.py:482:    mode.add_argument("--apply", action="store_true", help="Execute the SQL (requires --yes).")
shared\data_ingestion\tests\test_oig_leie.py:45:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_oig_leie.py:48:from shared.db.models.oig_leie_exclusions import OigLeieExclusion
shared\data_ingestion\tests\test_oig_leie.py:142:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_oig_leie.py:180:        """All 18 LEIE source fields must be captured in the ORM model."""
shared\data_ingestion\tests\test_oig_leie.py:189:        """Every expected LEIE column must exist on the ORM model."""
shared\data_ingestion\tests\test_oig_leie.py:190:        model_cols = {col.key for col in OigLeieExclusion.__table__.columns}
shared\data_ingestion\tests\test_oig_leie.py:197:        missing = expected - model_cols
shared\data_ingestion\tests\test_oig_leie.py:198:        assert not missing, f"ORM model missing columns: {missing}"
scripts\apply_rls [conflicted].py:42:CLI modes
scripts\apply_rls [conflicted].py:64:import argparse
scripts\apply_rls [conflicted].py:476:    parser = argparse.ArgumentParser(description="Apply RLS policies based on table introspection.")
scripts\apply_rls [conflicted].py:478:    mode = parser.add_mutually_exclusive_group()
scripts\apply_rls [conflicted].py:479:    mode.add_argument("--status", action="store_true", help="Print current RLS state per table.")
scripts\apply_rls [conflicted].py:480:    mode.add_argument("--dry-run", action="store_true", help="Print SQL that would apply (default).")
scripts\apply_rls [conflicted].py:481:    mode.add_argument("--diff", action="store_true",
scripts\apply_rls [conflicted].py:483:    mode.add_argument("--apply", action="store_true", help="Execute the SQL (requires --yes).")
modules\core-platform\src\notifications\service.py:29:from src.notifications.models import Notification, NotificationPreference
modules\core-platform\src\notifications\service.py:35:    injected without pulling in T2's user model."""
modules\core-platform\src\notifications\seed.py:11:from src.notifications.models import NotificationPreference
modules\core-platform\src\notifications\models.py:1:"""SQLAlchemy stand-in models for core.notifications + core.notification_preferences.
modules\core-platform\src\notifications\models.py:4:until Teammate 1 publishes the real models in ``shared.db.models.core``;
shared\data_ingestion\tests\test_nppes.py:73:    Parent packages (e.g. "prescriber_src", "prescriber_src.models") are
shared\data_ingestion\tests\test_nppes.py:92:            #   prescriber_src.models    → modules/prescriber-directory/src/models
shared\data_ingestion\tests\test_nppes.py:113:    _PRESCRIBER_SRC / "models" / "tables.py",
shared\data_ingestion\tests\test_nppes.py:114:    "prescriber_src.models.tables",
shared\data_ingestion\tests\test_nppes.py:117:    _PRESCRIBER_SRC / "models" / "nppes_tables.py",
shared\data_ingestion\tests\test_nppes.py:118:    "prescriber_src.models.nppes_tables",
shared\data_ingestion\tests\test_nppes.py:250:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_nppes.py:833:# ── Tests: Wave-11 NppesIngester modes ────────────────────────────────────
shared\data_ingestion\tests\test_nppes.py:836:def test_ingester_default_mode_is_weekly():
shared\data_ingestion\tests\test_nppes.py:840:    assert ing._mode == "weekly"
shared\data_ingestion\tests\test_nppes.py:844:def test_ingester_monthly_mode_uses_separate_source_name():
shared\data_ingestion\tests\test_nppes.py:847:    ing = NppesIngester(db_session=MagicMock(), mode="monthly")
shared\data_ingestion\tests\test_nppes.py:848:    assert ing._mode == "monthly"
shared\data_ingestion\tests\test_nppes.py:852:def test_ingester_deactivation_mode_uses_separate_source_name():
shared\data_ingestion\tests\test_nppes.py:855:    ing = NppesIngester(db_session=MagicMock(), mode="deactivation")
shared\data_ingestion\tests\test_nppes.py:856:    assert ing._mode == "deactivation"
shared\data_ingestion\tests\test_nppes.py:860:def test_ingester_rejects_unknown_mode():
shared\data_ingestion\tests\test_nppes.py:863:    with pytest.raises(ValueError, match="unknown NPPES mode"):
shared\data_ingestion\tests\test_nppes.py:864:        NppesIngester(db_session=MagicMock(), mode="yearly")  # type: ignore[arg-type]
shared\data_ingestion\tests\test_nppes.py:911:    ing = NppesIngester(db_session=MagicMock(), mode="deactivation")
shared\data_ingestion\tests\test_base.py:27:from shared.data_ingestion.models import IngestionRun
modules\core-platform\tests\bank_holidays\test_service.py:25:    from shared.db.models.bank_holidays import BankHoliday
modules\core-platform\tests\bank_holidays\test_service.py:43:    from shared.db.models.bank_holidays import BankHoliday
shared\data_ingestion\tests\test_api_routes.py:21:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_ncpdp_parser.py:69:from shared.data_ingestion.models import IngestionRun, IngestionSchedule  # noqa: E402
shared\data_ingestion\tests\test_ncpdp_parser.py:134:    _PHARM_SRC / "models" / "base.py", "pharmacy_src.models.base"
shared\data_ingestion\tests\test_ncpdp_parser.py:137:    _PHARM_SRC / "models" / "ncpdp_tables.py",
shared\data_ingestion\tests\test_ncpdp_parser.py:138:    "pharmacy_src.models.ncpdp_tables",
shared\data_ingestion\tests\test_ncpdp_parser.py:254:        join_transaction_mode="create_savepoint",
modules\edi-compliance\tests\integration\test_app_routes_extra.py:72:            "test_mode": True,
modules\core-platform\src\notifications\api.py:15:    model_config = ConfigDict(from_attributes=True)
modules\core-platform\src\notifications\api.py:29:    model_config = ConfigDict(from_attributes=True)
modules\core-platform\src\notifications\api.py:51:    @router.get("", response_model=list[NotificationRead])
modules\core-platform\src\notifications\api.py:89:        return NotificationRead.model_validate(row)
modules\core-platform\src\notifications\api.py:91:    @router.get("/preferences", response_model=list[PreferenceRead])
modules\core-platform\src\notifications\api.py:99:    @router.put("/preferences", response_model=PreferenceRead)
shared\data_ingestion\tests\test_medical_codes.py:54:from shared.data_ingestion.models import IngestionRun, IngestionSchedule  # noqa: E402
shared\data_ingestion\tests\test_medical_codes.py:71:from shared.db.models.hcpcs_codes import HcpcsCode  # noqa: E402
shared\data_ingestion\tests\test_medical_codes.py:72:from shared.db.models.icd10_cm_codes import Icd10CmCode  # noqa: E402
shared\data_ingestion\tests\test_medical_codes.py:177:        join_transaction_mode="create_savepoint",
modules\edi-compliance\tests\integration\test_app_integration.py:91:            "test_mode": True,
modules\billing\tests\integration\test_wired_routes.py:24:from src.models.tables import (
modules\billing\tests\integration\test_wired_routes.py:549:        funding_model="prefund",
modules\core-platform\tests\bank_holidays\test_api.py:24:from shared.db.models.bank_holidays import BankHoliday
modules\core-platform\src\models.py:1:"""Local ORM models for core-platform Session 4 tables.
modules\core-platform\src\models.py:4:When T1 ships canonical models in shared.db.models.core, swap the imports
shared\data_ingestion\tests\test_load_sam_script.py:50:# FakeConn / FakeCursor — model psycopg2 aborted-transaction semantics.
shared\data_ingestion\tests\test_load_sam_script.py:199:         patch.object(sys, "argv", ["load_sam", "--mode", "seed"]), \
shared\data_ingestion\tests\test_load_sam_script.py:221:         patch.object(sys, "argv", ["load_sam", "--mode", "seed"]), \
shared\data_ingestion\tests\test_load_sam_script.py:274:         patch.object(sys, "argv", ["load_sam", "--mode", "seed"]), \
modules\core-platform\tests\bank_holidays\conftest.py:26:    hook doesn't over-match ``shared/tests/db/test_bank_holidays_model.py``
modules\core-platform\src\main.py:99:        mode=os.getenv("LOG_MODE", "json"),
modules\core-platform\src\main.py:176:    mode (the shim uses SQLite in tests, Postgres in production).
shared\data_ingestion\tests\test_gov_exclusion.py:47:from shared.models.gov_exclusion_tables import GovernmentProgramBin
shared\data_ingestion\tests\test_gov_exclusion.py:121:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_fda_shortages.py:64:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_fda_shortages.py:73:from src.models.fda_supplementary_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_fda_shortages.py:187:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_fda_shortages.py:526:        from shared.data_ingestion.models import IngestionRun
shared\data_ingestion\tests\test_fda_shortages.py:595:            suffix=".json", mode="w", delete=False
modules\billing\tests\integration\test_consumer_persistence.py:25:from src.models.tables import APRecord, ARPayment, ARRecord, ClaimRecord, Invoice
shared\data_ingestion\tests\test_fda_shortages [conflicted].py:64:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_fda_shortages [conflicted].py:73:from drug_database.models.fda_supplementary_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_fda_shortages [conflicted].py:187:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_fda_shortages [conflicted].py:526:        from shared.data_ingestion.models import IngestionRun
shared\data_ingestion\tests\test_fda_shortages [conflicted].py:595:            suffix=".json", mode="w", delete=False
modules\switch-connectivity\tests\chaos\test_composed_failures.py:354:        Tests both inbound (stage 2) and outbound (stage 9) archive failure modes:
shared\data_ingestion\tests\test_fda_rems.py:67:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_fda_rems.py:76:from drug_database.models.fda_supplementary_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_fda_rems.py:190:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_fda_rems.py:371:        from shared.data_ingestion.models import IngestionRun
modules\switch-connectivity\tests\chaos\test_chaos_scenarios.py:5:  2. Audit chain contains the expected failure-mode event.
modules\billing\tests\integration\test_consumer_app_wired.py:31:from src.models.tables import APRecord, ClaimRecord
modules\billing\tests\integration\test_consumer_app_wired.py:50:    # Patch the `src.models.tables` metadata (used by conftest-imported
modules\billing\tests\integration\test_consumer_app_wired.py:51:    # symbols) AND the fully-qualified `modules.billing.src.models.tables`
modules\billing\tests\integration\test_consumer_app_wired.py:52:    # metadata (the one consumers import via relative `..models.tables`).
modules\billing\tests\integration\test_consumer_app_wired.py:55:    from src.models.tables import BillingBase as ShortBase
modules\billing\tests\integration\test_consumer_app_wired.py:56:    import modules.billing.src.models.tables as billing_models_full
modules\billing\tests\integration\test_consumer_app_wired.py:58:    for base in (ShortBase, billing_models_full.BillingBase):
modules\billing\tests\integration\test_consumer_app_wired.py:127:    import modules.billing.src.models.tables as t
shared\tests\observability\test_logging_config.py:113:    configure_logging(level="INFO", mode="json", stream=buf)
shared\tests\observability\test_logging_config.py:136:    configure_logging(level="INFO", mode="json", stream=buf)
shared\tests\observability\test_logging_config.py:144:def test_configure_text_mode_is_human_readable() -> None:
shared\tests\observability\test_logging_config.py:146:    configure_logging(level="DEBUG", mode="text", stream=buf)
shared\tests\observability\test_logging_config.py:154:    # Text mode is NOT JSON
shared\tests\observability\test_logging_config.py:161:    configure_logging(level="INFO", mode="json", stream=io.StringIO())
shared\tests\observability\test_logging_config.py:162:    configure_logging(level="WARNING", mode="text", stream=io.StringIO())
shared\tests\observability\test_logging_config.py:171:    configure_logging(level=logging.ERROR, mode="json", stream=buf)
shared\tests\observability\test_logging_config.py:182:    configure_logging(level="INFO", mode="json", stream=None)
shared\data_ingestion\tests\test_fda_purple_book.py:65:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_fda_purple_book.py:74:from src.models.fda_supplementary_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_fda_purple_book.py:185:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_fda_purple_book.py:456:        from shared.data_ingestion.models import IngestionRun
shared\data_ingestion\tests\test_fda_purple_book.py:577:            suffix=".csv", mode="w", delete=False, encoding="utf-8"
modules\edi-compliance\migrations\versions\0001_edi_baseline.py:36:        sa.Column("test_mode", sa.Boolean(), nullable=False, server_default="true"),
modules\edi-compliance\migrations\versions\0001_edi_baseline.py:161:        sa.Column("test_mode", sa.Boolean(), nullable=False, server_default="true"),
shared\data_ingestion\tests\test_fda_purple_book [conflicted].py:65:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_fda_purple_book [conflicted].py:74:from drug_database.models.fda_supplementary_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_fda_purple_book [conflicted].py:185:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_fda_purple_book [conflicted].py:456:        from shared.data_ingestion.models import IngestionRun
shared\data_ingestion\tests\test_fda_purple_book [conflicted].py:577:            suffix=".csv", mode="w", delete=False, encoding="utf-8"
modules\billing\src\utils\constants.py:60:# Funding models
modules\billing\tests\integration\test_api_routes.py:13:from src.models.tables import BillingBase
shared\data_ingestion\tests\test_fda_ndc_parser.py:56:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_fda_ndc_parser.py:68:# Import NDC models (drug-database is on sys.path so src.* resolves)
shared\data_ingestion\tests\test_fda_ndc_parser.py:69:from drug_database.models.ndc_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_fda_ndc_parser.py:195:        join_transaction_mode="create_savepoint",
modules\edi-compliance\tests\golden_master\test_golden_master.py:45:        test_mode=True,
modules\edi-compliance\tests\golden_master\test_golden_master.py:89:        test_mode=True,
modules\core-platform\src\jobs\scheduler.py:24:from ..models import Job, JobRun
modules\switch-connectivity\tests\chaos\fault_injection.py:3:Compose these into scenarios to exercise pipeline failure modes.
shared\data_ingestion\tests\test_dea.py:49:# pin it into sys.modules under the canonical `src.models.compliance_tables`
shared\data_ingestion\tests\test_dea.py:54:# ``src.models`` does NOT have a ``compliance_tables`` submodule, so a
shared\data_ingestion\tests\test_dea.py:55:# later ``from src.models.compliance_tables import ...`` inside the DEA
shared\data_ingestion\tests\test_dea.py:61:# ``from src.models.compliance_tables import DeaRegistration``
shared\data_ingestion\tests\test_dea.py:62:# (``src``, ``src.models``, ``src.models.compliance_tables``). Subsequent
shared\data_ingestion\tests\test_dea.py:72:    """Preload prescriber-directory's src.models into sys.modules.
shared\data_ingestion\tests\test_dea.py:74:    Preloads both ``src.models.tables`` (which exports ``PrescriberBase``
shared\data_ingestion\tests\test_dea.py:76:    ``src.models.compliance_tables`` (which exports ``DeaRegistration``).
shared\data_ingestion\tests\test_dea.py:77:    Extends ``src.models.__path__`` to include prescriber-directory's
shared\data_ingestion\tests\test_dea.py:78:    src/models/ so any not-yet-loaded sibling module resolves there too.
shared\data_ingestion\tests\test_dea.py:82:    ``src.models`` under sys.modules — we extend __path__ rather than
shared\data_ingestion\tests\test_dea.py:85:    prescriber_models_dir = str(_PRESCRIBER_DIR_SRC / "src" / "models")
shared\data_ingestion\tests\test_dea.py:88:    # 1. Ensure src and src.models packages exist, with prescriber-directory
shared\data_ingestion\tests\test_dea.py:100:    if "src.models" not in sys.modules:
shared\data_ingestion\tests\test_dea.py:101:        models_pkg = _types.ModuleType("src.models")
shared\data_ingestion\tests\test_dea.py:102:        models_pkg.__path__ = [prescriber_models_dir]  # type: ignore[attr-defined]
shared\data_ingestion\tests\test_dea.py:103:        sys.modules["src.models"] = models_pkg
shared\data_ingestion\tests\test_dea.py:105:        existing_models = sys.modules["src.models"]
shared\data_ingestion\tests\test_dea.py:106:        paths = getattr(existing_models, "__path__", None)
shared\data_ingestion\tests\test_dea.py:107:        if paths is not None and prescriber_models_dir not in paths:
shared\data_ingestion\tests\test_dea.py:108:            paths.append(prescriber_models_dir)
shared\data_ingestion\tests\test_dea.py:113:    #    this if the existing sys.modules["src.models.tables"] (if any)
shared\data_ingestion\tests\test_dea.py:115:    for mod_name in ("src.models.tables", "src.models.compliance_tables"):
shared\data_ingestion\tests\test_dea.py:125:        file_path = _PRESCRIBER_DIR_SRC / "src" / "models" / filename
shared\data_ingestion\tests\test_dea.py:137:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_dea.py:144:from src.models.compliance_tables import DeaRegistration  # type: ignore[import]
shared\data_ingestion\tests\test_dea.py:221:    from src.models.tables import PrescriberBase  # type: ignore[import]
shared\data_ingestion\tests\test_dea.py:244:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_dea.py:384:        # sys.modules["src.models.compliance_tables"] registration at
shared\data_ingestion\tests\test_dea.py:387:        model_cols = {col.key for col in DeaRegistration.__table__.columns}
shared\data_ingestion\tests\test_dea.py:393:        missing = expected - model_cols
shared\data_ingestion\tests\test_dea.py:394:        assert not missing, f"DEA ORM model missing columns: {missing}"
shared\data_ingestion\tests\test_dea.py:398:    """Tests that exercise _upsert_row() with the real DeaRegistration model."""
shared\data_ingestion\tests\test_dea.py:400:    async def test_load_inserts_and_updates_real_model(
shared\data_ingestion\tests\test_dea.py:403:        """load() inserts rows via _upsert_row when model is importable."""
shared\data_ingestion\tests\test_dea.py:460:    by mocking the DeaRegistration model import so we don't need the prescriber
shared\data_ingestion\tests\test_dea.py:471:        mock_model_instance = MagicMock()
shared\data_ingestion\tests\test_dea.py:675:        """Lines 186-192: if 'from src.models...' fails, sys.path is adjusted and retried."""
shared\data_ingestion\tests\test_dea.py:689:            if name == "src.models.compliance_tables" and not import_calls.count(name) > 1:
shared\data_ingestion\tests\test_dea.py:697:        original_import("src.models.compliance_tables")
modules\edi-compliance\tests\golden_master\generate_masters.py:43:        test_mode=True,
modules\edi-compliance\tests\golden_master\generate_masters.py:95:        test_mode=True,
modules\switch-connectivity\tests\chaos\conftest.py:8:auto mode without deprecation warnings from ``get_event_loop()``.
modules\edi-compliance\tests\conftest.py:68:# Import models to register on Base.metadata
modules\edi-compliance\tests\conftest.py:69:import src.models.edi_models  # noqa: F401
modules\edi-compliance\tests\conftest.py:108:    session = Session(bind=connection, join_transaction_mode="create_savepoint")
shared\data_ingestion\tests\test_dea [conflicted].py:49:# pin it into sys.modules under the canonical `src.models.compliance_tables`
shared\data_ingestion\tests\test_dea [conflicted].py:54:# ``src.models`` does NOT have a ``compliance_tables`` submodule, so a
shared\data_ingestion\tests\test_dea [conflicted].py:55:# later ``from src.models.compliance_tables import ...`` inside the DEA
shared\data_ingestion\tests\test_dea [conflicted].py:61:# ``from src.models.compliance_tables import DeaRegistration``
shared\data_ingestion\tests\test_dea [conflicted].py:62:# (``src``, ``src.models``, ``src.models.compliance_tables``). Subsequent
shared\data_ingestion\tests\test_dea [conflicted].py:72:    """Preload prescriber-directory's src.models into sys.modules.
shared\data_ingestion\tests\test_dea [conflicted].py:74:    Preloads both ``src.models.tables`` (which exports ``PrescriberBase``
shared\data_ingestion\tests\test_dea [conflicted].py:76:    ``src.models.compliance_tables`` (which exports ``DeaRegistration``).
shared\data_ingestion\tests\test_dea [conflicted].py:77:    Extends ``src.models.__path__`` to include prescriber-directory's
shared\data_ingestion\tests\test_dea [conflicted].py:78:    src/models/ so any not-yet-loaded sibling module resolves there too.
shared\data_ingestion\tests\test_dea [conflicted].py:82:    ``src.models`` under sys.modules — we extend __path__ rather than
shared\data_ingestion\tests\test_dea [conflicted].py:85:    prescriber_models_dir = str(_PRESCRIBER_DIR_SRC / "src" / "models")
shared\data_ingestion\tests\test_dea [conflicted].py:88:    # 1. Ensure src and src.models packages exist, with prescriber-directory
shared\data_ingestion\tests\test_dea [conflicted].py:100:    if "src.models" not in sys.modules:
shared\data_ingestion\tests\test_dea [conflicted].py:101:        models_pkg = _types.ModuleType("src.models")
shared\data_ingestion\tests\test_dea [conflicted].py:102:        models_pkg.__path__ = [prescriber_models_dir]  # type: ignore[attr-defined]
shared\data_ingestion\tests\test_dea [conflicted].py:103:        sys.modules["src.models"] = models_pkg
shared\data_ingestion\tests\test_dea [conflicted].py:105:        existing_models = sys.modules["src.models"]
shared\data_ingestion\tests\test_dea [conflicted].py:106:        paths = getattr(existing_models, "__path__", None)
shared\data_ingestion\tests\test_dea [conflicted].py:107:        if paths is not None and prescriber_models_dir not in paths:
shared\data_ingestion\tests\test_dea [conflicted].py:108:            paths.append(prescriber_models_dir)
shared\data_ingestion\tests\test_dea [conflicted].py:113:    #    this if the existing sys.modules["src.models.tables"] (if any)
shared\data_ingestion\tests\test_dea [conflicted].py:115:    for mod_name in ("src.models.tables", "src.models.compliance_tables"):
shared\data_ingestion\tests\test_dea [conflicted].py:125:        file_path = _PRESCRIBER_DIR_SRC / "src" / "models" / filename
shared\data_ingestion\tests\test_dea [conflicted].py:137:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_dea [conflicted].py:144:from src.models.compliance_tables import DeaRegistration  # type: ignore[import]
shared\data_ingestion\tests\test_dea [conflicted].py:221:    from src.models.tables import PrescriberBase  # type: ignore[import]
shared\data_ingestion\tests\test_dea [conflicted].py:244:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_dea [conflicted].py:384:        # sys.modules["src.models.compliance_tables"] registration at
shared\data_ingestion\tests\test_dea [conflicted].py:387:        model_cols = {col.key for col in DeaRegistration.__table__.columns}
shared\data_ingestion\tests\test_dea [conflicted].py:393:        missing = expected - model_cols
shared\data_ingestion\tests\test_dea [conflicted].py:394:        assert not missing, f"DEA ORM model missing columns: {missing}"
shared\data_ingestion\tests\test_dea [conflicted].py:398:    """Tests that exercise _upsert_row() with the real DeaRegistration model."""
shared\data_ingestion\tests\test_dea [conflicted].py:400:    async def test_load_inserts_and_updates_real_model(
shared\data_ingestion\tests\test_dea [conflicted].py:403:        """load() inserts rows via _upsert_row when model is importable."""
shared\data_ingestion\tests\test_dea [conflicted].py:460:    by mocking the DeaRegistration model import so we don't need the prescriber
shared\data_ingestion\tests\test_dea [conflicted].py:471:        mock_model_instance = MagicMock()
shared\data_ingestion\tests\test_dea [conflicted].py:675:        """Lines 186-192: if 'from src.models...' fails, sys.path is adjusted and retried."""
shared\data_ingestion\tests\test_dea [conflicted].py:689:            if name == "src.models.compliance_tables" and not import_calls.count(name) > 1:
shared\data_ingestion\tests\test_dea [conflicted].py:697:        original_import("src.models.compliance_tables")
shared\data_ingestion\tests\test_cms_opt_out.py:54:# Preload prescriber-directory's src.models submodules into sys.modules
shared\data_ingestion\tests\test_cms_opt_out.py:55:# under their canonical ``src.models.*`` names. Required because
shared\data_ingestion\tests\test_cms_opt_out.py:58:# to re-search sys.path when we say ``from src.models.tables import
shared\data_ingestion\tests\test_cms_opt_out.py:69:    prescriber_models_dir = str(_PRESCRIBER_ROOT / "src" / "models")
shared\data_ingestion\tests\test_cms_opt_out.py:81:    if "src.models" not in sys.modules:
shared\data_ingestion\tests\test_cms_opt_out.py:82:        models_pkg = _types.ModuleType("src.models")
shared\data_ingestion\tests\test_cms_opt_out.py:83:        models_pkg.__path__ = [prescriber_models_dir]  # type: ignore[attr-defined]
shared\data_ingestion\tests\test_cms_opt_out.py:84:        sys.modules["src.models"] = models_pkg
shared\data_ingestion\tests\test_cms_opt_out.py:86:        paths = getattr(sys.modules["src.models"], "__path__", None)
shared\data_ingestion\tests\test_cms_opt_out.py:87:        if paths is not None and prescriber_models_dir not in paths:
shared\data_ingestion\tests\test_cms_opt_out.py:88:            paths.append(prescriber_models_dir)
shared\data_ingestion\tests\test_cms_opt_out.py:90:    for mod_name in ("src.models.tables", "src.models.medicare_tables"):
shared\data_ingestion\tests\test_cms_opt_out.py:98:        file_path = _PRESCRIBER_ROOT / "src" / "models" / filename
shared\data_ingestion\tests\test_cms_opt_out.py:110:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_cms_opt_out.py:119:from src.models.medicare_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_cms_opt_out.py:124:from src.models.tables import Prescriber  # type: ignore[import]
shared\data_ingestion\tests\test_cms_opt_out.py:234:        join_transaction_mode="create_savepoint",
modules\billing\tests\conftest.py:19:from src.models.tables import BillingBase
modules\core-platform\src\jobs\api.py:15:from ..models import Job, JobRun
modules\core-platform\src\jobs\api.py:39:    model_config = ConfigDict(from_attributes=True)
modules\core-platform\src\jobs\api.py:52:    model_config = ConfigDict(from_attributes=True)
modules\core-platform\src\jobs\api.py:77:@router.get("", response_model=List[JobOut], dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
modules\core-platform\src\jobs\api.py:81:    return [JobOut.model_validate(r) for r in rows]
modules\core-platform\src\jobs\api.py:84:@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
modules\core-platform\src\jobs\api.py:104:    return JobOut.model_validate(job)
modules\core-platform\src\jobs\api.py:117:@router.put("/{job_id}", response_model=JobOut, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
modules\core-platform\src\jobs\api.py:135:    return JobOut.model_validate(job)
modules\core-platform\src\jobs\api.py:138:@router.post("/{job_id}/pause", response_model=JobOut, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
modules\core-platform\src\jobs\api.py:144:    return JobOut.model_validate(job)
modules\core-platform\src\jobs\api.py:147:@router.post("/{job_id}/run", response_model=JobRunOut, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
modules\core-platform\src\jobs\api.py:167:        return JobRunOut.model_validate(run)
modules\core-platform\src\jobs\api.py:192:    return JobRunOut.model_validate(run)
modules\core-platform\src\jobs\api.py:195:@router.get("/{job_id}/runs", response_model=List[JobRunOut], dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
modules\core-platform\src\jobs\api.py:201:    return [JobRunOut.model_validate(r) for r in rows]
modules\core-platform\src\jobs\api.py:204:@router.get("/runs/{run_id}", response_model=JobRunOut, dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
modules\core-platform\src\jobs\api.py:210:    return JobRunOut.model_validate(run)
shared\tests\fdb\test_client.py:179:def test_factory_stub_mode_returns_stub(monkeypatch):
shared\tests\fdb\test_client.py:186:def test_factory_real_mode_returns_not_implemented(monkeypatch):
shared\tests\fdb\test_client.py:187:    """Until a real adapter lands, 'real' mode returns the fail-loud
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:54:# Preload prescriber-directory's src.models submodules into sys.modules
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:55:# under their canonical ``src.models.*`` names. Required because
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:58:# to re-search sys.path when we say ``from src.models.tables import
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:69:    prescriber_models_dir = str(_PRESCRIBER_ROOT / "src" / "models")
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:81:    if "src.models" not in sys.modules:
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:82:        models_pkg = _types.ModuleType("src.models")
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:83:        models_pkg.__path__ = [prescriber_models_dir]  # type: ignore[attr-defined]
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:84:        sys.modules["src.models"] = models_pkg
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:86:        paths = getattr(sys.modules["src.models"], "__path__", None)
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:87:        if paths is not None and prescriber_models_dir not in paths:
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:88:            paths.append(prescriber_models_dir)
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:90:    for mod_name in ("src.models.tables", "src.models.medicare_tables"):
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:98:        file_path = _PRESCRIBER_ROOT / "src" / "models" / filename
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:110:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:119:from src.models.medicare_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:124:from src.models.tables import Prescriber  # type: ignore[import]
shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:234:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_cms_nadac.py:60:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_cms_nadac.py:70:from drug_database.models.pricing_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_cms_nadac.py:186:        join_transaction_mode="create_savepoint",
shared\data_ingestion\tests\test_cms_asp.py:54:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\test_cms_asp.py:64:from drug_database.models.pricing_tables import (  # type: ignore[import]
shared\data_ingestion\tests\test_cms_asp.py:180:        join_transaction_mode="create_savepoint",
modules\core-platform\src\bank_holidays\service.py:27:from shared.db.models.bank_holidays import BankHoliday
modules\core-platform\src\bank_holidays\seed.py:39:import argparse
modules\core-platform\src\bank_holidays\seed.py:46:# Pure-Python model stub for use in contexts where the real ORM model cannot
modules\core-platform\src\bank_holidays\seed.py:48:# actual ORM model when available; otherwise we fall back to this dataclass.
modules\core-platform\src\bank_holidays\seed.py:60:    Imports the real ORM model from shared; never instantiates a stub.
modules\core-platform\src\bank_holidays\seed.py:62:    from shared.db.models.bank_holidays import BankHoliday
modules\core-platform\src\bank_holidays\seed.py:231:    parser = argparse.ArgumentParser(
modules\core-platform\src\bank_holidays\schemas.py:14:    model_config = ConfigDict(from_attributes=True)
modules\core-platform\src\bank_holidays\schemas.py:53:    model_config = ConfigDict(populate_by_name=True)
modules\core-platform\src\bank_holidays\api.py:66:@router.get("", response_model=List[HolidayRead])
modules\core-platform\src\bank_holidays\api.py:78:    return [HolidayRead.model_validate(r) for r in rows]
modules\core-platform\src\bank_holidays\api.py:81:@router.post("", response_model=HolidayRead, status_code=201)
modules\core-platform\src\bank_holidays\api.py:110:    return HolidayRead.model_validate(h)
modules\core-platform\src\bank_holidays\api.py:113:@router.get("/is-business-day/{iso_date}", response_model=BusinessDayResponse)
modules\core-platform\src\bank_holidays\api.py:149:@router.get("/next-business-day/{iso_date}", response_model=NextBusinessDayResponse)
modules\reclaimrx\tests\wave42\integration\test_hierarchy_resolver.py:10:  * cross-tenant isolation (admin-bypass mode used here for seeding;
modules\ebv-ebi-rtbc\tests\conftest.py:30:from src.models.tables import EbvEbiBase
modules\ebv-ebi-rtbc\tests\conftest.py:92:        join_transaction_mode="create_savepoint",
modules\billing\src\models\tables.py:1:"""SQLAlchemy models for the billing module.
modules\billing\src\models\tables.py:669:    funding_model: Mapped[str] = mapped_column(String(50), nullable=False)
shared\tests\events\test_rabbitmq_bus_dlq.py:47:    from shared.db.models.events import EventDLQEntry
shared\tests\events\test_rabbitmq_bus_dlq.py:68:    from shared.db.models.events import EventDLQEntry
shared\program_config_queries\pharmacy.py:242:    not a silent generator failure mode.
modules\core-platform\src\government_programs\api.py:32:from shared.models.gov_exclusion_tables import VALID_CONFIDENCE_LEVELS, VALID_PLAN_TYPES, GovernmentProgramBin
modules\core-platform\src\government_programs\api.py:54:    model_config = ConfigDict(from_attributes=False)
modules\core-platform\src\government_programs\api.py:71:    model_config = ConfigDict(from_attributes=False)
modules\core-platform\src\government_programs\api.py:80:    model_config = ConfigDict(from_attributes=False)
modules\core-platform\src\government_programs\api.py:89:    model_config = ConfigDict(from_attributes=True)
modules\core-platform\src\government_programs\api.py:245:@router.get("/check", response_model=GovernmentCheckOut)
modules\core-platform\src\government_programs\api.py:259:@router.get("/copay-eligibility", response_model=CopayEligibilityOut)
modules\core-platform\src\government_programs\api.py:273:@router.get("/bins", response_model=list[GovernmentBinOut])
modules\core-platform\src\government_programs\api.py:291:    return [GovernmentBinOut.model_validate(r) for r in rows]
modules\core-platform\src\government_programs\api.py:294:@router.get("/bins/{bin_id}", response_model=GovernmentBinOut)
modules\core-platform\src\government_programs\api.py:305:    return GovernmentBinOut.model_validate(row)
modules\core-platform\src\government_programs\api.py:308:@router.get("/coverage-report", response_model=CoverageReport)
modules\core-platform\src\government_programs\api.py:340:@router.post("/bins", response_model=GovernmentBinOut, status_code=status.HTTP_201_CREATED)
modules\core-platform\src\government_programs\api.py:363:        **body.model_dump(),
modules\core-platform\src\government_programs\api.py:369:    return GovernmentBinOut.model_validate(entry)
modules\core-platform\src\government_programs\api.py:372:@router.put("/bins/{bin_id}", response_model=GovernmentBinOut)
modules\core-platform\src\government_programs\api.py:387:    for field_name, value in body.model_dump(exclude_none=True).items():
modules\core-platform\src\government_programs\api.py:392:    return GovernmentBinOut.model_validate(row)
modules\core-platform\src\government_programs\api.py:413:@router.post("/import", response_model=ImportResult)
modules\core-platform\src\auth\__init__.py:6:loader + revoked-token repo) using this module's ORM models.
shared\program_config_queries\claim_history.py:11:modules/adjudication-engine/src/models/tables.py would fail for
modules\core-platform\src\auth\_models.py:1:"""Stand-in SQLAlchemy models for core.users/roles/permissions.
modules\core-platform\src\auth\_models.py:5:These models exist only because Teammate 1 (infrastructure/database) is
modules\core-platform\src\auth\_models.py:6:working in parallel and has not yet landed ``shared.db.models.core``.
modules\core-platform\src\auth\_models.py:8:import site updated to use the shared models instead. The column set,
modules\core-platform\src\auth\_models.py:12:Schema: the real models live in the ``core`` Postgres schema. For the
modules\core-platform\src\auth\_models.py:99:    # shared models. The shim's String column is acceptable only for
shared\data_ingestion\tests\conftest.py:13:Python-level UUIDs are supplied in the ORM models via ``__init__`` overrides in
shared\data_ingestion\tests\conftest.py:41:# Import models so their metadata is populated before the engine fixture runs.
shared\data_ingestion\tests\conftest.py:42:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\tests\conftest.py:147:        join_transaction_mode="create_savepoint",
modules\ebv-ebi-rtbc\src\services\member_tools.py:55:DrugCostEstimate.model_rebuild()
shared\tests\events\test_dlq_service.py:10:from shared.db.models.events import EventDLQEntry
shared\tests\events\test_dlq_service.py:434:    from shared.db.models.events import EventDLQEntry
modules\core-platform\src\auth\wiring.py:1:"""Wire the shared auth dependencies to the core-platform ORM models.
modules\billing\src\events\consumers.py:9:  ``db=None`` the handler is in a dry-run mode that only logs — this exists so
modules\billing\src\events\consumers.py:33:from ..models.tables import APRecord, ARPayment, ARRecord, ClaimRecord
modules\ebv-ebi-rtbc\src\services\benefit_investigation.py:113:CoverageRequirements.model_rebuild()
shared\tests\events\test_dlq_repository.py:20:from shared.db.models.events import EventDLQEntry
modules\core-platform\src\files\service.py:15:from ..models import File
shared\observability\logging_config.py:6:output, so ``configure_logging(mode="text")`` keeps the default
shared\observability\logging_config.py:118:    *, level: str | int = "INFO", mode: str = "json", stream: Any = None
shared\observability\logging_config.py:124:        mode: "json" (production) or "text" (dev/tests).
shared\observability\logging_config.py:141:    if mode == "text":
shared\tests\events\test_dlq_models.py:1:"""Tests for EventDLQEntry and ProcessedEvent ORM models and migration.
shared\tests\events\test_dlq_models.py:18:from shared.db.models.events import EventDLQEntry, ProcessedEvent
shared\tests\events\test_dlq_models.py:47:    from shared.db.models import events as _events_module  # noqa: F401 — register models
modules\core-platform\src\files\api.py:36:    model_config = ConfigDict(from_attributes=True)
modules\core-platform\src\files\api.py:49:@router.post("/upload", response_model=FileOut, status_code=201, dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
modules\core-platform\src\files\api.py:90:@router.get("", response_model=List[FileOut], dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
modules\core-platform\src\files\api.py:100:    return [FileOut.model_validate(r) for r in rows]
shared\tests\events\test_cross_module_events.py:29:# ``from src.models.tables import ...`` (bare ``src`` package
modules\billing\src\db\session.py:4:sync ``Session`` class so that any model inheriting
modules\billing\src\db\session.py:6:contextvar. Billing's own models do not yet inherit the mixin — tracked
modules\billing\src\db\session.py:8:participates in platform-wide isolation the moment those models are
modules\core-platform\src\auth\sessions\service.py:17:from src.auth.sessions.models import Session_ as SessionRow
shared\models\gov_exclusion_tables.py:1:"""ORM model for government program BIN/PCN reference table.
modules\ebv-ebi-rtbc\src\models\tables.py:1:"""SQLAlchemy ORM models for the ebv_ebi schema.
shared\tests\events\conftest.py:28:    event-bus model tests exist to verify migration DDL, JSONB column
modules\core-platform\src\auth\sessions\models.py:1:"""Local session model for core.sessions (SQLite-compatible shim).
modules\core-platform\src\auth\sessions\models.py:3:Mirrors shared.db.models.sessions.UserSession but uses the module-local
modules\core-platform\src\auth\sessions\models.py:6:INTEGRATION NOTE: replace with shared.db.models.sessions.UserSession
modules\core-platform\src\auth\sessions\models.py:19:from src.auth._models import GUID, Base
modules\core-platform\src\auth\service.py:19:from src.auth._models import Permission, Role, User, UserRole
modules\core-platform\src\auth\service.py:115:    enumeration. The underlying failure mode is captured in the audit
modules\core-platform\src\auth\service.py:122:        from src.auth._models import Tenant
modules\reclaimrx\tests\unit\test_rule_engine.py:56:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:74:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:94:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:113:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:136:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:158:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:177:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:198:            detection_mode="post_adjudication",
modules\reclaimrx\tests\unit\test_rule_engine.py:215:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:232:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:253:            detection_mode="post_adjudication",
modules\reclaimrx\tests\unit\test_rule_engine.py:270:            detection_mode="post_adjudication",
modules\reclaimrx\tests\unit\test_rule_engine.py:302:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:320:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:339:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:359:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:377:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:395:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:412:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:429:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:448:            detection_mode="both",
modules\reclaimrx\tests\unit\test_rule_engine.py:477:            detection_mode="both",
modules\ebv-ebi-rtbc\src\api\schemas.py:3:All money fields as Decimal. Pydantic v2 models.
modules\core-platform\src\auth\seed\system_roles.py:23:from src.auth._models import Permission, Role, RolePermission
modules\core-platform\src\auth\seed\system_roles.py:261:    from src.auth._models import Base
modules\reclaimrx\tests\unit\test_ml_scoring.py:101:        # Not guaranteed, but trained model should reflect this
modules\reclaimrx\tests\unit\test_ml_scoring.py:105:    def test_model_uses_no_floats_for_money(self) -> None:
modules\reclaimrx\tests\unit\test_ml_scoring.py:137:    def test_fit_retrains_model(self) -> None:
modules\core-platform\src\auth\schemas.py:59:    model_config = ConfigDict(from_attributes=True)
modules\core-platform\src\auth\schemas.py:68:    # Present on the ORM model but omitted from the prior response shape.
modules\core-platform\src\auth\schemas.py:96:    model_config = ConfigDict(from_attributes=True)
modules\core-platform\src\auth\schemas.py:107:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\tests\unit\test_m04_pricing_refactor.py:109:        detection_mode="both",
modules\reclaimrx\tests\unit\test_letter_service.py:8:from src.models.tables import LetterTemplate
modules\reclaimrx\tests\unit\test_letter_service.py:135:        from src.models.tables import LetterTemplate as LT
shared\data_ingestion\sources\state_medicaid_bins.py:40:from shared.models.gov_exclusion_tables import (
modules\reclaimrx\tests\unit\test_investigation_service_extended.py:9:from src.models.tables import Investigation
shared\jobs\weekly_restore_evidence.py:23:import argparse
shared\jobs\weekly_restore_evidence.py:109:    parser = argparse.ArgumentParser(description="Weekly restore evidence runner (H-09)")
modules\ebv-ebi-rtbc\src\api\routes\rtpb.py:35:@router.post("/rtpb/check", response_model=RTPBResponse)
shared\data_ingestion\sources\sam_exclusions.py:533:        from shared.db.models.sam_exclusions import SamExclusion
modules\ebv-ebi-rtbc\src\api\routes\member_tools.py:60:@router.post("/member/cost-estimate", response_model=CostEstimateResponse)
modules\ebv-ebi-rtbc\src\api\routes\member_tools.py:87:@router.post("/member/pharmacy-compare", response_model=PharmacyCompareResponse)
modules\ebv-ebi-rtbc\src\api\routes\member_tools.py:114:@router.get("/member/{member_id}/progress", response_model=BenefitProgressResponse)
modules\ebv-ebi-rtbc\src\api\routes\member_tools.py:155:@router.get("/member/{member_id}/id-card", response_model=DigitalIDCardResponse)
shared\data_ingestion\sources\rxnorm.py:439:        from drug_database.models.rxnorm_tables import (  # type: ignore[import]
modules\ebv-ebi-rtbc\src\api\routes\hub.py:50:@router.post("/hub/bv", response_model=HubResponse)
modules\ebv-ebi-rtbc\src\api\routes\hub.py:85:@router.post("/hub/bi", response_model=HubResponse)
modules\ebv-ebi-rtbc\src\api\routes\hub.py:124:@router.post("/hub/status-update", response_model=HubResponse)
modules\billing\src\api\schemas\config.py:106:    funding_model: str
shared\data_ingestion\sources\oig_leie.py:217:        from shared.db.models.oig_leie_exclusions import OigLeieExclusion
modules\ebv-ebi-rtbc\src\api\routes\eligibility.py:41:@router.post("/eligibility/verify", response_model=EligibilityResponse)
modules\ebv-ebi-rtbc\src\api\routes\eligibility.py:56:@router.post("/eligibility/batch", response_model=list[EligibilityResponse])
shared\data_ingestion\sources\ofac_sdn.py:31:Upsert model:
shared\data_ingestion\sources\ofac_sdn.py:303:        from shared.db.models.ofac_sdn import (
modules\ebv-ebi-rtbc\src\api\routes\benefit.py:39:@router.post("/benefit/investigate", response_model=BenefitInvestigateResponse)
shared\data_ingestion\sources\nppes.py:219:    ``mode`` controls which CMS file we target and which load path runs:
shared\data_ingestion\sources\nppes.py:228:    ``source_name`` is derived from ``mode`` so each mode has its own
shared\data_ingestion\sources\nppes.py:233:    source_name = "nppes"  # default; overridden per-mode below
shared\data_ingestion\sources\nppes.py:239:        mode: Mode = "weekly",
shared\data_ingestion\sources\nppes.py:243:        if mode not in _MODE_CONFIG:
shared\data_ingestion\sources\nppes.py:244:            raise ValueError(f"unknown NPPES mode: {mode!r} (expected weekly/monthly/deactivation)")
shared\data_ingestion\sources\nppes.py:245:        self._mode: Mode = mode
shared\data_ingestion\sources\nppes.py:246:        self._config = _MODE_CONFIG[mode]
shared\data_ingestion\sources\nppes.py:247:        # Override class-level source_name with the mode-specific one so
shared\data_ingestion\sources\nppes.py:265:                "ingest_mode": self._mode,
shared\data_ingestion\sources\nppes.py:273:            timeout_seconds=600.0 if self._mode != "monthly" else 3600.0,
shared\data_ingestion\sources\nppes.py:289:                f"Could not locate {self._mode} NPPES file on {_CMS_INDEX_URL}. "
shared\data_ingestion\sources\nppes.py:322:        if self._mode == "deactivation":
shared\data_ingestion\sources\nppes.py:346:        import openpyxl  # lazy import — only pulled in for deactivation mode
shared\data_ingestion\sources\nppes.py:382:        if self._mode == "deactivation":
shared\data_ingestion\sources\nppes.py:398:            mode="w",
shared\data_ingestion\sources\nppes.py:422:                    "ingest_mode": self._mode,
shared\data_ingestion\sources\nppes.py:440:                        refresh_type=self._mode,
modules\reclaimrx\tests\unit\test_detection_rule_seeder.py:5:from src.models.tables import DetectionProfile, DetectionRule
modules\edi-compliance\src\x12\generators\schemas.py:22:    test_mode: bool = True
modules\edi-compliance\src\x12\generators\schemas.py:48:    test_mode: bool = True
modules\edi-compliance\src\x12\generators\schemas.py:73:    test_mode: bool = True
modules\edi-compliance\src\x12\generators\schemas.py:108:    test_mode: bool = True
modules\edi-compliance\src\x12\generators\schemas.py:135:    test_mode: bool = True
modules\edi-compliance\src\x12\generators\schemas.py:156:    test_mode: bool = True
modules\edi-compliance\src\x12\generators\schemas.py:175:    test_mode: bool = True
modules\edi-compliance\src\x12\generators\schemas.py:201:    test_mode: bool = True
modules\edi-compliance\src\x12\generators\schemas.py:222:    test_mode: bool = True
shared\auth\mfa\backup_codes.py:76:    """Load the list of stored hashes from the user model."""
shared\auth\mfa\backup_codes.py:84:    """Persist updated hash list to the user model."""
shared\fdb\client.py:229:        mode = os.environ.get("IFX_FDB_CLIENT", "stub").lower()
shared\fdb\client.py:230:        if mode == "real":
modules\billing\src\api\router.py:53:from src.models.tables import (
modules\billing\src\api\router.py:93:@router.post("/claims", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:108:@router.get("/claims", response_model=list[dict])
modules\billing\src\api\router.py:175:@router.get("/claims/{claim_id}", response_model=dict)
modules\billing\src\api\router.py:236:@router.get("/routing-rules", response_model=list[dict])
modules\billing\src\api\router.py:280:@router.post("/routing-rules", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:287:    return {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), **body.model_dump()}
modules\billing\src\api\router.py:290:@router.put("/routing-rules/{rule_id}", response_model=dict)
modules\billing\src\api\router.py:301:@router.post("/routing-rules/test", response_model=RoutingTestResponse)
modules\billing\src\api\router.py:316:@router.get("/ap", response_model=list[dict])
modules\billing\src\api\router.py:375:@router.get("/ap/summary", response_model=list[dict])
modules\billing\src\api\router.py:429:@router.get("/ap/{ap_id}", response_model=dict)
modules\billing\src\api\router.py:485:@router.get("/payment-batches", response_model=list[dict])
modules\billing\src\api\router.py:533:@router.post("/payment-batches/generate", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:543:@router.get("/payment-batches/{batch_id}", response_model=dict)
modules\billing\src\api\router.py:592:@router.post("/payment-batches/{batch_id}/validate", response_model=BatchValidateResponse)
modules\billing\src\api\router.py:602:@router.post("/payment-batches/{batch_id}/approve", response_model=dict)
modules\billing\src\api\router.py:612:@router.post("/payment-batches/{batch_id}/submit", response_model=dict)
modules\billing\src\api\router.py:622:@router.post("/payment-batches/{batch_id}/void", response_model=dict)
modules\billing\src\api\router.py:632:@router.get("/payment-batches/{batch_id}/payments", response_model=list[dict])
modules\billing\src\api\router.py:686:@router.post("/settlement/record", status_code=status.HTTP_200_OK, response_model=dict)
modules\billing\src\api\router.py:696:@router.get("/settlement/unmatched", response_model=list[dict])
modules\billing\src\api\router.py:744:@router.get("/invoicing-configs", response_model=list[dict])
modules\billing\src\api\router.py:786:@router.post("/invoicing-configs", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:793:    return {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), **body.model_dump()}
modules\billing\src\api\router.py:796:@router.put("/invoicing-configs/{config_id}", response_model=dict)
modules\billing\src\api\router.py:812:@router.get("/invoices", response_model=list[dict])
modules\billing\src\api\router.py:871:@router.post("/invoices/generate", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:881:@router.get("/invoices/{invoice_id}", response_model=dict)
modules\billing\src\api\router.py:951:@router.post("/invoices/{invoice_id}/approve", response_model=dict)
modules\billing\src\api\router.py:961:@router.post("/invoices/{invoice_id}/send", response_model=dict)
modules\billing\src\api\router.py:971:@router.post("/invoices/{invoice_id}/void", response_model=dict)
modules\billing\src\api\router.py:982:@router.get("/invoices/{invoice_id}/line-items", response_model=list[dict])
modules\billing\src\api\router.py:1035:@router.get("/ar", response_model=list[dict])
modules\billing\src\api\router.py:1088:@router.get("/ar/aging", response_model=ARAgingResponse)
modules\billing\src\api\router.py:1143:@router.post("/ar/{ar_id}/payment", status_code=status.HTTP_200_OK, response_model=dict)
modules\billing\src\api\router.py:1154:@router.post("/ar/{ar_id}/dispute", status_code=status.HTTP_200_OK, response_model=dict)
modules\billing\src\api\router.py:1165:@router.post("/ar/{ar_id}/write-off", status_code=status.HTTP_200_OK, response_model=dict)
modules\billing\src\api\router.py:1181:@router.get("/journal", response_model=list[dict])
modules\billing\src\api\router.py:1257:@router.get("/journal/summary", response_model=dict)
modules\billing\src\api\router.py:1312:@router.get("/journal/export", response_model=dict)
modules\billing\src\api\router.py:1324:@router.post("/journal/close-period", response_model=dict)
modules\billing\src\api\router.py:1339:@router.get("/fees", response_model=list[dict])
modules\billing\src\api\router.py:1383:@router.post("/fees", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:1390:    return {"id": str(uuid.uuid4()), **body.model_dump()}
modules\billing\src\api\router.py:1393:@router.put("/fees/{fee_id}", response_model=dict)
modules\billing\src\api\router.py:1409:@router.get("/program-budgets", response_model=list[dict])
modules\billing\src\api\router.py:1461:@router.post("/program-budgets", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:1468:    return {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), **body.model_dump()}
modules\billing\src\api\router.py:1471:@router.put("/program-budgets/{budget_id}", response_model=dict)
modules\billing\src\api\router.py:1482:@router.get("/program-budgets/{budget_id}/dashboard", response_model=dict)
modules\billing\src\api\router.py:1538:@router.get("/program-budgets/{budget_id}/snapshots", response_model=list[dict])
modules\billing\src\api\router.py:1580:@router.get("/program-budgets/{budget_id}/alerts", response_model=list[dict])
modules\billing\src\api\router.py:1628:    response_model=dict,
modules\billing\src\api\router.py:1645:@router.get("/payment-vendors", response_model=list[dict])
modules\billing\src\api\router.py:1687:@router.post("/payment-vendors", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:1694:    return {"id": str(uuid.uuid4()), **body.model_dump()}
modules\billing\src\api\router.py:1697:@router.put("/payment-vendors/{vendor_id}", response_model=dict)
modules\billing\src\api\router.py:1713:@router.get("/bank-accounts", response_model=list[dict])
modules\billing\src\api\router.py:1754:@router.post("/bank-accounts", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:1764:@router.put("/bank-accounts/{account_id}", response_model=dict)
modules\billing\src\api\router.py:1780:@router.get("/accounting/config", response_model=dict)
modules\billing\src\api\router.py:1789:@router.put("/accounting/config", response_model=dict)
modules\billing\src\api\router.py:1796:    return body.model_dump(exclude_none=True)
modules\billing\src\api\router.py:1804:@router.get("/remittance-configs", response_model=list[dict])
modules\billing\src\api\router.py:1845:@router.post("/remittance-configs", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:1852:    return {"id": str(uuid.uuid4()), **body.model_dump()}
modules\billing\src\api\router.py:1860:@router.get("/sftp-configs", response_model=list[dict])
modules\billing\src\api\router.py:1903:@router.post("/sftp-configs", status_code=status.HTTP_201_CREATED, response_model=dict)
modules\billing\src\api\router.py:1913:@router.post("/sftp-configs/{config_id}/test", response_model=SFTPTestResponse)
modules\billing\src\api\router.py:1928:@router.get("/funding", response_model=list[dict])
modules\billing\src\api\router.py:1947:                "funding_model": r.funding_model,
modules\billing\src\api\router.py:1969:@router.put("/funding/{config_id}", response_model=dict)
modules\billing\src\api\router.py:1980:@router.get("/funding/{config_id}/ledger", response_model=list[dict])
modules\billing\src\api\router.py:2025:@router.post("/funding/{config_id}/deposit", status_code=status.HTTP_200_OK, response_model=dict)
modules\billing\src\api\router.py:2036:@router.get("/funding/{config_id}/projection", response_model=dict)
modules\billing\src\api\router.py:2051:@router.get("/reports/ap-summary", response_model=dict)
modules\billing\src\api\router.py:2063:@router.get("/reports/ar-aging", response_model=dict)
modules\billing\src\api\router.py:2073:@router.get("/reports/payment-history", response_model=list[dict])
modules\billing\src\api\router.py:2085:@router.get("/reports/fee-summary", response_model=dict)
modules\billing\src\api\router.py:2097:@router.get("/reports/prefund-history", response_model=list[dict])
modules\billing\src\api\router.py:2107:@router.get("/reports/cash-flow", response_model=dict)
modules\billing\src\api\router.py:2118:@router.get("/reports/program-performance", response_model=dict)
modules\billing\src\api\router.py:2130:@router.get("/reports/period-close", response_model=dict)
modules\billing\src\api\router.py:2140:@router.get("/reports/1099-data", response_model=list[dict])
shared\data_ingestion\sources\ncpdp_dataq.py:488:        from src.models.ncpdp_tables import (
modules\core-platform\src\auth\api_keys\service.py:22:from src.auth.api_keys.models import ApiKey
modules\edi-compliance\src\x12\generators\gen_999.py:25:        "0", "T" if req.test_mode else "P", delims.sub_element,
modules\edi-compliance\src\x12\generators\gen_999.py:107:        "0", "T" if req.test_mode else "P", delims.sub_element,
shared\data_ingestion\sources\icd10_cm.py:351:    from shared.db.models.icd10_cm_codes import Icd10CmCode
modules\core-platform\src\auth\api_keys\models.py:1:"""Local model for core.api_keys (SQLite-compatible shim).
modules\core-platform\src\auth\api_keys\models.py:3:INTEGRATION NOTE: replace with shared.db.models.core.ApiKey
modules\core-platform\src\auth\api_keys\models.py:16:from src.auth._models import GUID, Base
modules\reclaimrx\tests\unit\test_consumers_and_jobs.py:31:    job_retrain_ml_models,
modules\reclaimrx\tests\unit\test_consumers_and_jobs.py:34:from src.models.tables import PaymentHold
modules\reclaimrx\tests\unit\test_consumers_and_jobs.py:165:    def test_retrain_ml_models(self, db: Session) -> None:
modules\reclaimrx\tests\unit\test_consumers_and_jobs.py:166:        result = job_retrain_ml_models(db, str(TEST_TENANT_ID))
modules\reclaimrx\tests\unit\test_consumers_and_jobs.py:167:        assert "models_retrained" in result
modules\reclaimrx\tests\unit\test_consumers_and_jobs.py:248:            "retrain_ml_models",
shared\data_ingestion\sources\hcpcs.py:429:    from shared.db.models.hcpcs_codes import HcpcsCode
modules\edi-compliance\src\x12\generators\gen_837p.py:23:    usage = "T" if req.test_mode else "P"
shared\data_ingestion\sources\gov_exclusion_federal_seed.py:31:from shared.models.gov_exclusion_tables import GovernmentProgramBin
modules\edi-compliance\src\x12\generators\gen_837i.py:30:        "0", "T" if req.test_mode else "P", delims.sub_element,
shared\data_ingestion\sources\gov_exclusion.py:36:from shared.models.gov_exclusion_tables import VALID_PLAN_TYPES, GovernmentProgramBin
shared\data_ingestion\sources\fda_rems.py:323:        from drug_database.models.fda_supplementary_tables import DrugRems, DrugRemsNdc  # type: ignore[import]
modules\edi-compliance\src\x12\generators\gen_837d.py:30:        "0", "T" if req.test_mode else "P", delims.sub_element,
shared\tests\db\test_tenant_context.py:8:* A query against a tenant-scoped model with *no* tenant context set is
shared\tests\db\test_tenant_context.py:26:from shared.db.models.core import Tenant, User
shared\tests\db\test_tenant_context.py:116:async def test_tenant_exempt_does_not_affect_non_scoped_models(pg_sessionmaker) -> None:
modules\edi-compliance\src\x12\generators\gen_278.py:24:        "0", "T" if req.test_mode else "P", delims.sub_element,
shared\data_ingestion\sources\fda_orange_book.py:509:        from drug_database.models.orange_book_tables import (  # type: ignore[import]
modules\core-platform\src\auth\api\user_router.py:54:@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
modules\core-platform\src\auth\api\user_router.py:79:@router.get("", response_model=list[UserResponse])
modules\core-platform\src\auth\api\user_router.py:87:@router.get("/{user_id}", response_model=UserResponse)
modules\core-platform\src\auth\api\user_router.py:100:@router.put("/{user_id}", response_model=UserResponse)
modules\core-platform\src\auth\api\user_router.py:123:@router.put("/{user_id}/roles", response_model=UserResponse)
modules\core-platform\src\auth\api\user_router.py:145:@router.post("/{user_id}/lock", response_model=UserResponse)
modules\core-platform\src\auth\api\user_router.py:165:@router.post("/{user_id}/unlock", response_model=UserResponse)
shared\data_ingestion\sources\fda_ndc.py:552:        from drug_database.models.ndc_tables import (  # type: ignore[import]
modules\core-platform\src\auth\api\role_router.py:46:@router.get("/roles", response_model=list[RoleResponse])
modules\core-platform\src\auth\api\role_router.py:54:@router.post("/roles", response_model=RoleResponse, status_code=201)
modules\core-platform\src\auth\api\role_router.py:75:@router.put("/roles/{role_id}", response_model=RoleResponse)
modules\core-platform\src\auth\api\role_router.py:99:@router.put("/roles/{role_id}/permissions", response_model=RoleResponse)
modules\core-platform\src\auth\api\role_router.py:123:@router.get("/permissions", response_model=list[PermissionResponse])
modules\edi-compliance\src\x12\generators\gen_277.py:21:        "0", "T" if req.test_mode else "P", delims.sub_element,
modules\core-platform\src\auth\api\auth_router.py:140:        ).model_dump()
modules\core-platform\src\auth\api\auth_router.py:149:    ).model_dump()
modules\core-platform\src\auth\api\auth_router.py:152:@router.post("/mfa/verify", response_model=TokenResponse)
modules\core-platform\src\auth\api\auth_router.py:171:    from src.auth._models import User
modules\core-platform\src\auth\api\auth_router.py:260:@router.post("/refresh", response_model=TokenResponse)
modules\core-platform\src\auth\api\auth_router.py:292:@router.get("/me", response_model=UserResponse)
modules\core-platform\src\auth\api\auth_router.py:303:@router.put("/me", response_model=UserResponse)
modules\edi-compliance\src\x12\generators\gen_276.py:21:        "0", "T" if req.test_mode else "P", delims.sub_element,
shared\data_ingestion\sources\dea_registrations.py:99:                "validator-only mode active"
shared\data_ingestion\sources\dea_registrations.py:118:                    "— validator-only mode active"
shared\data_ingestion\sources\dea_registrations.py:185:            from src.models.compliance_tables import DeaRegistration  # type: ignore[import]
shared\data_ingestion\sources\dea_registrations.py:192:            from src.models.compliance_tables import DeaRegistration  # type: ignore[import]
shared\data_ingestion\sources\dea_registrations.py:275:                "validator-only mode active"
shared\data_ingestion\sources\dea_registrations.py:278:                "DEA bulk file not accessible — validator-only mode",
shared\tests\db\test_phi_mixin.py:1:"""Tests for shared.db.models.phi_mixin.PHIMixin.
shared\tests\db\test_phi_mixin.py:23:from shared.db.models.phi_mixin import PHIMixin
shared\data_ingestion\sources\cms_opt_out.py:261:        _m = importlib.import_module("src.models.medicare_tables")
shared\data_ingestion\sources\cms_opt_out.py:337:        _mm = importlib.import_module("src.models.medicare_tables")
shared\data_ingestion\sources\cms_opt_out.py:339:        _mp = importlib.import_module("src.models.tables")
modules\edi-compliance\src\x12\generators\gen_271.py:21:        "0", "T" if req.test_mode else "P", delims.sub_element,
modules\billing\alembic\versions\0001_billing_baseline.py:3:Creates all 24 tables that the BillingBase ORM models define. Tables are
modules\billing\alembic\versions\0001_billing_baseline.py:546:        sa.Column("funding_model", sa.String(50), nullable=False),
modules\edi-compliance\src\x12\generators\gen_270.py:17:    usage = "T" if req.test_mode else "P"
modules\edi-compliance\src\x12\envelope.py:20:    test_mode: bool = True       # ISA15: T=test, P=production
modules\edi-compliance\src\x12\envelope.py:44:    usage = "T" if config.test_mode else "P"
modules\edi-compliance\src\x12\envelope.py:122:    test_mode: bool
modules\edi-compliance\src\x12\envelope.py:157:        test_mode=(isa[15] == "T"),
shared\tests\db\test_bank_holidays_model.py:23:from shared.db.models.bank_holidays import BankHoliday
shared\tests\db\test_bank_holidays_model.py:224:# 3. ORM model class-level tests (no DB needed)
modules\billing\alembic\env.py:3:Imports shared.db.base metadata and all billing ORM models so that
modules\billing\alembic\env.py:28:# ── Import all ORM models so metadata is populated ────────────────────────
modules\billing\alembic\env.py:30:from src.models.tables import (  # noqa: F401
modules\billing\alembic\env.py:125:if context.is_offline_mode():
shared\data_ingestion\scheduler.py:21:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\tests\db\conftest.py:32:from shared.db.models import core as _core_models  # noqa: F401  ensure metadata populated
shared\data_ingestion\parsers.py:195:    Uses ``openpyxl`` in read-only mode so large files don't balloon RAM.
shared\data_ingestion\ncpdp_roster.py:43:import argparse
shared\data_ingestion\ncpdp_roster.py:356:    parser = argparse.ArgumentParser(
modules\core-platform\src\audit\__init__.py:16:from src.audit.models import AuditLog
shared\data_ingestion\models.py:1:"""ORM models for ingestion run tracking and scheduling.
shared\data_ingestion\models.py:6:on each model cites LESSON-011.
modules\core-platform\src\audit\service.py:21:from src.audit.models import AuditLog, _as_uuid_str
shared\tests\ai\test_openai_client.py:92:            model="gpt-4.1",
shared\tests\ai\test_openai_client.py:103:                model="gpt-4.1",
shared\tests\ai\test_openai_client.py:159:        resp.model = "gpt-4.1"
shared\tests\ai\test_openai_client.py:186:                model="gpt-4.1",
shared\tests\ai\test_openai_client.py:217:                model="gpt-4.1",
shared\tests\ai\test_openai_client.py:247:                model="gpt-4.1",
shared\tests\ai\test_openai_client.py:278:                model="gpt-4.1",
shared\tests\ai\test_openai_client.py:317:                model="gpt-4.1",
shared\tests\ai\test_openai_client.py:351:                model="gpt-4.1",
shared\tests\ai\test_openai_client.py:379:                model="gpt-4.1",
modules\reclaimrx\tests\integration\test_fwa_pipeline.py:26:from src.models.tables import (
modules\core-platform\src\audit\schemas.py:16:    model_config = ConfigDict(frozen=False)
shared\data_ingestion\dataq_ncpdp\__main__.py:23:import argparse
shared\data_ingestion\dataq_ncpdp\__main__.py:60:    parser = argparse.ArgumentParser(
modules\core-platform\src\audit\models.py:1:"""SQLAlchemy stand-in models for core.audit_log.
modules\core-platform\src\audit\models.py:5:models in ``shared.db.models.core``; integration will reconcile by having
modules\core-platform\src\audit\models.py:6:``src.audit.models`` re-export the shared definitions.
modules\reclaimrx\tests\integration\test_cob_event_payload_roundtrip.py:51:from src.models.tables import FlaggedClaim  # noqa: E402
modules\reclaimrx\tests\integration\test_cob_event_payload_roundtrip.py:70:        detection_mode="post_adjudication",
modules\reclaimrx\tests\integration\test_cob_event_payload_roundtrip.py:108:            pricing_model_used="wac",
modules\reclaimrx\tests\integration\test_cob_event_payload_roundtrip.py:155:            pricing_model_used="wac",
modules\reclaimrx\tests\integration\test_api_endpoints_extended.py:13:from src.models.tables import (
shared\services\gov_exclusion_service.py:26:from shared.models.gov_exclusion_tables import GovernmentProgramBin
shared\data_ingestion\dataq_ncpdp\ingester.py:5:own distribution model (it ships a complete monthly snapshot, not
modules\core-platform\src\audit\api.py:39:    @router.get("", response_model=AuditPage)
modules\core-platform\src\audit\api.py:109:    @router.get("/{audit_id}", response_model=AuditEntryRead)
modules\edi-compliance\src\services\denial_scoring.py:3:Uses a lightweight logistic regression model trained on historical denial patterns.
modules\edi-compliance\src\services\denial_scoring.py:56:# In production these would be loaded from a trained model artifact.
modules\drug-database\tests\unit\test_nadac_pricing_lookup.py:14:asyncio_mode = "auto" in pyproject.toml — tests are plain ``async def``.
modules\drug-database\tests\unit\test_nadac_pricing_lookup.py:34:from drug_database.models.pricing_tables import DrugNADACPricingHistory, PricingBase
modules\drug-database\tests\unit\test_nadac_pricing_lookup.py:35:from drug_database.models.tables import DrugBase, DrugPricing
modules\drug-database\tests\unit\test_nadac_pricing_lookup.py:49:        "sqlite:///file:nadac_lookup_test?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\unit\test_nadac_pricing_lookup.py:78:    session = Session(bind=connection, join_transaction_mode="create_savepoint")
modules\ai-nlp\tests\unit\test_usage_logger.py:27:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_usage_logger.py:43:                model="gpt-4.1",
modules\ai-nlp\tests\unit\test_usage_logger.py:56:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_usage_logger.py:70:            model="gpt-4.1-mini",
modules\reclaimrx\tests\conftest.py:56:    session = Session(bind=connection, join_transaction_mode="create_savepoint")  # type: ignore[call-arg]
modules\edi-compliance\src\services\clearinghouse.py:45:    test_mode: bool = True
modules\ai-nlp\tests\unit\test_rag_service.py:91:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_rag_service.py:166:            model="gpt-4.1",
modules\core-platform\scripts\bootstrap_admin.py:47:import argparse
modules\core-platform\scripts\bootstrap_admin.py:73:from src.auth._models import Base, Tenant, User  # noqa: E402
modules\core-platform\scripts\bootstrap_admin.py:254:def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
modules\core-platform\scripts\bootstrap_admin.py:255:    parser = argparse.ArgumentParser(
modules\drug-database\tests\unit\test_infrastructure.py:22:from drug_database.models.tables import DrugBase
modules\drug-database\tests\unit\test_infrastructure.py:30:        "sqlite:///file:drug_test_infra?mode=memory&cache=shared&uri=true",
shared\data_ingestion\common.py:5:logic (flatten, upsert row shape, mode resolver, response-envelope
shared\data_ingestion\common.py:160:      - a ``str`` or ``pathlib.Path`` (opened in binary mode internally), or
modules\drug-database\tests\unit\test_bench_fdb_lookup_script.py:5:Verifies argparse behavior and SQL content WITHOUT requiring a live
modules\switch-connectivity\src\switch_connectivity\audit\writer.py:121:        # Local filesystem writes are synchronous and unbuffered (mode "a").
modules\ai-nlp\tests\unit\test_models.py:1:"""Unit tests for ai_nlp ORM models — written FIRST (TDD)."""
modules\ai-nlp\tests\unit\test_models.py:7:from src.models.tables import (
modules\drug-database\tests\unit\test_final_coverage_gaps.py:95:        from drug_database.models.tables import DrugBase, DrugPricing, DrugProduct
modules\drug-database\tests\unit\test_final_coverage_gaps.py:98:            "sqlite:///file:drug_no_eff_price?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\unit\test_final_coverage_gaps.py:181:        from drug_database.models.tables import DrugBase, DrugProduct, TenantPricingOverride
modules\drug-database\tests\unit\test_final_coverage_gaps.py:184:            "sqlite:///file:drug_update_override?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\unit\test_final_coverage_gaps.py:270:        from drug_database.models.tables import DrugBase, DrugShortage
modules\drug-database\tests\unit\test_final_coverage_gaps.py:273:            "sqlite:///file:drug_shortage_filter?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\unit\test_final_coverage_gaps.py:335:        from drug_database.models.tables import DrugBase
modules\drug-database\tests\unit\test_final_coverage_gaps.py:338:            "sqlite:///file:drug_shortage_badndc?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\unit\test_final_coverage_gaps.py:377:        from drug_database.models.tables import DrugBase
modules\drug-database\tests\unit\test_final_coverage_gaps.py:380:            "sqlite:///file:drug_deps_health?mode=memory&cache=shared&uri=true",
modules\edi-compliance\src\services\baa_tracking.py:7:Persistence: ``TradingPartnerAgreement`` model in ``models/edi_models.py``.
modules\edi-compliance\src\services\baa_tracking.py:9:Date inputs and outputs are ISO ``YYYY-MM-DD`` strings — the model column is
modules\edi-compliance\src\services\baa_tracking.py:25:from ..models.edi_models import TradingPartnerAgreement
modules\ai-nlp\tests\unit\test_guardrails.py:68:    def test_detects_self_reference_language_model(self) -> None:
modules\ai-nlp\tests\unit\test_guardrails.py:70:        result = g.check("I am a language model and cannot provide medical advice.")
modules\ai-nlp\tests\unit\test_guardrails.py:101:        result = g.check("I am a language model")
modules\drug-database\tests\unit\test_fdb_pricing_service.py:21:    - strict_swp mode skips Tier 2
modules\drug-database\tests\unit\test_fdb_pricing_service.py:39:from drug_database.models.fdb_pricing_tables import FDBNDCPriceHistory, FDBPricingBase
modules\drug-database\tests\unit\test_fdb_pricing_service.py:50:        "sqlite:///file:fdb_pricing_lookup_test?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\unit\test_fdb_pricing_service.py:66:    session = Session(bind=connection, join_transaction_mode="create_savepoint")
modules\drug-database\tests\unit\test_fdb_pricing_service.py:205:def test_strict_swp_mode_skips_swd_tier(db_session: Session) -> None:
shared\data_ingestion\base.py:25:from shared.data_ingestion.models import IngestionRun
modules\drug-database\tests\unit\test_fdb_pricing_models.py:1:"""Unit tests for FDBPricingBase ORM models (Phase 09 / 09.2 deliverable).
modules\drug-database\tests\unit\test_fdb_pricing_models.py:39:from drug_database.models.fdb_pricing_tables import (
modules\drug-database\tests\unit\test_fdb_pricing_models.py:60:        "sqlite:///file:fdb_pricing_models_test?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\unit\test_fdb_pricing_models.py:86:    session = Session(bind=connection, join_transaction_mode="create_savepoint")
modules\ai-nlp\tests\unit\test_final_coverage.py:52:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_final_coverage.py:108:        mock_resp.model = "gpt-4.1"
modules\ai-nlp\tests\unit\test_final_coverage.py:118:                model="gpt-4.1",
modules\ai-nlp\tests\unit\test_final_coverage.py:127:    async def test_mini_model_uses_mini_deployment(self) -> None:
modules\ai-nlp\tests\unit\test_final_coverage.py:147:        mock_resp.model = "gpt-4.1-mini"
modules\ai-nlp\tests\unit\test_final_coverage.py:162:                model="gpt-4.1-mini",
modules\ai-nlp\tests\unit\test_final_coverage.py:167:        assert captured[0]["model"] == "deploy-mini"
modules\ai-nlp\tests\unit\test_final_coverage.py:199:                model="gpt-4.1",
modules\ai-nlp\tests\unit\test_final_coverage.py:237:            model="gpt-4.1",
modules\switch-connectivity\src\switch_connectivity\audit\cli.py:9:Full CLI ergonomics (click, argparse, operator-toolkit integration) are
modules\switch-connectivity\src\switch_connectivity\audit\cli.py:16:import argparse
modules\switch-connectivity\src\switch_connectivity\audit\cli.py:32:    parser = argparse.ArgumentParser(
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:5:  * fdb_initial mode loads price_type_desc + RNP3 from DB.zip; all
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:7:  * fdb_weekly mode reads UPD.zip with A/C/D prefixes; transaction_code
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:35:from drug_database.models.fdb_pricing_tables import (
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:54:        "sqlite:///file:fdb_ingester_test?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:70:    session = Session(bind=connection, join_transaction_mode="create_savepoint")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:140:# Synthetic catalog rows (RPRDPTD0 — modern; pipe + latin-1 + CRLF).
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:196:            "RNP3_NDC_PRICE": b"",  # not read in fdb_weekly mode
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:239:# fdb_initial — full DB.zip baseline
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:243:def test_fdb_initial_loads_price_type_desc(initial_drop, db_session):
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:244:    """fdb_initial mode loads RPRDPTD0 + RNPTYPD0 into fdb_price_type_desc.
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:251:    result = ing.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:254:    assert result.mode == "fdb_initial"
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:265:def test_fdb_initial_legacy_rnptypd0_uses_synthetic_id(initial_drop, db_session):
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:273:    ing.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:287:def test_fdb_initial_loads_rnp3_with_transaction_code_a(initial_drop, db_session):
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:288:    """fdb_initial mode treats every RNP3 row as transaction_code='A'."""
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:290:    result = ing.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:301:def test_fdb_initial_denormalizes_price_type_id(initial_drop, db_session):
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:304:    ing.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:316:def test_fdb_initial_dry_run_does_not_write(initial_drop, db_session):
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:319:    result = ing.run(mode="fdb_initial", dry_run=True)
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:330:# fdb_weekly — UPD.zip A/C/D handling
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:334:def test_fdb_weekly_strips_acd_prefix_and_persists_codes(weekly_drop, db_session):
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:337:    result = ing.run(mode="fdb_weekly")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:353:    first = ing.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:361:    second = ing2.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:369:    ing.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:374:    second = ing2.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:387:    result = ing.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:393:    result = ing.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:401:    ing.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:428:    first = ing1.run(mode="fdb_initial")
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:450:    second = ing2.run(mode="fdb_initial")
modules\ai-nlp\tests\unit\test_events.py:97:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_events.py:126:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_document_extraction.py:109:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_document_extraction.py:136:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_document_extraction.py:163:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_document_extraction.py:195:            model="gpt-4.1",
modules\drug-database\tests\unit\test_drug_lookup_service.py:36:    def query(self, model):
modules\ai-nlp\tests\unit\test_coverage_gaps.py:143:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_coverage_gaps.py:285:        mock_resp.model = "gpt-4.1"
modules\ai-nlp\tests\unit\test_coverage_gaps.py:306:                model="gpt-4.1",
modules\ai-nlp\tests\unit\test_coverage_gaps.py:343:                model="gpt-4.1",
modules\ai-nlp\tests\unit\test_coverage_gaps.py:395:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_coverage_gaps.py:432:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_coverage_gaps.py:461:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_coverage_gaps.py:486:            model="gpt-4.1",
modules\ai-nlp\tests\unit\test_coverage_gaps.py:511:            model="gpt-4.1",
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:15:    `.run(mode=...)` method (smoke check; ingestion against synthetic
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:64:    import drug_database.models.fdb_pricing_tables  # noqa: F401
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:89:    from drug_database.models.fdb_pricing_tables import FDBPricingBase
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:103:    from drug_database.models.fdb_pricing_tables import FDBPricingBase
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:106:        "sqlite:///file:fdb_integration_test?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:122:    session = Session(bind=connection, join_transaction_mode="create_savepoint")
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:204:    """FDBPricingIngester instantiates and exposes .run(mode=...).
modules\edi-compliance\src\models\edi_models.py:1:"""SQLAlchemy ORM models for the edi schema.
modules\edi-compliance\src\models\edi_models.py:70:    test_mode: Mapped[bool] = mapped_column(Boolean, default=True)
modules\drug-database\tests\integration\test_coverage_gaps_integration.py:25:from drug_database.models.tables import DrugBase, DrugProduct, TenantPricingOverride
modules\drug-database\tests\integration\test_coverage_gaps_integration.py:34:        "sqlite:///file:drug_test_cov_gaps?mode=memory&cache=shared&uri=true",
shared\data_ingestion\api\routes.py:38:from shared.data_ingestion.models import IngestionRun, IngestionSchedule
shared\data_ingestion\api\routes.py:107:        **summary.model_dump(),
shared\data_ingestion\api\routes.py:129:    response_model=TriggerResponse,
shared\data_ingestion\api\routes.py:204:    response_model=TriggerResponse,
shared\data_ingestion\api\routes.py:262:    response_model=list[SourceStatus],
shared\data_ingestion\api\routes.py:297:    response_model=list[RunSummary],
shared\data_ingestion\api\routes.py:335:    response_model=RunDetail,
shared\data_ingestion\api\routes.py:357:    response_model=CancelResponse,
shared\data_ingestion\api\routes.py:408:    response_model=FieldCatalogResponse,
modules\switch-connectivity\src\switch_connectivity\api\auth.py:3:Security model (per Session 3 scope):
modules\switch-connectivity\src\switch_connectivity\api\auth.py:5:  * Dev-mode: bearer token is validated against the ``SWITCH_CONNECTIVITY_ADMIN_TOKEN``
modules\switch-connectivity\src\switch_connectivity\api\auth.py:11:  * Production-mode (Session 12): env var is replaced by JWT verification
modules\switch-connectivity\src\switch_connectivity\api\auth.py:36:# Environment variable that holds the admin bearer token in dev-mode.
modules\edi-compliance\src\main.py:64:        logger.info("edi-compliance service started (standalone mode)", extra={"svc_name": "edi-compliance"})
modules\drug-database\tests\integration\test_app_middleware.py:22:from drug_database.models.tables import DrugBase
modules\switch-connectivity\src\switch_connectivity\api\adapters.py:96:    response_model=AdapterReloadResponse,
modules\drug-database\tests\integration\test_api_router_coverage.py:20:from drug_database.models.tables import (
modules\drug-database\tests\integration\test_api_router_coverage.py:35:        "sqlite:///file:drug_test_router?mode=memory&cache=shared&uri=true",
modules\ncpdp-core\tests\wire\test_raw_roundtrip.py:166:    def test_lenient_mode_tolerates_short_input(self) -> None:
modules\drug-database\tests\integration\test_api_endpoints.py:25:from drug_database.models.tables import (
modules\drug-database\tests\integration\test_api_endpoints.py:46:        "sqlite:///file:drug_test_api?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\integration\test_api_endpoints.py:145:        severity="moderate",
modules\drug-database\tests\integration\test_api_endpoints.py:304:        assert data[0]["severity"] == "moderate"
modules\ncpdp-core\tests\wire\test_overpunch.py:215:    """Default mode: legacy-parity explicit sign + decimal-point form."""
modules\ncpdp-core\tests\wire\test_overpunch.py:230:    """Overpunch mode: spec-conformant D.Ø wire format (NC-FR-023)."""
modules\ncpdp-core\tests\wire\test_header.py:9:- Legacy parse_header_fields: strict and lenient modes preserved
modules\drug-database\tests\conftest.py:20:from drug_database.models.tables import DrugBase
modules\drug-database\tests\conftest.py:27:        "sqlite:///file:drug_test_shared?mode=memory&cache=shared&uri=true",
modules\drug-database\tests\conftest.py:53:    session = Session(bind=connection, join_transaction_mode="create_savepoint")
modules\ncpdp-core\tests\wire\test_codec.py:12:    """Well-formed input — behaves identically in strict and lenient modes."""
modules\reclaimrx\src\_shim\db.py:31:    """Declarative base for reclaimrx models."""
modules\reclaimrx\src\_shim\db.py:43:    # Wire the platform-wide tenant loader so reclaimrx models that
modules\payment-processing\tests\unit\test_submission_service.py:10:from src.models.tables import Settlement, Submission
modules\prescriber-directory\alembic\versions\0000_prescriber_baseline.py:4:exist but no prior migration ever created. Each table maps 1:1 to a model in
modules\prescriber-directory\alembic\versions\0000_prescriber_baseline.py:5:``src/models/tables.py``.
modules\prescriber-directory\alembic\versions\0000_prescriber_baseline.py:8:  * prescriber_dir.prescribers                       (owned by Prescriber model)
modules\payment-processing\tests\unit\test_reconciliation_service.py:9:from src.models.tables import Settlement, Submission
modules\prescriber-directory\alembic\env.py:3:Imports shared.db.base metadata and all prescriber_dir ORM models so that
modules\prescriber-directory\alembic\env.py:27:# ── Import all ORM models so metadata is populated ────────────────────────
modules\prescriber-directory\alembic\env.py:29:from src.models.tables import (  # noqa: F401
modules\prescriber-directory\alembic\env.py:39:from src.models.nppes_tables import (  # noqa: F401
modules\prescriber-directory\alembic\env.py:112:if context.is_offline_mode():
modules\ai-nlp\tests\integration\test_smoke_real_db.py:17:  * The ORM model drifted from the DB schema.
modules\ai-nlp\tests\integration\test_smoke_real_db.py:197:                       input_type, model_used, confidence_score, status)
modules\edi-compliance\src\api\trading_partners.py:17:from ..models.edi_models import TradingPartner
modules\edi-compliance\src\api\trading_partners.py:52:    test_mode: bool = True
modules\edi-compliance\src\api\trading_partners.py:65:    test_mode: bool
modules\edi-compliance\src\api\trading_partners.py:69:@router.get("", response_model=list[TradingPartnerResponse])
modules\edi-compliance\src\api\trading_partners.py:92:            test_mode=p.test_mode,
modules\edi-compliance\src\api\trading_partners.py:99:@router.post("", response_model=TradingPartnerResponse, status_code=201)
modules\edi-compliance\src\api\trading_partners.py:116:        test_mode=body.test_mode,
modules\edi-compliance\src\api\trading_partners.py:132:        test_mode=partner.test_mode,
modules\edi-compliance\src\api\trading_partners.py:176:@router.get("/{partner_id}/agreements", response_model=list[AgreementResponse])
modules\edi-compliance\src\api\trading_partners.py:189:@router.post("/{partner_id}/agreements", response_model=AgreementResponse, status_code=201)
modules\edi-compliance\src\api\trading_partners.py:220:@router.get("/agreements/expiring", response_model=list[AgreementResponse])
modules\ai-nlp\tests\integration\test_schema_smoke.py:70:                     input_type, model_used, status)
modules\ai-nlp\tests\integration\test_schema_smoke.py:108:                     chunk_text, embedding, model_used)
modules\ai-nlp\tests\integration\test_schema_smoke.py:151:                     input_type, model_used, confidence_score)
modules\edi-compliance\src\api\parse.py:49:@router.post("/835", response_model=ParseResponse)
modules\edi-compliance\src\api\parse.py:82:@router.post("/271", response_model=ParseResponse)
modules\edi-compliance\src\api\parse.py:114:@router.post("/277", response_model=ParseResponse)
modules\edi-compliance\src\api\parse.py:142:@router.post("/278", response_model=ParseResponse)
modules\edi-compliance\src\api\parse.py:172:@router.post("/834", response_model=ParseResponse)
modules\edi-compliance\src\api\parse.py:201:@router.post("/999", response_model=ParseResponse)
modules\edi-compliance\src\api\parse.py:230:@router.post("/ta1", response_model=ParseResponse)
modules\edi-compliance\src\api\parse.py:257:@router.post("/validate", response_model=ParseResponse)
modules\ncpdp-core\tests\conformance\test_relayhealth_production_pairs.py:11:RelayHealth produces, then for that segment our model is wire-correct.
modules\ncpdp-core\tests\conformance\test_relayhealth_production_pairs.py:141:    # fields are not yet modeled in our Layer 2 AM21 dataclass (Wave 32
modules\ncpdp-core\tests\conformance\test_relayhealth_production_pairs.py:264:    # UH/UF/FQ are present in raw fields even though our AM21 model doesn't
modules\ai-nlp\tests\integration\test_router_wiring.py:41:        model="gpt-4.1",
modules\ai-nlp\tests\integration\test_router_wiring.py:546:        mock_row.model = "gpt-4.1"
modules\ai-nlp\tests\integration\test_router_wiring.py:574:        assert row["model"] == "gpt-4.1"
modules\ai-nlp\tests\integration\test_router_wiring.py:728:        # The WHERE clause must contain tenant_id — verified by model-level TenantScopedMixin
modules\ai-nlp\tests\integration\test_router_wiring.py:738:    async def test_get_usage_stats_returns_model_aggregates(self) -> None:
modules\ai-nlp\tests\integration\test_router_wiring.py:742:        mock_row.model = "gpt-4.1"
modules\ai-nlp\tests\integration\test_router_wiring.py:758:        assert stats[0]["model"] == "gpt-4.1"
modules\ai-nlp\tests\integration\test_router_wiring.py:770:        mock_row.model = "gpt-4.1-mini"
modules\edi-compliance\src\api\generate.py:65:@router.post("/837p", response_model=GenerateResponse)
modules\edi-compliance\src\api\generate.py:82:@router.post("/270", response_model=GenerateResponse)
modules\edi-compliance\src\api\generate.py:93:@router.post("/271", response_model=GenerateResponse)
modules\edi-compliance\src\api\generate.py:104:@router.post("/276", response_model=GenerateResponse)
modules\edi-compliance\src\api\generate.py:115:@router.post("/277", response_model=GenerateResponse)
modules\edi-compliance\src\api\generate.py:126:@router.post("/837i", response_model=GenerateResponse)
modules\edi-compliance\src\api\generate.py:143:@router.post("/837d", response_model=GenerateResponse)
modules\edi-compliance\src\api\generate.py:160:@router.post("/278", response_model=GenerateResponse)
modules\edi-compliance\src\api\generate.py:171:@router.post("/999", response_model=GenerateResponse)
modules\edi-compliance\src\api\generate.py:182:@router.post("/ta1", response_model=GenerateResponse)
modules\payment-processing\tests\unit\test_ofac_db_screening.py:18:from src.models.tables import OfacScreeningAlert, OfacSdnEntry
modules\ai-nlp\tests\integration\test_rls_tenant_isolation.py:103:             input_type, model_used, status)
modules\ai-nlp\tests\integration\test_rls_tenant_isolation.py:127:            "requesting_module, input_type, model_used, status) VALUES "
modules\ai-nlp\tests\integration\test_rls_tenant_isolation.py:389:            "requesting_module, input_type, model_used, status) VALUES "
modules\ai-nlp\tests\integration\test_rls_tenant_isolation.py:430:                "service_type, requesting_module, input_type, model_used, status) "
modules\edi-compliance\src\api\compliance.py:17:from ..models.edi_models import TransactionFile
modules\edi-compliance\src\api\compliance.py:44:@router.get("", response_model=ComplianceDashboard)
modules\ncpdp-core\tests\conformance\test_ifx_production_samples.py:32:  - Field dropping: fields not modeled on typed segment classes are omitted from
modules\ncpdp-core\tests\conformance\test_ifx_production_samples.py:40:  modeled segments) passes for all 4 samples. This is the correct conformance
modules\ncpdp-core\tests\conformance\test_ifx_production_samples.py:42:  ordering, overpunch encoding, and non-modeled field passthrough, which is
modules\ncpdp-core\tests\conformance\test_ifx_production_samples.py:126:    - Field dropping: unmodeled fields absent from to_raw_transaction().
modules\ncpdp-core\tests\conformance\test_ifx_production_samples.py:210:    # mis-modeled at AM24 in Wave 32). IFX paid response carries AM22
modules\ncpdp-core\tests\conformance\test_ifx_production_samples.py:250:    # Response Layer 3 roundtrip — segment presence check (AM20 not modeled)
modules\ncpdp-core\tests\conformance\test_ifx_production_samples.py:327:    # Response Layer 3 roundtrip — segment presence check (AM20 not modeled)
modules\ncpdp-core\tests\conformance\test_ifx_production_samples.py:379:    # AM21 raw fields — 563-UH and 526-FQ not modeled as named attributes
modules\ncpdp-core\tests\transactions\test_e1_transactions.py:409:        §27.2; was previously modeled with phantom 524-FO Plan ID."""
modules\plan-design\tests\unit\test_pricing.py:1:"""Tests for all 8 pricing model calculators — 100% financial path coverage.
modules\switch-connectivity\src\switch_connectivity\adapters\relay_cmm\errors.py:4:the base class when they don't care about the specific failure mode, or
modules\reclaimrx\src\services\rule_engine.py:61:    detection_mode: str  # real_time, post_adjudication, both
modules\reclaimrx\src\services\rule_engine.py:291:                detection_mode=rule.detection_mode,
modules\reclaimrx\src\services\payment_hold_service.py:12:from src.models.tables import PaymentHold
modules\reclaimrx\src\services\ml_scoring.py:156:    """Generate synthetic training data for base model. Deterministic via seed."""
modules\reclaimrx\src\services\ml_scoring.py:175:    Ships with a base model trained on synthetic data.
modules\reclaimrx\src\services\ml_scoring.py:182:        self._model = XGBClassifier(
modules\reclaimrx\src\services\ml_scoring.py:192:        self._fit_base_model(n_training_samples)
modules\reclaimrx\src\services\ml_scoring.py:194:    def _fit_base_model(self, n_samples: int) -> None:
modules\reclaimrx\src\services\ml_scoring.py:196:        self._model.fit(X, y)
modules\reclaimrx\src\services\ml_scoring.py:203:        prob = float(self._model.predict_proba(arr)[0][1])
modules\reclaimrx\src\services\ml_scoring.py:211:        importances = self._model.feature_importances_
modules\reclaimrx\src\services\ml_scoring.py:219:        """Retrain model on labeled outcome data."""
modules\reclaimrx\src\services\ml_scoring.py:220:        self._model.fit(X, y)
modules\reclaimrx\src\services\ml_scoring.py:243:        self._model = IsolationForest(
modules\reclaimrx\src\services\ml_scoring.py:249:        self._fit_base_model()
modules\reclaimrx\src\services\ml_scoring.py:251:    def _fit_base_model(self) -> None:
modules\reclaimrx\src\services\ml_scoring.py:253:        self._model.fit(X)
modules\reclaimrx\src\services\ml_scoring.py:260:        self._model.fit(X)
modules\reclaimrx\src\services\ml_scoring.py:266:        raw_score = float(self._model.decision_function(arr)[0])
modules\reclaimrx\src\services\ml_scoring.py:275:        raw_scores = self._model.decision_function(X)
modules\reclaimrx\src\services\letter_service.py:9:from src.models.tables import LetterTemplate
modules\reclaimrx\src\services\investigation_service.py:11:from src.models.tables import Investigation, InvestigationActivity, Recovery
modules\reclaimrx\src\services\detection_rule_seeder.py:10:from src.models.tables import DetectionProfile, DetectionRule
modules\reclaimrx\src\services\detection_rule_seeder.py:20:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:34:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:48:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:62:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:76:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:90:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:104:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:118:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:137:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:151:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:166:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:180:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:194:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:208:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:222:        "detection_mode": "real_time",
modules\reclaimrx\src\services\detection_rule_seeder.py:236:        "detection_mode": "real_time",
modules\reclaimrx\src\services\detection_rule_seeder.py:250:        "detection_mode": "real_time",
modules\reclaimrx\src\services\detection_rule_seeder.py:264:        "detection_mode": "real_time",
modules\reclaimrx\src\services\detection_rule_seeder.py:278:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:293:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:307:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:321:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:335:        "detection_mode": "real_time",
modules\reclaimrx\src\services\detection_rule_seeder.py:349:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:363:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:377:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:395:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:409:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:423:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:438:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:452:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:466:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:480:        "detection_mode": "real_time",
modules\reclaimrx\src\services\detection_rule_seeder.py:495:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:509:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:523:        "detection_mode": "real_time",
modules\reclaimrx\src\services\detection_rule_seeder.py:537:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:551:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:566:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:580:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:594:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:608:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:623:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:637:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:651:        "detection_mode": "post_adjudication",
modules\reclaimrx\src\services\detection_rule_seeder.py:665:        "detection_mode": "both",
modules\reclaimrx\src\services\detection_rule_seeder.py:679:        "detection_mode": "post_adjudication",
modules\ncpdp-core\src\ncpdp_core\wire\overpunch.py:34:data model), NC-FR-005 (parse), NC-FR-023 (serialize); D.Ø IG §1;
modules\ncpdp-core\src\ncpdp_core\wire\overpunch.py:187:    Two output modes:
modules\ncpdp-core\src\ncpdp_core\wire\overpunch.py:207:    # Overpunch mode: strip sign, format as implied-two-digit-cents
modules\plan-design\tests\conftest.py:38:from src.models.tables import PlanDesignBase
modules\plan-design\tests\conftest.py:129:        join_transaction_mode="create_savepoint",
modules\reclaimrx\src\services\accumulator_service.py:17:from src.models.tables import AccumulatorDetection
modules\ncpdp-core\src\ncpdp_core\wire\header.py:23:``parse_request_header`` in strict mode.
modules\ncpdp-core\src\ncpdp_core\wire\header.py:241:    parse_errors)``. In strict mode (default), raises
modules\ncpdp-core\src\ncpdp_core\wire\header.py:243:    structure. In lenient mode (``strict=False``), returns safe
modules\ncpdp-core\src\ncpdp_core\wire\header.py:247:    Strict-mode enforcement:
modules\ncpdp-core\src\ncpdp_core\wire\header.py:251:    Lenient mode tolerates short input and non-D0 versions, emitting
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:62:    Strict-mode and lenient-mode behavior matches
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:93:    Strict mode (default, per NC-FR-004): fields shorter than 2 bytes
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:99:    Lenient mode (``strict=False``): sub-2-byte fragments are silently
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:110:            # Empty fragment from trailing FS — allowed in both modes.
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:151:        Strict mode (default) propagates WireFormatError from the header
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:152:        codec and field tokenizer. Lenient mode (``strict=False``) routes
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:159:        respectively in strict mode. In lenient mode the header is parsed
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:206:        # Lenient mode: direction-aware where possible, legacy fallback otherwise.
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:234:            # Request direction lenient mode (Wave 33 fix): use the
modules\ncpdp-core\src\ncpdp_core\wire\codec.py:268:            # Empty segment from consecutive RS; skip either mode.
modules\ncpdp-core\tests\conformance\fixtures\ifx_production_samples\convert_samples.py:97:    # Read in binary mode to preserve real control bytes in request lines
modules\payment-processing\tests\integration\test_jobs.py:10:from src.models.tables import Submission, VendorAdapter
modules\payment-processing\tests\integration\test_health_service.py:7:from src.models.tables import VendorAdapter
modules\payment-processing\tests\integration\test_health_service.py:87:        from src.models.tables import VendorHealthLog
modules\payment-processing\tests\integration\test_health_service.py:106:        from src.models.tables import VendorHealthLog
modules\ai-nlp\src\services\usage_logger.py:15:from src.models.tables import AiNlpUsageLog
modules\ai-nlp\src\services\usage_logger.py:27:        model: str,
modules\ai-nlp\src\services\usage_logger.py:39:            model=model,
modules\ai-nlp\src\services\usage_logger.py:55:        """Return per-model usage totals for the tenant."""
modules\ai-nlp\src\services\usage_logger.py:58:                AiNlpUsageLog.model,
modules\ai-nlp\src\services\usage_logger.py:65:            .group_by(AiNlpUsageLog.model)
modules\ai-nlp\src\services\usage_logger.py:66:            .order_by(AiNlpUsageLog.model)
modules\ai-nlp\src\services\usage_logger.py:72:                "model": row.model,
modules\ncpdp-core\tests\segments\test_am07_claim.py:214:        Previously these were modeled as a phantom AM18 segment (Wave
modules\ai-nlp\src\services\rag_service.py:121:            model="gpt-4.1",
modules\ai-nlp\src\services\rag_service.py:148:            model="gpt-4.1-mini",
modules\ncpdp-core\tests\segments\test_am06_workers_comp.py:3:Wave 32 M3c: entire field set re-modeled per IG D.0 §27.1.2. Prior
modules\ai-nlp\src\services\guardrails.py:16:from src.models.tables import AiNlpGuardrailEvent
modules\ai-nlp\src\services\guardrails.py:49:    re.compile(r"\bI\s+am\s+a\s+(language\s+model|AI|LLM|chatbot)\b", re.IGNORECASE),
modules\ai-nlp\src\services\guardrails.py:50:    re.compile(r"\bAs\s+an?\s+(AI|language\s+model|LLM)\b", re.IGNORECASE),
modules\ai-nlp\src\services\document_extraction.py:80:            model="gpt-4.1",
modules\ncpdp-core\tests\segments\test_am05_cob.py:322:        field this wave models."""
modules\ncpdp-core\tests\segments\test_am05_cob.py:453:    def test_duplicate_request_am05_round_trip_modeled_fields(self) -> None:
modules\ncpdp-core\tests\segments\test_am05_cob.py:454:        """Round-trip the fields this wave models from real wire data.
modules\payment-processing\tests\integration\test_api.py:12:from src.models.tables import (
modules\payment-processing\tests\integration\test_api.py:448:        from src.models.tables import AchReturnCode
modules\payment-processing\tests\integration\test_api.py:464:        from src.models.tables import PayeeEnrollment
modules\ncpdp-core\tests\segments\test_am01_patient.py:113:        this segment incorrectly modeled 1C-6C as an employer-address
modules\plan-design\src\services\pricing.py:4:Registry pattern: adding a new model is a config row + one class.
modules\plan-design\src\services\pricing.py:64:    code: str  # Matches pricing_models.code in DB
modules\reclaimrx\src\reclaimrx\models\__init__.py:1:from reclaimrx.models.tables import (
modules\ai-nlp\src\models\__init__.py:1:"""AI/NLP ORM models."""
modules\plan-design\src\services\network.py:18:from src.models.tables import (
modules\plan-design\src\services\network.py:100:            bagging_model=data.get("bagging_model"),
modules\reclaimrx\src\reclaimrx\models\tables.py:1:"""SQLAlchemy ORM models for the reclaimrx module — Wave 42 foundation.
modules\reclaimrx\src\reclaimrx\models\tables.py:46:    """Declarative base for reclaimrx ORM models."""
modules\ai-nlp\src\models\tables.py:1:"""SQLAlchemy ORM models for the ai_nlp schema.
modules\ai-nlp\src\models\tables.py:76:    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
modules\ai-nlp\src\models\tables.py:148:    primary_model_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
modules\ai-nlp\src\models\tables.py:149:    secondary_model_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
modules\ai-nlp\src\models\tables.py:226:    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
modules\ai-nlp\src\models\tables.py:247:    model: Mapped[str] = mapped_column(String(100), nullable=False)
modules\payment-processing\tests\conftest.py:14:from src.models.tables import (
modules\plan-design\src\services\market_access.py:17:from src.models.tables import Formulary, FormularyDrug, Plan
modules\plan-design\src\services\hierarchy.py:19:from src.models.tables import (
modules\plan-design\src\services\hierarchy.py:149:            pricing_model_id=data.get("pricing_model_id"),
modules\plan-design\src\services\hierarchy.py:237:            "pricing_model_id": str(plan.pricing_model_id) if plan.pricing_model_id else None,
modules\plan-design\src\services\hierarchy.py:280:            pricing_model_id=source.pricing_model_id,
modules\plan-design\src\services\formulary.py:19:from src.models.tables import (
modules\ncpdp-core\tests\segments\test_am27_response_insurance_additional_info.py:3:Wave 32 M3c: entire field set re-modeled per IG D.0 §27.2. Prior
modules\ncpdp-core\tests\segments\test_am26_response_prior_authorization.py:3:Wave 32 M6: entire field set re-modeled per IG D.0 + DD. Prior
modules\rules-engine\tests\unit\test_upstream_claims_multi.py:1:"""Wave 31 B4 — multi-Other-Payer data model.
modules\rules-engine\tests\unit\test_upstream_claims_multi.py:4:This test exercises the data-model extension that's ready for
modules\reclaimrx\src\reclaimrx\ingest\paysync_data.py:82:            # but matches the operator's mental model ("show me anomalies
modules\plan-design\src\models\__init__.py:1:"""Plan Design ORM models."""
modules\ncpdp-core\tests\segments\test_am14_additional_documentation.py:3:Wave 32 M3c: entire field set re-modeled per IG D.0 §27.1.2. Prior
modules\reclaimrx\src\reclaimrx\ingest\live_db.py:5:its hierarchy resolution snapshot. Real-time mode (subscribe to
modules\plan-design\src\models\tables.py:1:"""Plan Design ORM models — all tenant-scoped tables.
modules\plan-design\src\models\tables.py:3:Data model covers PRD §11:
modules\plan-design\src\models\tables.py:7:  plan_templates, pricing_models, plan_pricing,
modules\plan-design\src\models\tables.py:168:    Adding a new pricing model is a config row + one calculator class.
modules\plan-design\src\models\tables.py:171:    __tablename__ = "pricing_models"
modules\plan-design\src\models\tables.py:173:        UniqueConstraint("tenant_id", "code", name="uq_pricing_models_tenant_code"),
modules\plan-design\src\models\tables.py:174:        Index("ix_pricing_models_tenant_id", "tenant_id"),
modules\plan-design\src\models\tables.py:222:    pricing_model_id: Mapped[UUID | None] = mapped_column(
modules\plan-design\src\models\tables.py:224:        ForeignKey(f"{SCHEMA}.pricing_models.id"),
modules\plan-design\src\models\tables.py:294:    """Associates a pricing model with a plan (optionally per network tier)."""
modules\plan-design\src\models\tables.py:311:    pricing_model_id: Mapped[UUID] = mapped_column(
modules\plan-design\src\models\tables.py:313:        ForeignKey(f"{SCHEMA}.pricing_models.id"),
modules\plan-design\src\models\tables.py:502:            "bagging_model IN ('white', 'brown', 'clear', 'none') OR bagging_model IS NULL",
modules\plan-design\src\models\tables.py:523:    bagging_model: Mapped[str | None] = mapped_column(String(20))
modules\plan-design\src\models\tables.py:637:    """Saved what-if scenario for benefit design modeling."""
modules\ncpdp-core\tests\segments\test_am13_clinical.py:4:- 491-VE Diagnosis Code Count (was wrongly modeled as the qualifier).
modules\ncpdp-core\tests\segments\test_am13_clinical.py:5:- 492-WE Diagnosis Code Qualifier (was wrongly modeled as a counter).
modules\ncpdp-core\tests\segments\test_am13_clinical.py:7:- 494-ZE Measurement Date (was wrongly modeled as Measurement Unit).
modules\ncpdp-core\tests\segments\test_am13_clinical.py:8:- 495-H1 Measurement Time (was wrongly modeled as Measurement Value).
modules\ncpdp-core\tests\segments\test_am22_response_claim.py:3:Wave 32 M6b: re-modeled per IG D.0 response Claim Segment. Removed
modules\reclaimrx\src\reclaimrx\ingest\csv_upload.py:29:import argparse
modules\reclaimrx\src\reclaimrx\ingest\csv_upload.py:338:def _build_parser() -> argparse.ArgumentParser:
modules\reclaimrx\src\reclaimrx\ingest\csv_upload.py:339:    p = argparse.ArgumentParser(
modules\ncpdp-core\tests\segments\test_am12_prior_authorization.py:3:Wave 32 M3b — entire segment re-modeled per IG D.0 §13.2.6. Prior
modules\ncpdp-core\tests\segments\test_am12_prior_authorization.py:4:implementation modeled AM12 with AM07 Claim Segment field codes
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:73:        → REJECT under strict mode."""
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:81:    def test_flag_only_mode_passes_with_flag(self):
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:86:                "validation_mode": "flag_only",
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:194:    def test_advisory_mode_flags_and_passes(self):
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:211:                    "redirect_mode": "advisory",
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:518:    def test_flag_only_mode_passes_with_flag(self):
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:526:            "validation_mode": "flag_only",
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:546:# Wave 34 — denylist + combined-list mode (ClientE Organon BRD pattern)
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:555:    def test_denylist_mode_no_denylist_codes_passes(self):
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:556:        """Wave 34: list_mode=denylist, no codes hit → PASS."""
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:563:            "list_mode": "denylist",
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:567:    def test_denylist_mode_one_hit_rejects(self):
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:568:        """Wave 34: list_mode=denylist, code on denylist → REJECT 70."""
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:575:            "list_mode": "denylist",
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:581:    def test_both_mode_deny_takes_priority(self):
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:582:        """Wave 34: list_mode=both, claim has BOTH allowed (70) AND
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:596:            "list_mode": "both",
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:601:    def test_both_mode_only_allowed_codes_passes(self):
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:602:        """Wave 34: list_mode=both, no denied codes, all in allowlist → PASS."""
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:610:            "list_mode": "both",
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:614:    def test_denylist_mode_flag_only(self):
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:615:        """Wave 34: list_mode=denylist + validation_mode=flag_only."""
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:622:            "list_mode": "denylist",
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:623:            "validation_mode": "flag_only",
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:628:    def test_denylist_mode_unconfigured_passes(self):
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:629:        """list_mode=denylist with no denylist_oprc → PASS (no-op)."""
modules\rules-engine\tests\unit\test_tier2_routing_rules.py:635:            "list_mode": "denylist",
modules\reclaimrx\src\reclaimrx\ingest\base.py:54:    rules / ML models / etc. It returns the number of anomalies
modules\ai-nlp\src\events\__init__.py:44:            no-DB mode (e.g. test harnesses that exercise only the OpenAI
modules\ncpdp-core\tests\segments\test_am20_response_message.py:140:        the wire-format model away from the numbered-suffix
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:117:def test_copay_fixed_mode():
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:120:        ctx, {"mode": "fixed", "fixed_amount": "25.00"},
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:128:    result = TargetCopayRule().execute(ctx, {"mode": "fixed"})
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:135:        "mode": "first_fill_different",
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:145:        "mode": "first_fill_different",
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:157:        "mode": "first_fill_different",
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:170:        "mode": "save_off_primary", "save_amount": "50.00",
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:183:        "mode": "save_off_primary", "save_amount": "50.00",
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:191:        "mode": "save_off_primary", "save_amount": "50.00",
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:196:def test_copay_unknown_mode_passes():
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:199:        "mode": "wacky_mode", "fixed_amount": "5.00",
modules\rules-engine\tests\unit\test_tier1_pricing_rules.py:204:def test_copay_no_mode_passes():
modules\ai-nlp\src\events\consumers.py:32:                is wired in no-DB mode (e.g. test harnesses that exercise only
modules\ai-nlp\src\events\consumers.py:70:            model="gpt-4.1",
modules\rules-engine\tests\unit\test_tier1_completion_rules.py:251:    def test_unconfigured_mode_passes(self):
modules\rules-engine\tests\unit\test_tier1_completion_rules.py:259:            {"mode": "fixed_days", "fixed_days": 25},
modules\rules-engine\tests\unit\test_tier1_completion_rules.py:269:            "mode": "fixed_days", "fixed_days": 25,
modules\rules-engine\tests\unit\test_tier1_completion_rules.py:282:            "mode": "fixed_days", "fixed_days": 25,
modules\rules-engine\tests\unit\test_tier1_completion_rules.py:310:                "mode": "fixed_days", "fixed_days": 25,
modules\rules-engine\tests\unit\test_tier1_completion_rules.py:321:    def test_pct_of_prior_mode(self):
modules\rules-engine\tests\unit\test_tier1_completion_rules.py:341:                "mode": "pct_of_prior_days_supply",
modules\rules-engine\tests\unit\test_tier1_completion_rules.py:368:                "mode": "fixed_days", "fixed_days": 25,
modules\rules-engine\tests\unit\test_tier1_completion_rules.py:387:                "mode": "fixed_days", "fixed_days": 25,
modules\reclaimrx\src\reclaimrx\hierarchy\__init__.py:3:The reclaimrx anomaly model needs every detected anomaly tagged with
modules\payment-processing\src\_shim\db.py:6:contextvar. Payment-processing's own models do not yet inherit the mixin
modules\payment-processing\src\_shim\db.py:21:    """Declarative base shared by all payment-processing models."""
modules\rules-engine\tests\unit\test_rule_types.py:107:            {"mode": "fixed", "fixed_amount": "25.00"},
modules\payment-processing\src\jobs\scheduled.py:17:from ..models import Submission, VendorAdapter
modules\member-management\tests\unit\test_phi_encryption.py:1:"""RED tests for PHI encryption on Member model — 100% coverage required."""
modules\member-management\tests\unit\test_member_merge.py:28:    from src.models.tables import Member
modules\member-management\tests\unit\test_member_merge.py:40:    from src.models.tables import CoveragePeriod
modules\member-management\tests\unit\test_member_merge.py:51:    from src.models.tables import Accumulator
modules\member-management\tests\unit\test_member_merge.py:63:    from src.models.tables import CobRecord
modules\member-management\tests\unit\test_member_merge.py:92:        from src.models.tables import Member
modules\member-management\tests\unit\test_member_merge.py:264:# Member model needs merged_into_id field — test it exists
modules\member-management\tests\unit\test_member_merge.py:269:        from src.models.tables import Member
modules\member-management\tests\unit\test_member_events.py:216:        from src.models.tables import Accumulator, AccumulatorLedger, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_member_events.py:259:        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_member_events.py:300:        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_member_events.py:350:        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_member_events.py:388:        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_jobs.py:30:    from src.models.tables import Accumulator, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_jobs.py:71:        from src.models.tables import Accumulator
modules\member-management\tests\unit\test_jobs.py:87:        from src.models.tables import AccumulatorLedger
modules\member-management\tests\unit\test_jobs.py:103:        from src.models.tables import Accumulator
modules\member-management\tests\unit\test_jobs.py:119:        from src.models.tables import Accumulator
modules\member-management\tests\unit\test_jobs.py:141:        from src.models.tables import Member, CoveragePeriod
modules\member-management\tests\unit\test_jobs.py:167:        from src.models.tables import Member
modules\member-management\tests\unit\test_jobs.py:179:        from src.models.tables import Member
modules\member-management\tests\unit\test_jobs.py:200:        from src.models.tables import Member
modules\member-management\tests\unit\test_jobs.py:216:        from src.models.tables import Member
modules\payment-processing\alembic\versions\0002_rls_tenant_isolation.py:7:payment-processing's models declare ``Mapped[str] = mapped_column(String(36))``
modules\ncpdp-core\src\ncpdp_core\transactions\base.py:40:    Per PRD §5.7.2 the six archetypes split by (F1, AN). Layer 3 models
modules\payment-processing\alembic\versions\0002_rls_tenant_isolation (conflicted).py:7:payment-processing's models declare ``Mapped[str] = mapped_column(String(36))``
modules\ai-nlp\src\api\router.py:30:from src.models.tables import AiNlpDocumentResult, AiNlpPromptTemplate
modules\ai-nlp\src\api\router.py:102:            ).model_dump(),
modules\ai-nlp\src\api\router.py:208:        content=response_data.model_dump(),
modules\ai-nlp\src\api\router.py:269:        content=response_data.model_dump(),
modules\ai-nlp\src\api\router.py:498:            model="gpt-4.1",
modules\ai-nlp\src\api\router.py:531:        content=response_data.model_dump(),
modules\payment-processing\alembic\versions\0001_payment_processing_baseline.py:3:Creates all eight tables that map 1:1 to models in
modules\payment-processing\alembic\versions\0001_payment_processing_baseline.py:4:``src/models/tables.py``.  No prior migration exists for this module.
modules\payment-processing\alembic\versions\0001_payment_processing_baseline.py:18:matching the ORM model definitions.
modules\payment-processing\alembic\env.py:3:Imports Base metadata and all payment_proc ORM models so that
modules\payment-processing\alembic\env.py:25:# ── Import all ORM models so metadata is populated ────────────────────────
modules\payment-processing\alembic\env.py:27:from src.models.tables import (  # noqa: F401
modules\payment-processing\alembic\env.py:104:if context.is_offline_mode():
modules\ncpdp-core\src\ncpdp_core\transactions\b1_claim_billing_response_paid.py:18:model, F1 is optionally surfaced on AM21 (ResponseStatusSegment.header_response_status)
modules\member-management\tests\unit\test_accumulator_db.py:65:        from src.models.tables import Accumulator, AccumulatorLedger, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_accumulator_db.py:134:        from src.models.tables import Accumulator, AccumulatorLedger, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_accumulator_db.py:167:        from src.models.tables import Accumulator, AccumulatorLedger, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_accumulator_db.py:201:        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_accumulator_db.py:241:        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_accumulator_db.py:264:        from src.models.tables import Accumulator, AccumulatorLedger
modules\member-management\tests\unit\test_accumulator_db.py:277:        from src.models.tables import Accumulator, AccumulatorLedger
modules\member-management\tests\unit\test_accumulator_db.py:302:        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_accumulator_db.py:325:        from src.models.tables import AccumulatorLedger
modules\member-management\tests\unit\test_accumulator_db.py:355:        from src.models.tables import AccumulatorLedger
modules\member-management\tests\unit\test_accumulator_db.py:374:        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
modules\member-management\tests\unit\test_accumulator_db.py:396:        from src.models.tables import Accumulator, AccumulatorLedger
modules\member-management\tests\unit\test_accumulator_db.py:409:        from src.models.tables import Accumulator
modules\member-management\tests\unit\test_accumulator_db.py:419:        from src.models.tables import Accumulator
modules\member-management\tests\unit\test_accumulator_db.py:428:        from src.models.tables import AccumulatorLedger
modules\rules-engine\tests\integration\test_smoke_real_db.py:45:from src.models.tables import RuleInstance, RuleType  # noqa: E402
modules\prescriber-directory\tests\unit\test_state_prescribing_rules.py:47:        # Wave 3C: unmodeled (state, provider) pairs MUST default to the
modules\prescriber-directory\tests\unit\test_state_prescribing_rules.py:90:    def test_default_unmodeled_state_denies_controlled_substance(self, service):
modules\prescriber-directory\tests\unit\test_state_prescribing_rules.py:96:    def test_modeled_states_do_not_require_manual_review(self, service):
modules\prescriber-directory\tests\unit\test_state_prescribing_rules.py:97:        # Sanity: properly-modeled rules should NOT trigger manual review.
modules\payment-processing\src\services\submission_service.py:19:from ..models import Settlement, Submission
modules\prescriber-directory\tests\unit\test_nppes_upsert.py:9:from src.models.tables import DataRefreshLog, Prescriber
modules\payment-processing\src\api\schemas\payment.py:58:    model_config = ConfigDict(from_attributes=True)
modules\payment-processing\src\api\schemas\payment.py:81:    model_config = ConfigDict(from_attributes=True)
modules\payment-processing\src\api\schemas\payment.py:108:    model_config = ConfigDict(from_attributes=True)
modules\payment-processing\src\api\schemas\payment.py:134:    model_config = ConfigDict(from_attributes=True)
modules\payment-processing\src\api\schemas\payment.py:146:    model_config = ConfigDict(from_attributes=True)
modules\payment-processing\src\api\schemas\payment.py:158:    model_config = ConfigDict(from_attributes=True)
modules\ai-nlp\alembic\versions\0002_partition_hot_tables.py:91:            model_used              VARCHAR(100) NOT NULL,
modules\ai-nlp\alembic\versions\0002_partition_hot_tables.py:141:            model               VARCHAR(100) NOT NULL,
modules\ai-nlp\alembic\versions\0002_partition_hot_tables.py:205:        sa.Column("model_used", sa.String(100), nullable=False),
modules\ai-nlp\alembic\versions\0002_partition_hot_tables.py:235:        sa.Column("model", sa.String(100), nullable=False),
modules\payment-processing\src\api\router.py:15:from ..models import (
modules\payment-processing\src\api\router.py:59:@router.get("/vendors", response_model=list[VendorAdapterRead])
modules\payment-processing\src\api\router.py:70:    return [VendorAdapterRead.model_validate(r) for r in rows]
modules\payment-processing\src\api\router.py:73:@router.post("/vendors", response_model=VendorAdapterRead, status_code=status.HTTP_201_CREATED)
modules\payment-processing\src\api\router.py:106:    return VendorAdapterRead.model_validate(row)
modules\payment-processing\src\api\router.py:109:@router.put("/vendors/{vendor_id}", response_model=VendorAdapterRead)
modules\payment-processing\src\api\router.py:119:    for field, val in body.model_dump(exclude_none=True).items():
modules\payment-processing\src\api\router.py:126:    return VendorAdapterRead.model_validate(row)
modules\payment-processing\src\api\router.py:129:@router.get("/vendors/{vendor_id}/health", response_model=list[VendorHealthRead])
modules\payment-processing\src\api\router.py:141:    return [VendorHealthRead.model_validate(r) for r in rows]
modules\payment-processing\src\api\router.py:149:@router.get("/submissions", response_model=list[SubmissionRead])
modules\payment-processing\src\api\router.py:159:    return [SubmissionRead.model_validate(r) for r in rows]
modules\payment-processing\src\api\router.py:162:@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
modules\payment-processing\src\api\router.py:171:    return SubmissionRead.model_validate(row)
modules\payment-processing\src\api\router.py:174:@router.post("/submissions/{submission_id}/retry", response_model=SubmissionRead)
modules\payment-processing\src\api\router.py:197:    return SubmissionRead.model_validate(row)
modules\payment-processing\src\api\router.py:205:@router.get("/settlements", response_model=list[SettlementRead])
modules\payment-processing\src\api\router.py:215:    return [SettlementRead.model_validate(r) for r in rows]
modules\payment-processing\src\api\router.py:218:@router.get("/settlements/pending", response_model=list[SettlementRead])
modules\payment-processing\src\api\router.py:229:    return [SettlementRead.model_validate(r) for r in rows]
modules\payment-processing\src\api\router.py:232:@router.post("/settlements/{settlement_id}/manual", response_model=SettlementRead)
modules\payment-processing\src\api\router.py:249:    return SettlementRead.model_validate(row)
modules\payment-processing\src\api\router.py:257:@router.get("/returns", response_model=list[SettlementRead])
modules\payment-processing\src\api\router.py:268:    return [SettlementRead.model_validate(r) for r in rows]
modules\payment-processing\src\api\router.py:271:@router.post("/returns", response_model=SettlementRead, status_code=status.HTTP_201_CREATED)
modules\payment-processing\src\api\router.py:311:    return SettlementRead.model_validate(settle)
modules\payment-processing\src\api\router.py:314:@router.get("/returns/codes", response_model=list[AchReturnCodeRead])
modules\payment-processing\src\api\router.py:322:        return [AchReturnCodeRead.model_validate(r) for r in rows]
modules\payment-processing\src\api\router.py:343:@router.get("/enrollments", response_model=list[EnrollmentRead])
modules\payment-processing\src\api\router.py:351:    return [EnrollmentRead.model_validate(r) for r in rows]
modules\payment-processing\src\api\router.py:356:    response_model=EnrollmentRead,
modules\payment-processing\src\api\router.py:377:        return EnrollmentRead.model_validate(existing)
modules\payment-processing\src\api\router.py:388:    return EnrollmentRead.model_validate(row)
modules\payment-processing\src\api\router.py:391:@router.get("/enrollments/unenrolled", response_model=list[EnrollmentRead])
modules\payment-processing\src\api\router.py:402:    return [EnrollmentRead.model_validate(r) for r in rows]
modules\payment-processing\src\api\router.py:430:@router.get("/dashboard/reconciliation", response_model=list[ReconciliationRow])
modules\payment-processing\src\services\reconciliation_service.py:15:from ..models import Settlement, Submission
modules\reclaimrx\src\reclaimrx\detection\rules\refinement_ml\refinement_rules.py:129:            "mode_count": float(nq_dist.get("mode_count", 0)),
modules\reclaimrx\src\reclaimrx\detection\rules\refinement_ml\refinement_rules.py:132:            # cv = stddev / mean — low CV + high mode_count = clustering signal.
modules\reclaimrx\src\reclaimrx\detection\rules\refinement_ml\refinement_rules.py:138:                float(nq_dist.get("mode_count", 0))
modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:3:Creates the full ai-nlp schema declared in modules/ai-nlp/src/models/
modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:72:        sa.Column("model_used", sa.String(100), nullable=False),
modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:129:        sa.Column("primary_model_result", postgresql.JSONB(), nullable=True),
modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:130:        sa.Column("secondary_model_result", postgresql.JSONB(), nullable=True),
modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:198:            model_used  VARCHAR(100) NOT NULL,
modules\ai-nlp\alembic\versions\0001_ai_nlp_baseline.py:220:        sa.Column("model", sa.String(100), nullable=False),
modules\ai-nlp\alembic\env.py:35:# ── Import all ORM models so metadata is populated ────────────────────────
modules\ai-nlp\alembic\env.py:37:from src.models.tables import (  # noqa: F401
modules\ai-nlp\alembic\env.py:124:if context.is_offline_mode():
modules\payment-processing\src\services\ofac_screening.py:29:from src.models.tables import OfacScreeningAlert, OfacSdnEntry
modules\prescriber-directory\tests\unit\test_exclusion_columns.py:25:from src.models.tables import Prescriber, PrescriberBase
modules\payment-processing\src\services\health_service.py:16:from ..models import VendorAdapter, VendorHealthLog
modules\plan-design\src\api\schemas\network.py:45:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\network.py:55:    bagging_model: str | None = None
modules\plan-design\src\api\schemas\network.py:67:    @field_validator("latitude", "longitude", mode="before")
modules\plan-design\src\api\schemas\network.py:85:    bagging_model: str | None
modules\plan-design\src\api\schemas\network.py:98:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\network.py:112:    @field_validator("adequacy_pct", mode="before")
modules\plan-design\src\api\schemas\network.py:144:    model_config = {"from_attributes": True}
modules\member-management\tests\integration\test_eligibility_query_db.py:15:from src.models.tables import CobRecord, CoveragePeriod, Member
modules\member-management\tests\integration\test_crud_routes.py:20:from src.models.tables import CobRecord, CoveragePeriod, Group, Member
modules\rules-engine\src\services\rule_types.py:243:    # model-ready and synthetically tested. Layer 1/2 multi-
modules\rules-engine\src\services\rule_types.py:573:    ``GovernmentProgramBin`` ORM model to keep ``rule_types.py`` free of
modules\rules-engine\src\services\rule_types.py:727:    Raw SQL (text) is used rather than the Prescriber ORM model to
modules\rules-engine\src\services\rule_types.py:1145:    """Set patient_pay based on the configured copay mode.
modules\rules-engine\src\services\rule_types.py:1148:        mode: str — "fixed" | "first_fill_different" | "save_off_primary"
modules\rules-engine\src\services\rule_types.py:1149:        fixed_amount: str (Decimal) — used when mode=fixed
modules\rules-engine\src\services\rule_types.py:1150:        first_fill_amount: str (Decimal) — used when mode=first_fill_different
modules\rules-engine\src\services\rule_types.py:1153:        subsequent_fill_amount: str (Decimal) — used when mode=first_fill_different
modules\rules-engine\src\services\rule_types.py:1155:        save_amount: str (Decimal) — used when mode=save_off_primary;
modules\rules-engine\src\services\rule_types.py:1159:      - mode=save_off_primary but no upstream_claim or no
modules\rules-engine\src\services\rule_types.py:1162:      - mode=first_fill_different but is_first_fill_for_patient_drug
modules\rules-engine\src\services\rule_types.py:1164:      - Unknown mode or no mode configured → PASS.
modules\rules-engine\src\services\rule_types.py:1174:        mode = params.get("mode")
modules\rules-engine\src\services\rule_types.py:1175:        if not mode:
modules\rules-engine\src\services\rule_types.py:1178:                message="No target copay mode configured",
modules\rules-engine\src\services\rule_types.py:1183:        if mode == "fixed":
modules\rules-engine\src\services\rule_types.py:1188:                    message="mode=fixed but fixed_amount not set",
modules\rules-engine\src\services\rule_types.py:1194:        elif mode == "first_fill_different":
modules\rules-engine\src\services\rule_types.py:1201:                        "mode=first_fill_different but "
modules\rules-engine\src\services\rule_types.py:1220:        elif mode == "save_off_primary":
modules\rules-engine\src\services\rule_types.py:1230:                        "mode=save_off_primary but no upstream "
modules\rules-engine\src\services\rule_types.py:1246:                message=f"Unknown target copay mode: {mode!r}",
modules\rules-engine\src\services\rule_types.py:1252:            message=f"Target copay set: patient_pay={patient_pay} (mode={mode})",
modules\rules-engine\src\services\rule_types.py:1666:      mode: "fixed_days" | "pct_of_prior_days_supply"
modules\rules-engine\src\services\rule_types.py:1667:      fixed_days: int (mode=fixed_days) — min gap in days
modules\rules-engine\src\services\rule_types.py:1668:      pct_of_prior: Decimal (mode=pct_of_prior_days_supply) —
modules\rules-engine\src\services\rule_types.py:1683:        mode = params.get("mode")
modules\rules-engine\src\services\rule_types.py:1684:        if not mode:
modules\rules-engine\src\services\rule_types.py:1687:                message="No refill-too-soon mode configured",
modules\rules-engine\src\services\rule_types.py:1755:        if mode == "fixed_days":
modules\rules-engine\src\services\rule_types.py:1760:                    message="mode=fixed_days but fixed_days not set",
modules\rules-engine\src\services\rule_types.py:1763:        elif mode == "pct_of_prior_days_supply":
modules\rules-engine\src\services\rule_types.py:1769:                        "mode=pct_of_prior_days_supply but "
modules\rules-engine\src\services\rule_types.py:1783:                message=f"Unknown MinDaysBetweenFills mode: {mode!r}",
modules\rules-engine\src\services\rule_types.py:1931:      validation_mode: "strict" (default) | "flag_only"
modules\rules-engine\src\services\rule_types.py:1954:        mode = params.get("validation_mode", "strict")
modules\rules-engine\src\services\rule_types.py:1973:        if mode == "flag_only":
modules\rules-engine\src\services\rule_types.py:1999:      redirect_mode: "strict" (REJECT) | "advisory" (FLAG+PASS)
modules\rules-engine\src\services\rule_types.py:2011:      - Otherwise → REJECT or FLAG+PASS per redirect_mode, with
modules\rules-engine\src\services\rule_types.py:2083:        mode = params.get("redirect_mode", "strict")
modules\rules-engine\src\services\rule_types.py:2085:        if mode == "advisory":
modules\rules-engine\src\services\rule_types.py:2340:    + combined-list modes.
modules\rules-engine\src\services\rule_types.py:2357:      list_mode: "allowlist" (default) | "denylist" | "both"
modules\rules-engine\src\services\rule_types.py:2364:      validation_mode: "strict" (default) | "flag_only"
modules\rules-engine\src\services\rule_types.py:2372:      - list_mode evaluation per above
modules\rules-engine\src\services\rule_types.py:2381:        list_mode = params.get("list_mode", "allowlist")
modules\rules-engine\src\services\rule_types.py:2386:        # Backwards-compat: when list_mode defaults but only allowed
modules\rules-engine\src\services\rule_types.py:2388:        if list_mode == "allowlist" and not allowed:
modules\rules-engine\src\services\rule_types.py:2393:        if list_mode == "denylist" and not denylist:
modules\rules-engine\src\services\rule_types.py:2398:        if list_mode == "both" and not allowed and not denylist:
modules\rules-engine\src\services\rule_types.py:2401:                message="No OPRC lists configured (mode=both)",
modules\rules-engine\src\services\rule_types.py:2436:        # Denylist priority check (mode=denylist or mode=both): if any
modules\rules-engine\src\services\rule_types.py:2441:        if list_mode in ("denylist", "both"):
modules\rules-engine\src\services\rule_types.py:2444:                mode = params.get("validation_mode", "strict")
modules\rules-engine\src\services\rule_types.py:2451:                if mode == "flag_only":
modules\rules-engine\src\services\rule_types.py:2470:        # Allowlist evaluation (mode=allowlist or mode=both with no
modules\rules-engine\src\services\rule_types.py:2471:        # denylist hit). For mode=denylist alone, we already returned
modules\rules-engine\src\services\rule_types.py:2473:        if list_mode == "denylist":
modules\rules-engine\src\services\rule_types.py:2491:        mode = params.get("validation_mode", "strict")
modules\rules-engine\src\services\rule_types.py:2497:        if mode == "flag_only":
modules\prescriber-directory\tests\unit\test_event_consumer.py:9:from src.models.tables import Prescriber, PrescriberPharmacyRelationship
modules\rules-engine\src\services\rule_loader.py:36:# ``sys.path`` directly). Relative ``..models`` only resolves in the first
modules\rules-engine\src\services\rule_loader.py:39:    from ..models.tables import RuleInstance, RuleType
modules\rules-engine\src\services\rule_loader.py:41:    from models.tables import RuleInstance, RuleType  # type: ignore[no-redef]
modules\plan-design\src\api\schemas\market_access.py:23:    @field_validator("coverage_pct", "pa_required_pct", mode="before")
modules\plan-design\src\api\schemas\market_access.py:57:    @field_validator("commercial_pct", "medicare_pct", "medicaid_pct", "other_pct", mode="before")
modules\plan-design\src\api\schemas\market_access.py:71:    @field_validator("on_accumulator_plan_pct", "on_maximizer_plan_pct", mode="before")
modules\plan-design\src\api\schemas\market_access.py:102:        mode="before",
modules\plan-design\src\api\schemas\market_access.py:127:    model_config = {"from_attributes": True}
modules\payment-processing\src\models\__init__.py:1:"""Payment-processing ORM models."""
modules\member-management\tests\conftest.py:28:from src.models.tables import MemberMgmtBase
modules\member-management\tests\conftest.py:96:        join_transaction_mode="create_savepoint",
modules\plan-design\src\api\schemas\hierarchy.py:28:    model_config = {"populate_by_name": True}
modules\plan-design\src\api\schemas\hierarchy.py:42:    model_config = {"populate_by_name": True}
modules\plan-design\src\api\schemas\hierarchy.py:59:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\hierarchy.py:103:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\hierarchy.py:124:    @field_validator("coinsurance_pct", "annual_max_amount", "lifetime_max_amount", mode="before")
modules\plan-design\src\api\schemas\hierarchy.py:137:    pricing_model_id: UUID | None = None
modules\plan-design\src\api\schemas\hierarchy.py:153:        mode="before",
modules\plan-design\src\api\schemas\hierarchy.py:166:    pricing_model_id: UUID | None = None
modules\plan-design\src\api\schemas\hierarchy.py:183:        mode="before",
modules\plan-design\src\api\schemas\hierarchy.py:199:    pricing_model_id: UUID | None
modules\plan-design\src\api\schemas\hierarchy.py:216:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\hierarchy.py:276:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\hierarchy.py:308:    model_config = {"from_attributes": True}
modules\prescriber-directory\tests\unit\test_db_session.py:89:        from src.models.tables import PrescriberBase
modules\prescriber-directory\tests\unit\test_db_session.py:105:        from src.models.tables import PrescriberBase
modules\plan-design\src\api\schemas\formulary.py:46:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\formulary.py:69:    @field_validator("mfp_price", mode="before")
modules\plan-design\src\api\schemas\formulary.py:90:    @field_validator("mfp_price", mode="before")
modules\plan-design\src\api\schemas\formulary.py:122:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\formulary.py:134:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\formulary.py:150:    """Formulary change modeling request."""
modules\plan-design\src\api\schemas\formulary.py:165:    @field_validator("estimated_cost_delta", mode="before")
modules\plan-design\src\api\schemas\formulary.py:186:    model_config = {"from_attributes": True}
modules\plan-design\src\api\schemas\formulary.py:218:    model_config = {"from_attributes": True}
modules\prescriber-directory\tests\unit\test_credential_monitor.py:21:from src.models.tables import CredentialAlert, Prescriber, PrescriberBase
modules\rules-engine\src\models\tables.py:1:"""SQLAlchemy models for the rules-engine module.
modules\ncpdp-core\src\ncpdp_core\segments\am29_response_patient.py:9:Wave 32 M6b — entire field set re-modeled per IG spec. Prior
modules\ncpdp-core\src\ncpdp_core\segments\am27_response_insurance_additional_info.py:8:Wave 32 M3c — entire field set re-modeled per IG D.0 §27.2 / 5.317.
modules\plan-design\src\api\routes\network.py:37:@router.post("", response_model=NetworkResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\network.py:44:    network = svc.create_network(body.model_dump())
modules\plan-design\src\api\routes\network.py:49:@router.get("", response_model=list[NetworkResponse])
modules\plan-design\src\api\routes\network.py:59:@router.get("/{network_id}", response_model=NetworkResponse)
modules\plan-design\src\api\routes\network.py:72:@router.patch("/{network_id}", response_model=NetworkResponse)
modules\plan-design\src\api\routes\network.py:80:    network = svc.update_network(network_id, body.model_dump(exclude_none=True))
modules\plan-design\src\api\routes\network.py:92:@router.post("/{network_id}/pharmacies", response_model=NetworkPharmacyResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\network.py:100:    pharmacy = svc.add_pharmacy(network_id, body.model_dump())
modules\plan-design\src\api\routes\network.py:105:@router.get("/{network_id}/pharmacies", response_model=list[NetworkPharmacyResponse])
modules\plan-design\src\api\routes\network.py:135:@router.get("/{network_id}/adequacy", response_model=NetworkAdequacyResponse)
modules\plan-design\src\api\routes\network.py:150:@router.post("/{network_id}/awp-applications", response_model=AWPApplicationResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\network.py:158:    app = svc.submit_awp_application(network_id, body.model_dump())
modules\plan-design\src\api\routes\network.py:163:@router.get("/{network_id}/awp-applications", response_model=list[AWPApplicationResponse])
modules\plan-design\src\api\routes\network.py:174:@router.patch("/{network_id}/awp-applications/{app_id}", response_model=AWPApplicationResponse)
modules\plan-design\src\api\routes\network.py:183:    app = svc.update_awp_application(app_id, body.model_dump(exclude_none=True))
modules\ncpdp-core\src\ncpdp_core\segments\am26_response_prior_authorization.py:10:Wave 32 M6 — entire field set re-modeled per IG D.0 + DD. Prior
modules\plan-design\src\api\routes\market_access.py:33:@router.get("/coverage", response_model=CoverageLandscapeResponse)
modules\plan-design\src\api\routes\market_access.py:43:@router.get("/competitive", response_model=CompetitivePositioningResponse)
modules\plan-design\src\api\routes\market_access.py:53:@router.get("/pa-requirements", response_model=PAARequirementResponse)
modules\plan-design\src\api\routes\market_access.py:63:@router.get("/payer-mix", response_model=PayerMixResponse)
modules\plan-design\src\api\routes\market_access.py:73:@router.get("/accumulator-exposure", response_model=AccumulatorExposureResponse)
modules\plan-design\src\api\routes\market_access.py:83:@router.post("/plans/{plan_id}/what-if", response_model=WhatIfResponse)
modules\ncpdp-core\src\ncpdp_core\segments\am24_response_dur_pps.py:10:Wave 32 M6 — entire field set re-modeled per IG D.0 + DD. Prior
modules\plan-design\src\api\routes\hierarchy.py:49:@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\hierarchy.py:56:    org = svc.create_organization(body.model_dump(by_alias=False))
modules\plan-design\src\api\routes\hierarchy.py:61:@router.get("/organizations", response_model=list[OrganizationResponse])
modules\plan-design\src\api\routes\hierarchy.py:71:@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
modules\plan-design\src\api\routes\hierarchy.py:84:@router.patch("/organizations/{org_id}", response_model=OrganizationResponse)
modules\plan-design\src\api\routes\hierarchy.py:92:    org = svc.update_organization(org_id, body.model_dump(exclude_none=True, by_alias=False))
modules\plan-design\src\api\routes\hierarchy.py:104:@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\hierarchy.py:111:    group = svc.create_group(body.model_dump())
modules\plan-design\src\api\routes\hierarchy.py:116:@router.get("/groups", response_model=list[GroupResponse])
modules\plan-design\src\api\routes\hierarchy.py:127:@router.get("/groups/{group_id}", response_model=GroupResponse)
modules\plan-design\src\api\routes\hierarchy.py:140:@router.patch("/groups/{group_id}", response_model=GroupResponse)
modules\plan-design\src\api\routes\hierarchy.py:148:    group = svc.update_group(group_id, body.model_dump(exclude_none=True))
modules\plan-design\src\api\routes\hierarchy.py:160:@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\hierarchy.py:167:    plan = svc.create_plan(body.model_dump())
modules\plan-design\src\api\routes\hierarchy.py:172:@router.get("/plans", response_model=list[PlanResponse])
modules\plan-design\src\api\routes\hierarchy.py:183:@router.get("/plans/{plan_id}", response_model=PlanResponse)
modules\plan-design\src\api\routes\hierarchy.py:196:@router.patch("/plans/{plan_id}", response_model=PlanResponse)
modules\plan-design\src\api\routes\hierarchy.py:204:    plan = svc.update_plan(plan_id, body.model_dump(exclude_none=True))
modules\plan-design\src\api\routes\hierarchy.py:211:@router.get("/plans/{plan_id}/resolve", response_model=PlanResolveResponse)
modules\plan-design\src\api\routes\hierarchy.py:224:@router.post("/plans/{plan_id}/clone", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\hierarchy.py:246:@router.post("/plans/{plan_id}/promote", response_model=PlanResponse)
modules\plan-design\src\api\routes\hierarchy.py:261:@router.post("/plans/{plan_id}/rollback", response_model=PlanResponse)
modules\plan-design\src\api\routes\hierarchy.py:276:@router.post("/plans/bulk-import", response_model=BulkImportResponse)
modules\plan-design\src\api\routes\hierarchy.py:294:@router.post("/subgroups", response_model=SubGroupResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\hierarchy.py:301:    sg = svc.create_subgroup(body.model_dump())
modules\plan-design\src\api\routes\hierarchy.py:306:@router.get("/plans/{plan_id}/subgroups", response_model=list[SubGroupResponse])
modules\plan-design\src\api\routes\hierarchy.py:316:@router.patch("/subgroups/{sg_id}", response_model=SubGroupResponse)
modules\plan-design\src\api\routes\hierarchy.py:324:    sg = svc.update_subgroup(sg_id, body.model_dump(exclude_none=True))
modules\plan-design\src\api\routes\hierarchy.py:336:@router.post("/program-types", response_model=ProgramTypeResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\hierarchy.py:343:    pt = svc.create_program_type(body.model_dump())
modules\plan-design\src\api\routes\hierarchy.py:348:@router.get("/program-types", response_model=list[ProgramTypeResponse])
modules\prescriber-directory\tests\integration\test_validation_branches.py:19:from src.models.tables import CredentialAlert, Prescriber
modules\adjudication-engine\tests\unit\test_publisher_cob_fields.py:38:        pricing_model_used="wac",
modules\plan-design\src\api\routes\formulary.py:44:@router.post("", response_model=FormularyResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\formulary.py:51:    formulary = svc.create_formulary(body.model_dump())
modules\plan-design\src\api\routes\formulary.py:56:@router.get("", response_model=list[FormularyResponse])
modules\plan-design\src\api\routes\formulary.py:66:@router.get("/{formulary_id}", response_model=FormularyResponse)
modules\plan-design\src\api\routes\formulary.py:79:@router.patch("/{formulary_id}", response_model=FormularyResponse)
modules\plan-design\src\api\routes\formulary.py:87:    formulary = svc.update_formulary(formulary_id, body.model_dump(exclude_none=True))
modules\plan-design\src\api\routes\formulary.py:99:@router.post("/{formulary_id}/drugs", response_model=FormularyDrugResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\formulary.py:107:    drug = svc.add_drug(formulary_id, body.model_dump())
modules\plan-design\src\api\routes\formulary.py:112:@router.get("/{formulary_id}/drugs", response_model=list[FormularyDrugResponse])
modules\plan-design\src\api\routes\formulary.py:124:@router.patch("/{formulary_id}/drugs/{drug_id}", response_model=FormularyDrugResponse)
modules\plan-design\src\api\routes\formulary.py:133:    drug = svc.update_drug(drug_id, body.model_dump(exclude_none=True))
modules\plan-design\src\api\routes\formulary.py:140:@router.post("/{formulary_id}/drugs/import", response_model=DrugImportResponse)
modules\plan-design\src\api\routes\formulary.py:148:    drugs_data = [d.model_dump() for d in body.drugs]
modules\plan-design\src\api\routes\formulary.py:159:@router.get("/{formulary_id}/versions", response_model=list[FormularyVersionResponse])
modules\plan-design\src\api\routes\formulary.py:169:@router.post("/{formulary_id}/snapshot", response_model=FormularyVersionResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\formulary.py:193:@router.post("/{formulary_id}/publish-fb60", response_model=FBv60PublishResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\formulary.py:221:@router.post("/{formulary_id}/impact-analysis", response_model=FormularyImpactResponse)
modules\plan-design\src\api\routes\formulary.py:242:@router.get("/{formulary_id}/biosimilars/{reference_ndc}", response_model=list[FormularyDrugResponse])
modules\plan-design\src\api\routes\formulary.py:264:@pt_router.post("", response_model=PTMeetingResponse, status_code=status.HTTP_201_CREATED)
modules\plan-design\src\api\routes\formulary.py:271:    meeting = svc.create_pt_meeting(body.model_dump())
modules\plan-design\src\api\routes\formulary.py:276:@pt_router.get("/{meeting_id}", response_model=PTMeetingResponse)
modules\plan-design\src\api\routes\formulary.py:289:@pt_router.patch("/{meeting_id}", response_model=PTMeetingResponse)
modules\plan-design\src\api\routes\formulary.py:297:    meeting = svc.update_pt_meeting(meeting_id, body.model_dump(exclude_none=True))
modules\adjudication-engine\tests\unit\test_publishers.py:44:        pricing_model_used="awp_discount",
modules\adjudication-engine\tests\unit\test_publishers.py:68:        assert p["pricing_model_used"] == "awp_discount"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:279:    Two failure modes both yield silent-fallback to None:
modules\reclaimrx\src\reclaimrx\detection\providers\baseline.py:266:        """Extended NQ distribution statistics: mean, stddev, skew, kurtosis, mode_count."""
modules\reclaimrx\src\reclaimrx\detection\providers\baseline.py:786:        """Extended NQ distribution: mean/stddev + extra {skew, kurtosis, mode_count}."""
modules\reclaimrx\src\reclaimrx\detection\providers\baseline.py:795:                   COUNT(DISTINCT ROUND(ingredient_cost, 2)) AS mode_count
modules\reclaimrx\src\reclaimrx\detection\providers\baseline.py:821:                "mode_count": int(row.get("mode_count") or 0),
modules\prescriber-directory\tests\integration\test_api_extended.py:19:from src.models.tables import CredentialAlert, Prescriber
modules\prescriber-directory\tests\integration\test_api_extended.py:246:        from src.models.tables import PrescriberPharmacyRelationship
modules\prescriber-directory\tests\integration\test_api_extended.py:318:        from src.models.tables import DataRefreshLog
modules\ncpdp-core\src\ncpdp_core\segments\am22_response_claim.py:12:Wave 32 M6b — entire field set re-modeled per IG. Prior implementation
modules\ncpdp-core\src\ncpdp_core\segments\am22_response_claim.py:19:shape modeled; multi-occurrence expansion deferred to M7.
modules\prescriber-directory\tests\conftest.py:33:from src.models.tables import PrescriberBase
modules\prescriber-directory\tests\conftest.py:129:    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
modules\ncpdp-core\src\ncpdp_core\segments\am21_response_status.py:11:          In this Layer 2 schema, F1 is modeled as an Optional field on
modules\ncpdp-core\src\ncpdp_core\segments\am21_response_status.py:19:  segment. This schema models them as a tuple of up to 5 Optional[str]
modules\ncpdp-core\src\ncpdp_core\segments\am21_response_status.py:57:    status codes. Reject codes (up to 5) are modeled as individual
modules\ncpdp-core\src\ncpdp_core\segments\am20_response_message.py:10:response status segment ("AN" field). This Layer 2 schema models
modules\ncpdp-core\src\ncpdp_core\segments\am20_response_message.py:29:Earlier docstring + parse loop modeled numbered suffixes — that was
modules\adjudication-engine\tests\unit\test_listener_metrics_tls.py:150:        assert ctx.verify_mode == ssl.CERT_NONE
modules\adjudication-engine\tests\unit\test_listener_metrics_tls.py:169:        assert ctx.verify_mode == ssl.CERT_REQUIRED
modules\prescriber-directory\tests\integration\test_api_lookup.py:18:from src.models.tables import Prescriber
modules\ncpdp-core\src\ncpdp_core\segments\am15_facility.py:8:Wave 32 M3c — entire field set re-modeled per IG D.0 §27.1.2 + DD.
modules\ncpdp-core\src\ncpdp_core\segments\am14_additional_documentation.py:8:Wave 32 M3c — entire field set re-modeled per IG D.0 §27.1.2.
modules\adjudication-engine\tests\unit\test_adjudication.py:121:        "pricing_model": "awp_discount",
modules\adjudication-engine\tests\unit\test_adjudication.py:646:            "resolve_pricing_model",
modules\ncpdp-core\src\ncpdp_core\segments\am12_prior_authorization.py:9:Wave 32 M3b — entire segment re-modeled per IG D.0 §13.2.6.
modules\ncpdp-core\src\ncpdp_core\segments\am12_prior_authorization.py:11:The prior implementation modeled AM12 with AM07 Claim Segment field
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:86:        model_type: str = "xgboost",
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:132:                model_type=model_type,
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:162:        model_type: str,
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:168:        from sklearn.model_selection import train_test_split  # type: ignore[import-not-found]
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:209:        clf = _build_classifier(model_type, len(used_features))
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:217:            "model_type": model_type,
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:238:        model_file = artifact_dir / "model.joblib"
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:242:        joblib.dump(calibrated, model_file)
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:272:                  (detector_name, detector_version, model_artifact_path,
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:280:                    model_artifact_path = EXCLUDED.model_artifact_path,
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:376:def _build_classifier(model_type: str, n_features: int) -> Any:
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:378:    if model_type == "xgboost":
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:397:            model_type = "random_forest"
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:399:    if model_type in ("random_forest", "rf"):
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:411:        f"unknown model_type {model_type!r}; supported: 'xgboost', 'random_forest'"
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:421:    import argparse
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:426:    p = argparse.ArgumentParser(description="Train an ML detector")
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:431:    p.add_argument("--model-type", default="xgboost")
modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:452:            model_type=args.model_type,
modules\reclaimrx\src\events\consumers.py:23:from src.models.tables import (
modules\reclaimrx\src\events\consumers.py:154:                detection_mode=r.detection_mode,
modules\reclaimrx\src\events\consumers.py:372:            detection_mode="post_adjudication",
modules\reclaimrx\src\events\consumers.py:407:        detection_mode="post_adjudication",
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:38:      model.joblib   — the fitted pipeline/classifier
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:50:        model_artifact_path: str,
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:56:        self._artifact_path = Path(model_artifact_path)
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:60:        self._model: Any = None
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:88:        """True when the artifact directory exists and model.joblib is present."""
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:89:        model_file = self._artifact_path / "model.joblib"
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:90:        return model_file.exists()
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:92:    def model_metadata(self) -> dict[str, Any]:
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:98:        Loads the model lazily on first call; subsequent calls reuse the
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:99:        in-memory model. Raises MLDetectorNotTrainedError when not trained.
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:107:        model = self._get_model()
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:108:        return self._do_predict(model, features)
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:117:        model = self._get_model()
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:123:            raw_proba = model.predict_proba(X)[:, 1]
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:127:                contributions = _feature_contributions(model, row, self._feature_names)
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:132:                        model_version=self._version,
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:143:    def _get_model(self) -> Any:
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:144:        if self._loaded and self._model is not None:
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:145:            return self._model
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:150:            model_file = self._artifact_path / "model.joblib"
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:153:            self._model = joblib.load(model_file)
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:163:                f"Failed to load model artifact for {self._name!r} "
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:166:        return self._model
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:168:    def _do_predict(self, model: Any, features: dict[str, Any]) -> MLPrediction:
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:173:            prob = float(model.predict_proba(X)[0, 1])
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:175:            contributions = _feature_contributions(model, features, self._feature_names)
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:179:                model_version=self._version,
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:222:    def model_metadata(self) -> dict[str, Any]:
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:277:    model: Any,
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:281:    """Extract per-feature importance from model internals (best-effort).
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:283:    For tree models that expose feature_importances_, returns top-5 by
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:284:    importance × |feature_value|. Returns empty dict for models without
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:289:        estimator = model
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:290:        if hasattr(model, "calibrated_classifiers_"):
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:291:            estimator = model.calibrated_classifiers_[0].estimator
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:292:        elif hasattr(model, "named_steps"):
modules\reclaimrx\src\reclaimrx\detection\ml\sklearn_detector.py:294:            estimator = list(model.named_steps.values())[-1]
modules\reclaimrx\src\reclaimrx\detection\ml\registry.py:5:(when model_artifact_path is set) or a PlaceholderDetector.
modules\reclaimrx\src\reclaimrx\detection\ml\registry.py:66:                SELECT detector_name, detector_version, model_artifact_path,
modules\reclaimrx\src\reclaimrx\detection\ml\registry.py:76:            if row["is_placeholder"] or not row["model_artifact_path"]:
modules\reclaimrx\src\reclaimrx\detection\ml\registry.py:84:                    model_artifact_path=row["model_artifact_path"],
modules\reclaimrx\src\reclaimrx\detection\ml\registry.py:98:                SELECT detector_name, detector_version, model_artifact_path,
modules\reclaimrx\src\reclaimrx\detection\ml\registry.py:108:        if row["is_placeholder"] or not row["model_artifact_path"]:
modules\reclaimrx\src\reclaimrx\detection\ml\registry.py:116:                model_artifact_path=row["model_artifact_path"],
modules\reclaimrx\src\reclaimrx\detection\ml\registry.py:150:              (detector_name, detector_version, model_artifact_path,
modules\network-management\src\network_mgmt\models\__init__.py:1:from network_mgmt.models.tables import (
modules\reclaimrx\src\reclaimrx\detection\ml\protocol.py:31:    model_version is the version token from the registry row.
modules\reclaimrx\src\reclaimrx\detection\ml\protocol.py:36:    model_version: str = "0"
modules\reclaimrx\src\reclaimrx\detection\ml\protocol.py:63:        """Return True when the detector has a usable model artifact."""
modules\reclaimrx\src\reclaimrx\detection\ml\protocol.py:66:    def model_metadata(self) -> dict[str, Any]:
modules\network-management\src\network_mgmt\models\tables.py:1:"""SQLAlchemy ORM models for the network_mgmt schema.
modules\network-management\src\network_mgmt\models\tables.py:4:(this module models routing + identity, not amounts). Banking
modules\network-management\src\network_mgmt\models\tables.py:33:    """Declarative base for network_mgmt ORM models."""
modules\member-management\src\services\merge_service.py:13:from src.models.tables import (
modules\ncpdp-core\src\ncpdp_core\segments\am06_workers_comp.py:7:Wave 32 M3c — entire field set re-modeled per IG D.0 §27.1.2.
modules\rules-engine\src\api\schemas.py:34:    model_config = {"from_attributes": True}
modules\rules-engine\src\api\schemas.py:74:    model_config = {"from_attributes": True}
modules\rules-engine\src\api\schemas.py:98:    model_config = {"from_attributes": True}
modules\rules-engine\src\api\schemas.py:161:    model_config = {"from_attributes": True}
modules\rules-engine\src\api\routes.py:47:@router.post("/rule-types", response_model=RuleTypeResponse, status_code=status.HTTP_201_CREATED)
modules\rules-engine\src\api\routes.py:60:@router.get("/rule-types", response_model=list[RuleTypeResponse])
modules\rules-engine\src\api\routes.py:68:@router.get("/rule-types/{rule_type_id}", response_model=RuleTypeResponse)
modules\rules-engine\src\api\routes.py:79:@router.post("/rule-instances", response_model=RuleInstanceResponse, status_code=status.HTTP_201_CREATED)
modules\rules-engine\src\api\routes.py:100:@router.get("/rule-instances", response_model=list[RuleInstanceResponse])
modules\rules-engine\src\api\routes.py:110:@router.get("/rule-instances/{instance_id}", response_model=RuleInstanceResponse)
modules\rules-engine\src\api\routes.py:119:@router.put("/rule-instances/{instance_id}", response_model=RuleInstanceResponse)
modules\rules-engine\src\api\routes.py:143:@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
modules\rules-engine\src\api\routes.py:158:@router.get("/pipelines", response_model=list[PipelineResponse])
modules\rules-engine\src\api\routes.py:167:@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
modules\rules-engine\src\api\routes.py:176:@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse)
modules\rules-engine\src\api\routes.py:191:@router.post("/pipelines/{pipeline_id}/execute", response_model=PipelineExecuteResponse)
modules\rules-engine\src\api\routes.py:240:@router.get("/execution-logs", response_model=list[ExecutionLogResponse])
modules\member-management\src\services\eligibility_service.py:260:        from ..models.tables import CobRecord, CoveragePeriod, Member
modules\member-management\src\services\accumulator_db.py:18:from src.models.tables import Accumulator, AccumulatorLedger
modules\reclaimrx\src\api\schemas\schemas.py:27:    model_config = ConfigDict(strict=False)
modules\reclaimrx\src\api\schemas\schemas.py:50:    @field_validator("billed_amount", "paid_amount", mode="before")
modules\reclaimrx\src\api\schemas\schemas.py:81:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:90:    detection_mode: str
modules\reclaimrx\src\api\schemas\schemas.py:102:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:120:    detection_mode: str
modules\reclaimrx\src\api\schemas\schemas.py:154:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:202:    @field_validator("amount", mode="before")
modules\reclaimrx\src\api\schemas\schemas.py:211:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:236:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:262:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:296:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:312:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:330:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:344:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\schemas\schemas.py:357:    model_config = ConfigDict(from_attributes=True)
modules\reclaimrx\src\api\router.py:36:from src.models.tables import (
modules\reclaimrx\src\api\router.py:69:@router.post("/evaluate", response_model=ClaimEvaluateResponse)
modules\reclaimrx\src\api\router.py:79:    # Load active rules applicable to real-time mode
modules\reclaimrx\src\api\router.py:83:            DetectionRule.detection_mode.in_(["real_time", "both"]),
modules\reclaimrx\src\api\router.py:131:            detection_mode=rule.detection_mode,
modules\reclaimrx\src\api\router.py:156:                detection_mode="real_time",
modules\reclaimrx\src\api\router.py:199:@router.get("/rules", response_model=list[DetectionRuleRead])
modules\reclaimrx\src\api\router.py:210:@router.get("/rules/{rule_id}", response_model=DetectionRuleRead)
modules\reclaimrx\src\api\router.py:226:@router.get("/flags", response_model=PaginatedResponse[FlaggedClaimRead])
modules\reclaimrx\src\api\router.py:257:@router.get("/flags/{flag_id}", response_model=FlaggedClaimRead)
modules\reclaimrx\src\api\router.py:274:@router.put("/flags/{flag_id}", response_model=FlaggedClaimRead)
modules\reclaimrx\src\api\router.py:304:@router.get("/investigations", response_model=list[InvestigationRead])
modules\reclaimrx\src\api\router.py:323:@router.post("/investigations", response_model=InvestigationRead, status_code=201)
modules\reclaimrx\src\api\router.py:348:@router.get("/investigations/{investigation_id}", response_model=InvestigationRead)
modules\reclaimrx\src\api\router.py:361:@router.put("/investigations/{investigation_id}", response_model=InvestigationRead)
modules\reclaimrx\src\api\router.py:387:@router.get("/investigations/{investigation_id}/timeline", response_model=list[ActivityRead])
modules\reclaimrx\src\api\router.py:397:@router.post("/investigations/{investigation_id}/activity", response_model=ActivityRead, status_code=201)
modules\reclaimrx\src\api\router.py:419:@router.get("/recoveries", response_model=list[RecoveryRead])
modules\reclaimrx\src\api\router.py:431:@router.post("/recoveries", response_model=RecoveryRead, status_code=201)
modules\reclaimrx\src\api\router.py:454:@router.post("/holds", response_model=PaymentHoldRead, status_code=201)
modules\reclaimrx\src\api\router.py:477:@router.get("/holds", response_model=list[PaymentHoldRead])
modules\reclaimrx\src\api\router.py:492:@router.delete("/holds/{hold_id}", response_model=PaymentHoldRead)
modules\reclaimrx\src\api\router.py:515:@router.get("/pharmacy-profiles", response_model=list[PharmacyProfileRead])
modules\reclaimrx\src\api\router.py:536:@router.get("/pharmacy-profiles/{npi}", response_model=PharmacyProfileRead)
modules\reclaimrx\src\api\router.py:553:@router.get("/prescriber-profiles", response_model=list[PrescriberProfileRead])
modules\reclaimrx\src\api\router.py:571:@router.get("/member-profiles", response_model=list[MemberProfileRead])
modules\reclaimrx\src\api\router.py:591:@router.get("/accumulator/detections", response_model=list[AccumulatorDetectionRead])
modules\reclaimrx\src\api\router.py:611:@router.post("/tips", response_model=TipRead, status_code=201)
modules\reclaimrx\src\api\router.py:640:@router.get("/tips", response_model=list[TipRead])
modules\reclaimrx\src\models\__init__.py:1:"""ReclaimRx SQLAlchemy models."""
modules\reclaimrx\src\models\tables.py:1:"""ReclaimRx SQLAlchemy ORM models (reclaimrx schema).
modules\reclaimrx\src\models\tables.py:60:    detection_mode: Mapped[str] = mapped_column(String(50), nullable=False)
modules\reclaimrx\src\models\tables.py:151:    detection_mode: Mapped[str] = mapped_column(String(50), nullable=False)
modules\reclaimrx\src\models\tables.py:310:    __tablename__ = "reclaimrx_ml_models"
modules\reclaimrx\src\models\tables.py:315:    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
modules\reclaimrx\src\models\tables.py:316:    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
modules\reclaimrx\src\models\tables.py:336:    model_artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
modules\reclaimrx\src\models\tables.py:342:    predictions: Mapped[list[MlPrediction]] = relationship(back_populates="model", cascade="all, delete-orphan")
modules\reclaimrx\src\models\tables.py:349:    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("reclaimrx_ml_models.id"), nullable=False, index=True)
modules\reclaimrx\src\models\tables.py:365:    model: Mapped[MlModel] = relationship(back_populates="predictions")
modules\member-management\src\models\tables.py:1:"""SQLAlchemy ORM models for the member_mgmt schema.
modules\rules-engine\alembic\versions\0001_rules_engine_baseline.py:4:modules/rules-engine/src/models/tables.py.
modules\paysync\src\paysync\__main__.py:18:import argparse
modules\paysync\src\paysync\__main__.py:37:def _cmd_import(args: argparse.Namespace) -> int:
modules\paysync\src\paysync\__main__.py:72:    parser = argparse.ArgumentParser(prog="paysync")
modules\reclaimrx\src\jobs\scheduled.py:34:def job_retrain_ml_models(session: Any, tenant_id: str) -> dict[str, Any]:
modules\reclaimrx\src\jobs\scheduled.py:35:    """Monthly ML model retraining job.
modules\reclaimrx\src\jobs\scheduled.py:40:    _logger.info("reclaimrx.job.retrain_ml_models.start", extra={"tenant_id": tenant_id})
modules\reclaimrx\src\jobs\scheduled.py:41:    return {"models_retrained": 0}
modules\reclaimrx\src\jobs\scheduled.py:72:    from src.models.tables import PaymentHold  # type: ignore[import]
modules\reclaimrx\src\jobs\scheduled.py:117:    "retrain_ml_models": {"cron": "0 4 1 * *", "description": "Monthly ML model retraining"},
modules\rules-engine\alembic\env.py:38:# ── Import all ORM models so metadata is populated ────────────────────────
modules\rules-engine\alembic\env.py:39:from src.models.tables import (  # noqa: F401
modules\rules-engine\alembic\env.py:122:if context.is_offline_mode():
modules\network-management\alembic\env.py:22:from network_mgmt.models import (  # noqa: F401, E402
modules\network-management\alembic\env.py:97:if context.is_offline_mode():
modules\adjudication-engine\tests\integration\test_persistence.py:48:from src.models.tables import ClaimTransaction  # noqa: E402
modules\adjudication-engine\tests\integration\test_persistence.py:125:        pricing_model_used="awp_discount",
modules\prescriber-directory\src\services\state_prescribing_rules.py:3:Pre-loaded rules for represented states. Anything **not** explicitly modeled
modules\prescriber-directory\src\services\state_prescribing_rules.py:6:which silently authorized controlled-substance prescribing in ~40 unmodeled
modules\prescriber-directory\src\services\state_prescribing_rules.py:128:# authorized controlled-substance prescribing for the ~40 unmodeled states.
modules\prescriber-directory\src\services\state_prescribing_rules.py:140:        "State rules not yet modeled — default to restricted per DEA "
modules\prescriber-directory\src\services\state_prescribing_rules.py:160:        substance authority) when the (state, provider) pair is not modeled.
modules\prescriber-directory\src\services\state_prescribing_rules.py:172:        Returns False for any (state, provider) where no rule is modeled —
modules\prescriber-directory\src\services\state_prescribing_rules.py:187:        """True when the (state, provider) combination is not modeled.
modules\prescriber-directory\src\services\nppes_upsert.py:29:from src.models.tables import DataRefreshLog, Prescriber
modules\paysync\src\paysync\routing\nrid_router.py:13:    INFINITY + debit_card_amount > 0               → Klyre (model: IFX_PAID_CLAIMS sub-channel)
modules\member-management\src\jobs\dependent_aging.py:14:from src.models.tables import Member
modules\paysync\tests\integration\test_echo_sftp_delivery.py:93:    st_mode: int = stat.S_IFREG | 0o644
modules\prescriber-directory\src\services\nppes_ingestion.py:45:from ..models.nppes_tables import (
modules\paysync\tests\integration\test_echo_daily_candor.py:84:    st_mode: int = stat.S_IFREG | 0o644
modules\prescriber-directory\src\services\credential_monitor.py:16:from src.models.tables import CredentialAlert, Prescriber
modules\member-management\src\jobs\benefit_year_reset.py:17:from src.models.tables import Accumulator, CoveragePeriod
modules\adjudication-engine\tests\integration\test_tcp_listener_publish.py:118:        pricing_model_used="awp_discount",
modules\adjudication-engine\tests\integration\test_tcp_listener_publish.py:252:        pricing_model_used="awp_discount",
modules\adjudication-engine\tests\integration\test_listener_failure_modes.py:1:"""Wave 31 A2 — listener failure-mode coverage.
modules\adjudication-engine\tests\integration\test_listener_failure_modes.py:67:        pytest.skip("listener failure-mode tests need dev Postgres")
modules\adjudication-engine\tests\integration\test_listener_failure_modes.py:130:# Failure mode 1 — malformed wire bytes
modules\adjudication-engine\tests\integration\test_listener_failure_modes.py:166:# Failure mode 2 — oversized payload
modules\adjudication-engine\tests\integration\test_listener_failure_modes.py:197:# Failure mode 3 — idle connection times out
modules\adjudication-engine\tests\integration\test_listener_failure_modes.py:244:# Failure mode 4 — bin_routing miss without env override
modules\adjudication-engine\tests\integration\test_listener_failure_modes.py:278:# Failure mode 5 — internal error doesn't write partial claim row
modules\adjudication-engine\tests\integration\test_listener_failure_modes.py:336:# Failure mode 6 — listener accepts connection during shutdown gracefully
modules\reclaimrx\alembic\versions\0008_seed_ml_detector_placeholders.py:5:returning PlaceholderDetectors until real models are trained.
modules\reclaimrx\alembic\versions\0008_seed_ml_detector_placeholders.py:74:              (detector_name, detector_version, model_artifact_path,
modules\reclaimrx\alembic\versions\0008_seed_ml_detector_placeholders.py:93:               AND model_artifact_path IS NULL
modules\adjudication-engine\tests\integration\test_smoke_real_db.py:8:     the ORM models).
modules\adjudication-engine\tests\integration\test_smoke_real_db.py:48:from src.models.tables import (  # noqa: E402
modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:63:    "retrain_ml_models",
modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:87:    ORM model definition in reclaimrx/src/models/tables.py (PaymentHold at line 587).
modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:104:        # reclaimrx_payment_holds — DDL mirrors tables.py PaymentHold ORM model
modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:385:    def test_job_retrain_ml_models_wrapper_no_exception(
modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:388:        """job_retrain_ml_models runs inside per-tenant loop without exception."""
modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:389:        from jobs.scheduled import job_retrain_ml_models  # noqa: PLC0415
modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:392:        _run_tenant_scoped_job(job_retrain_ml_models, db_factory)
modules\paysync\src\paysync\echo\status_ingester.py:27:from paysync.models.tables import (
modules\adjudication-engine\tests\integration\test_reclaimrx_ml_api.py:110:    assert body["model_artifact_path"] is None
modules\reclaimrx\alembic\versions\0006_ml_detector_registry.py:49:        sa.Column("model_artifact_path", sa.Text(), nullable=True),
modules\prescriber-directory\src\models\tables.py:1:"""SQLAlchemy ORM models for the prescriber-directory module.
modules\prescriber-directory\src\models\tables.py:4:All models follow architecture rules:
modules\reclaimrx\alembic\versions\0006_ml_detector_registry [conflicted].py:51:        sa.Column("model_artifact_path", sa.Text(), nullable=True),
modules\paysync\src\paysync\echo\spec_400_generator.py:32:from paysync.models.tables import (
modules\reporting\tests\unit\test_services_coverage.py:15:from src.models.tables import ReportDefinition, ReportRun
modules\reporting\tests\unit\test_services_coverage.py:175:from src.models.tables import Dashboard, FilterPreset, UserDashboard
modules\reporting\tests\unit\test_services_coverage.py:299:from src.models.tables import RegulatorySubmission
modules\reporting\tests\unit\test_services_coverage.py:452:    async def test_list_models(self) -> None:
modules\reporting\tests\unit\test_services_coverage.py:453:        model = MagicMock()
modules\reporting\tests\unit\test_services_coverage.py:454:        db = _mock_db_with_row(model)
modules\reporting\tests\unit\test_services_coverage.py:456:        result = await svc.list_models("t1")
modules\reporting\tests\unit\test_services_coverage.py:460:    async def test_get_model_not_found(self) -> None:
modules\reporting\tests\unit\test_services_coverage.py:463:        result = await svc.get_model("missing", "t1")
modules\reporting\tests\unit\test_services_coverage.py:467:    async def test_run_scenario_model_not_found_raises(self) -> None:
modules\reporting\tests\unit\test_services_coverage.py:471:            await svc.run_scenario("missing_model", "t1", {})
modules\reporting\tests\unit\test_services_coverage.py:475:        model = MagicMock()
modules\reporting\tests\unit\test_services_coverage.py:476:        model.id = "m1"
modules\reporting\tests\unit\test_services_coverage.py:477:        model.tenant_id = "t1"
modules\reporting\tests\unit\test_services_coverage.py:478:        db = _mock_db_with_row(model)
modules\prescriber-directory\src\models\nppes_tables.py:14:The existing Prescriber model in tables.py is the canonical core record.
modules\prescriber-directory\src\models\nppes_tables.py:16:duplicating the core model.
modules\prescriber-directory\src\models\nppes_tables.py:107:    """Full NPPES V2 detail row — all fields not stored in the core Prescriber model.
modules\pharmacy-directory\tests\conftest.py:37:# Import models to register them on PharmacyBase.metadata before create_all
modules\pharmacy-directory\tests\conftest.py:38:from src.models.base import PharmacyBase
modules\pharmacy-directory\tests\conftest.py:39:from src.models.tables import (  # noqa: F401
modules\pharmacy-directory\tests\conftest.py:86:        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
modules\pharmacy-directory\tests\conftest.py:111:        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
modules\paysync\src\paysync\echo\sftp_delivery.py:27:from paysync.models.tables import EchoSpec400Run, ManualApRecord
modules\paysync\src\paysync\echo\sftp_delivery.py:239:            if stat.S_ISDIR(entry.st_mode):
modules\adjudication-engine\tests\integration\test_phase_c8_to_c11_pricing_e2e.py:160:                    "mode": "fixed",
modules\prescriber-directory\src\models\compliance_tables.py:36:    the ingester operates in validator-only mode and this table remains empty.
modules\paysync\src\paysync\echo\daily_candor.py:40:from paysync.models.tables import ManualApRecord
modules\reporting\tests\unit\test_phi_controls.py:219:        # member-management Member model
modules\reporting\tests\unit\test_phi_controls.py:232:        # medical-claims ClaimRecord model
modules\reporting\tests\unit\test_gap_coverage.py:97:        from src.models.tables import Dashboard
modules\paysync\src\paysync\cycle_close\__init__.py:4:  - cycle_schedules.py: cadence model + resolve_cycle_schedule
modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:400:        "redirect_mode": "strict",
modules\paysync\scripts\validation_run\generate_single_nacha.py:28:import argparse
modules\paysync\scripts\validation_run\generate_single_nacha.py:108:    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:124:        "mode": "fixed",
modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:138:        # Refill (disabled by no-mode lookup; individual tests enable)
modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:551:        "mode": "fixed_days",  # overrides the 'fixed' copay mode;
modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:552:        "fixed_amount": "25.00",  # keep copay mode usable for this test
modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:555:    # Wait — mode collides between TargetCopayRule and MinDaysBetweenFills.
modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:598:    # Need to set mode=fixed_days on the parameters
modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:603:            SET parameters = parameters || '{"mode": "fixed_days"}'::jsonb
modules\paysync\scripts\validation_run\generate_single_835.py:28:import argparse
modules\paysync\scripts\validation_run\generate_single_835.py:79:    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:123:                    "mode": "fixed",
modules\paysync\src\paysync\models\__init__.py:1:from paysync.models.tables import (
modules\paysync\src\paysync\models\tables.py:1:"""SQLAlchemy ORM models for the paysync module.
modules\paysync\src\paysync\models\tables.py:33:    """Declarative base for paysync ORM models."""
modules\reclaimrx\alembic\env.py:30:from reclaimrx.models import (  # noqa: F401, E402
modules\reclaimrx\alembic\env.py:109:if context.is_offline_mode():
modules\adjudication-engine\src\services\tcp_listener.py:8:Connection model: one request per connection (classic NCPDP pattern).
modules\adjudication-engine\src\services\tcp_listener.py:125:        ctx.verify_mode = ssl.CERT_REQUIRED
modules\adjudication-engine\src\services\tcp_listener.py:475:                "pricing_model": "awp_discount",
modules\member-management\src\api\schemas\member.py:158:    model_config = {"from_attributes": True}
modules\member-management\src\api\schemas\member.py:182:    model_config = {"from_attributes": True}
modules\adjudication-engine\src\services\tcp_listener (conflicted).py:8:Connection model: one request per connection (classic NCPDP pattern).
modules\adjudication-engine\src\services\tcp_listener (conflicted).py:128:        ctx.verify_mode = ssl.CERT_REQUIRED
modules\adjudication-engine\src\services\tcp_listener (conflicted).py:478:                "pricing_model": "awp_discount",
modules\adjudication-engine\src\services\tcp_listener (conflicted).py:535:                    pricing_model_used=result.pricing_model_used or "",
modules\prescriber-directory\src\events\consumer.py:41:    from src.models.tables import PrescriberPharmacyRelationship
modules\prescriber-directory\src\events\consumer.py:80:    from src.models.tables import Prescriber
modules\adjudication-engine\src\services\persistence.py:27:from src.models.tables import ClaimTransaction
modules\adjudication-engine\src\services\persistence.py:150:        pricing_model_used=result.pricing_model_used or None,
modules\adjudication-engine\src\services\parsed_claim.py:136:    single-payer modeling.
modules\adjudication-engine\src\services\ncpdp_validation.py:188:            # via vendor extension. Multi-payer claims model PCN
modules\adjudication-engine\src\services\ncpdp_validation.py:196:        # COBSegment models only the primary occurrence; multi-payer
modules\adjudication-engine\src\services\ncpdp_validation.py:200:        # decide when tertiary modeling is needed.
modules\adjudication-engine\src\services\ncpdp_validation.py:214:                        f"yet modeled by ncpdp-core; tracking via FLAG."
modules\member-management\src\api\routes\members.py:21:from src.models.tables import Member
modules\member-management\src\api\routes\groups.py:16:from src.models.tables import Group, Member
modules\member-management\src\api\routes\enrollment.py:23:from src.models.tables import EnrollmentFile
modules\paysync\src\paysync\invoicing\generator.py:274:        bill_to_id at the program level. PaySync's claim model
modules\pharmacy-directory\src\services\upsert.py:10:from src.models.tables import Pharmacy
modules\rebate-management\tests\unit\test_pass_through.py:31:    def query(self, model):
modules\rebate-management\tests\unit\test_pass_through.py:32:        return FakeQuery(self._flushed, model)
modules\rebate-management\tests\unit\test_pass_through.py:36:    def __init__(self, store, model):
modules\rebate-management\tests\unit\test_pass_through.py:38:        self._model = model
modules\member-management\src\api\routes\coverage.py:20:from src.models.tables import CoveragePeriod, Member
modules\reporting\tests\integration\test_smoke_real_db.py:13:  * The ORM model drifted from the DB schema.
modules\reporting\tests\integration\test_smoke_real_db.py:41:from src.models.tables import (  # noqa: E402
modules\pharmacy-directory\src\services\performance.py:15:from src.models.tables import PharmacyPerformanceSnapshot
modules\member-management\src\api\routes\cob.py:21:from src.models.tables import CobRecord, Member
modules\pharmacy-directory\src\services\network.py:16:from src.models.tables import Network, NetworkMembership, Pharmacy
modules\rebate-management\tests\unit\test_contracts.py:24:    def query(self, model):
modules\rebate-management\tests\unit\test_contracts.py:25:        return FakeContractQuery(self._store, model)
modules\rebate-management\tests\unit\test_contracts.py:29:    def __init__(self, store, model):
modules\rebate-management\tests\unit\test_contracts.py:31:        self._model = model
modules\reporting\tests\integration\test_api_routes.py:17:from src.models.tables import Dashboard, FilterPreset, ReportDefinition, ReportRun
modules\reporting\tests\integration\test_api_routes.py:463:        from src.models.tables import RegulatorySubmission
modules\reporting\tests\integration\test_api_routes.py:547:    def test_list_actuarial_models(self) -> None:
modules\reporting\tests\integration\test_api_routes.py:548:        from src.models.tables import ActuarialModel
modules\reporting\tests\integration\test_api_routes.py:550:        model = MagicMock(spec=ActuarialModel)
modules\reporting\tests\integration\test_api_routes.py:557:        resp = client.get("/api/v1/reporting/actuarial/models", headers=_headers())
modules\adjudication-engine\src\services\adjudication_pipeline.py:131:    pricing_model_used: str = ""
modules\adjudication-engine\src\services\adjudication_pipeline.py:331:def step_resolve_pricing_model(
modules\adjudication-engine\src\services\adjudication_pipeline.py:335:    """Step 4: Resolve pricing model from plan configuration.
modules\adjudication-engine\src\services\adjudication_pipeline.py:337:    Pricing models: AWP-discount, WAC-plus, MAC, U&C, lesser-of logic.
modules\adjudication-engine\src\services\adjudication_pipeline.py:339:    pricing_model = plan_data.get("pricing_model", "awp_discount")
modules\adjudication-engine\src\services\adjudication_pipeline.py:342:        step_name="resolve_pricing_model",
modules\adjudication-engine\src\services\adjudication_pipeline.py:344:        message=f"Pricing model: {pricing_model}",
modules\adjudication-engine\src\services\adjudication_pipeline.py:345:        data={"pricing_model": pricing_model},
modules\adjudication-engine\src\services\adjudication_pipeline.py:605:    pricing_model: str,
modules\adjudication-engine\src\services\adjudication_pipeline.py:610:    """Step 11: Calculate final pricing using resolved pricing model.
modules\adjudication-engine\src\services\adjudication_pipeline.py:612:    Applies the pricing model, incorporates rule modifications (copay,
modules\adjudication-engine\src\services\adjudication_pipeline.py:683:            "pricing_model": pricing_model,
modules\adjudication-engine\src\services\adjudication_pipeline.py:701:            f"Claim approved: {result.pricing_model_used} pricing applied"
modules\adjudication-engine\src\services\adjudication_pipeline.py:1013:    # Step 4: Resolve pricing model
modules\adjudication-engine\src\services\adjudication_pipeline.py:1015:    pricing_model_step = _run_step(step_resolve_pricing_model, plan_data, parsed)
modules\adjudication-engine\src\services\adjudication_pipeline.py:1016:    pricing_model = pricing_model_step.data.get("pricing_model", "awp_discount")
modules\adjudication-engine\src\services\adjudication_pipeline.py:1017:    result.pricing_model_used = pricing_model
modules\adjudication-engine\src\services\adjudication_pipeline.py:1143:        pricing_model,
modules\pharmacy-directory\src\services\lookup.py:13:from src.models.tables import Pharmacy
modules\adjudication-engine\src\scheduler.py:27:#   _RECLAIMRX_ROOT — for src._shim.db (Base) and src.models.tables (PaymentHold)
modules\adjudication-engine\src\scheduler.py:41:    job_retrain_ml_models,
modules\adjudication-engine\src\scheduler.py:56:    "retrain_ml_models",
modules\adjudication-engine\src\scheduler.py:64:    "retrain_ml_models": 3600,
modules\adjudication-engine\src\scheduler.py:157:        "retrain_ml_models": job_retrain_ml_models,
modules\pharmacy-directory\src\models\tables.py:1:"""ORM models for the pharmacy_dir schema.
modules\pharmacy-directory\src\models\tables.py:33:from src.models.base import PharmacyBase as Base
modules\pharmacy-directory\src\models\ncpdp_tables.py:1:"""ORM models for NCPDP DataQ v3.1 reference data — 13 tables.
modules\pharmacy-directory\src\models\base.py:24:    """ORM base for all pharmacy-directory models."""
modules\pharmacy-directory\src\services\credentialing.py:15:from src.models.tables import CredentialingApplication
modules\pharmacy-directory\src\api\router.py:31:from src.models.tables import (
modules\pharmacy-directory\src\api\router.py:120:@router.get("/lookup/{npi}", response_model=PharmacyResponse)
modules\pharmacy-directory\src\api\router.py:139:@router.get("/lookup/nabp/{nabp}", response_model=PharmacyResponse)
modules\pharmacy-directory\src\api\router.py:153:@router.get("/search", response_model=PharmacyListResponse)
modules\pharmacy-directory\src\api\router.py:165:@router.get("/nearby", response_model=PharmacyListResponse)
modules\pharmacy-directory\src\api\router.py:179:@router.post("/batch", response_model=dict)
modules\pharmacy-directory\src\api\router.py:195:@router.get("/networks", response_model=list[NetworkResponse])
modules\pharmacy-directory\src\api\router.py:206:@router.post("/networks", response_model=NetworkResponse, status_code=status.HTTP_201_CREATED)
modules\pharmacy-directory\src\api\router.py:296:@router.get("/networks/{network_id}/adequacy", response_model=AdequacyResponse)
modules\pharmacy-directory\src\api\router.py:313:@router.get("/credentialing", response_model=list[CredentialingApplicationResponse])
modules\pharmacy-directory\src\api\router.py:324:@router.post("/credentialing", response_model=CredentialingApplicationResponse, status_code=status.HTTP_201_CREATED)
modules\pharmacy-directory\src\api\router.py:348:@router.get("/credentialing/{application_id}", response_model=CredentialingApplicationResponse)
modules\pharmacy-directory\src\api\router.py:365:@router.post("/credentialing/{application_id}/approve", response_model=CredentialingApplicationResponse)
modules\pharmacy-directory\src\api\router.py:379:@router.post("/credentialing/{application_id}/deny", response_model=CredentialingApplicationResponse)
modules\pharmacy-directory\src\api\router.py:400:@router.get("/psaos", response_model=list[PsaoResponse])
modules\pharmacy-directory\src\api\router.py:407:@router.post("/psaos", response_model=PsaoResponse, status_code=status.HTTP_201_CREATED)
modules\pharmacy-directory\src\api\router.py:440:@router.get("/stats", response_model=DirectoryStatsResponse)
modules\adjudication-engine\src\models\__init__.py:1:"""ORM models for adjudication engine."""
modules\adjudication-engine\src\models\tables.py:1:"""SQLAlchemy ORM models for the adjudication_engine schema.
modules\adjudication-engine\src\models\tables.py:113:    pricing_model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
modules\prescriber-directory\src\api\schemas\prescriber.py:20:    model_config = ConfigDict(from_attributes=True)
modules\prescriber-directory\src\api\schemas\prescriber.py:76:    model_config = ConfigDict(from_attributes=True)
modules\prescriber-directory\src\api\schemas\prescriber.py:122:    model_config = ConfigDict(from_attributes=True)
modules\prescriber-directory\src\api\router.py:27:from src.models.tables import CredentialAlert, DataRefreshLog, Prescriber, PrescriberPharmacyRelationship
modules\prescriber-directory\src\api\router.py:58:@router.get("/lookup/{npi}", response_model=PrescriberResponse)
modules\prescriber-directory\src\api\router.py:71:@router.get("/lookup/dea/{dea_number}", response_model=PrescriberResponse)
modules\prescriber-directory\src\api\router.py:87:@router.get("/search", response_model=SearchResponse)
modules\prescriber-directory\src\api\router.py:125:@router.get("/batch", response_model=BatchLookupResponse)
modules\prescriber-directory\src\api\router.py:140:@router.get("/validate/{npi}", response_model=ValidationResponse)
modules\prescriber-directory\src\api\router.py:164:@router.get("/validate/{npi}/controlled/{schedule}", response_model=ControlledSubstanceAuthResponse)
modules\prescriber-directory\src\api\router.py:274:@router.get("/organizations", response_model=SearchResponse)
modules\prescriber-directory\src\api\router.py:297:@router.get("/organizations/{npi}", response_model=PrescriberResponse)
modules\prescriber-directory\src\api\router.py:318:@router.get("/monitoring/alerts", response_model=list[CredentialAlertResponse])
modules\prescriber-directory\src\api\router.py:355:@router.get("/stats", response_model=DirectoryStatsResponse)
modules\prescriber-directory\src\api\router.py:376:@router.get("/relationships/{npi}/pharmacies", response_model=list[PrescriberPharmacyRelationshipResponse])
modules\prescriber-directory\src\api\router.py:444:@router.post("/refresh", response_model=NpimportResultResponse, status_code=status.HTTP_202_ACCEPTED)
modules\reporting\src\utils\constants.py:94:# Actuarial model types
modules\medical-claims\tests\unit\test_unified_spend.py:10:from src.models.tables import ClaimRecord
modules\pharmacy-directory\tests\unit\test_exclusion_columns.py:23:from src.models.ncpdp_tables import NCPDPPharmacy
modules\medical-claims\tests\unit\test_service_extended.py:16:from src.models.tables import ClaimRecord
modules\adjudication-engine\src\events\publishers.py:38:    pricing_model_used: str,
modules\adjudication-engine\src\events\publishers.py:97:            "pricing_model_used": pricing_model_used,
modules\paysync\alembic\versions\0004_payment_batches.py:3:Adds the payment-side domain model on top of cycles + claims +
modules\medical-claims\tests\unit\test_phi_encryption.py:18:from src.models.tables import ClaimRecord
modules\medical-claims\tests\unit\test_phi_encryption.py:97:        # In SQLite test mode, LargeBinary may come back as base64 or bytes-like
modules\paysync\alembic\versions\0004_payment_batches (conflicted).py:3:Adds the payment-side domain model on top of cycles + claims +
modules\medical-claims\tests\unit\test_mapping_service.py:10:from src.models.tables import ClaimRecord
modules\reporting\src\services\report_service.py:11:from src.models.tables import ReportDefinition, ReportRun
modules\medical-claims\tests\unit\test_events.py:123:        from src.models.tables import UnifiedDrugSpend
modules\reporting\src\services\regulatory_service.py:11:from src.models.tables import RegulatorySubmission
modules\paysync\alembic\env.py:30:from paysync.models import (  # noqa: F401, E402
modules\paysync\alembic\env.py:107:if context.is_offline_mode():
modules\medical-claims\tests\unit\test_coverage_boost.py:26:from src.models.tables import ClaimRecord
modules\medical-claims\tests\unit\test_coverage_boost.py:985:        from src.models.tables import UnifiedDrugSpend
modules\pharmacy-directory\alembic\env.py:31:from src.models.base import PharmacyBase as Base  # noqa: E402
modules\pharmacy-directory\alembic\env.py:32:import src.models.tables  # noqa: E402, F401  — registers existing models
modules\pharmacy-directory\alembic\env.py:33:import src.models.ncpdp_tables  # noqa: E402, F401  — registers NCPDP models
modules\pharmacy-directory\alembic\env.py:105:if context.is_offline_mode():
modules\rebate-management\src\services\transparency.py:6:  - Spread pricing (should be zero in pass-through model)
modules\rebate-management\src\services\transparency.py:24:from src.models.tables import (
modules\rebate-management\src\services\transparency.py:161:        spread_pricing_amount = ZERO  # pass-through model: always zero
modules\rebate-management\src\services\spend_cap.py:15:from src.models.tables import SpendCapActual, SpendCapGuarantee
modules\reporting\src\services\dashboard_service.py:10:from src.models.tables import Dashboard, FilterPreset, UserDashboard
modules\rebate-management\src\services\pass_through.py:17:from src.models.tables import (
modules\reporting\src\services\actuarial_service.py:1:"""Actuarial modeling service: prospective cost, formulary impact, network savings, rebates."""
modules\reporting\src\services\actuarial_service.py:11:from src.models.tables import ActuarialModel
modules\reporting\src\services\actuarial_service.py:22:    async def list_models(self, tenant_id: str) -> list[ActuarialModel]:
modules\reporting\src\services\actuarial_service.py:31:    async def get_model(self, model_id: str, tenant_id: str) -> ActuarialModel | None:
modules\reporting\src\services\actuarial_service.py:33:            ActuarialModel.id == model_id,
modules\reporting\src\services\actuarial_service.py:80:        self, model_id: str, tenant_id: str, scenario_params: dict[str, Any]
modules\reporting\src\services\actuarial_service.py:82:        """Run a new scenario on an existing actuarial model."""
modules\reporting\src\services\actuarial_service.py:83:        model = await self.get_model(model_id, tenant_id)
modules\reporting\src\services\actuarial_service.py:84:        if model is None:
modules\reporting\src\services\actuarial_service.py:85:            raise ValueError(f"Model {model_id} not found")
modules\rebate-management\src\services\gtn_waterfall.py:21:from src.models.tables import GTNWaterfallSnapshot
modules\rebate-management\src\services\contracts.py:15:from src.models.tables import (
modules\rebate-management\src\api\schemas\pass_through.py:30:    model_config = ConfigDict(from_attributes=True)
modules\rebate-management\src\api\schemas\pass_through.py:43:    model_config = ConfigDict(from_attributes=True)
modules\pharmacy-directory\tests\integration\test_credentialing_service.py:11:from src.models.tables import CredentialingApplication, Network, Pharmacy
modules\adjudication-engine\src\api\schemas.py:16:    model_config = ConfigDict(strict=True)
modules\adjudication-engine\src\api\schemas.py:55:    model_config = ConfigDict(from_attributes=True)
modules\adjudication-engine\src\api\schemas.py:67:    pricing_model_used: str
modules\adjudication-engine\src\api\schemas.py:96:    model_config = ConfigDict(from_attributes=True)
modules\adjudication-engine\src\api\schemas.py:117:    pricing_model_used: str | None
modules\adjudication-engine\src\api\schemas.py:142:    model_config = ConfigDict(strict=True)
modules\rebate-management\src\api\schemas\contracts.py:58:    model_config = ConfigDict(from_attributes=True)
modules\rebate-management\src\services\compliance_dashboard.py:19:from src.models.tables import (
modules\rebate-management\src\services\compliance_dashboard.py:139:        spread_pricing_amount = ZERO  # always zero in pass-through model
modules\medical-claims\tests\unit\test_accumulator_service.py:11:from src.models.tables import ClaimRecord
modules\rebate-management\src\services\calculation.py:20:from src.models.tables import (
modules\adjudication-engine\src\api\routes.py:81:        pricing_model_used=result.pricing_model_used,
modules\adjudication-engine\src\api\routes.py:94:@router.post("/adjudicate", response_model=AdjudicationResponse)
modules\adjudication-engine\src\api\routes.py:156:@router.post("/reverse", response_model=AdjudicationResponse)
modules\adjudication-engine\src\api\routes.py:190:@router.get("/{claim_id}", response_model=ClaimDetailResponse)
modules\adjudication-engine\src\api\routes.py:215:@router.get("/{claim_id}/trace", response_model=ClaimTraceResponse)
modules\medical-claims\tests\unit\test_340b_detection.py:11:from src.models.tables import ClaimRecord
modules\rebate-management\src\api\schemas\bfsf.py:37:    model_config = ConfigDict(from_attributes=True)
modules\adjudication-engine\src\api\reclaimrx_routes.py:332:    response_model=RunOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:360:    response_model=RunOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:388:    response_model=RunOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:464:    response_model=PaginatedRunsOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:505:    response_model=RunOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:521:    response_model=PaginatedRowsOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:595:    response_model=PaginatedAnomaliesOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:656:    response_model=AnomalyOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:681:    response_model=AnomalyOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:724:    response_model=AnomalyOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:788:    response_model=AnomalyOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:845:    response_model=CaseOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:893:    response_model=PaginatedCasesOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:938:    response_model=CaseOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:954:    response_model=CaseOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:989:    response_model=CaseOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1028:    response_model=CaseOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1064:    response_model=CaseOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1107:    response_model=CaseOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1151:    response_model=CaseOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1197:    response_model=list[dict[str, Any]],
modules\adjudication-engine\src\api\reclaimrx_routes.py:1349:    response_model=list[RuleTypeOut],
modules\adjudication-engine\src\api\reclaimrx_routes.py:1387:    response_model=RuleTypeOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1473:    response_model=list[RuleInstanceOut],
modules\adjudication-engine\src\api\reclaimrx_routes.py:1504:    response_model=RuleInstanceOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1577:    response_model=RuleInstanceOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1702:    response_model=SeedDefaultsOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1909:    model_type: str = "xgboost"
modules\adjudication-engine\src\api\reclaimrx_routes.py:1947:    model_artifact_path: str | None
modules\adjudication-engine\src\api\reclaimrx_routes.py:1970:    response_model=TrainResponse,
modules\adjudication-engine\src\api\reclaimrx_routes.py:1997:            model_type=req.model_type,
modules\adjudication-engine\src\api\reclaimrx_routes.py:2016:    response_model=list[TrainingRunOut],
modules\adjudication-engine\src\api\reclaimrx_routes.py:2077:    response_model=TrainingRunOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:2126:    response_model=list[DetectorOut],
modules\adjudication-engine\src\api\reclaimrx_routes.py:2140:                       model_artifact_path, feature_schema_class,
modules\adjudication-engine\src\api\reclaimrx_routes.py:2152:            model_artifact_path=r["model_artifact_path"],
modules\adjudication-engine\src\api\reclaimrx_routes.py:2165:    response_model=DetectorOut,
modules\adjudication-engine\src\api\reclaimrx_routes.py:2179:                       model_artifact_path, feature_schema_class,
modules\adjudication-engine\src\api\reclaimrx_routes.py:2196:        model_artifact_path=row["model_artifact_path"],
modules\adjudication-engine\src\api\reclaimrx_routes.py:2207:    response_model=TestPredictResponse,
modules\reporting\src\models\__init__.py:1:"""Reporting module ORM models."""
modules\reporting\src\models\__init__.py:3:from src.models.tables import (
modules\rebate-management\src\services\bfsf.py:16:from src.models.tables import BFSFDocument, BFSFServiceCatalog
modules\adjudication-engine\src\api\paysync_invoicing_routes.py:231:    response_model=InvoiceSummaryOut,
modules\adjudication-engine\src\api\paysync_invoicing_routes.py:268:    response_model=InvoiceSummaryOut,
modules\adjudication-engine\src\api\paysync_invoicing_routes.py:305:    response_model=InvoiceSummaryOut,
modules\adjudication-engine\src\api\paysync_invoicing_routes.py:322:    response_model=InvoiceSummaryOut,
modules\adjudication-engine\src\api\paysync_invoicing_routes.py:351:    response_model=InvoiceSummaryOut,
modules\adjudication-engine\src\api\paysync_invoicing_routes.py:390:    response_model=InvoiceSummaryOut,
modules\adjudication-engine\src\api\paysync_invoicing_routes.py:463:    response_model=SaasantOut,
modules\adjudication-engine\src\api\paysync_invoicing_routes.py:547:    response_model=GlMappingOut,
modules\adjudication-engine\src\api\paysync_invoicing_routes.py:598:    response_model=list[GlMappingOut],
modules\reporting\src\models\tables.py:1:"""SQLAlchemy ORM models for the reporting schema.
modules\reporting\src\models\tables.py:4:All models are tenant-scoped; queries must always filter by tenant_id.
modules\reporting\src\models\tables.py:244:    __tablename__ = "actuarial_models"
modules\reporting\src\models\tables.py:251:    model_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
modules\adjudication-engine\src\api\paysync_close_routes.py:169:    response_model=CycleCloseOut,
modules\rebate-management\src\services\benchmarks.py:16:from src.models.tables import IndustryBenchmark, ProgramPerformanceMetric
modules\adjudication-engine\src\api\paysync_batch_routes.py:211:    response_model=AutoHoldOut,
modules\adjudication-engine\src\api\paysync_batch_routes.py:238:    response_model=BatchSummaryOut,
modules\adjudication-engine\src\api\paysync_batch_routes.py:279:    response_model=BatchListOut,
modules\adjudication-engine\src\api\paysync_batch_routes.py:311:    response_model=BatchSummaryOut,
modules\adjudication-engine\src\api\paysync_batch_routes.py:328:    response_model=BatchSummaryOut,
modules\adjudication-engine\src\api\paysync_batch_routes.py:378:    response_model=BatchSummaryOut,
modules\adjudication-engine\src\api\paysync_batch_routes.py:434:    response_model=GenerateNachaOut,
modules\adjudication-engine\src\api\paysync_batch_routes.py:482:    response_model=list[FiveFileOut],
modules\adjudication-engine\src\api\paysync_batch_routes.py:546:    response_model=list[HeldClaimOut],
modules\rebate-management\src\services\audit_export.py:22:from src.models.tables import (
modules\adjudication-engine\src\api\network_mgmt_routes.py:243:    response_model=PayToEntityOut,
modules\adjudication-engine\src\api\network_mgmt_routes.py:283:    response_model=PayToEntityOut,
modules\adjudication-engine\src\api\network_mgmt_routes.py:316:    response_model=BankingOut,
modules\adjudication-engine\src\api\network_mgmt_routes.py:369:    response_model=list[BankingOut],
modules\adjudication-engine\src\api\network_mgmt_routes.py:502:    response_model=TenantAchOriginationOut,
modules\adjudication-engine\src\api\network_mgmt_routes.py:569:    response_model=TenantAchOriginationOut | None,
modules\adjudication-engine\src\api\network_mgmt_routes.py:609:    response_model=list[DiscrepancyOut],
modules\program-config\tests\integration\test_smoke_real_db.py:42:from src.models.tables import Program, ProgramDrug  # noqa: E402
modules\adjudication-engine\src\api\maxacc_registry_routes.py:278:    response_model=list[SourceListOut],
modules\adjudication-engine\src\api\maxacc_registry_routes.py:308:    response_model=SourceListOut,
modules\adjudication-engine\src\api\maxacc_registry_routes.py:330:    response_model=SourceListOut,
modules\adjudication-engine\src\api\maxacc_registry_routes.py:382:    response_model=SourceListOut,
modules\adjudication-engine\src\api\maxacc_registry_routes.py:471:    response_model=NdcLookupOut,
modules\adjudication-engine\src\api\maxacc_registry_routes.py:506:    response_model=BinLookupOut,
modules\adjudication-engine\src\api\maxacc_registry_routes.py:564:    response_model=list[RunOut],
modules\adjudication-engine\src\api\maxacc_registry_routes.py:597:    response_model=RunOut,
modules\adjudication-engine\src\api\maxacc_registry_routes.py:620:    response_model=list[RunOut],
modules\adjudication-engine\src\api\maxacc_registry_routes.py:674:    response_model=RunOut,
modules\adjudication-engine\src\api\maxacc_registry_routes.py:744:    response_model=list[VendorPbmOut],
modules\adjudication-engine\src\api\maxacc_registry_routes.py:769:    response_model=VendorPbmOut,
modules\adjudication-engine\src\api\maxacc_registry_routes.py:825:    response_model=VendorPbmOut,
modules\adjudication-engine\src\api\maxacc_registry_routes.py:909:    response_model=list[VendorPbmOut],
modules\rebate-management\src\api\routes\calculations.py:27:@router.post("/run-period", response_model=CalculationResultResponse)
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:277:    response_model=list[SourceListOut],
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:307:    response_model=SourceListOut,
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:329:    response_model=SourceListOut,
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:381:    response_model=SourceListOut,
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:470:    response_model=NdcLookupOut,
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:505:    response_model=BinLookupOut,
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:563:    response_model=list[RunOut],
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:596:    response_model=RunOut,
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:619:    response_model=list[RunOut],
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:673:    response_model=RunOut,
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:743:    response_model=list[VendorPbmOut],
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:768:    response_model=VendorPbmOut,
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:824:    response_model=VendorPbmOut,
modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:908:    response_model=list[VendorPbmOut],
modules\adjudication-engine\src\api\health_scheduler.py:29:@router.get("/health/scheduler", response_model=SchedulerHealthResponse)
modules\rebate-management\src\models\__init__.py:1:"""Rebate Management ORM models."""
modules\reporting\src\jobs\scheduled.py:40:    from src.models.tables import ReportSchedule
modules\reporting\src\jobs\scheduled.py:158:    from src.models.tables import Dashboard, ReportDefinition
modules\adjudication-engine\src\api\config_routes.py:195:    response_model=SimulateChangeSetResponse,
modules\adjudication-engine\src\api\config_routes.py:293:    response_model=ApplyChangeSetResponse,
modules\rebate-management\src\api\routes\contracts.py:25:@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
modules\rebate-management\src\api\routes\contracts.py:73:@router.get("", response_model=list[ContractResponse])
modules\rebate-management\src\api\routes\contracts.py:83:@router.get("/{contract_id}", response_model=ContractResponse)
modules\rebate-management\src\api\routes\contracts.py:96:@router.post("/{contract_id}/transition", response_model=ContractResponse)
modules\rebate-management\src\api\routes\contracts.py:116:@router.post("/{contract_id}/amend", response_model=ContractResponse)
modules\program-config\src\services\program_service.py:19:from src.models.tables import (
modules\adjudication-engine\src\api\admin_routes.py:247:    response_model=InjectClaimResponse,
modules\adjudication-engine\src\api\admin_routes.py:353:            "pricing_model": "awp_discount",
modules\adjudication-engine\src\api\admin_routes.py:453:                pricing_model_used=result.pricing_model_used or "",
modules\rebate-management\src\models\tables.py:1:"""SQLAlchemy ORM models for the rebate-management module.
modules\rebate-management\src\models\tables.py:555:    )  # should be zero in pass-through model
modules\program-config\src\services\copay_recommender.py:108:    Designed as a class so a real ML model can replace ``recommend()``
modules\prior-authorization\tests\unit\test_pa_lifecycle.py:16:from src.models.tables import (
modules\prior-authorization\tests\unit\test_criteria_engine.py:13:from src.models.tables import PACriteriaSet, PARequest
modules\medical-claims\tests\conftest.py:37:from src.models.tables import MedicalClaimsBase
modules\medical-claims\tests\conftest.py:140:        join_transaction_mode="create_savepoint",
modules\reporting\alembic\env.py:35:# ── Import all ORM models so metadata is populated ────────────────────────
modules\reporting\alembic\env.py:37:from src.models.tables import (  # noqa: F401
modules\reporting\alembic\env.py:126:if context.is_offline_mode():
modules\prior-authorization\tests\conftest.py:59:from src.models.tables import PriorAuthBase
modules\prior-authorization\tests\conftest.py:112:        join_transaction_mode="create_savepoint",
modules\reporting\src\api\router.py:56:@router.get("/reports", response_model=list[ReportDefinitionRead])
modules\reporting\src\api\router.py:64:    return [ReportDefinitionRead.model_validate(d) for d in defns]
modules\reporting\src\api\router.py:67:@router.get("/reports/{report_id}", response_model=ReportDefinitionRead)
modules\reporting\src\api\router.py:77:    return ReportDefinitionRead.model_validate(defn)
modules\reporting\src\api\router.py:80:@router.post("/reports", response_model=ReportDefinitionRead, status_code=201)
modules\reporting\src\api\router.py:88:    defn = await svc.create_definition(tenant_id=tenant_id, data=body.model_dump())
modules\reporting\src\api\router.py:89:    return ReportDefinitionRead.model_validate(defn)
modules\reporting\src\api\router.py:92:@router.post("/reports/{report_id}/run", response_model=ReportRunRead, status_code=202)
modules\reporting\src\api\router.py:108:    return ReportRunRead.model_validate(run)
modules\reporting\src\api\router.py:111:@router.get("/reports/{report_id}/runs", response_model=list[ReportRunRead])
modules\reporting\src\api\router.py:119:    return [ReportRunRead.model_validate(r) for r in runs]
modules\reporting\src\api\router.py:122:@router.get("/reports/runs/{run_id}", response_model=ReportRunRead)
modules\reporting\src\api\router.py:132:    return ReportRunRead.model_validate(run)
modules\reporting\src\api\router.py:138:@router.get("/dashboards", response_model=list[DashboardRead])
modules\reporting\src\api\router.py:146:    return [DashboardRead.model_validate(d) for d in dashboards]
modules\reporting\src\api\router.py:149:@router.get("/dashboards/{dashboard_id}", response_model=DashboardRead)
modules\reporting\src\api\router.py:159:    return DashboardRead.model_validate(dashboard)
modules\reporting\src\api\router.py:162:@router.post("/dashboards", response_model=DashboardRead, status_code=201)
modules\reporting\src\api\router.py:170:    dashboard = await svc.create_dashboard(tenant_id=tenant_id, data=body.model_dump())
modules\reporting\src\api\router.py:171:    return DashboardRead.model_validate(dashboard)
modules\reporting\src\api\router.py:174:@router.put("/dashboards/{dashboard_id}", response_model=DashboardRead)
modules\reporting\src\api\router.py:184:        dashboard_id, tenant_id, body.model_dump(exclude_none=True)
modules\reporting\src\api\router.py:188:    return DashboardRead.model_validate(dashboard)
modules\reporting\src\api\router.py:213:@router.get("/my/filter-presets", response_model=list[FilterPresetRead])
modules\reporting\src\api\router.py:221:    return [FilterPresetRead.model_validate(p) for p in presets]
modules\reporting\src\api\router.py:224:@router.post("/my/filter-presets", response_model=FilterPresetRead, status_code=201)
modules\reporting\src\api\router.py:239:    return FilterPresetRead.model_validate(preset)
modules\reporting\src\api\router.py:372:    from src.models.tables import ReportRun
modules\reporting\src\api\router.py:415:    from src.models.tables import ReportDefinition, ReportRun
modules\reporting\src\api\router.py:469:    from src.models.tables import ReportDefinition
modules\reporting\src\api\router.py:509:    from src.models.tables import ReportDefinition, ReportRun
modules\reporting\src\api\router.py:559:@router.get("/regulatory", response_model=list[RegulatorySubmissionRead])
modules\reporting\src\api\router.py:565:    return [RegulatorySubmissionRead.model_validate(s) for s in subs]
modules\reporting\src\api\router.py:568:@router.post("/regulatory", response_model=RegulatorySubmissionRead, status_code=201)
modules\reporting\src\api\router.py:578:    sub = await svc.create_submission(tenant_id=tenant_id, data=body.model_dump())
modules\reporting\src\api\router.py:579:    return RegulatorySubmissionRead.model_validate(sub)
modules\reporting\src\api\router.py:582:@router.put("/regulatory/{submission_id}", response_model=RegulatorySubmissionRead)
modules\reporting\src\api\router.py:596:    return RegulatorySubmissionRead.model_validate(sub)
modules\reporting\src\api\router.py:611:@router.get("/actuarial/models", response_model=list[ActuarialModelRead])
modules\reporting\src\api\router.py:612:async def list_actuarial_models(tenant_id: TenantId, db: DB) -> list[ActuarialModelRead]:
modules\reporting\src\api\router.py:616:    models = await svc.list_models(tenant_id)
modules\reporting\src\api\router.py:617:    return [ActuarialModelRead.model_validate(m) for m in models]
modules\reporting\alembic\versions\0002_check_constraints.py:20:- actuarial_models.confidence_interval — Numeric(8,2), semantic
modules\program-config\src\models\tables.py:1:"""SQLAlchemy ORM models for the program_config schema.
modules\program-config\src\models\tables.py:461:# 340B, Mail, etc.) — NOT a hardcoded enum, so programs can model
modules\program-config\src\models\tables.py:476:    enum, so programs can model their own tier hierarchies.
modules\reporting\alembic\versions\0001_reporting_baseline.py:3:Creates the full reporting schema declared in modules/reporting/src/models/
modules\reporting\alembic\versions\0001_reporting_baseline.py:18:  8. actuarial_models       (no FK)
modules\reporting\alembic\versions\0001_reporting_baseline.py:253:    # ── 8. actuarial_models ──
modules\reporting\alembic\versions\0001_reporting_baseline.py:255:        "actuarial_models",
modules\reporting\alembic\versions\0001_reporting_baseline.py:259:        sa.Column("model_type", sa.String(100), nullable=False),
modules\reporting\alembic\versions\0001_reporting_baseline.py:271:        "ix_reporting_actuarial_models_tenant_id",
modules\reporting\alembic\versions\0001_reporting_baseline.py:272:        "actuarial_models", ["tenant_id"], schema=_SCHEMA,
modules\reporting\alembic\versions\0001_reporting_baseline.py:275:        "ix_reporting_actuarial_models_model_type",
modules\reporting\alembic\versions\0001_reporting_baseline.py:276:        "actuarial_models", ["model_type"], schema=_SCHEMA,
modules\reporting\alembic\versions\0001_reporting_baseline.py:336:    op.drop_table("actuarial_models", schema=_SCHEMA)
modules\adjudication-engine\alembic\versions\0001_adj_engine_baseline.py:4:modules/adjudication-engine/src/models/tables.py.
modules\adjudication-engine\alembic\versions\0001_adj_engine_baseline.py:63:        sa.Column("pricing_model_used", sa.String(50), nullable=True),
modules\adjudication-engine\alembic\env.py:37:# ── Import all ORM models so metadata is populated ────────────────────────
modules\adjudication-engine\alembic\env.py:38:from src.models.tables import (  # noqa: F401
modules\adjudication-engine\alembic\env.py:124:if context.is_offline_mode():
modules\reporting\src\api\schemas\dashboards.py:36:    model_config = {"from_attributes": True}
modules\reporting\src\api\schemas\dashboards.py:65:    model_config = {"from_attributes": True}
modules\reporting\src\api\schemas\regulatory.py:1:"""Pydantic schemas for regulatory submissions and actuarial models."""
modules\reporting\src\api\schemas\regulatory.py:52:    def model_post_init(self, __context: Any) -> None:
modules\reporting\src\api\schemas\regulatory.py:74:    model_config = {"from_attributes": True}
modules\reporting\src\api\schemas\regulatory.py:80:    def model_post_init(self, __context: Any) -> None:
modules\reporting\src\api\schemas\regulatory.py:87:    model_type: str
modules\reporting\src\api\schemas\regulatory.py:96:    model_type: str
modules\reporting\src\api\schemas\regulatory.py:104:    model_config = {"from_attributes": True}
modules\reporting\src\api\schemas\reports.py:8:from pydantic import BaseModel, Field, field_validator, model_validator
modules\reporting\src\api\schemas\reports.py:68:    model_config = {"from_attributes": True}
modules\reporting\src\api\schemas\reports.py:101:    model_config = {"from_attributes": True}
modules\reporting\src\api\schemas\reports.py:142:    @model_validator(mode="after")
modules\reporting\src\api\schemas\reports.py:169:    model_config = {"from_attributes": True}
modules\drug-database\src\services\fda_supplementary_ingestion.py:37:from src.models.fda_supplementary_tables import (
modules\prior-authorization\src\services\pa_lifecycle.py:21:from src.models.tables import (
modules\drug-database\src\services\drug_lookup.py:58:        from src.models.tables import DrugProduct
modules\prior-authorization\src\services\criteria_engine.py:17:from src.models.tables import PACriteriaSet, PARequest
modules\drug-database\alembic\versions\0008_fdb_pricing.py:8:                                         (modern RPRDPTD0 + legacy RNPTYPD0)
modules\drug-database\alembic\versions\0008_fdb_pricing.py:160:    # Unified price-type catalog (modern RPRDPTD0 + legacy RNPTYPD0).
modules\drug-database\alembic\versions\0008_fdb_pricing.py:175:            comment="Legacy 2-char join key. NULL for modern-only codes "
modules\drug-database\src\services\pricing_ingestion.py:37:from src.models.pricing_tables import (
modules\drug-database\src\services\pricing.py:17:from src.models.pricing_tables import DrugNADACPricingHistory
modules\prior-authorization\src\models\__init__.py:1:"""Prior Authorization ORM models."""
modules\prior-authorization\src\models\tables.py:1:"""SQLAlchemy ORM models for the prior_authorization schema.
modules\medical-claims\src\services\unified_spend_service.py:17:from src.models.tables import ClaimRecord, UnifiedDrugSpend
modules\medical-claims\src\services\pricing_service.py:16:from src.models.tables import AspPricing, ClaimRecord
modules\medical-claims\src\services\pricing_service.py:238:        return AspPricingResponse.model_validate(record)
modules\medical-claims\src\services\mapping_service.py:19:from src.models.tables import ClaimRecord, HcpcsNdcCrosswalk
modules\medical-claims\src\services\mapping_service.py:53:        matches = [CrosswalkResponse.model_validate(row) for row in q]
modules\drug-database\alembic\env.py:40:# Import drug_database NDC models to populate NDCBase.metadata
modules\drug-database\alembic\env.py:41:import drug_database.models.fdb_pricing_tables  # noqa: E402, F401
modules\drug-database\alembic\env.py:42:import drug_database.models.ndc_tables  # noqa: E402, F401
modules\drug-database\alembic\env.py:44:# Import FDB pricing models so FDBPricingBase.metadata is included in
modules\drug-database\alembic\env.py:49:from drug_database.models.fdb_pricing_tables import FDBPricingBase  # noqa: E402, F401
modules\drug-database\alembic\env.py:50:from drug_database.models.ndc_tables import NDCBase  # noqa: E402, F401
modules\drug-database\alembic\env.py:125:if context.is_offline_mode():
modules\medical-claims\src\services\detection_340b_service.py:18:from src.models.tables import ClaimRecord
modules\medical-claims\src\services\denial_service.py:12:from src.models.tables import ClaimRecord
modules\pharmacy-directory\src\jobs\credential_monitor.py:13:from src.models.tables import CredentialMonitoring, Pharmacy
modules\medical-claims\src\services\claim_service.py:12:from src.models.tables import ClaimRecord
modules\medical-claims\src\services\claim_service.py:183:        update_fields = data.model_dump(exclude_unset=True)
modules\pharmacy-directory\tests\integration\test_lookup.py:10:from src.models.tables import Pharmacy
modules\medical-claims\src\services\accumulator_service.py:17:from src.models.tables import ClaimRecord
modules\pharmacy-directory\tests\integration\test_cross_tenant_isolation.py:27:from src.models.tables import CredentialingApplication, Network, Pharmacy
modules\pharmacy-directory\tests\integration\test_credential_monitor_job.py:13:from src.models.tables import CredentialMonitoring, Pharmacy
modules\program-config\src\api\schemas\programs.py:60:    model_config = ConfigDict(from_attributes=True)
modules\program-config\src\api\schemas\programs.py:105:    @field_validator("copay_amount", "per_fill_cap", "annual_max", mode="before")
modules\program-config\src\api\schemas\programs.py:118:    model_config = ConfigDict(from_attributes=True)
modules\program-config\src\api\schemas\programs.py:153:    model_config = ConfigDict(from_attributes=True)
modules\program-config\src\api\schemas\programs.py:188:    model_config = ConfigDict(from_attributes=True)
modules\program-config\src\api\schemas\programs.py:241:    model_config = ConfigDict(from_attributes=True)
modules\program-config\src\api\schemas\programs.py:273:    model_config = ConfigDict(from_attributes=True)
modules\program-config\src\api\schemas\programs.py:312:    model_config = ConfigDict(from_attributes=True)
modules\pharmacy-directory\tests\integration\test_upsert.py:9:from src.models.tables import Pharmacy
modules\pharmacy-directory\tests\integration\test_performance_service.py:10:from src.models.tables import Pharmacy, PharmacyPerformanceSnapshot
modules\medical-claims\src\models\__init__.py:1:"""Medical Claims ORM models."""
modules\pharmacy-directory\tests\integration\test_router.py:27:from src.models.tables import Network, Pharmacy
modules\pharmacy-directory\tests\integration\test_network_service.py:12:from src.models.tables import Network, NetworkMembership, Pharmacy
modules\medical-claims\src\models\tables.py:1:"""SQLAlchemy ORM models for the medical_claims schema.
modules\medical-claims\src\models\tables.py:30:from shared.db.models.phi_mixin import PHIMixin
modules\pharmacy-directory\tests\integration\test_phi_encryption.py:18:from src.models.tables import Pharmacy, PharmacyPaymentInfo
modules\pharmacy-directory\tests\integration\test_phi_encryption.py:78:        from src.models.tables import PharmacyPaymentInfo as _PPI
modules\medical-claims\src\api\schemas\unified_spend.py:31:    model_config = {"from_attributes": True}
modules\drug-database\drug_database\services\drug_lookup.py:58:        from drug_database.models.tables import DrugProduct
modules\drug-database\drug_database\services\pricing_ingestion.py:37:from drug_database.models.pricing_tables import (
modules\medical-claims\src\api\schemas\denials.py:24:    model_config = {"from_attributes": True}
modules\program-config\src\api\routes\programs.py:33:from src.models.tables import Program, ProgramActivityLog, ProgramDrug
modules\program-config\src\api\routes\programs.py:65:@router.post("", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
modules\program-config\src\api\routes\programs.py:128:@router.get("", response_model=list[ProgramResponse])
modules\program-config\src\api\routes\programs.py:140:@router.get("/{program_id}", response_model=ProgramResponse)
modules\program-config\src\api\routes\programs.py:153:@router.patch("/{program_id}", response_model=ProgramResponse)
modules\program-config\src\api\routes\programs.py:165:    update_data = body.model_dump(exclude_none=True)
modules\program-config\src\api\routes\programs.py:186:@router.post("/{program_id}/status", response_model=ProgramResponse)
modules\program-config\src\api\routes\programs.py:235:@router.post("/{program_id}/drugs", response_model=ProgramDrugResponse, status_code=status.HTTP_201_CREATED)
modules\program-config\src\api\routes\programs.py:280:@router.get("/{program_id}/drugs", response_model=list[ProgramDrugResponse])
modules\medical-claims\src\api\schemas\crosswalk.py:25:    model_config = {"from_attributes": True}
modules\program-config\src\api\routes\brd.py:36:from src.models.tables import BrdSubmission, BrdTemplate, Program, ProgramActivityLog
modules\program-config\src\api\routes\brd.py:75:@router.post("/brd-templates", response_model=BrdTemplateResponse, status_code=status.HTTP_201_CREATED)
modules\program-config\src\api\routes\brd.py:107:@router.get("/brd-templates", response_model=list[BrdTemplateResponse])
modules\program-config\src\api\routes\brd.py:119:@router.get("/brd-templates/{template_id}", response_model=BrdTemplateResponse)
modules\program-config\src\api\routes\brd.py:134:@router.get("/brd-templates/defaults/{program_type}", response_model=dict[str, Any])
modules\program-config\src\api\routes\brd.py:154:@router.post("/brd-submissions", response_model=BrdSubmissionResponse, status_code=status.HTTP_201_CREATED)
modules\program-config\src\api\routes\brd.py:198:@router.get("/brd-submissions/{submission_id}", response_model=BrdSubmissionResponse)
modules\program-config\src\api\routes\brd.py:213:@router.post("/brd-submissions/{submission_id}/validate", response_model=BrdValidationResponse)
modules\program-config\src\api\routes\brd.py:239:@router.post("/brd-submissions/{submission_id}/review", response_model=BrdSubmissionResponse)
modules\program-config\src\api\routes\brd.py:292:@router.post("/brd-submissions/{submission_id}/sign", response_model=BrdSubmissionResponse)
modules\program-config\src\api\routes\brd.py:328:@router.get("/brd-submissions/{submission_id}/diff", response_model=BrdDiffResponse)
modules\program-config\src\api\routes\brd.py:357:        from src.models.tables import ProgramDrug
modules\program-config\src\api\routes\brd.py:375:@router.post("/brd-submissions/{submission_id}/apply", response_model=BrdSubmissionResponse)
modules\program-config\src\api\routes\brd.py:438:@router.post("/brd-submissions/{submission_id}/rollback", response_model=dict[str, str])
modules\drug-database\drug_database\services\pricing.py:17:from drug_database.models.pricing_tables import DrugNADACPricingHistory
modules\program-config\src\api\routes\onboarding.py:25:from src.models.tables import (
modules\program-config\src\api\routes\onboarding.py:53:@router.post("/{program_id}", response_model=OnboardingWorkflowResponse, status_code=status.HTTP_201_CREATED)
modules\program-config\src\api\routes\onboarding.py:104:@router.get("/dashboard", response_model=list[OnboardingDashboardEntry])
modules\program-config\src\api\routes\onboarding.py:144:@router.get("/{program_id}", response_model=OnboardingWorkflowResponse)
modules\program-config\src\api\routes\onboarding.py:162:@router.post("/{program_id}/steps", response_model=OnboardingWorkflowResponse)
modules\medical-claims\src\api\schemas\claims.py:190:    model_config = {"from_attributes": True}
modules\program-config\src\api\routes\manufacturer.py:28:from src.models.tables import ManufacturerProgramConfig, ProgramActivityLog
modules\program-config\src\api\routes\manufacturer.py:49:@router.post("", response_model=ManufacturerConfigResponse, status_code=status.HTTP_201_CREATED)
modules\program-config\src\api\routes\manufacturer.py:80:@router.get("", response_model=list[ManufacturerConfigResponse])
modules\program-config\src\api\routes\manufacturer.py:93:@router.get("/{config_id}", response_model=ManufacturerConfigResponse)
modules\program-config\src\api\routes\manufacturer.py:108:@router.patch("/{config_id}", response_model=ManufacturerConfigResponse)
modules\program-config\src\api\routes\manufacturer.py:128:    update_data = body.model_dump(exclude_none=True)
modules\program-config\src\api\routes\manufacturer.py:137:@router.post("/{config_id}/recommend-copay", response_model=CopayRecommendResponse)
modules\program-config\src\api\routes\manufacturer.py:201:@router.post("/{config_id}/submit-for-review", response_model=ManufacturerConfigResponse)
modules\program-config\src\api\routes\manufacturer.py:240:@router.post("/{config_id}/promote", response_model=ManufacturerConfigResponse)
modules\program-config\src\api\routes\contracts.py:26:from src.models.tables import Contract, ProgramActivityLog
modules\program-config\src\api\routes\contracts.py:49:@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
modules\program-config\src\api\routes\contracts.py:97:@router.get("", response_model=list[ContractResponse])
modules\program-config\src\api\routes\contracts.py:109:@router.get("/renewal-alerts", response_model=list[ContractResponse])
modules\program-config\src\api\routes\contracts.py:149:@router.get("/{contract_id}", response_model=ContractResponse)
modules\program-config\src\api\routes\contracts.py:162:@router.post("/{contract_id}/amendments", response_model=ContractResponse)
modules\medical-claims\src\api\schemas\asp.py:21:    model_config = {"from_attributes": True}
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:6:Three operating modes (SPEC §4.7):
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:8:  fdb_initial — one-time DB.zip baseline. ~15.6M RNP3 rows. Treats
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:10:  fdb_weekly  — routine UPD.zip application. ~10k-100k rows typical.
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:33:  * Loads RPRDPTD0_PRICE_TYPE_DESC (modern, 20 rows) into
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:64:from drug_database.models.fdb_pricing_tables import FDBNDCPriceHistory, FDBPriceTypeDesc
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:77:FDBIngestionMode = Literal["fdb_initial", "fdb_weekly", "fdb_rebase"]
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:82:    """Per-mode summary returned by FDBPricingIngester.run().
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:89:    mode: FDBIngestionMode
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:108:    # Batch size — kept modest to bound memory and surface failures
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:132:        mode: FDBIngestionMode,
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:135:        """Execute the ingestion for the given mode.
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:150:                "ingest_mode": mode,
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:159:            drop, mode=mode, dry_run=dry_run,
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:163:            mode=mode,
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:174:                "ingest_mode": mode,
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:184:    # price_type_desc — RPRDPTD0 (modern catalog)
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:198:          1. RPRDPTD0 (modern, 20 rows). PK = price_type_id; existing
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:212:        # --- step 1 — modern catalog (RPRDPTD0) ----------------------
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:306:        mode: FDBIngestionMode,
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:313:        # source-zip selection per mode:
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:314:        # - fdb_initial / fdb_rebase → DB.zip (full snapshot, all rows treated 'A')
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:315:        # - fdb_weekly              → UPD.zip (delta with A/C/D prefixes)
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:316:        if mode == "fdb_weekly":
modules\drug-database\drug_database\services\fdb_pricing.py:61:from drug_database.models.fdb_pricing_tables import FDBNDCPriceHistory
modules\prior-authorization\src\api\schemas.py:39:    @field_validator("approved_quantity", mode="before")
modules\prior-authorization\src\api\schemas.py:76:    @field_validator("first_fill_amount", mode="before")
modules\prior-authorization\src\api\schemas.py:110:    model_config = {"from_attributes": True}
modules\prior-authorization\src\api\schemas.py:125:    model_config = {"from_attributes": True}
modules\prior-authorization\src\api\schemas.py:127:    @field_validator("approved_quantity", mode="before")
modules\prior-authorization\src\api\schemas.py:147:    model_config = {"from_attributes": True}
modules\prior-authorization\src\api\schemas.py:169:    model_config = {"from_attributes": True}
modules\prior-authorization\src\api\schemas.py:171:    @field_validator("first_fill_amount", "manufacturer_absorbed_cost", mode="before")
modules\medical-claims\src\clients\pharmacy_directory_client.py:148:        return PharmacyLookupResult.model_validate(response.json())
modules\medical-claims\src\api\routes\unified_spend.py:34:@router.get("", response_model=UnifiedSpendListResponse)
modules\medical-claims\src\api\routes\unified_spend.py:59:            items=[UnifiedSpendResponse.model_validate(i) for i in items],
modules\medical-claims\src\api\routes\unified_spend.py:61:        ).model_dump(mode="json"),
modules\medical-claims\src\api\routes\unified_spend.py:66:@router.get("/member/{member_id}", response_model=UnifiedSpendListResponse)
modules\medical-claims\src\api\routes\unified_spend.py:77:            items=[UnifiedSpendResponse.model_validate(i) for i in items],
modules\medical-claims\src\api\routes\unified_spend.py:79:        ).model_dump(mode="json"),
modules\medical-claims\src\api\routes\unified_spend.py:84:@router.get("/duplications", response_model=list[DuplicationResponse])
modules\medical-claims\src\api\routes\unified_spend.py:100:                pharmacy_record=UnifiedSpendResponse.model_validate(d["pharmacy_record"]),
modules\medical-claims\src\api\routes\unified_spend.py:101:                medical_record=UnifiedSpendResponse.model_validate(d["medical_record"]),
modules\medical-claims\src\api\routes\unified_spend.py:105:        content=[r.model_dump(mode="json") for r in result],
modules\medical-claims\src\clients\member_management_client.py:149:        return EligibilityResult.model_validate(response.json())
modules\drug-database\drug_database\services\fda_supplementary_ingestion.py:37:from drug_database.models.fda_supplementary_tables import (
modules\medical-claims\src\api\routes\denials.py:34:@router.get("", response_model=list[DenialResponse])
modules\medical-claims\src\api\routes\denials.py:56:        content=[DenialResponse.model_validate(c).model_dump(mode="json") for c in items],
modules\drug-database\drug_database\models\tables.py:1:"""SQLAlchemy models for the drug-database module.
modules\medical-claims\src\clients\drug_database_client.py:168:        return DrugLookupResult.model_validate(response.json())
modules\medical-claims\src\clients\drug_database_client.py:232:        return [DrugPricingResult.model_validate(item) for item in data]
modules\medical-claims\src\api\routes\crosswalk.py:35:@router.get("/unmapped", response_model=list[dict])
modules\medical-claims\src\api\routes\crosswalk.py:53:@router.get("/{hcpcs_code}", response_model=CrosswalkLookupResponse)
modules\medical-claims\src\api\routes\crosswalk.py:65:@router.post("/claims/{claim_id}/drug-mapping", response_model=dict)
modules\medical-claims\src\api\routes\crosswalk.py:76:        return JSONResponse(status_code=400, content=err.model_dump())
modules\medical-claims\src\api\routes\crosswalk.py:84:        return JSONResponse(status_code=404, content=err.model_dump())
modules\drug-database\drug_database\models\rxnorm_tables.py:1:"""RxNorm ORM models for the drug-database module.
modules\prior-authorization\src\api\routes\decisions.py:41:    response_model=PADecisionResponse,
modules\prior-authorization\src\api\routes\decisions.py:63:        return PADecisionResponse.model_validate(decision)
modules\prior-authorization\src\api\routes\decisions.py:73:    response_model=PAAppealResponse,
modules\prior-authorization\src\api\routes\decisions.py:93:        return PAAppealResponse.model_validate(appeal)
modules\medical-claims\src\api\routes\claims_appeal.py:35:@router.post("/{claim_id}/appeal", response_model=ClaimResponse)
modules\medical-claims\src\api\routes\claims_appeal.py:53:        return JSONResponse(status_code=422, content=err.model_dump())
modules\medical-claims\src\api\routes\claims_appeal.py:57:        return JSONResponse(status_code=404, content=err.model_dump())
modules\medical-claims\src\api\routes\claims_appeal.py:60:        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
modules\drug-database\drug_database\models\pricing_tables.py:1:"""CMS NADAC and ASP pricing ORM models for the drug-database module.
modules\medical-claims\src\api\routes\claims.py:48:@router.get("", response_model=ClaimListResponse)
modules\medical-claims\src\api\routes\claims.py:78:        items=[ClaimResponse.model_validate(c) for c in items],
modules\medical-claims\src\api\routes\claims.py:85:@router.post("", response_model=ClaimResponse, status_code=201)
modules\medical-claims\src\api\routes\claims.py:95:        return JSONResponse(status_code=422, content=err.model_dump())
modules\medical-claims\src\api\routes\claims.py:99:        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
modules\medical-claims\src\api\routes\claims.py:104:@router.get("/{claim_id}", response_model=ClaimResponse)
modules\medical-claims\src\api\routes\claims.py:113:        return JSONResponse(status_code=404, content=err.model_dump())
modules\medical-claims\src\api\routes\claims.py:116:        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
modules\medical-claims\src\api\routes\claims.py:121:@router.put("/{claim_id}", response_model=ClaimResponse)
modules\medical-claims\src\api\routes\claims.py:130:        return JSONResponse(status_code=404, content=err.model_dump())
modules\medical-claims\src\api\routes\claims.py:133:        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
modules\medical-claims\src\api\routes\claims.py:138:@router.post("/{claim_id}/status", response_model=ClaimResponse)
modules\medical-claims\src\api\routes\claims.py:156:        return JSONResponse(status_code=422, content=err.model_dump())
modules\medical-claims\src\api\routes\claims.py:160:        return JSONResponse(status_code=404, content=err.model_dump())
modules\medical-claims\src\api\routes\claims.py:163:        content=ClaimResponse.model_validate(claim).model_dump(mode="json"),
modules\medical-claims\src\api\routes\claims.py:168:@router.post("/upload", response_model=FileUploadResponse)
modules\drug-database\drug_database\models\fdb_pricing_tables.py:1:"""FDB pricing ORM models — mirror of alembic migration 0008_fdb_pricing.
modules\drug-database\drug_database\models\fdb_pricing_tables.py:11:                                         (modern RPRDPTD0 + legacy RNPTYPD0).
modules\drug-database\drug_database\models\fdb_pricing_tables.py:22:the code under test calls ``db.commit()``. See ``test_fdb_pricing_models.py``
modules\drug-database\drug_database\models\fdb_pricing_tables.py:194:    """Unified FDB price-type catalog (modern RPRDPTD0 + legacy RNPTYPD0).
modules\drug-database\drug_database\models\fdb_pricing_tables.py:196:    Resolves the modern numeric ``price_type_id`` and the legacy 2-char
modules\drug-database\drug_database\models\fdb_pricing_tables.py:225:            "Legacy 2-char join key. NULL for modern-only codes "
modules\drug-database\drug_database\models\orange_book_tables.py:1:"""FDA Orange Book ORM models for the drug-database module.
modules\medical-claims\src\api\routes\asp.py:23:@router.get("/current-quarter", response_model=dict)
modules\medical-claims\src\api\routes\asp.py:26:    from src.models.tables import AspPricing
modules\medical-claims\src\api\routes\asp.py:35:@router.get("/{hcpcs_code}", response_model=AspPricingResponse)
modules\medical-claims\src\api\routes\asp.py:50:        return JSONResponse(status_code=404, content=err.model_dump())
modules\medical-claims\src\api\routes\asp.py:51:    return JSONResponse(content=record.model_dump(mode="json"))
modules\medical-claims\src\api\routes\asp.py:54:@router.post("/refresh", response_model=AspRefreshResponse)
modules\medical-claims\src\api\routes\asp.py:67:        return JSONResponse(status_code=400, content=err.model_dump())
modules\medical-claims\src\api\routes\asp.py:75:        ).model_dump(mode="json")
modules\prior-authorization\src\api\routes\pa_requests.py:48:    response_model=PAResponse,
modules\prior-authorization\src\api\routes\pa_requests.py:50:    responses={409: {"model": ErrorResponse}},
modules\prior-authorization\src\api\routes\pa_requests.py:75:        return PAResponse.model_validate(pa)
modules\prior-authorization\src\api\routes\pa_requests.py:85:    response_model=CriteriaResultResponse,
modules\prior-authorization\src\api\routes\pa_requests.py:120:    response_model=PAStatusResponse,
modules\prior-authorization\src\api\routes\pa_requests.py:137:    response_model=CopayEPAResponse,
modules\prior-authorization\src\api\routes\pa_requests.py:157:        return CopayEPAResponse.model_validate(record)
modules\medical-claims\src\api\routes\analytics.py:37:@router.get("/340b/claims", response_model=list[ClaimResponse])
modules\medical-claims\src\api\routes\analytics.py:50:            "items": [ClaimResponse.model_validate(c).model_dump(mode="json") for c in items],
modules\medical-claims\src\api\routes\analytics.py:64:    from src.models.tables import ClaimRecord
modules\medical-claims\src\api\routes\analytics.py:93:    from src.models.tables import ClaimRecord
modules\medical-claims\src\api\routes\analytics.py:137:    from src.models.tables import ClaimRecord
modules\medical-claims\src\api\routes\analytics.py:172:    from src.models.tables import ClaimRecord
modules\medical-claims\src\api\routes\analytics.py:207:    from src.models.tables import ClaimRecord
modules\drug-database\drug_database\models\ndc_tables.py:1:"""FDA NDC Directory ORM models for the drug-database module.
modules\drug-database\drug_database\models\ndc_tables.py:4:DrugProduct/DrugPricing models in tables.py).
modules\drug-database\drug_database\models\fda_supplementary_tables.py:1:"""FDA supplementary ORM models: REMS, Drug Shortages, Purple Book.
modules\drug-database\src\models\fda_supplementary_tables.py:1:"""FDA supplementary ORM models: REMS, Drug Shortages, Purple Book.
modules\program-config\alembic\versions\0001_program_config_baseline.py:4:modules/program-config/src/models/tables.py.
modules\program-config\alembic\env.py:31:from src.models.tables import (  # noqa: F401
modules\program-config\alembic\env.py:106:if context.is_offline_mode():
modules\drug-database\drug_database\api\router.py:24:from drug_database.models.tables import (
modules\drug-database\drug_database\api\router.py:53:@router.get("/lookup/batch", response_model=list[DrugProductResponse])
modules\drug-database\drug_database\api\router.py:71:@router.get("/lookup/{ndc}", response_model=DrugProductResponse)
modules\drug-database\drug_database\api\router.py:84:@router.get("/search", response_model=DrugSearchResponse)
modules\drug-database\drug_database\api\router.py:122:@router.get("/pricing/{ndc}", response_model=list[PricingResponse])
modules\drug-database\drug_database\api\router.py:155:@router.get("/pricing/{ndc}/history", response_model=list[PricingHistoryResponse])
modules\drug-database\drug_database\api\router.py:177:@router.get("/interactions", response_model=list[InteractionResponse])
modules\drug-database\drug_database\api\router.py:214:@router.get("/equivalents/{ndc}", response_model=list[TherapeuticEquivalenceResponse])
modules\drug-database\drug_database\api\router.py:239:@router.get("/overrides", response_model=list[TenantOverrideResponse])
modules\drug-database\drug_database\api\router.py:248:@router.post("/overrides/upload", response_model=MACUploadResponse)
modules\drug-database\drug_database\api\router.py:307:@router.get("/rems/{ndc}", response_model=list[RemsProgramResponse])
modules\drug-database\drug_database\api\router.py:320:@router.get("/shortages", response_model=list[DrugShortageResponse])
modules\drug-database\drug_database\api\router.py:332:@router.get("/shortages/{ndc}", response_model=list[DrugShortageResponse])
modules\drug-database\drug_database\api\router.py:345:@router.get("/refresh/status", response_model=list[RefreshStatusResponse])
modules\dataiq\src\api\router.py:35:from src.models.tables import (
modules\dataiq\src\api\router.py:86:@router.get("/metrics", response_model=list[MetricDefinitionResponse])
modules\dataiq\src\api\router.py:175:@router.get("/metrics/{metric_key}/history", response_model=MetricHistoryResponse)
modules\dataiq\src\api\router.py:239:@router.get("/metrics/{metric_key}/anomalies", response_model=list[AnomalyResponse])
modules\dataiq\src\api\router.py:283:@router.get("/drug-trend/decomposition", response_model=list[DecompositionResponse])
modules\dataiq\src\api\router.py:322:@router.get("/drug-trend/top-drugs", response_model=list[TopDrugResponse])
modules\dataiq\src\api\router.py:537:@router.get("/network/adequacy", response_model=NetworkAdequacyResponse)
modules\dataiq\src\api\router.py:977:@router.get("/data-quality", response_model=DataQualityScoreResponse)
modules\dataiq\src\api\router.py:1081:@router.get("/benchmarks", response_model=list[BenchmarkResponse])
modules\dataiq\src\api\router.py:1112:@router.post("/benchmarks", response_model=BenchmarkResponse, status_code=status.HTTP_201_CREATED)
modules\dataiq\src\api\router.py:1148:@router.put("/benchmarks/{benchmark_id}", response_model=BenchmarkResponse)
modules\dataiq\src\api\router.py:1261:@router.get("/insights", response_model=list[InsightAlertResponse])
modules\dataiq\src\api\router.py:1334:@router.get("/insights/summary", response_model=InsightSummaryResponse)
modules\drug-database\drug_database\api\schemas\drugs.py:127:    @field_validator("ndc_11", mode="before")
modules\dataiq\src\models\tables.py:1:"""SQLAlchemy ORM models for the dataiq schema.
modules\dataiq\src\models\tables.py:3:Follows PRD data model exactly. All tenant-owned tables inherit TenantScopedMixin.
modules\dataiq\src\models\tables.py:212:    """Trained forecast models with results."""
modules\dataiq\src\models\tables.py:214:    __tablename__ = "forecast_models"
modules\dataiq\src\models\tables.py:216:        sa.Index("ix_forecast_models_tenant_id", "tenant_id"),
modules\dataiq\src\models\tables.py:228:    model_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
modules\dataiq\src\models\tables.py:229:    model_parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
modules\drug-database\src\api\router.py:24:from src.models.tables import (
modules\drug-database\src\api\router.py:53:@router.get("/lookup/batch", response_model=list[DrugProductResponse])
modules\drug-database\src\api\router.py:71:@router.get("/lookup/{ndc}", response_model=DrugProductResponse)
modules\drug-database\src\api\router.py:84:@router.get("/search", response_model=DrugSearchResponse)
modules\drug-database\src\api\router.py:122:@router.get("/pricing/{ndc}", response_model=list[PricingResponse])
modules\drug-database\src\api\router.py:155:@router.get("/pricing/{ndc}/history", response_model=list[PricingHistoryResponse])
modules\drug-database\src\api\router.py:177:@router.get("/interactions", response_model=list[InteractionResponse])
modules\drug-database\src\api\router.py:214:@router.get("/equivalents/{ndc}", response_model=list[TherapeuticEquivalenceResponse])
modules\drug-database\src\api\router.py:239:@router.get("/overrides", response_model=list[TenantOverrideResponse])
modules\drug-database\src\api\router.py:248:@router.post("/overrides/upload", response_model=MACUploadResponse)
modules\drug-database\src\api\router.py:307:@router.get("/rems/{ndc}", response_model=list[RemsProgramResponse])
modules\drug-database\src\api\router.py:320:@router.get("/shortages", response_model=list[DrugShortageResponse])
modules\drug-database\src\api\router.py:332:@router.get("/shortages/{ndc}", response_model=list[DrugShortageResponse])
modules\drug-database\src\api\router.py:345:@router.get("/refresh/status", response_model=list[RefreshStatusResponse])
modules\dataiq\src\api\schemas\metrics.py:14:    model_config = ConfigDict(from_attributes=True)
modules\dataiq\src\api\schemas\metrics.py:29:    model_config = ConfigDict(from_attributes=True)
modules\dataiq\src\api\schemas\metrics.py:93:    model_config = ConfigDict(from_attributes=True)
modules\dataiq\src\api\schemas\metrics.py:107:    model_config = ConfigDict(from_attributes=True)
modules\dataiq\src\api\schemas\metrics.py:132:    model_config = ConfigDict(from_attributes=True)
modules\maxacc-registry\alembic\env.py:98:if context.is_offline_mode():
modules\maxacc-registry\src\maxacc_registry\ingest\curated_seed.py:37:import argparse
modules\maxacc-registry\src\maxacc_registry\ingest\curated_seed.py:428:    parser = argparse.ArgumentParser(prog="maxacc_registry.ingest.curated_seed")
modules\drug-database\src\models\ndc_tables.py:1:"""FDA NDC Directory ORM models for the drug-database module.
modules\drug-database\src\models\ndc_tables.py:4:DrugProduct/DrugPricing models in tables.py).
modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:35:import argparse
modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:153:        envelope = _ScraperOutputEnvelope.model_validate(raw)
modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:295:        entry = _NdcEntry.model_validate(raw_entry)
modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:310:        entry = _BinPcnEntry.model_validate(raw_entry)
modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:337:        entry = _EmployerEntry.model_validate(raw_entry)
modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:375:    parser = argparse.ArgumentParser(prog="maxacc_registry.ingest.scraper_output")
modules\drug-database\src\models\orange_book_tables.py:1:"""FDA Orange Book ORM models for the drug-database module.
modules\drug-database\src\api\schemas\drugs.py:127:    @field_validator("ndc_11", mode="before")
modules\drug-database\src\models\pricing_tables.py:1:"""CMS NADAC and ASP pricing ORM models for the drug-database module.
modules\drug-database\src\models\rxnorm_tables.py:1:"""RxNorm ORM models for the drug-database module.
modules\drug-database\src\models\tables.py:1:"""SQLAlchemy models for the drug-database module.

codex
The loader-mode erratum resolves differently from the draft note: the current `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, and `fdb_rebase`, so B9.A does not need to invent `fdb_weekly`. The larger blocker is arithmetic: Tier C “non-RNDC14 except three special” must be 16, not 17, which explains the false 284 and the `218/217` overshoot.
codex
## PLAN R1 GATE VERDICT

GO-WITH-FIXES

## Plan-level verification

| # | Criterion | Verdict | Evidence / notes |
|---|---|---|---|
| 1 | Goal-backward coverage of all SCs | PARTIAL | Table exists for SC-1..SC-11 at `plan.md:315-331`, but SC-1/SC-6 artifacts use unreconciled bad counts: `pg_class == 220` and `284/284` at `plan.md:321,326`. |
| 2 | Threat model completeness | PARTIAL | T1-T11 exist at `plan.md:335-349`, but charter R4 “weekly delta breaks because NEW columns” (`charter.md:88`) is not covered with schema-version detection/drift halt. T7 only covers idempotency (`plan.md:345`). |
| 3 | Phase boundaries respect SPEC-locked granularity | PARTIAL | RNDC14 standalone is honored (`plan.md:184-205`), but Tier A/B part-file options inflate migrations to 9-10 (`plan.md:95,141,389-390`) despite charter locking per-phase batched migrations `0009..0014` (`charter.md:75-79`). |
| 4 | Mini-GATE-CLOSE criteria concrete | YES | B9.B has counts/FDW/tests/idempotency (`plan.md:117-126`); B9.C inherits plus FK integrity (`plan.md:154`); B9.D/E/F/G add measurable audits/tests/perf gates (`plan.md:180,205,231-238,267-272`). |
| 5 | D2 perf gate real | YES | B9.F requires timed dry-run, EXPLAIN ANALYZE, storage delta, FDW/Postgres verify under 5min, weekly delta timing (`plan.md:213-238`). |
| 6 | MTL guards triple-layered | YES | Schema-only migration, loader exclusion, config flag, and zero-row integration test are all present (`plan.md:61,248-260,267-272`). |
| 7 | Pre-execute invariants testable | YES | Invariants have concrete checks: commit/memory references, FDW verify, `df -h`, config flag location, `pytest --collect-only`, manifest parse, consult slots (`plan.md:30-44`). |
| 8 | Session sizing realistic | DEFENSIBLE-BUT-RISKY | Tier A is explicitly aggressive at ~12 tables/session (`plan.md:92-128`); Tier B is more plausible at ~5.5/session with FK checks (`plan.md:136-154`). |
| 9 | Commit chains executable | PARTIAL | B9.A C0-C7 in 2-3 sessions is crowded (`plan.md:52-85`), and B9.B/B9.C migration shape is unresolved inside execution (`plan.md:95,141`). |
| 10 | Codex iteration plan complete | YES | SPEC R1/R2, PLAN R1, ADVERSARIAL, B9.B-G mini-closes, and final GATE-CLOSE are listed (`plan.md:357-367`). |

## Errata verification

| Erratum | Resolution | Evidence |
|---|---|---|
| FDW count 283 vs 284 | **283 is right.** Recon: 220 FDB source tables, 3 already covered, 217-table gap (`recon.md:11,99`). FDW baseline has 66 entries and B9 adds 217, so 66 + 217 = 283. Plan’s 284 comes from a Tier C arithmetic bug: “19 except RNDC14/RNP2/RPRDPP0” is 16, not 17 (`plan.md:158-160,263-265`). Correct sequence: 66→179→245→261→262→264→283. | `recon.md:11,14,99,114`; `plan.md:62,158-160,261-265,282-283,389`; `charter.md:55,66`. |
| Migration batching shape | Use the charter-locked **6 migration files**: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` with 16 tables, `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`. Do not split Tier A/B into 25-table part revisions unless SPEC is amended. | Charter locks this exact shape (`charter.md:75-79`). Recon says one Tier A migration is reviewable because tables are uniform (`recon.md:173-180`). Plan’s 9-10 option is unresolved (`plan.md:95,141,389-390`). |
| Loader modes | Existing loader already supports both `fdb_initial` and `fdb_weekly`; B9.A does **not** need to add `fdb_weekly`. It may need to add new tier/MTL modes if the plan keeps `fdb_tier_a`, `fdb_tier_b`, and `fdb_mtl_data`. | `scripts/load_fdb.py:5-9,68-69`; plan erratum is stale at `plan.md:391`. |

## Charter-vs-plan consistency

| # | Question | Answer |
|---|---|---|
| 14 | Per-phase gates honored | NO. The phase structure is broadly aligned, but the count ladder is wrong after B9.D, B9.H uses 284 instead of charter SC-6’s 283, and migration part files conflict with SPEC-locked granularity. |
| 15 | Effort math reconciled | NO. Plan totals 42 sessions while charter says ~39. The delta is not explained; some B9.A/B9.H/C0/perf/closeout work appears double-counted against charter W5 and phase rows. |

## Vendor-name sanity check

PASS. Grep across `charter.md`, `plan.md`, and `recon.md` for prohibited PBM/vendor names returned no hits.

## New concerns (any HIGH/MEDIUM/LOW issues beyond the above)

- HIGH: Tier C arithmetic error: `19 - 3 = 16`, not 17. This causes the false 284 FDW count, `cum 218/217`, and incorrect phase count ladder.
- HIGH: SC-1 verification artifact says `pg_class` FDB-prefixed table count should be 220 (`plan.md:321`), but recon says 3 source tables currently map to 2 DB tables (`recon.md:91-97`). Final DB-table count needs explicit definition, likely not `220`.
- MEDIUM: Weekly delta/UPD structure risk from recon is underplanned. Recon warns some tables may not use A/C/D deltas and may require TRUNCATE+INSERT (`recon.md:259-262`); plan only gates rerun idempotency.
- MEDIUM: `pytest --collect-only` “134 failures baseline” is conceptually mismatched: collect-only captures collection count/errors, not failure count. Use a real baseline command for failures or reword.

## Final verdict + next action

GO-WITH-FIXES. Produce PLAN v2 before ADVERSARIAL: correct Tier C non-special count to 16, reconcile all FDW/SC-1 counts to 283 final FDW entries, lock migrations to the 6 SPEC-approved files, fix the loader-mode erratum, add a real weekly-delta schema/UPD-format guard, and explain the 42-vs-39 session delta or reduce the plan back to the charter budget.
tokens used
70,166
## PLAN R1 GATE VERDICT

GO-WITH-FIXES

## Plan-level verification

| # | Criterion | Verdict | Evidence / notes |
|---|---|---|---|
| 1 | Goal-backward coverage of all SCs | PARTIAL | Table exists for SC-1..SC-11 at `plan.md:315-331`, but SC-1/SC-6 artifacts use unreconciled bad counts: `pg_class == 220` and `284/284` at `plan.md:321,326`. |
| 2 | Threat model completeness | PARTIAL | T1-T11 exist at `plan.md:335-349`, but charter R4 “weekly delta breaks because NEW columns” (`charter.md:88`) is not covered with schema-version detection/drift halt. T7 only covers idempotency (`plan.md:345`). |
| 3 | Phase boundaries respect SPEC-locked granularity | PARTIAL | RNDC14 standalone is honored (`plan.md:184-205`), but Tier A/B part-file options inflate migrations to 9-10 (`plan.md:95,141,389-390`) despite charter locking per-phase batched migrations `0009..0014` (`charter.md:75-79`). |
| 4 | Mini-GATE-CLOSE criteria concrete | YES | B9.B has counts/FDW/tests/idempotency (`plan.md:117-126`); B9.C inherits plus FK integrity (`plan.md:154`); B9.D/E/F/G add measurable audits/tests/perf gates (`plan.md:180,205,231-238,267-272`). |
| 5 | D2 perf gate real | YES | B9.F requires timed dry-run, EXPLAIN ANALYZE, storage delta, FDW/Postgres verify under 5min, weekly delta timing (`plan.md:213-238`). |
| 6 | MTL guards triple-layered | YES | Schema-only migration, loader exclusion, config flag, and zero-row integration test are all present (`plan.md:61,248-260,267-272`). |
| 7 | Pre-execute invariants testable | YES | Invariants have concrete checks: commit/memory references, FDW verify, `df -h`, config flag location, `pytest --collect-only`, manifest parse, consult slots (`plan.md:30-44`). |
| 8 | Session sizing realistic | DEFENSIBLE-BUT-RISKY | Tier A is explicitly aggressive at ~12 tables/session (`plan.md:92-128`); Tier B is more plausible at ~5.5/session with FK checks (`plan.md:136-154`). |
| 9 | Commit chains executable | PARTIAL | B9.A C0-C7 in 2-3 sessions is crowded (`plan.md:52-85`), and B9.B/B9.C migration shape is unresolved inside execution (`plan.md:95,141`). |
| 10 | Codex iteration plan complete | YES | SPEC R1/R2, PLAN R1, ADVERSARIAL, B9.B-G mini-closes, and final GATE-CLOSE are listed (`plan.md:357-367`). |

## Errata verification

| Erratum | Resolution | Evidence |
|---|---|---|
| FDW count 283 vs 284 | **283 is right.** Recon: 220 FDB source tables, 3 already covered, 217-table gap (`recon.md:11,99`). FDW baseline has 66 entries and B9 adds 217, so 66 + 217 = 283. Plan’s 284 comes from a Tier C arithmetic bug: “19 except RNDC14/RNP2/RPRDPP0” is 16, not 17 (`plan.md:158-160,263-265`). Correct sequence: 66→179→245→261→262→264→283. | `recon.md:11,14,99,114`; `plan.md:62,158-160,261-265,282-283,389`; `charter.md:55,66`. |
| Migration batching shape | Use the charter-locked **6 migration files**: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` with 16 tables, `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`. Do not split Tier A/B into 25-table part revisions unless SPEC is amended. | Charter locks this exact shape (`charter.md:75-79`). Recon says one Tier A migration is reviewable because tables are uniform (`recon.md:173-180`). Plan’s 9-10 option is unresolved (`plan.md:95,141,389-390`). |
| Loader modes | Existing loader already supports both `fdb_initial` and `fdb_weekly`; B9.A does **not** need to add `fdb_weekly`. It may need to add new tier/MTL modes if the plan keeps `fdb_tier_a`, `fdb_tier_b`, and `fdb_mtl_data`. | `scripts/load_fdb.py:5-9,68-69`; plan erratum is stale at `plan.md:391`. |

## Charter-vs-plan consistency

| # | Question | Answer |
|---|---|---|
| 14 | Per-phase gates honored | NO. The phase structure is broadly aligned, but the count ladder is wrong after B9.D, B9.H uses 284 instead of charter SC-6’s 283, and migration part files conflict with SPEC-locked granularity. |
| 15 | Effort math reconciled | NO. Plan totals 42 sessions while charter says ~39. The delta is not explained; some B9.A/B9.H/C0/perf/closeout work appears double-counted against charter W5 and phase rows. |

## Vendor-name sanity check

PASS. Grep across `charter.md`, `plan.md`, and `recon.md` for prohibited PBM/vendor names returned no hits.

## New concerns (any HIGH/MEDIUM/LOW issues beyond the above)

- HIGH: Tier C arithmetic error: `19 - 3 = 16`, not 17. This causes the false 284 FDW count, `cum 218/217`, and incorrect phase count ladder.
- HIGH: SC-1 verification artifact says `pg_class` FDB-prefixed table count should be 220 (`plan.md:321`), but recon says 3 source tables currently map to 2 DB tables (`recon.md:91-97`). Final DB-table count needs explicit definition, likely not `220`.
- MEDIUM: Weekly delta/UPD structure risk from recon is underplanned. Recon warns some tables may not use A/C/D deltas and may require TRUNCATE+INSERT (`recon.md:259-262`); plan only gates rerun idempotency.
- MEDIUM: `pytest --collect-only` “134 failures baseline” is conceptually mismatched: collect-only captures collection count/errors, not failure count. Use a real baseline command for failures or reword.

## Final verdict + next action

GO-WITH-FIXES. Produce PLAN v2 before ADVERSARIAL: correct Tier C non-special count to 16, reconcile all FDW/SC-1 counts to 283 final FDW entries, lock migrations to the 6 SPEC-approved files, fix the loader-mode erratum, add a real weekly-delta schema/UPD-format guard, and explain the 42-vs-39 session delta or reduce the plan back to the charter budget.
