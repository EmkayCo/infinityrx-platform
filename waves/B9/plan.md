# Wave B9 — Execution Plan v3.1

**Status:** PLAN v3.1 LOCKED — **ADVERSARIAL GATE FINAL VERDICT: GO** (`codex-adversarial-r2.md` tail). B9.A meta-phase gate cycle CLOSED. Ready for B9.A C0-C14 execution, then B9.B opens (Tier A — 113 simple lookups via generic table-driven ingester).

**Iteration history:** PLAN v1 → PLAN R1 GO-WITH-FIXES (8 fixes) → PLAN v2 → PLAN R2 GO-WITH-FIXES (charter v3.1 erratum) → PLAN GATE FINAL VERDICT GO → ADVERSARIAL R1 HIGH-SEVERITY OBJECTIONS PRESENT (9 HIGH + 11 MED + 4 novel) → PLAN v3 (all mitigations folded) → charter v3.2 erratum (MTL FDW exposure) → ADVERSARIAL R2 GO-WITH-FIXES (one stale line) → PLAN v3.1 (narrow fix) → ADVERSARIAL R3 first ping (caught one more stale FDW reference) → cleanup → ADVERSARIAL R3 second ping **GO**.
**Predecessor:** `charter.md` v3 LOCKED (SPEC R2 GO-WITH-FIXES, stale D4 row corrected).
**Recon ground truth:** `recon.md` (2026-05-11) — 217 gap tables, 6 FDB modules, 4 effort tiers.
**Scope:** All 217 currently-missing FDB NDDF Plus tables (3 already covered) reach the platform as ingested or schema-only across phases B9.A → B9.H.

---

## How to read this plan

PLAN v1 is the WHEN/HOW that bridges charter v3 (WHAT) to executable commits. It locks:

1. **Cross-cutting infrastructure** all phases depend on (B9.A deliverables).
2. **Per-phase scope, deliverables, success-criteria mapping, gate criteria, est sessions, commit shape** for B9.B..B9.H.
3. **Per-phase batched migration plan** (SPEC-locked at charter v3 §SPEC-locked migration granularity).
4. **D2 perf gate** specifics (charter SC-4).
5. **MTL loader/runtime guards** (charter SC-5; Alembic NOT config-gated).
6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
7. **Threat model + risks** synthesised from recon §7 and charter §risks.

What PLAN v1 deliberately does NOT lock:

- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
- The exact `RECORD_COUNTS.TXT` tolerance numbers (per-table; published in each phase evidence doc).
- The text of each ingester contract test (template-driven; B9.A produces the template).

---

## ADVERSARIAL R1 mitigations folded in (all 9 HIGH + 11 MEDIUM + 4 novel)

Each codex ADVERSARIAL R1 attack with its plan v3 response. Maps to threats T13-T32 below.

| Attack | Sev | Codex finding (summary) | PLAN v3 mitigation |
|---|---|---|---|
| A4 idempotency | H | `ON CONFLICT DO NOTHING` proves replay safety, not delta correctness — mutable lookups silently serve stale data | New `DELTA_SEMANTICS` field on every `TableSpec` (values: APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD). B9.A C8 contract test simulates A/C/D/re-A scenarios per table per delta type. See T13. |
| A5 MTL guard | H | Loader exclusion can be bypassed by direct INSERT | B9.G adds DB-level guard: `REVOKE INSERT/UPDATE/DELETE ON ALL TABLES IN SCHEMA drug_database TO ifx_dev_app, ifx_mock_app` for MTL-prefixed tables; only `ifx_reference_writer` retains write. See T14. |
| A7 perf gate | H | "Documented" without abort | B9.F hard timing aborts: FDW verify > 5 min → FAIL; per-table weekly delta > 30s → FAIL; total weekly delta > 10 min → FAIL. Charter SC-4 wording strengthened in plan §B9.F. See T15. |
| A8 MTL FDW silent | H | Empty FDW foreign tables = silent false-negative joins | MTL excluded from default FDW manifest (charter v3.2 erratum: 264 default / 283 conditional). MTL data activation work — including the +19 FDW entries — moves to a future wave when licensing flips. See T16. |
| A11 write path | H | `load_fdb.py` URL fallback can write FDB to env DB | B9.A C9 invariant + script change: B9 FDB loaders require explicit `DATABASE_URL_SYNC_REFERENCE`; no fallback; assert `current_database()` is `infinityrx_reference` before any write. See T17. |
| A14 adjudication ripple | H | Consumer audit missing | B9.H Session 3 adds adjudication audit: pricing-enrichment path with B9 data present; TCP listener publish smoke; FDW query smoke with new tables. See T18. |
| A15 reclaimrx pricing | H | B9.F changes `awp_basis` data; reclaimrx guards untested | B9.F Session 4 adds reclaimrx-protocol tests with populated RNP2 + RPRDPP0 + RNP3; asserts no new basis values; literal-AWP guards still reject correctly. See T19. |
| N1 FDW name collision | H | `setup_fdw.sh` fatals on duplicate; no preflight | B9.A C10 preflight: generate all 217 B9 table names; scan `infinityrx_reference` schemas (drug_database / drug_db / reference / shared) for collisions; abort if any. See T20. |
| N4 parse_table skip | H | Parser silently skips field-count errors | Contract test policy: ANY `parse_table` warning fails the contract unless explicitly allowlisted in `waves/B9/parse_warning_allowlist.md` with documented count-impact. B9.A C3 template enforces. See T21. |
| A1 session overflow | M | "Next absorbs overflow" not a control | Per-table escape-hatch: any Tier A table that consumes > 1 hour solo gets reclassified to Tier B/C; removed from `0009_fdb_tier_a.py`; FDW ladder updated; mini-re-plan triggered if session burn > +20%. See T22. |
| A2 migration blast radius | M | 113-table migration failure = wide blast | Each migration requires `alembic upgrade + downgrade + upgrade` evidence captured on a disposable DB before commit; mini-GATE-CLOSE checks evidence file exists. See T23. |
| A3 FDW manifest | M | Hard-coded "expected 66"; concurrent-edit conflicts | B9.A C11 replaces hard-coded 66 in `setup_fdw.sh --verify` with manifest-derived count; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is the source of truth. See T24. |
| A6 RNDC14 iteration | M | 2 sessions fragile if 5+ type issues | B9.E iteration rule: sessions may expand from 2 → up to 4 without borrowing from B9.F budget; mini-GATE-CLOSE will not close on partial column review. See T25. |
| A9 calendar slip | M | 4-5 months freeze of visible delivery | 4-week calendar checkpoint: at week-4 / week-8 / week-12 owner reviews B9.X.* progress + decides whether to ship intermediate milestone tags (B9.B-shipped, B9.C-shipped) under the single B9 label. See T26. |
| A10 codex cadence | M | Network/budget fragility (SPEC R2 hit it once) | Offline fallback: per gate has a local-checklist reviewer path (see `waves/B9/local_review_checklists/`); retry budget = 3 attempts per consult; if 3 retries fail → escalate to owner. See T27. |
| A12 Phase 09 compat | M | Existing 3-table coverage might break | B9.A C12 captures Phase 09 baseline: row counts for `fdb_ndc_price_history` + `fdb_price_type_desc`, query latency on representative NDC + price_type lookups, default-mode behavior. Mini-GATE-CLOSE re-runs and asserts unchanged. See T28. |
| A13 flaky test baseline | M | 134-failure count is noisy if flakes exist | B9.A C0 captures TWO test snapshots: collection node-ID list + failing node-ID list (NOT raw counts). Mini-GATE-CLOSE asserts node-ID DELTA, not count delta; known flakes go in `waves/B9/test_flake_quarantine.md`. See T29. |
| A16 memory consistency | M | 13-week wave + memory churn → contradictions | Single `waves/B9/status.md` ledger as source of truth. Memory entries reference this ledger; do not restate mutable facts. See T30. |
| N2 manifest semantics | M | `>0 rows` policy contradicts B9.G empty MTL | Resolved by A8 mitigation (MTL not in default FDW). Document the policy explicitly in `infrastructure/scripts/lib/expected_reference_tables.txt` header. See T31. |
| N3 model-import test cost | M | 217 models in one base slow unrelated tests | B9.A C13 designs module-level declarative bases or targeted metadata creation; profile B9.A before/after with a representative test subset. See T32. |

---

## Pre-execute invariants (must hold before B9.A C0)

Before any B9 commit lands:

1. **B8.2 closure absorbed** — `1c28e44` build_response docstring shipped on develop. (Memory `project_phase11b_implemented.md`.)
2. **B7.2 Phase 11A COMPLETE** — `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
4. **Disk budget verified** — `df -h` shows ≥ 5 GB free on the reference DB volume to absorb D2's +1.16 GB (RNP2 + RPRDPP0) plus indexes plus working space. Captured at B9.A C0.
5. **`fdb_load_product_prices` config flag still in code** — Phase 09 deferral flag location identified; B9.F will flip default to `True` and document.
6. **134 pre-existing test failures baseline frozen** — at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged ± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
7. **FDB drop manifest reachable** — `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon §1.5 verified — re-verify at C0).
8. **`charter.md` v3 + `recon.md` checked into Werkbench/projects/infinityrx-platform/waves/B9/** at the moment B9.A starts (commit reference required in B9.A C0 evidence).
9. **Codex consult ledger ready** — `codex-plan-consult-r1.md` slot reserved; `codex-adversarial-r1.md` slot reserved.

If any invariant fails, B9.A C0 stops and reports — do not paper over.

---

## Phased commit chain

B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).

### B9.A — Charter v3 close + Plan v1 close + infrastructure scaffolding (2-3 sessions)

**Scope:** This meta-phase. Lock charter v3 (DONE), draft PLAN v1 (DONE — this doc), pass codex PLAN consult, pass codex ADVERSARIAL consult, and ship the cross-cutting infrastructure all subsequent phases consume.

**Cross-cutting infrastructure delivered in B9.A (NOT per-tier):**

- **`TableSpec` registry expansion path** — adds a `TIER`, `RECORD_COUNTS_KEY`, and `LOADER_GROUP` field to existing `TableSpec` so generic ingester can: (a) tier-filter, (b) row-count reconcile, (c) loader-register by tier. Backward-compatible default values mean existing FDB pricing TableSpecs still work.
- **Generated migration template** — script in `modules/drug-database/scripts/gen_fdb_tier_migration.py` consumes a `TableSpec` list + tier label and emits an idempotent Alembic migration file. Single-tier batched migrations are produced by this template (charter §SPEC-locked migration granularity).
- **Ingester contract test template** — `modules/drug-database/tests/_fdb_contract.py` reusable test pattern: schema-parity assertion, latin-1 decode smoke, row-count reconciliation skeleton, ON CONFLICT idempotency. Each phase wires concrete `TableSpec` lists into this template.
- **MTL loader guard** — `fdb_load_mtl=False` config flag added to settings; loader registry default-excludes MTL; integration test `test_fdb_mtl_zero_rows_under_default` asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly`. Test added in B9.A so it stays green through every later phase (no MTL data loads exist yet, so the assertion is trivial-true until B9.G; the test stays present after B9.G).
- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder (charter v3.2 + ADVERSARIAL A8 mitigation): **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 264 (after B9.G — MTL schema lands but is EXCLUDED from default FDW manifest to prevent silent false-negative joins)**. B9.H final verify: **264/264 default**; conditional 283/283 only if `fdb_load_mtl=True` (future MTL activation wave adds the +19 FDW entries together with data load + grant flip). MTL contributes 0 default FDW entries.
- **pytest baseline markers** — committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.

**B9.A commits (expanded for ADVERSARIAL mitigations):**

| C | Scope | Files touched |
|---|---|---|
| C0 | Baseline + invariants captured (df, pg_authid, FDW 66/66, pytest node-ID snapshots × 2 runs for flake detection) | `waves/B9/baseline.md`, `waves/B9/test_flake_quarantine.md` |
| C1 | `TableSpec` registry expansion + new `DELTA_SEMANTICS` field (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD) | `modules/drug-database/src/.../fdb/specs.py`, unit tests |
| C2 | Generated migration template (with `alembic upgrade + downgrade + upgrade` dry-run evidence capture) | `modules/drug-database/scripts/gen_fdb_tier_migration.py` |
| C3 | Ingester contract test template (parity + decode + count + idempotency + **A/C/D/re-A simulation** + parse-warning-fails-test policy) | `modules/drug-database/tests/_fdb_contract.py`, `waves/B9/parse_warning_allowlist.md` (empty initial) |
| C4 | MTL config flag + zero-row CI test + **DB-level guard (REVOKE writes from app roles on MTL tables)** | `shared/config/...`, MTL guard migration / GRANT script |
| C5 | Codex PLAN R1 consult dispatched, verdict captured | `waves/B9/codex-plan-consult-r1.md` |
| C6 | Codex ADVERSARIAL R1 consult dispatched, verdict captured | `waves/B9/codex-adversarial-r1.md` |
| C7 | Apply consult fixes; bump plan version; tag PLAN LOCKED | `plan.md` v-bump |
| **C8** | **`DELTA_SEMANTICS` contract test (per-table A/C/D/re-A simulation) — verifies delta correctness, not just replay safety** | `modules/drug-database/tests/_fdb_delta_semantics.py` |
| **C9** | **Reference-DB write-path enforcement: B9 FDB loaders require explicit `DATABASE_URL_SYNC_REFERENCE`; remove URL fallback; assert `current_database()=='infinityrx_reference'` before any write** | `scripts/load_fdb.py` (or B9 wrapper), `waves/B9/write_path_enforcement.md` |
| **C10** | **FDW name collision preflight — generate 217 B9 table names; scan all `infinityrx_reference` schemas; abort on any collision** | `infrastructure/scripts/preflight_b9_name_collision.py`, evidence |
| **C11** | **`setup_fdw.sh --verify` manifest-derived count (replace hard-coded `expected 66`) + deterministic sorted manifest ordering** | `infrastructure/scripts/setup_fdw.sh`, `infrastructure/scripts/lib/expected_reference_tables.txt` |
| **C12** | **Phase 09 compatibility baseline: capture RNP3 + RPRDPTD0 + RNPTYPD0 row counts + query latency + default-mode behavior; mini-GATE-CLOSE re-asserts unchanged at every phase** | `waves/B9/phase09_compat_baseline.md`, compat test |
| **C13** | **Module-level declarative base design / targeted metadata creation; profile B9.A test-suite with and without B9 models loaded** | `modules/drug-database/src/.../fdb/models/__init__.py`, profile evidence |
| **C14** | **`waves/B9/status.md` ledger created (single source of truth for wave progress); memory entries reference this, do not duplicate state** | `waves/B9/status.md` |

**B9.A mini-GATE-CLOSE criteria (charter SC-9, expanded for ADVERSARIAL):**

- All cross-cutting infra commits (C1-C4, C8-C14) unit-tested green.
- Pytest baselines captured: collection node-IDs + failing node-IDs (NOT raw counts); known flakes quarantined.
- `setup_fdw.sh --verify` still passes against current manifest-derived count (no FDB tables added yet; expected count == current count).
- Phase 09 compatibility baseline established and PASS-asserted.
- Write-path enforcement verified: attempting a fallback write FAILS LOUDLY.
- FDW name collision preflight returns 0 collisions for all 217 generated B9 names.
- DB-level MTL guard verified: app role INSERT into MTL table fails with permission error.
- Module-level base design profiled: B9-models-loaded vs not, delta documented.
- Codex PLAN R1 + R2 + ADVERSARIAL R1 + R2 verdicts all captured; all HIGH/MEDIUM objections addressed.
- Memory updated: `project_b9_plan_v3_locked.md`; `waves/B9/status.md` ledger initialized.

**B9.A revised session estimate:** 3 → 4 sessions (C8-C14 add ~1 session of infra work).

---

### B9.B — Tier A: 113 simple lookup tables (≤ 5 columns, generic ingester) (10 sessions)

**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier — short tables (mostly < 10K rows, all ≤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.

**Per-session shape (10 sessions = ~12 tables/session):**

- 12 new `TableSpec` definitions per session
- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon §4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
- 12 contract-test wirings per session (each table gets the parity + decode + count + idempotency test set)
- 1 partial loader registry update per session (incremental)

**Deliverables:**

- 113 SQLAlchemy models in `modules/drug-database/src/.../fdb/models/tier_a/`
- 113 `TableSpec` entries in `specs.py`
- 1 alembic migration (`0009_fdb_tier_a.py`)
- Contract test coverage = 113 tables (template-driven)
- Loader-orchestration entry: `--mode fdb_tier_a` loads only Tier A
- `setup_fdw.sh` foreign-table count: 66 → 179

**Success criteria (charter mapping):**

- SC-1 (217 tables have models + migrations + ingester) — partial: +113
- SC-2 (RECORD_COUNTS reconciliation) — every loaded Tier A table: actual ÷ expected within ±0.1% tolerance (small lookups should be exact)
- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
- SC-7 (weekly idempotency) — verified for Tier A only at B9.B mini-GATE-CLOSE
- SC-8 (test strategy) — contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
- SC-9 (mini-GATE-CLOSE) — see below

**B9.B mini-GATE-CLOSE criteria:**

- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` ± documented tolerance
- `setup_fdw.sh --verify` 179/179 PASS both env DBs
- All Tier A contract tests green
- Sampled behavioral tests: 10 randomly-picked Tier A tables exercise non-trivial query (FK join, where-clause, sort)
- Migration apply + reverse + apply: clean
- Weekly delta path: `load_fdb.py --mode fdb_tier_a` re-run produces 0 new rows (idempotent)
- `pytest --collect-only` count unchanged vs B9.A C0 baseline ± 113 new contract tests (counted in baseline)
- Codex mini-GATE-CLOSE consult: GO

**Risk:** 113 tables × ~12/session is aggressive. Mitigation: each session targets contiguous functional groups (e.g., all NDDF BASICS lookups one session; all ETC lookups another) to keep review cohesion. If a session lands fewer tables, the next absorbs the overflow — total session count flexes within the charter's 10-session band.

---

### B9.C — Tier B: 66 NDC/GCN-keyed joins (12 sessions)

**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.

**Per-session shape (12 sessions = ~5.5 tables/session — slower than Tier A because of join-design + FK-target verification per table):**

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
- FDW foreign-table count: 179 → 245

**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.

**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.

---

### B9.D — Tier C non-RNDC14: 16 complex/large tables (4 sessions)

**Scope:** All 19 Tier C tables EXCEPT the three special-handled ones (RNDC14, RNP2, RPRDPP0). That leaves **16 tables** (19 - 3 = 16). Complex tables here are > 8 columns or > 50 MB. Includes ETC master, product master (RPRD0_PRODUCT — load before RNDC14), GCN master, etc.

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
- FDW foreign-table count: 245 → **261**
- Tier C dedicated behavioral tests for the 3-4 highest-value tables (ETC master, RPRD0_PRODUCT)

**Success criteria:** SC-1 (partial: cum 195/217), SC-2, SC-6 (261/261), SC-7, SC-8 (dedicated Tier C tests), SC-9.

**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.

---

### B9.E — RNDC14 dedicated migration (2 sessions)

**Scope:** RNDC14_NDC_MSTR alone — the canonical FDB NDC master, 68 columns, 183 MB, ~501K rows. Highest single-table value in the wave.

**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).

**Per-session shape (2 sessions):**

- Session 1: SQLAlchemy model with all 68 columns, type-mapped (numeric → Decimal where money-relevant; integers where ID; text where descriptor); migration `0012_fdb_rndc14_ndc_mstr.py`; full contract test set
- Session 2: NDC normalization audit (handle 9/10/11-digit NDC inputs and store canonical 11-digit); behavioral tests (FK from existing tables that reference NDC); EXPLAIN ANALYZE runbook addition for high-volume NDC lookups against this table

**Deliverables:**

- 1 SQLAlchemy model (68 cols)
- 1 alembic migration (`0012_fdb_rndc14_ndc_mstr.py`)
- Contract test + behavioral test + EXPLAIN ANALYZE runbook entry
- `tier_c_curation.md` updated with RNDC14 entry (no columns dropped per D1)
- FDW foreign-table count: 261 → 262

**Success criteria:** SC-1 (cum 196/217), SC-3 (RNDC14 all 68 cols), SC-2, SC-6 (262/262), SC-7, SC-8 (dedicated RNDC14 tests), SC-9.

**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.

**B9.E iteration allowance (ADVERSARIAL A6 mitigation):** If column-by-column review surfaces 5+ type-correctness issues, sessions may expand from 2 → up to 4 WITHOUT borrowing from B9.F's budget. Mini-GATE-CLOSE will not close on partial column review. Charter `~39 sessions` budget absorbs up to 2 extra sessions here from W3's headroom.

---

### B9.F — RNP2 + RPRDPP0 + C0 perf gate (4 sessions)

**Scope:** The two large pricing tables explicitly deferred in Phase 09, reversed per charter D2. RNP2_NDC_PRICE (595 MB, 13.2M rows) and RPRDPP0_PRODUCT_PRICE (561 MB). +1.16 GB storage. Includes the **D2 performance gate** (charter SC-4) — not just disk verification.

**Per-session shape (4 sessions):**

- Session 1: SQLAlchemy models for RNP2 + RPRDPP0; migration `0013_fdb_pricing_big.py`; flip `fdb_load_product_prices=True` default
- Session 2: Timed full-load dry run for both tables; capture wall-clock + final row count + Postgres index build time; capture `df -h` before/after
- Session 3: EXPLAIN ANALYZE on representative query patterns — NDC + price_type + effective_date join, ROW_NUMBER OVER PARTITION BY pattern matching `fdb_ndc_price_history` pattern (re-use `docs/runbooks/fdb_lookup_perf.md` patterns); index design + creation
- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline; **reclaimrx pricing-protocol tests** (ADVERSARIAL A15): exercise `awp_basis` distribution with populated RNP2 + RPRDPP0 + RNP3; assert no new basis values appear; assert literal-AWP guards still reject correctly

**Deliverables:**

- 2 SQLAlchemy models (RNP2 + RPRDPP0)
- 1 alembic migration (`0013_fdb_pricing_big.py`)
- Contract tests + dedicated behavioral tests for both
- Performance evidence in `waves/B9/perf_b9f.md`: timed dry-run, EXPLAIN ANALYZE, storage delta, weekly delta timing
- Default flag flip: `fdb_load_product_prices=True`
- FDW foreign-table count: 262 → 264

**Success criteria:** SC-1 (cum 198/217), SC-4 (D2 perf gate met: timed dry-run + EXPLAIN ANALYZE + storage budget + weekly delta timing all documented), SC-2, SC-6 (264/264), SC-7, SC-8 (RNP2 + RPRDPP0 dedicated behavioral), SC-9.

**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4 + ADVERSARIAL A7 hard aborts:**

- Timed full-load wall-clock recorded for both tables (acceptance: documented)
- `EXPLAIN ANALYZE` output captured for at least 3 query patterns per table (NDC lookup, price_type filter, effective_date range)
- Storage delta vs. C0 baseline: **HARD ABORT if > +1.4 GB total** (1.16 GB raw + index headroom)
- FDW + Postgres verify after indexes built: **HARD ABORT if > 5 minutes**
- Weekly delta re-run: 0 new rows AND **HARD ABORT if per-table delta > 30s OR total weekly delta > 10 min**
- ReclaimRx pricing-protocol tests green: no new `awp_basis` values; literal-AWP guards still reject correctly
- Codex mini-GATE-CLOSE consult: GO; codex reviews EXPLAIN ANALYZE for index gaps + reviews reclaimrx test deltas

**On HARD ABORT:** B9.F STOPS. Index/query/storage redesign required before B9.G can open. No "documented but slow" pass.

---

### B9.G — Tier D MTL schema-only + loader-registration safeguards (3 sessions)

**Scope:** 19 MTL (Medical Test Lexicon) tables. Schema lands; data does NOT load. Per charter D3 + SC-5.

**Per-session shape (3 sessions):**

- Session 1: 19 SQLAlchemy models in `tier_d/`; migration `0014_fdb_mtl_schema.py` (un-gated, lands schema); 19 contract tests asserting tables exist + are queryable + are EMPTY. **MTL tables NOT added to FDW manifest by default** (ADVERSARIAL A8 mitigation — prevents silent false-negative joins from downstream queries).
- Session 2: Loader registry: explicit exclusion of MTL from `--mode fdb_initial` and `--mode fdb_weekly`; opt-in mode `--mode fdb_mtl_data` exists but requires `fdb_load_mtl=True` config flag. **DB-level guard active (set in B9.A C4):** app roles (`ifx_dev_app`, `ifx_mock_app`) lack INSERT/UPDATE/DELETE on MTL tables; only `ifx_reference_writer` writes during opt-in load.
- Session 3: Integration test `test_fdb_mtl_zero_rows_under_default` (from B9.A C4) exercises the live MTL tables — asserts zero rows after default load. **Negative test added:** app-role INSERT into MTL table MUST fail with permission error (verifies DB-level guard works). Documentation: `docs/runbooks/fdb-mtl-opt-in.md` explains the FUTURE activation path (FDW manifest expansion to 283 + grant flip + data load) when licensing flips.

**Deliverables:**

- 19 SQLAlchemy models
- 1 alembic migration (`0014_fdb_mtl_schema.py`)
- Loader-registration exclusion of MTL from default modes
- Opt-in mode `--mode fdb_mtl_data` gated on flag
- 19 contract tests asserting table exists + empty
- Integration test asserting zero MTL rows after default load
- **Negative test** asserting app-role INSERT to MTL fails
- Runbook `docs/runbooks/fdb-mtl-opt-in.md` (covers MTL activation: FDW expansion 264→283, grants, loader flag flip)
- FDW foreign-table count: 264 → **264** (unchanged — MTL excluded by default per ADVERSARIAL A8 + charter v3.2)

**FDW count derivation (final per charter v3.2):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + **0 (B9.G MTL — schema-only, FDW-excluded)** = **264**. Charter v3.2 SC-6 = 264/264 default; conditional 283/283 if MTL data is later enabled.

**Success criteria:** SC-1 (cum 217/217 — MTL schema present even though FDW-excluded), SC-5 (MTL zero-row test green + DB guard verified), SC-6 (264/264 default), SC-9.

**B9.G mini-GATE-CLOSE criteria:**

- `0014_fdb_mtl_schema.py` apply + reverse + apply: clean
- Integration test `test_fdb_mtl_zero_rows_under_default` green after live load attempt with default flag
- Negative test (app-role INSERT fails on MTL): green
- FDW manifest verified: MTL tables NOT present (264 entries total)
- Opt-in flag flip + `--mode fdb_mtl_data` invocation succeeds (validated, then rolled back; verifies `ifx_reference_writer` path still works)
- Codex mini-GATE-CLOSE consult: GO; codex verifies (a) DB-level guard prevents app-role writes, (b) flipping `fdb_load_mtl=False` after data load DOES NOT delete data, (c) MTL exclusion from FDW is correct for default state

---

### B9.H — Manifest extension + consumer audits + final closeout (5 sessions)

**Scope:** Reconcile `expected_reference_tables.txt` to the final count (264 default), run final FDW verify, audit downstream consumers (adjudication + reclaimrx + TCP listener), produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.

**Per-session shape (5 sessions — +1 session for consumer audits per ADVERSARIAL A14):**

- Session 1: Manifest expansion — `expected_reference_tables.txt` final count locked at **264** (charter v3.2 SC-6 default; MTL excluded). Update Werkbench inventory + glossary if new tables/concepts warrant.
- Session 2: Final `setup_fdw.sh --verify` **264/264** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables (217 + 2 existing = 219 DB tables; 264 FDW entries); published in `waves/B9/evidence.md`
- **Session 3 (NEW — ADVERSARIAL A14):** Consumer audit. Runs three smoke suites against the populated reference DB: (a) **adjudication pricing-enrichment** path — `enrich_pricing()` returns correct WAC/AWP/NADAC + `awp_basis` for representative NDCs across all 5 pricing tables (RNP2/RNP3/RPRDPP0 + NADAC); (b) **TCP listener publish** — claim adjudication runs end-to-end, `claim.adjudicated` event publishes with FDB enrichment fields present; (c) **FDW query smoke** — adjudication, reclaimrx, network-management each run their top-3 FDB-reading queries; all succeed. Failures here trigger B9.H NO-GO and consumer-side fixes.
- Session 4: Cross-tier behavioral suite: NDC lookup goes RNDC14 → RPRD0_PRODUCT → tier-A descriptors → pricing (RNP3, RNP2, RPRDPP0); verifies the wave's value-creation chain
- Session 5: B9 ship artifacts (`waves/B9/ship.md`); memory entry; wave-history index update; codex final GATE-CLOSE consult; PR creation if any of the FDB schema work was branched

**Deliverables:**

- Reconciled `expected_reference_tables.txt`
- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
- `waves/B9/ship.md`
- Cross-tier behavioral test suite
- Memory: `project_b9_implemented.md` and MEMORY.md index line
- `docs/audit/wave-history.md` entry
- Codex final GATE-CLOSE verdict in `waves/B9/codex-gate-close.md`

**Success criteria — ALL SC-1..SC-11:**

- SC-1: 217 tables have models + migrations + ingester (verified via `pg_class` count + alembic history scan)
- SC-2: RECORD_COUNTS reconciled per table (or documented tolerance / exclusion for MTL)
- SC-3: RNDC14 ingest covers all 68 columns
- SC-4: D2 perf gate evidence present
- SC-5: MTL zero-row test green
- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
- SC-7: Weekly delta idempotent across all 220 tables (verified at B9.H by running `--mode fdb_weekly` → 0 new rows in all 217 + already-covered 3)
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
| SC-6 | `setup_fdw.sh --verify` output **264/264** in dev + mock default (charter v3.2 matched); conditional 283/283 when `fdb_load_mtl=True` | B9.H Session 2 |
| SC-7 | `load_fdb.py --mode fdb_weekly` re-run logs zero new rows across all 220 tables | B9.H Session 4 |
| SC-8 | Test counts per category in evidence.md: 217 contract tests + 220 schema-parity + 217 row-count assertions + N sampled behavioral + dedicated Tier C suite | B9.H Session 2 |
| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
| SC-10 | `waves/B9/codex-gate-close.md` with GO verdict | B9.H Session 4 |
| SC-11 | `evidence.md`, `ship.md`, memory file, `wave-history.md` line all present and pointing at the right commits | B9.H Session 4 |

---

## Threat model

| T | Threat | Likelihood | Severity | Mitigation |
|---|---|---|---|---|
| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon §7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
| T3 | RNP2 + RPRDPP0 ingest exhausts dev disk (charter R2) | LOW | HIGH | C0 disk check (≥ 5 GB free); B9.F session 2 timed dry-run captures real consumption; abort + escalate if > +1.4 GB |
| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
| T5 | MTL accidentally loads data despite guards (charter R7) | LOW | HIGH | Triple-layer guard: schema-only migration ✓, loader-registry default exclusion ✓, integration test asserts zero rows ✓; B9.G codex consult specifically reviews the guard chain |
| T6 | RNDC14 68-column model has wrong type for one or more columns (NUMERIC vs Decimal vs Integer vs Text confusion) | MED | MED | B9.E session 1 produces type-mapping table from DDL `.txt` definitions; session 2 codex column-by-column review |
| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, ± in-phase contract tests on the collection number. |
| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) — ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
| T14 | MTL data inserted via direct SQL bypassing loader guard — ADVERSARIAL A5 | LOW | **HIGH** | B9.A C4 + B9.G S2 DB-level guard: `REVOKE INSERT/UPDATE/DELETE` on MTL tables from `ifx_dev_app`/`ifx_mock_app`; only `ifx_reference_writer` retains writes (and is used only by opt-in `--mode fdb_mtl_data`); negative test in B9.G S3 verifies app-role INSERT fails |
| T15 | B9.F perf gate documented without aborting — slow query "passes" — ADVERSARIAL A7 | LOW | **HIGH** | HARD ABORT criteria: FDW verify > 5 min, per-table weekly delta > 30s, total weekly delta > 10 min, storage delta > +1.4 GB. Any breach → B9.F fails, design rework required before B9.G opens. |
| T16 | MTL FDW foreign tables empty → silent false-negative downstream joins — ADVERSARIAL A8 | MED | **HIGH** | MTL EXCLUDED from default FDW manifest (charter v3.2 erratum). Conditional inclusion (264 → 283) only when MTL data is activated. Downstream join to MTL fails LOUDLY (relation does not exist) instead of silently empty. |
| T17 | `load_fdb.py` URL fallback writes FDB to env DB by accident — ADVERSARIAL A11 | LOW | **HIGH** | B9.A C9: B9 FDB loaders require explicit `DATABASE_URL_SYNC_REFERENCE`; fallback removed; runtime assertion `current_database()=='infinityrx_reference'` before any write; failure raises immediately |
| T18 | Adjudication consumers untested against B9 data; new FDB tables may change pricing-enrichment paths — ADVERSARIAL A14 | MED | **HIGH** | B9.H Session 3 runs three consumer audits: (a) `enrich_pricing()` against representative NDCs, (b) TCP listener publish smoke with `claim.adjudicated` event verification, (c) FDW query smoke from adjudication + reclaimrx + network-management top-3 queries |
| T19 | ReclaimRx `awp_basis` guards untested against B9.F populated pricing — ADVERSARIAL A15 | MED | **HIGH** | B9.F Session 4 runs reclaimrx-protocol tests with RNP2 + RPRDPP0 + RNP3 populated; asserts no new basis values, literal-AWP rejection still works |
| T20 | FDW name collision — `setup_fdw.sh` fatals on duplicate names across reference schemas — ADVERSARIAL N1 | LOW | **HIGH** | B9.A C10: preflight scans 217 generated B9 table names against `drug_database / drug_db / reference / shared` schemas; aborts if any collision. Test in CI per-phase. |
| T21 | `parse_table` silently skips field-count errors; large tables can systematically drop rows masked by row-count tolerance — ADVERSARIAL N4 | MED | **HIGH** | Contract test policy: ANY `parse_table` warning fails the test unless explicitly allowlisted in `waves/B9/parse_warning_allowlist.md` with documented count-impact + reviewer sign-off |
| T22 | Tier A session-size overflow if a misclassified table consumes a full session — ADVERSARIAL A1 | MED | MED | Per-table escape-hatch: > 1h solo → reclassify to Tier B/C, remove from `0009`, update FDW ladder; > 20% session burn → trigger mini-replan; charter W1 budget can flex with W2 buffer if needed |
| T23 | 113-table migration failure has large debug blast radius — ADVERSARIAL A2 | LOW | MED | Each migration captures `alembic upgrade + downgrade + upgrade` on a disposable DB before commit; evidence file required at mini-GATE-CLOSE; failed migration auto-flagged for codex review |
| T24 | `setup_fdw.sh --verify` hard-codes "expected 66"; B9.B verify fails without script change — ADVERSARIAL A3 | LOW | MED | B9.A C11 replaces hard-coded count with manifest-derived; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is source of truth |
| T25 | RNDC14 2-session budget insufficient if column review surfaces multiple issues — ADVERSARIAL A6 | MED | MED | B9.E iteration allowance: 2 → up to 4 sessions without borrowing from B9.F; mini-GATE-CLOSE will not close on partial review |
| T26 | 4-5 month wave freezes visible delivery; overruns invisible — ADVERSARIAL A9 | MED | MED | 4-week calendar checkpoint at weeks 4/8/12; intermediate milestone tags (B9.B-shipped, B9.C-shipped) under single B9 label; owner reviews scope/split decision at each checkpoint |
| T27 | 12 codex consults depend on network; past SPEC R2 saw connectivity fragility — ADVERSARIAL A10 | MED | MED | Offline fallback: local-checklist reviewer path per gate (`waves/B9/local_review_checklists/`); retry budget = 3 attempts per consult; 3-retry-fail → escalate to owner |
| T28 | Existing Phase 09 coverage breaks due to registry expansion or migration interaction — ADVERSARIAL A12 | LOW | MED | B9.A C12 captures Phase 09 baseline: RNP3/RPRDPTD0/RNPTYPD0 row counts + query latency + default-mode behavior; per-phase mini-GATE-CLOSE re-asserts unchanged |
| T29 | Flaky test noise drowns real signal in 134-failure baseline — ADVERSARIAL A13 | MED | MED | B9.A C0 captures node-ID snapshots × 2 runs (NOT raw counts); known flakes quarantined in `waves/B9/test_flake_quarantine.md`; mini-GATE-CLOSE asserts node-ID delta, not count delta |
| T30 | Memory churn over 13 weeks contradicts earlier state — ADVERSARIAL A16 | LOW | LOW | B9.A C14 creates `waves/B9/status.md` ledger as single source of truth; memory entries reference this; do not restate mutable facts |
| T31 | `expected_reference_tables.txt` `>0 rows` policy contradicts schema-only MTL — ADVERSARIAL N2 | LOW | LOW | Resolved by T16 (MTL not in default FDW). Document policy explicitly in manifest file header. |
| T32 | 217 model imports in shared declarative base slow unrelated tests — ADVERSARIAL N3 | MED | MED | B9.A C13: module-level declarative bases or targeted metadata creation; profile B9.A C0 vs after with representative test subset; abort + redesign if test wall-clock degrades > 50% |

---

## Codex iteration plan

| Round | Phase | Dispatch trigger | Verdict file |
|---|---|---|---|
| SPEC R1 | B9.A | Charter v1 dispatched 2026-05-11 | `codex-spec-consult-r1.md` — GO-WITH-FIXES |
| SPEC R2 | B9.A | Charter v2 dispatched 2026-05-11 | `codex-spec-consult-r2.md` — GO-WITH-FIXES → cleanup applied → v3 LOCKED |
| PLAN R1 | B9.A | Plan v1 dispatched 2026-05-11 | `codex-plan-consult-r1.md` — GO-WITH-FIXES (8 fixes) |
| PLAN R2 | B9.A | Plan v2 with R1 fixes; verify | `codex-plan-consult-r2.md` — GO-WITH-FIXES → charter v3.1 erratum → PLAN GATE FINAL GO |
| ADVERSARIAL R1 | B9.A | Plan v2 LOCKED dispatched 2026-05-11 | `codex-adversarial-r1.md` — HIGH-SEVERITY OBJECTIONS PRESENT (9 HIGH + 11 MED + 4 novel) |
| **ADVERSARIAL R2** | **B9.A** | **Plan v3 with R1 mitigations absorbed; verify** | **`codex-adversarial-r2.md` — pending** |
| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
| GATE-CLOSE | B9.H | Wave shipping artifacts assembled | `codex-gate-close.md` |

**Total codex consults projected:** 13 (2 SPEC + 2 PLAN + 2 ADVERSARIAL + 6 mini-GATE-CLOSE + 1 final GATE-CLOSE = 13). Token spend through ADVERSARIAL R1: ~280k. Remaining gate consults: ~50-80k for ADVERSARIAL R2 + ~300k for 6 mini-GATE-CLOSEs + ~40k for final = ~390-420k more codex tokens.

---

## Out of plan (deferred — explicitly NOT in scope for B9)

- Phase 4 portal feature work (forward feature work; charter §Out of scope)
- 134 pre-existing test failures (forensic wave handles these; charter §Out of scope)
- B8.2 followups (already shipped commit `1c28e44`; charter §Out of scope)
- MTL data ingest (schema only; flip flag in a later wave IF licensing changes)
- RNDC14 column-curation (charter D1 locks full 68-col; no triage)
- Splitting B9 into multiple wave labels (charter D4 locks single milestone)
- New external data sources beyond NDDF Plus (FDB Atomic, FDB MedKnowledge: separate waves)
- Clinical screening data (NOT subscribed per memory `project_fdb_nddf_plus_dataset.md`)
- Reference DB replication to Azure (deferred per memory `project_phase11a_decision.md`)

---

## Errata resolved by codex PLAN R1 (kept for traceability)

1. **FDW final count: 283 vs 284** → **RESOLVED in PLAN v2: 283** (arithmetic) → **SUPERSEDED in PLAN v3 by ADVERSARIAL A8: 264 default, 283 conditional.** Tier C arithmetic bug (`19 - 3 = 16, not 17`) cascaded to 284; v2 corrected to 283; v3 changed final default to 264 (MTL excluded from default FDW per charter v3.2). Final ladder: 66 → 179 → 245 → 261 → 262 → 264 default; 283 ONLY when `fdb_load_mtl=True` in a future MTL activation wave.
2. **Migration count: 5 vs 6 vs 9-10** → **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.
3. **Loader-orchestration modes: existing vs new** → **RESOLVED:** existing `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, `fdb_rebase`. B9.A C4 does NOT need to add `fdb_weekly`. It may need to add tier-specific modes (`fdb_tier_a`, `fdb_tier_b`, `fdb_mtl_data`) if per-tier loaders are desired; PLAN v2 leaves that as a B9.A C1 design decision (additive to existing modes).

## Effort math reconciliation (charter 39 vs plan 42)

Both numbers are correct under different framings; PLAN v2 makes the distinction explicit:

- **Charter §Workstreams view (39 sessions):** counts only productive ingest work — W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
- **Plan v3 §Phased commit chain view (44 sessions):** counts every phase including expanded B9.A meta-phase (charter v3.2 + plan v1/v2/v3 + 2 SPEC + 2 PLAN + 2 ADVERSARIAL + infra scaffolding C0-C14 = 4 sessions, +1 vs plan v2 for the C8-C14 mitigations) and B9.H closeout with consumer audits (5 sessions, +1 vs plan v2 for ADVERSARIAL A14 audit session). 4 + B (10) + C (12) + D (4) + E (2 → up to 4 per iteration allowance) + F (4) + G (3) + H (5) = **44** (base) / up to **46** (with B9.E iteration headroom).

The 5-session delta (44 - 39) vs charter is the meta-overhead the workstream view excludes: B9.A meta-phase (4 sessions) + B9.H consumer audits (1 extra session) = 5. Both views remain accurate. Charter's "~39" is the productive ingest commitment; PLAN v3's 44 is the calendar-aware total including framework gates + ADVERSARIAL mitigations.

---

## Status reporting cadence

Per session-framework rules (`.claude/rules/session-framework.md`):

- Each B9.X session lands its own evidence row in `waves/B9/sessions.md` (created at B9.A)
- At each mini-GATE-CLOSE: full sign-off sheet committed
- Memory updates after each phase closes
- B9.H final ship: full memory + wave-history entry

**End of PLAN v1.**
