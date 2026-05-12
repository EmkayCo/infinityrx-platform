# Wave B9 — FDB NDDF Plus 220-table extension (full scope)

**Status:** SPEC v3.2 LOCKED — erratum chain: (v3.1) arithmetic drift correction surfaced by codex PLAN R2 → B9.B FDW `116/116`→`179/179`, B9.D "17 complex"→"16 complex"; (v3.2) MTL FDW-exposure policy surfaced by codex ADVERSARIAL R1 → MTL excluded from default FDW manifest to prevent silent false-negative joins, conditional 19 entries added only when `fdb_load_mtl=True` (future MTL activation wave). B9.H final FDW count: **264/264 default, 283/283 conditional**. No scope change. See `codex-plan-consult-r2.md` and `codex-adversarial-r1.md`. Ready for PLAN v3 → ADVERSARIAL R2.
**Recon:** `recon.md` (2026-05-11) — verified scope and effort
**Predecessor:** Phase 09 FDB pricing ingester (3 tables); Phase 11A reference DB topology; B7.2 architectural cleanup
**Authority:** Project owner locked 4 scope decisions 2026-05-11 (this document captures them)

---

## Goal

Extend FDB NDDF Plus ingest from current **3 tables → all 220 tables** (217-table gap). Adjudication, formulary, reclaimrx, and future Phase 4 modules gain full FDB reference coverage. Single B9 wave milestone; multi-session execution.

## Locked decisions (2026-05-11)

| # | Decision | Rationale |
|---|---|---|
| D1 | **RNDC14 = full 68-column ingest** | Future-proof; avoids N+1 schema-extension waves as consumers surface column needs. |
| D2 | **RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE = include + load by default** | Reverses Phase 09 `fdb_load_product_prices=False` deferral. +1.16 GB storage required; needs disk + Postgres performance verification at C0. |
| D3 | **Medical Test Lexicon (MTL) = schema-only, no data load** | Honors "clinical screening NOT subscribed" memory while landing table structure for future activation. 19 tables, 103 KB raw. If licensing changes, flip a config flag. |
| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4–5 months with multitasking. |

## Workstreams (recon-validated effort)

| W | Scope | Tables | Effort (recon line 14 + sections 6/7) |
|---|---|---|---|
| W1 | Tier A — simple lookups (≤5 columns, generic ingester) | 113 | ~10 sessions |
| W2 | Tier B — NDC/GCN-keyed joins | 66 | ~12 sessions |
| W3 | Tier C — complex/large + RNDC14 full + RNP2 + RPRDPP0 + perf gate | 19 | ~10 sessions (8 baseline + ~2 D2 perf gate) |
| W4 | Tier D — MTL schema-only (no data load) | 19 | ~3 sessions |
| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |

**Total: ~39 sessions** (recon's A+B+C estimate is 34; +3 Tier D + ~2 D2 perf gate = 39). With codex review cadence already baked into per-phase budget. **Charter v1's 100-session figure was a misread; v2 corrects to recon's actual numbers.** Wall-clock at 3 sessions/week: ~13 weeks (~3 months).

## Out of scope (deferred)

- Clinical screening DATA ingest (only schema lands per D3)
- B8.2 followups (build_response docstring already shipped `1c28e44`)
- 134 pre-existing test failures (forensic wave)
- Phase 4 forward feature work

## Phased execution + per-phase closure gates (HIGH #1 codex fix)

B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.

| Phase | Sub-scope | Sessions | Closure gate |
|---|---|---|---|
| B9.A | Charter v2 + plan v1 + codex SPEC R2 / PLAN / ADVERSARIAL | 2-3 | Plan v1 locked |
| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 179/179 + ingester contract tests |
| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests (FDW 245/245) |
| B9.D | Tier C non-RNDC14 — 16 complex tables | 4 | **B9.D mini-GATE-CLOSE** (FDW 261/261) |
| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** — column-by-column model review |
| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** — perf test results + EXPLAIN ANALYZE + storage budget verification |
| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** — integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
| B9.H | Manifest extension (66 → 264 FDW entries default; +19 conditional MTL) + consumer audits + final closeout artifacts | 5 | **Final B9 GATE-CLOSE** — full cross-tier consult |

## Success criteria

| SC | Description |
|---|---|
| SC-1 | All 217 currently-missing FDB tables have SQLAlchemy models + alembic migrations + ingester support |
| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
| SC-5 | MTL schema lands but **runtime/loader guards** prevent data load: `fdb_load_mtl=False` default; MTL tables excluded from default loader registry; integration test asserts **zero MTL rows** after default `load_fdb.py --mode fdb_weekly`. Alembic migration itself is NOT config-gated (per codex SPEC R1 #4). |
| SC-6 | `setup_fdw.sh --verify` 264/264 PASS in both env DBs by default (MTL excluded from FDW per ADVERSARIAL R1 mitigation); conditional 283/283 when `fdb_load_mtl=True` |
| SC-7 | Weekly delta ingest path idempotent across all 220 tables (ON CONFLICT DO NOTHING or UPSERT per table; verified by re-running) |
| SC-8 | **Test coverage strategy** (per codex SPEC R1 #6): contract coverage for every `TableSpec`; schema/model parity for every table; row-count reconciliation for every loaded table; sampled behavioral tests per tier; dedicated Tier C tests for RNDC14 / RNP2 / RPRDPP0 / weekly delta. **No bespoke per-table behavioral tests** for the 217 tables — too heavy. |
| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
| SC-10 | Final B9 GATE-CLOSE GO or GO-WITH-FIXES |
| SC-11 | Evidence + ship + memory + wave-history + B9 phased-progress dashboard |

## SPEC-locked migration granularity (codex SPEC R1 #5 fix)

**Migration granularity is SPEC-locked**, not deferred to plan:
- **NO** one-table-per-migration (213 migrations would be unmaintainable)
- **NO** single 217-table migration (atomicity ruined; review intractable)
- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE

## Risks

| # | Risk | Mit |
|---|---|---|
| R1 | 217 alembic migrations is unwieldy for review | SPEC-locked above to ~6 per-phase batched migrations + RNDC14 standalone. |
| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
| R3 | RNDC14 68 columns include latin-1 quirks (mixed-case names, accented chars, NULL sentinels) | Per-column normalization pass in ingester; latin-1 → UTF-8 with replacement strategy documented |
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

**~39 sessions × 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong — corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)

## Note on scope vs recon recommendation

The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.

---

## Resume next session

1. `/werkbench`
2. Read this charter
3. Codex SPEC consult round 1 (against this v1)
4. Iterate to GO; then plan v1
