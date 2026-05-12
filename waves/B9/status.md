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
| B9.A | Infra + contracts | **IN PROGRESS — gate-close pending** | `503cd7b..9b61d6d` (9 commits) | C0-C14 below |
| B9.B | Tier A — 113 simple lookups | NOT STARTED | — | Blocked on B9.A gate-close |
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
**Artifacts:**
- `waves/B9/codex-gate-close-r1-prompt.md`
- `waves/B9/codex-gate-close-r1-result.md` (Werkbench)

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
