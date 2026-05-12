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
session id: 019e1885-4c95-7b02-b0a7-95ee4731f47f
--------
user
You are codex acting as the ADVERSARIAL reviewer for the InfinityRx platform's Wave B9. Your role this round is hostile, not constructive: **find ways this plan will fail in execution**.

## Context

B9 = FDB NDDF Plus 220-table extension (217-table gap → ingested or schema-only across 8 phases B9.A..B9.H). SPEC v3.1 LOCKED. PLAN v2 LOCKED (codex PLAN R1 GO-WITH-FIXES → 8 fixes applied → PLAN R2 GO-WITH-FIXES → charter erratum → PLAN GATE FINAL VERDICT GO).

The plan has passed two rounds of constructive review. It now needs an adversarial pass before execute. Constructive review asks "does the plan meet the spec?" — adversarial review asks "where will this plan break?"

## Artifacts

1. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\plan.md` — PLAN v2 LOCKED (~400 lines)
2. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md` — SPEC v3.1 LOCKED (~115 lines)
3. `C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\recon.md` — scope ground truth (328 lines)
4. (Codebase context if needed) `C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\scripts\load_fdb.py` and `C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\` for the existing ingester surface

## Adversarial questions to attack the plan

Probe each of these — find the failure mode where the plan breaks:

**Execution attacks:**
1. **Session size attack:** Tier A says 12 tables/session. What if a single Tier A table has a hidden complexity (e.g., requires a join, or has > 5 columns despite recon classification)? How does the plan handle a single-session overflow without dragging the wave's 10-session budget?
2. **Migration attack:** A single migration covering 113 tables (Tier A) is large. What if alembic apply fails partway? Is there a rollback strategy? Can a half-applied migration leave the DB in a state that blocks reverse?
3. **FDW manifest attack:** The plan additively grows `expected_reference_tables.txt`. What if two phases both touch this file in parallel sessions? Is there merge-conflict resolution?
4. **Idempotency attack:** Plan claims weekly delta is idempotent. What if FDB's UPD file has an A (add) record for a row that was previously D (deleted) and then re-A'd with different values? Does ON CONFLICT DO NOTHING preserve the latest or the oldest? Plan doesn't say.
5. **MTL guard attack:** The triple-layer guard (schema + loader exclusion + integration test) prevents data load. What if a developer in a future wave adds an INSERT statement targeting an MTL table directly, bypassing the loader? Plan's guard doesn't catch that.

**Boundary attacks:**
6. **B9.E RNDC14 attack:** Plan dedicates 2 sessions to a 68-column model. What if column-by-column codex review surfaces 5+ type-correctness issues? Does the mini-GATE-CLOSE allow iteration, or does it fail outright?
7. **B9.F perf gate attack:** RNP2+RPRDPP0 timed dry-run says ≤ 5 min FDW verify after indexes. What if the actual dry-run takes 20 min? What's the abort criterion? Charter says "abort + escalate if > +1.4 GB" for storage — but no explicit abort for timing.
8. **B9.G MTL FDW attack:** Plan says MTL tables ARE in FDW as foreign-table entries pointing at empty reference tables. What if a downstream query joins to an MTL foreign table? Postgres won't error, but the join returns empty — silent failure mode.

**Schedule attacks:**
9. **Calendar slip:** 42 sessions × 4 hours = 168 hours. At 3 sessions/week = 14 weeks. What if half the sessions overrun by 50% (typical for wave-grade work)? Then 21 weeks = 5+ months. Is the team prepared for that calendar?
10. **Codex consult cadence attack:** 12 codex consults planned. Each takes ~30-60k tokens. Total ~500k-700k codex tokens. What's the budget? Are there fallbacks if codex network is down (we already saw this fail once in SPEC R2)?

**Hidden assumption attacks:**
11. **`infinityrx_reference` write path:** Plan assumes loaders write directly to the reference DB. Is the connection-string config in place for every loader? What if a loader picks up a dev/mock connection string by accident and writes to the wrong DB?
12. **Existing 3-table coverage interaction:** Phase 09 covers RNP3 + RPRDPTD0 + RNPTYPD0. Does B9.A's new TableSpec registry change break these? Migration `0009_fdb_tier_a` is independent of them, but the registry might re-process them.
13. **Test count baseline assumption:** Plan freezes 134 failures. What if those 134 include flaky tests that pass 30% of the time? Then mini-GATE-CLOSE might falsely show 135 failures one session and 132 the next.

**Cross-module / regression attacks:**
14. **adjudication-engine ripple:** Adjudication queries FDB tables via reference DB FDW. If B9 adds 217 new FDB tables, does adjudication's query path change? Plan doesn't audit the consumer side.
15. **reclaimrx pricing-protocol assertion:** `assert_awp_basis_acceptable` in reclaimrx depends on FDB pricing data. Does B9.F (RNP2+RPRDPP0 inclusion) change which `awp_basis` values are populated? Plan doesn't trace.
16. **Memory consistency:** Plan adds memory entries per phase. If B9 spans 13 weeks, memory churn is high. What if a later phase contradicts an earlier memory line and no one notices?

## Verdict format

```
## ADVERSARIAL VERDICT

<NO HIGH-SEVERITY UNADDRESSED OBJECTIONS | HIGH-SEVERITY OBJECTIONS PRESENT | STRUCTURAL FLAW>

## Attack findings

| # | Attack | Severity | Finding | Plan addresses? | Mitigation needed |
|---|---|---|---|---|---|
| 1 | Session size | <H/M/L> | <what breaks> | YES / PARTIAL / NO | <what to add> |
... (all 16, plus any novel attack you discover)

## Novel attacks (not in the 16 questions)

<list with severity, or "None">

## Strongest single objection (the one that, if unaddressed, would block GO)

<one paragraph>

## Final verdict + next action

<one paragraph: if no HIGH unaddressed → PLAN locks fully, B9.A closes, B9.B opens; if HIGH unaddressed → plan v3 needs <list of required mitigations>; if STRUCTURAL FLAW → escalate to architectural pause>
```

Be relentless. The goal is to find the breakage now, not in production. If the plan addresses the attack, mark YES and move on. If it papers over the attack or is silent, flag PARTIAL or NO and demand a mitigation.
codex
I’ll read the locked B9 artifacts and the existing loader surface, then I’ll produce the adversarial verdict in the requested table format. I’m treating this as review only because the task is to attack the plan, not edit it.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 383ms:
# Wave B9 â€” FDB NDDF Plus 220-table extension (full scope)

**Status:** SPEC v3.1 LOCKED â€” SPEC v3 + erratum applied after codex PLAN R2 surfaced arithmetic drift between charter and PLAN v2. Erratum: B9.B closure-gate FDW count `116/116` â†’ `179/179`; B9.D scope "17 complex tables" â†’ "16 complex tables" (19 Tier C minus 3 special-handled). No scope change; arithmetic correction only. See `codex-plan-consult-r2.md`. Ready for PLAN v2 â†’ ADVERSARIAL.
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
| B9.B | Tier A â€” 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** â€” evidence + row-count manifest + FDW verify 179/179 + ingester contract tests |
| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests (FDW 245/245) |
| B9.D | Tier C non-RNDC14 â€” 16 complex tables | 4 | **B9.D mini-GATE-CLOSE** (FDW 261/261) |
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

 succeeded in 394ms:
# Wave B9 â€” Execution Plan v2

**Status:** PLAN v2 LOCKED â€” codex PLAN R1 GO-WITH-FIXES (8 fixes) + PLAN R2 GO-WITH-FIXES (charter erratum) + PLAN GATE FINAL VERDICT GO (`codex-plan-consult-r2.md`). Pending codex ADVERSARIAL consult before B9.A closes and B9.B opens.
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
6. **134 pre-existing test failures baseline frozen** â€” at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged Â± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
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
- **`setup_fdw.sh --verify` manifest expansion mechanism** â€” `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline â†’ 179 (after B9.B +113) â†’ 245 (after B9.C +66) â†’ 261 (after B9.D +16) â†’ 262 (after B9.E +1 RNDC14) â†’ 264 (after B9.F +2 pricing) â†’ 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
- **pytest baseline markers** â€” committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.

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
- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon Â§4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
- 12 contract-test wirings per session (each table gets the parity + decode + count + idempotency test set)
- 1 partial loader registry update per session (incremental)

**Deliverables:**

- 113 SQLAlchemy models in `modules/drug-database/src/.../fdb/models/tier_a/`
- 113 `TableSpec` entries in `specs.py`
- 1 alembic migration (`0009_fdb_tier_a.py`)
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
- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.

**Deliverables:**

- 66 SQLAlchemy models in `modules/drug-database/src/.../fdb/models/tier_b/`
- 66 `TableSpec` entries
- 1 alembic migration (`0010_fdb_tier_b.py`)
- Contract test coverage = 66 tables + FK-integrity assertions
- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
- FDW foreign-table count: 179 â†’ 245

**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.

**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.

---

### B9.D â€” Tier C non-RNDC14: 16 complex/large tables (4 sessions)

**Scope:** All 19 Tier C tables EXCEPT the three special-handled ones (RNDC14, RNP2, RPRDPP0). That leaves **16 tables** (19 - 3 = 16). Complex tables here are > 8 columns or > 50 MB. Includes ETC master, product master (RPRD0_PRODUCT â€” load before RNDC14), GCN master, etc.

**Per-session shape (4 sessions = ~4 tables/session):**

- 4 new `TableSpec` definitions per session
- Each Tier C table gets explicit column-curation note (which columns kept, which dropped, why) in a per-table block in `waves/B9/tier_c_curation.md`
- Money columns (if any) flagged for `Decimal` typing review per `.claude/rules/financial-precision.md`
- 1 batched alembic migration: `0011_fdb_tier_c_minus_rndc14.py`

**Deliverables:**

- 16 SQLAlchemy models in `modules/drug-database/src/.../fdb/models/tier_c/`
- 16 `TableSpec` entries
- 1 alembic migration (`0011_fdb_tier_c_minus_rndc14.py`)
- Contract tests + column-curation note + money-path audit
- FDW foreign-table count: 245 â†’ **261**
- Tier C dedicated behavioral tests for the 3-4 highest-value tables (ETC master, RPRD0_PRODUCT)

**Success criteria:** SC-1 (partial: cum 195/217), SC-2, SC-6 (261/261), SC-7, SC-8 (dedicated Tier C tests), SC-9.

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
- FDW foreign-table count: 261 â†’ 262

**Success criteria:** SC-1 (cum 196/217), SC-3 (RNDC14 all 68 cols), SC-2, SC-6 (262/262), SC-7, SC-8 (dedicated RNDC14 tests), SC-9.

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
- FDW foreign-table count: 262 â†’ 264

**Success criteria:** SC-1 (cum 198/217), SC-4 (D2 perf gate met: timed dry-run + EXPLAIN ANALYZE + storage budget + weekly delta timing all documented), SC-2, SC-6 (264/264), SC-7, SC-8 (RNP2 + RPRDPP0 dedicated behavioral), SC-9.

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
- FDW foreign-table count: 264 â†’ **283** (MTL tables ARE in FDW even though data isn't loaded â€” they exist as foreign-table entries pointing at empty reference tables)

**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D â€” 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.

**Success criteria:** SC-1 (cum 217/217), SC-5 (MTL zero-row test green), SC-6 (283/283), SC-9.

**B9.G mini-GATE-CLOSE criteria:**

- `0014_fdb_mtl_schema.py` apply + reverse + apply: clean
- Integration test `test_fdb_mtl_zero_rows_under_default` green after live load attempt with default flag
- Opt-in flag flip + `--mode fdb_mtl_data` invocation succeeds (validated, then rolled back)
- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)

---

### B9.H â€” Manifest extension + final closeout (4 sessions)

**Scope:** Reconcile `infrastructure/scripts/lib/expected_reference_tables.txt` to the true final count, run final FDW verify, produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.

**Per-session shape (4 sessions):**

- Session 1: Manifest expansion â€” `expected_reference_tables.txt` final count locked at **283** (matches charter SC-6; codex PLAN R1 reconciled). Update Werkbench inventory + glossary if new tables/concepts warrant.
- Session 2: Final `setup_fdw.sh --verify` **283/283** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables; published in `waves/B9/evidence.md`
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
| SC-1 | `pg_class` count of FDB-prefixed tables in `drug_database` schema == **219** (2 already-covered + 113 + 66 + 16 + 1 + 2 + 19 = 219 DB tables; the 220 source FDB tables map to 219 DB tables because RNP3+RPRDPTD0+RNPTYPD0 collapse into 2 DB tables `fdb_ndc_price_history` + `fdb_price_type_desc`); `alembic history` shows migrations 0009..0014 applied | B9.H Session 2 evidence |
| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
| SC-4 | `waves/B9/perf_b9f.md`: timed dry-run, EXPLAIN ANALYZE, storage delta, weekly delta timing | B9.F |
| SC-5 | `test_fdb_mtl_zero_rows_under_default` green; opt-in mode reviewed in codex consult | B9.G |
| SC-6 | `setup_fdw.sh --verify` output **283/283** in dev + mock (charter-matched) | B9.H Session 2 |
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
| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, Â± in-phase contract tests on the collection number. |
| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables â€” some tables may require TRUNCATE+INSERT instead of UPSERT (recon Â§7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |

---

## Codex iteration plan

| Round | Phase | Dispatch trigger | Verdict file |
|---|---|---|---|
| SPEC R1 | B9.A | Charter v1 dispatched 2026-05-11 | `codex-spec-consult-r1.md` â€” GO-WITH-FIXES |
| SPEC R2 | B9.A | Charter v2 dispatched 2026-05-11 | `codex-spec-consult-r2.md` â€” GO-WITH-FIXES â†’ cleanup applied â†’ v3 LOCKED |
| PLAN R1 | B9.A | Plan v1 dispatched 2026-05-11 | `codex-plan-consult-r1.md` â€” **GO-WITH-FIXES** |
| **PLAN R2** | **B9.A** | **Plan v2 with R1 fixes absorbed; verify** | **`codex-plan-consult-r2.md` â€” pending** |
| ADVERSARIAL R1 | B9.A | After PLAN R2 GO | `codex-adversarial-r1.md` |
| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
| GATE-CLOSE | B9.H | Wave shipping artifacts assembled | `codex-gate-close.md` |

**Total codex consults projected:** 12 (2 SPEC done + PLAN R1 done + PLAN R2 + ADVERSARIAL + 6 mini-GATE-CLOSE + final GATE-CLOSE = 12).

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

## Errata resolved by codex PLAN R1 (kept for traceability)

1. **FDW final count: 283 vs 284** â†’ **RESOLVED: 283.** Tier C arithmetic bug (`19 - 3 = 16, not 17`) cascaded to 284. Plan v2 corrects all references: 66 â†’ 179 â†’ 245 â†’ 261 â†’ 262 â†’ 264 â†’ 283.
2. **Migration count: 5 vs 6 vs 9-10** â†’ **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.
3. **Loader-orchestration modes: existing vs new** â†’ **RESOLVED:** existing `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, `fdb_rebase`. B9.A C4 does NOT need to add `fdb_weekly`. It may need to add tier-specific modes (`fdb_tier_a`, `fdb_tier_b`, `fdb_mtl_data`) if per-tier loaders are desired; PLAN v2 leaves that as a B9.A C1 design decision (additive to existing modes).

## Effort math reconciliation (charter 39 vs plan 42)

Both numbers are correct under different framings; PLAN v2 makes the distinction explicit:

- **Charter Â§Workstreams view (39 sessions):** counts only productive ingest work â€” W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
- **Plan Â§Phased commit chain view (42 sessions):** counts every phase including B9.A meta-phase (charter v3 + plan v1/v2 + codex SPEC R2 + PLAN R1 + ADVERSARIAL + infra scaffolding = 3 sessions) and B9.H closeout (4 sessions). 3 + B (10) + C (12) + D (4) + E (2) + F (4) + G (3) + H (4) = **42**.

The 3-session delta is the B9.A meta-phase which the workstream view excludes by design (it's not table-ingest work). Both views are accurate. Charter's "~39" is the productive-work commitment; PLAN's 42 is the calendar-aware total including framework gates.

---

## Status reporting cadence

Per session-framework rules (`.claude/rules/session-framework.md`):

- Each B9.X session lands its own evidence row in `waves/B9/sessions.md` (created at B9.A)
- At each mini-GATE-CLOSE: full sign-off sheet committed
- Memory updates after each phase closes
- B9.H final ship: full memory + wave-history entry

**End of PLAN v1.**

 succeeded in 402ms:
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
The plan has several built-in gates, but I’m already seeing places where the gate records evidence without saying what happens on failure. I’m checking the real loader and model layout now so the verdict can distinguish plan-level silence from actual codebase constraints.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\InfinityRx\\infinityrx-platform\\scripts\\load_fdb.py'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-ChildItem -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\InfinityRx\\infinityrx-platform\\modules\\drug-database' -Recurse -File | Select-Object -ExpandProperty FullName | Select-Object -First 120" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "TableSpec|FDBLocalDropAdapter|ON CONFLICT|fdb_load_product_prices|assert_awp_basis_acceptable|setup_fdw|expected_reference_tables|infinityrx_reference|create_engine|DATABASE_URL" -S .' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 402ms:
"""Load FDB NDDF Plus drops into drug_database.

Reads operator-managed drops at `data/reference/fdb/TEL251759D/` via
`FDBLocalDropAdapter` and writes to `fdb_price_type_desc` +
`fdb_ndc_price_history`. Three modes per SPEC Â§4.7:

  --mode fdb_initial   one-time full DB.zip baseline (~15.6M rows)
  --mode fdb_weekly    routine UPD.zip application (typical ~10k-100k)
  --mode fdb_rebase    operator-triggered DB.zip re-baseline (recovery)

Idempotency: composite UNIQUE on
  (ndc_11, price_type, effective_date, as_of_date, transaction_code,
   drop_sequence)
catches duplicates. Replay of the same drop produces 0 net new rows.

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_fdb.py --mode fdb_weekly
    python scripts/load_fdb.py --mode fdb_initial --dry-run

Environment:
    DATABASE_URL_SYNC â€” set by switch_env.sh
    FDB_DROP_ROOT     â€” defaults to data/reference/fdb/TEL251759D/
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"
for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_fdb")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    # async driver doesn't work for sync engine
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _resolve_root() -> Path:
    raw = os.environ.get("FDB_DROP_ROOT")
    if raw:
        return Path(raw)
    return _REPO_ROOT / "data" / "reference" / "fdb" / "TEL251759D"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["fdb_initial", "fdb_weekly", "fdb_rebase"],
        required=True,
        help="ingestion mode (SPEC Â§4.7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse + count rows; do not write to the DB",
    )
    parser.add_argument(
        "--ingestion-run-id",
        default=None,
        help="optional shared.ingestion_runs FK to record on each inserted row",
    )
    args = parser.parse_args()

    # Imports deferred until after sys.path setup so module imports resolve.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from drug_database.services.fdb_adapter import FDBLocalDropAdapter
    from drug_database.services.fdb_pricing_ingester import FDBPricingIngester

    db_url = _resolve_db_url()
    root = _resolve_root()
    if not root.exists():
        logger.error("FDB drop root not found: %s", root)
        return 2

    engine = create_engine(db_url)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()

    try:
        adapter = FDBLocalDropAdapter(root)
        ingester = FDBPricingIngester(
            adapter=adapter,
            session=session,
            ingestion_run_id=args.ingestion_run_id,
        )
        result = ingester.run(mode=args.mode, dry_run=args.dry_run)
    finally:
        session.close()
        engine.dispose()

    logger.info(
        "fdb_ingest_summary mode=%s drop_date=%s "
        "price_type_desc_inserted=%d "
        "rnp3_inserted=%d rnp3_duplicate_skipped=%d rnp3_invalid_skipped=%d "
        "dry_run=%s",
        result.mode,
        result.drop_date,
        result.price_type_desc_inserted,
        result.rnp3_inserted,
        result.rnp3_duplicate_skipped,
        result.rnp3_invalid_skipped,
        result.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

 succeeded in 487ms:
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.coverage
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\alembic.ini
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\conftest.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\pyproject.toml
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\README [conflicted].md
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\README.md
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\uv.lock
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.pytest_cache\.gitignore
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.pytest_cache\CACHEDIR.TAG
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.pytest_cache\README.md
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.pytest_cache\v\cache\lastfailed
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.pytest_cache\v\cache\nodeids
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.ruff_cache\.gitignore
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.ruff_cache\CACHEDIR.TAG
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.ruff_cache\0.15.10\12859377578870967306
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.ruff_cache\0.15.10\13641821600515041040
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.ruff_cache\0.15.10\1857170389829685446
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.ruff_cache\0.15.10\3465387833675883010
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.ruff_cache\0.15.10\4435421518724123701
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.ruff_cache\0.15.10\6776193098465131356
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\.gitignore
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\.lock
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\CACHEDIR.TAG
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\pyvenv.cfg
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\py.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\_virtualenv.pth
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\_virtualenv.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\ansi.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\ansitowin32.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\initialise.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\win32.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\winterm.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\__init__.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\tests\ansitowin32_test.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\tests\ansi_test.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\tests\initialise_test.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\tests\isatty_test.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\tests\utils.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\tests\winterm_test.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\tests\__init__.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\__pycache__\ansi.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\__pycache__\ansitowin32.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\__pycache__\initialise.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\__pycache__\win32.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\__pycache__\winterm.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama\__pycache__\__init__.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama-0.4.6.dist-info\INSTALLER
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama-0.4.6.dist-info\METADATA
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama-0.4.6.dist-info\RECORD
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama-0.4.6.dist-info\REQUESTED
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama-0.4.6.dist-info\WHEEL
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\colorama-0.4.6.dist-info\licenses\LICENSE.txt
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig\exceptions.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig\py.typed
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig\_parse.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig\_version.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig\__init__.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig\__pycache__\exceptions.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig\__pycache__\_parse.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig\__pycache__\__init__.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig-2.3.0.dist-info\INSTALLER
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig-2.3.0.dist-info\METADATA
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig-2.3.0.dist-info\RECORD
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig-2.3.0.dist-info\REQUESTED
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig-2.3.0.dist-info\top_level.txt
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig-2.3.0.dist-info\WHEEL
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\iniconfig-2.3.0.dist-info\licenses\LICENSE
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\dependency_groups.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\direct_url.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\errors.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\markers.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\metadata.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\py.typed
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\pylock.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\requirements.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\specifiers.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\tags.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\utils.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\version.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\_elffile.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\_manylinux.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\_musllinux.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\_parser.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\_structures.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\_tokenizer.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\__init__.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\licenses\_spdx.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging\licenses\__init__.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging-26.2.dist-info\INSTALLER
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging-26.2.dist-info\METADATA
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging-26.2.dist-info\RECORD
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging-26.2.dist-info\REQUESTED
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging-26.2.dist-info\WHEEL
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging-26.2.dist-info\licenses\LICENSE
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging-26.2.dist-info\licenses\LICENSE.APACHE
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\packaging-26.2.dist-info\licenses\LICENSE.BSD
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\py.typed
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\_callers.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\_hooks.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\_manager.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\_result.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\_tracing.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\_version.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\_warnings.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\__init__.py
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\__pycache__\_callers.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\__pycache__\_hooks.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\__pycache__\_manager.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\__pycache__\_result.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\__pycache__\_tracing.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\__pycache__\_version.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\__pycache__\_warnings.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy\__pycache__\__init__.cpython-313.pyc
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy-1.6.0.dist-info\INSTALLER
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy-1.6.0.dist-info\METADATA
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy-1.6.0.dist-info\RECORD
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy-1.6.0.dist-info\REQUESTED
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy-1.6.0.dist-info\top_level.txt
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy-1.6.0.dist-info\WHEEL
C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform\modules\drug-database\.venv\Lib\site-packages\pluggy-1.6.0.dist-info\licenses\LICENSE

 succeeded in 558ms:
.\azure-pipelines.yml:130:          DATABASE_URL: postgresql://infinityrx:test@localhost:5432/infinityrx_test
.\AGENTS [conflicted].md:41:1640 8:45a 🔵 Current FDB ingester implementation uses generic TableSpec-driven pattern; enables 220-table extension without new code
.\AGENTS [conflicted].md:62:1659 " ⚖️ Ingester architecture: generic TableSpec-driven for Tier A+B (179 tables); per-table services for Tier C
.\infrastructure\scripts\init-multi-db.sql:6:--   infinityrx_reference  — single shared reference catalog (loaders write
.\infrastructure\scripts\init-multi-db.sql:17:--   │  infinityrx_reference   │  ← loaders ingest licensed/public reference
.\infrastructure\scripts\init-multi-db.sql:25:--                │ postgres_fdw (configured by setup_fdw.sh)
.\infrastructure\scripts\init-multi-db.sql:33:-- │  billing,│         │  billing,│    infinityrx_reference. App code does
.\infrastructure\scripts\init-multi-db.sql:36:--                                      forwards to infinityrx_reference.
.\infrastructure\scripts\init-multi-db.sql:65:CREATE DATABASE infinityrx_reference OWNER ifx_reference_writer;
.\infrastructure\scripts\init-multi-db.sql:71:-- CONNECT on infinityrx_reference for the FDW user mapping (per env's
.\infrastructure\scripts\init-multi-db.sql:73:GRANT CONNECT ON DATABASE infinityrx_reference TO ifx_ref_reader, ifx_dev_app, ifx_mock_app;
.\infrastructure\scripts\init-multi-db.sql:78:GRANT ALL PRIVILEGES ON DATABASE infinityrx_reference TO infinityrx;
.\infrastructure\scripts\init-multi-db.sql:83:-- infinityrx_reference schema scaffolding
.\infrastructure\scripts\init-multi-db.sql:101:\connect infinityrx_reference
.\infrastructure\scripts\init-multi-db.sql:155:-- created by setup_fdw.sh as a FDW import target, NOT here. Module schemas
.\infrastructure\scripts\load_demo_claims.py:9:Writes: <DATABASE_URL>.billing.claim_records, scoped to a fixed DEMO_TENANT_ID
.\infrastructure\scripts\load_demo_claims.py:13:The DATABASE_URL is read from the active environment (.env.mock when
.\infrastructure\scripts\load_demo_claims.py:228:    db_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
.\infrastructure\scripts\load_demo_claims.py:231:        print("          Active DATABASE_URL points at infinityrx_prod.", file=sys.stderr)
.\infrastructure\evidence\p11a\07b-migrations.txt:1:=== Wave B7 C7b alembic migrations against infinityrx_reference — 2026-05-09T16:55:22-04:00 ===
.\infrastructure\evidence\p11a\07b-migrations.txt:162:## Post-migration: tables in infinityrx_reference
.\infrastructure\evidence\p11a\07b-migrations.txt:168:=== C7b retry: core-platform alembic against infinityrx_reference — 2026-05-09T16:57:15-04:00 ===
.\infrastructure\evidence\p11a\07b-migrations.txt:339:## Post-migration: tables in infinityrx_reference per schema
.\infrastructure\scripts\run_migrations.sh:6:# We pass DATABASE_URL/DATABASE_URL_SYNC inline so they take precedence over
.\infrastructure\scripts\run_migrations.sh:46:# Force DATABASE_URL_SYNC to use asyncpg too — modules/core-platform/alembic
.\infrastructure\scripts\run_migrations.sh:48:export DATABASE_URL_SYNC="$DATABASE_URL"
.\infrastructure\scripts\run_migrations.sh:65:echo "  DATABASE_URL: ${DATABASE_URL%@*}@***"
.\infrastructure\scripts\run_migrations.sh:90:      SYNC_URL="${DATABASE_URL/+asyncpg/+psycopg2}"
.\infrastructure\scripts\run_migrations.sh:92:        DATABASE_URL="$SYNC_URL" \
.\infrastructure\scripts\run_migrations.sh:93:        DATABASE_URL_SYNC="$SYNC_URL" \
.\infrastructure\evidence\p11a\07-bringup.txt:7:infinityrx_reference
.\infrastructure\evidence\p11a\07-bringup.txt:18:## infinityrx_reference schemas
.\infrastructure\evidence\p11a\08-loader-run-manifest.txt:28:  Ground-truth row counts (queried from infinityrx_reference)
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:3:# shared `infinityrx_reference` database ONCE.
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:8:#                                                       # DATABASE_URL_SYNC_REFERENCE
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:47:# Reference DB URL must be set (loaders prefer DATABASE_URL_SYNC_REFERENCE
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:49:if [ -z "${DATABASE_URL_SYNC_REFERENCE:-}" ]; then
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:54:if [ -z "${DATABASE_URL_SYNC_REFERENCE:-}" ]; then
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:55:  echo "FATAL: DATABASE_URL_SYNC_REFERENCE not set. Source .env.dev or .env.mock first." >&2
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:59:# Override DATABASE_URL_SYNC for the loader subprocess so any code that
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:62:export DATABASE_URL_SYNC="$DATABASE_URL_SYNC_REFERENCE"
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:63:export DATABASE_URL="$DATABASE_URL_SYNC_REFERENCE"
.\infrastructure\scripts\run_reference_loaders (conflicted).sh:133:echo "  DATABASE_URL_SYNC_REFERENCE: ${DATABASE_URL_SYNC_REFERENCE%@*}@***"
.\infrastructure\scripts\lib\psql_strict.sh:11:#   result=$(psql_strict "$DATABASE_URL_SYNC_REFERENCE" "SELECT count(*) FROM foo") || exit 1
.\infrastructure\scripts\run_reference_loaders.sh:3:# shared `infinityrx_reference` database ONCE.
.\infrastructure\scripts\run_reference_loaders.sh:8:#                                                       # DATABASE_URL_SYNC_REFERENCE
.\infrastructure\scripts\run_reference_loaders.sh:47:# Reference DB URL must be set (loaders prefer DATABASE_URL_SYNC_REFERENCE
.\infrastructure\scripts\run_reference_loaders.sh:49:if [ -z "${DATABASE_URL_SYNC_REFERENCE:-}" ]; then
.\infrastructure\scripts\run_reference_loaders.sh:54:if [ -z "${DATABASE_URL_SYNC_REFERENCE:-}" ]; then
.\infrastructure\scripts\run_reference_loaders.sh:55:  echo "FATAL: DATABASE_URL_SYNC_REFERENCE not set. Source .env.dev or .env.mock first." >&2
.\infrastructure\scripts\run_reference_loaders.sh:59:# Override DATABASE_URL_SYNC for the loader subprocess so any code that
.\infrastructure\scripts\run_reference_loaders.sh:62:export DATABASE_URL_SYNC="$DATABASE_URL_SYNC_REFERENCE"
.\infrastructure\scripts\run_reference_loaders.sh:63:export DATABASE_URL="$DATABASE_URL_SYNC_REFERENCE"
.\infrastructure\scripts\run_reference_loaders.sh:133:echo "  DATABASE_URL_SYNC_REFERENCE: ${DATABASE_URL_SYNC_REFERENCE%@*}@***"
.\waves\B8.1.1\codex-gate-close.md:52:- `.env.dev` holds environment-specific config values (DATABASE_URL, REDIS_URL, etc.)
.\infrastructure\scripts\seed_reference_shim.py:28:Idempotent: every row uses ON CONFLICT (natural_key) DO UPDATE so re-running
.\infrastructure\scripts\seed_reference_shim.py:277:ON CONFLICT (ndc_11) DO UPDATE SET
.\infrastructure\scripts\seed_reference_shim.py:291:ON CONFLICT (ncpdp_provider_id) DO UPDATE SET
.\infrastructure\scripts\seed_reference_shim.py:413:ON CONFLICT (bin, pcn, group_number) DO UPDATE SET
.\infrastructure\scripts\seed_reference_shim.py:435:ON CONFLICT (npi) DO UPDATE SET
.\infrastructure\scripts\seed_reference_shim.py:450:    raw_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("+psycopg2", "")
.\infrastructure\scripts\lib\cleanup_tier1_ifx_prod_app_policies.sql:16:--   docker compose exec -T postgres psql -U infinityrx -d infinityrx_reference \
.\infrastructure\scripts\setup_fdw.sh:2:# setup_fdw.sh — Wave B7 (Phase 11A) FDW configuration.
.\infrastructure\scripts\setup_fdw.sh:6:#   2. Idempotently create FDW server pointing at infinityrx_reference
.\infrastructure\scripts\setup_fdw.sh:11:#      schema in infinityrx_reference (consolidates `shared`,
.\infrastructure\scripts\setup_fdw.sh:36:# Connects via Postgres unix socket inside the container, so DATABASE_URL
.\infrastructure\scripts\setup_fdw.sh:91:# Iterates all 66 entries in expected_reference_tables.txt and confirms each
.\infrastructure\scripts\setup_fdw.sh:99:  MANIFEST="$LIB_DIR/expected_reference_tables.txt"
.\infrastructure\scripts\setup_fdw.sh:154:  echo "  setup_fdw.sh --verify complete"
.\infrastructure\scripts\setup_fdw.sh:168:: "${DATABASE_URL_SYNC_REFERENCE:?DATABASE_URL_SYNC_REFERENCE must be set}"
.\infrastructure\scripts\setup_fdw.sh:187:COLLISIONS=$(exec_psql_strict "ifx_reference_writer" "infinityrx_reference" "
.\infrastructure\scripts\setup_fdw.sh:208:SOURCE_SCHEMAS=$(exec_psql_strict "ifx_reference_writer" "infinityrx_reference" "
.\infrastructure\scripts\setup_fdw.sh:229:    echo "  --reset: DROP SERVER infinityrx_reference_srv CASCADE"
.\infrastructure\scripts\setup_fdw.sh:230:    exec_psql_run "$ENV_USER" "$ENV_DB" "DROP SERVER IF EXISTS infinityrx_reference_srv CASCADE"
.\infrastructure\scripts\setup_fdw.sh:245:      IF NOT EXISTS (SELECT 1 FROM pg_foreign_server WHERE srvname = 'infinityrx_reference_srv') THEN
.\infrastructure\scripts\setup_fdw.sh:246:        CREATE SERVER infinityrx_reference_srv
.\infrastructure\scripts\setup_fdw.sh:248:          OPTIONS (host '$FDW_HOST', port '5432', dbname 'infinityrx_reference');
.\infrastructure\scripts\setup_fdw.sh:254:    ALTER SERVER infinityrx_reference_srv
.\infrastructure\scripts\setup_fdw.sh:255:      OPTIONS (SET host '$FDW_HOST', SET port '5432', SET dbname 'infinityrx_reference')"
.\infrastructure\scripts\setup_fdw.sh:260:      SERVER infinityrx_reference_srv
.\infrastructure\scripts\setup_fdw.sh:264:      SERVER infinityrx_reference_srv
.\infrastructure\scripts\setup_fdw.sh:273:      SERVER infinityrx_reference_srv
.\infrastructure\scripts\setup_fdw.sh:277:      SERVER infinityrx_reference_srv
.\infrastructure\scripts\setup_fdw.sh:294:    IMPORT_TABLES=$(exec_psql_strict "ifx_reference_writer" "infinityrx_reference" "
.\infrastructure\scripts\setup_fdw.sh:330:        FROM SERVER infinityrx_reference_srv INTO reference"
.\infrastructure\scripts\setup_fdw.sh:344:echo "  setup_fdw.sh complete (mode=$MODE, dry_run=$DRY_RUN)"
.\infrastructure\scripts\seed_admin.py:19:from sqlalchemy import create_engine, text  # noqa: E402
.\infrastructure\scripts\seed_admin.py:23:    "DATABASE_URL_SEED",
.\infrastructure\scripts\seed_admin.py:34:    engine = create_engine(DB_URL, future=True)
.\infrastructure\scripts\seed_admin.py:41:                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
.\infrastructure\scripts\seed_admin.py:52:                ON CONFLICT (id) DO NOTHING
.\infrastructure\scripts\seed_admin.py:70:                    ON CONFLICT (id) DO UPDATE
.\infrastructure\scripts\seed_admin.py:87:                    ON CONFLICT (user_id, role_id) DO NOTHING
.\data\reference\fdb\README.md:635:> **2026-05-07 codex MF5 fix.** An earlier draft of §3.7.2 declared per-table abstractmethods (`parse_rnp3_rows`, `parse_rprdpp0_rows`, `parse_rprdptd0_rows`). Codex correctly observed that this won't scale once Phase C adds NDC master, GCN, MEDID, MAPs, ETC, and therapeutic-class tables — each new table forces an interface amendment + every concrete adapter update. The generic surface below uses a `TableSpec` carrying column order + type coercers + filters; new tables become data, not interface methods. Typed convenience wrappers stay only for hot-path tables (RNP3) where call sites benefit from explicit type hints.
.\data\reference\fdb\README.md:657:class TableSpec:
.\data\reference\fdb\README.md:661:    become new TableSpec values — no FDBAdapter method needed for each one.
.\data\reference\fdb\README.md:680:    parsing pipe-delimited latin-1 rows into typed dicts via TableSpec.
.\data\reference\fdb\README.md:703:        self, drop: FDBDrop, spec: TableSpec, *, source: str = "DB",
.\data\reference\fdb\README.md:705:        """Parse one FDB table per the given TableSpec.
.\data\reference\fdb\README.md:725:The four Phase 8 tables are then expressed as `TableSpec` values (data, not interface methods):
.\data\reference\fdb\README.md:730:RNP3_NDC_PRICE = TableSpec(
.\data\reference\fdb\README.md:745:RPRDPP0_PRODUCT_PRICE = TableSpec(
.\data\reference\fdb\README.md:762:RPRDPTD0_PRICE_TYPE_DESC = TableSpec(
.\data\reference\fdb\README.md:777:RNPTYPD0_NDC_PRICE_TYPE_DESC = TableSpec(  # legacy 2-char-only catalog
.\data\reference\fdb\README.md:823:No typed wrappers for `RPRDPP0`, `RPRDPTD0`, `RNPTYPD0`. Their loaders consume the generic `parse_table` output directly. Phase C / Phase D add new TableSpec values without touching the FDBAdapter interface.
.\data\reference\fdb\README.md:827:| Concern | Per-table abstractmethods (rejected) | TableSpec generic surface (chosen) |
.\data\reference\fdb\README.md:829:| Add a new table (Phase C: GCN, MEDID, etc.) | New abstractmethod + implementation in every concrete adapter | New TableSpec value; no interface change |
.\data\reference\fdb\README.md:833:| Dead/aspirational methods (DDIM, Dosing) | Drift back in over time | TableSpec values are explicit data; no aspirational specs sit unused |
.\data\reference\fdb\README.md:835:#### 3.7.3 Concrete `FDBLocalDropAdapter` implementation
.\data\reference\fdb\README.md:840:class FDBLocalDropAdapter(FDBAdapter):
.\data\reference\fdb\README.md:918:# Inside FDBLocalDropAdapter.parse_table — generic body that works for any TableSpec
.\data\reference\fdb\README.md:920:    self, drop: FDBDrop, spec: TableSpec, *, source: str = "DB",
.\data\reference\fdb\README.md:981:The legacy per-table-method shape (e.g. `parse_rnp3_rows`) was abandoned in §3.7.2 codex MF5 fix — replaced by `parse_table(drop, spec)` + the typed wrapper `parse_rnp3` for the hot path. This block shows what `parse_table`'s body looks like; the same body handles RNP3, RPRDPP0, RPRDPTD0, RNPTYPD0, and any future TableSpec value without modification.
.\data\reference\fdb\README.md:993:Append-only history tables don't need ON CONFLICT machinery — primary-key already includes (ndc_11, price_type, effective_date, as_of_date), so duplicate inserts from a re-run of the same drop violate the unique constraint and are caught at the batch level. The unique constraint is the idempotency mechanism.
.\data\reference\fdb\README.md:1014:        # Phase 8 default: fdb_load_product_prices=False (see §3.7.7).
.\data\reference\fdb\README.md:1015:        if self._config.fdb_load_product_prices:
.\data\reference\fdb\README.md:1041:    fdb_load_product_prices: bool = False
.\data\reference\fdb\README.md:1047:`fdb_awp_source = "strict_swp"` tells `FDBPricingLookup.lookup_at_dos` to skip Tier 2 SWD lookup entirely (use only SWP). `fdb_awp_source = "swd_cascade"` (Phase 8 default) enables Tier 2 SWD lookup on `fdb_ndc_price_history` codes 17/18 — `fdb_load_product_prices` stays False because no product-keyed table is needed for the value lookup. Activating `fdb_load_product_prices=True` unlocks the deferred source-basis recovery path documented in §3.6.3 — strictly Phase 8.5 / Phase C territory.
.\data\reference\fdb\README.md:1757:The parser MUST assign `drop_sequence` from the file line index inside each table file in the UPD/DB zip. The generic `parse_table` (§3.7.4) tracks `enumerate(_stream_pipe_rows(...))` and writes `row["drop_sequence"] = line_idx` for every yielded row — applies uniformly to RNP3 (via the `parse_rnp3` typed wrapper) and every other TableSpec. Line indexes are stable as long as FDB's file order is stable within a drop.
.\data\reference\fdb\README.md:1943:**Ingestion column-set (Phase 8 / C1):** Identity + Lifecycle + Clinical coding = **23 of 68 columns**. The Postgres mirror table `fdb_ndc_master` (alembic `0009_fdb_maps`, full schema in §5.1) MUST include these 23 columns as NOT NULL where the source allows and NULL-safe everywhere else (most RNDC14 columns are NULLable). Remaining 45 columns are CSV-archived to Azure Blob alongside the source RNDC14 dump as audit-only material. **(Codex C8 v1 D2 wording fix.)** When a deferred column becomes hot for adjudication (eg unit-of-measure normalization needs `PS` / `DF` / `AD` / `UD`), the SPEC requires a schema-expansion wave: add the column to `fdb_ndc_master`, extend the §5.0b ingestion TableSpec, and run a backfill from the next FDB drop. The Azure Blob archive is NOT a queryable substitute for hot-path columns — it exists for audit and one-time replay only.
.\data\reference\fdb\README.md:1945:### 5.0b RNDC14 adapter integration via TableSpec
.\data\reference\fdb\README.md:1947:RNDC14 is ingested through the same generic `FDBAdapter.parse_table()` surface defined in §3.7.2. No abstractmethod is added to `FDBAdapter` for NDC master ingestion — the existing TableSpec pattern handles it.
.\data\reference\fdb\README.md:1954:RNDC14_NDC_MSTR = TableSpec(
.\data\reference\fdb\README.md:3280:### 6.0e Adapter integration via TableSpec
.\data\reference\fdb\README.md:3282:Same generic pattern as RNDC14 in §5.0b — three new TableSpec values for the three RNDCAT0-family tables.
.\data\reference\fdb\README.md:3287:RNDCAT0_NDC_ATTRIBUTE = TableSpec(
.\data\reference\fdb\README.md:3304:RNDCTD0_NDC_ATTRIBUTE_TYP_DSC = TableSpec(
.\data\reference\fdb\README.md:3315:RNDCVD0_NDC_ATTRIBUTE_VALU_DSC = TableSpec(
.\data\reference\fdb\README.md:3349:- **A rows** → INSERT … ON CONFLICT DO NOTHING on the 4-column composite PK `(ndc_11, attribute_type_cd, attribute_sn, attribute_value)`.
.\data\reference\fdb\README.md:3652:| `modules/drug-database/src/services/fdb_adapter.py` (extended for new TableSpecs) | 8.1 / 8.2 | ~150 net additions |
.\data\reference\fdb\README.md:4045:### 7.0e Adapter integration via TableSpec
.\data\reference\fdb\README.md:4047:Five new TableSpec values — one per strength-related table. Same generic surface from §3.7.2.
.\data\reference\fdb\README.md:4052:RGCNSTR0_INGREDIENT_STRENGTH = TableSpec(
.\data\reference\fdb\README.md:4084:RPEIGS0_GCNSEQNO_STR_LINK = TableSpec(
.\data\reference\fdb\README.md:4124:RSTRSCD0_STRENGTH_STATUS_DESC = TableSpec(
.\data\reference\fdb\README.md:4132:RSTRTD0_STRENGTH_TYP_DESC = TableSpec(
.\data\reference\fdb\README.md:4140:RSTRUOM0_STRENGTH_UOM = TableSpec(
.\data\reference\fdb\README.md:4969:- **Azure Blob (recommended for production):** customer-licensed FDB data lives outside the repo; restricted-access container; Phase 8 ingester can read from `azure://fdb-data/TEL251759D/<DATE>.TEL251759D/` with the same path semantics. Implementation requires `FDBLocalDropAdapter` swap to `FDBAzureBlobAdapter` — different classes, same interface (§3.7.2 contract).
.\waves\B7.2\ship.md:30:| W3 | Live cluster REVOKE/re-GRANT (14 `pharmacy_dir.dataq_*` tables) | **CLOSED** — `remaining_deps = 0`; `setup_fdw.sh --verify` 66/66 PASS | `94d5f15` |
.\waves\B7.2\ship.md:50:- B7: Phase 11A architecture implemented (single `infinityrx_reference` + FDW; 26.5M rows)
.\waves\B7.2\ship.md:52:- B7.1: Tier 1 RLS migrations env-driven; `setup_fdw.sh --verify` net-new; loader rc; OFAC fix; .sh bits; .gitignore
.\waves\B7.2\evidence.md:48:Commands run against `infinityrx_reference` on live dev cluster (2026-05-10 ~11:45pm EDT):
.\waves\B7.2\evidence.md:62:**setup_fdw.sh --verify post-W3:**
.\waves\B7.2\evidence.md:69:  setup_fdw.sh --verify complete
.\scripts\teardown_ifx_dev_tenant.py:10:    DATABASE_URL_SYNC=... .venv/bin/python scripts/teardown_ifx_dev_tenant.py
.\scripts\teardown_ifx_dev_tenant.py:24:from sqlalchemy import create_engine, text  # noqa: E402
.\scripts\teardown_ifx_dev_tenant.py:42:    url = os.environ.get("DATABASE_URL_SYNC")
.\scripts\teardown_ifx_dev_tenant.py:44:        sys.stderr.write("ERROR: DATABASE_URL_SYNC not set.\n")
.\scripts\teardown_ifx_dev_tenant.py:58:    engine = create_engine(_engine_url(), future=True)
.\scripts\smoke_test_b8.py:16:    DATABASE_URL_SYNC=postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev \\
.\scripts\smoke_test_b8.py:40:os.environ.setdefault("DATABASE_URL",
.\scripts\smoke_test_b8.py:42:os.environ.setdefault("DATABASE_URL_SYNC",
.\scripts\smoke_test_b8.py:83:    print(f"DB:      {os.environ['DATABASE_URL_SYNC'][:60]}...")
.\scripts\smoke_test_b8.py:206:            sync_url = os.environ["DATABASE_URL_SYNC"]
.\scripts\seed_ifx_dev_tenant.py:29:Connection: DATABASE_URL_SYNC env var. Default:
.\scripts\seed_ifx_dev_tenant.py:36:    DATABASE_URL_SYNC=... .venv/bin/python scripts/seed_ifx_dev_tenant.py
.\scripts\seed_ifx_dev_tenant.py:75:from sqlalchemy import create_engine, text  # noqa: E402
.\scripts\seed_ifx_dev_tenant.py:140:    url = os.environ.get("DATABASE_URL_SYNC")
.\scripts\seed_ifx_dev_tenant.py:143:            "ERROR: DATABASE_URL_SYNC not set. Example:\n"
.\scripts\seed_ifx_dev_tenant.py:144:            "  export DATABASE_URL_SYNC=postgresql+psycopg2://ifx_dev_admin:"
.\scripts\seed_ifx_dev_tenant.py:154:    Each insert uses ON CONFLICT DO NOTHING with the deterministic PK,
.\scripts\seed_ifx_dev_tenant.py:176:            ON CONFLICT (id) DO NOTHING
.\scripts\seed_ifx_dev_tenant.py:216:            ON CONFLICT (id) DO NOTHING
.\scripts\seed_ifx_dev_tenant.py:256:            ON CONFLICT (id) DO NOTHING
.\scripts\seed_ifx_dev_tenant.py:292:            ON CONFLICT (id) DO NOTHING
.\scripts\seed_ifx_dev_tenant.py:325:            ON CONFLICT (id) DO NOTHING
.\scripts\seed_ifx_dev_tenant.py:352:            ON CONFLICT (id) DO NOTHING
.\scripts\seed_ifx_dev_tenant.py:389:            ON CONFLICT (id) DO NOTHING
.\scripts\seed_ifx_dev_tenant.py:420:            ON CONFLICT (id) DO NOTHING
.\scripts\seed_ifx_dev_tenant.py:461:            ON CONFLICT (id) DO NOTHING
.\scripts\seed_ifx_dev_tenant.py:484:    engine = create_engine(_engine_url(), future=True)
.\tests\test_sam_cross_ref.py:24:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\tests\test_sam_cross_ref.py:25:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\scripts\load_rxnorm.py:24:    DATABASE_URL_SYNC — set by switch_env.sh
.\scripts\load_rxnorm.py:53:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_rxnorm.py:56:            "DATABASE_URL_SYNC not set. "
.\scripts\load_rxnorm.py:95:    from sqlalchemy import create_engine, text
.\scripts\load_rxnorm.py:101:    engine = create_engine(db_url, echo=False)
.\tests\test_common.py:200:    monkeypatch.delenv("DATABASE_URL_SYNC", raising=False)
.\tests\test_common.py:201:    monkeypatch.delenv("DATABASE_URL", raising=False)
.\tests\test_common.py:202:    with pytest.raises(RuntimeError, match="DATABASE_URL"):
.\tests\test_common.py:214:    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql+psycopg2://u:p@h/d")
.\tests\test_common.py:227:    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql+asyncpg://u:p@h/d")
.\tests\test_common.py:240:    monkeypatch.delenv("DATABASE_URL_SYNC", raising=False)
.\tests\test_common.py:241:    monkeypatch.setenv("DATABASE_URL", "postgresql://plain/db")
.\tests\test_column_width_drift.py:16:Test is skipped when ``DATABASE_URL_SYNC`` is not configured so local
.\tests\test_column_width_drift.py:36:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL", "")
.\tests\test_column_width_drift.py:43:        pytest.skip("DATABASE_URL_SYNC not configured (or SQLite) — drift "
.\tests\test_column_width_drift.py:76:        pytest.skip("DATABASE_URL_SYNC not configured")
.\scripts\load_rxnorm [conflicted].py:24:    DATABASE_URL_SYNC — set by switch_env.sh
.\scripts\load_rxnorm [conflicted].py:53:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_rxnorm [conflicted].py:56:            "DATABASE_URL_SYNC not set. "
.\scripts\load_rxnorm [conflicted].py:95:    from sqlalchemy import create_engine, text
.\scripts\load_rxnorm [conflicted].py:101:    engine = create_engine(db_url, echo=False)
.\scripts\load_orange_book.py:20:    DATABASE_URL_SYNC — set by switch_env.sh
.\scripts\load_orange_book.py:46:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_orange_book.py:49:            "DATABASE_URL_SYNC not set. "
.\scripts\load_orange_book.py:91:    from sqlalchemy import create_engine, text
.\scripts\load_orange_book.py:97:    engine = create_engine(db_url, echo=False)
.\scripts\load_orange_book [conflicted].py:20:    DATABASE_URL_SYNC — set by switch_env.sh
.\scripts\load_orange_book [conflicted].py:46:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_orange_book [conflicted].py:49:            "DATABASE_URL_SYNC not set. "
.\scripts\load_orange_book [conflicted].py:91:    from sqlalchemy import create_engine, text
.\scripts\load_orange_book [conflicted].py:97:    engine = create_engine(db_url, echo=False)
.\scripts\load_opt_out.py:18:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_opt_out.py:43:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_opt_out.py:46:            "DATABASE_URL_SYNC not set. "
.\scripts\load_opt_out.py:54:    from sqlalchemy import create_engine, text
.\scripts\load_opt_out.py:60:    engine = create_engine(db_url, echo=False)
.\scripts\load_opt_out [conflicted].py:18:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_opt_out [conflicted].py:43:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_opt_out [conflicted].py:46:            "DATABASE_URL_SYNC not set. "
.\scripts\load_opt_out [conflicted].py:54:    from sqlalchemy import create_engine, text
.\scripts\load_opt_out [conflicted].py:60:    engine = create_engine(db_url, echo=False)
.\scripts\load_oig_leie.py:18:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_oig_leie.py:47:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_oig_leie.py:50:            "DATABASE_URL_SYNC not set. "
.\scripts\load_oig_leie.py:58:    from sqlalchemy import create_engine, text
.\scripts\load_oig_leie.py:64:    engine = create_engine(db_url, echo=False)
.\tests\scripts\test_loader_env_precedence.py:5:DATABASE_URL_SYNC_REFERENCE precedence introduced in C3.
.\tests\scripts\test_loader_env_precedence.py:8:    DATABASE_URL_SYNC_REFERENCE
.\tests\scripts\test_loader_env_precedence.py:9:        > DATABASE_URL_SYNC
.\tests\scripts\test_loader_env_precedence.py:10:        > DATABASE_URL
.\tests\scripts\test_loader_env_precedence.py:13:DATABASE_URL_SYNC; existing direct invocations don't break.
.\tests\scripts\test_loader_env_precedence.py:47:REF_URL = "postgresql://refw:x@h/infinityrx_reference"
.\tests\scripts\test_loader_env_precedence.py:55:    """When DATABASE_URL_SYNC_REFERENCE is set, _resolve_db_url returns it."""
.\tests\scripts\test_loader_env_precedence.py:60:    monkeypatch.setenv("DATABASE_URL_SYNC_REFERENCE", REF_URL)
.\tests\scripts\test_loader_env_precedence.py:61:    monkeypatch.setenv("DATABASE_URL_SYNC", ENV_URL)
.\tests\scripts\test_loader_env_precedence.py:62:    monkeypatch.setenv("DATABASE_URL", ENV_URL)
.\tests\scripts\test_loader_env_precedence.py:73:    """When only DATABASE_URL_SYNC is set, fall back to it."""
.\tests\scripts\test_loader_env_precedence.py:75:    monkeypatch.delenv("DATABASE_URL_SYNC_REFERENCE", raising=False)
.\tests\scripts\test_loader_env_precedence.py:76:    monkeypatch.setenv("DATABASE_URL_SYNC", ENV_URL)
.\tests\scripts\test_loader_env_precedence.py:77:    monkeypatch.setenv("DATABASE_URL", ENV_URL)
.\tests\scripts\test_loader_env_precedence.py:101:    monkeypatch.setenv("DATABASE_URL_SYNC_REFERENCE", REF_URL)
.\tests\scripts\test_loader_env_precedence.py:102:    monkeypatch.setenv("DATABASE_URL_SYNC", ENV_URL)
.\tests\scripts\test_loader_env_precedence.py:103:    monkeypatch.setenv("DATABASE_URL", ENV_URL)
.\tests\scripts\test_loader_env_precedence.py:113:    """Without REFERENCE, fall back to DATABASE_URL_SYNC."""
.\tests\scripts\test_loader_env_precedence.py:125:    monkeypatch.delenv("DATABASE_URL_SYNC_REFERENCE", raising=False)
.\tests\scripts\test_loader_env_precedence.py:126:    monkeypatch.setenv("DATABASE_URL_SYNC", ENV_URL)
.\tests\scripts\test_loader_env_precedence.py:127:    monkeypatch.setenv("DATABASE_URL", ENV_URL)
.\scripts\load_oig_leie [conflicted].py:18:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_oig_leie [conflicted].py:47:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_oig_leie [conflicted].py:50:            "DATABASE_URL_SYNC not set. "
.\scripts\load_oig_leie [conflicted].py:58:    from sqlalchemy import create_engine, text
.\scripts\load_oig_leie [conflicted].py:64:    engine = create_engine(db_url, echo=False)
.\scripts\load_ofac.py:19:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_ofac.py:42:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_ofac.py:45:            "DATABASE_URL_SYNC not set. "
.\scripts\load_ofac.py:53:    from sqlalchemy import create_engine, text
.\scripts\load_ofac.py:59:    engine = create_engine(db_url, echo=False)
.\scripts\load_ofac [conflicted].py:19:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_ofac [conflicted].py:42:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_ofac [conflicted].py:45:            "DATABASE_URL_SYNC not set. "
.\scripts\load_ofac [conflicted].py:53:    from sqlalchemy import create_engine, text
.\scripts\load_ofac [conflicted].py:59:    engine = create_engine(db_url, echo=False)
.\scripts\load_nppes.py:64:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_nppes.py:67:            "DATABASE_URL_SYNC not set. "
.\scripts\load_nppes.py:119:    from sqlalchemy import create_engine, text
.\scripts\load_nppes.py:129:    engine = create_engine(db_url, echo=False)
.\scripts\load_nppes.py:187:    from sqlalchemy import create_engine, text
.\scripts\load_nppes.py:193:    engine = create_engine(db_url, echo=False)
.\scripts\load_nppes [conflicted].py:64:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_nppes [conflicted].py:67:            "DATABASE_URL_SYNC not set. "
.\scripts\load_nppes [conflicted].py:119:    from sqlalchemy import create_engine, text
.\scripts\load_nppes [conflicted].py:129:    engine = create_engine(db_url, echo=False)
.\scripts\load_nppes [conflicted].py:187:    from sqlalchemy import create_engine, text
.\scripts\load_nppes [conflicted].py:193:    engine = create_engine(db_url, echo=False)
.\scripts\load_new_sources.py:71:    from sqlalchemy import create_engine
.\scripts\load_new_sources.py:74:    db_url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_new_sources.py:76:        print("DATABASE_URL_SYNC required", file=sys.stderr)
.\scripts\load_new_sources.py:79:    engine = create_engine(db_url, echo=False)
.\scripts\load_ncpdp.py:58:        os.environ.get("DATABASE_URL_SYNC_REFERENCE")
.\scripts\load_ncpdp.py:59:        or os.environ.get("DATABASE_URL_SYNC")
.\scripts\load_ncpdp.py:60:        or os.environ.get("DATABASE_URL")
.\scripts\load_ncpdp.py:64:            "DATABASE_URL_SYNC not set. "
.\scripts\load_ncpdp.py:73:    from sqlalchemy import create_engine, text
.\scripts\load_ncpdp.py:80:    engine = create_engine(_resolve_db_url(), echo=False)
.\scripts\load_medicaid_bins.py:21:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_medicaid_bins.py:46:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_medicaid_bins.py:49:            "DATABASE_URL_SYNC not set. "
.\scripts\load_medicaid_bins.py:57:    from sqlalchemy import create_engine, text
.\scripts\load_medicaid_bins.py:66:    engine = create_engine(db_url, echo=False)
.\tests\repo\test_no_local_date_today_in_pg_date_tests.py:52:from sqlalchemy import create_engine, text
.\tests\repo\test_no_local_date_today_in_pg_date_tests.py:68:_DATABASE_URL_SYNC = os.environ.get(
.\tests\repo\test_no_local_date_today_in_pg_date_tests.py:69:    "DATABASE_URL_SYNC",
.\tests\repo\test_no_local_date_today_in_pg_date_tests.py:72:_DATABASE_URL_PSYCOPG = _DATABASE_URL_SYNC.replace(
.\tests\repo\test_no_local_date_today_in_pg_date_tests.py:79:        psycopg2.connect(_DATABASE_URL_PSYCOPG).close()
.\tests\repo\test_no_local_date_today_in_pg_date_tests.py:109:    return create_engine(_DATABASE_URL_SYNC, pool_pre_ping=True)
.\scripts\load_medicaid_bins [conflicted].py:21:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_medicaid_bins [conflicted].py:46:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_medicaid_bins [conflicted].py:49:            "DATABASE_URL_SYNC not set. "
.\scripts\load_medicaid_bins [conflicted].py:57:    from sqlalchemy import create_engine, text
.\scripts\load_medicaid_bins [conflicted].py:66:    engine = create_engine(db_url, echo=False)
.\scripts\load_icd10.py:35:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_icd10.py:38:            "DATABASE_URL_SYNC not set. "
.\scripts\load_icd10.py:46:    from sqlalchemy import create_engine, text
.\scripts\load_icd10.py:52:    engine = create_engine(db_url, echo=False, future=True)
.\scripts\load_icd10 [conflicted].py:35:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_icd10 [conflicted].py:38:            "DATABASE_URL_SYNC not set. "
.\scripts\load_icd10 [conflicted].py:46:    from sqlalchemy import create_engine, text
.\scripts\load_icd10 [conflicted].py:52:    engine = create_engine(db_url, echo=False, future=True)
.\scripts\load_hcpcs.py:37:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_hcpcs.py:40:            "DATABASE_URL_SYNC not set. "
.\scripts\load_hcpcs.py:48:    from sqlalchemy import create_engine, text
.\scripts\load_hcpcs.py:54:    engine = create_engine(db_url, echo=False, future=True)
.\scripts\load_hcpcs [conflicted].py:37:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_hcpcs [conflicted].py:40:            "DATABASE_URL_SYNC not set. "
.\scripts\load_hcpcs [conflicted].py:48:    from sqlalchemy import create_engine, text
.\scripts\load_hcpcs [conflicted].py:54:    engine = create_engine(db_url, echo=False, future=True)
.\scripts\load_fdb.py:4:`FDBLocalDropAdapter` and writes to `fdb_price_type_desc` +
.\scripts\load_fdb.py:22:    DATABASE_URL_SYNC — set by switch_env.sh
.\scripts\load_fdb.py:47:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_fdb.py:50:            "DATABASE_URL_SYNC not set. "
.\scripts\load_fdb.py:86:    from sqlalchemy import create_engine
.\scripts\load_fdb.py:88:    from drug_database.services.fdb_adapter import FDBLocalDropAdapter
.\scripts\load_fdb.py:97:    engine = create_engine(db_url)
.\scripts\load_fdb.py:102:        adapter = FDBLocalDropAdapter(root)
.\scripts\load_fda_rems.py:19:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_fda_rems.py:44:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_fda_rems.py:47:            "DATABASE_URL_SYNC not set. "
.\scripts\load_fda_rems.py:55:    from sqlalchemy import create_engine, text
.\scripts\load_fda_rems.py:61:    engine = create_engine(db_url, echo=False)
.\scripts\load_fda_rems [conflicted].py:19:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_fda_rems [conflicted].py:44:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_fda_rems [conflicted].py:47:            "DATABASE_URL_SYNC not set. "
.\scripts\load_fda_rems [conflicted].py:55:    from sqlalchemy import create_engine, text
.\scripts\load_fda_rems [conflicted].py:61:    engine = create_engine(db_url, echo=False)
.\scripts\load_fda_ndc.py:21:    DATABASE_URL_SYNC — set by switch_env.sh
.\scripts\load_fda_ndc.py:47:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_fda_ndc.py:50:            "DATABASE_URL_SYNC not set. "
.\scripts\load_fda_ndc.py:92:    from sqlalchemy import create_engine, text
.\scripts\load_fda_ndc.py:98:    engine = create_engine(db_url, echo=False)
.\scripts\load_fda_ndc [conflicted].py:21:    DATABASE_URL_SYNC — set by switch_env.sh
.\scripts\load_fda_ndc [conflicted].py:47:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_fda_ndc [conflicted].py:50:            "DATABASE_URL_SYNC not set. "
.\scripts\load_fda_ndc [conflicted].py:92:    from sqlalchemy import create_engine, text
.\scripts\load_fda_ndc [conflicted].py:98:    engine = create_engine(db_url, echo=False)
.\scripts\load_cms_nadac.py:17:    DATABASE_URL_SYNC — set by switch_env.sh
.\scripts\load_cms_nadac.py:43:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_cms_nadac.py:46:            "DATABASE_URL_SYNC not set. "
.\scripts\load_cms_nadac.py:80:    from sqlalchemy import create_engine, text
.\scripts\load_cms_nadac.py:86:    engine = create_engine(db_url, echo=False)
.\scripts\load_cms_nadac [conflicted].py:17:    DATABASE_URL_SYNC — set by switch_env.sh
.\scripts\load_cms_nadac [conflicted].py:43:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_cms_nadac [conflicted].py:46:            "DATABASE_URL_SYNC not set. "
.\scripts\load_cms_nadac [conflicted].py:80:    from sqlalchemy import create_engine, text
.\scripts\load_cms_nadac [conflicted].py:86:    engine = create_engine(db_url, echo=False)
.\scripts\load_cms_asp.py:18:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_cms_asp.py:44:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_cms_asp.py:47:            "DATABASE_URL_SYNC not set. "
.\scripts\load_cms_asp.py:90:    from sqlalchemy import create_engine, text
.\scripts\load_cms_asp.py:96:    engine = create_engine(db_url, echo=False)
.\scripts\load_cms_asp [conflicted].py:18:    DATABASE_URL_SYNC - set by switch_env.sh
.\scripts\load_cms_asp [conflicted].py:44:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\load_cms_asp [conflicted].py:47:            "DATABASE_URL_SYNC not set. "
.\scripts\load_cms_asp [conflicted].py:90:    from sqlalchemy import create_engine, text
.\scripts\load_cms_asp [conflicted].py:96:    engine = create_engine(db_url, echo=False)
.\tests\integration\test_validation_run_cli.py:7:Skipped cleanly when DATABASE_URL_SYNC is not set.
.\tests\integration\test_validation_run_cli.py:29:DATABASE_URL_SYNC = os.environ.get(
.\tests\integration\test_validation_run_cli.py:30:    "DATABASE_URL_SYNC",
.\tests\integration\test_validation_run_cli.py:33:DATABASE_URL_PSYCOPG = DATABASE_URL_SYNC.replace("postgresql+psycopg2://", "postgresql://", 1)
.\tests\integration\test_validation_run_cli.py:38:        psycopg2.connect(DATABASE_URL_PSYCOPG).close()
.\tests\integration\test_validation_run_cli.py:49:    monkeypatch.setenv("DATABASE_URL_SYNC", DATABASE_URL_SYNC)
.\tests\integration\test_payment_processing_smoke.py:19:from sqlalchemy import create_engine, text
.\tests\integration\test_payment_processing_smoke.py:31:    engine = create_engine(integration_postgres["admin_url_sync"], future=True)
.\tests\integration\test_core_platform_smoke.py:16:from sqlalchemy import create_engine, text
.\tests\integration\test_core_platform_smoke.py:31:    engine = create_engine(integration_postgres["admin_url_sync"], future=True)
.\scripts\cleanup_test_tenant.py:12:Requires DATABASE_URL_SYNC (set by switch_env.sh dev or .env.dev).
.\scripts\cleanup_test_tenant.py:41:    if not os.environ.get("DATABASE_URL_SYNC"):
.\scripts\cleanup_test_tenant.py:43:            "ERROR: DATABASE_URL_SYNC not set. Run `source infrastructure/"
.\tests\integration\test_billing_smoke.py:23:from sqlalchemy import create_engine, text
.\tests\integration\test_billing_smoke.py:44:    engine = create_engine(integration_postgres["admin_url_sync"], future=True)
.\scripts\bench_nppes_satellite.py:59:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\bench_nppes_satellite.py:62:            "DATABASE_URL_SYNC not set. "
.\scripts\bench_nppes_satellite.py:177:    from sqlalchemy import create_engine
.\scripts\bench_nppes_satellite.py:181:    engine = create_engine(db_url, echo=False, future=True)
.\tests\integration\conftest.py:174:    state + explicit DATABASE_URL_SYNC. This matches how dev/CI runs
.\tests\integration\conftest.py:178:    env["DATABASE_URL_SYNC"] = tenant_url
.\tests\integration\conftest.py:179:    # DATABASE_URL is used by some module env.py files. Keep it in sync
.\tests\integration\conftest.py:181:    env["DATABASE_URL"] = tenant_url.replace("postgresql://", "postgresql+asyncpg://", 1)
.\tests\integration\conftest.py:250:        # Wave 21b: export DATABASE_URL_SYNC so pre-Wave-21 tests that
.\tests\integration\conftest.py:254:        _prev_sync = os.environ.get("DATABASE_URL_SYNC")
.\tests\integration\conftest.py:255:        _prev_async = os.environ.get("DATABASE_URL")
.\tests\integration\conftest.py:256:        os.environ["DATABASE_URL_SYNC"] = tenant_url
.\tests\integration\conftest.py:257:        os.environ["DATABASE_URL"] = tenant_url.replace(
.\tests\integration\conftest.py:275:                os.environ.pop("DATABASE_URL_SYNC", None)
.\tests\integration\conftest.py:277:                os.environ["DATABASE_URL_SYNC"] = _prev_sync
.\tests\integration\conftest.py:279:                os.environ.pop("DATABASE_URL", None)
.\tests\integration\conftest.py:281:                os.environ["DATABASE_URL"] = _prev_async
.\scripts\bench_fdb_lookup.py:21:    1 — plan regression detected OR DATABASE_URL_SYNC unset.
.\scripts\bench_fdb_lookup.py:217:            "Does NOT require DATABASE_URL_SYNC."
.\scripts\bench_fdb_lookup.py:239:    # Resolve DATABASE_URL_SYNC — required for live run
.\scripts\bench_fdb_lookup.py:240:    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\scripts\bench_fdb_lookup.py:243:            "ERROR: DATABASE_URL_SYNC is not set.\n"
.\scripts\bench_fdb_lookup.py:255:        from sqlalchemy import create_engine, text
.\scripts\bench_fdb_lookup.py:286:    engine = create_engine(db_url, echo=False)
.\scripts\audit_column_widths.py:97:    url = os.environ["DATABASE_URL_SYNC"]
.\scripts\apply_rls.py:463:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL", "")
.\scripts\apply_rls.py:465:        print("ERROR: DATABASE_URL_SYNC (or DATABASE_URL) must be set", file=sys.stderr)
.\scripts\apply_rls [conflicted].py:464:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL", "")
.\scripts\apply_rls [conflicted].py:466:        print("ERROR: DATABASE_URL_SYNC (or DATABASE_URL) must be set", file=sys.stderr)
.\tasks\loader-bugs.md:111:  syntactically correct (`INSERT ... ON CONFLICT DO UPDATE` via
.\tasks\loader-bugs.md:115:     unique constraint on the live schema, causing the ON CONFLICT to
.\tasks\loader-bugs.md:136:- **Original tracking note**: "missing ON CONFLICT" — this was wrong.
.\tasks\loader-bugs.md:535:  shim's 10 rows still exist and the loader's ON CONFLICT DO UPDATE
.\infrastructure\scripts\switch_env.sh:53:echo "  DATABASE_URL    : ${DATABASE_URL%@*}@***"
.\infrastructure\scripts\switch_env [conflicted].sh:58:echo "  DATABASE_URL    : ${DATABASE_URL%@*}@***"
.\data\reference\nppes\README.md:89:│ INSERT ... ON CONFLICT     │   │ prescriber_taxonomies                    │
.\data\reference\nppes\README.md:100:  `ON CONFLICT ... DO UPDATE`. Late source changes re-apply cleanly on
.\data\reference\nppes\README.md:133:`INSERT ... VALUES (row₁),(row₂),...(rowₙ) ON CONFLICT DO UPDATE`
.\data\reference\nppes\README.md:167:5. Upsert: `INSERT INTO target SELECT * FROM stg ON CONFLICT
.\docs\audit\CLAUDE_archive_pre_wave_42.md:59:| adjudication-engine | 4 | In progress | 3,071 LOC across 13-step adjudication pipeline (member → eligibility → plan → pricing → history → overrides → rules → DUR → COB → accumulator → pricing), `ParsedClaim` hierarchy with NCPDP `HeaderSegment.bin_number` captured, NCPDP adapter, API routes, 6 ORM models in `tables.py` (claim_transactions + 5 satellite tables). **Wave 26 Phase A-prep through C.4 foundation** (compacted pre-Wave-27; see git history for per-phase detail): alembic baseline schema (6 tables) + check constraints + RLS; Phase A.2 `/admin/inject-claim` spine wiring `adjudicate()` + `persist_claim_transaction` under tenant context; Phase B `claim.adjudicated` event publishing with billing-consumer aliases; Phase C.2 `build_rules_executor` dispatching via `rule_cache.get_or_load` → `rule_loader.load_tenant_program_rules` → `execute_pipeline` (Phase A.2's hard-coded 4-rule list deleted — empty `rule_instances` adjudicates clean); Phase C.3 FLAG architecture as orthogonal metadata with alembic 0004 `claim_transactions.flags JSONB` + GIN index + is-array CHECK, hoisted before REJECT short-circuit so flags survive rejection; Phase C.4 reference-data rules wired into claim-time pipeline via `build_context()` reading pcn/group_number/occ_code/date_of_service and `build_rules_executor()` exposing `ctx.db_session` inside `session.begin()`. Phase C.7 PRE-A through PRE-D ClaimContext extensions (upstream_claim, submission_clarification_codes, network_tier_at_pharmacy, is_first_fill_for_patient_drug, preflight_flags). Admin surface uses JSON summary; wire response builders in ncpdp-core remain for the TCP-listener path (see Wave 27 Sub-wave 4 for listener implementation). **Wave 26 Phase C.12-C.17 M1 landed alembic 0006 + `claim_transactions.program_id UUID nullable` + `idx_claim_tenant_member_drug_program` composite index supporting refill-too-soon history lookups. New service `src/services/accumulator_writer.py::apply_accumulator_for_claim` runs inside the same session.begin() block as persist_claim_transaction — on paid claims with program_pay > 0 increments PRE-C accumulators (fills_used + dollars_used); on B2 reversals decrements by the matching prior paid claim's program_pay (scoped by tenant+program+member+drug+year-of-DOS). Never raises — on failure attaches flag (accumulator_write_failed / accumulator_skip_no_member / accumulator_skip_reversal_no_original) so claim lands. Cross-module fix in shared.program_config_queries.accumulator.increment_accumulator: negative deltas take UPDATE-only path because Postgres evaluates CHECK constraints on the candidate INSERT tuple BEFORE ON CONFLICT resolution, so the prior INSERT ON CONFLICT DO UPDATE failed ck_accumulator_dollars_nonnegative on -476 even though the UPDATE would compute 476+(-476)=0. 6 new integration tests (paid increments, REJECT no-increment, cross-year separate buckets, B2 reversal decrements to 0/0, B2 with no prior flag, two paid claims accumulate).** **Wave 27 (platform hardening + operator tooling + pharmacy ingestion + cleanup, 2026-04-24) shipped 4 sub-waves: SW1 cleanup (shared.db.rule_instance_seeding helper consolidating 12 inline INSERT patterns across test files with time-rot-immune DEFAULT_EFFECTIVE_DATE 2020-01-01; docs/audit/wave-27-rule-registry-audit.md classifies 32 RULE_TYPE_REGISTRY entries as 19 BRD-canonical + 9 pre-BRD primitives deprecated + 4 Phase A baseline; CLAUDE.md compaction of pre-C.8 wave detail). SW2 pharmacy TIN/UEI/CAGE ingestion (pharmacy-directory alembic 0006 added uei varchar(12) + cage_code varchar(5) columns with partial indexes; federal_tax_id pre-existed as varchar(9) TIN; shared/data_ingestion/pharmacy_tin_uei.py CSV upsert stub with 6 tests; PharmacyExclusionRule extended with new `_lookup_pharmacy_entity_exclusion` helper cross-referencing shared.sam_exclusions by UEI/CAGE in addition to the existing NPI path; PharmacyMetadata extended with tin/uei/cage_code; 5 new E2E tests). SW3 operator-portal API (new /admin/config/simulate-change-set endpoint replays recent claim history via PRE-F regress_scenarios against date_a=today vs date_b=change_set.effective_date returning per-claim diff; /admin/config/apply-change-set triggers PRE-E atomic apply; platform_admin role gated; tenant-scoped; 8 integration tests; portal is React/Next.js, endpoints consumed by portal team). SW4 hardening (FDB adapter: shared/fdb/README.md documents vendor-spec acquisition, interface already production-stable from PRE-G; NCPDP TCP listener: new src/services/tcp_listener.py with asyncio.start_server + parse_wire_request adapter helper returning tuple[ParsedClaim, typed_Transaction] + adjudicate → persist → respond + reject-response framing for malformed / unrouted / oversized / timeout cases + env-var routing via IFX_NCPDP_LISTEN_TENANT_ID/PROGRAM_ID + 4 integration tests including real paid_request.bin round trip; latent ncpdp_adapter bugs fixed: RawHeader attribute names bin_number→bin and version→version_release, PharmacyProvider.provider_id→service_provider_id both via getattr shims; transaction_code validation against canonical NCPDP set so garbage bytes reject before persistence; cross-module events: 5 pre-existing failures FIXED — sys.path shim for reclaimrx, BILLING_DATABASE_URL env from DATABASE_URL_SYNC, no-op MagicMock session_factory for wire_consumers in bus-wire-verification tests). Totals: 232 adjudication-engine + 333 rules-engine + 1240 ncpdp-core + all shared/tests subdirs green in isolation. Pre-existing 3 test_network.py cross-test-pollution failures remain known-issue (pass in isolation, fail only when run alongside shared/tests/events/).** **Wave 26 Phase C.24-C.26 (BRD catalog completion — 19/19 rule types) added 3 final-tier rules: `high_deductible_mitigation_rule` (C.24, Tier 4 HDHP, NCPDP 70 default, OCC 00/08 scope, reads ctx.upstream_claim.patient_responsibility_amount via PRE-A.5 for HDHP-primary threshold check BRD-observed $570, pharmacy-role-aware dual-message templating via new `classify_pharmacy_in_program` shared helper on program_hub_spoke_pairs returning hub/spoke/unknown with hub-wins ordering, unknown defaults to spoke template for safer redirect guidance, hub_pharmacy_allowed flag controls OCC 00 path, fail-safe FLAG+PASS when OCC 08 missing upstream NQ), `required_fields_rule` (C.26, Tier 6 generic, NCPDP 01 default, iterates required_fields via `shared.utils.ncpdp_field_lookup` reused from C.23 M3 no duplication, first-missing-wins sequential-rejection convention, unknown field code → config-error REJECT), `medication_specific_response_message_rule` (C.25, Tier 6, smallest rule, purely additive never REJECTs, PASS with FlagEntry carrying rendered `response_message_template` when ctx.ndc ∈ target_ndcs, severity parameterizable default informational, flag persists to claim_transactions.flags via Phase C.3 hoist). New shared helper `classify_pharmacy_in_program(session, program_id, npi, dos)` single-query role determination from program_hub_spoke_pairs, effective-dated. RULE_TYPE_REGISTRY now 31 entries. **BRD coverage closed at 19/19 rule types**: Tier 1 10 rules (C.9-C.17), Tier 2 5 rules (C.18-C.22), Tier 3 1 rule (C.23), Tier 4 1 rule (C.24), Tier 6 2 rules (C.25-C.26), Tier 5 3 legacy exclusion rules (C.4-C.6). Time-rot sweep across 4 Phase C test files (C.3/C.4/C.5/C.6) swapped `effective_date = CURRENT_DATE - 1` for `DATE '2020-01-01'` — same bug Phase C.8 fixed in shared/db/test_helpers; manifested only after 2026-04-22 as wall-clock time passed the hardcoded DOS. 32 new unit tests + 8 E2E tests + 6 real-DB classify helper tests. 215 adjudication-engine + 333 rules-engine tests pass.** **Wave 26 Phase C.23 added `pa_timer_rule` (PriorAuthorizationTimerRule) — BRD-declared most complex single rule (XL). 5-phase derived state machine (NOT_STARTED/ACTIVE/EXPIRED/BYPASSED/RESET_REQUIRED) over PRE-C member_program_flags rows keyed on `pa_timer:{drug_brand}` — per-drug isolation so DRUG_A's timer doesn't affect DRUG_B. Derivation priority BYPASSED > RESET_REQUIRED > EXPIRED > ACTIVE > NOT_STARTED; empty current BIN never triggers reset. New shared module `shared/program_config_queries/pa_timer.py` with helpers `read_pa_timer_state` / `write_pa_timer_flag` / `apply_scc_bypass` / `clear_pa_timer_flag` / PaTimerState dataclass with `time_remaining(now)` clamped at zero. PRE-C `set_member_flag` extended with optional `effective_from` kwarg + `get_member_flag` gained stable tiebreakers `, created_at DESC, id DESC` because Postgres freezes NOW() per transaction and two same-tx writes tied on effective_from returned non-deterministic rows. New `shared/utils/ncpdp_field_lookup.py` generic resolver mapping NCPDP field codes (101-A1 BIN, 411-DB prescriber NPI, 420-DK SCC, 304-C4 DOB, etc.) to ClaimContext attributes via `NCPDP_FIELD_TO_CTX_ATTR` dict + `lookup_field` / `is_field_populated`; unmapped codes raise UnknownNcpdpFieldError so rule-config typos surface loudly. Rule evaluation: (1) scope guard (FLAG+PASS on missing member/drug/program), (2) SCC bypass check (any ctx.submission_clarification_codes in bypass_scc_codes → apply_scc_bypass + PASS, runs BEFORE required-fields so bypass honors "pharmacy has PA" signal), (3) required-fields validation (distinct required_field_reject_code default 01 so pharmacy doesn't wait 72h for data-completeness issue), (4) state dispatch. NOT_STARTED and RESET_REQUIRED write a fresh flag + REJECT countdown 72h; RESET_REQUIRED also attaches `pa_timer_reset_on_bin_change` observability flag. ACTIVE computes hours/minutes from expires_at - now. EXPIRED and BYPASSED PASS. Templated reject message supports both `{hoursLeft}`/`{minutesLeft}` (BRD-native brace-form) and `[HOURS_LEFT]`/`[MINUTES_LEFT]` (PRE-D bracket-form) via _render_pa_template shared context. NCPDP 75 Prior Authorization Required (parameterizable). RULE_TYPE_REGISTRY now 28 entries. 27 new tests (16 PA timer state machine real-DB + 11 field lookup unit) + 21 rule unit tests + 5 E2E multi-claim sequence tests. 301 rules-engine + 207 adjudication-engine tests pass.** **Wave 26 Phase C.18-C.22 added 5 Tier 2 network + routing rules per BRD synthesis: `network_pharmacy_validation_rule` (C.18, NCPDP MH, reads ctx.network_tier_at_pharmacy from PRE-B, strict/flag_only modes, reject_code parameter override), `consignment_redirect_rule` (C.19, NCPDP MH, uses PRE-B resolve_hub_for_spoke + new pharmacy metadata helper, templates hub name/NPI/phone into redirect message, strict/advisory modes), `primary_payer_redirect_rule` (C.20, NCPDP MH, iterates triggers on upstream BIN+PCN, templates target pharmacy + PA override into message), `other_payer_verification_rule` (C.21, NCPDP 75 Prior Auth Required, stateful one-time verification for OCC=03 + configured upstream BIN+PCN, writes member_program_flags row on REJECT so subsequent claims PASS), `primary_insurance_rejection_allowlist_rule` (C.22, NCPDP 70 Product/Service Not Covered, OPRC allowlist for OCC=03, reads ctx.upstream_claim.reject_codes from PRE-A.5 + Layer 1 multi-reject; BRD-observed default allowlist 3Y/40/50/60/606/608/65/66/70/75/75F/75U/76/78/7X/88/MR/R6). New shared helper `get_pharmacy_metadata(session, npi)` reads pharmacy_dir.ncpdp_pharmacies returning PharmacyMetadata {npi, name (dba_name preferred, legal_name fallback), phone, address}. RULE_TYPE_REGISTRY now 27 entries. Every Tier 2 rule exposes `reject_code` parameter override for vendor-specific switch requirements. 35 new unit tests + 10 E2E tests (C.18/C.19 via /admin/inject-claim + pharmacy_dir seeding; C.20-C.22 via direct rules-executor with ParsedClaim+COBSegment because admin InjectClaimRequest schema doesn't yet carry upstream-claim fields — real wire adapter via am05_cob.py will). 280 rules-engine + 202 adjudication-engine tests pass.** **Wave 26 Phase C.12-C.17 M2-M7 added 6 new rule types completing Tier 1 per BRD synthesis: `quantity_range_ndc_rule` (C.12, NCPDP 7E), `days_supply_range_ndc_rule` (C.13, NCPDP 7C/19), `annual_maximum_benefit_rule` (C.14, NCPDP 76, stateful reads accumulator.dollars_used, requires post-pricing priority_order), `fill_limitation_rule` (C.15, NCPDP 76, stateful reads accumulator.fills_used, pre-pricing), `minimum_days_between_fills_rule` (C.16, NCPDP 79, two modes fixed_days + pct_of_prior_days_supply, BRD-style defer_on_covered for OCC 02/08, templated [HOURS_LEFT] countdown), `age_restriction_ndc_rule` (C.17, NCPDP 60, fail-safe PASS+flag on missing DOB). All use PRE-H hierarchical parameter resolution via `_resolve_pricing_parameters`. Templated reject messages via PRE-D `render_message` with defensive fallback on template errors. New shared helper `get_last_successful_claim_for_patient_drug` for C.16. RULE_TYPE_REGISTRY now 22 entries. Tenant_id field refactor: `ClaimContext.tenant_id` added as first-class; `build_context` sets `claim_id = ParsedClaim.claim.prescription_number` (NCPDP 455-EM canonical Rx number) and tenant_id separately — eliminates the Phase A.2 overload where `claim_id=str(tenant_id)`. 33 new unit tests + 10 new E2E tests (each rule's REJECT path + stateful paths reading accumulator/history + full-pass with accumulator increment). 245 rules-engine + 192 adjudication-engine tests pass.** **Wave 26 Phase C.8 landed alembic 0005 + `claim_transactions.amounts JSONB NOT NULL DEFAULT '{}'` + `claim_txn_amounts_gin` GIN index + CHECK `jsonb_typeof='object'`. `AdjudicationResult.amounts` first-class dict hoisted from the rule step; `_adapt_result_to_hook_dict` serializes Decimal → str for JSONB round-trip safety; `persist_claim_transaction` writes to `claim_transactions.amounts`. `build_context` now populates `ctx.amount_billed` = `ingredient_cost_submitted + dispensing_fee_submitted` (NCPDP 430-DU synthesis) and `ctx.program_id` (was defaulted to "" — needed by PRE-H resolver calls in pricing rules). REJECT clears amounts on the pipeline side per NCPDP "no payment on rejected claim" semantic. New `test_phase_c8_to_c11_pricing_e2e.py` adds 5 e2e tests: canonical composition (qty=5, billed=500, MRA 95/1425, fee 1, copay 25 → program_pay=476, patient_pay=25, dispense_fee=1), amount_billed binds the cap, total_mra binds at high qty, REJECT-before-pricing clears amounts, pipeline-order verification (MRA=10 before DispenseFee=20 before TargetCopay=30). 176 adjudication-engine tests pass (was 171 + 5 new).** |
.\docs\audit\CLAUDE_archive_pre_wave_42.md:63:| ncpdp-core | 4 | In progress | 10,617 LOC NCPDP D.Ø library: wire codec, segments, transactions (B1/B2/B3/E1/P1–P4), structural/profile validators, payer profiles, response builders (6 archetypes). Active multi-session build (Sessions 1–17 per `.claude/rules/session-framework.md`). No DB persistence needed — library module. **Wave 26 Phase C.7-NCPDP-COB-FIX corrected systematic AM05 field-code mis-assignments against NCPDP D.Ø IG + real IFX production wire data (AM28 response-side COB had correct mapping all along, served as authoritative reference). Renamed: 337-4C was `other_payer_amount_paid` (Decimal) → `coordination_of_benefits_count` (int); 338-5C was `other_payer_date` → `other_payer_coverage_type`; 341-HB was `other_payer_group_id` → `other_payer_amount_paid_count` (int); 342-HC was `other_payer_rx_id` → `other_payer_amount_paid_qualifier`. Annotation fix: `other_payer_id` code 7B→7C. Added: `other_payer_date` (443-E8), `other_payer_amount_paid` (431-DV, Decimal). Dropped mis-labeled fields (HD/HE/HF/HG/HH) deferred to EXPAND with correct spec codes (471-5E reject count, 353-NR/351-NP/352-NQ patient-responsibility, 392-MU/393-MV/394-MW benefit-stage). Single-occurrence shape preserved; multi-payer + repeating sub-groups were originally C.7-NCPDP-COB-EXPAND scope. Legacy corpus fixture + 43 rewritten AM05 tests (including 4 real-IFX-wire-bytes conformance tests parsing duplicate_request.bin / paid_request.bin / reversed_request.bin AM05 segments) + README correction (prior "6E70 = DV $0.70 JSON artifact" narrative was wrong; 6E is 472-6E reject code in a 5E2-governed repeating group). Full ncpdp-core suite 1228 passing (up from 1208). Note: cross-module audit surfaced 4 pre-existing Phase C.2 rule_config test failures unrelated to this wave.** **Wave 26 Phase C.7-NCPDP-AM07-SCC + Audit Docs (2026-04-22) shipped a scaled-down deliverable after EXPAND Step 0 surfaced a Layer 1 architectural gap: `wire/codec.py:parse_segment_fields` uses `dict[str, str]` keyed on 2-char NCPDP field code, silently collapsing repeating same-code fields to last-value-wins. Real IFX paid_request.bin AM05 `5E2 6E70 6EMR` loses "70". Affects every segment with NCPDP repeating-group fields (AM05/AM07/AM08/AM10/AM20/AM28+). Compounding finding: AM20's April 2026 multi-reject-code "correction" was built on misreading of D.Ø spec — its docstring claims numbered-suffix keys (FB1/FB2/FC1/FC2), real wire uses repeated FB; tests pass only because synthetic fixtures pre-collapse into the wrong shape. Both findings filed: `docs/audit/wave-26-ncpdp-core-layer1-repeating-groups.md` (3-5 session estimate for Layer 1 redesign + segment migrations) and `docs/audit/wave-26-ncpdp-core-am20-misreading.md` (bundled with Layer 1 fix wave). Shipped: AM07 ClaimSegment.submission_clarification_code (Optional[str]) renamed to submission_clarification_codes (tuple[str, ...]) — Python API shape correct; wire round-trip works at count ≤ 1 (covers all current IFX samples including paid_request.bin's NX1/DK99); multi-SCC unblocked when Layer 1 ships. 8 new AM07 SCC tests including real-IFX-wire conformance. ncpdp-core suite 1236 passing. Hardening discipline established: real-IFX-wire conformance tests as primary authority for repeating-field segments; synthetic-fixture-only tests have now hidden three categories of issue (AM05 field codes, AM20 misreading, Layer 1 representation). PRE-A.5 (adapter wiring) unblocked for single-primary-payer + single-SCC scenarios covering all current IFX production samples; multi-anything blocks until Layer 1 correction wave.** **Wave 26 Phase C.7-NCPDP-LAYER1 (2026-04-23) shipped the Layer 1 fix and the dependent segment migrations in a single autonomous wave. Layer 1 codec gained an additive ordered-view `RawSegment.repeating_fields: tuple[tuple[str, str], ...]` populated alongside the existing `fields` dict (backward-compat preserved — every prior segment test passes unchanged). New `parse_segment_fields_ordered()` Layer 1 entry; new `get_field_all()` segments-base helper; serializer merges both views (repeating_fields wins for codes present in both). AM20 fix: replaced numbered-suffix parse loop with spec-correct repeated-FB consumption via ordered view, fallback to dict for hand-constructed test fixtures; updated 3 to_raw tests asserting on the wrong FB1/FC1 shape; docstring corrected. AM07 multi-SCC: removed count<=1 limitation; multi-SCC parse + serialize round-trip via ordered view; new end-to-end wire codec round-trip test for 3 SCCs. AM05 multi-reject + patient-responsibility: added `other_payer_reject_count` (471-5E) + `other_payer_reject_codes: tuple[str, ...]` (472-6E repeating); added `other_payer_patient_responsibility_count` (353-NR) + qualifier (351-NP) + amount (352-NQ Decimal). paid_request.bin AM05 reject codes now parse as `('70', 'MR')` correctly; duplicate_request.bin AM05 NR/NP/NQ now round-trip. Multi-Other-Payer (337-4C > 1) and benefit-stage group (392-MU/393-MV/394-MW Medicare Part D) explicitly deferred until IFX wire samples surface them — per the real-IFX-wire-conformance discipline. ncpdp-core suite 1240 passing. Cross-module adjudication-engine: same 14 pre-existing failures, zero new regressions. PRE-A.5 (adapter wiring) fully unblocked for the IFX wire-format space — multi-reject upstream payer claims, multi-SCC submissions, and patient-responsibility extraction are all wire-correct now.** **Wave 26 Phase C.7-ADAPTER-THROUGH-PRE-D (2026-04-23) shipped 4 milestones autonomously. (M1 PRE-A.5) Adapter wires AM05 COB + AM07 SCC into ParsedClaim and through build_context into ClaimContext.upstream_claim, .submission_clarification_codes, and .preflight_flags. New ParsedClaim.cob (COBSegment with all NCPDP-correct fields), ClaimSegment.submission_clarification_codes: list[str]. Multi-upstream-payer detection (4C count > 1) attaches an informational FlagEntry via ctx.preflight_flags which build_rules_executor hoists into PipelineResult.flags so it persists to claim_transactions.flags. 11 new unit tests covering SCC empty/single/multi, COB absent/empty/single/reject-codes/zero-amount, multi-upstream flag attachment. (M2 PRE-B) Three new program_config tables: program_networks (named tier per program — Hub/Spoke/Retail/Premium-Base/Premium-Mid/Premium-Top/Consignment/Specialty etc., NOT hardcoded enum), program_network_pharmacies (effective-dated NPI-to-tier membership with partial unique index for "one active membership per (program, pharmacy) at a time"), program_hub_spoke_pairs (consignment redirect). Helpers in shared/program_config_queries/network.py (resolve_network_tier_at_pharmacy + resolve_hub_for_spoke); build_context populates ctx.network_tier_at_pharmacy when session+program_id provided, removing PRE-A's TODO. (M3 PRE-C) Two new program_config tables: member_drug_program_accumulators (per-(member, drug_brand, program, calendar_year) with fills_used/dollars_used Decimal/scc_overrides_used + check constraints for non-negative + sane year range), member_program_flags (JSONB flag_value with effective dating). Helpers in shared/program_config_queries/accumulator.py (read_accumulator, is_first_fill_for_patient_drug, atomic increment_accumulator via INSERT ON CONFLICT, get/set/clear_member_flag). build_context populates ctx.is_first_fill_for_patient_drug, removing PRE-A's TODO. Per-drug scoping (NOT global per-member) matches manufacturer copay program semantics. (M4 PRE-D) shared/utils/message_template.py — render_message() utility for [VAR] uppercase-bracket and {var} lowercase-brace template substitution with Decimal money formatting (suffix-detection $X.XX), phone formatting (###-###-####), and explicit MessageTemplateError on missing keys (silent missing-key substitution would hide rule-author bugs). Both syntaxes per BRD synthesis observations. Helpers + ORM use shared/program_config_queries/ rather than modules/program-config/src/services/ to avoid namespace collision with rules-engine's services.* package via adjudication-engine's sys.path manipulation. Alembic 0004 deployed to dev DB; FORCE RLS + NULLIF-wrapped tenant predicate on all 5 new tables. Defensive guards (hasattr session.execute) keep existing fake-session test fixtures passing. Test totals: +11 build_context population, +18 message template, +19 helper real-DB tests; ncpdp-core 1240 unchanged; rules-engine 179 unchanged; adjudication-engine 14 pre-existing failures unchanged. PRE-E (effective-dated config), PRE-F (test harness), PRE-G (FDB integration), PRE-H (parameter resolution layer) remain as future scope.** **Wave 26 Phase C.8-C.11 added the SET_AMOUNT outcome type + three Tier 1 pricing rules per BRD rule catalog synthesis Section 6 Decision 1. (C.8) `RuleAction.SET_AMOUNT` fourth outcome; `RuleResult.amounts` + `PipelineResult.amounts` + `ClaimContext.amounts` + `ClaimContext.amount_billed` fields added. Pipeline SET_AMOUNT branch merges rule.amounts into running result.amounts AND ctx.amounts via dict.update semantics so DispenseFee can read program_pay from MRA's prior output and return the sum. REJECT branch clears both dicts per NCPDP semantic. Legacy PASS/REJECT/MODIFY/FLAG semantics preserved. 9 new pipeline unit tests. (C.9) `MaxReimbursementAmountRule` code `max_reimbursement_amount_rule` — caps program_pay at min(amount_billed, qty * mra_per_unit, total_mra). Reads parameters via new `_resolve_pricing_parameters(ctx, rule_instance_params)` helper which calls PRE-H's `resolve_program_parameters` then overlays rule_instance.parameters. FDB PRE-G stub called for audit note only; MRA math uses program_config caps. PASS when no MRA configured for scope. (C.10) `TargetCopayRule` code `target_copay_rule` — three modes per BRD: `fixed` (patient_pay=fixed_amount), `first_fill_different` (picks first vs subsequent via PRE-C `ctx.is_first_fill_for_patient_drug`; PASS when flag unknown), `save_off_primary` (max(0, NQ - save_amount) from ctx.upstream_claim.patient_responsibility_amount via PRE-A.5; PASS when no upstream). (C.11) `DispenseFeeAmountRule` code `dispense_fee_amount_rule` — reads ctx.amounts['program_pay'] and returns SET_AMOUNT with program_pay=current+fee AND dispense_fee=fee. 24 new Tier 1 pricing unit tests. RULE_TYPE_REGISTRY now 19 entries (16 + 3 pricing). All money Decimal, quantize(0.01, ROUND_HALF_UP). 212 rules-engine tests pass (was 188 + 24 new).** |
.\docs\audit\CLAUDE_archive_pre_wave_42.md:72:| paysync | 2 | In progress | Wave 35 foundation: 7-table schema (`paysync.*`) with FORCE RLS + NULLIF tenant predicate + GRANTs to ifx_*_app + ifx_*_admin (alembic 0001 + 0002); typed canonical-field catalog (~80 fields) + 4 built-in profiles (IFX_EXPORT_63_COLUMN from real `data/raw/ifx-exports/` header, IFX_HISTORY_53_COLUMN positional, IFX_184_COLUMN placeholder per M1 audit, GENERIC_CSV scaffold); claims ingester with idempotent ON CONFLICT (tenant_id, auth_num) DO UPDATE + canonical member resolution via `shared.program_config_queries.member_resolution` + per-row error persistence to `paysync.import_run_errors` + CLI `python -m paysync import`; NRID router with priority chain (client_special_rules > exact NRID > pattern prefix > UNRESOLVED) + Klyre sub_channel detection (INFINITY+debit_card_amount>0); cycle manager (1H/2H half-month default, idempotent labels, DOS/adjudication-time range assignment, close with unresolved-channel gating + orphaned-reversal surfacing). 73 paysync tests green (45 integration real-DB + 28 unit). **Wave 36 added paysync × network-mgmt integration**: alembic 0003 introduces paysync.pay_to_resolutions (per-claim immutable snapshot of network-mgmt waterfall — UPSERT on (tenant, claim_id) so re-imports stay idempotent) + paysync.banking_discrepancy_reviews (operator review queue) + claims.pay_to_resolution_id back-pointer FK; ingester extension calls resolve_pay_to after each claim insert and snapshots the result, runs compare_imported_banking when claim row carried banking (NO_RECORD → auto-record with source='imported'; MISMATCH → review row created, banking NOT auto-updated; MATCH → no-op). Wave 36 paysync test totals: 82 green (was 73; +9 M4 integration). **Wave 37 added payment batch + NACHA + 835 EDI**: alembic 0004 introduces 5 tables (paysync.payment_batches with status state machine draft → pending_approval → approved → submitted → settled → reconciled + voided/failed terminal; payment_batch_credits with claim_ids UUID[] + trace_number + entry_class_code; payment_batch_held_claims with partial-unique active-hold per claim; payment_batch_files with sha256 hex-format CHECK; batch_audit_log append-only). batch_generator.generate_batch aggregates eligible claims by pay_to_entity (skipping statement_account, net-zero/negative, and held), entry-class detection from banking.account_type (PPD/CCD), idempotent on (tenant, cycle, batch_number). auto_hold_claims_in_cycle flags missing-banking + pending-discrepancy claims; release_held_claim toggles released_at. nacha_generator emits 94-char fixed-width records (1/5/6/8/9 + 9-fill padding to blocking factor 10), decrypts banking via secret_box in-memory only (test asserts plaintext absent from logs), persists trace_number per credit + sha256 in payment_batch_files; refuses voided/already-submitted batches; refuses missing tenant_ach_origination. eight_thirty_five_generator emits ASC X12 005010X221A1 (ISA/GS/ST/BPR/TRN/N1*PR/N1*PE/[LX/CLP/NM1*QC/NM1*82/REF*EA/DTM*232/SVC]/SE/GE/IEA); CLP status 1=primary, 22=reversal; multi-recipient generate_all_eight_thirty_five_for_batch de-dupes by (pay_to_entity, destination_id). Admin API on adjudication-engine: /admin/paysync/cycles/{id}/auto-hold + /batches CRUD + approve/void/generate-nacha/generate-835 + held-claim release. Wave 37 paysync test totals: 119 (was 82 pre-Wave-37; +37). **Wave 38 added invoicing engine + customizable exports + claims statements + email delivery**: alembic 0005-0007 introduce 11 tables (invoice_sequences + invoice_sequence_change_log + invoices + invoice_lines + invoice_attachments + invoice_audit_log + fee_schedules + gl_account_mappings + export_templates + email_templates + email_recipients + email_deliveries; total 26 paysync tables now). Two-sequence invoice numbering (reimbursement / client_fees) per scope (tenant/program/client) with atomic FOR UPDATE allocation, operator override + audit log. Invoice generators (reimbursement excludes statement-account claims; client-fees applies fee_schedule.fee_lines with flat_per_claim/flat_one_time/percentage_of_claim_count calc methods). Lifecycle state machine draft → finalized → sent → paid|partial → reconciled with voided terminal (force_paid_void required to void from paid). Customizable export templates (column/filter/sort/summary JSONB) rendering xlsx (openpyxl 2-sheet Summary+Details) / csv / pipe_delimited; PHI tokenization via HMAC-SHA256 deterministic per-template seed. SaaSant Excel for QuickBooks Online with GL account mappings. Per-NPI pharmacy claims statements (no PHI). cycle_summary_csv flat extract. Provider-abstracted email (SmtpEmailProvider + NoOpEmailProvider) with Jinja2 sandboxed templates + IFX_SMTP_PASSWORD_ENCRYPTED via secret_box. Admin API: /admin/paysync/invoices CRUD + finalize/send/mark-paid/void, /exports/saasant, /email-recipients, /gl-account-mappings. Wave 38 paysync test totals: 198 (was 119; +79). **Wave 39 added cycle close orchestration + three-way reconciliation + bank settlement ingest + manual AP + carryovers + Echo Spec 400 readiness**: alembic 0008-0013 introduce 11 tables (cycle_schedules, manual_ap_records + echo_spec_400_runs + echo_payment_status_records, carryovers, cycle_close_runs, bank_settlements + bank_settlement_entries + bank_file_adapters, cycle_reconciliations) + extends claims with payment_cycle_id + invoice_cycle_id + pharmacy_state. Cycle schedule waterfall (state→npi→program→client→tenant). 10-step orchestrator (preflight → holds → manual_ap_recognition → carryover_ingestion → batch → NACHA → 835 → invoice → reconciliation → finalization) with cycle_close_runs.step_status JSONB. Three-way reconciliation (Tie 1 claims↔invoice, Tie 2 claims↔total AP, Tie 3 batch↔NACHA↔835) at $0.01 tolerance. Bank settlement ingest (manual + NACHA Return File parser for R01-R31) with bounce → auto-carryover. Echo Spec 400 generation deferred to Phase 4/5 (schema ready). Admin API: /cycles/{id}/{close, close-status, reconcile, reconciliations} + /cycle-schedules + /manual-ap-records + /carryovers + /bank-settlements. Wave 39 paysync test totals: 295 (was 198; +97). **Phase 2 PaySync structurally complete**; Wave 40+ is operational hardening; Wave 41 portal UI. |
.\docs\audit\CLAUDE_archive_pre_wave_42.md:75:| maxacc-registry | 3 | Built | **Wave 44a (2026-04-27)** ships the global reference-data substrate Wave 44b ReclaimRx ML detection layers on. Same architectural pattern as DataQ NCPDP / NPPES / OIG-SAM / drug_db: NO `tenant_id`, NO RLS, platform-owned, app-role SELECT-only + admin-role full DML. Schema (`maxacc_registry.*`, alembic 0001 + 0002): 5 tables — `source_lists`, `ndc_list_entries` (NDC stored as canonical 11-digit no-hyphens matching drug_db convention; CHECK `ndc ~ '^[0-9]{11}$'`), `bin_pcn_group_vendor_map`, `vendor_pbm_relationships` (10-vendor canonical seed at migration time: PrudentRx→CVS Caremark/CVS Specialty exclusive, SaveOnSP→Express Scripts/Accredo exclusive, Variable Copay→OptumRx/Optum Specialty exclusive, 7 independent), `import_runs` (provenance: file SHA-256, counts, status, errors). COALESCE-based unique indexes for nullable composite uniques (source_name + vendor_name; bin + pcn + group_id + vendor). Three ingest entry points: (1) `curated_seed.import_curated_seed_file` — operator CSV with one ImportRun per `(source_name, vendor_name)` bucket so drop-off detection scopes per-list (CLI: `python -m maxacc_registry.ingest.curated_seed`); (2) `scraper_output.import_scraper_output` — JSON envelope from out-of-band scraper sessions, Pydantic-validated, per-entry failures logged with index without aborting run (CLI: `python -m maxacc_registry.ingest.scraper_output`); (3) admin API multipart on adjudication-engine. Idempotent UPSERT via ON CONFLICT keyed on (source_list_id, ndc) + (bin, pcn, group_id, vendor) preserves first_observed_at, bumps last_observed_at, clears no_longer_*_at on reappearance. Drop-off detection: per-run, SET no_longer_*_at = drop_off_date for active rows not in seen-set (drop_off_date = max observed_at across run, falls back to today). employer_list rows recorded informationally (no detail-table write in W44a; W44b can promote when BIN association is observed). Read-side helpers `maxacc_registry.queries.lookup`: `ndc_on_any_maximizer_list(session, ndc, *, as_of_date=None)` returns `NdcMaximizerLookup` with is_listed/currently_listed/sources/first/last_observed; `resolve_bin_pcn_group_vendor(session, bin, *, pcn=None, group_id=None, as_of_date=None)` runs 4-tier waterfall (bin+pcn+group → bin+pcn → bin → none) with ORDER BY confidence ASC LIMIT 1, joins vendor_pbm_relationships for pbm_carrier + exclusive_specialty_pharmacy + is_exclusive_relationship; `vendor_runs_known_program_for_bin_combo` boolean wrapper; `list_active_source_lists` / `list_recent_imports` for catalog enumeration. Admin API on adjudication-engine at `/admin/maxacc-registry/*` — source-lists CRUD + lookup/{ndc,bin} reads + runs (list, detail, curated-seed multipart, scraper-output multipart) + vendor-pbm-relationships CRUD + /seed canonical re-run. Auth: reads operator|platform_admin|fwa_investigator; writes platform_admin only. Session factory swaps DATABASE_URL_SYNC's app role → admin role in-process (or honors ADMIN_DATABASE_URL override) because migration 0001 grants app SELECT only. Errors mapped 404/409/422 per platform standard. Tests: 55 module (11 schema smoke + 6 vendor-PBM + 8 curated-seed + 8 scraper + 20 lookup + 2 e2e) + 26 admin endpoint integration on adjudication-engine. Cross-module regression: ncpdp-core 1,280, rules-engine 264, network-mgmt 38, reclaimrx 384 unchanged; adjudication-engine integration 237 (was 211 + 26 maxacc admin). Wave 44b (ML detection) consumes `from maxacc_registry.queries.lookup import …` directly; cross-module import smoke test in `test_e2e_pipeline.py::test_cross_module_import_smoke` is the public-API contract. Vocabulary discipline: surfaces describe "patient assistance program manipulation tracking" / "anomaly identification", never fraud/FWA/abuse. |
.\docs\audit\CLAUDE_archive_pre_wave_42.md:772:  (Wave 30 Phase B same resolver Phase 1 uses) → ON CONFLICT
.\docs\audit\CLAUDE_archive_pre_wave_42.md:1472:- **M4 — anomaly persistence + workflow**: `reclaimrx.anomalies.repository` ships create_anomaly + create_manual_flag (operator-created without rule, confidence=1.0, detection_id=NULL) + status state machine (open→under_review→confirmed→in_recoup→in_audit→resolved|written_off; dismissed/resolved/written_off terminal — validated in code AND backstopped by schema CHECK) + link_anomaly_to_case (requires status='confirmed'; flips to 'in_recoup' + sets case_id back-pointer + writes case_anomaly_links with ON CONFLICT DO NOTHING idempotency) + unlink_anomaly_from_case (allowed when in_recoup or in_audit; reverses to 'confirmed') + resolve_anomaly (writes resolution_method + resolved_at + resolved_by + recovery_amount as a coherent triple, target status 'resolved' or 'written_off' based on resolution_method). Every state-changing operation writes one or more rows to `anomaly_audit_log` with old_value/new_value JSONB snapshots — six event types: created, manual_flag_created, status_change, linked_to_case, unlinked_from_case, resolved. Tenant isolation: every UPDATE/SELECT joins on (id, tenant_id); cross-tenant access raises AnomalyNotFoundError; RLS layer backstops on the DB. 14 real-DB tests cover create + audit emission, kind/id pair validation (manual_flag must NOT carry detection_id; rule/ml_pattern MUST), manual flag with notes audit, every valid + each invalid state transition, dismissed/resolved/written_off terminal enforcement, link-requires-confirmed, link/unlink round trip with audit trail, resolve via recovered/written_off + invalid-from-open rejection, unknown method rejection, cross-tenant isolation.
.\docs\audit\CLAUDE_archive_pre_wave_42.md:1515:  migration time via ON CONFLICT (vendor_name) DO UPDATE: PrudentRx →
.\docs\audit\CLAUDE_archive_pre_wave_42.md:1556:  writes platform_admin only. Session factory swaps DATABASE_URL_SYNC's
.\docs\audit\CLAUDE_archive_pre_wave_42.md:1558:  ADMIN_DATABASE_URL override) because migration 0001 grants app
.\docs\architecture\environments.md:4:runs three databases on one Postgres cluster — `infinityrx_reference`
.\docs\architecture\environments.md:14:├── infinityrx_reference     ← loaders write here ONCE
.\docs\architecture\environments.md:35:│       (created by setup_fdw.sh)   infinityrx_reference.{shared,
.\docs\architecture\environments.md:49:forwards to `infinityrx_reference` via the FDW server. Cross-DB JOINs
.\docs\architecture\environments.md:52:Reference data flows ONE direction: loaders → `infinityrx_reference` →
.\docs\architecture\environments.md:71:| `DATABASE_URL` | async URL for the env's writable DB (asyncpg driver) |
.\docs\architecture\environments.md:72:| `DATABASE_URL_SYNC` | sync URL for the env's writable DB (psycopg2 driver) |
.\docs\architecture\environments.md:73:| `DATABASE_URL_SYNC_REFERENCE` | sync URL for `infinityrx_reference` — used by reference-data loaders only; app code reads via FDW |
.\docs\architecture\environments.md:76:Loaders prefer `DATABASE_URL_SYNC_REFERENCE` > `DATABASE_URL_SYNC` >
.\docs\architecture\environments.md:77:`DATABASE_URL` (precedence introduced in Wave B7 C3).
.\docs\architecture\environments.md:87:| `ifx_reference_writer` | infinityrx_reference owner — used by loaders only | LOGIN |
.\docs\architecture\environments.md:88:| `ifx_ref_reader`     | read-only on infinityrx_reference + FDW user-mapping target | LOGIN |
.\docs\architecture\environments.md:93:   medical codes) — single source of truth in `infinityrx_reference`.
.\docs\architecture\environments.md:103:`DATABASE_URL`, `DATABASE_URL_SYNC`, `DATABASE_URL_SYNC_REFERENCE`,
.\docs\architecture\environments.md:120:- Reference data is loaded ONCE into `infinityrx_reference` (Wave B7).
.\docs\api-contracts\events\claim.adjudicated.md:170:value via `assert_awp_basis_acceptable(snapshot,
.\shared\utils\preflight.py:65:    "DATABASE_URL",
.\shared\utils\preflight.py:87:    url = settings.DATABASE_URL.replace("+asyncpg", "")
.\docs\audit\wave-0-tasks\loader-bugs.md:111:  syntactically correct (`INSERT ... ON CONFLICT DO UPDATE` via
.\docs\audit\wave-0-tasks\loader-bugs.md:115:     unique constraint on the live schema, causing the ON CONFLICT to
.\docs\audit\wave-0-tasks\loader-bugs.md:136:- **Original tracking note**: "missing ON CONFLICT" — this was wrong.
.\docs\audit\wave-0-tasks\loader-bugs.md:535:  shim's 10 rows still exist and the loader's ON CONFLICT DO UPDATE
.\portal\shared\lib\constants.ts:22:    process.env.NEXT_PUBLIC_DRUG_DATABASE_URL ?? "http://localhost:8011",
.\docs\audit\wave-41-5-test-quality-review.md:9:Run with `DATABASE_URL_SYNC=postgresql+psycopg2://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev`.
.\docs\audit\wave-41-5-test-quality-review.md:52:`DATABASE_URL_SYNC` set + pointing at Postgres (not SQLite). Each skip
.\docs\audit\wave-35-ifx-billing-audit.md:119:PaySync M4 uses `ON CONFLICT (tenant_id, auth_num) DO UPDATE` so
.\docs\testing.md:30:Requires `DATABASE_URL_SYNC` pointing at dev (e.g. via `source
.\docs\audit\wave-41-7-listener-perf.md:120:   DATABASE_URL_SYNC=postgresql+psycopg2://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev \
.\docs\audit\wave-41-7-ai-nlp-session-audit.md:97:  create_engine(url_sync)                ← sync engine
.\docs\audit\wave-41-7-ai-nlp-session-audit.md:113:| F-04 | `tests/integration/test_smoke_real_db.py:56–61, 90–96, 124–136, 165–172, 191–208` | Sync `create_engine` + sync `Session` (via `sessionmaker`) used throughout the integration smoke suite. All production paths are async. | **(c) Intentional — leave as-is** | This is a deliberate architectural choice for the testcontainer ORM-mapping verification suite: sync sessions are simpler for sequential test steps, and the suite explicitly imports `install_rls_session_sync` (the sync RLS hook). No production async path is exercised by these tests; they verify schema/migration/RLS only. Do not change. |
.\shared\tests\test_preflight.py:77:    p.write_text("DATABASE_URL=x\n", encoding="utf-8")
.\shared\tests\test_preflight.py:86:        "DATABASE_URL=x\nREDIS_URL=y\nRABBITMQ_URL=z\nJWT_SECRET=" + "x" * 32 + "\n",
.\shared\tests\test_preflight.py:178:    checker reads ``shared.config.get_settings().DATABASE_URL`` at call
.\docs\audit\wave-history [conflicted].md:47:| Wave B7.1 | 2026-05-10 | B7+B8 cleanup wave: W2 `setup_fdw.sh --verify` net-new (66/66 PASS dev+mock, closes B7 C9 Phase 2) + SELECT grant on reference foreign tables (round-2 fix); W3 Tier 1 env-drive `ifx_prod_app` in 15 RLS-policy migrations across 9 modules (`init-multi-db.sql` preserved; DROP blocked by `pg_shdepend` 31 dependents → B7.1.1; Tier 2 GRANTs deferred); W4 hygiene bundle (12 loader rc propagation, OFAC CRLF fix, .sh chmod, gitignore patterns); W1 NPPES status doc (~4.9M < 7M target → B7.1.1). **13 commits, `7e9e1ff..e30fdfb`.** SC-2/4/5/6/7/9 PASS, SC-1/SC-3 PARTIAL, SC-8 GO-WITH-FIXES (codex 2 rounds: real SELECT-grant gap fixed; 3 false positives dismissed — Tier 2 GRANTs, claude-mem pattern, wave-history timing). |
.\docs\audit\wave-history [conflicted].md:50:| Wave B7.2 | 2026-05-10 | **Phase 11A COMPLETE.** Tier 2 architectural GRANT wave: W1 env-drive `ifx_prod_app` in 26 files (25 Tier 2 migrations + `scripts/apply_rls.py`) via `IFX_APP_ROLE`; W2 remove `ifx_prod_app` key from both `_ROLE_PAIRS` dicts (`maxacc_registry_routes.py` + `test_helpers.py`); W3 REVOKE 14 `pharmacy_dir.dataq_*` cluster GRANTs from `ifx_prod_app` + re-GRANT to `ifx_dev_app` (`pg_shdepend = 0`; `setup_fdw.sh --verify` 66/66 PASS); W4 `DROP ROLE ifx_prod_app` (`pg_authid count = 0`). 8-suite test verification: all 8 suites match C0 baseline (no regressions). Script preserved at `infrastructure/scripts/lib/cleanup_tier2_ifx_prod_app_grants.sql`. Wave artifacts at `waves/B7.2/`. **7 commits, `2964ebc..276fd99`.** SC-1..SC-5/SC-7 PASS. Codex: SPEC 2 rounds GO-WITH-FIXES (9 concerns); PLAN + ADVERSARIAL skipped; GATE-CLOSE: R1 NO-GO (artifacts not in repo) → R2 GO-WITH-FIXES → GO (C9 placeholder fill). Deferred: `tests/integration/conftest.py:149` + `shared/config.py:159` (charter v3 explicit, non-load-bearing). `ifx_prod_app` gone from live cluster + all GRANT targets + both runtime dicts. |
.\shared\events\jobs\cleanup_processed_events.py:44:    DELETE statement with ON CONFLICT DO NOTHING semantics for safety.
.\docs\known-issues.md:52:**Symptom**: Tests using `DATABASE_URL_SYNC` to connect as the app role
.\docs\known-issues.md:62:**Action**: When setting `DATABASE_URL_SYNC` manually, use
.\shared\events\idempotency.py:83:    Uses ``INSERT ... ON CONFLICT DO NOTHING`` so concurrent consumers racing
.\shared\events\idempotency.py:140:                    "ON CONFLICT DO NOTHING"
.\shared\tests\test_harness\test_scheduled_changes.py:48:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\test_harness\test_scheduled_changes.py:64:    from sqlalchemy import create_engine
.\shared\tests\test_harness\test_scheduled_changes.py:73:    engine = create_engine(_resolve_admin_url())
.\shared\tests\test_harness\test_scheduled_changes.py:130:            ON CONFLICT (id) DO NOTHING
.\shared\tests\test_config.py:12:    "DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
.\shared\tests\test_config.py:13:    "DATABASE_URL_SYNC": "postgresql+asyncpg://u:p@h/d",
.\docs\sops\backup-restore.md:57:   `DATABASE_URL` secret. Roll deployments.
.\shared\tests\program_config_queries\test_scheduler.py:34:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\program_config_queries\test_scheduler.py:52:    from sqlalchemy import create_engine
.\shared\tests\program_config_queries\test_scheduler.py:56:    engine = create_engine(_resolve_admin_url())
.\shared\tests\program_config_queries\test_pharmacy_storefronts.py:25:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\program_config_queries\test_pharmacy_storefronts.py:86:    from sqlalchemy import create_engine  # noqa: PLC0415
.\shared\tests\program_config_queries\test_pharmacy_storefronts.py:88:    url = os.environ["DATABASE_URL_SYNC"]
.\shared\tests\program_config_queries\test_pharmacy_storefronts.py:91:    engine = create_engine(url, future=True)
.\docs\runbooks\validation-upload.md:43:   export DATABASE_URL_SYNC="postgresql+psycopg2://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev"
.\docs\runbooks\validation-upload.md:53:   DATABASE_URL_SYNC="postgresql+psycopg2://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev" \
.\docs\runbooks\validation-upload.md:62:   DATABASE_URL_SYNC="postgresql+psycopg2://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev" \
.\docs\runbooks\validation-upload.md:69:   DATABASE_URL_SYNC="postgresql+psycopg2://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev" \
.\docs\runbooks\validation-upload.md:84:   DATABASE_URL_SYNC="postgresql+psycopg2://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev" \
.\docs\runbooks\validation-upload.md:89:   DATABASE_URL_SYNC="postgresql+psycopg2://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev" \
.\shared\tests\program_config_queries\test_pharmacy_payment_lookup.py:34:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\program_config_queries\test_pharmacy_payment_lookup.py:110:    from sqlalchemy import create_engine
.\shared\tests\program_config_queries\test_pharmacy_payment_lookup.py:113:    url = os.environ["DATABASE_URL_SYNC"]
.\shared\tests\program_config_queries\test_pharmacy_payment_lookup.py:114:    engine = create_engine(url, future=True)
.\docs\runbooks\reference-db-replication.md:4:**Local-tier:** implemented (single `infinityrx_reference` + FDW).
.\docs\runbooks\reference-db-replication.md:27:│  - infinityrx_reference (primary)   │  logical   │  (warm standby)          │
.\docs\runbooks\reference-db-replication.md:103:# 3. Source dev env (gets DATABASE_URL_SYNC_REFERENCE)
.\docs\runbooks\reference-db-replication.md:123:tables added to the reference DB after `setup_fdw.sh` last ran will
.\docs\runbooks\reference-db-replication.md:137:infrastructure/scripts/setup_fdw.sh --refresh --env both
.\docs\runbooks\reference-db-replication.md:151:INFINITYRX_DESTRUCTIVE_OK=1 infrastructure/scripts/setup_fdw.sh --reset --env both
.\docs\runbooks\reference-db-replication.md:163:detected without a corresponding `setup_fdw.sh --refresh` run. Out of
.\docs\runbooks\reference-db-replication.md:176:`infinityrx_reference` only. Env DBs (`_dev`, `_mock`) keep the 30 s
.\docs\runbooks\reference-db-replication.md:181:ALTER DATABASE infinityrx_reference SET statement_timeout = 0;
.\docs\runbooks\reference-db-replication.md:200:- `infrastructure/scripts/setup_fdw.sh` — FDW configuration
.\docs\runbooks\reference-db-replication.md:201:- `infrastructure/scripts/lib/expected_reference_tables.txt` — coverage contract
.\docs\runbooks\reclaimrx-csv-upload.md:36:  * `DATABASE_URL_SYNC` is set in the operator's environment (or pass
.\shared\tests\program_config_queries\test_pa_timer.py:31:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\program_config_queries\test_pa_timer.py:42:    from sqlalchemy import create_engine
.\shared\tests\program_config_queries\test_pa_timer.py:46:    engine = create_engine(_resolve_admin_url())
.\docs\runbooks\phase1-troubleshooting.md:39:1. Check env vars: `DATABASE_URL_SYNC` set + reachable; TLS
.\docs\runbooks\phase1-troubleshooting.md:48:   `DATABASE_URL_SYNC` carries `ifx_<tier>_admin` the RLS policies
.\shared\tests\program_config_queries\test_parameters.py:28:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\program_config_queries\test_parameters.py:40:    from sqlalchemy import create_engine
.\shared\tests\program_config_queries\test_parameters.py:44:    engine = create_engine(_resolve_admin_url())
.\shared\tests\program_config_queries\test_network.py:28:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\program_config_queries\test_network.py:45:    from sqlalchemy import create_engine, text
.\shared\tests\program_config_queries\test_network.py:49:    engine = create_engine(_resolve_admin_url())
.\shared\tests\program_config_queries\test_member_resolution.py:39:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\program_config_queries\test_member_resolution.py:48:    from sqlalchemy import create_engine  # noqa: PLC0415
.\shared\tests\program_config_queries\test_member_resolution.py:53:    engine = create_engine(_resolve_admin_url())
.\shared\tests\program_config_queries\test_canonical_member_cross_claim.py:41:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\program_config_queries\test_canonical_member_cross_claim.py:47:    from sqlalchemy import create_engine  # noqa: PLC0415
.\shared\tests\program_config_queries\test_canonical_member_cross_claim.py:52:    engine = create_engine(_resolve_admin_url())
.\shared\tests\program_config_queries\test_canonical_member_cross_claim.py:166:            ON CONFLICT DO NOTHING
.\shared\tests\program_config_queries\test_accumulator.py:30:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\program_config_queries\test_accumulator.py:44:    from sqlalchemy import create_engine, text
.\shared\tests\program_config_queries\test_accumulator.py:48:    engine = create_engine(_resolve_admin_url())
.\docs\runbooks\local-dev-seed.md:56:export DATABASE_URL_SYNC="postgresql+psycopg2://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev"
.\docs\runbooks\local-dev-seed.md:72:INSERT uses `ON CONFLICT DO NOTHING` against the deterministic PK).
.\docs\runbooks\local-dev-seed.md:126:DATABASE_URL_SYNC=... .venv/bin/pytest tests/integration/test_validation_run_cli.py -v
.\docs\runbooks\fdb_lookup_perf.md:220:### 6.4 DATABASE_URL_SYNC not set
.\shared\tests\observability\test_slow_query.py:9:from sqlalchemy import Column, Integer, String, create_engine, text
.\shared\tests\observability\test_slow_query.py:27:    eng = create_engine("sqlite:///:memory:")
.\shared\db\test_helpers.py:13:The admin URL is derived from ``DATABASE_URL_SYNC`` by swapping the
.\shared\db\test_helpers.py:96:            "ON CONFLICT (id) DO NOTHING",
.\shared\db\test_helpers.py:111:    them deterministically. Safe to call multiple times; ON CONFLICT
.\shared\db\test_helpers.py:146:                "ON CONFLICT (code) DO NOTHING",
.\shared\db\test_helpers.py:164:            "ON CONFLICT (id) DO NOTHING",
.\shared\db\test_helpers.py:286:    """Derive the admin-role connection URL from DATABASE_URL_SYNC.
.\shared\db\test_helpers.py:290:      - ADMIN_DATABASE_URL: full URL, used directly if set
.\shared\db\test_helpers.py:293:    override = os.environ.get("ADMIN_DATABASE_URL")
.\shared\db\test_helpers.py:297:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\shared\db\test_helpers.py:300:            "seed_as_admin needs DATABASE_URL_SYNC (or ADMIN_DATABASE_URL) "
.\shared\db\test_helpers.py:314:            f"seed_as_admin could not parse DATABASE_URL_SYNC as "
.\shared\db\test_helpers.py:323:            f"Set ADMIN_DATABASE_URL to override."
.\shared\db\test_helpers [conflicted].py:13:The admin URL is derived from ``DATABASE_URL_SYNC`` by swapping the
.\shared\db\test_helpers [conflicted].py:96:            "ON CONFLICT (id) DO NOTHING",
.\shared\db\test_helpers [conflicted].py:111:    them deterministically. Safe to call multiple times; ON CONFLICT
.\shared\db\test_helpers [conflicted].py:146:                "ON CONFLICT (code) DO NOTHING",
.\shared\db\test_helpers [conflicted].py:164:            "ON CONFLICT (id) DO NOTHING",
.\shared\db\test_helpers [conflicted].py:285:    """Derive the admin-role connection URL from DATABASE_URL_SYNC.
.\shared\db\test_helpers [conflicted].py:289:      - ADMIN_DATABASE_URL: full URL, used directly if set
.\shared\db\test_helpers [conflicted].py:292:    override = os.environ.get("ADMIN_DATABASE_URL")
.\shared\db\test_helpers [conflicted].py:296:    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\shared\db\test_helpers [conflicted].py:299:            "seed_as_admin needs DATABASE_URL_SYNC (or ADMIN_DATABASE_URL) "
.\shared\db\test_helpers [conflicted].py:313:            f"seed_as_admin could not parse DATABASE_URL_SYNC as "
.\shared\db\test_helpers [conflicted].py:322:            f"Set ADMIN_DATABASE_URL to override."
.\docs\audit\_scratch\teammate4-notes.md:67:- Added BILLING_DATABASE_URL, DRUG_DB_DATABASE_URL, PRESCRIBER_DB_URL
.\docs\architecture\rls-pattern.md:125:Used by: FastAPI app processes serving tenant-facing HTTP requests. Connection string lives in `DATABASE_URL` per `.env.<tier>` files.
.\docs\architecture\rls-pattern.md:274:`scripts/load_sam.py`, `scripts/load_oig_leie.py`, `scripts/rerun_oig_cross_ref.py`, `scripts/load_nppes.py` etc. connect via `get_db_connection()` which reads `DATABASE_URL_SYNC` — currently pointing at `ifx_dev_app` (tenant role).
.\docs\architecture\rls-pattern.md:288:Migrations today run as the user in `DATABASE_URL_SYNC` — typically `ifx_dev_app` in dev. RLS doesn't interact with DDL (CREATE TABLE, ALTER TABLE, DROP TABLE are not row-level operations). Existing migrations continue to work unchanged.
.\shared\db\rule_instance_seeding.py:14:   ON CONFLICT DO UPDATE dance. Not bug-free.
.\shared\db\rule_instance_seeding.py:126:            "ON CONFLICT (id) DO UPDATE SET "
.\shared\db\rule_instance_seeding.py:133:        "do_nothing": "ON CONFLICT (id) DO NOTHING",
.\docs\architecture\exclusions-subsystem-audit.md:346:- 🟡 **[NEW — `.env.local` drift]** `.env.local` has `DATABASE_URL_SYNC=postgresql+asyncpg://...` (wrong — asyncpg is not sync). `.env.dev` is correctly `postgresql://...`. Hit during Wave 16b when alembic migrations failed with `MissingGreenlet`. Not exclusions-related, but filed here because it bit mid-wave. Fix should be a broader `.env.local` review.
.\docs\audit\_scratch\06-perf-deps.md:24:  - `modules/billing/src/db/session.py` — sync `create_engine`, no `pool_size`/`max_overflow` set
.\docs\audit\_scratch\06-perf-deps.md:25:  - `modules/drug-database/src/db/session.py` — sync `create_engine`, no pool config
.\docs\audit\_scratch\06-perf-deps.md:26:  - `modules/prescriber-directory/src/db/session.py` — sync `create_engine`, no pool config
.\docs\audit\_scratch\06-perf-deps.md:27:  - `modules/payment-processing/src/_shim/db.py` — sync `create_engine`
.\docs\audit\_scratch\06-perf-deps.md:28:  - `modules/reclaimrx/src/_shim/db.py` — sync `create_engine`
.\docs\audit\_scratch\06-perf-deps.md:29:  - `modules/core-platform/src/_shim/db.py` — sync `create_engine`
.\docs\architecture\phase-c-reference-data-rules-plan-v2.md:495:  per type, idempotent via ON CONFLICT).
.\docs\audit\_scratch\02-docs-process-config.md:86:`.env.example` is comprehensive and well-commented. It covers `DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`, `RABBITMQ_URL`, `JWT_SECRET` (with length hint), `STORAGE_PROVIDER`, `SMTP_HOST/PORT`, `OIG_EXCLUSION_URL`, `SAM_API_KEY`, `ENCRYPTION_KEY_ACTIVE`, and `MAX_UPLOAD_BYTES`. Comment included for how to generate the encryption key. `shared/config.py` has a module docstring explaining all fields and startup validation behavior.
.\docs\audit\_scratch\02-docs-process-config.md:88:Gap: Module-specific env vars (`DRUG_DB_DATABASE_URL`, `BILLING_DATABASE_URL`, `PRESCRIBER_DB_URL`) are not documented in `.env.example`. They only appear in the module's `session.py` fallback defaults.
.\docs\audit\_scratch\02-docs-process-config.md:208:   (fallback when `DRUG_DB_DATABASE_URL` not set)
.\docs\audit\_scratch\02-docs-process-config.md:214:   (fallback when `BILLING_DATABASE_URL` not set)
.\docs\audit\_scratch\02-docs-process-config.md:234:`shared/config.py` uses `pydantic_settings.BaseSettings` with required fields (`DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`, `RABBITMQ_URL`, `JWT_SECRET`) — missing values raise a `ValidationError` at startup. `JWT_SECRET` has a `min_length=32` validator. This is correct.
.\shared\db\engine.py:34:            settings.DATABASE_URL,
.\shared\tests\events\test_dlq_models.py:4:and composite-PK ON CONFLICT behaviour cannot be exercised on SQLite.
.\shared\tests\events\test_cross_module_events.py:44:# billing's default session provider requires BILLING_DATABASE_URL at
.\shared\tests\events\test_cross_module_events.py:45:# runtime. Mirror the canonical value from DATABASE_URL_SYNC so the
.\shared\tests\events\test_cross_module_events.py:49:_sync_url = os.environ.get("DATABASE_URL_SYNC") or ""
.\shared\tests\events\test_cross_module_events.py:50:if _sync_url and "BILLING_DATABASE_URL" not in os.environ:
.\shared\tests\events\test_cross_module_events.py:51:    os.environ["BILLING_DATABASE_URL"] = (
.\shared\tests\events\conftest.py:6:set TEST_DATABASE_URL or relied on the dev container — just against a
.\shared\data_ingestion\tests\test_state_medicaid_loader.py:37:from sqlalchemy import JSON, String, create_engine, event
.\shared\data_ingestion\tests\test_state_medicaid_loader.py:44:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_state_medicaid_loader.py:45:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_state_medicaid_loader.py:113:    raw = create_engine(
.\shared\tests\db\test_seed_as_admin.py:8:  3. URL derivation from DATABASE_URL_SYNC swaps correctly
.\shared\tests\db\test_seed_as_admin.py:11:Skipped when DATABASE_URL_SYNC isn't set or points at SQLite.
.\shared\tests\db\test_seed_as_admin.py:30:    DATABASE_URL_SYNC and produces the matching admin URL."""
.\shared\tests\db\test_seed_as_admin.py:35:    """With DATABASE_URL_SYNC pointing at ifx_dev_app, the helper must
.\shared\program_config_queries\accumulator.py:139:    INSERT tuple BEFORE ON CONFLICT resolution runs, so the usual
.\shared\program_config_queries\accumulator.py:203:        ON CONFLICT (tenant_id, member_id, drug_brand, program_id, calendar_year)
.\shared\tests\db\test_rule_instance_seeding.py:28:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\db\test_rule_instance_seeding.py:48:            ON CONFLICT (id) DO NOTHING
.\shared\tests\db\test_rule_instance_seeding.py:129:    from sqlalchemy import create_engine
.\shared\tests\db\test_rule_instance_seeding.py:133:    engine = create_engine(_resolve_admin_url())
.\shared\data_ingestion\tests\test_sam_exclusions.py:26:from sqlalchemy import JSON, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_sam_exclusions.py:33:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_sam_exclusions.py:34:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_sam_exclusions.py:104:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_rxnorm.py:33:from sqlalchemy import BigInteger, Integer, JSON, String, Text, create_engine, event
.\shared\data_ingestion\tests\test_rxnorm.py:43:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_rxnorm.py:44:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_rxnorm.py:207:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_orange_book.py:34:from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event, text
.\shared\data_ingestion\tests\test_orange_book.py:44:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_orange_book.py:45:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_orange_book.py:169:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_oig_leie.py:27:from sqlalchemy import JSON, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_oig_leie.py:34:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_oig_leie.py:35:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_oig_leie.py:100:    raw_engine = create_engine(
.\shared\tests\db\test_phi_mixin.py:18:from sqlalchemy import LargeBinary, create_engine
.\shared\tests\db\test_phi_mixin.py:53:    engine = create_engine("sqlite:///:memory:")
.\shared\tests\db\test_phase_a_tenant.py:17:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\db\test_phase_a_tenant.py:19:        pytest.skip("DATABASE_URL_SYNC needs to point at the dev Postgres")
.\shared\tests\db\test_engine_and_session.py:3:Drives real async connections to the configured DATABASE_URL — marked
.\shared\tests\db\test_engine_and_session.py:25:    ``shared.config.get_settings().DATABASE_URL`` at the ephemeral
.\shared\tests\db\test_engine_and_session.py:30:    DATABASE_URL env is set (dev DB or nothing). Patch at fixture
.\shared\tests\db\test_engine_and_session.py:36:    monkeypatch.setenv("DATABASE_URL", integration_postgres["url_async"])
.\shared\data_ingestion\tests\test_nppes.py:34:from sqlalchemy import JSON, Integer, String, Text, create_engine, event
.\shared\data_ingestion\tests\test_nppes.py:57:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_nppes.py:58:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_nppes.py:203:    raw = create_engine(
.\shared\observability\slow_query.py:17:    from sqlalchemy import create_engine
.\shared\observability\slow_query.py:20:    engine = create_engine(url)
.\shared\data_ingestion\tests\test_ncpdp_parser.py:34:from sqlalchemy import JSON, String, create_engine, event, select, text
.\shared\data_ingestion\tests\test_ncpdp_parser.py:44:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_ncpdp_parser.py:45:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_ncpdp_parser.py:213:    raw_engine = create_engine(
.\shared\tests\db\test_bank_holidays_model.py:19:from sqlalchemy import create_engine
.\shared\tests\db\test_bank_holidays_model.py:64:    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
.\shared\tests\db\test_bank_holidays_model.py:263:    env = {**os.environ, "DATABASE_URL_SYNC": ""}  # force asyncpg path in env.py
.\shared\tests\db\test_bank_holidays_model.py:285:    engine = create_async_engine(settings.DATABASE_URL)
.\shared\tests\db\test_bank_holidays_model.py:342:    engine = create_async_engine(settings.DATABASE_URL)
.\shared\data_ingestion\tests\test_medical_codes.py:31:from sqlalchemy import JSON, String, create_engine, event
.\shared\data_ingestion\tests\test_medical_codes.py:41:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_medical_codes.py:42:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_medical_codes.py:133:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_load_sam_script.py:16:CONFLICT target mismatch. The loader does not use ON CONFLICT —
.\shared\data_ingestion\tests\test_load_sam_script.py:34:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_load_sam_script.py:35:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_load_sam_script.py:284:    The loader does not use ON CONFLICT. It uses the module-level
.\shared\data_ingestion\tests\test_load_sam_script.py:290:    violated even without explicit ON CONFLICT.
.\shared\data_ingestion\tests\test_gov_exclusion.py:30:from sqlalchemy import JSON, String, create_engine, event
.\shared\data_ingestion\tests\test_gov_exclusion.py:37:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_gov_exclusion.py:38:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_gov_exclusion.py:93:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_fda_shortages.py:29:from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_fda_shortages.py:39:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_shortages.py:40:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_shortages.py:146:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_fda_shortages [conflicted].py:29:from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_fda_shortages [conflicted].py:39:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_shortages [conflicted].py:40:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_shortages [conflicted].py:146:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_fda_rems.py:32:from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_fda_rems.py:42:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_rems.py:43:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_rems.py:149:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_fda_purple_book.py:30:from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_fda_purple_book.py:40:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_purple_book.py:41:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_purple_book.py:144:    raw_engine = create_engine(
.\shared\tests\data_ingestion\test_pharmacy_tin_uei.py:23:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\data_ingestion\test_pharmacy_tin_uei.py:35:    from sqlalchemy import create_engine
.\shared\tests\data_ingestion\test_pharmacy_tin_uei.py:38:    engine = create_engine(_resolve_admin_url())
.\shared\tests\data_ingestion\test_pharmacy_tin_uei.py:61:            ON CONFLICT (ncpdp_provider_id) DO NOTHING
.\shared\data_ingestion\tests\test_fda_purple_book [conflicted].py:30:from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_fda_purple_book [conflicted].py:40:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_purple_book [conflicted].py:41:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_purple_book [conflicted].py:144:    raw_engine = create_engine(
.\shared\tests\data_ingestion\test_ncpdp_roster.py:26:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\data_ingestion\test_ncpdp_roster.py:37:    from sqlalchemy import create_engine
.\shared\tests\data_ingestion\test_ncpdp_roster.py:40:    engine = create_engine(_resolve_admin_url())
.\shared\data_ingestion\tests\test_fda_ndc_parser.py:29:from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_fda_ndc_parser.py:36:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_ndc_parser.py:37:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_fda_ndc_parser.py:148:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_dea.py:24:from sqlalchemy import JSON, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_dea.py:31:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_dea.py:32:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_dea.py:200:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_dea [conflicted].py:24:from sqlalchemy import JSON, Integer, String, create_engine, event
.\shared\data_ingestion\tests\test_dea [conflicted].py:31:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_dea [conflicted].py:32:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_dea [conflicted].py:200:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_cms_opt_out.py:27:from sqlalchemy import JSON, String, create_engine, event
.\shared\data_ingestion\tests\test_cms_opt_out.py:36:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_cms_opt_out.py:37:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_cms_opt_out.py:194:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_cms_opt_out.py:729:        """When dialect reports postgresql, pg_insert ON CONFLICT path is used."""
.\shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:27:from sqlalchemy import JSON, String, create_engine, event
.\shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:36:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:37:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:194:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_cms_opt_out [conflicted].py:729:        """When dialect reports postgresql, pg_insert ON CONFLICT path is used."""
.\shared\data_ingestion\tests\test_cms_nadac.py:35:from sqlalchemy import BigInteger, Integer, JSON, String, create_engine, event
.\shared\data_ingestion\tests\test_cms_nadac.py:42:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_cms_nadac.py:43:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_cms_nadac.py:145:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_cms_asp.py:29:from sqlalchemy import BigInteger, Integer, JSON, String, create_engine, event
.\shared\data_ingestion\tests\test_cms_asp.py:36:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_cms_asp.py:37:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\test_cms_asp.py:139:    raw_engine = create_engine(
.\shared\data_ingestion\tests\test_batching_copy.py:383:    assert "ON CONFLICT" in executed[2]
.\shared\tests\data_ingestion\dataq_ncpdp\test_full_ingest_integration.py:52:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\tests\data_ingestion\dataq_ncpdp\test_full_ingest_integration.py:86:    from sqlalchemy import create_engine  # noqa: PLC0415
.\shared\tests\data_ingestion\dataq_ncpdp\test_full_ingest_integration.py:94:    url = os.environ["DATABASE_URL_SYNC"]
.\shared\tests\data_ingestion\dataq_ncpdp\test_full_ingest_integration.py:103:    engine = create_engine(url, future=True)
.\shared\tests\data_ingestion\dataq_ncpdp\test_full_ingest_integration.py:199:    from sqlalchemy import create_engine  # noqa: PLC0415
.\shared\tests\data_ingestion\dataq_ncpdp\test_full_ingest_integration.py:202:    url = os.environ["DATABASE_URL_SYNC"]
.\shared\tests\data_ingestion\dataq_ncpdp\test_full_ingest_integration.py:205:    engine = create_engine(url, future=True)
.\shared\tests\crypto\test_sqlalchemy_types.py:9:from sqlalchemy import Column, Integer, String, create_engine, text
.\shared\tests\crypto\test_sqlalchemy_types.py:60:    eng = create_engine("sqlite:///:memory:", echo=False)
.\modules\member-management\tests\conftest.py:24:from sqlalchemy import JSON, String, create_engine, event
.\modules\member-management\tests\conftest.py:58:    engine = create_engine(
.\modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:6:  * `assert_awp_basis_acceptable` guard:
.\modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:32:    assert_awp_basis_acceptable,
.\modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:132:# assert_awp_basis_acceptable — consumer guard
.\modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:148:    result = assert_awp_basis_acceptable(
.\modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:166:    result = assert_awp_basis_acceptable(
.\modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:185:        assert_awp_basis_acceptable(
.\modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:203:        assert_awp_basis_acceptable(
.\modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:221:        assert_awp_basis_acceptable(
.\modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:239:        assert_awp_basis_acceptable(
.\modules\rules-engine\tests\unit\test_tier4_tier6_rules.py:442:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\rules-engine\tests\unit\test_tier4_tier6_rules.py:457:        from sqlalchemy import create_engine
.\modules\rules-engine\tests\unit\test_tier4_tier6_rules.py:461:        engine = create_engine(_resolve_admin_url())
.\modules\drug-database\tests\unit\test_nadac_pricing_lookup.py:29:from sqlalchemy import create_engine, event
.\modules\drug-database\tests\unit\test_nadac_pricing_lookup.py:48:    engine = create_engine(
.\modules\drug-database\tests\unit\test_infrastructure.py:12:from sqlalchemy import create_engine
.\modules\drug-database\tests\unit\test_infrastructure.py:29:    engine = create_engine(
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:90:        from sqlalchemy import create_engine
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:97:        engine = create_engine(
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:176:        from sqlalchemy import create_engine
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:183:        engine = create_engine(
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:265:        from sqlalchemy import create_engine
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:272:        engine = create_engine(
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:330:        from sqlalchemy import create_engine
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:337:        engine = create_engine(
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:373:        from sqlalchemy import create_engine
.\modules\drug-database\tests\unit\test_final_coverage_gaps.py:379:        engine = create_engine(
.\modules\drug-database\tests\unit\test_fdb_pricing_service.py:34:from sqlalchemy import create_engine, event
.\modules\drug-database\tests\unit\test_fdb_pricing_service.py:49:    engine = create_engine(
.\modules\drug-database\tests\unit\test_fdb_pricing_models.py:33:from sqlalchemy import create_engine, event, inspect, select
.\modules\drug-database\tests\unit\test_fdb_pricing_models.py:59:    engine = create_engine(
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:30:from sqlalchemy import create_engine, event
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:40:from drug_database.services.fdb_adapter import FDBDrop, FDBLocalDropAdapter
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:53:    engine = create_engine(
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:225:            # Delegate to the real FDBLocalDropAdapter — we just override
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:227:            real = FDBLocalDropAdapter(drop_.db_zip_path.parents[2])
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:408:# ON CONFLICT DO NOTHING — collision counting (Phase 10 / Item 4)
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:413:    """ON CONFLICT DO NOTHING skips duplicates atomically in a single round-trip.
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:423:    verifying the ON CONFLICT path returns correct inserted/duplicate counts
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:442:            real = FDBLocalDropAdapter(drop_.db_zip_path.parents[2])
.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:453:    # Row count unchanged — ON CONFLICT DO NOTHING is a no-op.
.\modules\drug-database\tests\unit\test_fdb_adapter.py:48:    FDBLocalDropAdapter,
.\modules\drug-database\tests\unit\test_fdb_adapter.py:151:    adapter = FDBLocalDropAdapter(root)
.\modules\drug-database\tests\unit\test_fdb_adapter.py:178:    adapter = FDBLocalDropAdapter(root)
.\modules\drug-database\tests\unit\test_fdb_adapter.py:196:    adapter = FDBLocalDropAdapter(root)
.\modules\drug-database\tests\unit\test_fdb_adapter.py:210:    adapter = FDBLocalDropAdapter(root)
.\modules\drug-database\tests\unit\test_fdb_adapter.py:221:    adapter = FDBLocalDropAdapter(root)
.\modules\drug-database\tests\unit\test_fdb_adapter.py:241:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:278:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:306:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:335:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:357:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:380:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:409:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:433:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:464:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:479:    """RNPTYPD0 (legacy 2-char-only catalog) — minimal 2-col TableSpec."""
.\modules\drug-database\tests\unit\test_fdb_adapter.py:488:    adapter = FDBLocalDropAdapter(tmp_path / "TEL251759D")
.\modules\drug-database\tests\unit\test_fdb_adapter.py:529:# Bonus — TableSpec values pass module-import-time invariants
.\modules\drug-database\tests\unit\test_fdb_adapter.py:534:    """All four Phase 8 TableSpec values exposed by the module."""
.\modules\drug-database\tests\unit\test_fdb_adapter.py:544:    """TableSpec is a frozen dataclass — values are constants."""
.\modules\drug-database\tests\unit\test_bench_fdb_lookup_script.py:193:        monkeypatch.delenv("DATABASE_URL_SYNC", raising=False)
.\modules\drug-database\tests\unit\test_bench_fdb_lookup_script.py:194:        monkeypatch.delenv("DATABASE_URL", raising=False)
.\modules\drug-database\tests\unit\test_bench_fdb_lookup_script.py:198:        assert "DATABASE_URL_SYNC" in err
.\modules\drug-database\tests\unit\test_bench_fdb_lookup_script.py:201:        monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://localhost/test")
.\modules\rules-engine\tests\unit\test_pa_timer_rule.py:48:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\rules-engine\tests\unit\test_pa_timer_rule.py:61:    from sqlalchemy import create_engine
.\modules\rules-engine\tests\unit\test_pa_timer_rule.py:65:    engine = create_engine(_resolve_admin_url())
.\modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:27:from sqlalchemy import MetaData, create_engine, inspect
.\modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:81:    engine = create_engine("sqlite:///:memory:")
.\modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:40:from sqlalchemy import create_engine, event
.\modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:105:    engine = create_engine(
.\modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:209:    from drug_database.services.fdb_adapter import FDBLocalDropAdapter
.\modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:215:    adapter = FDBLocalDropAdapter(Path("/nonexistent"))
.\modules\rules-engine\tests\integration\test_smoke_real_db.py:41:from sqlalchemy import create_engine, select  # noqa: E402
.\modules\rules-engine\tests\integration\test_smoke_real_db.py:52:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\rules-engine\tests\integration\test_smoke_real_db.py:54:        pytest.skip("DATABASE_URL_SYNC not set; smoke test needs the dev DB")
.\modules\rules-engine\tests\integration\test_smoke_real_db.py:56:        pytest.skip("DATABASE_URL_SYNC points at SQLite; smoke test needs Postgres")
.\modules\rules-engine\tests\integration\test_smoke_real_db.py:72:    url = os.environ["DATABASE_URL_SYNC"].replace("+asyncpg", "+psycopg2")
.\modules\rules-engine\tests\integration\test_smoke_real_db.py:73:    engine = create_engine(url, future=True)
.\modules\rules-engine\tests\integration\test_rule_loader.py:29:from sqlalchemy import create_engine  # noqa: E402
.\modules\rules-engine\tests\integration\test_rule_loader.py:38:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\rules-engine\tests\integration\test_rule_loader.py:40:        pytest.skip("DATABASE_URL_SYNC not set; loader test needs dev DB")
.\modules\rules-engine\tests\integration\test_rule_loader.py:49:    url = os.environ["DATABASE_URL_SYNC"].replace("+asyncpg", "+psycopg2")
.\modules\rules-engine\tests\integration\test_rule_loader.py:50:    engine = create_engine(url, future=True)
.\modules\rules-engine\tests\integration\test_rule_loader.py:74:            "VALUES (%s, %s, %s, %s, 'active') ON CONFLICT (id) DO NOTHING",
.\modules\drug-database\tests\integration\test_coverage_gaps_integration.py:19:from sqlalchemy import create_engine
.\modules\drug-database\tests\integration\test_coverage_gaps_integration.py:33:    engine = create_engine(
.\modules\drug-database\tests\integration\test_app_middleware.py:17:from sqlalchemy import create_engine
.\modules\drug-database\tests\integration\test_app_middleware.py:29:    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
.\modules\drug-database\tests\integration\test_api_router_coverage.py:15:from sqlalchemy import create_engine
.\modules\drug-database\tests\integration\test_api_router_coverage.py:34:    engine = create_engine(
.\modules\drug-database\tests\integration\test_api_router_coverage.py:232:# `TableSpec`-driven surface per SPEC §3.7.2 (codex MF5 fix). New
.\modules\drug-database\tests\integration\test_api_endpoints.py:20:from sqlalchemy import create_engine
.\modules\drug-database\tests\integration\test_api_endpoints.py:45:    engine = create_engine(
.\modules\drug-database\tests\conftest.py:17:from sqlalchemy import create_engine, event
.\modules\drug-database\tests\conftest.py:26:    engine = create_engine(
.\modules\rebate-management\src\db\session.py:9:from sqlalchemy import create_engine
.\modules\rebate-management\src\db\session.py:21:        db_url = os.environ.get("REBATE_DATABASE_URL")
.\modules\rebate-management\src\db\session.py:24:                "REBATE_DATABASE_URL environment variable is required but not set. "
.\modules\rebate-management\src\db\session.py:27:        _engine = create_engine(db_url, pool_pre_ping=True)
.\modules\prescriber-directory\tests\unit\test_exclusion_columns.py:21:from sqlalchemy import create_engine, select
.\modules\prescriber-directory\tests\unit\test_exclusion_columns.py:31:    eng = create_engine(
.\modules\prescriber-directory\tests\unit\test_db_session.py:15:from sqlalchemy import create_engine
.\modules\prescriber-directory\tests\unit\test_db_session.py:34:        engine = create_engine(
.\modules\prescriber-directory\tests\unit\test_db_session.py:57:        engine = create_engine(
.\modules\prescriber-directory\tests\unit\test_db_session.py:72:        engine = create_engine(
.\modules\prescriber-directory\tests\unit\test_db_session.py:90:        engine = create_engine(
.\modules\prescriber-directory\tests\unit\test_db_session.py:106:        engine = create_engine(
.\modules\prescriber-directory\tests\unit\test_credential_monitor.py:17:from sqlalchemy import create_engine, select
.\modules\prescriber-directory\tests\unit\test_credential_monitor.py:28:    engine = create_engine(
.\modules\drug-database\src\services\pricing_ingestion.py:3:This file used to hand-roll per-batch commits, in-batch dedup, ON CONFLICT
.\modules\drug-database\src\services\fda_supplementary_ingestion.py:14:  - INSERT ON CONFLICT DO UPDATE for current-state tables.
.\modules\drug-database\src\services\fda_supplementary_ingestion.py:69:    drug_shortages: INSERT ON CONFLICT DO UPDATE.
.\modules\prescriber-directory\tests\conftest.py:29:from sqlalchemy import create_engine, event
.\modules\prescriber-directory\tests\conftest.py:99:    engine = create_engine(
.\modules\prescriber-directory\src\services\nppes_upsert.py:4:primitive: in-batch dedup, pg_insert + ``ON CONFLICT DO UPDATE``, per-batch
.\modules\prescriber-directory\src\services\nppes_upsert.py:9:statements per 500-row batch; this path issues one INSERT ... ON CONFLICT
.\modules\prescriber-directory\src\services\nppes_upsert.py:17:``ON CONFLICT DO UPDATE`` clause leaves them untouched.
.\modules\prescriber-directory\src\services\nppes_upsert.py:42:# excluded from the ``ON CONFLICT DO UPDATE`` SET clause.
.\modules\rules-engine\alembic\env.py:8:Uses synchronous alembic (engine_from_config + psycopg2). DATABASE_URL_SYNC
.\modules\rules-engine\alembic\env.py:60:# Allow DATABASE_URL env override (for CI / Docker)
.\modules\rules-engine\alembic\env.py:61:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\rules-engine\alembic\env.py:71:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\rules-engine\alembic\env.py:73:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\modules\prescriber-directory\src\services\nppes_ingestion.py:340:# Pharmacy supplement (unchanged from pre-Wave-11 — already uses ON CONFLICT)
.\modules\prescriber-directory\src\services\nppes_ingestion.py:398:            ON CONFLICT (npi) DO UPDATE SET
.\modules\drug-database\src\db\session.py:3:M-16: No hardcoded DB URL fallback. DRUG_DB_DATABASE_URL must be set
.\modules\drug-database\src\db\session.py:12:from sqlalchemy import create_engine
.\modules\drug-database\src\db\session.py:24:        db_url = os.environ.get("DRUG_DB_DATABASE_URL")
.\modules\drug-database\src\db\session.py:27:                "DRUG_DB_DATABASE_URL environment variable is required but not set. "
.\modules\drug-database\src\db\session.py:30:        _engine = create_engine(db_url, pool_pre_ping=True)
.\modules\program-config\tests\integration\test_smoke_real_db.py:38:from sqlalchemy import create_engine, select  # noqa: E402
.\modules\program-config\tests\integration\test_smoke_real_db.py:49:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\program-config\tests\integration\test_smoke_real_db.py:51:        pytest.skip("DATABASE_URL_SYNC not set; smoke test needs the dev DB")
.\modules\program-config\tests\integration\test_smoke_real_db.py:53:        pytest.skip("DATABASE_URL_SYNC points at SQLite; smoke test needs Postgres")
.\modules\program-config\tests\integration\test_smoke_real_db.py:69:    url = os.environ["DATABASE_URL_SYNC"].replace("+asyncpg", "+psycopg2")
.\modules\program-config\tests\integration\test_smoke_real_db.py:70:    engine = create_engine(url, future=True)
.\modules\billing\tests\unit\test_tenant_loader_wired.py:11:from sqlalchemy import create_engine
.\modules\billing\tests\unit\test_tenant_loader_wired.py:20:    return create_engine(
.\modules\drug-database\README [conflicted].md:18:- **FDB Adapter** — `FDBLocalDropAdapter` reads operator-managed NDDF Plus drops at `data/reference/fdb/TEL251759D/`. Generic `TableSpec`-driven surface (SPEC §3.7.2): `discover_latest_drop` / `open_table` / `parse_table`. Phase 8 TableSpec values: `RNP3_NDC_PRICE` (+ UPD variant), `RPRDPTD0_PRICE_TYPE_DESC`, `RNPTYPD0_NDC_PRICE_TYPE_DESC`. Hot-path `parse_rnp3` typed wrapper for the ingester's main loop.
.\modules\billing\tests\integration\test_wired_routes.py:20:from sqlalchemy import create_engine, event
.\modules\billing\tests\integration\test_wired_routes.py:68:    engine = create_engine(
.\modules\billing\tests\integration\test_rls_tenant_isolation.py:12:Skipped when DATABASE_URL_SYNC isn't set or points at SQLite.
.\modules\billing\tests\integration\test_rls_tenant_isolation.py:38:    url = os.environ["DATABASE_URL_SYNC"]
.\modules\prescriber-directory\src\db\session.py:18:from sqlalchemy import create_engine
.\modules\prescriber-directory\src\db\session.py:37:        _engine = create_engine(db_url, pool_pre_ping=True, future=True)
.\modules\drug-database\drug_database\services\pricing_ingestion.py:3:This file used to hand-roll per-batch commits, in-batch dedup, ON CONFLICT
.\modules\billing\tests\integration\test_consumer_app_wired.py:46:    from sqlalchemy import create_engine
.\modules\billing\tests\integration\test_consumer_app_wired.py:48:    private_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, future=True)
.\modules\billing\tests\integration\test_consumer_app_wired.py:76:    # Make BILLING_DATABASE_URL non-empty so `_get_engine()` doesn't
.\modules\billing\tests\integration\test_consumer_app_wired.py:78:    monkeypatch.setenv("BILLING_DATABASE_URL", "sqlite:///:memory:")
.\modules\billing\tests\integration\test_api_routes.py:10:from sqlalchemy import create_engine, event
.\modules\billing\tests\integration\test_api_routes.py:33:    engine = create_engine(
.\modules\drug-database\drug_database\services\fdb_pricing_ingester.py:20:  re-run of the same drop produces 0 net new rows — ON CONFLICT DO
.\modules\drug-database\drug_database\services\fdb_pricing_ingester.py:42:    (config flag `fdb_load_product_prices=False` is the default).
.\modules\drug-database\drug_database\services\fdb_pricing_ingester.py:46:    Decimal in the TableSpec (09.3).
.\modules\drug-database\drug_database\services\fdb_pricing_ingester.py:380:        """Flush one batch using ON CONFLICT DO NOTHING — one commit per batch.
.\modules\drug-database\drug_database\services\fdb_adapter.py:5:`parse_dosing`) with a generic `TableSpec`-driven surface — codex MF5
.\modules\drug-database\drug_database\services\fdb_adapter.py:16:  TableSpec: schema-driving dataclass (columns + coercers + filters).
.\modules\drug-database\drug_database\services\fdb_adapter.py:19:  FDBLocalDropAdapter: file-system concrete adapter for operator-
.\modules\drug-database\drug_database\services\fdb_adapter.py:22:  Four TableSpec values for Phase 8: RNP3_NDC_PRICE (+ _UPD variant),
.\modules\drug-database\drug_database\services\fdb_adapter.py:30:  * New tables become data (TableSpec values), not interface methods.
.\modules\drug-database\drug_database\services\fdb_adapter.py:39:  * surgical-changes.md — TableSpec values only as SPEC §3.7.2 lists
.\modules\drug-database\drug_database\services\fdb_adapter.py:88:    coercer for RNP3 + RPRDPP0 TableSpecs.
.\modules\drug-database\drug_database\services\fdb_adapter.py:145:class TableSpec:
.\modules\drug-database\drug_database\services\fdb_adapter.py:149:    become new TableSpec values — no FDBAdapter method needed for
.\modules\drug-database\drug_database\services\fdb_adapter.py:187:    TableSpec. Loading into Postgres is delegated to the ingester
.\modules\drug-database\drug_database\services\fdb_adapter.py:219:        spec: TableSpec,
.\modules\drug-database\drug_database\services\fdb_adapter.py:223:        """Parse one FDB table per the given TableSpec.
.\modules\drug-database\drug_database\services\fdb_adapter.py:265:    via TableSpec.coercers in `parse_table`.
.\modules\drug-database\drug_database\services\fdb_adapter.py:301:class FDBLocalDropAdapter(FDBAdapter):
.\modules\drug-database\drug_database\services\fdb_adapter.py:397:    # parse_table — generic body (works for any TableSpec)
.\modules\drug-database\drug_database\services\fdb_adapter.py:403:        spec: TableSpec,
.\modules\drug-database\drug_database\services\fdb_adapter.py:483:# Phase 8 TableSpec values (SPEC §3.7.2)
.\modules\drug-database\drug_database\services\fdb_adapter.py:487:RNP3_NDC_PRICE = TableSpec(
.\modules\drug-database\drug_database\services\fdb_adapter.py:503:RPRDPTD0_PRICE_TYPE_DESC = TableSpec(
.\modules\drug-database\drug_database\services\fdb_adapter.py:524:RNPTYPD0_NDC_PRICE_TYPE_DESC = TableSpec(  # legacy 2-char-only catalog
.\modules\drug-database\drug_database\services\fdb_adapter.py:540:    Field renames vs. raw TableSpec output:
.\modules\drug-database\drug_database\services\fdb_adapter.py:583:    "FDBLocalDropAdapter",
.\modules\drug-database\drug_database\services\fdb_adapter.py:588:    "TableSpec",
.\modules\drug-database\drug_database\services\fda_supplementary_ingestion.py:14:  - INSERT ON CONFLICT DO UPDATE for current-state tables.
.\modules\drug-database\drug_database\services\fda_supplementary_ingestion.py:69:    drug_shortages: INSERT ON CONFLICT DO UPDATE.
.\modules\reporting\tests\integration\test_smoke_real_db.py:30:from sqlalchemy import create_engine, select, text
.\modules\reporting\tests\integration\test_smoke_real_db.py:57:    engine = create_engine(integration_postgres["url_sync"], future=True)
.\modules\billing\tests\conftest.py:17:from sqlalchemy import create_engine, event
.\modules\billing\tests\conftest.py:24:    engine = create_engine(
.\modules\drug-database\alembic\env.py:12:Uses synchronous alembic (engine_from_config + psycopg2). DATABASE_URL_SYNC
.\modules\drug-database\alembic\env.py:62:_DB_URL = _SETTINGS.DATABASE_URL_SYNC or _SETTINGS.DATABASE_URL
.\modules\drug-database\alembic\env.py:80:    DATABASE_URL_SYNC drifts to ``postgresql+asyncpg://``.
.\modules\drug-database\alembic\env.py:85:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\drug-database\alembic\env.py:87:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\modules\reporting\alembic\env.py:7:Uses synchronous alembic (engine_from_config + psycopg2). DATABASE_URL_SYNC
.\modules\reporting\alembic\env.py:59:# Allow DATABASE_URL env override (for CI / Docker)
.\modules\reporting\alembic\env.py:60:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\reporting\alembic\env.py:70:    DATABASE_URL_SYNC drifts to ``postgresql+asyncpg://``.
.\modules\reporting\alembic\env.py:75:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\reporting\alembic\env.py:77:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\modules\program-config\alembic\env.py:8:DATABASE_URL_SYNC must NOT contain the +asyncpg driver prefix.
.\modules\program-config\alembic\env.py:52:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\program-config\alembic\env.py:61:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix."
.\modules\prescriber-directory\alembic\env.py:54:# Allow DATABASE_URL env override (for CI / Docker)
.\modules\prescriber-directory\alembic\env.py:55:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\prescriber-directory\alembic\env.py:65:    DATABASE_URL_SYNC drifts to ``postgresql+asyncpg://``.
.\modules\prescriber-directory\alembic\env.py:70:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\prescriber-directory\alembic\env.py:72:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\modules\medical-claims\tests\unit\test_clients.py:411:        """Base URL is read from DRUG_DATABASE_URL env var."""
.\modules\medical-claims\tests\unit\test_clients.py:412:        monkeypatch.setenv("DRUG_DATABASE_URL", "http://drug-svc:9002")
.\modules\drug-database\drug_database\db\session.py:3:M-16: No hardcoded DB URL fallback. DRUG_DB_DATABASE_URL must be set
.\modules\drug-database\drug_database\db\session.py:12:from sqlalchemy import create_engine
.\modules\drug-database\drug_database\db\session.py:24:        db_url = os.environ.get("DRUG_DB_DATABASE_URL")
.\modules\drug-database\drug_database\db\session.py:27:                "DRUG_DB_DATABASE_URL environment variable is required but not set. "
.\modules\drug-database\drug_database\db\session.py:30:        _engine = create_engine(db_url, pool_pre_ping=True)
.\modules\paysync\tests\integration\test_wave39_e2e.py:26:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_wave39_e2e.py:87:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_wave38_e2e.py:24:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_wave38_e2e.py:80:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_wave37_e2e.py:22:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_wave37_e2e.py:87:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_wave37_e2e.py:120:            ON CONFLICT (tenant_id, cardholder_id, date_of_birth) DO NOTHING
.\modules\paysync\tests\integration\test_schema_smoke.py:9:Skips when DATABASE_URL_SYNC is unset (CI without DB).
.\modules\paysync\tests\integration\test_saasant_exports.py:16:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_saasant_exports.py:61:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_reconciliation.py:15:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_reconciliation.py:74:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\billing\src\events\__init__.py:38:    sets BILLING_DATABASE_URL doesn't blow up at module import time.
.\modules\paysync\tests\integration\test_pay_to_resolution.py:15:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_pay_to_resolution.py:76:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_nrid_router.py:12:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_nrid_router.py:52:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_nrid_router.py:289:    eng = create_engine(TENANT_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\medical-claims\tests\conftest.py:31:from sqlalchemy import JSON, String, create_engine, event
.\modules\medical-claims\tests\conftest.py:103:    engine = create_engine(
.\modules\paysync\tests\integration\test_nacha_generator.py:17:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_nacha_generator.py:78:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_manual_ap_records.py:13:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_manual_ap_records.py:54:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_invoice_sequences.py:13:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_invoice_sequences.py:56:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_invoice_sequences.py:202:    create_engine_url = ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
.\modules\paysync\tests\integration\test_invoice_sequences.py:206:    seed_engine = create_engine(create_engine_url, future=True)
.\modules\paysync\tests\integration\test_invoice_sequences.py:227:            local_engine = create_engine(create_engine_url, future=True)
.\modules\paysync\tests\integration\test_invoice_sequences.py:253:    cleanup_engine = create_engine(create_engine_url, future=True)
.\modules\paysync\tests\integration\test_invoice_sequences.py:400:    eng = create_engine(tenant_url.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\plan-design\tests\conftest.py:32:from sqlalchemy import JSON, String, create_engine, event
.\modules\plan-design\tests\conftest.py:92:    engine = create_engine(
.\modules\paysync\tests\integration\test_invoice_generator.py:15:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_invoice_generator.py:58:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_ingester.py:6:  - idempotent ON CONFLICT upsert
.\modules\paysync\tests\integration\test_ingester.py:27:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_ingester.py:77:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_ingester.py:187:    """ON CONFLICT DO UPDATE: re-import with new total_pay overwrites."""
.\modules\paysync\tests\integration\test_export_templates.py:16:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_export_templates.py:60:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\billing\src\db\session.py:11:M-16: No hardcoded DB URL fallback. BILLING_DATABASE_URL must be set
.\modules\billing\src\db\session.py:21:from sqlalchemy import create_engine
.\modules\billing\src\db\session.py:33:        db_url = os.environ.get("BILLING_DATABASE_URL")
.\modules\billing\src\db\session.py:36:                "BILLING_DATABASE_URL environment variable is required but not set. "
.\modules\billing\src\db\session.py:39:        _engine = create_engine(db_url, pool_pre_ping=True)
.\modules\prior-authorization\tests\conftest.py:32:from sqlalchemy import JSON, String, create_engine, event
.\modules\prior-authorization\tests\conftest.py:84:    engine = create_engine(
.\modules\paysync\tests\integration\test_email_sender.py:14:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_email_sender.py:64:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_eight_thirty_five.py:16:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_eight_thirty_five.py:79:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_eight_thirty_five.py:136:            ON CONFLICT (tenant_id, cardholder_id, date_of_birth) DO NOTHING
.\modules\paysync\tests\integration\test_eight_thirty_five.py:182:            ON CONFLICT (ncpdp_provider_id) DO NOTHING
.\modules\paysync\tests\integration\test_echo_status_ingester.py:17:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_echo_status_ingester.py:60:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_echo_spec_400_generator.py:14:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_echo_spec_400_generator.py:59:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\billing\alembic\env.py:67:# Allow DATABASE_URL env override (for CI / Docker)
.\modules\billing\alembic\env.py:68:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\billing\alembic\env.py:78:    DATABASE_URL_SYNC drifts to ``postgresql+asyncpg://``.
.\modules\billing\alembic\env.py:83:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\billing\alembic\env.py:85:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\modules\paysync\tests\integration\test_echo_sftp_delivery.py:22:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_echo_sftp_delivery.py:75:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_echo_daily_candor.py:21:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_echo_daily_candor.py:72:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_cycle_schedules.py:13:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_cycle_schedules.py:54:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_cycle_manager.py:12:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_cycle_manager.py:51:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_cycle_close_orchestrator.py:15:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_cycle_close_orchestrator.py:75:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_carryovers.py:14:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_carryovers.py:56:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_batch_generator.py:15:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_batch_generator.py:76:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\tests\integration\test_bank_settlements.py:15:from sqlalchemy import create_engine, text
.\modules\paysync\tests\integration\test_bank_settlements.py:73:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\shared\data_ingestion\dataq_ncpdp\__main__.py:11:  DATABASE_URL_SYNC — admin-role URL. Migrations + TRUNCATE
.\shared\data_ingestion\dataq_ncpdp\__main__.py:32:from sqlalchemy import create_engine
.\shared\data_ingestion\dataq_ncpdp\__main__.py:82:    db_url = os.environ.get("DATABASE_URL_SYNC")
.\shared\data_ingestion\dataq_ncpdp\__main__.py:84:        print("ERROR: DATABASE_URL_SYNC not set", file=sys.stderr)
.\shared\data_ingestion\dataq_ncpdp\__main__.py:125:        engine = create_engine(db_url, future=True)
.\modules\maxacc-registry\tests\integration\test_vendor_pbm_seed.py:10:from sqlalchemy import create_engine, text
.\modules\maxacc-registry\tests\integration\test_vendor_pbm_seed.py:41:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\maxacc-registry\tests\integration\test_scraper_output.py:12:from sqlalchemy import create_engine, text
.\modules\maxacc-registry\tests\integration\test_scraper_output.py:37:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\shared\data_ingestion\dataq_ncpdp\README.md:144:DATABASE_URL_SYNC="postgresql://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev" \
.\shared\data_ingestion\dataq_ncpdp\README.md:148:DATABASE_URL_SYNC="postgresql://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev" \
.\shared\data_ingestion\dataq_ncpdp\README.md:180:DATABASE_URL_SYNC="<admin-url>" \
.\shared\data_ingestion\dataq_ncpdp\README.md:184:DATABASE_URL_SYNC="<admin-url>" \
.\shared\data_ingestion\dataq_ncpdp\README.md:289:$ DATABASE_URL_SYNC="postgresql://ifx_dev_admin:..." \
.\modules\maxacc-registry\tests\integration\test_lookup.py:19:from sqlalchemy import create_engine, text
.\modules\maxacc-registry\tests\integration\test_lookup.py:49:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\maxacc-registry\tests\integration\test_e2e_pipeline.py:28:from sqlalchemy import create_engine, text
.\modules\maxacc-registry\tests\integration\test_e2e_pipeline.py:58:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\maxacc-registry\tests\integration\test_curated_seed.py:11:from sqlalchemy import create_engine, text
.\modules\maxacc-registry\tests\integration\test_curated_seed.py:35:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\plan-design\src\db\session.py:4:installed. PLAN_DESIGN_DATABASE_URL environment variable required.
.\modules\plan-design\src\db\session.py:13:from sqlalchemy import create_engine
.\modules\plan-design\src\db\session.py:25:        db_url = os.environ.get("PLAN_DESIGN_DATABASE_URL")
.\modules\plan-design\src\db\session.py:28:                "PLAN_DESIGN_DATABASE_URL environment variable is required but not set. "
.\modules\plan-design\src\db\session.py:31:        _engine = create_engine(db_url, pool_pre_ping=True)
.\modules\maxacc-registry\src\maxacc_registry\seeding\vendor_pbm_seed.py:163:                ON CONFLICT (vendor_name) DO UPDATE SET
.\modules\ai-nlp\tests\integration\test_smoke_real_db.py:30:from sqlalchemy import create_engine, select, text
.\modules\ai-nlp\tests\integration\test_smoke_real_db.py:56:    engine = create_engine(integration_postgres["url_sync"], future=True)
.\modules\ai-nlp\tests\integration\test_schema_smoke.py:5:psycopg2 (not mocked). Skipped when DATABASE_URL_SYNC is unset or
.\modules\ai-nlp\tests\integration\test_schema_smoke.py:39:    ``seed_as_admin`` helper (which reads DATABASE_URL_SYNC) sees the
.\modules\ai-nlp\tests\integration\test_rls_tenant_isolation.py:22:Skipped when DATABASE_URL_SYNC isn't set or points at SQLite.
.\modules\ai-nlp\tests\integration\test_rls_tenant_isolation.py:42:    """Wave 21b: depend on the testcontainers fixture so DATABASE_URL_SYNC
.\modules\ai-nlp\tests\integration\test_rls_tenant_isolation.py:50:    url = os.environ["DATABASE_URL_SYNC"]
.\modules\paysync\src\paysync\__main__.py:24:from sqlalchemy import create_engine, text
.\modules\paysync\src\paysync\__main__.py:29:    db_url = url or os.environ.get("DATABASE_URL_SYNC")
.\modules\paysync\src\paysync\__main__.py:32:            "DATABASE_URL_SYNC env var or --db-url required"
.\modules\paysync\src\paysync\__main__.py:34:    return create_engine(db_url.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\paysync\src\paysync\__main__.py:86:    p_import.add_argument("--db-url", default=None, help="override DATABASE_URL_SYNC")
.\modules\reclaimrx\tests\conftest.py:7:from sqlalchemy import create_engine, event
.\modules\reclaimrx\tests\conftest.py:26:    eng = create_engine(
.\modules\medical-claims\src\clients\drug_database_client.py:98:        self._base_url = (base_url or os.environ.get("DRUG_DATABASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
.\modules\medical-claims\src\clients\drug_database_client.py:116:        GET {DRUG_DATABASE_URL}/api/v1/drugs/lookup/{ndc}
.\modules\medical-claims\src\clients\drug_database_client.py:179:        GET {DRUG_DATABASE_URL}/api/v1/drugs/pricing/{ndc}
.\modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:361:    from sqlalchemy import create_engine
.\modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:364:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:366:        raise SystemExit("DATABASE_URL_SYNC env var required")
.\modules\maxacc-registry\src\maxacc_registry\ingest\scraper_output.py:369:    engine = create_engine(url, future=True)
.\modules\maxacc-registry\src\maxacc_registry\ingest\curated_seed.py:414:    from sqlalchemy import create_engine
.\modules\maxacc-registry\src\maxacc_registry\ingest\curated_seed.py:417:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\maxacc-registry\src\maxacc_registry\ingest\curated_seed.py:419:        raise SystemExit("DATABASE_URL_SYNC env var required")
.\modules\maxacc-registry\src\maxacc_registry\ingest\curated_seed.py:422:    engine = create_engine(url, future=True)
.\modules\reclaimrx\src\_shim\db.py:20:from sqlalchemy import create_engine
.\modules\reclaimrx\src\_shim\db.py:41:    _engine = create_engine(url, future=True, connect_args=connect_args)
.\modules\reclaimrx\tests\wave44b\integration\test_ml_schema_and_training.py:20:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave44b\integration\test_ml_schema_and_training.py:49:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\reclaimrx\tests\wave44b\integration\test_ml_schema_and_training.py:57:    eng = create_engine(TENANT_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\reclaimrx\tests\wave44b\integration\test_ml_schema_and_training.py:215:    eng_b = create_engine(
.\modules\reclaimrx\tests\wave44b\integration\test_m7_catalog_and_registry.py:20:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave44b\integration\test_m7_catalog_and_registry.py:45:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\reclaimrx\tests\wave44b\integration\test_flagged_npis.py:18:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave44b\integration\test_flagged_npis.py:50:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\maxacc-registry\alembic\versions\0002_vendor_pbm_seed.py:71:            ON CONFLICT (vendor_name) DO UPDATE SET
.\modules\reclaimrx\tests\wave44b\integration\test_baseline_extensions.py:23:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave44b\integration\test_baseline_extensions.py:50:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\maxacc-registry\alembic\env.py:8:``DATABASE_URL_SYNC`` must NOT contain the +asyncpg driver prefix.
.\modules\maxacc-registry\alembic\env.py:42:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\maxacc-registry\alembic\env.py:51:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix."
.\modules\paysync\src\paysync\importers\ingester.py:21:Idempotency: ON CONFLICT (tenant_id, auth_num) DO UPDATE.
.\modules\paysync\src\paysync\importers\ingester.py:266:    ON CONFLICT (tenant_id, auth_num) DO UPDATE SET
.\modules\paysync\src\paysync\importers\ingester.py:459:            ON CONFLICT (tenant_id, claim_id) DO UPDATE
.\modules\paysync\src\paysync\importers\ingester.py:752:            # On ON CONFLICT UPDATE the row's id may not match payload['id'];
.\modules\reclaimrx\tests\wave43\integration\test_multi_rule_e2e.py:27:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave43\integration\test_multi_rule_e2e.py:56:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\reclaimrx\tests\wave43\integration\test_history_providers.py:20:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave43\integration\test_history_providers.py:53:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\reclaimrx\tests\wave43\integration\test_evaluator_e2e.py:21:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave43\integration\test_evaluator_e2e.py:56:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\paysync\scripts\validation_run\generate_single_nacha.py:17:    DATABASE_URL_SYNC=... .venv/bin/python \\
.\modules\paysync\scripts\validation_run\generate_single_nacha.py:21:    DATABASE_URL_SYNC=... .venv/bin/python \\
.\modules\paysync\scripts\validation_run\generate_single_nacha.py:50:from sqlalchemy import create_engine, text  # noqa: E402
.\modules\paysync\scripts\validation_run\generate_single_nacha.py:61:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\paysync\scripts\validation_run\generate_single_nacha.py:64:            "ERROR: DATABASE_URL_SYNC not set. Example:\n"
.\modules\paysync\scripts\validation_run\generate_single_nacha.py:65:            "  export DATABASE_URL_SYNC=postgresql+psycopg2://ifx_dev_admin:"
.\modules\paysync\scripts\validation_run\generate_single_nacha.py:135:    engine = create_engine(_engine_url(), future=True)
.\modules\reclaimrx\tests\wave43\integration\test_baseline_provider.py:12:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave43\integration\test_baseline_provider.py:39:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\paysync\scripts\validation_run\generate_single_835.py:11:    DATABASE_URL_SYNC=... .venv/bin/python \\
.\modules\paysync\scripts\validation_run\generate_single_835.py:15:    DATABASE_URL_SYNC=... .venv/bin/python \\
.\modules\paysync\scripts\validation_run\generate_single_835.py:54:from sqlalchemy import create_engine, text  # noqa: E402
.\modules\paysync\scripts\validation_run\generate_single_835.py:67:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\paysync\scripts\validation_run\generate_single_835.py:70:            "ERROR: DATABASE_URL_SYNC not set. Example:\n"
.\modules\paysync\scripts\validation_run\generate_single_835.py:71:            "  export DATABASE_URL_SYNC=postgresql+psycopg2://ifx_dev_admin:"
.\modules\paysync\scripts\validation_run\generate_single_835.py:106:    engine = create_engine(_engine_url(), future=True)
.\modules\paysync\README.md:23:3. **Claims ingester** — idempotent ON CONFLICT upsert against
.\modules\paysync\README.md:538:DATABASE_URL_SYNC=postgresql://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev \
.\modules\paysync\README.md:547:DATABASE_URL_SYNC=postgresql://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev \
.\modules\reclaimrx\tests\wave42\integration\test_ingesters.py:23:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave42\integration\test_ingesters.py:57:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\reclaimrx\tests\wave42\integration\test_ingesters.py:310:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\reclaimrx\tests\wave42\integration\test_hierarchy_resolver.py:25:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave42\integration\test_hierarchy_resolver.py:53:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\reclaimrx\tests\wave42\integration\test_case_manager.py:17:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave42\integration\test_case_manager.py:60:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\reclaimrx\tests\wave42\integration\test_anomaly_repository.py:17:from sqlalchemy import create_engine, text
.\modules\reclaimrx\tests\wave42\integration\test_anomaly_repository.py:54:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://"))
.\modules\paysync\src\paysync\echo\README.md:76:from sqlalchemy import create_engine
.\modules\paysync\src\paysync\echo\README.md:81:engine = create_engine('postgresql://...')
.\shared\data_ingestion\common.py:22:    psycopg2 connection factory from DATABASE_URL_SYNC (falls back to
.\shared\data_ingestion\common.py:23:    DATABASE_URL). Strips SQLAlchemy driver prefixes. Caller owns
.\shared\data_ingestion\common.py:137:    """Return a new psycopg2 connection using DATABASE_URL_SYNC.
.\shared\data_ingestion\common.py:144:    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\shared\data_ingestion\common.py:147:            "DATABASE_URL_SYNC / DATABASE_URL not set — cannot connect to Postgres."
.\shared\data_ingestion\batching.py:9:  triggered ``UniqueViolation`` because ``ON CONFLICT ... DO UPDATE`` does not
.\shared\data_ingestion\batching.py:120:    ``table`` with ``ON CONFLICT DO NOTHING`` on ``unique_key``.
.\shared\data_ingestion\batching.py:141:    * ``unique_key`` — list of column names that form the ON CONFLICT target
.\shared\data_ingestion\batching.py:155:      ``SET`` clause of ``ON CONFLICT DO UPDATE`` (defaults to ``id`` +
.\shared\data_ingestion\batching.py:389:        """Execute one ``INSERT ... ON CONFLICT`` statement for the batch.
.\shared\data_ingestion\batching.py:416:        """Emit a history row — ON CONFLICT DO NOTHING on the history unique key."""
.\shared\data_ingestion\batching.py:628:    """One-shot dedup + ON CONFLICT upsert + per-batch commit.
.\shared\data_ingestion\batching.py:816:#   3. INSERT INTO target SELECT ... FROM stg ON CONFLICT DO UPDATE
.\shared\data_ingestion\batching.py:959:          ON CONFLICT (unique_key) DO UPDATE SET ...`` when there is
.\shared\data_ingestion\batching.py:1042:            # INSERT ... SELECT ... ON CONFLICT
.\shared\data_ingestion\batching.py:1051:                    f"ON CONFLICT ({conflict_cols_sql}) DO UPDATE SET {set_clause}"
.\shared\data_ingestion\batching.py:1059:                    f"ON CONFLICT ({conflict_cols_sql}) DO NOTHING"
.\modules\reclaimrx\src\reclaimrx\ingest\csv_upload.py:365:            "Sync DB URL. Defaults to DATABASE_URL_SYNC env then "
.\modules\reclaimrx\src\reclaimrx\ingest\csv_upload.py:390:    from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\reclaimrx\src\reclaimrx\ingest\csv_upload.py:394:    db_url = args.db_url or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("RECLAIMRX_DB_URL")
.\modules\reclaimrx\src\reclaimrx\ingest\csv_upload.py:397:            "ERROR: no DB URL — pass --db-url or set DATABASE_URL_SYNC.",
.\modules\reclaimrx\src\reclaimrx\ingest\csv_upload.py:402:    eng = create_engine(db_url)
.\modules\reclaimrx\src\reclaimrx\detection\seeding.py:65:                ON CONFLICT (code) DO UPDATE SET
.\shared\config.py:79:    DATABASE_URL: str
.\shared\config.py:80:    DATABASE_URL_SYNC: str
.\shared\config.py:82:    # at the same physical database as DATABASE_URL — reference tables live
.\shared\config.py:84:    # Falls back to DATABASE_URL if not explicitly set.
.\shared\config.py:161:    return get_settings().DATABASE_URL
.\shared\config.py:173:    return settings.REFERENCE_DB_URL or settings.DATABASE_URL
.\modules\paysync\alembic\env.py:8:DATABASE_URL_SYNC must NOT contain the +asyncpg driver prefix.
.\modules\paysync\alembic\env.py:49:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\paysync\alembic\env.py:58:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix."
.\modules\pharmacy-directory\alembic\env.py:7:Uses synchronous alembic (engine_from_config + psycopg2). DATABASE_URL_SYNC
.\modules\pharmacy-directory\alembic\env.py:42:_DB_URL = _SETTINGS.DATABASE_URL_SYNC or _SETTINGS.DATABASE_URL
.\modules\pharmacy-directory\alembic\env.py:60:    DATABASE_URL_SYNC drifts to ``postgresql+asyncpg://``.
.\modules\pharmacy-directory\alembic\env.py:65:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\pharmacy-directory\alembic\env.py:67:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\shared\data_ingestion\tests\conftest.py:25:from sqlalchemy import JSON, String, create_engine, event
.\shared\data_ingestion\tests\conftest.py:32:os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
.\shared\data_ingestion\tests\conftest.py:33:os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
.\shared\data_ingestion\tests\conftest.py:104:    raw_engine = create_engine(
.\modules\reclaimrx\src\reclaimrx\detection\providers\baseline.py:11:writes go through ``INSERT ... ON CONFLICT (...) DO UPDATE`` so
.\modules\reclaimrx\src\reclaimrx\detection\providers\baseline.py:414:                ON CONFLICT
.\modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:6:`assert_awp_basis_acceptable` helper to prevent silent SWP-as-AWP
.\modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:128:def assert_awp_basis_acceptable(
.\modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:170:    "assert_awp_basis_acceptable",
.\shared\data_ingestion\ncpdp_roster.py:350:    Opens its own DB session via DATABASE_URL_SYNC env. For ops
.\shared\data_ingestion\ncpdp_roster.py:371:    url = os.environ.get("DATABASE_URL_SYNC")
.\shared\data_ingestion\ncpdp_roster.py:373:        print("ERROR: DATABASE_URL_SYNC not set", file=sys.stderr)
.\shared\data_ingestion\ncpdp_roster.py:378:    from sqlalchemy import create_engine  # noqa: PLC0415
.\shared\data_ingestion\ncpdp_roster.py:381:    engine = create_engine(url, future=True)
.\shared\data_ingestion\sources\cms_opt_out.py:253:        SQLite-path note: the shared primitive emits pg_insert + ON CONFLICT
.\modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:278:                ON CONFLICT (detector_name) DO UPDATE SET
.\modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:423:    from sqlalchemy import create_engine
.\modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:435:    db_url = os.environ.get("DATABASE_URL_SYNC", "")
.\modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:437:        raise SystemExit("DATABASE_URL_SYNC env var required")
.\modules\reclaimrx\src\reclaimrx\detection\ml\training_pipeline.py:438:    engine = create_engine(db_url.replace("+asyncpg", "+psycopg2"))
.\modules\reclaimrx\src\reclaimrx\detection\ml\registry.py:156:            ON CONFLICT (detector_name) DO NOTHING
.\shared\data_ingestion\sources\fda_ndc.py:11:    the drugs table has TWO unique constraints and ON CONFLICT can only
.\shared\data_ingestion\sources\fda_drug_shortages.py:15:  - drug_shortages: upsert (INSERT ON CONFLICT DO UPDATE).
.\shared\data_ingestion\sources\ncpdp_dataq.py:621:                    # Tables with a DB-level unique constraint need ON CONFLICT
.\modules\reclaimrx\src\events\__init__.py:35:    RECLAIMRX_DATABASE_URL don't blow up at module import time.
.\shared\data_ingestion\sources\state_medicaid_bins.py:18:Upsert logic: ON CONFLICT (bin, pcn, group_number) DO UPDATE using
.\shared\data_ingestion\sources\ofac_sdn.py:33:  - Parent (ofac_sdn): flush_upsert_batch by ent_num. ON CONFLICT DO
.\shared\data_ingestion\sources\rxnorm.py:13:SQL INSERT…SELECT…ON CONFLICT DO UPDATE (Postgres-only):
.\shared\data_ingestion\sources\rxnorm.py:426:        Cross-batch duplicates are handled by ON CONFLICT DO UPDATE.
.\shared\data_ingestion\sources\rxnorm.py:557:        ``ON CONFLICT … DO UPDATE``. On any other dialect the crosswalk build
.\shared\data_ingestion\sources\rxnorm.py:592:                    ON CONFLICT (ndc_11) DO UPDATE
.\shared\data_ingestion\sources\rxnorm.py:653:                    ON CONFLICT ON CONSTRAINT uq_rxnorm_atc_crosswalk DO UPDATE
.\shared\data_ingestion\sources\oig_leie.py:153:        (individuals). SQL ON CONFLICT treats NULL as distinct — running
.\modules\reclaimrx\src\reclaimrx\anomalies\repository.py:400:            ON CONFLICT (case_id, anomaly_id) DO NOTHING
.\modules\reclaimrx\README.md:204:The CLI reads `DATABASE_URL_SYNC` from the environment unless `--db-url`
.\modules\core-platform\tests\bank_holidays\test_seed.py:326:    assert second == 0  # ON CONFLICT DO NOTHING → no new rows
.\modules\core-platform\tests\bank_holidays\test_api.py:208:    Wave 21b: URL source swapped from settings.DATABASE_URL_SYNC to
.\modules\core-platform\tests\bank_holidays\test_api.py:212:    from sqlalchemy import create_engine
.\modules\core-platform\tests\bank_holidays\test_api.py:215:    engine = create_engine(integration_postgres["admin_url_sync"], future=True)
.\modules\core-platform\tests\bank_holidays\conftest.py:18:from sqlalchemy import create_engine
.\modules\core-platform\tests\bank_holidays\conftest.py:54:    engine = create_engine(integration_postgres["admin_url_sync"], future=True)
.\modules\ai-nlp\alembic\env.py:7:Uses synchronous alembic (engine_from_config + psycopg2). DATABASE_URL_SYNC
.\modules\ai-nlp\alembic\env.py:57:# Allow DATABASE_URL env override (for CI / Docker)
.\modules\ai-nlp\alembic\env.py:58:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\ai-nlp\alembic\env.py:68:    DATABASE_URL_SYNC drifts to ``postgresql+asyncpg://``.
.\modules\ai-nlp\alembic\env.py:73:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\ai-nlp\alembic\env.py:75:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\modules\reclaimrx\alembic\versions\0008_seed_ml_detector_placeholders.py:7:The ON CONFLICT DO NOTHING guard makes this idempotent — running
.\modules\reclaimrx\alembic\versions\0008_seed_ml_detector_placeholders.py:81:            ON CONFLICT (detector_name) DO NOTHING
.\modules\core-platform\tests\auth\sessions\test_session_service.py:15:from sqlalchemy import create_engine
.\modules\core-platform\tests\auth\sessions\test_session_service.py:40:    eng = create_engine(
.\modules\core-platform\tests\auth\conftest.py:10:from sqlalchemy import create_engine
.\modules\core-platform\tests\auth\conftest.py:28:    eng = create_engine(
.\modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:78:    # _get_composite returns None when DATABASE_URL_SYNC is unset (which
.\modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:81:    monkeypatch.delenv("DATABASE_URL_SYNC", raising=False)
.\modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:82:    monkeypatch.delenv("DATABASE_URL", raising=False)
.\modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:280:      1. DATABASE_URL{,_SYNC} unset → `pricing_enrichment_db_url_missing`
.\modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:288:    monkeypatch.delenv("DATABASE_URL_SYNC", raising=False)
.\modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:289:    monkeypatch.delenv("DATABASE_URL", raising=False)
.\modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:305:    monkeypatch.setenv("DATABASE_URL_SYNC", "")  # still falsy
.\modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:306:    monkeypatch.delenv("DATABASE_URL", raising=False)
.\modules\core-platform\tests\auth\api_keys\test_api_key_service.py:14:from sqlalchemy import create_engine
.\modules\core-platform\tests\auth\api_keys\test_api_key_service.py:36:    eng = create_engine(
.\modules\adjudication-engine\tests\unit\test_bin_routing.py:31:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\unit\test_bin_routing.py:81:    from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\adjudication-engine\tests\unit\test_bin_routing.py:83:    url = os.environ["DATABASE_URL_SYNC"]
.\modules\adjudication-engine\tests\unit\test_bin_routing.py:86:    engine = create_engine(url, future=True)
.\modules\reclaimrx\alembic\env.py:8:DATABASE_URL_SYNC must NOT contain the +asyncpg driver prefix.
.\modules\reclaimrx\alembic\env.py:53:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\reclaimrx\alembic\env.py:62:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix."
.\modules\adjudication-engine\tests\load\test_throughput.py:110:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\core-platform\alembic\versions\README.md:54:2. Forces `DATABASE_URL_SYNC=DATABASE_URL` because this module's
.\modules\core-platform\alembic\versions\README.md:56:   driver — the otherwise-sync `DATABASE_URL_SYNC` with a psycopg2
.\modules\core-platform\src\_shim\db.py:16:from sqlalchemy import create_engine
.\modules\core-platform\src\_shim\db.py:34:    _engine = create_engine(url, future=True, connect_args=connect_args)
.\modules\core-platform\src\bank_holidays\seed.py:175:    Uses ``INSERT ... ON CONFLICT DO NOTHING`` so running twice is safe.
.\modules\core-platform\src\bank_holidays\seed.py:198:                    "ON CONFLICT (holiday_date, country) DO NOTHING"
.\modules\core-platform\src\bank_holidays\seed.py:239:    from sqlalchemy import create_engine
.\modules\core-platform\src\bank_holidays\seed.py:243:    engine = create_engine(settings.DATABASE_URL_SYNC)
.\modules\adjudication-engine\tests\integration\test_tcp_listener_db_routing.py:58:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_tcp_listener.py:47:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_smoke_real_db.py:16:Requires DATABASE_URL_SYNC pointing at the dev DB (set by
.\modules\adjudication-engine\tests\integration\test_smoke_real_db.py:18:DATABASE_URL_SYNC isn't set.
.\modules\adjudication-engine\tests\integration\test_smoke_real_db.py:44:from sqlalchemy import create_engine, select  # noqa: E402
.\modules\adjudication-engine\tests\integration\test_smoke_real_db.py:59:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_smoke_real_db.py:61:        pytest.skip("DATABASE_URL_SYNC not set; smoke test needs the dev DB")
.\modules\adjudication-engine\tests\integration\test_smoke_real_db.py:63:        pytest.skip("DATABASE_URL_SYNC points at SQLite; smoke test needs Postgres")
.\modules\adjudication-engine\tests\integration\test_smoke_real_db.py:68:    """psycopg2 URL for the tenant role (whatever role DATABASE_URL_SYNC uses)."""
.\modules\adjudication-engine\tests\integration\test_smoke_real_db.py:81:    url = os.environ["DATABASE_URL_SYNC"].replace("+asyncpg", "+psycopg2")
.\modules\adjudication-engine\tests\integration\test_smoke_real_db.py:82:    engine = create_engine(url, future=True)
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:23:from sqlalchemy import create_engine, text
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:94:    engine = create_engine(db_url, future=True, connect_args=connect_args)
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:234:    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:265:        old_env = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:266:        os.environ["DATABASE_URL_SYNC"] = db_url
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:277:            os.environ.pop("DATABASE_URL_SYNC", None)
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:279:            os.environ["DATABASE_URL_SYNC"] = old_env
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:344:        old_env = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:345:        os.environ["DATABASE_URL_SYNC"] = db_url
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:357:            os.environ.pop("DATABASE_URL_SYNC", None)
.\modules\adjudication-engine\tests\integration\test_scheduler_wiring.py:359:            os.environ["DATABASE_URL_SYNC"] = old_env
.\modules\adjudication-engine\tests\integration\test_reclaimrx_rules_admin.py:41:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_reclaimrx_ml_api.py:37:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_reclaimrx_flagged_npis_api.py:40:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\core-platform\alembic\env.py:7:Uses synchronous alembic (engine_from_config + psycopg2). DATABASE_URL_SYNC
.\modules\core-platform\alembic\env.py:39:_DB_URL = _SETTINGS.DATABASE_URL_SYNC or _SETTINGS.DATABASE_URL
.\modules\core-platform\alembic\env.py:55:    DATABASE_URL_SYNC drifts to ``postgresql+asyncpg://``.
.\modules\core-platform\alembic\env.py:60:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\core-platform\alembic\env.py:62:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\modules\adjudication-engine\tests\integration\test_reclaimrx_admin.py:50:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_w27_pharmacy_tin_uei_exclusion.py:55:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_w27_pharmacy_tin_uei_exclusion.py:116:            ON CONFLICT (id) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_w27_pharmacy_tin_uei_exclusion.py:182:            ON CONFLICT DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_w27_pharmacy_tin_uei_exclusion.py:257:    from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\adjudication-engine\tests\integration\test_phase_w27_pharmacy_tin_uei_exclusion.py:270:    url = os.environ["DATABASE_URL_SYNC"]
.\modules\adjudication-engine\tests\integration\test_phase_w27_pharmacy_tin_uei_exclusion.py:271:    engine = create_engine(url, future=True)
.\modules\adjudication-engine\tests\integration\test_phase_c8_to_c11_pricing_e2e.py:62:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c8_to_c11_pricing_e2e.py:93:                ON CONFLICT (code) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c8_to_c11_pricing_e2e.py:109:            ON CONFLICT (id) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c6_pharmacy_exclusion.py:102:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c6_pharmacy_exclusion.py:118:            "ON CONFLICT (code) DO NOTHING",
.\modules\adjudication-engine\tests\integration\test_phase_c6_pharmacy_exclusion.py:125:            "ON CONFLICT (code) DO NOTHING",
.\modules\adjudication-engine\tests\integration\test_phase_c6_pharmacy_exclusion.py:149:            "ON CONFLICT (id) DO NOTHING",
.\modules\adjudication-engine\alembic\env.py:8:Uses synchronous alembic (engine_from_config + psycopg2). DATABASE_URL_SYNC
.\modules\adjudication-engine\alembic\env.py:57:# Allow DATABASE_URL env override (for CI / Docker)
.\modules\adjudication-engine\alembic\env.py:58:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\adjudication-engine\alembic\env.py:68:    DATABASE_URL_SYNC drifts to ``postgresql+asyncpg://``.
.\modules\adjudication-engine\alembic\env.py:73:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\adjudication-engine\alembic\env.py:75:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\modules\adjudication-engine\tests\integration\test_phase_c5_prescriber_exclusion.py:93:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c5_prescriber_exclusion.py:110:            "ON CONFLICT (code) DO NOTHING",
.\modules\adjudication-engine\tests\integration\test_phase_c5_prescriber_exclusion.py:117:            "ON CONFLICT (code) DO NOTHING",
.\modules\adjudication-engine\tests\integration\test_phase_c5_prescriber_exclusion.py:141:            "ON CONFLICT (id) DO NOTHING",
.\modules\ebv-ebi-rtbc\tests\conftest.py:26:from sqlalchemy import JSON, String, create_engine, event
.\modules\ebv-ebi-rtbc\tests\conftest.py:57:    engine = create_engine(
.\modules\adjudication-engine\tests\integration\test_phase_c4_bin_exclusion.py:82:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c4_bin_exclusion.py:99:            "ON CONFLICT (code) DO NOTHING",
.\modules\adjudication-engine\tests\integration\test_phase_c4_bin_exclusion.py:122:            "ON CONFLICT (id) DO NOTHING",
.\modules\adjudication-engine\tests\integration\test_paysync_invoicing_admin.py:41:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c3_flags.py:118:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c3_flags.py:141:                "ON CONFLICT (code) DO NOTHING",
.\modules\adjudication-engine\tests\integration\test_phase_c3_flags.py:167:            "ON CONFLICT (id) DO NOTHING",
.\modules\edi-compliance\README.md:77:| `DATABASE_URL` | PostgreSQL connection string |
.\modules\adjudication-engine\tests\integration\test_phase_c2_rule_config.py:51:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_paysync_close_admin.py:40:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c24_c26_final_tier_e2e.py:55:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c24_c26_final_tier_e2e.py:85:                ON CONFLICT (code) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c24_c26_final_tier_e2e.py:101:            ON CONFLICT (id) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c24_c26_final_tier_e2e.py:121:            ON CONFLICT DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c24_c26_final_tier_e2e.py:291:    from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\adjudication-engine\tests\integration\test_phase_c24_c26_final_tier_e2e.py:304:    url = os.environ["DATABASE_URL_SYNC"]
.\modules\adjudication-engine\tests\integration\test_phase_c24_c26_final_tier_e2e.py:305:    engine = create_engine(url, future=True)
.\modules\adjudication-engine\tests\integration\test_paysync_batch_admin.py:48:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_paysync_batch_admin.py:209:            ON CONFLICT (tenant_id, cardholder_id, date_of_birth) DO NOTHING
.\modules\edi-compliance\tests\conftest.py:60:from sqlalchemy import JSON, String, create_engine, event
.\modules\edi-compliance\tests\conftest.py:87:    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
.\modules\adjudication-engine\tests\integration\test_phase_c23_pa_timer_e2e.py:59:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c23_pa_timer_e2e.py:81:            ON CONFLICT (code) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c23_pa_timer_e2e.py:97:            ON CONFLICT (id) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c23_pa_timer_e2e.py:182:    from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\adjudication-engine\tests\integration\test_phase_c23_pa_timer_e2e.py:195:    url = os.environ["DATABASE_URL_SYNC"]
.\modules\adjudication-engine\tests\integration\test_phase_c23_pa_timer_e2e.py:196:    engine = create_engine(url, future=True)
.\modules\adjudication-engine\tests\integration\test_phase_c23_pa_timer_e2e.py:263:    from sqlalchemy import create_engine
.\modules\adjudication-engine\tests\integration\test_phase_c23_pa_timer_e2e.py:267:    engine = create_engine(_resolve_admin_url())
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:55:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:90:                ON CONFLICT (code) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:106:            ON CONFLICT (id) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:120:    global (no RLS), so these persist across tests — use ON CONFLICT
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:142:                ON CONFLICT (ncpdp_provider_id) DO UPDATE SET
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:164:            ON CONFLICT (tenant_id, program_id, name) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:179:                ON CONFLICT DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:192:            ON CONFLICT DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:462:    from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:475:    url = os.environ["DATABASE_URL_SYNC"]
.\modules\adjudication-engine\tests\integration\test_phase_c18_c22_tier2_e2e.py:476:    engine = create_engine(url, future=True)
.\modules\adjudication-engine\tests\integration\test_network_mgmt_admin.py:40:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\core-platform\src\auth\seed\system_roles.py:258:    from sqlalchemy import create_engine
.\modules\core-platform\src\auth\seed\system_roles.py:263:    url = os.environ.get("DATABASE_URL", "sqlite:///./seed.sqlite")
.\modules\core-platform\src\auth\seed\system_roles.py:264:    engine = create_engine(url, future=True)
.\modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:53:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:87:                ON CONFLICT (code) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:103:            ON CONFLICT (id) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:260:    Idempotent — INSERT ON CONFLICT DO NOTHING. Returns the
.\modules\adjudication-engine\tests\integration\test_phase_c12_c17_tier1_e2e.py:277:            ON CONFLICT (tenant_id, cardholder_id, date_of_birth)
.\modules\adjudication-engine\tests\integration\test_maxacc_registry_admin.py:47:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:51:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:75:                ON CONFLICT (code) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:91:            ON CONFLICT (id) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:375:    from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:387:    url = os.environ["DATABASE_URL_SYNC"]
.\modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:388:    engine = create_engine(url, future=True)
.\modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:506:    from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:517:    url = os.environ["DATABASE_URL_SYNC"]
.\modules\adjudication-engine\tests\integration\test_phase_c12_accumulator_writes.py:518:    engine = create_engine(url, future=True)
.\modules\adjudication-engine\tests\integration\test_phase_b_bus_and_billing.py:53:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_phase_b_bus_and_billing.py:55:        pytest.skip("DATABASE_URL_SYNC needs to point at the dev Postgres")
.\modules\adjudication-engine\tests\integration\test_phase_b_bus_and_billing.py:63:    sync_url = os.environ["DATABASE_URL_SYNC"]
.\modules\adjudication-engine\tests\integration\test_phase_b_bus_and_billing.py:65:        "BILLING_DATABASE_URL",
.\modules\adjudication-engine\tests\integration\test_listener_failure_modes.py:65:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_persistence.py:45:from sqlalchemy import create_engine, text  # noqa: E402
.\modules\adjudication-engine\tests\integration\test_persistence.py:64:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_persistence.py:66:        pytest.skip("DATABASE_URL_SYNC needs to point at the dev Postgres")
.\modules\adjudication-engine\tests\integration\test_persistence.py:73:    engine = create_engine(url, future=True)
.\modules\adjudication-engine\tests\integration\test_config_admin_endpoints.py:47:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_config_admin_endpoints.py:67:            ON CONFLICT (id) DO NOTHING
.\modules\adjudication-engine\tests\integration\test_config_admin_endpoints.py:139:    from sqlalchemy import create_engine
.\modules\adjudication-engine\tests\integration\test_config_admin_endpoints.py:143:    engine = create_engine(_resolve_admin_url())
.\modules\adjudication-engine\tests\integration\test_claim_spine_phase_a2_e2e.py:59:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\tests\integration\test_claim_spine_phase_a2_e2e.py:61:        pytest.skip("DATABASE_URL_SYNC needs to point at the dev Postgres")
.\modules\adjudication-engine\tests\integration\test_claim_spine_phase_a2_e2e.py:67:    # Import inside fixture so DATABASE_URL_SYNC is already set on first touch.
.\modules\adjudication-engine\tests\integration\test_claim_spine_phase_a2_e2e.py:74:    # test's DATABASE_URL_SYNC.
.\modules\core-platform\scripts\bootstrap_admin.py:12:    DATABASE_URL=postgresql://... \
.\modules\core-platform\scripts\bootstrap_admin.py:67:from sqlalchemy import create_engine, func, select  # noqa: E402
.\modules\core-platform\scripts\bootstrap_admin.py:211:    engine = create_engine(database_url, future=True, connect_args=connect_args)
.\modules\core-platform\scripts\bootstrap_admin.py:292:        help="SQLAlchemy database URL. Falls back to $DATABASE_URL.",
.\modules\core-platform\scripts\bootstrap_admin.py:300:    database_url = args.database_url or os.environ.get("DATABASE_URL")
.\modules\core-platform\scripts\bootstrap_admin.py:303:            "error: DATABASE_URL env var or --database-url flag is required",
.\modules\adjudication-engine\src\services\tcp_listener.py:52:from sqlalchemy import create_engine
.\modules\adjudication-engine\src\services\tcp_listener.py:210:    tests can swap DATABASE_URL_SYNC before spawning.
.\modules\adjudication-engine\src\services\tcp_listener.py:270:        url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\services\tcp_listener.py:273:                "DATABASE_URL_SYNC not set; TCP listener needs a sync DB URL"
.\modules\adjudication-engine\src\services\tcp_listener.py:277:        engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\services\tcp_listener (conflicted).py:52:from sqlalchemy import create_engine
.\modules\adjudication-engine\src\services\tcp_listener (conflicted).py:213:    tests can swap DATABASE_URL_SYNC before spawning.
.\modules\adjudication-engine\src\services\tcp_listener (conflicted).py:273:        url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\services\tcp_listener (conflicted).py:276:                "DATABASE_URL_SYNC not set; TCP listener needs a sync DB URL"
.\modules\adjudication-engine\src\services\tcp_listener (conflicted).py:280:        engine = create_engine(url, future=True)
.\modules\payment-processing\src\_shim\db.py:14:from sqlalchemy import create_engine
.\modules\payment-processing\src\_shim\db.py:33:        _engine = create_engine(
.\modules\payment-processing\src\_shim\db.py:41:        _engine = create_engine(url, future=True, connect_args=connect_args)
.\modules\adjudication-engine\src\services\pricing_enrichment.py:21:     fresh-session factories backed by DATABASE_URL_SYNC.
.\modules\adjudication-engine\src\services\pricing_enrichment.py:109:        from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\adjudication-engine\src\services\pricing_enrichment.py:122:        db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get(
.\modules\adjudication-engine\src\services\pricing_enrichment.py:123:            "DATABASE_URL", ""
.\modules\adjudication-engine\src\services\pricing_enrichment.py:133:        engine = create_engine(db_url, pool_pre_ping=True)
.\modules\adjudication-engine\src\scheduler.py:147:        db_factory: Sync sessionmaker (built from DATABASE_URL_SYNC in
.\modules\adjudication-engine\src\main.py:58:    from sqlalchemy import create_engine  # noqa: PLC0415
.\modules\adjudication-engine\src\main.py:75:    url = os.environ.get("DATABASE_URL_SYNC", "sqlite:///./scheduler_test.db")
.\modules\adjudication-engine\src\main.py:78:    sync_engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\api\admin_routes.py:38:from sqlalchemy import create_engine
.\modules\adjudication-engine\src\api\admin_routes.py:144:    Uses DATABASE_URL_SYNC directly — admin endpoint needs sync
.\modules\adjudication-engine\src\api\admin_routes.py:151:        url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\api\admin_routes.py:154:                "DATABASE_URL_SYNC not set; /admin/inject-claim needs a sync DB URL"
.\modules\adjudication-engine\src\api\admin_routes.py:158:        engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\api\admin_routes.py:167:    """Clear the cached factory so tests can swap DATABASE_URL_SYNC."""
.\modules\network-management\alembic\env.py:42:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\network-management\alembic\env.py:50:            "This module uses sync alembic. DATABASE_URL_SYNC contains '+asyncpg'."
.\modules\network-management\README.md:150:DATABASE_URL_SYNC=postgresql://ifx_dev_admin:dev_admin_password@localhost:5432/infinityrx_dev \
.\modules\payment-processing\alembic\env.py:46:# Allow DATABASE_URL env override (for CI / Docker)
.\modules\payment-processing\alembic\env.py:47:_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
.\modules\payment-processing\alembic\env.py:57:    DATABASE_URL_SYNC drifts to ``postgresql+asyncpg://``.
.\modules\payment-processing\alembic\env.py:62:            "DATABASE_URL_SYNC contains '+asyncpg' driver prefix, "
.\modules\payment-processing\alembic\env.py:64:            "Either remove +asyncpg from DATABASE_URL_SYNC, or "
.\modules\adjudication-engine\src\api\config_routes.py:33:from sqlalchemy import create_engine
.\modules\adjudication-engine\src\api\config_routes.py:138:        url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\api\config_routes.py:141:                "DATABASE_URL_SYNC not set; config admin endpoints need "
.\modules\adjudication-engine\src\api\config_routes.py:146:        engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\api\maxacc_registry_routes.py:36:from sqlalchemy import create_engine, text
.\modules\adjudication-engine\src\api\maxacc_registry_routes.py:72:      1. ADMIN_DATABASE_URL — full URL override
.\modules\adjudication-engine\src\api\maxacc_registry_routes.py:73:      2. swap ``ifx_*_app`` for ``ifx_*_admin`` in DATABASE_URL_SYNC
.\modules\adjudication-engine\src\api\maxacc_registry_routes.py:77:    override = os.environ.get("ADMIN_DATABASE_URL")
.\modules\adjudication-engine\src\api\maxacc_registry_routes.py:81:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\api\maxacc_registry_routes.py:84:            "DATABASE_URL_SYNC not set; maxacc-registry admin endpoints "
.\modules\adjudication-engine\src\api\maxacc_registry_routes.py:112:        engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:36:from sqlalchemy import create_engine, text
.\modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:71:      1. ADMIN_DATABASE_URL — full URL override
.\modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:72:      2. swap ``ifx_*_app`` for ``ifx_*_admin`` in DATABASE_URL_SYNC
.\modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:76:    override = os.environ.get("ADMIN_DATABASE_URL")
.\modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:80:    url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:83:            "DATABASE_URL_SYNC not set; maxacc-registry admin endpoints "
.\modules\adjudication-engine\src\api\maxacc_registry_routes (conflicted).py:111:        engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\api\paysync_batch_routes.py:22:from sqlalchemy import create_engine, text
.\modules\adjudication-engine\src\api\paysync_batch_routes.py:44:        url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\api\paysync_batch_routes.py:47:                "DATABASE_URL_SYNC not set; paysync batch endpoints "
.\modules\adjudication-engine\src\api\paysync_batch_routes.py:52:        engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\api\paysync_invoicing_routes.py:20:from sqlalchemy import create_engine, text
.\modules\adjudication-engine\src\api\paysync_invoicing_routes.py:42:        url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\api\paysync_invoicing_routes.py:45:                "DATABASE_URL_SYNC not set; paysync invoicing endpoints "
.\modules\adjudication-engine\src\api\paysync_invoicing_routes.py:50:        engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\api\paysync_close_routes.py:21:from sqlalchemy import create_engine, text
.\modules\adjudication-engine\src\api\paysync_close_routes.py:43:        url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\api\paysync_close_routes.py:45:            raise RuntimeError("DATABASE_URL_SYNC not set")
.\modules\adjudication-engine\src\api\paysync_close_routes.py:48:        engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\api\network_mgmt_routes.py:26:from sqlalchemy import create_engine, text
.\modules\adjudication-engine\src\api\network_mgmt_routes.py:53:        url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\api\network_mgmt_routes.py:56:                "DATABASE_URL_SYNC not set; network admin endpoints "
.\modules\adjudication-engine\src\api\network_mgmt_routes.py:61:        engine = create_engine(url, future=True)
.\modules\adjudication-engine\src\api\reclaimrx_routes.py:50:from sqlalchemy import create_engine, text
.\modules\adjudication-engine\src\api\reclaimrx_routes.py:82:        url = os.environ.get("DATABASE_URL_SYNC")
.\modules\adjudication-engine\src\api\reclaimrx_routes.py:85:                "DATABASE_URL_SYNC not set; reclaimrx admin endpoints "
.\modules\adjudication-engine\src\api\reclaimrx_routes.py:90:        engine = create_engine(url, future=True)
.\modules\network-management\tests\integration\test_tenant_ach_origination.py:11:from sqlalchemy import create_engine, text
.\modules\network-management\tests\integration\test_tenant_ach_origination.py:159:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\network-management\tests\integration\test_resolver.py:12:from sqlalchemy import create_engine, text
.\modules\network-management\tests\integration\test_resolver.py:68:    eng = create_engine(ADMIN_URL.replace("postgresql://", "postgresql+psycopg2://", 1))
.\modules\network-management\src\network_mgmt\services\resolver.py:329:            ON CONFLICT (tenant_id, entity_type, external_id) DO NOTHING
.\modules\network-management\src\network_mgmt\services\upserts.py:54:            ON CONFLICT (tenant_id, entity_type, external_id) DO UPDATE

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'modules\\drug-database\\drug_database\\services\\fdb_adapter.py'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'modules\\drug-database\\drug_database\\services\\fdb_pricing_ingester.py'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'modules\\drug-database\\drug_database\\models\\fdb_pricing_tables.py'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "assert_awp_basis_acceptable|awp_basis|fdb_ndc_price_history|fdb_price_type_desc|FDBPricingLookup|pricing_enrichment" modules -S' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 422ms:
"""FDB pricing ingester â€” loads NDDF Plus DB.zip + weekly UPD.zip drops.

Phase 09 / Unit 09.7 deliverable. Implements `FDBPricingIngester` per
SPEC Â§3.7.6 / Â§3.7.7 / Â§4 (codex GO at 9aa576b).

Three operating modes (SPEC Â§4.7):

  fdb_initial â€” one-time DB.zip baseline. ~15.6M RNP3 rows. Treats
                every row as transaction_code='A' per Â§4.4.
  fdb_weekly  â€” routine UPD.zip application. ~10k-100k rows typical.
                Strips A/C/D prefix from each row (parse_table).
  fdb_rebase  â€” operator-triggered re-baseline. Re-runs initial on the
                most recent DB.zip. Append-only schema + composite UC
                make this idempotent (duplicates collide on
                uq_fdb_ndc_price_history).

Idempotency:
  Composite UNIQUE on (ndc_11, price_type, effective_date, as_of_date,
  transaction_code, drop_sequence) IS the idempotency mechanism. A
  re-run of the same drop produces 0 net new rows â€” ON CONFLICT DO
  NOTHING skips duplicates atomically; `duplicate_skipped` is computed
  as len(batch) - rowcount.

A/C/D semantics (SPEC Â§4.4):
  All rows are INSERTed (append-only history). transaction_code is
  preserved on the row so `lookup_at_dos` can apply the Â§4.4
  partition-then-pick-latest pattern. D rows do NOT trigger DELETE â€”
  they are stored as marker rows whose presence retroactively masks
  the matching (ndc_11, price_type, effective_date) partition at
  query time.

Phase 8 scope:
  * Loads RPRDPTD0_PRICE_TYPE_DESC (modern, 20 rows) into
    fdb_price_type_desc.
  * Loads RNPTYPD0_NDC_PRICE_TYPE_DESC (legacy, 21 rows) per SPEC
    Â§3.5 line 233. Codes already in RPRDPTD0 are skipped (PK
    collision); legacy-only codes (e.g. '11' FFPUL frozen 2017-03-30)
    get a synthetic price_type_id (9000-base counter) + is_active=False
    so adjudication queries can filter them. Phase 09.9 codex fix I5.
  * Loads RNP3_NDC_PRICE (15.6M, big) into fdb_ndc_price_history.
  * SKIPS RPRDPP0_PRODUCT_PRICE â€” Phase 8.5 / Phase C territory
    (config flag `fdb_load_product_prices=False` is the default).

Discipline:
  * financial-precision.md â€” Decimal-only money path; coercer is
    Decimal in the TableSpec (09.3).
  * LESSON-005 â€” log keys prefixed `ingest_*`.
  * Surgical â€” does NOT integrate `shared.ingestion_runs` here. The
    `ingestion_run_id` column on fdb_ndc_price_history is left NULL
    when not provided. Wire-up is a 09.8 / future concern.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from drug_database.models.fdb_pricing_tables import FDBNDCPriceHistory, FDBPriceTypeDesc
from drug_database.services.fdb_adapter import (
    RNP3_NDC_PRICE,
    RNP3_NDC_PRICE_UPD,
    RNPTYPD0_NDC_PRICE_TYPE_DESC,
    RPRDPTD0_PRICE_TYPE_DESC,
    FDBAdapter,
    FDBDrop,
)

_log = logging.getLogger(__name__)


FDBIngestionMode = Literal["fdb_initial", "fdb_weekly", "fdb_rebase"]


@dataclass(frozen=True)
class FDBIngestionResult:
    """Per-mode summary returned by FDBPricingIngester.run().

    Counts intentionally split by table + by transaction_code. Replay-
    idempotent runs report `rows_duplicate_skipped > 0` and
    `rows_inserted == 0`.
    """

    mode: FDBIngestionMode
    drop_date: str                # ISO date of the resolved drop
    price_type_desc_inserted: int
    rnp3_inserted: int
    rnp3_duplicate_skipped: int
    rnp3_invalid_skipped: int
    dry_run: bool


# A factory returns a fresh row id for each insert. Required because
# SQLite's reflected BigInteger PK doesn't autoincrement; production
# Postgres uses SERIAL semantics so a None id is fine. The factory
# defaults to None (Postgres path); SQLite tests pass a counter.
RowIdFactory = Callable[[], int | None]


class FDBPricingIngester:
    """Drives the FDB drop â†’ DB load orchestration."""

    # Batch size â€” kept modest to bound memory and surface failures
    # close to the offending row. Production target ~5,000.
    BATCH_SIZE = 5000

    def __init__(
        self,
        adapter: FDBAdapter,
        session: Session,
        *,
        ingestion_run_id: str | None = None,
        row_id_factory: RowIdFactory = lambda: None,
    ) -> None:
        self._adapter = adapter
        self._session = session
        self._ingestion_run_id = ingestion_run_id
        self._row_id_factory = row_id_factory

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        mode: FDBIngestionMode,
        dry_run: bool = False,
    ) -> FDBIngestionResult:
        """Execute the ingestion for the given mode.

        Order (mirrors NPPES core+satellite pattern):
          1. Discover the drop (resolves Current/ pointer).
          2. Load reference tables (price_type_desc).
          3. Load RNP3 (NDC-keyed price history).

        Failures in step 3 do NOT roll back step 2 â€” the reference data
        is consistent on its own. If step 2 fails the run aborts before
        touching RNP3.
        """
        drop = self._adapter.discover_latest_drop()
        _log.info(
            "fdb_ingest_start",
            extra={
                "ingest_mode": mode,
                "ingest_drop_date": drop.drop_date.isoformat(),
                "ingest_dry_run": dry_run,
            },
        )

        ptd_inserted = self._load_price_type_desc(drop, dry_run=dry_run)

        rnp3_inserted, rnp3_dup, rnp3_invalid = self._load_rnp3(
            drop, mode=mode, dry_run=dry_run,
        )

        result = FDBIngestionResult(
            mode=mode,
            drop_date=drop.drop_date.isoformat(),
            price_type_desc_inserted=ptd_inserted,
            rnp3_inserted=rnp3_inserted,
            rnp3_duplicate_skipped=rnp3_dup,
            rnp3_invalid_skipped=rnp3_invalid,
            dry_run=dry_run,
        )
        _log.info(
            "fdb_ingest_complete",
            extra={
                "ingest_mode": mode,
                "ingest_price_type_desc_inserted": ptd_inserted,
                "ingest_rnp3_inserted": rnp3_inserted,
                "ingest_rnp3_duplicate_skipped": rnp3_dup,
                "ingest_rnp3_invalid_skipped": rnp3_invalid,
            },
        )
        return result

    # ------------------------------------------------------------------
    # price_type_desc â€” RPRDPTD0 (modern catalog)
    # ------------------------------------------------------------------

    # Phase 09.9 codex P9 fix I5 â€” legacy-only codes (e.g. RNPTYPD0
    # '11' FFPUL) get synthetic price_type_ids starting here. Modern
    # RPRDPTD0 ids are <100 in practice (the largest verified is 29);
    # 9000+ is comfortably out-of-range so the synthetic IDs cannot
    # collide.
    _LEGACY_SYNTHETIC_ID_BASE = 9000

    def _load_price_type_desc(self, drop: FDBDrop, *, dry_run: bool) -> int:
        """Load RPRDPTD0 + RNPTYPD0 into fdb_price_type_desc per SPEC Â§3.5.

        Order:
          1. RPRDPTD0 (modern, 20 rows). PK = price_type_id; existing
             rows skipped on PK collision; new rows inserted with
             is_active=True.
          2. RNPTYPD0 (legacy, 21 rows). For each row whose `npt_type`
             is NOT already covered by an RPRDPTD0 row, INSERT with a
             synthetic price_type_id (9000-base counter) and
             is_active=False â€” the row is preserved so adjudication
             queries joining `price_type='11'` (FFPUL) can resolve a
             description, even though the code is frozen 2017-03-30.

        Phase 09.9 codex P9 fix I5 closes the SPEC Â§3.5 line 233 gap:
        "the Phase 8 ingester must load RNPTYPD0 IN ADDITION TO
        RPRDPTD0 so all RNP3 codes have a description join."
        """
        # --- step 1 â€” modern catalog (RPRDPTD0) ----------------------
        # Track every npt_type encountered in RPRDPTD0 (existing rows
        # included) so step 2 can identify legacy-only codes regardless
        # of dry_run / replay state.
        covered_npt: set[str] = {
            r.npt_type
            for r in self._session.query(FDBPriceTypeDesc).all()
            if r.npt_type is not None
        }
        inserted = 0
        for row in self._adapter.parse_table(drop, RPRDPTD0_PRICE_TYPE_DESC, source="DB"):
            existing = self._session.get(FDBPriceTypeDesc, row["price_type_id"])
            if existing is not None:
                if existing.npt_type:
                    covered_npt.add(existing.npt_type)
                continue
            if row.get("npt_type"):
                covered_npt.add(row["npt_type"])
            obj = FDBPriceTypeDesc(
                price_type_id=row["price_type_id"],
                short_desc=row["short_desc"],
                long_desc=row.get("long_desc"),
                npt_type=row.get("npt_type"),
                price_type_definition=row.get("price_type_definition"),
                is_active=True,
                created_at=datetime.now(UTC),
            )
            if dry_run:
                inserted += 1
                continue
            self._session.add(obj)
            inserted += 1

        if not dry_run and inserted > 0:
            self._session.commit()

        # --- step 2 â€” legacy catalog (RNPTYPD0) ----------------------
        # `covered_npt` was built during step 1 (DB-existing + this-run
        # RPRDPTD0 rows). Step 2 inserts only legacy-only npt_types not
        # already covered.
        next_synthetic = self._next_synthetic_id()
        for row in self._adapter.parse_table(
            drop, RNPTYPD0_NDC_PRICE_TYPE_DESC, source="DB",
        ):
            npt = row["npt_type"]
            if npt in covered_npt:
                continue
            obj = FDBPriceTypeDesc(
                price_type_id=next_synthetic,
                short_desc=row["short_desc"],
                long_desc=None,
                npt_type=npt,
                price_type_definition=None,
                is_active=False,  # legacy-only â€” adjudication filters out
                created_at=datetime.now(UTC),
            )
            if dry_run:
                inserted += 1
                next_synthetic += 1
                continue
            self._session.add(obj)
            inserted += 1
            covered_npt.add(npt)
            next_synthetic += 1

        if not dry_run and inserted > 0:
            self._session.commit()

        return inserted

    def _next_synthetic_id(self) -> int:
        """Pick the next free synthetic price_type_id starting at the base.

        Idempotency: if RNPTYPD0 has already been ingested in a prior
        run, existing synthetic IDs are >= base; this returns base +
        count_of_existing_synthetic. Re-runs land at the same id for
        the same row (npt_type lookup), so PK collisions don't happen.
        """
        max_id = (
            self._session.query(FDBPriceTypeDesc.price_type_id)
            .filter(FDBPriceTypeDesc.price_type_id >= self._LEGACY_SYNTHETIC_ID_BASE)
            .order_by(FDBPriceTypeDesc.price_type_id.desc())
            .first()
        )
        return (max_id[0] + 1) if max_id else self._LEGACY_SYNTHETIC_ID_BASE

    # ------------------------------------------------------------------
    # RNP3 â€” NDC-keyed price history (the big table)
    # ------------------------------------------------------------------

    def _load_rnp3(
        self,
        drop: FDBDrop,
        *,
        mode: FDBIngestionMode,
        dry_run: bool,
    ) -> tuple[int, int, int]:
        """Load RNP3_NDC_PRICE rows into fdb_ndc_price_history.

        Returns (inserted, duplicate_skipped, invalid_skipped).
        """
        # source-zip selection per mode:
        # - fdb_initial / fdb_rebase â†’ DB.zip (full snapshot, all rows treated 'A')
        # - fdb_weekly              â†’ UPD.zip (delta with A/C/D prefixes)
        if mode == "fdb_weekly":
            spec = RNP3_NDC_PRICE_UPD
            source = "UPD"
        else:
            spec = RNP3_NDC_PRICE
            source = "DB"

        # Build a price_type â†’ price_type_id map once; denormalize at
        # ingest time per migration comment (line 76-79 of 0008).
        price_type_id_map = self._load_price_type_id_map()

        inserted = 0
        duplicate = 0
        invalid = 0
        batch: list[FDBNDCPriceHistory] = []

        for raw in self._adapter.parse_table(drop, spec, source=source):
            obj = FDBNDCPriceHistory(
                id=self._row_id_factory(),
                ndc_11=raw["ndc"],
                price_type=raw["price_type"],
                price_type_id=price_type_id_map.get(raw["price_type"]),
                effective_date=raw["effective_date_raw"],
                price=raw["price_raw"],
                as_of_date=raw["as_of_date"],
                transaction_code=raw["transaction_code"],
                drop_sequence=raw["drop_sequence"],
                ingestion_run_id=self._ingestion_run_id,
                created_at=datetime.now(UTC),
            )
            batch.append(obj)
            if len(batch) >= self.BATCH_SIZE:
                ins, dup, inv = self._flush_rnp3_batch(batch, dry_run=dry_run)
                inserted += ins
                duplicate += dup
                invalid += inv
                batch = []

        if batch:
            ins, dup, inv = self._flush_rnp3_batch(batch, dry_run=dry_run)
            inserted += ins
            duplicate += dup
            invalid += inv

        return inserted, duplicate, invalid

    # Composite UC columns â€” used as the conflict target on SQLite, which
    # does not support named-constraint conflict targets in SQLAlchemy's
    # dialect. Postgres uses the constraint name directly.
    _UC_COLUMNS = (
        "ndc_11",
        "price_type",
        "effective_date",
        "as_of_date",
        "transaction_code",
        "drop_sequence",
    )

    def _flush_rnp3_batch(
        self,
        batch: list[FDBNDCPriceHistory],
        *,
        dry_run: bool,
    ) -> tuple[int, int, int]:
        """Flush one batch using ON CONFLICT DO NOTHING â€” one commit per batch.

        Dialect dispatch:
          Postgres â€” pg_insert().on_conflict_do_nothing(constraint=
                     "uq_fdb_ndc_price_history"). One round-trip; skipped
                     duplicates are not counted by the DB engine and are
                     computed as len(batch) - rowcount.
          SQLite   â€” sqlite_insert().on_conflict_do_nothing(index_elements=
                     _UC_COLUMNS). Same semantics; SQLAlchemy's SQLite
                     dialect does not accept named constraints as conflict
                     targets, so the column list is used instead.

        Performance: re-baseline path (15.6M rows Ã— 5,000-batch) drops from
        5,000 round-trips per batch to 1, with duplicate-skip happening
        atomically inside the single INSERT.
        """
        if dry_run:
            return len(batch), 0, 0

        # Wave B7 â€” dialect-aware id handling:
        #   Postgres: omit `id` so the nextval() server default fires.
        #            Including {"id": None} explicitly overrides the
        #            default and trips the NOT NULL bigserial constraint.
        #   SQLite (test): include `id` (even as None) so the INTEGER-
        #            PRIMARY-KEY auto-assign fires on INSERT-NULL.
        # The two dialects have opposite behavior for explicit NULL on a
        # PK with autoincrement, hence the dialect-conditional below.
        dialect = self._session.get_bind().dialect.name

        def _row_for(obj: FDBNDCPriceHistory) -> dict[str, object]:
            data: dict[str, object] = {
                "ndc_11": obj.ndc_11,
                "price_type": obj.price_type,
                "price_type_id": obj.price_type_id,
                "effective_date": obj.effective_date,
                "price": obj.price,
                "as_of_date": obj.as_of_date,
                "transaction_code": obj.transaction_code,
                "drop_sequence": obj.drop_sequence,
                "ingestion_run_id": obj.ingestion_run_id,
                "created_at": obj.created_at,
            }
            if dialect != "postgresql":
                data["id"] = obj.id
            return data

        rows = [_row_for(obj) for obj in batch]
        if dialect == "postgresql":
            stmt = (
                pg_insert(FDBNDCPriceHistory)
                .values(rows)
                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
            )
        else:
            # SQLite (test environment) â€” column-list conflict target.
            stmt = (
                sqlite_insert(FDBNDCPriceHistory)
                .values(rows)
                .on_conflict_do_nothing(index_elements=list(self._UC_COLUMNS))
            )

        result = self._session.execute(stmt)
        self._session.commit()

        inserted = result.rowcount if result.rowcount >= 0 else len(batch)
        duplicate = len(batch) - inserted
        return inserted, duplicate, 0

    def _load_price_type_id_map(self) -> dict[str, int]:
        """Build npt_type â†’ price_type_id map from already-loaded RPRDPTD0.

        Used to denormalize `price_type_id` on each fdb_ndc_price_history
        row at ingest time (per migration column comment). Legacy codes
        not in RPRDPTD0 (e.g. '11' FFPUL) get None â€” Tier 4 cascade
        handles the missing join downstream.
        """
        mapping: dict[str, int] = {}
        rows = self._session.query(FDBPriceTypeDesc).all()
        for row in rows:
            if row.npt_type:
                mapping[row.npt_type] = row.price_type_id
        return mapping


__all__ = [
    "FDBIngestionMode",
    "FDBIngestionResult",
    "FDBPricingIngester",
    "RowIdFactory",
]

 succeeded in 422ms:
"""FDB pricing ORM models â€” mirror of alembic migration 0008_fdb_pricing.

Schema: ``drug_database`` (same as NDC + NADAC tables).

Tables (Phase 8 SPEC Â§3.6.1 / Â§3.6.2; locked by 4-pass codex review of
data/reference/fdb/README.md, codex GO at commit 9aa576b):

  drug_database.fdb_ndc_price_history  â€” append-only NDC-keyed FDB price
                                         history (mirror of RNP3_NDC_PRICE).
  drug_database.fdb_price_type_desc    â€” unified price-type catalog
                                         (modern RPRDPTD0 + legacy RNPTYPD0).

Data rules (non-negotiable):
  - ``price`` column: ``sa.Numeric(16, 5)`` per RNP3 ANSI DDL â€” NOT (18, 6).
    Distinct from NADAC tables which use Numeric(18, 6). Python Decimal +
    ROUND_HALF_UP. No float, no Float, no REAL anywhere â€” financial-precision.md.
  - Global reference data â€” no TenantScopedMixin (LESSON-011).
  - Column inventory mirrors `alembic/versions/0008_fdb_pricing.py` byte-for-byte
    so alembic autogenerate produces no diff against this Base.

LESSON-001: tests using this Base MUST use SAVEPOINT-isolated sessions when
the code under test calls ``db.commit()``. See ``test_fdb_pricing_models.py``
for the canonical fixture pattern.

Composite uniqueness on (ndc_11, price_type, effective_date, as_of_date,
transaction_code, drop_sequence) â€” supports replay of same-drop A+D
collisions per Â§4.4 / codex MF1 fix.

Index ``ix_fdb_ndc_price_lookup`` lead columns (ndc_11, price_type,
effective_date) define the Â§4.4 partition; trailing ``as_of_date DESC,
drop_sequence DESC, id DESC`` resolve the latest row within each partition.
Postgres satisfies DISTINCT ON + WHERE + ORDER from this index alone (true
DESC indexes have existed since Postgres 8.3).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "drug_database"


class FDBPricingBase(DeclarativeBase):
    """Declarative base for FDB pricing tables (Phase 8 SPEC Â§3.6).

    Kept separate from ``PricingBase`` (NADAC/ASP) and ``NDCBase`` (NDC core)
    so each Base can be wired into alembic env.py autogenerate independently
    and so tests can create_all() the FDB tables without dragging in
    unrelated ones.
    """


class FDBNDCPriceHistory(FDBPricingBase):
    """Append-only FDB NDC price history (mirror of RNP3_NDC_PRICE).

    One row per (NDC, price_type, effective_date, as_of_date, transaction_code,
    drop_sequence). Ingest writes A/C/D rows; ``lookup_at_dos`` resolves the
    latest visible row per partition via ``ix_fdb_ndc_price_lookup``.

    All money columns: Numeric(16, 5), Python Decimal, ROUND_HALF_UP.
    Global reference data â€” no TenantScopedMixin (LESSON-011).
    """

    __tablename__ = "fdb_ndc_price_history"
    __table_args__ = (
        # Composite uniqueness â€” mirrors `uq_fdb_ndc_price_history` in the
        # 0008 migration. (ndc_11, price_type, effective_date) alone is NOT
        # unique because UPD can ship multiple as_of_date snapshots for the
        # same effective_date, and same-drop A+D collisions resolve via
        # drop_sequence (Â§4.4).
        UniqueConstraint(
            "ndc_11",
            "price_type",
            "effective_date",
            "as_of_date",
            "transaction_code",
            "drop_sequence",
            name="uq_fdb_ndc_price_history",
        ),
        # Primary lookup index â€” covers Â§4.4 partition-then-pick-latest.
        # Trailing DESC columns let DISTINCT ON + ORDER BY satisfy from the
        # index alone on Postgres.
        Index(
            "ix_fdb_ndc_price_lookup",
            "ndc_11",
            "price_type",
            "effective_date",
            text("as_of_date DESC"),
            text("drop_sequence DESC"),
            text("id DESC"),
        ),
        Index("ix_fdb_ndc_price_effective_date", "effective_date"),
        Index("ix_fdb_ndc_price_as_of_date", "as_of_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Surrogate PK; supports DESC tiebreak in ix_fdb_ndc_price_lookup",
    )
    ndc_11: Mapped[str] = mapped_column(
        String(11),
        nullable=False,
        comment="11-digit normalized NDC (5-4-2); matches NADAC pattern",
    )
    price_type: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        comment=(
            "Legacy 2-char NPT_TYPE (e.g. '07'=SWP, '09'=WHN/WAC). "
            "Joins to fdb_price_type_desc.npt_type. See SPEC Â§3.5 "
            "for verified codes."
        ),
    )
    price_type_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Modern numeric PRICE_TYPE_ID denormalized at ingest from "
            "fdb_price_type_desc lookup. NULL only for legacy code "
            "'11' (FFPUL â€” frozen 2017-03-30, see SPEC Â§3.5)."
        ),
    )
    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="FDB-published effective date for this price",
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(16, 5),
        nullable=False,
        comment="Per RNP3 ANSI DDL NUMERIC(16,5). Decimal/ROUND_HALF_UP. Never float.",
    )
    as_of_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment=(
            "FDB drop date this row was loaded from "
            "(e.g. 2026-05-06 for the 06MAY2026 delivery)"
        ),
    )
    transaction_code: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        comment=(
            "FDB UPD transaction code: 'A'=Add, 'C'=Change, 'D'=Delete. "
            "Full DB.zip rows are loaded as 'A'. See SPEC Â§4 + Â§4.4."
        ),
    )
    drop_sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment=(
            "Line number within the source UPD/DB.zip file (0-indexed). "
            "Required for stable ordering of same-as_of_date D+A pairs "
            "(NDC re-use scenarios per PDF p.352, codex MF1 fix)."
        ),
    )
    ingestion_run_id: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        comment="shared.ingestion_runs FK; NULL for backfill imports",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment=(
            "Postgres-side default. SQLite has no NOW(); test fixtures "
            "must supply created_at explicitly."
        ),
    )


class FDBPriceTypeDesc(FDBPricingBase):
    """Unified FDB price-type catalog (modern RPRDPTD0 + legacy RNPTYPD0).

    Resolves the modern numeric ``price_type_id`` and the legacy 2-char
    ``npt_type`` to a human-readable description. Adjudication queries
    filter on ``is_active`` to skip deprecated codes (e.g. legacy '11'
    FFPUL frozen 2017-03-30 per SPEC Â§3.5).

    Global reference data â€” no TenantScopedMixin (LESSON-011).
    """

    __tablename__ = "fdb_price_type_desc"
    __table_args__ = (
        Index("ix_fdb_price_type_npt", "npt_type"),
        {"schema": SCHEMA},
    )

    price_type_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        comment="Modern PRICE_TYPE_ID. UNIQUE; PK.",
    )
    short_desc: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="e.g. 'SWP', 'WHN', 'WSD'",
    )
    long_desc: Mapped[str | None] = mapped_column(String(100), nullable=True)
    npt_type: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        comment=(
            "Legacy 2-char join key. NULL for modern-only codes "
            "(27/28/29 case prices)."
        ),
    )
    price_type_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
        comment=(
            "False for deprecated codes (e.g. legacy '11' FFPUL "
            "frozen 2017-03-30). Adjudication queries filter is_active."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


__all__ = [
    "FDBPricingBase",
    "FDBNDCPriceHistory",
    "FDBPriceTypeDesc",
    "SCHEMA",
]

 succeeded in 423ms:
"""FDB (First DataBank) NDDF Plus adapter â€” generic table surface.

Phase 8 / Phase 09 implementation. Replaces the prior 5-method stub
interface (`fetch_feed`/`parse_feed`/`parse_pricing`/`parse_interactions`/
`parse_dosing`) with a generic `TableSpec`-driven surface â€” codex MF5
fix per SPEC Â§3.7.2 (`data/reference/fdb/README.md`, locked at codex
GO commit `9aa576b`).

New shape:

  FDBAdapter (ABC):
    discover_latest_drop() -> FDBDrop
    open_table(drop, table_name, *, source) -> Iterator[bytes]
    parse_table(drop, spec, *, source) -> Iterator[dict]

  TableSpec: schema-driving dataclass (columns + coercers + filters).
  FDBDrop:   one full FDB delivery folder (drop_date + paths).

  FDBLocalDropAdapter: file-system concrete adapter for operator-
  managed drops at `data/reference/fdb/TEL251759D/`.

  Four TableSpec values for Phase 8: RNP3_NDC_PRICE (+ _UPD variant),
  RPRDPTD0_PRICE_TYPE_DESC, RNPTYPD0_NDC_PRICE_TYPE_DESC.

  parse_rnp3() typed wrapper for the hot-path RNP3 caller (15.6M rows
  weekly) â€” preserves IDE autocomplete + type-checker support at the
  ingester's main loop.

Why generic surface, not per-table abstractmethods (SPEC Â§3.7.2.2):
  * New tables become data (TableSpec values), not interface methods.
  * Single `test_parse_table_*` suite covers all tables.
  * Two-method MagicMock for tests vs. six-method.
  * Aspirational specs (DDIM, dosing) can't drift back in unused.

Discipline:
  * LESSON-004 â€” date regex uses `re.fullmatch(r"\\A\\d{8}\\Z", ...)`.
  * LESSON-005 â€” log keys prefixed `ingest_*`.
  * financial-precision.md â€” Decimal coercer; never float.
  * surgical-changes.md â€” TableSpec values only as SPEC Â§3.7.2 lists
    them. Additional hardening helpers (`_str11` / `_decimal_16_5` /
    etc.) deferred until a downstream unit needs them.
"""
from __future__ import annotations

import logging
import re
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypedDict

from drug_database.utils.ndc import InvalidNDCError, normalize_ndc

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FDBDropError(RuntimeError):
    """Raised when an FDB drop folder is malformed or inconsistent.

    Concrete cases: missing NDDF_PRODUCT_INFO.TXT, drop_date in
    the file content does not match the folder name, folder name
    does not parse as ``<DDMMMYYYY>.<LICENSE>``.
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FDB_DATE_RE = re.compile(r"\A\d{8}\Z")


def _parse_fdb_date(raw: str) -> date:
    """Parse an 8-digit YYYYMMDD string into a `date`.

    LESSON-004: `re.fullmatch` with `\\A\\d{8}\\Z` rejects trailing
    newlines and partial matches. Used as the canonical `effective_date`
    coercer for RNP3 + RPRDPP0 TableSpecs.
    """
    if not _FDB_DATE_RE.fullmatch(raw):
        raise ValueError(f"FDB date '{raw}' is not 8-digit YYYYMMDD")
    return datetime.strptime(raw, "%Y%m%d").date()


_DROP_FOLDER_RE = re.compile(r"\A(\d{2})([A-Z]{3})(\d{4})\.([A-Z]{3}\d{6}[A-Z])\Z")
_MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _parse_drop_folder_name(name: str) -> tuple[date, str]:
    """Parse folder name `<DDMMMYYYY>.<LICENSE>` â†’ (drop_date, license_code).

    Example: ``06MAY2026.TEL251759D`` â†’ (date(2026, 5, 6), "TEL251759D").
    Raises FDBDropError on malformed names.
    """
    m = _DROP_FOLDER_RE.fullmatch(name)
    if not m:
        raise FDBDropError(
            f"FDB drop folder name '{name}' does not match "
            f"<DDMMMYYYY>.<LICENSE> pattern"
        )
    dd, mmm, yyyy, license_code = m.groups()
    month = _MONTH_MAP.get(mmm)
    if month is None:
        raise FDBDropError(f"FDB drop folder month '{mmm}' is not a valid abbreviation")
    return date(int(yyyy), month, int(dd)), license_code


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FDBDrop:
    """One full FDB delivery folder (e.g. 06MAY2026.TEL251759D/).

    All paths are absolute; the adapter is responsible for resolving
    them. Tests typically construct FDBDrop with synthetic paths under
    a tempdir.
    """

    drop_date: date
    license_code: str
    db_zip_path: Path
    ddl_zip_path: Path
    upd_zip_path: Path
    highlights_zip_path: Path
    record_counts_path: Path


@dataclass(frozen=True)
class TableSpec:
    """Schema + parse rules for one FDB table.

    Drives `FDBAdapter.parse_table`. New tables in Phase C / Phase D
    become new TableSpec values â€” no FDBAdapter method needed for
    each one (SPEC Â§3.7.2.2).

    Fields:
      table_name: filename inside the zip (no extension); equals the
                  literal FDB table name (e.g. ``RNP3_NDC_PRICE``).
      columns:    column order â€” must match the DDL byte-for-byte.
      coercers:   raw_str â†’ typed value, per column. Coercer raising
                  ValueError / InvalidOperation / InvalidNDCError causes
                  the row to be logged + skipped (does NOT abort parsing).
      nullable:   columns where empty string â†’ None (bypasses coercer).
      sentinel_filter: row filter applied AFTER coercion. Rows where
                  the predicate returns True are SKIPPED.
                  E.g. RNP3 PRICE_TYPE='14' (NOPRC).
      has_transaction_code: True for UPD-shape files where each row is
                  prefixed with A/C/D + delimiter. parse_table extracts
                  the prefix into ``transaction_code``.
                  False for DB.zip files (treated as 'A' per Â§4.4).
    """

    table_name: str
    columns: Sequence[str]
    coercers: dict[str, Callable[[str], Any]]
    nullable: frozenset[str] = field(default_factory=frozenset)
    sentinel_filter: Callable[[dict[str, Any]], bool] | None = None
    has_transaction_code: bool = False


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class FDBAdapter(ABC):
    """Abstract interface for the FDB NDDF Plus delivery.

    Concerns: locating the latest drop; streaming individual table
    files; parsing pipe-delimited latin-1 rows into typed dicts via
    TableSpec. Loading into Postgres is delegated to the ingester
    service layer (Phase 09.7).
    """

    @abstractmethod
    def discover_latest_drop(self) -> FDBDrop:  # pragma: no cover - abstract
        """Return the FDB drop folder pointed at by ``Current/``.

        Resolves the symlink/junction; reads NDDF_PRODUCT_INFO.TXT
        (single-line YYYYMMDD) to confirm the drop date matches the
        folder name. Raises FDBDropError on mismatch.
        """

    @abstractmethod
    def open_table(
        self,
        drop: FDBDrop,
        table_name: str,
        *,
        source: str = "DB",
    ) -> Iterator[bytes]:  # pragma: no cover - abstract
        """Stream raw bytes for a single table file inside the chosen zip.

        ``source`` âˆˆ {"DB", "UPD"} â€” picks which zip to open. Streaming
        generator â€” never materializes the full file in memory (RNP3
        is 673 MB uncompressed).
        """

    @abstractmethod
    def parse_table(
        self,
        drop: FDBDrop,
        spec: TableSpec,
        *,
        source: str = "DB",
    ) -> Iterator[dict[str, Any]]:  # pragma: no cover - abstract
        """Parse one FDB table per the given TableSpec.

        Yields one dict per row with typed fields per spec.coercers.

        Behavior contract:
          * If spec.has_transaction_code, leading 'A'/'C'/'D' field is
            stripped and stored as ``transaction_code``. Otherwise rows
            are emitted with ``transaction_code='A'`` (DB.zip baseline,
            Â§4.4).
          * ``drop_sequence`` = parser line index within the file
            (0-indexed). Required for Â§4.4 stable same-as_of_date D+A
            ordering.
          * Rows where ``spec.sentinel_filter`` returns True are SKIPPED.
          * Rows whose field count != len(spec.columns) (after the
            optional A/C/D prefix) are LOGGED + SKIPPED with
            ``ingest_field_count_mismatch``.
          * Rows whose coercion raises ValueError / InvalidOperation /
            InvalidNDCError are LOGGED + SKIPPED with
            ``ingest_row_invalid``.
          * The yielded dict adds drop-level provenance:
            ``as_of_date = drop.drop_date``.
        """


# ---------------------------------------------------------------------------
# Streaming primitive
# ---------------------------------------------------------------------------


def _stream_pipe_rows(
    zip_path: Path, table_name: str, *, chunk_bytes: int = 2 * 1024 * 1024,
) -> Iterator[list[str]]:
    """Stream one row at a time from a table inside an FDB zip.

    Verified format (SPEC Â§2.2):
      * pipe (|) delimiter
      * latin-1 encoding (Windows-1252 superset)
      * CRLF (\\r\\n) line terminator
      * no header row
      * filename = literal table name (no extension)

    Yields list[str] of raw fields. No type coercion â€” callers decode
    via TableSpec.coercers in `parse_table`.

    Memory budget: peak is bounded by ``chunk_bytes`` + one row buffer.
    Default 2 MB chunk handles RNP3's 673 MB uncompressed body without
    materializing the file.
    """
    with zipfile.ZipFile(zip_path) as z:
        target = next(
            (n for n in z.namelist() if n.endswith(f"/{table_name}") or n == table_name),
            None,
        )
        if target is None:
            raise FileNotFoundError(
                f"FDB table '{table_name}' not found in zip '{zip_path.name}'"
            )
        with z.open(target) as f:
            buf = b""
            for chunk in iter(lambda: f.read(chunk_bytes), b""):
                buf += chunk
                *lines, buf = buf.split(b"\r\n")
                for line in lines:
                    if not line:
                        continue
                    yield line.decode("latin-1").split("|")
            # Trailing line without CRLF terminator (defensive â€” FDB
            # files do terminate, but guard against operator-edited
            # samples).
            if buf:
                yield buf.decode("latin-1").split("|")


# ---------------------------------------------------------------------------
# Concrete adapter â€” local file system
# ---------------------------------------------------------------------------


class FDBLocalDropAdapter(FDBAdapter):
    """File-system FDBAdapter for operator-managed drops.

    The vendor (FDB) delivers via FTP. Operator downloads + extracts to
    ``data/reference/fdb/TEL251759D/<DATE>.TEL251759D/`` and updates the
    ``Current/`` pointer. This adapter consumes from there; it does NOT
    automate the FTP fetch (operator concern; deferred to a future wave).
    """

    def __init__(self, root: Path) -> None:
        # root = data/reference/fdb/TEL251759D/
        self._root = root

    # ------------------------------------------------------------------
    # discover_latest_drop
    # ------------------------------------------------------------------

    def discover_latest_drop(self) -> FDBDrop:
        current = self._root / "Current"
        # Resolve symlink/NTFS-junction; on Windows the resolution is
        # handled by Path.resolve() since 3.6.
        resolved = current.resolve()

        drop_date, license_code = _parse_drop_folder_name(resolved.name)

        # Cross-check NDDF_PRODUCT_INFO.TXT (single-line YYYYMMDD).
        product_info_path = resolved / "NDDF_PRODUCT_INFO.TXT"
        product_info = product_info_path.read_text().strip()
        if not _FDB_DATE_RE.fullmatch(product_info):
            raise FDBDropError(
                f"NDDF_PRODUCT_INFO.TXT contents '{product_info}' "
                f"does not match expected YYYYMMDD format"
            )
        # Folder name encodes the vendor DELIVERY date. NDDF_PRODUCT_INFO
        # encodes the data CUTOFF date â€” vendor builds the drop a few days
        # before shipping it, so cutoff < delivery is normal. Wave B7 found
        # both 06MAY2026 and 29APR2026 drops had inner dates 6 days earlier.
        # Allow a tolerance of 30 days (weekly drops with normal delivery
        # lag stay well under). A future-dated cutoff (cutoff > delivery)
        # is suspicious â€” keep that as an error.
        info_date = datetime.strptime(product_info, "%Y%m%d").date()
        delta_days = (drop_date - info_date).days
        if delta_days < 0:
            # Inner date is AFTER delivery date â€” vendor data inconsistency
            raise FDBDropError(
                f"NDDF_PRODUCT_INFO.TXT date {product_info} is AFTER "
                f"folder name drop_date {drop_date.isoformat()} â€” refusing"
            )
        if delta_days > 30:
            raise FDBDropError(
                f"NDDF_PRODUCT_INFO.TXT date {product_info} is more than "
                f"30 days before folder name drop_date {drop_date.isoformat()} "
                f"({delta_days} days) â€” drops should ship weekly"
            )
        if delta_days > 0:
            _log.warning(
                "FDB drop %s has data cutoff %s (%d day delivery lag) â€” "
                "expected for normal vendor schedule",
                drop_date.isoformat(), info_date.isoformat(), delta_days,
            )

        return FDBDrop(
            drop_date=drop_date,
            license_code=license_code,
            db_zip_path=resolved / "NDDF Plus DB" / "NDDF PLUS DB.zip",
            ddl_zip_path=resolved / "NDDF Plus DDL" / "NDDF PLUS DDL.zip",
            upd_zip_path=resolved / "NDDF Plus UPD" / "NDDF PLUS UPD.zip",
            highlights_zip_path=resolved / "FDB_CLINICAL_HIGHLIGHTS.ZIP",
            record_counts_path=resolved / "RECORD_COUNTS.TXT",
        )

    # ------------------------------------------------------------------
    # open_table
    # ------------------------------------------------------------------

    def open_table(
        self,
        drop: FDBDrop,
        table_name: str,
        *,
        source: str = "DB",
    ) -> Iterator[bytes]:
        zip_path = drop.upd_zip_path if source == "UPD" else drop.db_zip_path
        with zipfile.ZipFile(zip_path) as z:
            target = next(
                (n for n in z.namelist() if n.endswith(f"/{table_name}") or n == table_name),
                None,
            )
            if target is None:
                raise FileNotFoundError(
                    f"FDB table '{table_name}' not found in {zip_path.name}"
                )
            with z.open(target) as f:
                yield from iter(lambda: f.read(2 * 1024 * 1024), b"")

    # ------------------------------------------------------------------
    # parse_table â€” generic body (works for any TableSpec)
    # ------------------------------------------------------------------

    def parse_table(
        self,
        drop: FDBDrop,
        spec: TableSpec,
        *,
        source: str = "DB",
    ) -> Iterator[dict[str, Any]]:
        rows_yielded = 0
        rows_skipped_filter = 0
        zip_path = drop.upd_zip_path if source == "UPD" else drop.db_zip_path
        expected_cols = len(spec.columns)

        for line_idx, fields in enumerate(_stream_pipe_rows(zip_path, spec.table_name)):
            # Strip transaction-code prefix for UPD-shape files.
            if spec.has_transaction_code:
                if not fields or fields[0] not in {"A", "C", "D"}:
                    _log.warning(
                        "fdb_table_transaction_code_missing",
                        extra={
                            "ingest_table": spec.table_name,
                            "ingest_line": line_idx,
                        },
                    )
                    continue
                transaction_code = fields[0]
                fields = fields[1:]
            else:
                transaction_code = "A"  # DB.zip rows treated as Add per Â§4.4.

            if len(fields) != expected_cols:
                _log.warning(
                    "fdb_table_field_count_mismatch",
                    extra={
                        "ingest_table": spec.table_name,
                        "ingest_field_count": len(fields),
                        "ingest_expected": expected_cols,
                        "ingest_row_sample": "|".join(fields)[:200],
                    },
                )
                continue

            try:
                row: dict[str, Any] = {
                    col: (
                        None
                        if (col in spec.nullable and not raw)
                        else spec.coercers[col](raw)
                    )
                    for col, raw in zip(spec.columns, fields, strict=True)
                }
            except (ValueError, InvalidOperation, InvalidNDCError) as e:
                _log.warning(
                    "fdb_table_row_invalid",
                    extra={
                        "ingest_table": spec.table_name,
                        "ingest_error": type(e).__name__,
                        "ingest_message": str(e),
                    },
                )
                continue

            # Sentinel filter (e.g. RNP3 PRICE_TYPE='14' NOPRC).
            if spec.sentinel_filter and spec.sentinel_filter(row):
                rows_skipped_filter += 1
                continue

            row["transaction_code"] = transaction_code
            row["drop_sequence"] = line_idx
            row["as_of_date"] = drop.drop_date
            yield row
            rows_yielded += 1

        _log.info(
            "fdb_table_parse_complete",
            extra={
                "ingest_table": spec.table_name,
                "ingest_rows_yielded": rows_yielded,
                "ingest_rows_skipped_filter": rows_skipped_filter,
            },
        )


# ---------------------------------------------------------------------------
# Phase 8 TableSpec values (SPEC Â§3.7.2)
# ---------------------------------------------------------------------------


RNP3_NDC_PRICE = TableSpec(
    table_name="RNP3_NDC_PRICE",
    columns=("ndc", "price_type", "effective_date_raw", "price_raw"),
    coercers={
        "ndc": normalize_ndc,                  # â†’ 11-digit normalized NDC
        "price_type": str,                     # 2-char legacy NPT_TYPE
        "effective_date_raw": _parse_fdb_date, # YYYYMMDD â†’ date
        "price_raw": Decimal,                  # NUMERIC(16,5) â€” never float
    },
    sentinel_filter=lambda r: r["price_type"] == "14",  # NOPRC â€” skip
    has_transaction_code=False,                # DB.zip
)

RNP3_NDC_PRICE_UPD = replace(RNP3_NDC_PRICE, has_transaction_code=True)


RPRDPTD0_PRICE_TYPE_DESC = TableSpec(
    table_name="RPRDPTD0_PRICE_TYPE_DESC",
    columns=(
        "price_type_id",
        "short_desc",
        "long_desc",
        "npt_type",
        "price_type_definition",
    ),
    coercers={
        "price_type_id": int,
        "short_desc": str,
        "long_desc": str,
        "npt_type": str,
        "price_type_definition": str,
    },
    nullable=frozenset({"long_desc", "npt_type", "price_type_definition"}),
    has_transaction_code=False,
)


RNPTYPD0_NDC_PRICE_TYPE_DESC = TableSpec(  # legacy 2-char-only catalog
    table_name="RNPTYPD0_NDC_PRICE_TYPE_DESC",
    columns=("npt_type", "short_desc"),
    coercers={"npt_type": str, "short_desc": str},
    has_transaction_code=False,
)


# ---------------------------------------------------------------------------
# Hot-path typed wrapper (SPEC Â§3.7.2.1)
# ---------------------------------------------------------------------------


class _RNP3Row(TypedDict):
    """Typed row shape for RNP3_NDC_PRICE consumers (hot path).

    Field renames vs. raw TableSpec output:
      ndc â†’ ndc_11   (matches schema column name)
      effective_date_raw â†’ effective_date
      price_raw â†’ price
    """

    ndc_11: str
    price_type: str
    effective_date: date
    price: Decimal
    transaction_code: str  # 'A' for DB.zip; 'A'/'C'/'D' for UPD.zip
    drop_sequence: int
    as_of_date: date


def parse_rnp3(
    adapter: FDBAdapter,
    drop: FDBDrop,
    *,
    source: str = "DB",
) -> Iterator[_RNP3Row]:
    """Hot-path RNP3 wrapper â€” typed return for the ingester's main loop.

    For all other tables, callers use ``adapter.parse_table(drop, spec)``
    directly and treat the returned dicts as ``Mapping[str, Any]``.
    """
    spec = RNP3_NDC_PRICE_UPD if source == "UPD" else RNP3_NDC_PRICE
    for row in adapter.parse_table(drop, spec, source=source):
        yield _RNP3Row(
            ndc_11=row["ndc"],
            price_type=row["price_type"],
            effective_date=row["effective_date_raw"],
            price=row["price_raw"],
            transaction_code=row.get("transaction_code", "A"),
            drop_sequence=row["drop_sequence"],
            as_of_date=row["as_of_date"],
        )


__all__ = [
    "FDBAdapter",
    "FDBDrop",
    "FDBDropError",
    "FDBLocalDropAdapter",
    "RNP3_NDC_PRICE",
    "RNP3_NDC_PRICE_UPD",
    "RNPTYPD0_NDC_PRICE_TYPE_DESC",
    "RPRDPTD0_PRICE_TYPE_DESC",
    "TableSpec",
    "parse_rnp3",
]

 succeeded in 414ms:
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:4:  * `awp_basis` is non-optional; default "NONE" preserves M0.4 callers.
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:5:  * NadacPricingLookup snapshots always emit `awp_basis="NONE"`.
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:6:  * `assert_awp_basis_acceptable` guard:
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:11:  * `_NADACSnapshot` dataclass exposes `awp_basis` as a settable field.
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:32:    assert_awp_basis_acceptable,
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:38:# _NADACSnapshot — awp_basis default + explicit setting
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:42:def test_nadac_snapshot_requires_explicit_awp_basis() -> None:
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:43:    """Phase 09.9 codex P9 fix I8 — awp_basis has NO default; must be set.
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:45:    Constructing without awp_basis is a TypeError (missing required
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:50:    with pytest.raises(TypeError, match="awp_basis"):
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:62:def test_nadac_snapshot_explicit_awp_basis_set() -> None:
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:63:    """awp_basis can be set explicitly when constructing."""
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:68:        awp_basis="NONE",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:74:    assert snap.awp_basis == "NONE"
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:83:        awp_basis="NONE",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:90:        snap.awp_basis = "FDB_SWP"  # type: ignore[misc]
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:94:# reclaimrx PriceSnapshot — awp_basis default
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:98:def test_pricesnapshot_requires_explicit_awp_basis() -> None:
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:103:    with pytest.raises(TypeError, match="awp_basis"):
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:125:        awp_basis="FDB_SWP",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:127:    assert snap.awp_basis == "FDB_SWP"
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:132:# assert_awp_basis_acceptable — consumer guard
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:146:        awp_basis="FDB_SWP",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:148:    result = assert_awp_basis_acceptable(
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:164:        awp_basis="LITERAL_AWP",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:166:    result = assert_awp_basis_acceptable(
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:182:        awp_basis="FDB_SWP",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:185:        assert_awp_basis_acceptable(
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:200:        awp_basis="FDB_SWD",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:203:        assert_awp_basis_acceptable(
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:218:        awp_basis="NONE",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:221:        assert_awp_basis_acceptable(
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:236:        awp_basis="FDB_SWP",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:239:        assert_awp_basis_acceptable(
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:257:    """Explicit awp_basis kwarg construction is the post-09.9 contract."""
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:262:        awp_basis="NONE",
modules\drug-database\tests\unit\test_pricing_snapshot_amendment.py:275:    assert snap.awp_basis == "NONE"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:1:"""Unit tests for FDBPricingLookup.lookup_at_dos / .lookup_at_dos_sync.
modules\drug-database\tests\unit\test_fdb_pricing_service.py:6:  AC-4 — awp_basis non-optional, ∈ {LITERAL_AWP / FDB_SWP / FDB_SWD / NONE}.
modules\drug-database\tests\unit\test_fdb_pricing_service.py:18:    - Tier 1 SWP hit → awp_basis="FDB_SWP"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:19:    - Tier 1 NULL + Tier 2 hit → awp_basis="FDB_SWD"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:20:    - Both null → awp_basis="NONE"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:40:from drug_database.services.fdb_pricing import FDBPricingLookup, _FDBPriceSnapshot
modules\drug-database\tests\unit\test_fdb_pricing_service.py:125:# §3.5c — awp_basis provenance
modules\drug-database\tests\unit\test_fdb_pricing_service.py:130:    """SWP code 07 row → awp_basis='FDB_SWP'."""
modules\drug-database\tests\unit\test_fdb_pricing_service.py:140:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:146:    assert snap.awp_basis == "FDB_SWP"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:152:    """No SWP, but SWD code 17 present → awp_basis='FDB_SWD'."""
modules\drug-database\tests\unit\test_fdb_pricing_service.py:162:    svc = FDBPricingLookup(db_session, awp_source="swd_cascade")
modules\drug-database\tests\unit\test_fdb_pricing_service.py:168:    assert snap.awp_basis == "FDB_SWD"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:174:    """Only WAC code 09 present → awp_basis='NONE', wac populated."""
modules\drug-database\tests\unit\test_fdb_pricing_service.py:184:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:191:    assert snap.awp_basis == "NONE"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:198:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:216:    svc = FDBPricingLookup(db_session, awp_source="strict_swp")
modules\drug-database\tests\unit\test_fdb_pricing_service.py:250:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:272:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:293:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:311:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:338:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:346:    assert snap.awp_basis == "FDB_SWP"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:392:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:409:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:419:    assert snap.awp_basis == "FDB_SWP"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:432:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:450:        awp_basis="NONE",
modules\drug-database\tests\unit\test_fdb_pricing_service.py:457:        snap.awp_basis = "FDB_SWP"  # type: ignore[misc]
modules\drug-database\tests\unit\test_fdb_pricing_service.py:467:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:482:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:506:    svc = FDBPricingLookup(session=session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:525:    svc = FDBPricingLookup(session=session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:551:    svc = FDBPricingLookup(db_session)
modules\drug-database\tests\unit\test_fdb_pricing_service.py:559:    assert snap.awp_basis == "FDB_SWP"
modules\drug-database\tests\unit\test_fdb_pricing_service.py:568:    """FDBPricingLookup.close() invokes session.close()."""
modules\drug-database\tests\unit\test_fdb_pricing_service.py:572:    svc = FDBPricingLookup(session=session)
modules\drug-database\tests\unit\test_fdb_pricing_models.py:171:    assert "fdb_ndc_price_history" in table_names
modules\drug-database\tests\unit\test_fdb_pricing_models.py:172:    assert "fdb_price_type_desc" in table_names
modules\drug-database\tests\unit\test_fdb_pricing_models.py:239:    """uq_fdb_ndc_price_history: 6-col composite key rejects duplicates.
modules\drug-database\tests\unit\test_fdb_pricing_models.py:365:    assert "fdb_ndc_price_history" in insp.get_table_names()
modules\drug-database\tests\unit\test_fdb_pricing_models.py:367:    cols = {c["name"] for c in insp.get_columns("fdb_ndc_price_history")}
modules\drug-database\tests\unit\test_fdb_pricing_models.py:386:    assert "fdb_price_type_desc" in insp.get_table_names()
modules\drug-database\tests\unit\test_fdb_pricing_models.py:388:    cols = {c["name"] for c in insp.get_columns("fdb_price_type_desc")}
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:15:    fdb_price_type_desc lookup at ingest time.
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:244:    """fdb_initial mode loads RPRDPTD0 + RNPTYPD0 into fdb_price_type_desc.
modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:399:    """When provided, ingestion_run_id is written on every fdb_ndc_price_history row."""
modules\drug-database\tests\unit\test_composite_pricing.py:8:    awp/wac None; awp_basis NONE; source "NADAC"; WARNING logged.
modules\drug-database\tests\unit\test_composite_pricing.py:15:Tests use mocked NadacPricingLookup + FDBPricingLookup factories — no
modules\drug-database\tests\unit\test_composite_pricing.py:55:        awp_basis="NONE",  # SPEC §3.5c — NADAC has no AWP curve
modules\drug-database\tests\unit\test_composite_pricing.py:67:    awp_basis: str = "FDB_SWP",
modules\drug-database\tests\unit\test_composite_pricing.py:76:        awp_basis=awp_basis,  # type: ignore[arg-type]
modules\drug-database\tests\unit\test_composite_pricing.py:143:            awp_basis="FDB_SWP",
modules\drug-database\tests\unit\test_composite_pricing.py:161:    assert snap.awp_basis == "FDB_SWP"
modules\drug-database\tests\unit\test_composite_pricing.py:198:    assert snap.awp_basis == "NONE"
modules\drug-database\tests\unit\test_composite_pricing.py:211:        fdb_return=_fdb_snap(awp_basis="FDB_SWP"),
modules\drug-database\tests\unit\test_composite_pricing.py:222:    assert snap.awp_basis == "FDB_SWP"
modules\drug-database\tests\unit\test_composite_pricing.py:295:    assert snap.awp_basis == "NONE"
modules\drug-database\tests\unit\test_composite_pricing.py:302:        fdb_return=_fdb_snap(awp_basis="FDB_SWP", source="FDB-SWP"),
modules\drug-database\tests\unit\test_composite_pricing.py:309:    assert snap.awp_basis == "FDB_SWP"
modules\drug-database\tests\unit\test_composite_pricing.py:317:            awp_basis="FDB_SWD", source="FDB-SWD-unknown-basis",
modules\drug-database\tests\unit\test_composite_pricing.py:325:    assert snap.awp_basis == "FDB_SWD"
modules\drug-database\tests\unit\test_composite_pricing.py:333:            awp_basis="FDB_SWD", source="FDB-SWD-unknown-basis",
modules\drug-database\tests\unit\test_composite_pricing.py:341:    assert snap.awp_basis == "FDB_SWD"
modules\drug-database\tests\unit\test_composite_pricing.py:402:        awp_basis="NONE",
modules\drug-database\tests\unit\test_composite_pricing.py:413:        snap.awp_basis = "FDB_SWP"  # type: ignore[misc]
modules\drug-database\tests\unit\test_bench_fdb_lookup_script.py:46:        assert "drug_database.fdb_ndc_price_history" in _bench._EXPLAIN_SQL
modules\drug-database\tests\unit\test_bench_fdb_lookup_script.py:118:        "                    ->  Seq Scan on fdb_ndc_price_history\n"
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:121:def test_upgrade_creates_fdb_ndc_price_history(engine_with_migration_context):
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:127:    assert "fdb_ndc_price_history" in insp.get_table_names()
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:129:    columns = {col["name"] for col in insp.get_columns("fdb_ndc_price_history")}
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:139:def test_upgrade_creates_fdb_price_type_desc(engine_with_migration_context):
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:145:    assert "fdb_price_type_desc" in insp.get_table_names()
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:147:    columns = {col["name"] for col in insp.get_columns("fdb_price_type_desc")}
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:162:        idx["name"] for idx in insp.get_indexes("fdb_ndc_price_history")
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:165:        idx["name"] for idx in insp.get_indexes("fdb_price_type_desc")
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:175:    """uq_fdb_ndc_price_history rejects duplicates on the 6-col key."""
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:182:    history = metadata.tables["fdb_ndc_price_history"]
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:224:    assert "fdb_ndc_price_history" not in tables
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:225:    assert "fdb_price_type_desc" not in tables
modules\drug-database\tests\unit\test_alembic_0008_fdb_pricing.py:239:    cols = {col["name"]: col for col in insp.get_columns("fdb_ndc_price_history")}
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:10:  * `FDBPricingLookup` instantiates against an app-scoped session and
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:88:    """FDBPricingBase.metadata exposes fdb_ndc_price_history + fdb_price_type_desc."""
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:92:    assert "fdb_ndc_price_history" in table_names
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:93:    assert "fdb_price_type_desc" in table_names
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:97:# FDBPricingLookup wired against a real SAVEPOINT-isolated session
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:137:    """FDBPricingLookup.lookup_at_dos returns None against an empty DB.
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:142:    from drug_database.services.fdb_pricing import FDBPricingLookup
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:144:    lookup = FDBPricingLookup(db_session)
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:169:    from drug_database.services.fdb_pricing import FDBPricingLookup
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:177:    def fdb_factory() -> FDBPricingLookup:
modules\drug-database\tests\integration\test_fdb_pricing_through_create_app.py:178:        return FDBPricingLookup(session=session_local())
modules\drug-database\alembic\versions\0008_fdb_pricing.py:5:  drug_database.fdb_ndc_price_history  — append-only NDC-keyed FDB price history
modules\drug-database\alembic\versions\0008_fdb_pricing.py:7:  drug_database.fdb_price_type_desc    — unified price-type catalog
modules\drug-database\alembic\versions\0008_fdb_pricing.py:55:    # fdb_ndc_price_history — Phase B SPEC §3.6.1
modules\drug-database\alembic\versions\0008_fdb_pricing.py:59:        "fdb_ndc_price_history",
modules\drug-database\alembic\versions\0008_fdb_pricing.py:72:                    "Joins to fdb_price_type_desc.npt_type. See SPEC §3.5 "
modules\drug-database\alembic\versions\0008_fdb_pricing.py:78:                    "fdb_price_type_desc lookup. NULL only for legacy code "
modules\drug-database\alembic\versions\0008_fdb_pricing.py:122:            name="uq_fdb_ndc_price_history",
modules\drug-database\alembic\versions\0008_fdb_pricing.py:138:        "fdb_ndc_price_history",
modules\drug-database\alembic\versions\0008_fdb_pricing.py:151:        "fdb_ndc_price_history", ["effective_date"], schema=_SCHEMA,
modules\drug-database\alembic\versions\0008_fdb_pricing.py:155:        "fdb_ndc_price_history", ["as_of_date"], schema=_SCHEMA,
modules\drug-database\alembic\versions\0008_fdb_pricing.py:159:    # fdb_price_type_desc — Phase B SPEC §3.6.2
modules\drug-database\alembic\versions\0008_fdb_pricing.py:163:        "fdb_price_type_desc",
modules\drug-database\alembic\versions\0008_fdb_pricing.py:193:        "ix_fdb_price_type_npt", "fdb_price_type_desc", ["npt_type"],
modules\drug-database\alembic\versions\0008_fdb_pricing.py:203:        table_name="fdb_price_type_desc", schema=_SCHEMA,
modules\drug-database\alembic\versions\0008_fdb_pricing.py:205:    op.drop_table("fdb_price_type_desc", schema=_SCHEMA)
modules\drug-database\alembic\versions\0008_fdb_pricing.py:209:        table_name="fdb_ndc_price_history", schema=_SCHEMA,
modules\drug-database\alembic\versions\0008_fdb_pricing.py:213:        table_name="fdb_ndc_price_history", schema=_SCHEMA,
modules\drug-database\alembic\versions\0008_fdb_pricing.py:217:        table_name="fdb_ndc_price_history", schema=_SCHEMA,
modules\drug-database\alembic\versions\0008_fdb_pricing.py:219:    # uq_fdb_ndc_price_history is an inline UNIQUE — drops with the table.
modules\drug-database\alembic\versions\0008_fdb_pricing.py:220:    op.drop_table("fdb_ndc_price_history", schema=_SCHEMA)
modules\drug-database\README [conflicted].md:75:- Cross-module consumers (e.g. `adjudication-engine/src/services/pricing_enrichment.py`)
modules\drug-database\drug_database\services\composite_pricing.py:3:Composes `NadacPricingLookup` and `FDBPricingLookup` into a single
modules\drug-database\drug_database\services\composite_pricing.py:55:from drug_database.services.fdb_pricing import AwpBasis, FDBPricingLookup, _FDBPriceSnapshot
modules\drug-database\drug_database\services\composite_pricing.py:78:        config + SWP missing). `awp_basis` is then "NONE".
modules\drug-database\drug_database\services\composite_pricing.py:80:    `awp_basis` is non-optional per §3.5c.
modules\drug-database\drug_database\services\composite_pricing.py:89:    awp_basis: AwpBasis  # Literal["LITERAL_AWP","FDB_SWP","FDB_SWD","NONE"]
modules\drug-database\drug_database\services\composite_pricing.py:111:FdbFactory = Callable[[], FDBPricingLookup]
modules\drug-database\drug_database\services\composite_pricing.py:195:        Both NadacPricingLookup and FDBPricingLookup expose `close()`
modules\drug-database\drug_database\services\composite_pricing.py:282:    # awp_basis: take FDB's basis when FDB is present; otherwise NONE
modules\drug-database\drug_database\services\composite_pricing.py:284:    awp_basis: AwpBasis = fdb.awp_basis if fdb is not None else "NONE"
modules\drug-database\drug_database\services\composite_pricing.py:290:        awp_basis=awp_basis,
modules\drug-database\drug_database\services\pricing.py:20:# Phase 09 / 09.6 amendment — awp_basis Literal type is shared with the
modules\drug-database\drug_database\services\pricing.py:119:    semantics). Phase 8 fills them via FDBPricingLookup; the composite
modules\drug-database\drug_database\services\pricing.py:123:      * `awp_basis` is non-optional and has NO default. Constructors
modules\drug-database\drug_database\services\pricing.py:133:    awp_basis: _AwpBasis            # SPEC §3.5c — non-optional, no default
modules\drug-database\drug_database\services\pricing.py:168:        Phase 09.9 codex P9 pass 2 fix — mirrors FDBPricingLookup.close()
modules\drug-database\drug_database\services\pricing.py:198:        true sync companion mirroring FDBPricingLookup's shape. The
modules\drug-database\drug_database\services\pricing.py:246:                        awp_basis="NONE",  # Phase 09.9 codex I8 — explicit
modules\drug-database\drug_database\services\pricing.py:285:            awp_basis="NONE",  # Phase 09.9 codex I8 — NADAC always emits NONE
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:15:                uq_fdb_ndc_price_history).
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:34:    fdb_price_type_desc.
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:40:  * Loads RNP3_NDC_PRICE (15.6M, big) into fdb_ndc_price_history.
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:49:    `ingestion_run_id` column on fdb_ndc_price_history is left NULL
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:195:        """Load RPRDPTD0 + RNPTYPD0 into fdb_price_type_desc per SPEC §3.5.
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:309:        """Load RNP3_NDC_PRICE rows into fdb_ndc_price_history.
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:384:                     "uq_fdb_ndc_price_history"). One round-trip; skipped
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:431:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
modules\drug-database\drug_database\services\fdb_pricing_ingester.py:451:        Used to denormalize `price_type_id` on each fdb_ndc_price_history
modules\drug-database\drug_database\services\fdb_pricing.py:3:Phase 09 / Unit 09.4 deliverable. Implements `FDBPricingLookup` per
modules\drug-database\drug_database\services\fdb_pricing.py:7:triple by querying `fdb_ndc_price_history`. The query implements the
modules\drug-database\drug_database\services\fdb_pricing.py:15:  * Tier 1 — SWP (price_type IN ('07','08'))   → awp_basis="FDB_SWP"
modules\drug-database\drug_database\services\fdb_pricing.py:16:  * Tier 2 — SWD (price_type IN ('17','18'))   → awp_basis="FDB_SWD"
modules\drug-database\drug_database\services\fdb_pricing.py:21:  * Tier 1 hit                          → awp_basis="FDB_SWP"
modules\drug-database\drug_database\services\fdb_pricing.py:22:  * Tier 1 NULL + Tier 2 hit            → awp_basis="FDB_SWD"
modules\drug-database\drug_database\services\fdb_pricing.py:23:  * Both NULL                           → awp_basis="NONE"
modules\drug-database\drug_database\services\fdb_pricing.py:88:    """FDB-only price snapshot returned by FDBPricingLookup.
modules\drug-database\drug_database\services\fdb_pricing.py:95:    `awp_basis` is non-optional; "NONE" when `awp_per_unit is None`.
modules\drug-database\drug_database\services\fdb_pricing.py:101:    awp_basis: AwpBasis
modules\drug-database\drug_database\services\fdb_pricing.py:113:class FDBPricingLookup:
modules\drug-database\drug_database\services\fdb_pricing.py:196:          5. Build snapshot. `awp_basis` = FDB_SWP | FDB_SWD | NONE.
modules\drug-database\drug_database\services\fdb_pricing.py:233:        awp_basis: AwpBasis
modules\drug-database\drug_database\services\fdb_pricing.py:235:            awp_basis = "FDB_SWP"
modules\drug-database\drug_database\services\fdb_pricing.py:240:            awp_basis = "FDB_SWD" if awp_row is not None else "NONE"
modules\drug-database\drug_database\services\fdb_pricing.py:243:            awp_basis = "NONE"
modules\drug-database\drug_database\services\fdb_pricing.py:255:            awp_row=awp_row, awp_basis=awp_basis, wac_row=wac_row,
modules\drug-database\drug_database\services\fdb_pricing.py:392:        awp_basis: AwpBasis,
modules\drug-database\drug_database\services\fdb_pricing.py:412:        if awp_basis == "FDB_SWP":
modules\drug-database\drug_database\services\fdb_pricing.py:414:        elif awp_basis == "FDB_SWD":
modules\drug-database\drug_database\services\fdb_pricing.py:425:            awp_basis=awp_basis,
modules\drug-database\drug_database\services\fdb_pricing.py:452:            # Phase 09.9 codex P9 fix CACHE-2: validate awp_basis
modules\drug-database\drug_database\services\fdb_pricing.py:456:            basis = payload.get("awp_basis")
modules\drug-database\drug_database\services\fdb_pricing.py:462:                        "cache_reason": "invalid_awp_basis",
modules\drug-database\drug_database\services\fdb_pricing.py:479:                awp_basis=basis,
modules\drug-database\drug_database\services\fdb_pricing.py:513:                        "awp_basis": snapshot.awp_basis,
modules\drug-database\drug_database\services\fdb_pricing.py:531:    "FDBPricingLookup",
modules\drug-database\drug_database\models\fdb_pricing_tables.py:8:  drug_database.fdb_ndc_price_history  — append-only NDC-keyed FDB price
modules\drug-database\drug_database\models\fdb_pricing_tables.py:10:  drug_database.fdb_price_type_desc    — unified price-type catalog
modules\drug-database\drug_database\models\fdb_pricing_tables.py:80:    __tablename__ = "fdb_ndc_price_history"
modules\drug-database\drug_database\models\fdb_pricing_tables.py:82:        # Composite uniqueness — mirrors `uq_fdb_ndc_price_history` in the
modules\drug-database\drug_database\models\fdb_pricing_tables.py:94:            name="uq_fdb_ndc_price_history",
modules\drug-database\drug_database\models\fdb_pricing_tables.py:129:            "Joins to fdb_price_type_desc.npt_type. See SPEC §3.5 "
modules\drug-database\drug_database\models\fdb_pricing_tables.py:138:            "fdb_price_type_desc lookup. NULL only for legacy code "
modules\drug-database\drug_database\models\fdb_pricing_tables.py:204:    __tablename__ = "fdb_price_type_desc"
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:3:`PriceSnapshot` carries a non-optional `awp_basis` field that names the
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:6:`assert_awp_basis_acceptable` helper to prevent silent SWP-as-AWP
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:9:`awp_basis` values:
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:25:`awp_basis` has no default — every constructor MUST pass it
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:27:pass `"NONE"` since NADAC has no AWP curve; FDBPricingLookup chooses
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:48:    `awp_basis != "LITERAL_AWP"` — refusing the silent SWP-as-AWP
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:63:      * `awp_basis` is non-optional and has NO default. Constructors
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:74:      * `awp_basis`      — names the provenance of `awp_per_unit`.
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:94:    awp_basis: AwpBasis              # SPEC §3.5c — non-optional, no default
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:112:    """Protocol satisfied structurally by NadacPricingLookup, FDBPricingLookup,
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:128:def assert_awp_basis_acceptable(
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:153:    if requires_literal_awp and snapshot.awp_basis != "LITERAL_AWP":
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:156:            f"basis={snapshot.awp_basis!r} — refusing silent "
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:157:            f"{snapshot.awp_basis}-as-AWP substitution. Either expand "
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:159:            f"explicitly accept {snapshot.awp_basis}, or switch to a "
modules\reclaimrx\src\reclaimrx\detection\pricing_protocol.py:170:    "assert_awp_basis_acceptable",
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:10:    str(Decimal) per financial-precision rule; awp_basis carried verbatim.
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:30:from src.services import pricing_enrichment
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:36:    pricing_enrichment.reset_for_tests()
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:39:    pricing_enrichment.reset_for_tests()
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:50:        pricing_enrichment.enrich_pricing(
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:58:        "awp_basis": "NONE",
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:66:        pricing_enrichment.enrich_pricing(
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:70:    assert result["awp_basis"] == "NONE"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:84:        pricing_enrichment.enrich_pricing(
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:88:    assert result["awp_basis"] == "NONE"  # composite was None, fallback fired
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:98:    assert pricing_enrichment._parse_dos("20260506") == date(2026, 5, 6)
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:103:    assert pricing_enrichment._parse_dos("2026-05-06") == date(2026, 5, 6)
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:108:    assert pricing_enrichment._parse_dos("not-a-date") is None
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:109:    assert pricing_enrichment._parse_dos("") is None
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:126:        pricing_enrichment, "_get_composite", lambda: mock_composite,
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:138:    snap.awp_basis = "FDB_SWP"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:142:        pricing_enrichment.enrich_pricing(
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:150:        "awp_basis": "FDB_SWP",
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:161:    snap.awp_basis = "NONE"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:165:        pricing_enrichment.enrich_pricing(
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:172:    assert result["awp_basis"] == "NONE"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:181:        pricing_enrichment.enrich_pricing(
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:185:    assert result["awp_basis"] == "NONE"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:201:        pricing_enrichment, "_get_composite", lambda: mock_composite,
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:204:    with caplog.at_level(logging.WARNING, logger="adjudication_engine.pricing_enrichment"):
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:206:            pricing_enrichment.enrich_pricing(
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:210:    assert result["awp_basis"] == "NONE"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:212:        r.message == "pricing_enrichment_lookup_failed" for r in caplog.records
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:225:    snap.awp_basis = "NONE"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:228:    with caplog.at_level(logging.WARNING, logger="adjudication_engine.pricing_enrichment"):
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:230:            pricing_enrichment.enrich_pricing(
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:234:    assert result["awp_basis"] == "NONE"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:237:        r.message == "pricing_enrichment_dos_unparseable" for r in caplog.records
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:253:        snap.awp_basis = "NONE"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:258:    monkeypatch.setattr(pricing_enrichment, "_get_composite", lambda: mock)
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:261:        pricing_enrichment.enrich_pricing(
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:280:      1. DATABASE_URL{,_SYNC} unset → `pricing_enrichment_db_url_missing`
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:282:         `pricing_enrichment_init_failed`
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:291:    with caplog.at_level(logging.WARNING, logger="adjudication_engine.pricing_enrichment"):
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:292:        result = pricing_enrichment._get_composite()
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:296:            "pricing_enrichment_db_url_missing",
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:297:            "pricing_enrichment_init_failed",
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:307:    pricing_enrichment._composite_attempted = True
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:308:    pricing_enrichment._composite_cached = "stale"
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:310:    pricing_enrichment.reset_for_tests()
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:311:    assert pricing_enrichment._composite_attempted is False
modules\adjudication-engine\tests\unit\test_pricing_enrichment.py:312:    assert pricing_enrichment._composite_cached is None
modules\adjudication-engine\src\services\pricing_enrichment.py:6:`nadac_per_unit / wac_per_unit / awp_per_unit / awp_basis` (Phase 10 /
modules\adjudication-engine\src\services\pricing_enrichment.py:47:logger = logging.getLogger("adjudication_engine.pricing_enrichment")
modules\adjudication-engine\src\services\pricing_enrichment.py:56:    "awp_basis": "NONE",
modules\adjudication-engine\src\services\pricing_enrichment.py:116:            FDBPricingLookup,
modules\adjudication-engine\src\services\pricing_enrichment.py:127:                "pricing_enrichment_db_url_missing",
modules\adjudication-engine\src\services\pricing_enrichment.py:142:            return FDBPricingLookup(session=session_local())
modules\adjudication-engine\src\services\pricing_enrichment.py:150:            "pricing_enrichment_init_failed",
modules\adjudication-engine\src\services\pricing_enrichment.py:169:         "awp_per_unit":   str | None, "awp_basis": "FDB_SWP" | ... | "NONE"}
modules\adjudication-engine\src\services\pricing_enrichment.py:186:            "pricing_enrichment_dos_unparseable",
modules\adjudication-engine\src\services\pricing_enrichment.py:200:            "pricing_enrichment_lookup_failed",
modules\adjudication-engine\src\services\pricing_enrichment.py:222:        "awp_basis": snap.awp_basis,
modules\adjudication-engine\tests\integration\test_tcp_listener_publish.py:25:     awp_basis (None-defaults are acceptable when enrichment is off).
modules\adjudication-engine\tests\integration\test_tcp_listener_publish.py:171:    from src.services.pricing_enrichment import reset_for_tests  # noqa: PLC0415
modules\adjudication-engine\tests\integration\test_tcp_listener_publish.py:221:    assert "awp_basis" in payload, "Payload missing 'awp_basis'"
modules\adjudication-engine\tests\integration\test_tcp_listener_publish.py:226:    assert payload["awp_basis"] == "NONE"
modules\adjudication-engine\tests\integration\test_tcp_listener_publish.py:262:    from src.services.pricing_enrichment import reset_for_tests  # noqa: PLC0415
modules\adjudication-engine\src\services\tcp_listener (conflicted).py:74:from ..services.pricing_enrichment import enrich_pricing
modules\adjudication-engine\src\services\tcp_listener (conflicted).py:546:                    awp_basis=_pricing["awp_basis"],
modules\adjudication-engine\src\events\publishers.py:58:    awp_basis: str = "NONE",
modules\adjudication-engine\src\events\publishers.py:117:            "awp_basis": awp_basis,
modules\adjudication-engine\src\api\admin_routes.py:54:from ..services.pricing_enrichment import enrich_pricing
modules\adjudication-engine\src\api\admin_routes.py:464:                awp_basis=_pricing["awp_basis"],

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'infrastructure\\scripts\\lib\\expected_reference_tables.txt'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'infrastructure\\scripts\\setup_fdw.sh' | Select-Object -First 380" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'modules\\adjudication-engine\\src\\services\\pricing_enrichment.py'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-Content -LiteralPath 'modules\\reclaimrx\\src\\reclaimrx\\detection\\pricing_protocol.py'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 375ms:
# Wave B7 â€” EXPECTED reference DB tables manifest (FIRST-RUN RECONCILED 2026-05-10)
#
# Format: <schema>|<table>     # optional comment after #
#
# Coverage contract for C9 Phase 1. Reconciled from actual ingestion
# after C8 first-run completed (18/18 loaders OK). Tables included only
# if they have > 0 rows. Empty tables (env-DB types, unimplemented
# loader paths) are present but NOT in manifest.
#
# Manifest grows as new sources are added; does NOT shrink without
# charter amendment.

drug_database|drug_active_ingredients
drug_database|drug_asp_pricing
drug_database|drug_asp_pricing_history
drug_database|drug_exclusivity
drug_database|drug_nadac_pricing
drug_database|drug_nadac_pricing_history
drug_database|drug_orange_book
drug_database|drug_packages
drug_database|drug_patents
drug_database|drug_pharm_classes
drug_database|drug_purple_book
drug_database|drug_rems
drug_database|drug_rems_ndc
drug_database|drug_shortages
drug_database|drug_shortages_history
drug_database|drugs
drug_database|fdb_ndc_price_history
drug_database|fdb_price_type_desc
drug_database|rxnorm_atc_crosswalk
drug_database|rxnorm_attributes
drug_database|rxnorm_concepts
drug_database|rxnorm_ndc_crosswalk
drug_database|rxnorm_relationships
drug_database|rxnorm_semantic_types
pharmacy_dir|dataq_change_of_ownership
pharmacy_dir|dataq_eprescribing_information
pharmacy_dir|dataq_fwa_attestation
pharmacy_dir|dataq_master
pharmacy_dir|dataq_medicaid_information
pharmacy_dir|dataq_parent_organization
pharmacy_dir|dataq_payment_center
pharmacy_dir|dataq_provider_relationship
pharmacy_dir|dataq_relationship_demographic
pharmacy_dir|dataq_remit_and_reconciliation
pharmacy_dir|dataq_services_offered
pharmacy_dir|dataq_state_license
pharmacy_dir|dataq_taxonomy_information
pharmacy_dir|ncpdp_pharmacy_additional_info
pharmacy_dir|ncpdp_pharmacy_coordinates
pharmacy_dir|ncpdp_pharmacy_erx_capabilities
pharmacy_dir|ncpdp_pharmacy_fwa_actions
pharmacy_dir|ncpdp_pharmacy_medicaid
pharmacy_dir|ncpdp_pharmacy_patient_care
pharmacy_dir|ncpdp_pharmacy_programs
pharmacy_dir|ncpdp_pharmacy_recertification
pharmacy_dir|ncpdp_pharmacy_remittance
pharmacy_dir|ncpdp_pharmacy_services
pharmacy_dir|ncpdp_pharmacy_state_licenses
pharmacy_dir|ncpdp_pharmacy_taxonomies
prescriber_dir|data_refresh_log
prescriber_dir|medicare_opt_out
prescriber_dir|nppes_prescriber_details
prescriber_dir|prescriber_addresses
prescriber_dir|prescriber_identifiers
prescriber_dir|prescriber_taxonomies
prescriber_dir|prescribers
shared|government_program_bins
shared|hcpcs_codes
shared|icd10_cm_codes
shared|ingestion_runs
shared|ofac_sdn
shared|ofac_sdn_addresses
shared|ofac_sdn_aliases
shared|ofac_sdn_comments
shared|oig_leie_exclusions
shared|sam_exclusions

 succeeded in 437ms:
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
# Iterates all 66 entries in expected_reference_tables.txt and confirms each
# foreign table is queryable via FDW in each target env DB.
# Foreign tables are mounted as reference.<table> regardless of source schema.
# PASS = query exits 0 (empty result is fine â€” FDW link is the contract).
# Uses exec_psql_strict (respects IN_DOCKER flag, same as Phase 1 path).
# Exit 0 if all tables pass; exit 1 if any fail.
if [ "$MODE" = "verify" ]; then
  LIB_DIR="$SCRIPT_DIR/lib"
  MANIFEST="$LIB_DIR/expected_reference_tables.txt"
  if [ ! -f "$MANIFEST" ]; then
    echo "FATAL: manifest not found: $MANIFEST" >&2
    exit 2
  fi

  # Assert manifest contains exactly 66 data lines (non-blank, non-comment).
  # Protects against silent manifest truncation producing false-PASS results.
  MANIFEST_COUNT=0
  while IFS='|' read -r schema table; do
    table="${table%$'\r'}"; schema="${schema%$'\r'}"
    [[ -z "$schema" || "$schema" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$table" ]] && continue
    MANIFEST_COUNT=$((MANIFEST_COUNT + 1))
  done < "$MANIFEST"
  if [ "$MANIFEST_COUNT" -ne 66 ]; then
    echo "FATAL: manifest has ${MANIFEST_COUNT} data lines; expected 66. Update this check if the manifest was intentionally expanded." >&2
    exit 2
  fi
  echo "  Manifest: ${MANIFEST_COUNT} entries"

  total_pass=0
  total_fail=0
  fail_details=()

  for env in "${ENVS[@]}"; do
    env_db="infinityrx_${env}"
    env_pass=0
    env_fail=0
    echo "â”€â”€ Verifying FDW foreign tables in ${env_db} â”€â”€"
    while IFS='|' read -r schema table; do
      # Strip Windows CR if present
      table="${table%$'\r'}"
      schema="${schema%$'\r'}"
      # Skip blank lines and comment lines
      [[ -z "$schema" || "$schema" =~ ^[[:space:]]*# ]] && continue
      [[ -z "$table" ]] && continue
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
    done < "$MANIFEST"
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

 succeeded in 409ms:
"""Pricing Protocol amended for Phase 8 (SPEC Â§3.5c MF4 fix).

`PriceSnapshot` carries a non-optional `awp_basis` field that names the
provenance of `awp_per_unit`. Consumers performing AWP-named external
reimbursement contracts MUST guard the value with the
`assert_awp_basis_acceptable` helper to prevent silent SWP-as-AWP
substitution into a contract that demands literal AWP.

`awp_basis` values:

  * "LITERAL_AWP" â€” value is a literal Average Wholesale Price from a
    vendor that publishes AWP under that name (e.g. Medi-Span,
    Red Book, FDB BlueBook AWP add-on). NEVER from FDB NDDF Plus
    (FDB discontinued AWP 2011-09-28).
  * "FDB_SWP"     â€” value is FDB Suggested Wholesale Price (codes
    07/08). Industry-standard post-2011 AWP-equivalent benchmark per
    SPEC Â§3.5b.
  * "FDB_SWD"     â€” value is FDB Consolidated Price 2 (codes 17/18) â€”
    FDB's pre-built SWPâ†’WACâ†’DIR cascade. Source basis NOT recovered
    in Phase 8.
  * "NONE"        â€” `awp_per_unit is None`. Always emitted as the
    basis when no AWP-equivalent value is available. Includes the
    NADAC-only path (NADAC has no AWP curve).

`awp_basis` has no default â€” every constructor MUST pass it
explicitly (Phase 09.9 codex P9 fix I8). NadacPricingLookup callers
pass `"NONE"` since NADAC has no AWP curve; FDBPricingLookup chooses
between `"FDB_SWP"` / `"FDB_SWD"` / `"NONE"` per the resolved tier.
The previous default of `"NONE"` was removed because it risked silent
provenance erasure when a new caller forgot the field.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

AwpBasis = Literal["LITERAL_AWP", "FDB_SWP", "FDB_SWD", "NONE"]


class ContractAWPGuardError(Exception):
    """Raised when a literal-AWP contract is asked to consume a non-literal basis.

    SPEC Â§3.5c: external-facing reimbursement contracts that name "AWP"
    by string MUST guard at consumption time. The guard fires when
    `contract.requires_literal_awp` is True and the snapshot's
    `awp_basis != "LITERAL_AWP"` â€” refusing the silent SWP-as-AWP
    substitution.

    Resolutions:
      1. Expand FDB licensing to BlueBook AWP (literal AWP feed).
      2. Amend the contract to explicitly accept FDB_SWP.
      3. Switch the contract to a non-AWP fee schedule.
    """


@dataclass(frozen=True)
class PriceSnapshot:
    """Point-in-time pricing snapshot returned by lookup_at_dos.

    Phase 8 amendment per SPEC Â§3.5c (Phase 09.9 codex P9 fix I8):
      * `awp_basis` is non-optional and has NO default. Constructors
        MUST set it explicitly. The previous default of `"NONE"`
        contradicted Â§3.5c's "must be set explicitly" rule and risked
        silent provenance erasure for new constructors that forgot
        the field.

    Field semantics:
      * `nadac_per_unit` â€” populated from drug_nadac_pricing_history.
      * `wac_per_unit`   â€” populated from FDB codes 09/10 (Phase 8+).
      * `awp_per_unit`   â€” populated from FDB SWP (07/08) or SWD
        (17/18) per Phase 8 Â§3.8.2; literal AWP from a future vendor.
      * `awp_basis`      â€” names the provenance of `awp_per_unit`.
        See module docstring for the four values.
      * `effective_date` / `as_of_date` â€” legacy single-source dates;
        for composite snapshots = MAX(per-source non-null dates).
      * `nadac_effective_date` / `nadac_as_of_date` â€” per-source
        provenance dates for NADAC (Phase 10 / Item 3 amendment per
        SPEC Â§3.9.5.1). None when NADAC contributed nothing
        (single-source FDB snapshot, NADAC timeout, NADAC error).
      * `fdb_effective_date` / `fdb_as_of_date` â€” per-source
        provenance dates for FDB. None when FDB contributed nothing
        (single-source NADAC snapshot, FDB timeout, FDB error).
      * `source`         â€” short label, e.g. "NADAC", "FDB-SWP",
        "NADAC+FDB-SWP".
      * `source_version` â€” concatenated drop versions, e.g.
        "NADAC_20260301+FDB_20260506".
    """

    nadac_per_unit: Decimal | None
    wac_per_unit: Decimal | None
    awp_per_unit: Decimal | None
    awp_basis: AwpBasis              # SPEC Â§3.5c â€” non-optional, no default
    effective_date: date
    as_of_date: date
    source: str
    source_version: str
    # --- per-source provenance dates (Phase 10 / Item 3, SPEC Â§3.9.5.1) ---
    # These default to None so existing single-source callers that don't
    # populate them keep working unchanged. Composite snapshots (Phase
    # 09.5 _CompositePriceSnapshot) populate them with the relevant
    # source's effective_date / as_of_date.
    nadac_effective_date: date | None = None
    nadac_as_of_date: date | None = None
    fdb_effective_date: date | None = None
    fdb_as_of_date: date | None = None


@runtime_checkable
class PricingLookup(Protocol):
    """Protocol satisfied structurally by NadacPricingLookup, FDBPricingLookup,
    and CompositePricingLookup.

    reclaimrx imports only this Protocol at runtime â€” never drug-database
    directly. Wired at adjudication-engine startup or in test fixtures via
    dependency injection.
    """

    async def lookup_at_dos(
        self,
        ndc: str,
        date_of_service: date,
        knowledge_date: date | None = None,
    ) -> PriceSnapshot | None: ...


def assert_awp_basis_acceptable(
    snapshot: PriceSnapshot,
    *,
    requires_literal_awp: bool,
    contract_id: str = "<unknown>",
) -> Decimal | None:
    """Guard helper for AWP-named reimbursement contracts (SPEC Â§3.5c).

    Returns ``snapshot.awp_per_unit`` when:
      * the contract does NOT require literal AWP, OR
      * the contract requires literal AWP AND the snapshot's basis is
        ``"LITERAL_AWP"``.

    Raises ``ContractAWPGuardError`` when a literal-AWP contract is
    asked to consume a non-literal basis (e.g. FDB_SWP, FDB_SWD, NONE).
    Exception message identifies the contract and the basis encountered
    so the operator can choose between resolutions documented on the
    exception class.

    Internal callers (anomaly detection, ML features, fraud scoring)
    should NOT use this helper â€” read ``snapshot.awp_per_unit`` directly;
    the SWP-as-AWP substitution is documented and acceptable for
    benchmark purposes per SPEC Â§3.5b. **External-facing reimbursement
    paths MUST use this guard.**
    """
    if requires_literal_awp and snapshot.awp_basis != "LITERAL_AWP":
        raise ContractAWPGuardError(
            f"Contract {contract_id} requires LITERAL_AWP but snapshot has "
            f"basis={snapshot.awp_basis!r} â€” refusing silent "
            f"{snapshot.awp_basis}-as-AWP substitution. Either expand "
            f"FDB licensing to BlueBook AWP, amend the contract to "
            f"explicitly accept {snapshot.awp_basis}, or switch to a "
            f"non-AWP fee schedule."
        )
    return snapshot.awp_per_unit


__all__ = [
    "AwpBasis",
    "ContractAWPGuardError",
    "PriceSnapshot",
    "PricingLookup",
    "assert_awp_basis_acceptable",
]

 succeeded in 410ms:
"""FDB pricing enrichment for the claim.adjudicated event payload.

Phase 10 / Item 1 deliverable. Wires `CompositePricingLookup` (drug-
database) into the adjudication-engine claim publishing path so the
emitted `claim.adjudicated` event payload carries
`nadac_per_unit / wac_per_unit / awp_per_unit / awp_basis` (Phase 10 /
Item 2) per SPEC Â§3.9.6.

Per CLAUDE.md non-negotiable #7, adjudication-engine is the platform's
gateway and is allowed to direct-import from drug-database. This helper
isolates that cross-module touch to a single file so the rest of
adjudication-engine doesn't need to know about FDB pricing internals.

Feature flag: `FDB_PRICING_ENRICHMENT_ENABLED` env var (default: off).
When off, `enrich_pricing()` returns the all-None / "NONE" default dict
unconditionally â€” adjudication ships normally, the event payload's
new fields stay null, no DB hit.

When on, the helper:
  1. Constructs `CompositePricingLookup` lazily (once per process) with
     fresh-session factories backed by DATABASE_URL_SYNC.
  2. Parses `date_of_service` from NCPDP CCYYMMDD format â†’ `date`.
  3. Calls `composite.lookup_at_dos(ndc, dos)` with `knowledge_date=today`.
  4. Maps the snapshot to the four-field dict, serializing Decimals as
     strings per financial-precision rule.
  5. On any failure (DB unreachable, malformed NDC, malformed date,
     timeout), logs at WARNING and returns the default dict â€” silent-
     fallback rule per SPEC Â§3.9.4.

The helper is intentionally synchronous at the call site even though
`CompositePricingLookup.lookup_at_dos` is async â€” adjudication's
publish path runs inside an async route, so a thin `asyncio.run`-style
bridge is unnecessary; we use the loop's `run_until_complete` pattern
via `asyncio.get_event_loop().run_until_complete` if called from a
sync context. For now, the public API returns a coroutine which the
async caller awaits.

LESSON-005: log keys prefixed `pricing_*`.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any

logger = logging.getLogger("adjudication_engine.pricing_enrichment")


# Default snapshot fields when enrichment is disabled, NDC fails to
# normalize, lookup returns None, or any error fires.
_DEFAULT_PAYLOAD: dict[str, Any] = {
    "nadac_per_unit": None,
    "wac_per_unit": None,
    "awp_per_unit": None,
    "awp_basis": "NONE",
}


_ENV_ENABLED = "FDB_PRICING_ENRICHMENT_ENABLED"


def _is_enabled() -> bool:
    """True iff `FDB_PRICING_ENRICHMENT_ENABLED` env var is truthy.

    Truthy: "1", "true", "yes", "on" (case-insensitive). Anything else
    (including unset) â†’ False. Default off so existing deployments are
    unchanged until operators opt in.
    """
    raw = os.environ.get(_ENV_ENABLED, "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _parse_dos(raw: str) -> date | None:
    """Parse NCPDP CCYYMMDD date string â†’ date. Returns None on malformed input.

    NCPDP wire format is fixed-width CCYYMMDD (e.g. "20260506"). Some
    test fixtures or upstream parsers may pass ISO format; tolerate
    both. None for anything else (silent-fallback per Â§3.9.4).
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# Process-local composite singleton; constructed on first use when the
# env flag is on. None when disabled or import fails (in which case the
# helper falls back to defaults silently).
_composite_cached: Any = None
_composite_attempted: bool = False


def _get_composite() -> Any:
    """Lazily construct CompositePricingLookup. Returns None on any failure."""
    global _composite_cached, _composite_attempted
    if _composite_attempted:
        return _composite_cached
    _composite_attempted = True
    try:
        # Local imports â€” drug-database modules live on the same Python
        # path. Imports are deferred so adjudication-engine doesn't pay
        # the import cost when enrichment is disabled.
        from sqlalchemy import create_engine  # noqa: PLC0415
        from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

        from drug_database.services.composite_pricing import (  # noqa: PLC0415
            CompositePricingLookup,
        )
        from drug_database.services.fdb_pricing import (  # noqa: PLC0415
            FDBPricingLookup,
        )
        from drug_database.services.pricing import (  # noqa: PLC0415
            NadacPricingLookup,
        )

        db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get(
            "DATABASE_URL", ""
        )
        if not db_url:
            logger.warning(
                "pricing_enrichment_db_url_missing",
                extra={"pricing_env_flag": _ENV_ENABLED},
            )
            return None
        # async driver doesn't work for sync SQLAlchemy
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(db_url, pool_pre_ping=True)
        session_local = sessionmaker(
            bind=engine, autocommit=False, autoflush=False,
        )

        def nadac_factory() -> Any:
            return NadacPricingLookup(session=session_local())

        def fdb_factory() -> Any:
            return FDBPricingLookup(session=session_local())

        _composite_cached = CompositePricingLookup(
            nadac_factory=nadac_factory, fdb_factory=fdb_factory,
        )
        return _composite_cached
    except Exception as e:  # noqa: BLE001 â€” broad: silent-fallback rule
        logger.warning(
            "pricing_enrichment_init_failed",
            extra={
                "pricing_error_type": type(e).__name__,
                "pricing_error_message": str(e),
            },
        )
        _composite_cached = None
        return None


async def enrich_pricing(
    ndc: str,
    date_of_service: str,
    knowledge_date: date | None = None,
) -> dict[str, Any]:
    """Resolve FDB + NADAC pricing â†’ 4-field payload dict.

    Returns:
        {"nadac_per_unit": str | None, "wac_per_unit": str | None,
         "awp_per_unit":   str | None, "awp_basis": "FDB_SWP" | ... | "NONE"}

    Decimal values are serialized as strings (financial-precision.md).
    On any failure or when the env flag is off, the default dict is
    returned â€” caller should treat that as "no pricing data" and emit
    the event normally.
    """
    if not _is_enabled():
        return dict(_DEFAULT_PAYLOAD)

    composite = _get_composite()
    if composite is None:
        return dict(_DEFAULT_PAYLOAD)

    dos = _parse_dos(date_of_service)
    if dos is None:
        logger.warning(
            "pricing_enrichment_dos_unparseable",
            extra={"pricing_dos_raw": date_of_service[:32]},
        )
        return dict(_DEFAULT_PAYLOAD)

    if knowledge_date is None:
        knowledge_date = date.today()

    try:
        snap = await composite.lookup_at_dos(
            ndc, date_of_service=dos, knowledge_date=knowledge_date,
        )
    except Exception as e:  # noqa: BLE001 â€” silent-fallback rule Â§3.9.4
        logger.warning(
            "pricing_enrichment_lookup_failed",
            extra={
                "pricing_ndc": ndc[:32],
                "pricing_error_type": type(e).__name__,
                "pricing_error_message": str(e)[:200],
            },
        )
        return dict(_DEFAULT_PAYLOAD)

    if snap is None:
        return dict(_DEFAULT_PAYLOAD)

    return {
        "nadac_per_unit": (
            str(snap.nadac_per_unit) if snap.nadac_per_unit is not None else None
        ),
        "wac_per_unit": (
            str(snap.wac_per_unit) if snap.wac_per_unit is not None else None
        ),
        "awp_per_unit": (
            str(snap.awp_per_unit) if snap.awp_per_unit is not None else None
        ),
        "awp_basis": snap.awp_basis,
    }


def reset_for_tests() -> None:
    """Drop the cached composite so tests can re-init with fresh env vars.

    Tests that toggle FDB_PRICING_ENRICHMENT_ENABLED need to invalidate
    the singleton between cases.
    """
    global _composite_cached, _composite_attempted
    _composite_cached = None
    _composite_attempted = False


__all__ = ["enrich_pricing", "reset_for_tests"]

codex
## ADVERSARIAL VERDICT

HIGH-SEVERITY OBJECTIONS PRESENT

## Attack findings

| # | Attack | Severity | Finding | Plan addresses? | Mitigation needed |
|---|---|---:|---|---|---|
| 1 | Session size | M | “Next absorbs overflow” is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
| 2 | Migration | M | Postgres transactional DDL reduces half-applied risk, but 113-table migration failure still creates a large debug blast radius. Reverse/apply gate happens after implementation, not before merge pressure. | PARTIAL | Require generated migration dry-run on disposable DB before commit; capture `alembic upgrade + downgrade + upgrade` evidence per migration before mini-GATE. |
| 3 | FDW manifest | M | Additive manifest edits across sessions can conflict, and current `setup_fdw.sh --verify` hard-codes `expected 66`, so B9.B verify will fail unless this is changed. | PARTIAL | Make manifest generated or sorted deterministically; replace hard-coded 66 with an expected-count argument or manifest-derived count. |
| 4 | Idempotency | H | `ON CONFLICT DO NOTHING` preserves the oldest row for mutable lookup tables. A D then later A with changed values can be silently ignored if the conflict key is natural key only. | NO | Define per-table delta semantics: append-only, upsert/update, delete tombstone, or truncate+reload. Contract tests must simulate A/C/D/re-A with changed values. |
| 5 | MTL guard | H | Loader exclusion does not prevent direct SQL writes. Future code can insert into MTL tables and all current guards still pass until default loader runs. | PARTIAL | Add DB-level guard: revoke writer grants on MTL tables by default, or enforce trigger/check policy tied to an explicit session setting. |
| 6 | B9.E RNDC14 | M | Two sessions is fragile. Five type issues in 68 columns will likely require another model/migration/test pass. | PARTIAL | Add explicit “RNDC14 iteration allowed” rule: B9.E cannot close until all column issues converge, and session count may expand without borrowing from B9.F. |
| 7 | B9.F perf gate | H | Timing gate says FDW verify must complete within 5 min, but only storage has abort/escalate language. A 20-min verify could be “documented” and still pass. | PARTIAL | Add hard timing abort: if verify or weekly delta exceeds threshold, B9.F fails and requires index/query redesign before B9.G opens. |
| 8 | B9.G MTL FDW | H | Empty MTL foreign tables create a silent false-negative surface. A downstream join to MTL returns no rows instead of erroring. | NO | Do not expose MTL via FDW by default, or expose guarded views that raise/flag when `fdb_load_mtl=False`; update FDW count accordingly if excluded. |
| 9 | Calendar slip | M | Charter admits 4-5 months, but plan still gates as one large B9. Overruns can freeze visible delivery for months. | PARTIAL | Add calendar checkpoint every 4 weeks with scope/split decision; allow B9.B/B9.C shipped milestone tags even under single B9 label. |
| 10 | Codex cadence | M | 12 consults depend on network and token budget. Past SPEC R2 already saw connectivity fragility. | PARTIAL | Add offline fallback: local checklist reviewer path, retry budget, and explicit “consult unavailable” escalation rule. |
| 11 | `infinityrx_reference` write path | H | `scripts/load_fdb.py` falls back from `DATABASE_URL_SYNC_REFERENCE` to `DATABASE_URL_SYNC` to `DATABASE_URL`. That can write FDB into env DB by accident. | PARTIAL | For B9 loaders, require reference-only URL and assert database name/role before write; remove fallback or make fallback dry-run only. |
| 12 | Existing 3-table coverage | M | The registry expansion could reprocess RNP3/RPRDPTD0/RNPTYPD0, change modes, or duplicate existing TableSpecs. | PARTIAL | Add compatibility tests proving existing Phase 09 modes, row counts, price lookup behavior, and `fdb_price_type_desc` synthesis are unchanged. |
| 13 | Test baseline | M | Freezing “134 failures” is brittle if failures are flaky. Phase gates can fail or pass due to noise unrelated to B9. | PARTIAL | Freeze exact node IDs plus two baseline runs; quarantine known flaky IDs or require delta analysis by failed node, not raw count only. |
| 14 | Adjudication ripple | H | Plan does not audit consumer queries. Adding 217 tables may not change paths directly, but new FDW names and pricing tables can alter assumptions, imports, or fallback behavior. | NO | Add consumer audit in B9.H or earlier: adjudication pricing enrichment, TCP publish path, and FDW query smoke tests with B9 data present. |
| 15 | ReclaimRx pricing protocol | H | B9.F changes pricing data availability, but plan does not trace whether `awp_basis` distribution changes or whether guards still reject literal-AWP contracts correctly. | NO | Add reclaimrx protocol tests using populated RNP2/RPRDPP0/RNP3 combinations; assert no new basis value and no literal-AWP bypass. |
| 16 | Memory consistency | L | Long wave plus per-phase memory updates can contradict earlier state. This is a coordination risk, not an execution blocker. | PARTIAL | Add single B9 status ledger as source of truth; memory entries link to it rather than restating mutable facts. |

## Novel attacks

| Attack | Severity | Finding | Mitigation needed |
|---|---:|---|---|
| FDW name collision | H | `setup_fdw.sh` imports all source schemas into one `reference` schema. 217 new FDB names could collide with existing reference table names or future schemas; the script fatals on collision. | Preflight generated B9 table names against all reference schemas before B9.B implementation starts. |
| Manifest semantics drift | M | Current manifest comments say only tables with `>0 rows` are included. B9.G adds empty MTL tables, contradicting the manifest contract. | Update manifest policy explicitly before adding MTL, or keep schema-only tables in a separate FDW schema/manifest. |
| SQLite/test scaling | M | Recon warned 219-table `create_all()` can slow tests. Plan does not preserve base-splitting; 217 model imports can make unrelated tests pay the cost. | Require module-level declarative bases or targeted metadata creation before adding mass models. |
| Field-count skip false pass | H | `parse_table` logs and skips field-count/coercion errors. Row-count reconciliation catches totals, but small tolerance can mask systematic skipped rows on large tables. | Any parse warning for a B9 table should fail the contract test unless explicitly allowlisted with count impact. |

## Strongest single objection

The idempotency story is not executable for 217 heterogeneous tables. The plan repeatedly says `ON CONFLICT DO NOTHING` and “weekly re-run produces 0 new rows,” but that only proves replay safety, not correctness of FDB delta semantics. For mutable reference tables, “do nothing” can preserve stale descriptions, resurrected rows, deleted rows, or old effective values. This can pass row-count checks and still serve wrong reference data.

## Final verdict + next action

Do not fully lock execution yet. PLAN v3 needs targeted mitigations for: per-table delta semantics, reference-DB write-path enforcement, MTL FDW silent-failure prevention, B9.F timing abort criteria, consumer-side adjudication/reclaimrx audits, and current FDW manifest/script hard-coded count drift. After those are added, B9.A can close and B9.B can open with far less hidden failure surface.
tokens used
78,242
## ADVERSARIAL VERDICT

HIGH-SEVERITY OBJECTIONS PRESENT

## Attack findings

| # | Attack | Severity | Finding | Plan addresses? | Mitigation needed |
|---|---|---:|---|---|---|
| 1 | Session size | M | “Next absorbs overflow” is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
| 2 | Migration | M | Postgres transactional DDL reduces half-applied risk, but 113-table migration failure still creates a large debug blast radius. Reverse/apply gate happens after implementation, not before merge pressure. | PARTIAL | Require generated migration dry-run on disposable DB before commit; capture `alembic upgrade + downgrade + upgrade` evidence per migration before mini-GATE. |
| 3 | FDW manifest | M | Additive manifest edits across sessions can conflict, and current `setup_fdw.sh --verify` hard-codes `expected 66`, so B9.B verify will fail unless this is changed. | PARTIAL | Make manifest generated or sorted deterministically; replace hard-coded 66 with an expected-count argument or manifest-derived count. |
| 4 | Idempotency | H | `ON CONFLICT DO NOTHING` preserves the oldest row for mutable lookup tables. A D then later A with changed values can be silently ignored if the conflict key is natural key only. | NO | Define per-table delta semantics: append-only, upsert/update, delete tombstone, or truncate+reload. Contract tests must simulate A/C/D/re-A with changed values. |
| 5 | MTL guard | H | Loader exclusion does not prevent direct SQL writes. Future code can insert into MTL tables and all current guards still pass until default loader runs. | PARTIAL | Add DB-level guard: revoke writer grants on MTL tables by default, or enforce trigger/check policy tied to an explicit session setting. |
| 6 | B9.E RNDC14 | M | Two sessions is fragile. Five type issues in 68 columns will likely require another model/migration/test pass. | PARTIAL | Add explicit “RNDC14 iteration allowed” rule: B9.E cannot close until all column issues converge, and session count may expand without borrowing from B9.F. |
| 7 | B9.F perf gate | H | Timing gate says FDW verify must complete within 5 min, but only storage has abort/escalate language. A 20-min verify could be “documented” and still pass. | PARTIAL | Add hard timing abort: if verify or weekly delta exceeds threshold, B9.F fails and requires index/query redesign before B9.G opens. |
| 8 | B9.G MTL FDW | H | Empty MTL foreign tables create a silent false-negative surface. A downstream join to MTL returns no rows instead of erroring. | NO | Do not expose MTL via FDW by default, or expose guarded views that raise/flag when `fdb_load_mtl=False`; update FDW count accordingly if excluded. |
| 9 | Calendar slip | M | Charter admits 4-5 months, but plan still gates as one large B9. Overruns can freeze visible delivery for months. | PARTIAL | Add calendar checkpoint every 4 weeks with scope/split decision; allow B9.B/B9.C shipped milestone tags even under single B9 label. |
| 10 | Codex cadence | M | 12 consults depend on network and token budget. Past SPEC R2 already saw connectivity fragility. | PARTIAL | Add offline fallback: local checklist reviewer path, retry budget, and explicit “consult unavailable” escalation rule. |
| 11 | `infinityrx_reference` write path | H | `scripts/load_fdb.py` falls back from `DATABASE_URL_SYNC_REFERENCE` to `DATABASE_URL_SYNC` to `DATABASE_URL`. That can write FDB into env DB by accident. | PARTIAL | For B9 loaders, require reference-only URL and assert database name/role before write; remove fallback or make fallback dry-run only. |
| 12 | Existing 3-table coverage | M | The registry expansion could reprocess RNP3/RPRDPTD0/RNPTYPD0, change modes, or duplicate existing TableSpecs. | PARTIAL | Add compatibility tests proving existing Phase 09 modes, row counts, price lookup behavior, and `fdb_price_type_desc` synthesis are unchanged. |
| 13 | Test baseline | M | Freezing “134 failures” is brittle if failures are flaky. Phase gates can fail or pass due to noise unrelated to B9. | PARTIAL | Freeze exact node IDs plus two baseline runs; quarantine known flaky IDs or require delta analysis by failed node, not raw count only. |
| 14 | Adjudication ripple | H | Plan does not audit consumer queries. Adding 217 tables may not change paths directly, but new FDW names and pricing tables can alter assumptions, imports, or fallback behavior. | NO | Add consumer audit in B9.H or earlier: adjudication pricing enrichment, TCP publish path, and FDW query smoke tests with B9 data present. |
| 15 | ReclaimRx pricing protocol | H | B9.F changes pricing data availability, but plan does not trace whether `awp_basis` distribution changes or whether guards still reject literal-AWP contracts correctly. | NO | Add reclaimrx protocol tests using populated RNP2/RPRDPP0/RNP3 combinations; assert no new basis value and no literal-AWP bypass. |
| 16 | Memory consistency | L | Long wave plus per-phase memory updates can contradict earlier state. This is a coordination risk, not an execution blocker. | PARTIAL | Add single B9 status ledger as source of truth; memory entries link to it rather than restating mutable facts. |

## Novel attacks

| Attack | Severity | Finding | Mitigation needed |
|---|---:|---|---|
| FDW name collision | H | `setup_fdw.sh` imports all source schemas into one `reference` schema. 217 new FDB names could collide with existing reference table names or future schemas; the script fatals on collision. | Preflight generated B9 table names against all reference schemas before B9.B implementation starts. |
| Manifest semantics drift | M | Current manifest comments say only tables with `>0 rows` are included. B9.G adds empty MTL tables, contradicting the manifest contract. | Update manifest policy explicitly before adding MTL, or keep schema-only tables in a separate FDW schema/manifest. |
| SQLite/test scaling | M | Recon warned 219-table `create_all()` can slow tests. Plan does not preserve base-splitting; 217 model imports can make unrelated tests pay the cost. | Require module-level declarative bases or targeted metadata creation before adding mass models. |
| Field-count skip false pass | H | `parse_table` logs and skips field-count/coercion errors. Row-count reconciliation catches totals, but small tolerance can mask systematic skipped rows on large tables. | Any parse warning for a B9 table should fail the contract test unless explicitly allowlisted with count impact. |

## Strongest single objection

The idempotency story is not executable for 217 heterogeneous tables. The plan repeatedly says `ON CONFLICT DO NOTHING` and “weekly re-run produces 0 new rows,” but that only proves replay safety, not correctness of FDB delta semantics. For mutable reference tables, “do nothing” can preserve stale descriptions, resurrected rows, deleted rows, or old effective values. This can pass row-count checks and still serve wrong reference data.

## Final verdict + next action

Do not fully lock execution yet. PLAN v3 needs targeted mitigations for: per-table delta semantics, reference-DB write-path enforcement, MTL FDW silent-failure prevention, B9.F timing abort criteria, consumer-side adjudication/reclaimrx audits, and current FDW manifest/script hard-coded count drift. After those are added, B9.A can close and B9.B can open with far less hidden failure surface.
