# Wave B9 — Status Ledger

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
| B9.A | Infra + contracts | **CLOSED** (gate-close R1+R2+R3 absorbed) | `503cd7b..a114303` (13 commits) | C0-C14 + 3 gate-close absorptions |
| B9.B | Tier A — **107 specs / FDW 173 / migration with PKs / generic loader** | **R1 ABSORBED — pending R2** | `93c9d8b..<HEAD>` | Scope amended: B9.B closes at 107 (not 113); B9.C absorbs the 6 NDC/GCN/MEDID-keyed reclassifieds (now 72 tables, not 66) |
| B9.C | Tier B — 66 NDC/GCN joins | NOT STARTED | — | Blocked on B9.B |
| B9.D | Tier C non-RNDC14 — 16 complex | NOT STARTED | — | Blocked on B9.C |
| B9.E | RNDC14 standalone | NOT STARTED | — | Blocked on B9.D |
| B9.F | Pricing big — RNP2 + RPRDPP0 | NOT STARTED | — | Blocked on B9.E |
| B9.G | MTL schema-only — 19 Tier D | NOT STARTED | — | Blocked on B9.F |
| B9.H | Cross-cutting cleanup + final gate | NOT STARTED | — | Blocked on B9.G |

---

## B9.A commits ledger

| C# | Scope | Commit | Test count (cumulative) |
|---|---|---|---|
| C0  | Baseline + invariants captured | (pre-session; `baseline.md` only) | — |
| C1  | TableSpec registry expansion (Tier + DeltaSemantics + 4 fields) | `9b19457` | 24 (24) |
| C2  | Generated migration template (gen_fdb_tier_migration.py) | `e54425f` | 12 (36) |
| C3  | Ingester contract test template (N4/A4/T12 mitigations) | `3ead3bd` | 22 (58) |
| C4  | MTL config flag + loader registry + DB REVOKE template | `33a2fb3` | 14 (72) |
| C5  | Codex PLAN R1 consult (captured pre-session) | (Werkbench: `codex-plan-consult-r1.md`) | — |
| C6  | Codex ADVERSARIAL R1 consult (captured pre-session) | (Werkbench: `codex-adversarial-r1.md`) | — |
| C7  | Plan v-bump → v3.1 LOCKED (captured pre-session) | (Werkbench: `plan.md`) | — |
| C8  | SQLite-backed DELTA_SEMANTICS simulator + A4 detector | `d6cefd8` | 8 (80) |
| C9  | Reference-DB write-path guard (env-strict + SQL assert) | `2b1f2b9` | 11 (91) |
| C10 | FDW name-collision preflight script | `c03e37a` | 16 (107) |
| C11 | setup_fdw.sh manifest-derived count + deterministic sort | `60c6cc0` | 9 (116) |
| C12 | Phase 09 compat baseline (markdown + opt-in DB test) | `9b61d6d` | 3 (119, 3 DB-skip) |
| C13 | Module base profile + lock-in test | `9b61d6d` | 3 (122) |
| C14 | This ledger (no code) | (this commit) | — |

**Cumulative B9.A new unit tests: 116 pass; 3 integration tests skip without live DB.**

---

## Codex GATE-CLOSE R1 — verdict & absorption

**Verdict:** GO-WITH-FIXES (2 HIGH + 2 MEDIUM)
**Round:** R1 (2026-05-12)
**Artifacts (all in-repo after R2 F2-completion):**
- `waves/B9/codex-gate-close-r1-prompt.md`
- `waves/B9/codex-gate-close-r1-result.md`
- `waves/B9/codex-gate-close-r2-prompt.md`
- `waves/B9/codex-gate-close-r2-result.md`

**Absorbed in same session as gate-close:**

| Sev | Concern | Fix commit / location |
|---|---|---|
| HIGH | MTL REVOKE template `{{APP_ROLES_QUOTED}}` undocumented; `{{MTL_TABLES}}` schema-prefix bug | F1 — `infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` (docs + SQL line 43 fix) + new test `tests/unit/test_fdb_mtl_revoke_template.py` (6 tests, no-placeholder-survives assertion) |
| HIGH | Wave artifacts not in repo checkout (only Werkbench) | F2 — mirrored `waves/B9/{status,parse_warning_allowlist,phase09_compat_baseline,module_base_profile,write_path_enforcement}.md` into repo |
| MEDIUM | Parse-warning allowlist policy unenforced (free `Iterable[str]`) | F3 — `load_parse_warning_allowlist()` helper in `_fdb_contract.py` + 4 tests; the helper reads `waves/B9/parse_warning_allowlist.md` and returns only entries inside the "Approved" table block, section-anchored |
| MEDIUM | Delta-contract bypass risk (B9.B-G omitted from contract) | **F4 — deferred to B9.B opening.** Codex's own suggested fix specifies: "In B9.B, add a registry-vs-contract coverage test proving every new non-UNKNOWN/non-TRUNCATE_RELOAD TableSpec is represented in the delta contract suite." This is a B9.B C1-class commit. |

**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
spec lands, add `test_delta_contract_coverage` to assert
`{spec.table_name for spec in registry if spec.delta_semantics in
{UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}}
== {spec covered by a contract-test wrapper}`. Failing this test
forces a contract wiring per new spec.

---

## Codex GATE-CLOSE R2 — verdict & absorption

**Verdict:** GO-WITH-FIXES (1 HIGH residual on F2)
**Round:** R2 (2026-05-12)
**Artifact:** `waves/B9/codex-gate-close-r2-result.md`

R2 accepted F1, F3, F4 outright; flagged F2 as incomplete — the
mirrored 5 artifacts referenced `charter.md`, `plan.md`,
`baseline.md`, and the R1 prompt/result, but those were still
Werkbench-only. F2-completion (same session as R2):

- Mirrored `charter.md`, `plan.md`, `baseline.md` into `waves/B9/`.
- Mirrored `codex-gate-close-r1-prompt.md` + `codex-gate-close-r1-result.md`
  into `waves/B9/` so the R1 ladder is reviewable from the
  InfinityRx checkout alone (no Werkbench dependency).
- `status.md` "Artifacts" row updated to reflect in-repo paths.

After F2-completion, B9.A close is reconstructible from the
InfinityRx checkout — every wave artifact named in this file
resolves to an actual in-repo path.

---

## Codex GATE-CLOSE R3 — verdict & final absorption

**Verdict:** GO-WITH-FIXES (1 MEDIUM residual — downgraded from R2 HIGH)
**Round:** R3 (2026-05-12)
**Artifacts:** `waves/B9/codex-gate-close-r3-prompt.md`,
              `waves/B9/codex-gate-close-r3-result.md`

R3 confirmed F2-completion substantially absorbed the R2 HIGH —
charter/plan/baseline + R1/R2 prompt-result pairs are now in-repo.
The residual flag: `status.md` (line 37) and `plan.md` named the
PLAN-consult and ADVERSARIAL-consult artifacts (`codex-plan-consult-r1.md`,
`codex-adversarial-r1.md`) which were still Werkbench-only.

**F2-final absorption (same session):**

Mirrored the full codex consult ladder into the repo:

```
waves/B9/codex-spec-consult-r1.md
waves/B9/codex-spec-consult-r2.md
waves/B9/codex-plan-consult-r1.md
waves/B9/codex-plan-consult-r2.md
waves/B9/codex-adversarial-r1.md
waves/B9/codex-adversarial-r2.md
```

After F2-final, **every consult artifact named in `status.md` or
`plan.md` resolves to an in-repo path.** B9.A close is fully
reconstructible from the InfinityRx checkout alone.

F1 / F3 / F4: all remained accepted across R1 → R2 → R3.

---

## B9.B GATE-CLOSE R1 — verdict & absorption

**Verdict:** GO-WITH-FIXES (2 HIGH + 3 MEDIUM)
**Round:** R1 (2026-05-12)
**Artifact:** `waves/B9/codex-b9b-gate-close-r1-result.md`

**Absorbed in same session:**

| Sev | Concern | Fix |
|---|---|---|
| HIGH 1 | `load_fdb.py` had no `--mode fdb_tier_a` | New `drug_database/services/fdb_tier_loader.py` generic loader; `--mode fdb_tier_a` wired in `scripts/load_fdb.py`. 5 unit tests pass. |
| HIGH 2 | Migration `0009_fdb_tier_a.py` had no PK constraints — `ON CONFLICT` would fail at runtime | Added `natural_key: tuple[str, ...]` field to TableSpec; patched all 99 UPSERT specs across 11 batches; generator now emits `sa.PrimaryKeyConstraint(...)` per spec; generator validates natural_key presence for UPSERT semantics (raises ValueError otherwise) |
| MEDIUM 1 | Charter said 113 / FDW 179; reality is 107 / 173 | Status ledger amended above. Plan scope for B9.C will inherit the 6 reclassifieds. |
| MEDIUM 2 | `UOM_CONVERSION_FACTOR` was NUMERIC(16,6) emitted as Numeric(16,5) | New `decimal_16_6` coercer in `fdb_adapter.py`; generator maps it to `sa.Numeric(16, 6)`; batch_10 spec swapped to use it |
| MEDIUM 3 | Live-DB evidence (FDW verify, migration up/down/up, row-count reconciliation) missing | Deferred to Docker-up follow-on session. Unit-test layer is gate-close-ready; live verification is a separate gate. |

**Regenerated migration:** 1,432 lines (was 1,220); 99 `PrimaryKeyConstraint` + 1 `Numeric(16, 6)` confirmed via grep.

**Test result post-absorption:** 789 unit tests pass (784 B9 batches + adapter + helpers + 5 new tier loader). No regression.

R2 (verification of R1 absorption) returned GO-WITH-FIXES with 1 residual HIGH — see below.

---

## B9.B GATE-CLOSE R2 — verdict & absorption

**Verdict:** GO-WITH-FIXES (1 HIGH residual)
**Round:** R2 (2026-05-12)
**Artifact:** `waves/B9/codex-b9b-gate-close-r2-result.md`

R2 confirmed F1-F4 from R1 cleanly. The lone residual HIGH:
APPEND_ONLY history specs in batch_09 had no PK/unique constraint —
loader's plain-INSERT path would duplicate rows on same-drop replay,
violating the SC-7 idempotency contract.

**Absorbed in same session (single commit):**

| Sev | Fix |
|---|---|
| HIGH | All 8 batch_09 APPEND_ONLY specs gained `natural_key=` covering their non-nullable columns (the immutable identifying tuple). Generator now emits `sa.UniqueConstraint` (not PK) for APPEND_ONLY specs with natural_key — history rows can repeat the same logical fact via DO NOTHING dedupe. Loader's APPEND_ONLY path applies `INSERT ... ON CONFLICT (natural_key) DO NOTHING` when natural_key is set, falling back to plain INSERT for legacy specs without it. |

**Regenerated migration:** 99 PrimaryKeyConstraint + **8 UniqueConstraint** + 1 Numeric(16,6). Every Tier A table now has a uniqueness surface.

**New replay-idempotency test** (`test_append_only_replay_with_natural_key_does_not_duplicate`): constructs SQLite table with UNIQUE index over natural_key, loads twice, asserts row count unchanged after second load. Green.

787 unit tests pass. R3 (verification of R2 absorption) dispatched next.

---

## B9.B C2 — Real-file lock-in (parser-format fix)

**Surfaced 2026-05-12 while staging multi-agent dispatch.** B9.A C3 + C10 parsers assumed `RECORD_COUNTS.TXT` used `=` as the delimiter (per synthetic test fixtures). The REAL file at `data/reference/fdb/TEL251759D/Current/RECORD_COUNTS.TXT` uses `|`.

**Defect impact (would have surfaced on first B9.B C3 row-count reconciliation):**
- `_parse_record_counts` returned `{}` for every real-file invocation.
- `assert_row_count_reconciles` would fail every B9.B+ contract test with "no entry for key" — masking the real assertion.
- Preflight `load_expected_names` returned `[]`, so name-collision scan was vacuously PASS.

**Fix shipped (same commit as B9.B C2):**
- Both parsers (`_fdb_contract._parse_record_counts` and `preflight_b9_name_collision.load_expected_names`) now prefer `|`, fall back to `=` for synthetic-fixture compatibility.
- New integration test `tests/integration/test_fdb_record_counts_real_file.py` (4 tests) runs against the live FDB drop when present; skips otherwise.

**Discovery: 906 vs 220 — canonical list re-points to DB.zip.**
- RECORD_COUNTS.TXT contains **906 entries**, NOT 220. It is a superset that includes archive snapshots (`AR*`), clinical surveillance (`CMCS*`), UPD-only variants, and vendor bookkeeping rows.
- The canonical 220 B9 schema-driving tables live in `NDDF Plus DB.zip` namelist (220 files exactly).
- **B9.B C3 design decision (deferred to next session):** re-point the preflight `load_expected_names` to source from DB.zip namelist instead of RECORD_COUNTS. RECORD_COUNTS remains the row-count reconciliation source for the 220 tables it DOES cover.
- Lock-in test `test_db_zip_has_220_tables` confirms the canonical universe.

This is the kind of defect the recon's "verify against real drop" gate is designed to catch. Surfaced before the multi-agent per-table dispatch could amplify it across 113 specs.

---

## B9.B prep ledger (C1–C4 — multi-agent dispatch enablement)

| C | Commit | Scope |
|---|---|---|
| C1 | `93c9d8b` | F4 coverage canary — `fdb_specs.py` + `test_fdb_contract_coverage.py` |
| C2 | `2d3e791` | RECORD_COUNTS parser format fix (`|` not `=`) + 906-vs-220 discovery |
| C3 | `d8af39e` | Canonical 220-table namelist + preflight re-pointed to DB.zip source |
| C4 | `353a04b` | Per-table DDL manifest (221 entries, 7 lock-in tests) |

**Multi-agent dispatch readiness (C5+):**

With C1–C4 landed, each B9.B per-table builder agent has authoritative inputs:
- `infrastructure/scripts/lib/fdb_db_zip_namelist.txt` — 220 canonical table names
- `infrastructure/scripts/lib/fdb_table_ddl_manifest.json` — per-table columns + types + nullable
- `modules/drug-database/tests/_fdb_contract.py` — contract helpers (6 assertion fns + allowlist loader)
- `modules/drug-database/drug_database/services/fdb_specs.py` — `REGISTERED_SPECS` registry to append to
- `modules/drug-database/tests/unit/test_fdb_contract_coverage.py` — `CONTRACT_TESTED_SPECS` coverage registry

**B9.B C5 design (next-session first commit):**

Author ONE batch by hand (12 Tier A tables) as the canonical pattern.
Pattern includes:
- `drug_database/services/fdb_tier_a_batches/batch_01.py` with `BATCH_01: list[TableSpec] = [...]`
- `drug_database/services/fdb_specs.py` aggregates batches
- `tests/unit/test_fdb_tier_a_batch_01.py` wires each spec through the 6 contract helpers
- Appends 12 names to `CONTRACT_TESTED_SPECS`

**B9.B C6+ multi-agent dispatch (after template proven):**

10 parallel `general-purpose` agents, each owning 1 batch (~12 tables).
Per-agent isolation via per-batch file ownership — no merge conflicts on shared registries. Each agent commits independently.

---

## Codex consult ladder summary (full B9 audit trail)

| Round | Phase | Verdict | Artifact |
|---|---|---|---|
| SPEC R1 | Charter design | GO-WITH-FIXES | `codex-spec-consult-r1.md` |
| SPEC R2 | Charter v3 | GO-WITH-FIXES (5/6 verified) | `codex-spec-consult-r2.md` |
| PLAN R1 | Plan v1 | GO-WITH-FIXES | `codex-plan-consult-r1.md` |
| PLAN R2 | Plan v3.1 | GO | `codex-plan-consult-r2.md` |
| ADVERSARIAL R1 | Attack vectors | 20 attacks surfaced | `codex-adversarial-r1.md` |
| ADVERSARIAL R2 | Mitigation verify | GO | `codex-adversarial-r2.md` |
| GATE-CLOSE R1 | B9.A close v1 | GO-WITH-FIXES (2H + 2M) | `codex-gate-close-r1-result.md` |
| GATE-CLOSE R2 | B9.A close v2 (F1+F3+F4 + partial F2) | GO-WITH-FIXES (1H residual) | `codex-gate-close-r2-result.md` |
| GATE-CLOSE R3 | B9.A close v3 (F2-completion) | GO-WITH-FIXES (1M residual) | `codex-gate-close-r3-result.md` |
| **GATE-CLOSE R3 F2-final absorption** | **mirror remaining consults → in-repo audit trail** | **complete** | this commit |

B9.A closes after the F2-final absorption commit. Next session opens
B9.B with the F4 pre-opening obligation as its first commit.

---

## B9.A mini-GATE-CLOSE checklist (charter SC-9)

Per `waves/B9/plan.md:116-127`:

- [x] All cross-cutting infra commits unit-tested green (116/116 pass)
- [x] Pytest collection node-IDs captured at baseline (waves/B9/baseline.md)
- [x] `setup_fdw.sh --verify` still passes (132 PASS, 0 FAIL — captured post-B7.3)
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
| SC-2 | RECORD_COUNTS reconciliation (within ±0.1%) | Contract template ready (C3); per-table assertions land B9.B+ |
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

1. **195 pre-existing test failures** — out of B9 scope per charter
   §Out-of-scope row 3 ("134 pre-existing test failures (forensic wave)").
   The +61 vs prior memory was resolved by B7.3 (commit `503cd7b`).
2. **tests/integration collection error** — pre-existing plugin
   registration conflict; forensic wave fixes.
3. **Second-run flake snapshot** — DEFERRED to next Docker-up session.

---

## Update protocol

This file is updated:

* When a B9.A C# commit lands — append the commit row.
* When a phase enters / exits / blocks — update the phase ledger row.
* When a charter SC moves status — update the SC mapping row.
* At every mini-GATE-CLOSE — append the per-phase evidence section.

Memory entries (`~/.claude/.../memory/project_b9_*.md`) reference
this file via a pointer (`see status.md row X`). They do NOT
duplicate state — that creates two-source-of-truth drift.
