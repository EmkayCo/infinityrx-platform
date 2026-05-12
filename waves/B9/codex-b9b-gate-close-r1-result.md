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
session id: 019e1cad-9a7c-76b2-b65b-39d5119f5921
--------
user
# Codex B9.B mini-GATE-CLOSE R1 — Consult Prompt

**Wave:** B9 (FDB NDDF Plus 217-table extension)
**Phase:** B9.B (Tier A — 113-table simple lookups, recon §3 estimate)
**Verdict requested:** GO / GO-WITH-FIXES / NO-GO
**Predecessor:** B9.A CLOSED — `a114303` with 3 rounds of codex review absorbed
**Plan reference:** `waves/B9/plan.md:133-173`

## Scope

B9.B is the first per-table data wave. Goal per recon §3:
"113 Tier A tables = simple lookup descriptors (≤ 5 cols, < 2 MB)".

**Actual delivered: 107 specs across 11 batches + migration + FDW manifest.**

Diff vs recon estimate: 6 short. The 6 residual were reclassified as
Tier B per recon §3's own definition — they are NDC/GCN/MEDID-keyed
link tables that join to upstream entity IDs (e.g., RAHFSGC1_GCNSEQNO_LINK,
RGCN0_GCN_GCNSEQNO_LINK). They will land in B9.C.

## What changed since B9.A close

Commits on `develop` (in scope of this review):

```
93c9d8b  B9.B C1 (F4): registry-vs-contract coverage assertion + Tier A charter
2d3e791  B9.B C2: RECORD_COUNTS.TXT parser-format fix + 906-vs-220 discovery
d8af39e  B9.B C3: re-point preflight to DB.zip canonical 220-table namelist
353a04b  B9.B C4: per-table DDL manifest for multi-agent dispatch
50e7a88  B9.B C5: auto-aggregation infrastructure (multi-agent isolation)
79d3416  B9.B C6: Tier A batch_01 (canonical template, 12 id+desc lookups)
7bb9964  B9.B C9: Tier A batch_04 (10 lookup tables) + bundled batch_02 (10)
4a58889  B9.B C8: Tier A batch_03 (10 lookup tables)
697393c  B9.B C10: Tier A batch_05 (10 lookup tables including 1 DATE coercer)
1d3ffde  B9.B C11: Tier A batch_06 (10 lookup tables)
6c1ed28  B9.B C12: Tier A batch_07 (10 lookup tables)
1292c04  B9.B C13: composite-NK template (batch_08, 5 TALL MAN tables)
a4ea4db  B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
86515b5  B9.B C15: Tier A batch_10 (11 link tables — composite+single NK hybrid)
2f226ae  B9.B C16: Tier A batch_11 (11 link tables with DATE columns)
7c1c5e9  B9.B C17+C18: alembic migration 0009_fdb_tier_a + FDW manifest expansion (66 → 173)
```

## Files added / modified

### Production code (drug_database/services/fdb_tier_a/)
- `__init__.py` — pkgutil-based auto-aggregator (C5)
- `batch_01.py` through `batch_11.py` — 107 TableSpec instances total
- `fdb_specs.py` (parent module) — `REGISTERED_SPECS = list(TIER_A_SPECS)`

### Tests (tests/unit/)
- `test_fdb_contract_coverage.py` — F4 coverage canary (loads BATCH_TESTED_NAMES via pkgutil)
- `test_fdb_tier_a_batch_01.py` through `test_fdb_tier_a_batch_11.py` — 691 parametrized + sanity tests
- `test_fdb_contract.py`, `test_fdb_delta_semantics.py` — unchanged from B9.A

### Migration + FDW
- `modules/drug-database/alembic/versions/0009_fdb_tier_a.py` — 1,220 lines auto-generated via `gen_fdb_tier_migration.py`. Creates all 107 tables in `drug_database` schema with proper column types, nullables, GRANTs (env-driven IFX_APP_ROLE pattern), and operator dry-run docstring.
- `infrastructure/scripts/lib/expected_reference_tables.txt` — 66 → 173 entries (+107 Tier A appended in a new section)

### Wave artifacts
- `waves/B9/B9.B-charter.md` — wave charter
- `waves/B9/status.md` — ledger updated to reflect B9.B ready for gate-close

## Test result

```
B9.B Tier A unit tests:      691 pass
B9.A inherited unit tests:   ~130 pass (unchanged)
Integration:                 3 skipped (live-DB only)
drug-database total:         326 → 1000+, no regression
```

Per-batch test counts (after the hybrid pattern shake-out):
batch_01: 60 + batch_02: 61 + batch_03: 61 + batch_04: 61 +
batch_05: 61 + batch_06: 61 + batch_07: 61 + batch_08: 36 +
batch_09: 57 + batch_10: 78 + batch_11: 79 + coverage: 2 = 678

(Discrepancy with 691 is a few schema-parity tests duplicated across
the auto-aggregator vs per-batch — both green either way.)

## Architectural patterns introduced

1. **Auto-aggregator via `pkgutil.iter_modules`** (C5). Parallel
   agents own per-batch files (`batch_NN.py` + `test_fdb_tier_a_batch_NN.py`)
   without touching shared aggregation lists. The auto-loader
   discovers all `batch_*.py` modules and unions their `SPECS`
   exports into `TIER_A_SPECS`. Same pattern for the test side
   via `BATCH_TESTED_NAMES` constants.

2. **Three delta-semantics patterns**:
   - **Single-NK UPSERT** (batch_01 - batch_07): 12-10 specs each.
     2-5 columns; NK is first column; ACD test uses `extra_cols`
     to fill placeholder values for non-key columns.
   - **Composite-NK UPSERT** (batch_08, batch_10, batch_11):
     2-4 column NKs. ACD test parametrizes `natural_key` dict
     from `spec.columns[:NK_COUNT]`. Hybrid in batch_10/11 handles
     both NK=1 and NK>=2 conditionally.
   - **APPEND_ONLY history** (batch_09): 2-5 columns;
     `make_sqlite_simulator(append_only=True)`; D becomes
     tombstone append; contract template's APPEND_ONLY branch
     asserts row-count growth across A/C/D/re-A.

3. **DATE coercer pattern** (batch_05, batch_09, batch_11):
   `_parse_fdb_date` imported from `fdb_adapter`. Test placeholders
   are raw `YYYYMMDD` strings; coercion happens at parse time,
   not in the SQLite contract simulator.

4. **Multi-agent worktree dispatch** (C7-C16): 6 agents authored
   batches 02-07 + 10-11 in parallel, each in isolated worktrees.
   Auto-aggregator picks up commits as they land on `develop`.

## Areas to scrutinize

1. **107 vs 113 — is the Tier B reclassification rationale sound?**
   The 6 deferred specs are NDC/GCN/MEDID-keyed (RAHFSGC1_GCNSEQNO_LINK,
   RATCGC0_ATC_GCNSEQNO_LINK, RGCN0_GCN_GCNSEQNO_LINK, RETCNDC0_ETC_NDC,
   RGCNINH0_GCNSEQNO_INACTV_LINK, RGCNINS0_STUDY_TABLE). Recon §3
   explicitly defines Tier B as "NDC/GCN/MedID-keyed link/crossref
   tables". Forcing them into Tier A would violate that classification.
   But: does deferring 6 invalidate B9.B as a clean wave boundary,
   or is "Tier A as recon defines it" the right framing?

2. **All-NK junction tables in batch_11** (RXRFDDX0, RXRGDFQ0,
   RXRMDFQ0, RXRPDFQ0). Every column is part of the natural key —
   there are no non-key columns for the C step to toggle. The agent
   correctly identified this and used `if not non_nk_cols:` to
   short-circuit the ACD assertion. Is treating "no-op C" as valid
   UPSERT_BY_NATURAL_KEY the right call, or should these be a new
   `JUNCTION_TABLE` delta semantic?

3. **Decimal coercer in batch_10** for `RPEIUC0_UOM_CONVERSION.
   UOM_CONVERSION_FACTOR` (NUMERIC(16,6)). The agent applied
   `.claude/rules/financial-precision.md` aggressively — even
   though UOM conversion isn't money. Is this overreach, or correct
   conservative defaulting? (Phase 09 used Decimal for RNP3.PRICE
   per the same rule.)

4. **APPEND_ONLY ACD test pattern** in batch_09. The contract
   template's APPEND_ONLY branch asserts count >= 4 after A/C/D/re-A
   (every step appends). The test passes string placeholder DATE
   values; coercion is deferred to parse time. Does the test
   adequately catch a regression where the loader collapses
   history rows via UPSERT?

5. **Alembic migration scale** — 1,220 lines for 107 tables in one
   file. The recon recommends single-tier batched migrations
   (`charter.md:75-79`). Is the file size still reviewable by a
   human reviewer, or should it split into part-files?

6. **Generator output quality** — sample first/last 100 lines of
   `0009_fdb_tier_a.py`. Are the column types reasonable (sa.Integer
   for NUMERIC, sa.Text for VARCHAR, sa.Date for DATE)? Note: the
   generator does NOT map VARCHAR(n) to sa.String(n) — it uses
   sa.Text uniformly. This is fine for Postgres (TEXT vs VARCHAR(n)
   has no storage difference) but loses the DDL-documented width.

7. **F4 coverage canary** still green at 107 specs. Confirm by
   reading `modules/drug-database/tests/unit/test_fdb_contract_coverage.py`
   — the pkgutil walk picks up all 11 batch test modules' BATCH_TESTED_NAMES.

## Verdict format

GO — B9.B closes; B9.C opens (Tier B — 66 NDC/GCN-keyed joins, plus the 6 reclassified residuals).
GO-WITH-FIXES — list residual HIGH / MEDIUM concerns.
NO-GO — fundamental issue requiring charter or plan revision.

For GO-WITH-FIXES, return concerns as:
| Severity | Area | Issue | Suggested fix |

codex
I’ll treat this as a gate review: verify the stated artifacts against the repo, sample the migration and tests, then return a GO / GO-WITH-FIXES / NO-GO verdict with concrete findings.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path waves/B9/plan.md -TotalCount 190 | Select-Object -Skip 120' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git log --oneline -18' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-ChildItem -Path modules/drug-database/drug_database/services/fdb_tier_a -Filter '*.py' | Select-Object -ExpandProperty Name; Get-ChildItem -Path modules/drug-database/tests/unit -Filter 'test_fdb_tier_a_batch_*.py' | Select-Object -ExpandProperty Name" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/tests/unit/test_fdb_contract_coverage.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 617ms:
"""B9.B C1 â€” F4 from codex GATE-CLOSE R1 MEDIUM 2.

The DELTA_SEMANTICS contract template at `_fdb_contract.py` is
useless if a B9.B-G commit can land a new spec WITHOUT wiring a
contract test. This file is the coverage canary:

  For every TableSpec in `drug_database.services.fdb_specs.
  REGISTERED_SPECS` whose `delta_semantics` is in the checkable set
  ({UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}),
  the spec's `table_name` MUST appear in `CONTRACT_TESTED_SPECS`
  below, AND there must be a test in the suite that calls
  `assert_delta_semantics_acd_cycle(spec, ...)` for it.

The atomic-per-spec PR pattern: a B9.B Tier A commit that adds a
spec to `REGISTERED_SPECS` ALSO appends to `CONTRACT_TESTED_SPECS`
AND lands the contract test in the same commit. Forgetting any one
of those three fails this test.

UNKNOWN and TRUNCATE_RELOAD specs are intentionally excluded â€”
UNKNOWN is Phase 09 backward-compat (no contract by design) and
TRUNCATE_RELOAD has a separate end-to-end reload contract that
runs at the integration layer, not via the A/C/D simulator.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import DeltaSemantics
from drug_database.services.fdb_specs import REGISTERED_SPECS


# Delta semantics classes that require an A/C/D contract test.
_CHECKABLE_SEMANTICS = frozenset({
    DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
    DeltaSemantics.APPEND_ONLY,
})


# Names of TableSpecs known to have a contract-test wired up.
#
# B9.B C5+ pattern: per-batch test modules declare their own
# `BATCH_TESTED_NAMES` constant. This loader unions every such constant
# across all `test_fdb_tier_a_batch_*.py` modules in the same package.
# Parallel agents own their own batch_N file; no merge conflict here.
#
# Phase 09's 3 pricing specs (RNP3 / RPRDPTD0 / RNPTYPD0) live outside
# REGISTERED_SPECS with delta_semantics=UNKNOWN â€” they predate the
# contract template and are out of scope for this assertion.


def _load_batch_tested_names() -> frozenset[str]:
    """Discover per-batch BATCH_TESTED_NAMES exports and union them.

    Looks at every sibling test module in this package whose name
    starts with `test_fdb_tier_a_batch_`. Imports each, reads its
    BATCH_TESTED_NAMES constant (frozenset[str] expected). Missing
    or wrong-typed exports raise loudly â€” silent type drift would
    let the coverage canary go quiet on a real omission.
    """
    import importlib
    import pkgutil

    parent_pkg = ".".join(__name__.split(".")[:-1]) or __name__
    try:
        pkg = importlib.import_module(parent_pkg)
    except ImportError:
        return frozenset()
    if not hasattr(pkg, "__path__"):
        return frozenset()
    out: set[str] = set()
    for info in pkgutil.iter_modules(pkg.__path__):
        if not info.name.startswith("test_fdb_tier_a_batch_"):
            continue
        mod = importlib.import_module(f"{parent_pkg}.{info.name}")
        names = getattr(mod, "BATCH_TESTED_NAMES", None)
        if names is None:
            # Tolerate batch test modules that haven't declared the
            # constant yet (during the C6+ wave evolution); the F4
            # canary will still fire on coverage gaps.
            continue
        if not isinstance(names, (frozenset, set, tuple, list)):
            raise TypeError(
                f"{parent_pkg}.{info.name}.BATCH_TESTED_NAMES must be "
                f"frozenset/set/tuple/list of str; got {type(names).__name__}."
            )
        out.update(names)
    return frozenset(out)


CONTRACT_TESTED_SPECS: frozenset[str] = _load_batch_tested_names()


# ---------------------------------------------------------------------------
# F4 invariant
# ---------------------------------------------------------------------------


def test_every_checkable_spec_has_contract_coverage() -> None:
    """For each registered spec with checkable delta semantics, a test exists."""
    checkable_names = {
        s.table_name for s in REGISTERED_SPECS
        if s.delta_semantics in _CHECKABLE_SEMANTICS
    }
    missing = checkable_names - CONTRACT_TESTED_SPECS
    assert not missing, (
        f"B9.B F4 coverage violation: {len(missing)} TableSpec(s) "
        f"registered with checkable delta_semantics but missing from "
        f"CONTRACT_TESTED_SPECS: {sorted(missing)}. For each:\n"
        f"  1. Add a test calling assert_delta_semantics_acd_cycle(spec, ...).\n"
        f"  2. Append the table_name to CONTRACT_TESTED_SPECS in this file.\n"
        f"Failure to do BOTH means a regression like the A4 "
        f"'ON CONFLICT DO NOTHING' bug could ship undetected."
    )


def test_no_stale_entries_in_contract_tested_specs() -> None:
    """A name in CONTRACT_TESTED_SPECS that is NOT in REGISTERED_SPECS = stale.

    Stale entries hide deletions: if a spec is removed from the
    registry but its name stays in CONTRACT_TESTED_SPECS, the
    coverage assertion still passes but the contract test now
    references a non-existent spec â€” likely silently skipped.
    """
    registered_names = {s.table_name for s in REGISTERED_SPECS}
    stale = CONTRACT_TESTED_SPECS - registered_names
    assert not stale, (
        f"B9.B F4: {len(stale)} stale entries in CONTRACT_TESTED_SPECS "
        f"(in coverage set but NOT in REGISTERED_SPECS): {sorted(stale)}. "
        f"Either restore the spec to the registry, or remove the name + "
        f"its contract test in the same commit."
    )


# ---------------------------------------------------------------------------
# Empty-baseline canary â€” DELETED on first batch landing (B9.B C6, `50e7a88`).
# The canary served its purpose: forced the operator's attention to this
# file when the first Tier A spec arrived. Now that batch_01 is in, the
# coverage assertion above is the live invariant.
# ---------------------------------------------------------------------------

 succeeded in 650ms:
- Phase 09 compatibility baseline established and PASS-asserted.
- Write-path enforcement verified: attempting a fallback write FAILS LOUDLY.
- FDW name collision preflight returns 0 collisions for all 217 generated B9 names.
- DB-level MTL guard verified: app role INSERT into MTL table fails with permission error.
- Module-level base design profiled: B9-models-loaded vs not, delta documented.
- Codex PLAN R1 + R2 + ADVERSARIAL R1 + R2 verdicts all captured; all HIGH/MEDIUM objections addressed.
- Memory updated: `project_b9_plan_v3_locked.md`; `waves/B9/status.md` ledger initialized.

**B9.A revised session estimate:** 3 â†’ 4 sessions (C8-C14 add ~1 session of infra work).

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

 succeeded in 632ms:
batch_01.py
batch_02.py
batch_03.py
batch_04.py
batch_05.py
batch_06.py
batch_07.py
batch_08.py
batch_09.py
batch_10.py
batch_11.py
__init__.py
test_fdb_tier_a_batch_01.py
test_fdb_tier_a_batch_02.py
test_fdb_tier_a_batch_03.py
test_fdb_tier_a_batch_04.py
test_fdb_tier_a_batch_05.py
test_fdb_tier_a_batch_06.py
test_fdb_tier_a_batch_07.py
test_fdb_tier_a_batch_08.py
test_fdb_tier_a_batch_09.py
test_fdb_tier_a_batch_10.py
test_fdb_tier_a_batch_11.py

 succeeded in 663ms:
 M data/reference/ncpdp/NCPDP_v3.1_Monthly_Master_20240501.ZIP
 M infrastructure/scripts/backup.sh
 M infrastructure/scripts/restore.sh
 M infrastructure/scripts/run_migrations.sh
 M infrastructure/scripts/run_reference_loaders.sh
 M infrastructure/scripts/switch_env.sh
 M infrastructure/scripts/verify_backup.py
 M portal/operator/next-env.d.ts
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
?? B10-eslint-output.txt
?? B10-playwright-output.txt
?? B10-qa-output.txt
?? B10-vitest-output.txt
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
?? waves/B9/codex-b9b-gate-close-r1-prompt.md
?? waves/B9/codex-b9b-gate-close-r1-result.md
7c1c5e9 B9.B C17+C18: alembic migration 0009_fdb_tier_a + FDW manifest expansion (66 → 173)
2f226ae B9.B C16: Tier A batch_11 (11 link tables with DATE columns)
86515b5 B9.B C15: Tier A batch_10 (11 link tables — composite+single NK hybrid)
a4ea4db B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
1292c04 B9.B C13: composite-NK template (batch_08, 5 TALL MAN tables)
1d3ffde B9.B C11: Tier A batch_06 (10 lookup tables)
6c1ed28 B9.B C12: Tier A batch_07 (10 lookup tables)
3bbc499 wave(B10) W4.6: env-gated B10 test-mode auth bypass for next start probe
f6d666b wave(B10) W4.4: playwright config env-aware reuseExistingServer (RE-APPLY after pCloud sync overwrote first attempt)
7bb9964 B9.B C9: Tier A batch_04 (10 lookup tables)
697393c B9.B C10: Tier A batch_05 (10 lookup tables including 1 DATE coercer)
4a58889 B9.B C8: Tier A batch_03 (10 lookup tables)
79d3416 B9.B C6: Tier A batch_01 (canonical template, 12 id+desc lookups)
50e7a88 B9.B C5: auto-aggregation infrastructure (multi-agent isolation)
fc978f2 wave(B10) W4.1-W4.3+W4.5: workspace-aware lint/test config + precursor cleanup
8a477b5 B9.B status ledger: C1–C4 prep ledger + multi-agent dispatch plan
353a04b B9.B C4: per-table DDL manifest for multi-agent dispatch
d8af39e B9.B C3: re-point preflight to DB.zip canonical 220-table namelist
warning: could not open directory '.claude/skills$skill/': No such file or directory

codex
The repo is very dirty outside the B9.B slice, so I’m treating committed `develop` history and the named B9 files as the review surface. The B9.B commits are present at the tip cluster, with unrelated B10 commits interleaved.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/drug_database/services/fdb_tier_a/__init__.py; Get-Content -Path modules/drug-database/drug_database/services/fdb_specs.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/alembic/versions/0009_fdb_tier_a.py -TotalCount 140; Get-Content -Path modules/drug-database/alembic/versions/0009_fdb_tier_a.py -Tail 140' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '(Get-Content -Path infrastructure/scripts/lib/expected_reference_tables.txt | Where-Object { $_ -match '"'"'^drug_database'"\\.fdb_' }).Count; Get-Content -Path infrastructure/scripts/lib/expected_reference_tables.txt -Tail 130" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4"` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '(Get-Content -Path infrastructure/scripts/lib/expected_reference_tables.txt | Where-Object { $_ -match '"'"'^drug_database'"\\.fdb_' }).Count; Get-Content -Path infrastructure/scripts/lib/expected_reference_tables.txt -Tail 130"` rejected: blocked by policy
2026-05-12T14:54:03.000553Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4"` rejected: blocked by policy
2026-05-12T14:54:03.000561Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '(Get-Content -Path infrastructure/scripts/lib/expected_reference_tables.txt | Where-Object { $_ -match '"'"'^drug_database'"\\.fdb_' }).Count; Get-Content -Path infrastructure/scripts/lib/expected_reference_tables.txt -Tail 130"` rejected: blocked by policy
 succeeded in 477ms:
"""B9.B Tier A â€” Per-batch TableSpec aggregator.

Auto-discovers every `batch_*.py` module in this package and unions
their `SPECS` exports into a single `TIER_A_SPECS` list. Multi-agent
parallelism: each agent owns one `batch_N.py` file; the aggregator
picks up all batches without anyone editing a shared registry list.

Per-batch module contract:

    # drug_database/services/fdb_tier_a/batch_NN.py
    from drug_database.services.fdb_adapter import (
        DeltaSemantics, TableSpec, Tier,
    )

    SPECS: list[TableSpec] = [
        TableSpec(
            table_name="RFOO_TEST",
            columns=("col_a", "col_b"),
            coercers={"col_a": int, "col_b": str},
            tier=Tier.A,
            loader_group="fdb_tier_a",
            record_counts_key="RFOO_TEST",
            delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        ),
        ...
    ]

The aggregator imports each batch on first access, caches the unioned
result, and exposes:

    TIER_A_SPECS         â€” list[TableSpec]    (the canonical Tier A registry)
    TIER_A_TABLE_NAMES   â€” frozenset[str]     (helper for coverage tests)
    discovered_batches() â€” list[str]          (which batch modules loaded)
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drug_database.services.fdb_adapter import TableSpec


_BATCH_PREFIX = "batch_"


def _discover_batch_modules() -> list[str]:
    """Return sorted names of every batch_*.py module in this package."""
    pkg = importlib.import_module(__name__)
    names = sorted(
        info.name for info in pkgutil.iter_modules(pkg.__path__)
        if info.name.startswith(_BATCH_PREFIX)
    )
    return names


def _load_specs() -> list["TableSpec"]:
    """Import every batch module and concatenate its SPECS list.

    Order is lexicographic by module name (batch_01, batch_02, ...).
    Each batch module MUST expose a top-level `SPECS: list[TableSpec]`.
    Missing SPECS â†’ loud ImportError so the operator notices.
    """
    out: list["TableSpec"] = []
    for name in _discover_batch_modules():
        mod = importlib.import_module(f"{__name__}.{name}")
        specs = getattr(mod, "SPECS", None)
        if specs is None:
            raise ImportError(
                f"{__name__}.{name} missing required `SPECS: list[TableSpec]` "
                f"export. Every batch module must declare it (see package "
                f"docstring for the contract)."
            )
        out.extend(specs)
    return out


# Eager load at package import â€” the registry is a known cost paid once.
TIER_A_SPECS: list["TableSpec"] = _load_specs()
TIER_A_TABLE_NAMES: frozenset[str] = frozenset(s.table_name for s in TIER_A_SPECS)


def discovered_batches() -> list[str]:
    """Return the list of batch module names that were loaded.

    Useful for status-line reporting and for the F4 coverage test.
    """
    return _discover_batch_modules()


__all__ = [
    "TIER_A_SPECS",
    "TIER_A_TABLE_NAMES",
    "discovered_batches",
]
"""B9.B â€” Registry of FDB TableSpec instances by tier.

This module is the SINGLE SOURCE OF TRUTH for which FDB tables the
platform knows about. B9.B-G populates it tier by tier:

  B9.B â†’ 113 Tier A specs
  B9.C â†’ 66 Tier B specs
  B9.D â†’ 16 Tier C non-RNDC14
  B9.E â†’ 1 RNDC14
  B9.F â†’ 2 pricing big (RNP2 + RPRDPP0)
  B9.G â†’ 19 Tier D / MTL specs

Phase 09's 3 pricing specs (RNP3, RPRDPTD0, RNPTYPD0) live inside
`fdb_pricing_ingester.py` for historical reasons â€” they predate the
unified registry. The B9 F4 coverage assertion does NOT scan them
because their `delta_semantics` is UNKNOWN (backward-compat default).
They will migrate into this registry in a future cleanup wave.

The F4 contract (codex GATE-CLOSE R1 MEDIUM 2):
  For every spec in REGISTERED_SPECS whose delta_semantics is in
  {UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY},
  there MUST be a contract-test wired up â€” see
  `tests/unit/test_fdb_contract_coverage.py`.
"""
from __future__ import annotations

from drug_database.services.fdb_adapter import TableSpec
from drug_database.services.fdb_tier_a import TIER_A_SPECS


# Tier A: auto-aggregated from `fdb_tier_a.batch_*` modules so parallel
# agents do not contend on this file (B9.B C5+ pattern). Each agent
# adds their batch_NN.py + matching test module; this list discovers
# them via pkgutil.
#
# Tier B-G: append-here when those waves land (B9.C-G).
REGISTERED_SPECS: list[TableSpec] = list(TIER_A_SPECS)


__all__ = ["REGISTERED_SPECS"]

 succeeded in 487ms:
"""B9 Tier A batch â€” 107 FDB tables (simple lookups, generic ingester).

Generated by `modules/drug-database/scripts/gen_fdb_tier_migration.py`
on 2026-05-12. SPEC: charter v3.1 Â§SPEC-locked migration granularity;
plan v3.1 Â§W1-W4 tier scope.

Operator: dry-run on a disposable DB before committing (ADVERSARIAL R1 A2):

    alembic upgrade head      # forward
    alembic downgrade -1      # reverse
    alembic upgrade head      # re-apply

All three steps must succeed cleanly. Capture evidence to
`waves/B9/Tier A_dryrun_evidence.md` before committing.

Revision ID: 0009_fdb_tier_a
Revises: 0008_fdb_pricing
Create Date: 2026-05-12
"""
from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0009_fdb_tier_a"
down_revision: Union[str, None] = "0008_fdb_pricing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "drug_database"

# B7.3 env-driven role pattern â€” defaults to dev-safe role if env unset.
# Production sets IFX_APP_ROLE=ifx_prod_app explicitly.
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_APP_ROLES = ("ifx_dev_app", "ifx_mock_app", _APP_ROLE)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}".format(_SCHEMA=_SCHEMA))

    # RAHFSD1_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RAHFSD1
    op.create_table(
        "rahfsd1_desc",
        sa.Column('AHFS8', sa.Integer(), nullable=False),
        sa.Column('AHFS_DESC', sa.Text(), nullable=True),
        schema='drug_database',
    )

    # RAPLRT0_APPL_RELATION_TYPE â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RAPLRT0
    op.create_table(
        "raplrt0_appl_relation_type",
        sa.Column('APPL_RELATION_TYPE_ID', sa.Integer(), nullable=False),
        sa.Column('APPL_RELATION_TYPE_DESC', sa.Text(), nullable=False),
        schema='drug_database',
    )

    # RAPPLTD0_FDA_APPL_TYPE â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RAPPLTD0
    op.create_table(
        "rappltd0_fda_appl_type",
        sa.Column('APPL_TYPE_CD', sa.Integer(), nullable=False),
        sa.Column('APPL_TYPE_CD_DESC', sa.Text(), nullable=False),
        schema='drug_database',
    )

    # RATCD0_ATC_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RATCD0
    op.create_table(
        "ratcd0_atc_desc",
        sa.Column('ATC', sa.Text(), nullable=False),
        sa.Column('ATC_DESC', sa.Text(), nullable=True),
        schema='drug_database',
    )

    # RBLANG0_NAME_GRP_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RBLANG0
    op.create_table(
        "rblang0_name_grp_desc",
        sa.Column('BIOLOGIC_NAME_GROUPER_ID', sa.Integer(), nullable=False),
        sa.Column('BIOLOGIC_NAME_GROUPER_DESC', sa.Text(), nullable=False),
        schema='drug_database',
    )

    # RBLASG0_SUBSTANCE_GRP_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RBLASG0
    op.create_table(
        "rblasg0_substance_grp_desc",
        sa.Column('SUBSTANCE_GROUP_ID', sa.Integer(), nullable=False),
        sa.Column('SUBSTANCE_GROUP_DESC', sa.Text(), nullable=False),
        schema='drug_database',
    )

    # RDCCD0_DRUG_CAT_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RDCCD0
    op.create_table(
        "rdccd0_drug_cat_desc",
        sa.Column('DCC', sa.Text(), nullable=False),
        sa.Column('DCC_DESC', sa.Text(), nullable=True),
        schema='drug_database',
    )

    # RETCCTD0_ETC_CHANGE_TYPE_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RETCCTD0
    op.create_table(
        "retcctd0_etc_change_type_desc",
        sa.Column('ETC_CHANGE_TYPE_CODE', sa.Text(), nullable=False),
        sa.Column('ETC_CHANGE_TYPE_CODE_DESC', sa.Text(), nullable=True),
        schema='drug_database',
    )

    # RGTCD0_GEN_THERAP_CLASS_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RGTCD0
    op.create_table(
        "rgtcd0_gen_therap_class_desc",
        sa.Column('GTC', sa.Integer(), nullable=False),
        sa.Column('GTC_DESC', sa.Text(), nullable=True),
        schema='drug_database',
    )

    # RHICSCD0_ING_STAT_CD_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RHICSCD0
    op.create_table(
        "rhicscd0_ing_stat_cd_desc",
        sa.Column('ING_STATUS_CD', sa.Integer(), nullable=False),
        sa.Column('ING_STATUS_CD_DESC', sa.Text(), nullable=True),
        schema='drug_database',
    )

    # RMEDCD0_MED_CONCEPT_TYP_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RMEDCD0
    op.create_table(
        "rmedcd0_med_concept_typ_desc",
        sa.Column('MED_CONCEPT_ID_TYP', sa.Integer(), nullable=False),
        sa.Column('MED_CONCEPT_ID_TYP_DESC', sa.Text(), nullable=True),
        schema='drug_database',
    )

    # RMEDMRD0_MOVE_REASON_DESC â€” tier=A delta=UPSERT_BY_NATURAL_KEY record_counts_key=RMEDMRD0
    op.create_table(
        "rmedmrd0_move_reason_desc",
        sa.Column('MOVE_REASON_CD', sa.Integer(), nullable=False),
        sa.Column('MOVE_REASON_CD_DESC', sa.Text(), nullable=False),
        schema='drug_database',
    )

        "rhicrh0_ing_hist",
        "rmidfrh1_routed_dose_form_hist",
        "rminmrh1_med_name_hist",
        "rmirh1_med_hist",
        "rmirmrh1_routed_med_hist",
        "retcsch0_etc_search",
        "retcxrf0_etc_hic3_etc",
        "rpeial0_df_attribute_link",
        "rpeigl0_gen_df_mstr_link",
        "rpeiml0_med_df_mstr_link",
        "rpeiol0_ovw_df_mstr_link",
        "rpeirer0_related_rt",
        "rpeirh0_rt_hierarchy",
        "rpeiuc0_uom_conversion",
        "runitsd0_units_desc",
        "rxrnsrc0_source_desc",
        "rblahic0_ingredients",
        "rblapn0_proprietary_name",
        "rmedmgl0_med_generic_med_link",
        "rmedmhl0_med_hiclseqno_link",
        "rprdpc0_ext_product_cd",
        "rxrfahx0_agcsp_hicseqn",
        "rxrfddx0_dacn_agcsp",
        "rxrgdfq0_gcdf_script_qq",
        "rxrmdfq0_meddosfm_script_qq",
        "rxrncqq0_qq_mstr",
        "rxrpdfq0_poemdosfm_script_qq",
    ):
        for _role in _APP_ROLES:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.{_table} TO {_role}")


def downgrade() -> None:
    op.drop_table("rxrpdfq0_poemdosfm_script_qq", schema=_SCHEMA)
    op.drop_table("rxrncqq0_qq_mstr", schema=_SCHEMA)
    op.drop_table("rxrmdfq0_meddosfm_script_qq", schema=_SCHEMA)
    op.drop_table("rxrgdfq0_gcdf_script_qq", schema=_SCHEMA)
    op.drop_table("rxrfddx0_dacn_agcsp", schema=_SCHEMA)
    op.drop_table("rxrfahx0_agcsp_hicseqn", schema=_SCHEMA)
    op.drop_table("rprdpc0_ext_product_cd", schema=_SCHEMA)
    op.drop_table("rmedmhl0_med_hiclseqno_link", schema=_SCHEMA)
    op.drop_table("rmedmgl0_med_generic_med_link", schema=_SCHEMA)
    op.drop_table("rblapn0_proprietary_name", schema=_SCHEMA)
    op.drop_table("rblahic0_ingredients", schema=_SCHEMA)
    op.drop_table("rxrnsrc0_source_desc", schema=_SCHEMA)
    op.drop_table("runitsd0_units_desc", schema=_SCHEMA)
    op.drop_table("rpeiuc0_uom_conversion", schema=_SCHEMA)
    op.drop_table("rpeirh0_rt_hierarchy", schema=_SCHEMA)
    op.drop_table("rpeirer0_related_rt", schema=_SCHEMA)
    op.drop_table("rpeiol0_ovw_df_mstr_link", schema=_SCHEMA)
    op.drop_table("rpeiml0_med_df_mstr_link", schema=_SCHEMA)
    op.drop_table("rpeigl0_gen_df_mstr_link", schema=_SCHEMA)
    op.drop_table("rpeial0_df_attribute_link", schema=_SCHEMA)
    op.drop_table("retcxrf0_etc_hic3_etc", schema=_SCHEMA)
    op.drop_table("retcsch0_etc_search", schema=_SCHEMA)
    op.drop_table("rmirmrh1_routed_med_hist", schema=_SCHEMA)
    op.drop_table("rmirh1_med_hist", schema=_SCHEMA)
    op.drop_table("rminmrh1_med_name_hist", schema=_SCHEMA)
    op.drop_table("rmidfrh1_routed_dose_form_hist", schema=_SCHEMA)
    op.drop_table("rhicrh0_ing_hist", schema=_SCHEMA)
    op.drop_table("retcnmh0_etc_med_name_id_hist", schema=_SCHEMA)
    op.drop_table("retchlh0_etc_hiclseqno_hist", schema=_SCHEMA)
    op.drop_table("retchch0_etc_hicseqn_hist", schema=_SCHEMA)
    op.drop_table("rtmrmid1_tm_routed_med", schema=_SCHEMA)
    op.drop_table("rtmnmid1_tm_med_name", schema=_SCHEMA)
    op.drop_table("rtmngn0_tm_gnn", schema=_SCHEMA)
    op.drop_table("rtmmid1_tm_med", schema=_SCHEMA)
    op.drop_table("rtmdfid1_tm_routed_df_med", schema=_SCHEMA)
    op.drop_table("rtmsrcd1_tm_source_desc", schema=_SCHEMA)
    op.drop_table("rtmngt0_tm_gnn_type", schema=_SCHEMA)
    op.drop_table("rtmgrpd1_tm_group_desc", schema=_SCHEMA)
    op.drop_table("rtmdt0_tm_name_type", schema=_SCHEMA)
    op.drop_table("rtcd0_std_therap_class_desc", schema=_SCHEMA)
    op.drop_table("rstruom0_strength_uom", schema=_SCHEMA)
    op.drop_table("rstrtd0_strength_typ_desc", schema=_SCHEMA)
    op.drop_table("rstrscd0_strength_status_desc", schema=_SCHEMA)
    op.drop_table("rstr1_strngth_desc", schema=_SCHEMA)
    op.drop_table("rrtgnsd0_rtd_gen_status_dsc", schema=_SCHEMA)
    op.drop_table("rrtgn0_routed_gen_mstr", schema=_SCHEMA)
    op.drop_table("rrouted3_route_desc", schema=_SCHEMA)
    op.drop_table("rprduom0_price_qty_uom", schema=_SCHEMA)
    op.drop_table("rprdsd0_product_status_desc", schema=_SCHEMA)
    op.drop_table("rprdpkd0_package_desc", schema=_SCHEMA)
    op.drop_table("rprdpcd0_ext_product_cd_desc", schema=_SCHEMA)
    op.drop_table("rprdpav0_price_attr_value_desc", schema=_SCHEMA)
    op.drop_table("rprdpat0_price_attr_type_desc", schema=_SCHEMA)
    op.drop_table("rndcvd0_ndc_attribute_valu_dsc", schema=_SCHEMA)
    op.drop_table("rndctd0_ndc_attribute_typ_dsc", schema=_SCHEMA)
    op.drop_table("rprdpad0_price_attr_desc", schema=_SCHEMA)
    op.drop_table("rprdcc0_currency_cd_desc", schema=_SCHEMA)
    op.drop_table("rpeiut0_uom_type_desc", schema=_SCHEMA)
    op.drop_table("rpeist0_str_conc_type", schema=_SCHEMA)
    op.drop_table("rpeirl0_rt_labeled_desc", schema=_SCHEMA)
    op.drop_table("rpeipp0_patient_param_req_desc", schema=_SCHEMA)
    op.drop_table("rpeidt0_dosage_form_type", schema=_SCHEMA)
    op.drop_table("rpeidm0_dosage_form_mstr", schema=_SCHEMA)
    op.drop_table("rpeidfa0_dosage_form_attribute", schema=_SCHEMA)
    op.drop_table("rpeiav0_attribute_value_desc", schema=_SCHEMA)
    op.drop_table("rpeiat0_attribute_type_desc", schema=_SCHEMA)
    op.drop_table("rpeiad0_attribute_desc", schema=_SCHEMA)
    op.drop_table("robcd0_obc_desc", schema=_SCHEMA)
    op.drop_table("rmiscd1_status_desc", schema=_SCHEMA)
    op.drop_table("rmirtd1_route", schema=_SCHEMA)
    op.drop_table("rmirmid1_routed_med", schema=_SCHEMA)
    op.drop_table("rminmd1_med_name_type_desc", schema=_SCHEMA)
    op.drop_table("rminamd1_name_src_desc", schema=_SCHEMA)
    op.drop_table("rmimltd1_ref_multi_src_desc", schema=_SCHEMA)
    op.drop_table("rmilgnd1_ref_fed_lgnd_desc", schema=_SCHEMA)
    op.drop_table("rmiinnd1_ref_innov_ind_desc", schema=_SCHEMA)
    op.drop_table("rmigscd1_ref_gen_prc_sprd_desc", schema=_SCHEMA)
    op.drop_table("rmigpcd1_ref_gen_prc_desc", schema=_SCHEMA)
    op.drop_table("rmigncd1_ref_gen_name_desc", schema=_SCHEMA)
    op.drop_table("rmigecd1_ref_gen_therap_desc", schema=_SCHEMA)
    op.drop_table("rmigcnd1_gcnseqno_assgn_desc", schema=_SCHEMA)
    op.drop_table("rmidfid1_routed_dose_form_med", schema=_SCHEMA)
    op.drop_table("rmidfd1_dose_form", schema=_SCHEMA)
    op.drop_table("rmidesd1_ref_desi_ind_desc", schema=_SCHEMA)
    op.drop_table("rmidead1_ref_fed_dea_desc", schema=_SCHEMA)
    op.drop_table("rmide2d1_ref_desi2_ind_desc", schema=_SCHEMA)
    op.drop_table("rmedstd0_search_term_type_desc", schema=_SCHEMA)
    op.drop_table("rmedst0_medid_search_term", schema=_SCHEMA)
    op.drop_table("rmedspd0_specification_desc", schema=_SCHEMA)
    op.drop_table("rlblrid3_lblr_desc", schema=_SCHEMA)
    op.drop_table("rhic3d3_hic_therap_class_desc", schema=_SCHEMA)
    op.drop_table("rhic2d3_hic_rx_class_desc", schema=_SCHEMA)
    op.drop_table("rhic1d2_hic_organ_sys_desc", schema=_SCHEMA)
    op.drop_table("rdosed2_dose_desc", schema=_SCHEMA)
    op.drop_table("raplt0_appl_type", schema=_SCHEMA)
    op.drop_table("rmedmrd0_move_reason_desc", schema=_SCHEMA)
    op.drop_table("rmedcd0_med_concept_typ_desc", schema=_SCHEMA)
    op.drop_table("rhicscd0_ing_stat_cd_desc", schema=_SCHEMA)
    op.drop_table("rgtcd0_gen_therap_class_desc", schema=_SCHEMA)
    op.drop_table("retcctd0_etc_change_type_desc", schema=_SCHEMA)
    op.drop_table("rdccd0_drug_cat_desc", schema=_SCHEMA)
    op.drop_table("rblasg0_substance_grp_desc", schema=_SCHEMA)
    op.drop_table("rblang0_name_grp_desc", schema=_SCHEMA)
    op.drop_table("ratcd0_atc_desc", schema=_SCHEMA)
    op.drop_table("rappltd0_fda_appl_type", schema=_SCHEMA)
    op.drop_table("raplrt0_appl_relation_type", schema=_SCHEMA)
    op.drop_table("rahfsd1_desc", schema=_SCHEMA)

codex
The first migration sample shows table creation and grants but no primary key or unique constraints in the visible part. I’m checking the adapter contract now because UPSERT_BY_NATURAL_KEY only has real database protection if the migration creates a matching uniqueness surface or the loader implements a different replacement strategy.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "class TableSpec|DeltaSemantics|natural|conflict|upsert|ON CONFLICT|append_only|make_sqlite_simulator" modules/drug-database/drug_database/services modules/drug-database/tests/unit -g "*.py"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"sa\\.PrimaryKeyConstraint|sa\\.UniqueConstraint|primary_key=True|create_index|unique=True\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py modules/drug-database/alembic/versions/0008_fdb_pricing.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "RPEIUC0_UOM_CONVERSION|UOM_CONVERSION_FACTOR|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0|APPEND_ONLY|_parse_fdb_date|Decimal" modules/drug-database/drug_database/services/fdb_tier_a modules/drug-database/tests/unit/test_fdb_tier_a_batch_*.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -c \"TableSpec\\(\" modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py; rg -c \"op\\.create_table\\(\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py; rg -c \"op\\.drop_table\\(\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
2026-05-12T14:54:28.147541Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.7 seconds
Output:
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:5:(DOSAGE_FORM_RETIRE_DT) which requires the `_parse_fdb_date` coercer
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:28:    _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:61:    # DOSAGE_FORM_RETIRE_DT is DATE: uses _parse_fdb_date (YYYYMMDD→date).
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:76:            "DOSAGE_FORM_RETIRE_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:16:    Decimal money columns and no Date columns (those are Tier B/C).
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No Date or Decimal columns
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No Date or Decimal columns
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No DATE or Decimal columns
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:16:DATE columns use `_parse_fdb_date` from fdb_adapter (same as
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:25:    _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:45:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:68:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:91:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:106:            "HIC_REPL_EFF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:125:            "MED_ROUTED_DF_MED_ID_REP_EF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:140:            "MED_NAME_ID_REPL_EFF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:154:            "MED_MEDID_REPL_EFF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:172:            "MED_ROUTED_MED_ID_REPL_EFF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:25:    RPEIUC0_UOM_CONVERSION      — (FROM_UOM_MSTR_ID, TO_UOM_MSTR_ID) + UOM_CONVERSION_FACTOR
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:46:from decimal import Decimal
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:210:        table_name="RPEIUC0_UOM_CONVERSION",
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:214:            "UOM_CONVERSION_FACTOR",
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:219:            "UOM_CONVERSION_FACTOR": Decimal,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:287:    "RPEIUC0_UOM_CONVERSION": 2,      # NK=2, conversion factor is 3rd col
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:14:All DATE columns use `_parse_fdb_date` (YYYYMMDD → datetime.date).
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:30:    _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:93:            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:118:            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:141:            "EXT_PRODUCT_CD_START_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:143:            "EXT_PRODUCT_CD_END_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:173:        table_name="RXRFDDX0_DACN_AGCSP",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:184:        record_counts_key="RXRFDDX0",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:190:        table_name="RXRGDFQ0_GCDF_SCRIPT_QQ",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:201:        record_counts_key="RXRGDFQ0",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:207:        table_name="RXRMDFQ0_MEDDOSFM_SCRIPT_QQ",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:218:        record_counts_key="RXRMDFQ0",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:237:            "OBSOLETE_DATE": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:248:        table_name="RXRPDFQ0_POEMDOSFM_SCRIPT_QQ",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:259:        record_counts_key="RXRPDFQ0",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:276:    "RXRFDDX0_DACN_AGCSP": 2,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:277:    "RXRGDFQ0_GCDF_SCRIPT_QQ": 2,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:278:    "RXRMDFQ0_MEDDOSFM_SCRIPT_QQ": 2,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:280:    "RXRPDFQ0_POEMDOSFM_SCRIPT_QQ": 2,
rg: modules/drug-database/tests/unit/test_fdb_tier_a_batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)

 succeeded in 776ms:
modules/drug-database/alembic/versions/0008_fdb_pricing.py:62:            primary_key=True, autoincrement=True,
modules/drug-database/alembic/versions/0008_fdb_pricing.py:119:        sa.UniqueConstraint(
modules/drug-database/alembic/versions/0008_fdb_pricing.py:136:    op.create_index(
modules/drug-database/alembic/versions/0008_fdb_pricing.py:149:    op.create_index(
modules/drug-database/alembic/versions/0008_fdb_pricing.py:153:    op.create_index(
modules/drug-database/alembic/versions/0008_fdb_pricing.py:165:            "price_type_id", sa.Integer, primary_key=True,
modules/drug-database/alembic/versions/0008_fdb_pricing.py:192:    op.create_index(

 exited 1 in 651ms:
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:5:(DOSAGE_FORM_RETIRE_DT) which requires the `_parse_fdb_date` coercer
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:28:    _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:61:    # DOSAGE_FORM_RETIRE_DT is DATE: uses _parse_fdb_date (YYYYMMDD→date).
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:76:            "DOSAGE_FORM_RETIRE_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:16:    Decimal money columns and no Date columns (those are Tier B/C).
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No Date or Decimal columns
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No Date or Decimal columns
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No DATE or Decimal columns
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:16:DATE columns use `_parse_fdb_date` from fdb_adapter (same as
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:25:    _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:45:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:68:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:91:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:106:            "HIC_REPL_EFF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:125:            "MED_ROUTED_DF_MED_ID_REP_EF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:140:            "MED_NAME_ID_REPL_EFF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:154:            "MED_MEDID_REPL_EFF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:172:            "MED_ROUTED_MED_ID_REPL_EFF_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:25:    RPEIUC0_UOM_CONVERSION      — (FROM_UOM_MSTR_ID, TO_UOM_MSTR_ID) + UOM_CONVERSION_FACTOR
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:46:from decimal import Decimal
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:210:        table_name="RPEIUC0_UOM_CONVERSION",
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:214:            "UOM_CONVERSION_FACTOR",
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:219:            "UOM_CONVERSION_FACTOR": Decimal,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:287:    "RPEIUC0_UOM_CONVERSION": 2,      # NK=2, conversion factor is 3rd col
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:14:All DATE columns use `_parse_fdb_date` (YYYYMMDD → datetime.date).
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:30:    _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:93:            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:118:            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:141:            "EXT_PRODUCT_CD_START_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:143:            "EXT_PRODUCT_CD_END_DT": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:173:        table_name="RXRFDDX0_DACN_AGCSP",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:184:        record_counts_key="RXRFDDX0",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:190:        table_name="RXRGDFQ0_GCDF_SCRIPT_QQ",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:201:        record_counts_key="RXRGDFQ0",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:207:        table_name="RXRMDFQ0_MEDDOSFM_SCRIPT_QQ",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:218:        record_counts_key="RXRMDFQ0",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:237:            "OBSOLETE_DATE": _parse_fdb_date,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:248:        table_name="RXRPDFQ0_POEMDOSFM_SCRIPT_QQ",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:259:        record_counts_key="RXRPDFQ0",
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:276:    "RXRFDDX0_DACN_AGCSP": 2,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:277:    "RXRGDFQ0_GCDF_SCRIPT_QQ": 2,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:278:    "RXRMDFQ0_MEDDOSFM_SCRIPT_QQ": 2,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:280:    "RXRPDFQ0_POEMDOSFM_SCRIPT_QQ": 2,
rg: modules/drug-database/tests/unit/test_fdb_tier_a_batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)

 succeeded in 792ms:
modules/drug-database/tests/unit\test_fdb_adapter.py:46:    DeltaSemantics,
modules/drug-database/tests/unit\test_fdb_adapter.py:559:# B9.A C1 — TableSpec registry expansion: Tier + DeltaSemantics + 4 new fields
modules/drug-database/tests/unit\test_fdb_adapter.py:573:    """DeltaSemantics taxonomy per codex ADVERSARIAL R1 A4 mitigation."""
modules/drug-database/tests/unit\test_fdb_adapter.py:574:    assert DeltaSemantics.APPEND_ONLY.value == "APPEND_ONLY"
modules/drug-database/tests/unit\test_fdb_adapter.py:575:    assert DeltaSemantics.UPSERT_BY_NATURAL_KEY.value == "UPSERT_BY_NATURAL_KEY"
modules/drug-database/tests/unit\test_fdb_adapter.py:576:    assert DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE.value == "UPSERT_WITH_EFFECTIVE_DATE"
modules/drug-database/tests/unit\test_fdb_adapter.py:577:    assert DeltaSemantics.TRUNCATE_RELOAD.value == "TRUNCATE_RELOAD"
modules/drug-database/tests/unit\test_fdb_adapter.py:578:    assert DeltaSemantics.UNKNOWN.value == "UNKNOWN"
modules/drug-database/tests/unit\test_fdb_adapter.py:593:        assert spec.delta_semantics is DeltaSemantics.UNKNOWN, spec.table_name
modules/drug-database/tests/unit\test_fdb_adapter.py:605:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_adapter.py:610:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY
modules/drug-database/drug_database/services\fda_ndc_parser.py:3:Parses the FDA NDC JSON/CSV export into DrugProduct dicts ready for upsert.
modules/drug-database/tests/unit\test_fdb_contract.py:19:    DeltaSemantics,
modules/drug-database/tests/unit\test_fdb_contract.py:53:    delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_contract.py:414:    def __init__(self, natural_key_fields: tuple[str, ...]) -> None:
modules/drug-database/tests/unit\test_fdb_contract.py:416:        self._key = natural_key_fields
modules/drug-database/tests/unit\test_fdb_contract.py:434:    """Simulates the regression A4 guards against: ON CONFLICT DO NOTHING."""
modules/drug-database/tests/unit\test_fdb_contract.py:439:            self._rows.setdefault(k, dict(row))  # NOTHING on conflict
modules/drug-database/tests/unit\test_fdb_contract.py:447:def test_delta_semantics_upsert_by_natural_key_passes_correct_impl() -> None:
modules/drug-database/tests/unit\test_fdb_contract.py:452:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_contract.py:454:    sim = _InMemoryUpsertStore(natural_key_fields=("id",))
modules/drug-database/tests/unit\test_fdb_contract.py:457:        natural_key={"id": 42},
modules/drug-database/tests/unit\test_fdb_contract.py:464:def test_delta_semantics_upsert_FAILS_on_silent_conflict_do_nothing() -> None:
modules/drug-database/tests/unit\test_fdb_contract.py:470:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_contract.py:472:    sim = _BrokenUpsertStore(natural_key_fields=("id",))
modules/drug-database/tests/unit\test_fdb_contract.py:476:            natural_key={"id": 42},
modules/drug-database/tests/unit\test_fdb_contract.py:489:        delta_semantics=DeltaSemantics.UNKNOWN,
modules/drug-database/tests/unit\test_fdb_contract.py:497:        natural_key={"id": 1},
modules/drug-database/tests/unit\test_fdb_contract.py:504:def test_delta_semantics_append_only_expects_history_growth() -> None:
modules/drug-database/tests/unit\test_fdb_contract.py:509:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit\test_fdb_contract.py:520:        natural_key={"ndc_11": "00000000001"},
modules/drug-database/tests/unit\test_fdb_contract.py:533:        delta_semantics=DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
modules/drug-database/tests/unit\test_fdb_contract.py:547:        natural_key={"id": 1},
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:26:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:32:    DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:33:    DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:34:    DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:43:# Parallel agents own their own batch_N file; no merge conflict here.
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:111:        f"'ON CONFLICT DO NOTHING' bug could ship undetected."
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:19:    DeltaSemantics,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:28:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:39:# UPSERT_BY_NATURAL_KEY — correct INSERT...ON CONFLICT DO UPDATE
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:43:def test_upsert_by_natural_key_passes_with_real_sqlite_upsert(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:47:        table_name="upsert_ok",
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:51:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:53:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:55:        table_name="upsert_ok",
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:56:        natural_key_columns=("id",),
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:58:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:63:            natural_key={"id": 1},
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:72:def test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:75:    """A4 regression detector: ON CONFLICT DO NOTHING silently drops C.
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:83:        table_name="upsert_broken",
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:87:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:89:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:91:        table_name="upsert_broken",
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:92:        natural_key_columns=("id",),
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:94:        conflict_action="nothing",  # ← the regression
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:100:                natural_key={"id": 1},
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:110:# APPEND_ONLY — every operation appends a row (no conflict resolution)
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:114:def test_append_only_passes_when_every_tx_grows_history(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:122:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:124:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:127:        natural_key_columns=("entity_id",),
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:129:        append_only=True,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:134:            natural_key={"entity_id": 99},
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:148:def test_upsert_with_effective_date_passes_when_c_opens_new_row(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:156:        delta_semantics=DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:158:    # Effective-dated tables use (id, eff_date) as the conflict target
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:160:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:163:        natural_key_columns=("id", "eff_date"),
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:165:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:170:            natural_key={"id": 1, "eff_date": "20260101"},  # bound to step A's row
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:172:            # C carries a NEW eff_date — natural key shifts, new row appears.
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:190:        delta_semantics=DeltaSemantics.UNKNOWN,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:201:        natural_key={"id": 1},
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:213:        delta_semantics=DeltaSemantics.TRUNCATE_RELOAD,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:224:        natural_key={"id": 1},
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:232:# make_sqlite_simulator — input validation
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:236:def test_simulator_rejects_append_only_with_explicit_conflict_action(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:239:    """Operator can't claim append_only + a conflict_action — surface the contradiction."""
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:241:        make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:244:            natural_key_columns=("id",),
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:246:            append_only=True,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:247:            conflict_action="nothing",
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:251:def test_simulator_rejects_unknown_conflict_action(sqlite_engine: Engine) -> None:
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:252:    with pytest.raises(ValueError, match="conflict_action must be"):
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:253:        make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:256:            natural_key_columns=("id",),
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:258:            conflict_action="weird",
modules/drug-database/tests/unit\test_fdb_loader_registry.py:27:    DeltaSemantics,
modules/drug-database/tests/unit\test_fdb_loader_registry.py:47:    delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit\test_fdb_pricing_ingester.py:408:# ON CONFLICT DO NOTHING — collision counting (Phase 10 / Item 4)
modules/drug-database/tests/unit\test_fdb_pricing_ingester.py:412:def test_replay_uses_on_conflict_do_nothing(initial_drop, db_session):
modules/drug-database/tests/unit\test_fdb_pricing_ingester.py:413:    """ON CONFLICT DO NOTHING skips duplicates atomically in a single round-trip.
modules/drug-database/tests/unit\test_fdb_pricing_ingester.py:418:    drop_sequence) is what triggers the conflict, not the PK.
modules/drug-database/tests/unit\test_fdb_pricing_ingester.py:423:    verifying the ON CONFLICT path returns correct inserted/duplicate counts
modules/drug-database/tests/unit\test_fdb_pricing_ingester.py:434:    # isolating the composite-UC conflict from any PK conflict.
modules/drug-database/tests/unit\test_fdb_pricing_ingester.py:453:    # Row count unchanged — ON CONFLICT DO NOTHING is a no-op.
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:20:  re-run of the same drop produces 0 net new rows — ON CONFLICT DO
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:362:    # Composite UC columns — used as the conflict target on SQLite, which
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:363:    # does not support named-constraint conflict targets in SQLAlchemy's
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:380:        """Flush one batch using ON CONFLICT DO NOTHING — one commit per batch.
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:383:          Postgres — pg_insert().on_conflict_do_nothing(constraint=
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:387:          SQLite   — sqlite_insert().on_conflict_do_nothing(index_elements=
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:389:                     dialect does not accept named constraints as conflict
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:431:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:434:            # SQLite (test environment) — column-list conflict target.
modules/drug-database/drug_database/services\fdb_pricing_ingester.py:438:                .on_conflict_do_nothing(index_elements=list(self._UC_COLUMNS))
modules/drug-database/drug_database/services\fdb_adapter.py:168:class DeltaSemantics(Enum):
modules/drug-database/drug_database/services\fdb_adapter.py:172:    `ON CONFLICT DO NOTHING` proves replay safety but NOT delta
modules/drug-database/drug_database/services\fdb_adapter.py:174:    is silently ignored if the conflict key is natural-key only.
modules/drug-database/drug_database/services\fdb_adapter.py:179:      UPSERT_BY_NATURAL_KEY      — most reference tables; ON CONFLICT DO UPDATE
modules/drug-database/drug_database/services\fdb_adapter.py:181:      TRUNCATE_RELOAD            — tables w/o stable natural key, full reload
modules/drug-database/drug_database/services\fdb_adapter.py:196:class TableSpec:
modules/drug-database/drug_database/services\fdb_adapter.py:244:    delta_semantics: DeltaSemantics = DeltaSemantics.UNKNOWN
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:10:    (the dominant Tier A pattern — code→desc lookups upsert on the
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:11:    natural key; weekly delta = corrections).
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:28:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:44:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:54:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:64:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:75:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:88:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:98:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:123:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:134:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:145:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:156:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:166:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:4:shared/. REMS was extracted in Wave 9d — its upsert path lives in
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:5:shared/data_ingestion/sources/fda_rems.py directly, using flush_upsert_batch
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:9:  DrugShortagesIngestionService — drug_database.drug_shortages (upsert) + drug_shortages_history (append)
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:10:  PurpleBookIngestionService   — drug_database.drug_purple_book (upsert)
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:14:  - INSERT ON CONFLICT DO UPDATE for current-state tables.
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:15:  - INSERT only (no conflict clause) for drug_shortages_history.
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:16:  - PostgreSQL pg_insert used for upserts.
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:18:These two services are candidates for the same flush_upsert_batch refactor
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:54:# RemsIngestionService was removed in Wave 9d. REMS upsert path now lives
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:55:# inline in shared/data_ingestion/sources/fda_rems.py using flush_upsert_batch
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:57:# a single bulk DELETE + INSERT after the parent upsert commits.
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:67:    """Batch upsert/append service for FDA Drug Shortages.
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:69:    drug_shortages: INSERT ON CONFLICT DO UPDATE.
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:70:    drug_shortages_history: append-only INSERT (no conflict clause).
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:94:                ins, upd, err, smp = self._upsert_shortages_batch(rows, today)
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:102:            ins, upd, err, smp = self._upsert_shortages_batch(rows, today)
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:130:    def _upsert_shortages_batch(
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:165:                stmt = stmt.on_conflict_do_update(
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:210:                    "Drug shortage row upsert error",
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:229:    """Batch upsert service for FDA Purple Book (biologics).
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:254:                ins, upd, err, smp = self._upsert_purple_book_batch(rows)
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:262:            ins, upd, err, smp = self._upsert_purple_book_batch(rows)
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:290:    def _upsert_purple_book_batch(
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:326:                    stmt = stmt.on_conflict_do_update(
modules/drug-database/drug_database/services\fda_supplementary_ingestion.py:356:                    "Purple Book row upsert error",
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:16:  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:24:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:43:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:54:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:65:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:81:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:98:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:122:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:144:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:157:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:167:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:12:  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:22:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:37:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:47:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:61:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:83:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:93:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:106:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:119:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:132:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:145:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:155:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:33:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:44:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:121:    natural key is the FIRST column; the second column is the
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:123:    restores. Correct UPSERT (ON CONFLICT DO UPDATE) passes all four
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:126:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:131:    natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:135:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:138:        natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:140:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:145:            natural_key={natural_key_col: "key_val_42"},
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:22:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:40:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:53:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:66:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:79:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:81:    # Routed medication (5 columns; natural key = ROUTED_MED_ID, first col)
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:101:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:115:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:128:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:143:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:164:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:185:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:109:    natural key is the FIRST column; the second column is the
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:112:    Correct UPSERT (ON CONFLICT DO UPDATE) passes all four sub-assertions
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:116:    dict keys into the supplied row for every non-natural-key column, so
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:126:    natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:136:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:139:        natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:141:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:146:            natural_key={natural_key_col: "key_val_42"},
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:25:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:36:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:112:    Each Tier A table is UPSERT_BY_NATURAL_KEY: the natural key is the
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:115:    deletes; re-A restores. Correct UPSERT (ON CONFLICT DO UPDATE)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:124:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:129:    natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:139:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:142:        natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:144:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:149:            natural_key={natural_key_col: "key_val_42"},
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:109:    natural key is the FIRST column; the second column is the
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:112:    Correct UPSERT (ON CONFLICT DO UPDATE) passes all four sub-assertions
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:116:    dict keys into the supplied row for every non-natural-key column, so
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:126:    natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:136:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:139:        natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:141:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:146:            natural_key={natural_key_col: "key_val_42"},
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:25:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:45:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:58:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:83:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:96:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:122:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:135:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:148:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:161:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:182:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:109:    natural key is the FIRST column; the second column is the
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:112:    Correct UPSERT (ON CONFLICT DO UPDATE) passes all four sub-assertions
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:116:    dict keys into the supplied row for every non-natural-key column, so
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:126:    natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:136:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:139:        natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:141:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:146:            natural_key={natural_key_col: "key_val_42"},
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:27:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:38:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:115:    natural key is the FIRST column; the second column is used as the
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:118:    changed_values as required by the SQLite simulator's ON CONFLICT
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:126:    natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:128:    non_key_cols = [c for c in spec.columns if c != natural_key_col]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:132:    # the simulator's ON CONFLICT DO UPDATE set_ dict can be constructed
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:137:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:140:        natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:142:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:147:            natural_key={natural_key_col: "key_val_42"},
modules/drug-database/drug_database/services\pricing_ingestion.py:3:This file used to hand-roll per-batch commits, in-batch dedup, ON CONFLICT
modules/drug-database/drug_database/services\pricing_ingestion.py:4:upserts, and history-row emission in ~500 lines of boilerplate — one copy for
modules/drug-database/drug_database/services\pricing_ingestion.py:74:    """Batch upsert service for CMS NADAC pricing data.
modules/drug-database/drug_database/services\pricing_ingestion.py:92:        """Stream and upsert NADAC records through :class:`BatchedUpserter`."""
modules/drug-database/drug_database/services\pricing_ingestion.py:93:        upserter = BatchedUpserter(
modules/drug-database/drug_database/services\pricing_ingestion.py:107:        return upserter.load(records)
modules/drug-database/drug_database/services\pricing_ingestion.py:185:    """Batch upsert service for CMS ASP pricing data.
modules/drug-database/drug_database/services\pricing_ingestion.py:200:        upserter = BatchedUpserter(
modules/drug-database/drug_database/services\pricing_ingestion.py:214:        return upserter.load(records)
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:22:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:40:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:58:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:79:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:98:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:121:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:141:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:160:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:173:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:196:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:218:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:22:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:41:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:58:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:72:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:86:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:102:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:116:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:130:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:144:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:158:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:172:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:3:The previous batches all used single-column natural keys. Batch 08
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:10:  1. natural_key dict has multiple entries (all spec.columns except
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:12:  2. Simulator's `natural_key_columns` is a tuple of those column names.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:24:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:90:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:98:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:101:        natural_key_columns=nk_cols,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:103:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:106:        # Build natural_key dict — placeholder values for every NK column.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:107:        natural_key = {
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:112:            natural_key=natural_key,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:144:    """Every batch_08 spec has multi-column natural key per NATURAL_KEY_COUNT."""
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:3:This batch mixes single-column and multi-column natural keys:
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:13:            natural_key dict; last column as the changed value.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:15:            col as natural_key; second col as desc; remaining cols as
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:38:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:46:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:105:    """Return a stable placeholder for a natural-key column.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:121:    NK >= 2 (composite-NK): natural_key spans the first NK columns;
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:124:    NK == 1 (single-NK): first column is the natural key; second column
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:127:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:139:        sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:142:            natural_key_columns=nk_cols,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:144:            conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:147:            natural_key = {
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:153:                # A and C carry the same full-NK row; ON CONFLICT DO NOTHING
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:157:                    natural_key=natural_key,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:186:                    natural_key=natural_key,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:199:        natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:211:        sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:214:            natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:216:            conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:221:                natural_key={natural_key_col: "key_val_42"},
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:252:def test_spec_natural_key_count_registered(spec) -> None:
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:269:def test_natural_key_count_covers_all_specs() -> None:
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:109:    natural key is the FIRST column; the second column is the
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:112:    Correct UPSERT (ON CONFLICT DO UPDATE) passes all four sub-assertions
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:116:    dict keys into the supplied row for every non-natural-key column, so
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:126:    natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:136:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:139:        natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:141:        conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:146:            natural_key={natural_key_col: "key_val_42"},
modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:9:                3-column natural key
modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:23:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:48:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:63:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:85:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:105:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:125:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:130:# Number of natural-key columns per spec — drives the test's
modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:132:# is: all columns except the LAST are the natural key; the LAST is
modules/drug-database/drug_database/services\nadac_parser.py:3:Parses CMS NADAC CSV into DrugPricing dicts ready for upsert.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:5:simulator uses `append_only=True` (not `conflict_action="upsert"`),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:17:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:25:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:77:def test_delta_semantics_append_only_for_each_spec(spec, sqlite_engine) -> None:
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:81:    `make_sqlite_simulator` with `append_only=True` makes every
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:82:    INSERT a plain INSERT (no ON CONFLICT), and D becomes a tombstone
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:91:    # (just count growth); the natural_key is used only for the "find row"
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:92:    # lookup, which is allowed to return None for append_only tables.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:93:    natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:95:    natural_key = {natural_key_col: "nk_42"}
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:99:    sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:102:        natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:104:        append_only=True,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:109:            natural_key=natural_key,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:140:def test_spec_uses_append_only_semantics(spec) -> None:
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:22:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:7:    batch_04 pattern — natural key is columns[0]; extra_cols fills
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:13:    simulator falls through to `on_conflict_do_nothing` because
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:19:    batch_08 pattern — first NK cols are the natural key; last column(s)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:30:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:38:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:102:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:107:    natural_key = {col: f"nk_val_{i}" for i, col in enumerate(nk_cols)}
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:114:        natural_key_col = spec.columns[0]
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:120:        sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:123:            natural_key_columns=(natural_key_col,),
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:125:            conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:130:                natural_key={natural_key_col: "key_val_42"},
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:140:        # Pure-link path: ALL columns form the natural key; no non-key
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:141:        # column exists. The simulator falls back to on_conflict_do_nothing.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:145:        sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:148:            natural_key_columns=nk_cols,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:150:            conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:155:                natural_key=natural_key,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:166:        # first nk_count cols are the natural key; last column is the
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:170:        sim, teardown = make_sqlite_simulator(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:173:            natural_key_columns=nk_cols,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:175:            conflict_action="upsert",
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:180:                natural_key=natural_key,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:211:def test_natural_key_count_entry_exists(spec) -> None:
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:34:drops update in-place by natural key; deletion is explicit A/C/D. The
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:35:link-with-indicator tables update the indicator flag on conflict; pure-
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:36:link tables have nothing to update on conflict (no-op, correct per the
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:37:simulator's `on_conflict_do_nothing` fallback for all-NK tables).
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:40:  value = number of leading columns that form the natural key.
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:49:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:72:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:90:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:108:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:128:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:148:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:168:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:186:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:204:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:224:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:245:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:264:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:269:# Number of natural-key columns per spec — drives the test's ACD cycle
modules/drug-database/tests/unit\test_gen_fdb_tier_migration.py:27:    DeltaSemantics,
modules/drug-database/tests/unit\test_gen_fdb_tier_migration.py:80:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:27:    DeltaSemantics,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:56:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:77:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:99:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:124:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:149:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:168:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:185:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:202:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:219:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:243:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:260:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:265:# Number of natural-key columns per spec — drives the test's hybrid
modules/drug-database/drug_database/services\fdb_tier_a\__init__.py:12:        DeltaSemantics, TableSpec, Tier,
modules/drug-database/drug_database/services\fdb_tier_a\__init__.py:23:            delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,

 succeeded in 691ms:
107
107
rg: modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: IO error for operation on modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/drug_database/services/fdb_adapter.py -TotalCount 330' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/scripts/gen_fdb_tier_migration.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "CONTRACT_TESTED_SPECS|BATCH_TESTED_NAMES|assert_delta_semantics_acd_cycle|if not non_nk_cols|count >= 4|APPEND_ONLY" modules/drug-database/tests/unit' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 474ms:
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
from enum import Enum
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


class Tier(Enum):
    """B9 effort-classification tier per `recon.md` Â§3.

    Phase 09 used a single tier implicitly (the 3 pricing-related
    TableSpecs were all hand-curated). B9 extends to 217 more tables
    classified by complexity:

      A â€” simple lookups, â‰¤5 cols, generic ingester (113 tables)
      B â€” NDC/GCN-keyed joins (66 tables)
      C â€” complex/large (>8 cols or >50 MB) including RNDC14 + pricing (19 tables)
      D â€” MTL (medical test lexicon), schema-only, no data load (19 tables)

    UNKNOWN is the backward-compat default for Phase 09 TableSpecs
    that pre-date the tier field. They behave as before.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    UNKNOWN = "UNKNOWN"


class DeltaSemantics(Enum):
    """How a TableSpec's weekly FDB delta should be applied.

    Codex ADVERSARIAL R1 A4 mitigation (`waves/B9/codex-adversarial-r1.md`):
    `ON CONFLICT DO NOTHING` proves replay safety but NOT delta
    correctness on mutable lookups. A D-then-re-A with changed values
    is silently ignored if the conflict key is natural-key only.

    Per-table classification:

      APPEND_ONLY                â€” immutable insert (pricing history; RNP3)
      UPSERT_BY_NATURAL_KEY      â€” most reference tables; ON CONFLICT DO UPDATE
      UPSERT_WITH_EFFECTIVE_DATE â€” time-bucketed; new row per (key, eff_date)
      TRUNCATE_RELOAD            â€” tables w/o stable natural key, full reload
      UNKNOWN                    â€” backward-compat default for Phase 09

    B9.A C8 contract test simulates A / C / D / re-A scenarios per
    semantics class to verify delta correctness, not just replay safety.
    """

    APPEND_ONLY = "APPEND_ONLY"
    UPSERT_BY_NATURAL_KEY = "UPSERT_BY_NATURAL_KEY"
    UPSERT_WITH_EFFECTIVE_DATE = "UPSERT_WITH_EFFECTIVE_DATE"
    TRUNCATE_RELOAD = "TRUNCATE_RELOAD"
    UNKNOWN = "UNKNOWN"


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

    B9 extension fields (additive; backward-compat defaults â€” Phase 09
    TableSpecs unchanged):
      tier:               effort-classification per `recon.md` Â§3.
      record_counts_key:  key for row-count reconciliation against
                          FDB's `RECORD_COUNTS.TXT` manifest.
                          Defaults to `table_name` if None.
      loader_group:       tier-loader registration label
                          (e.g., "fdb_tier_a" â€” loaders register by group).
                          Defaults to None (single-tier Phase 09 behavior).
      delta_semantics:    how weekly delta is applied â€” per codex
                          ADVERSARIAL A4 mitigation. UNKNOWN preserves
                          Phase 09 behavior (treated as APPEND_ONLY
                          downstream for backward-compat).
    """

    table_name: str
    columns: Sequence[str]
    coercers: dict[str, Callable[[str], Any]]
    nullable: frozenset[str] = field(default_factory=frozenset)
    sentinel_filter: Callable[[dict[str, Any]], bool] | None = None
    has_transaction_code: bool = False
    # B9 additive fields â€” defaults preserve Phase 09 behavior
    tier: Tier = Tier.UNKNOWN
    record_counts_key: str | None = None
    loader_group: str | None = None
    delta_semantics: DeltaSemantics = DeltaSemantics.UNKNOWN


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

 succeeded in 470ms:
"""B9.A C2 â€” Unit tests for the FDB tier migration generator.

The generator runs ONCE per tier during B9.B-G execution. Its output
becomes a real `alembic/versions/<revision>.py` file. These tests
verify the generator produces valid Python with the right structure
before any tier actually runs through it.
"""
from __future__ import annotations

import ast
from decimal import Decimal

import pytest
import sys
from pathlib import Path

# Add the scripts/ directory to path so we can import the generator.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from gen_fdb_tier_migration import (  # noqa: E402
    _sql_type_for_coercer,
    generate_tier_migration,
)

from drug_database.services.fdb_adapter import (  # noqa: E402
    DeltaSemantics,
    TableSpec,
    Tier,
)


# ---------------------------------------------------------------------------
# _sql_type_for_coercer â€” coercer â†’ SQL type mapping
# ---------------------------------------------------------------------------


def test_sql_type_for_int() -> None:
    assert _sql_type_for_coercer(int) == "sa.Integer()"


def test_sql_type_for_str() -> None:
    assert _sql_type_for_coercer(str) == "sa.Text()"


def test_sql_type_for_decimal() -> None:
    """Decimal â†’ Numeric(16,5) matches RNP3 ANSI DDL exactly (financial-precision.md)."""
    assert _sql_type_for_coercer(Decimal) == "sa.Numeric(16, 5)"


def test_sql_type_for_float_is_rejected() -> None:
    """float is forbidden for FDB columns (financial-precision rule)."""
    with pytest.raises(ValueError, match="float coercer is forbidden"):
        _sql_type_for_coercer(float)


def test_sql_type_for_unknown_coercer_raises() -> None:
    """Unknown coercers must error loudly; no silent default (ADVERSARIAL N4)."""
    def my_custom_coercer(s: str) -> object:
        return s

    with pytest.raises(ValueError, match="Unknown coercer"):
        _sql_type_for_coercer(my_custom_coercer)


# ---------------------------------------------------------------------------
# generate_tier_migration â€” full output
# ---------------------------------------------------------------------------


def _make_simple_tier_a_spec(name: str = "RMIID1_MED") -> TableSpec:
    """A minimal valid Tier A TableSpec for tests."""
    return TableSpec(
        table_name=name,
        columns=("med_name_id", "med_name"),
        coercers={"med_name_id": int, "med_name": str},
        tier=Tier.A,
        record_counts_key=name.split("_")[0],
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )


def test_generated_migration_is_valid_python() -> None:
    """ast.parse on the generator output succeeds â€” output is a real .py file."""
    specs = [_make_simple_tier_a_spec("RMIID1_MED"), _make_simple_tier_a_spec("RTGEN1_GEN")]
    src = generate_tier_migration(
        specs=specs,
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    ast.parse(src)  # raises SyntaxError on invalid Python


def test_generated_migration_has_revision_metadata() -> None:
    """Output declares the right revision + down_revision."""
    specs = [_make_simple_tier_a_spec()]
    src = generate_tier_migration(
        specs=specs,
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    assert 'revision: str = "0009_fdb_tier_a"' in src
    assert 'down_revision: Union[str, None] = "0008_fdb_pricing"' in src


def test_generated_migration_includes_all_specs_in_upgrade_and_downgrade() -> None:
    """Each spec produces a CREATE TABLE in upgrade() and a DROP in downgrade()."""
    specs = [
        _make_simple_tier_a_spec("RMIID1_MED"),
        _make_simple_tier_a_spec("RTGEN1_GEN"),
        _make_simple_tier_a_spec("RDFID1_DOSE"),
    ]
    src = generate_tier_migration(
        specs=specs,
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    # Tables present in lower-case form in op.create_table() + op.drop_table()
    assert 'op.create_table(\n        "rmiid1_med"' in src
    assert 'op.create_table(\n        "rtgen1_gen"' in src
    assert 'op.create_table(\n        "rdfid1_dose"' in src
    assert 'op.drop_table("rmiid1_med", schema=_SCHEMA)' in src
    assert 'op.drop_table("rtgen1_gen", schema=_SCHEMA)' in src
    assert 'op.drop_table("rdfid1_dose", schema=_SCHEMA)' in src


def test_generated_migration_uses_env_driven_role_pattern() -> None:
    """B7.3 lesson: GRANT statements use IFX_APP_ROLE env, NOT hardcoded ifx_prod_app."""
    src = generate_tier_migration(
        specs=[_make_simple_tier_a_spec()],
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    assert 'os.environ.get("IFX_APP_ROLE", "ifx_dev_app")' in src
    assert '_APP_ROLES = ("ifx_dev_app", "ifx_mock_app", _APP_ROLE)' in src
    # And critically â€” NO hardcoded ifx_prod_app as the default fallback
    # (the comment may explain prod set IFX_APP_ROLE=ifx_prod_app â€” that's fine)
    assert 'os.environ.get("IFX_APP_ROLE", "ifx_prod_app")' not in src


def test_empty_specs_list_raises() -> None:
    """Generator refuses to emit a migration with no tables."""
    with pytest.raises(ValueError, match="empty specs"):
        generate_tier_migration(
            specs=[],
            tier=Tier.A,
            revision_id="0009_fdb_tier_a",
            down_revision="0008_fdb_pricing",
        )


def test_spec_with_wrong_tier_raises() -> None:
    """Generator refuses to mix tiers in one migration (SPEC-locked granularity)."""
    tier_b_spec = TableSpec(
        table_name="RNDC9_BAR",
        columns=("a",),
        coercers={"a": str},
        tier=Tier.B,
    )
    with pytest.raises(ValueError, match="tier B but generator was invoked for tier A"):
        generate_tier_migration(
            specs=[_make_simple_tier_a_spec(), tier_b_spec],
            tier=Tier.A,
            revision_id="0009_fdb_tier_a",
            down_revision="0008_fdb_pricing",
        )


def test_generated_migration_includes_dryrun_reminder() -> None:
    """ADVERSARIAL R1 A2: docstring instructs operator to dry-run alembic up+down+up."""
    src = generate_tier_migration(
        specs=[_make_simple_tier_a_spec()],
        tier=Tier.A,
        revision_id="0009_fdb_tier_a",
        down_revision="0008_fdb_pricing",
    )
    assert "alembic upgrade head" in src
    assert "alembic downgrade -1" in src
    assert "dryrun_evidence.md" in src

 succeeded in 486ms:
modules/drug-database/tests/unit\test_fdb_adapter.py:574:    assert DeltaSemantics.APPEND_ONLY.value == "APPEND_ONLY"
modules/drug-database/tests/unit\test_fdb_contract.py:32:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_contract.py:455:    assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_contract.py:474:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_contract.py:495:    assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_contract.py:509:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit\test_fdb_contract.py:518:    assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_contract.py:545:    assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:9:  * APPEND_ONLY history table                  → PASS (row count grows)
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:27:from _fdb_contract import assert_delta_semantics_acd_cycle  # noqa: E402
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:61:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:98:            assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:110:# APPEND_ONLY — every operation appends a row (no conflict resolution)
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:122:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:132:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:168:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:199:    assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_delta_semantics.py:222:    assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:9:  ({UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE, APPEND_ONLY}),
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:10:  the spec's `table_name` MUST appear in `CONTRACT_TESTED_SPECS`
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:12:  `assert_delta_semantics_acd_cycle(spec, ...)` for it.
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:15:spec to `REGISTERED_SPECS` ALSO appends to `CONTRACT_TESTED_SPECS`
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:34:    DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:41:# `BATCH_TESTED_NAMES` constant. This loader unions every such constant
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:51:    """Discover per-batch BATCH_TESTED_NAMES exports and union them.
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:55:    BATCH_TESTED_NAMES constant (frozenset[str] expected). Missing
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:74:        names = getattr(mod, "BATCH_TESTED_NAMES", None)
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:82:                f"{parent_pkg}.{info.name}.BATCH_TESTED_NAMES must be "
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:89:CONTRACT_TESTED_SPECS: frozenset[str] = _load_batch_tested_names()
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:103:    missing = checkable_names - CONTRACT_TESTED_SPECS
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:107:        f"CONTRACT_TESTED_SPECS: {sorted(missing)}. For each:\n"
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:108:        f"  1. Add a test calling assert_delta_semantics_acd_cycle(spec, ...).\n"
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:109:        f"  2. Append the table_name to CONTRACT_TESTED_SPECS in this file.\n"
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:116:    """A name in CONTRACT_TESTED_SPECS that is NOT in REGISTERED_SPECS = stale.
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:119:    registry but its name stays in CONTRACT_TESTED_SPECS, the
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:124:    stale = CONTRACT_TESTED_SPECS - registered_names
modules/drug-database/tests/unit\test_fdb_contract_coverage.py:126:        f"B9.B F4: {len(stale)} stale entries in CONTRACT_TESTED_SPECS "
modules/drug-database/tests/unit\test_fdb_loader_registry.py:47:    delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:7:  2. Declares `BATCH_TESTED_NAMES: frozenset[str]` — the
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:9:     CONTRACT_TESTED_SPECS becomes the union of all batch declarations.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:41:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:54:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:143:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:29:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:42:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:144:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:33:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:46:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:147:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:29:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:42:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:144:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:35:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:48:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:145:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:29:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:42:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:144:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:30:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:37:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:110:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:29:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:42:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:144:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:1:"""B9.B C14 — Tier A batch 09 contract tests (APPEND_ONLY history template).
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:3:batch_09 specs are all `delta_semantics=APPEND_ONLY` — history rows
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:6:and the contract template's APPEND_ONLY branch asserts row-count
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:23:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:30:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:67:# APPEND_ONLY ACD cycle
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:78:    """Every batch_09 spec passes the APPEND_ONLY A/C/D/re-A contract.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:80:    APPEND_ONLY semantics: every transaction grows the row count.
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:86:        f"{spec.table_name}: batch_09 invariant — APPEND_ONLY only."
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:90:    # The template's APPEND_ONLY branch doesn't check state-after-A specifically
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:107:        assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:141:    """batch_09 is APPEND_ONLY only — no UPSERTs in history tables."""
modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:36:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:47:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:128:            assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:153:            assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:178:            assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:44:    assert_delta_semantics_acd_cycle,
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:51:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:151:            if not non_nk_cols:
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:155:                assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:184:                assert_delta_semantics_acd_cycle(
modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:219:            assert_delta_semantics_acd_cycle(

 succeeded in 487ms:
"""B9.A C2 â€” Generated migration template for FDB tier batches.

Consumes a list of `TableSpec` instances + tier label and emits an
idempotent Alembic migration source as a string. Used by B9.B-G to
mass-produce the 6 SPEC-locked migrations:

    0009_fdb_tier_a              â€” 113 simple lookups (Tier A)
    0010_fdb_tier_b              â€” 66 NDC/GCN-keyed joins (Tier B)
    0011_fdb_tier_c_minus_rndc14 â€” 16 complex/large non-RNDC14 (Tier C)
    0012_fdb_rndc14              â€” RNDC14_NDC_MSTR standalone (68 cols)
    0013_fdb_pricing_big         â€” RNP2 + RPRDPP0 (Tier C, D2 perf gate)
    0014_fdb_mtl_schema          â€” 19 MTL schema-only (Tier D)

The generator is intentionally NOT invoked at migration time. It runs
ONCE per tier during B9.B-G execution; the operator reviews the
output, lands it as a real `.py` file in `alembic/versions/`, and
that file becomes the canonical migration. The generator is a
helper, not a runtime dependency.

ADVERSARIAL R1 A2 mitigation: every generated migration includes an
explicit `alembic upgrade + downgrade + upgrade` evidence-capture
docstring footer reminding the operator to dry-run on a disposable
DB before committing.

ADVERSARIAL R1 N4 mitigation: column types are derived from a known
coercer-to-SQL-type table. Unknown coercers raise loudly â€” they do
NOT silently fall through to a default type.

B7.3 lesson folded in: GRANT statements use the `IFX_APP_ROLE`
env-driven pattern with `ifx_dev_app` safe fallback, NOT a hardcoded
`ifx_prod_app` reference.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from drug_database.services.fdb_adapter import TableSpec, Tier


# ---------------------------------------------------------------------------
# Coercer â†’ SQL column-type lookup
# ---------------------------------------------------------------------------
#
# Maps the Python coercer attached to a TableSpec column to a string
# representation of the SQLAlchemy column type. Unknown coercers
# raise ValueError â€” the operator must extend this table explicitly
# rather than fall through to a sloppy default.


def _sql_type_for_coercer(coercer: Callable[[str], Any]) -> str:
    """Return SQLAlchemy type literal for a TableSpec coercer.

    Raises ValueError if the coercer isn't recognized. Extend this
    function (not the call site) when adding new coercer kinds.
    """
    # Built-in types (functions are also types in Python)
    if coercer is int:
        return "sa.Integer()"
    if coercer is str:
        return "sa.Text()"
    if coercer is bool:
        return "sa.Boolean()"
    if coercer is float:  # explicitly reject â€” FDB has no float columns
        raise ValueError(
            "float coercer is forbidden in FDB tables (see "
            "financial-precision.md). Use Decimal."
        )
    if coercer is Decimal:
        return "sa.Numeric(16, 5)"  # FDB pricing precision; override per-table if different

    # Named functions â€” match by attribute name
    name = getattr(coercer, "__name__", "")
    if name == "_parse_fdb_date":
        return "sa.Date()"
    if name == "normalize_ndc":
        return "sa.String(11)"
    if name in {"_str11", "_str14"}:  # NDC string forms used in fdb_adapter helpers
        width = int(name[4:])
        return f"sa.String({width})"

    raise ValueError(
        f"Unknown coercer {coercer!r} (name={name!r}) â€” extend "
        "_sql_type_for_coercer() in gen_fdb_tier_migration.py before "
        "regenerating this tier's migration."
    )


# ---------------------------------------------------------------------------
# Migration source template
# ---------------------------------------------------------------------------


def _column_block(spec: TableSpec) -> str:
    """Generate the sa.Column(...) lines for one table."""
    lines: list[str] = []
    for col in spec.columns:
        coercer = spec.coercers[col]
        sql_type = _sql_type_for_coercer(coercer)
        nullable = col in spec.nullable
        nullable_kw = "True" if nullable else "False"
        lines.append(
            f'        sa.Column({col!r}, {sql_type}, nullable={nullable_kw}),'
        )
    return "\n".join(lines)


def _create_table_block(spec: TableSpec, schema: str) -> str:
    """Generate the op.create_table(...) call for one table."""
    table_name = spec.table_name.lower()  # FDB names are upper; DB tables snake_case
    rcounts_key = spec.record_counts_key or spec.table_name
    return f"""    # {spec.table_name} â€” tier={spec.tier.value} delta={spec.delta_semantics.value} record_counts_key={rcounts_key}
    op.create_table(
        "{table_name}",
{_column_block(spec)}
        schema={schema!r},
    )"""


def _grant_block(table_names: Sequence[str], schema: str) -> str:
    """Emit GRANT statements via env-driven role (B7.3 pattern)."""
    lines = ['    for _table in (']
    for tn in table_names:
        lines.append(f'        "{tn.lower()}",')
    lines.append("    ):")
    lines.append(
        f'        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE '
        f'ON {schema}.{{_table}} TO {{role}}" '
        f'for role in _APP_ROLES)'
    )
    return "\n".join(lines)


_MIGRATION_TEMPLATE = '''"""B9 {tier_label} batch â€” {n_tables} FDB tables ({tier_desc}).

Generated by `modules/drug-database/scripts/gen_fdb_tier_migration.py`
on {gen_date}. SPEC: charter v3.1 Â§SPEC-locked migration granularity;
plan v3.1 Â§W1-W4 tier scope.

Operator: dry-run on a disposable DB before committing (ADVERSARIAL R1 A2):

    alembic upgrade head      # forward
    alembic downgrade -1      # reverse
    alembic upgrade head      # re-apply

All three steps must succeed cleanly. Capture evidence to
`waves/B9/{tier_label}_dryrun_evidence.md` before committing.

Revision ID: {revision_id}
Revises: {down_revision}
Create Date: {gen_date}
"""
from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "{revision_id}"
down_revision: Union[str, None] = "{down_revision}"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "{schema}"

# B7.3 env-driven role pattern â€” defaults to dev-safe role if env unset.
# Production sets IFX_APP_ROLE=ifx_prod_app explicitly.
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_APP_ROLES = ("ifx_dev_app", "ifx_mock_app", _APP_ROLE)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {{_SCHEMA}}".format(_SCHEMA=_SCHEMA))

{create_tables_block}

{grant_block}


def downgrade() -> None:
{drop_tables_block}
'''


def generate_tier_migration(
    *,
    specs: Sequence[TableSpec],
    tier: Tier,
    revision_id: str,
    down_revision: str,
    schema: str = "drug_database",
    gen_date: str | None = None,
) -> str:
    """Generate alembic migration source for a B9 tier batch.

    Args:
        specs: TableSpec list for this tier; all must have spec.tier == tier.
        tier: the B9 effort tier (used in docstring + revision metadata).
        revision_id: alembic revision identifier (e.g., "0009_fdb_tier_a").
        down_revision: parent revision (e.g., "0008_fdb_pricing").
        schema: target Postgres schema (default "drug_database").
        gen_date: ISO date string for the docstring; None â†’ today.

    Returns:
        A string containing the full migration .py source. Caller is
        responsible for writing it to `alembic/versions/<revision>.py`
        and reviewing before committing.

    Raises:
        ValueError: if any spec has a coercer not in _sql_type_for_coercer.
        ValueError: if specs contains a spec whose tier != tier.
    """
    if not specs:
        raise ValueError("generate_tier_migration: empty specs list")
    for spec in specs:
        if spec.tier is not tier:
            raise ValueError(
                f"Spec {spec.table_name!r} has tier {spec.tier.value} "
                f"but generator was invoked for tier {tier.value}."
            )

    if gen_date is None:
        gen_date = date.today().isoformat()

    table_names = [s.table_name for s in specs]
    create_blocks = "\n\n".join(_create_table_block(s, schema) for s in specs)

    # Grant block: one for-loop over (table, role) pairs
    grants: list[str] = ["    for _table in ("]
    for tn in table_names:
        grants.append(f'        "{tn.lower()}",')
    grants.append("    ):")
    grants.append("        for _role in _APP_ROLES:")
    grants.append(
        f'            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE '
        f'ON {{_SCHEMA}}.{{_table}} TO {{_role}}")'
    )
    grant_block = "\n".join(grants)

    # Downgrade: drop in reverse order
    drop_lines = [
        f'    op.drop_table("{s.table_name.lower()}", schema=_SCHEMA)'
        for s in reversed(specs)
    ]
    drop_tables_block = "\n".join(drop_lines)

    tier_desc = {
        Tier.A: "simple lookups, generic ingester",
        Tier.B: "NDC/GCN-keyed joins",
        Tier.C: "complex/large (>8 cols or >50 MB)",
        Tier.D: "MTL â€” schema-only, no data load",
        Tier.UNKNOWN: "uncategorized (should not be generated)",
    }[tier]

    tier_label = f"Tier {tier.value}"
    return _MIGRATION_TEMPLATE.format(
        tier_label=tier_label,
        tier_desc=tier_desc,
        n_tables=len(specs),
        gen_date=gen_date,
        revision_id=revision_id,
        down_revision=down_revision,
        schema=schema,
        create_tables_block=create_blocks,
        grant_block=grant_block,
        drop_tables_block=drop_tables_block,
    )


__all__ = ["generate_tier_migration", "_sql_type_for_coercer"]

codex
The TableSpec layer is parse metadata only; it does not carry natural-key columns. The tests infer keys per batch, but the migration generator does not emit keys or unique constraints, and `rg` found none in `0009_fdb_tier_a.py`. That is now the main risk I’m validating against the stated gate criteria.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "fdb_tier_a|loader_group|REGISTERED_SPECS|load_fdb|DeltaSemantics|on_conflict_do_update|on_conflict_do_nothing" scripts modules/drug-database/drug_database modules/drug-database/tests -g "*.py"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "fdb_tier_a|Tier A|B9.B|0009_fdb_tier_a|dryrun|mini-GATE|row count|FDW|verify" waves/B9 modules/drug-database infrastructure/scripts/lib/expected_reference_tables.txt -g "*.md" -g "*.txt"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
2026-05-12T14:55:07.391106Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$env:PYTHONPATH='"'modules/drug-database'; "'$env:PYTHONDONTWRITEBYTECODE='"'1'; python -c \"from drug_database.services.fdb_specs import REGISTERED_SPECS; from drug_database.services.fdb_tier_a import discovered_batches; print(len(REGISTERED_SPECS)); print(discovered_batches())\""` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$env:PYTHONPATH='"'modules/drug-database'; "'$env:PYTHONDONTWRITEBYTECODE='"'1'; python -c \"from drug_database.services.fdb_specs import REGISTERED_SPECS; from drug_database.services.fdb_tier_a import discovered_batches; print(len(REGISTERED_SPECS)); print(discovered_batches())\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "RAHFSGC1|RATCGC0|RGCN0|RETCNDC0|RGCNINH0|RGCNINS0|Tier B|NDC/GCN|MedID" waves/B9 data/reference/fdb modules/drug-database/drug_database/services/fdb_tier_a -g "*.md" -g "*.py" -g "*.txt"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$env:PYTHONPATH='"'modules/drug-database'; "'$env:PYTHONDONTWRITEBYTECODE='"'1'; python -c \"from drug_database.services.fdb_specs import REGISTERED_SPECS; from drug_database.services.fdb_tier_a import discovered_batches; print(len(REGISTERED_SPECS)); print(discovered_batches())\""` rejected: blocked by policy
 succeeded in 527ms:
infrastructure/scripts/lib/expected_reference_tables.txt:80:# ─── B9.B Tier A: 107 FDB lookup tables (auto-aggregated from fdb_tier_a/batch_*) ───
waves/B9\B9.B-charter.md:1:# Wave B9.B — Tier A: 113 simple lookup tables
waves/B9\B9.B-charter.md:7:**FDW manifest target:** 66 → 179 (+113)
waves/B9\B9.B-charter.md:11:113 Tier A tables from the FDB NDDF Plus drop — simple lookup
waves/B9\B9.B-charter.md:15:Tier A definition (per `recon.md` §3):
waves/B9\B9.B-charter.md:23:The first B9.B commit that opens this wave already shipped:
waves/B9\B9.B-charter.md:28:any Tier A spec lands. See codex GATE-CLOSE R1 MEDIUM 2.
waves/B9\B9.B-charter.md:32:Each B9.B session lands:
waves/B9\B9.B-charter.md:38:- Partial loader registry update (`--mode fdb_tier_a` group)
waves/B9\B9.B-charter.md:42:One alembic migration `0009_fdb_tier_a.py` covering all 113 Tier A
waves/B9\B9.B-charter.md:56:`waves/B9/B9.B-dryrun_evidence.md`.
waves/B9\B9.B-charter.md:58:## B9.B mini-GATE-CLOSE criteria
waves/B9\B9.B-charter.md:62:- All 113 Tier A tables row-count-reconciled vs `RECORD_COUNTS.TXT`
waves/B9\B9.B-charter.md:64:- `setup_fdw.sh --verify` PASS 179/179 both env DBs
waves/B9\B9.B-charter.md:67:- Sampled behavioral tests: 10 randomly-picked Tier A tables
waves/B9\B9.B-charter.md:69:- Migration `0009_fdb_tier_a.py` apply + reverse + apply: clean
waves/B9\B9.B-charter.md:71:  fdb_tier_a` produces 0 net new rows
waves/B9\B9.B-charter.md:75:- Codex B9.B mini-GATE-CLOSE consult: GO
waves/B9\B9.B-charter.md:87:for B9.B specifically:
waves/B9\B9.B-charter.md:89:- **T1 (latin-1 decode)**: every Tier A contract runs the latin-1
waves/B9\B9.B-charter.md:91:- **T12 (UPD A/C/D probe)**: every Tier A spec with
waves/B9\B9.B-charter.md:94:- **N4 (silent skip)**: every Tier A contract runs
waves/B9\B9.B-charter.md:98:## When B9.B closes
waves/B9\B9.B-charter.md:100:When all 113 Tier A tables pass the per-spec contract suite, the
waves/B9\B9.B-charter.md:101:mini-GATE-CLOSE criteria are green, AND codex returns GO on the
waves/B9\B9.B-charter.md:102:B9.B close consult. Next: B9.C — 66 NDC/GCN-keyed joins.
waves/B9\codex-b9b-gate-close-r1-prompt.md:1:# Codex B9.B mini-GATE-CLOSE R1 — Consult Prompt
waves/B9\codex-b9b-gate-close-r1-prompt.md:4:**Phase:** B9.B (Tier A — 113-table simple lookups, recon §3 estimate)
waves/B9\codex-b9b-gate-close-r1-prompt.md:11:B9.B is the first per-table data wave. Goal per recon §3:
waves/B9\codex-b9b-gate-close-r1-prompt.md:12:"113 Tier A tables = simple lookup descriptors (≤ 5 cols, < 2 MB)".
waves/B9\codex-b9b-gate-close-r1-prompt.md:14:**Actual delivered: 107 specs across 11 batches + migration + FDW manifest.**
waves/B9\codex-b9b-gate-close-r1-prompt.md:26:93c9d8b  B9.B C1 (F4): registry-vs-contract coverage assertion + Tier A charter
waves/B9\codex-b9b-gate-close-r1-prompt.md:27:2d3e791  B9.B C2: RECORD_COUNTS.TXT parser-format fix + 906-vs-220 discovery
waves/B9\codex-b9b-gate-close-r1-prompt.md:28:d8af39e  B9.B C3: re-point preflight to DB.zip canonical 220-table namelist
waves/B9\codex-b9b-gate-close-r1-prompt.md:29:353a04b  B9.B C4: per-table DDL manifest for multi-agent dispatch
waves/B9\codex-b9b-gate-close-r1-prompt.md:30:50e7a88  B9.B C5: auto-aggregation infrastructure (multi-agent isolation)
waves/B9\codex-b9b-gate-close-r1-prompt.md:31:79d3416  B9.B C6: Tier A batch_01 (canonical template, 12 id+desc lookups)
waves/B9\codex-b9b-gate-close-r1-prompt.md:32:7bb9964  B9.B C9: Tier A batch_04 (10 lookup tables) + bundled batch_02 (10)
waves/B9\codex-b9b-gate-close-r1-prompt.md:33:4a58889  B9.B C8: Tier A batch_03 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-prompt.md:34:697393c  B9.B C10: Tier A batch_05 (10 lookup tables including 1 DATE coercer)
waves/B9\codex-b9b-gate-close-r1-prompt.md:35:1d3ffde  B9.B C11: Tier A batch_06 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-prompt.md:36:6c1ed28  B9.B C12: Tier A batch_07 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-prompt.md:37:1292c04  B9.B C13: composite-NK template (batch_08, 5 TALL MAN tables)
waves/B9\codex-b9b-gate-close-r1-prompt.md:38:a4ea4db  B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
waves/B9\codex-b9b-gate-close-r1-prompt.md:39:86515b5  B9.B C15: Tier A batch_10 (11 link tables — composite+single NK hybrid)
waves/B9\codex-b9b-gate-close-r1-prompt.md:40:2f226ae  B9.B C16: Tier A batch_11 (11 link tables with DATE columns)
waves/B9\codex-b9b-gate-close-r1-prompt.md:41:7c1c5e9  B9.B C17+C18: alembic migration 0009_fdb_tier_a + FDW manifest expansion (66 → 173)
waves/B9\codex-b9b-gate-close-r1-prompt.md:46:### Production code (drug_database/services/fdb_tier_a/)
waves/B9\codex-b9b-gate-close-r1-prompt.md:53:- `test_fdb_tier_a_batch_01.py` through `test_fdb_tier_a_batch_11.py` — 691 parametrized + sanity tests
waves/B9\codex-b9b-gate-close-r1-prompt.md:56:### Migration + FDW
waves/B9\codex-b9b-gate-close-r1-prompt.md:57:- `modules/drug-database/alembic/versions/0009_fdb_tier_a.py` — 1,220 lines auto-generated via `gen_fdb_tier_migration.py`. Creates all 107 tables in `drug_database` schema with proper column types, nullables, GRANTs (env-driven IFX_APP_ROLE pattern), and operator dry-run docstring.
waves/B9\codex-b9b-gate-close-r1-prompt.md:58:- `infrastructure/scripts/lib/expected_reference_tables.txt` — 66 → 173 entries (+107 Tier A appended in a new section)
waves/B9\codex-b9b-gate-close-r1-prompt.md:61:- `waves/B9/B9.B-charter.md` — wave charter
waves/B9\codex-b9b-gate-close-r1-prompt.md:62:- `waves/B9/status.md` — ledger updated to reflect B9.B ready for gate-close
waves/B9\codex-b9b-gate-close-r1-prompt.md:67:B9.B Tier A unit tests:      691 pass
waves/B9\codex-b9b-gate-close-r1-prompt.md:84:   agents own per-batch files (`batch_NN.py` + `test_fdb_tier_a_batch_NN.py`)
waves/B9\codex-b9b-gate-close-r1-prompt.md:119:   tables". Forcing them into Tier A would violate that classification.
waves/B9\codex-b9b-gate-close-r1-prompt.md:120:   But: does deferring 6 invalidate B9.B as a clean wave boundary,
waves/B9\codex-b9b-gate-close-r1-prompt.md:121:   or is "Tier A as recon defines it" the right framing?
waves/B9\codex-b9b-gate-close-r1-prompt.md:151:   `0009_fdb_tier_a.py`. Are the column types reasonable (sa.Integer
waves/B9\codex-b9b-gate-close-r1-prompt.md:163:GO — B9.B closes; B9.C opens (Tier B — 66 NDC/GCN-keyed joins, plus the 6 reclassified residuals).
waves/B9\charter.md:3:**Status:** SPEC v3.2 LOCKED — erratum chain: (v3.1) arithmetic drift correction surfaced by codex PLAN R2 → B9.B FDW `116/116`→`179/179`, B9.D "17 complex"→"16 complex"; (v3.2) MTL FDW-exposure policy surfaced by codex ADVERSARIAL R1 → MTL excluded from default FDW manifest to prevent silent false-negative joins, conditional 19 entries added only when `fdb_load_mtl=True` (future MTL activation wave). B9.H final FDW count: **264/264 default, 283/283 conditional**. No scope change. See `codex-plan-consult-r2.md` and `codex-adversarial-r1.md`. Ready for PLAN v3 → ADVERSARIAL R2.
waves/B9\charter.md:21:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4–5 months with multitasking. |
waves/B9\charter.md:27:| W1 | Tier A — simple lookups (≤5 columns, generic ingester) | 113 | ~10 sessions |
waves/B9\charter.md:31:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
waves/B9\charter.md:44:B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\charter.md:49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 179/179 + ingester contract tests |
waves/B9\charter.md:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests (FDW 245/245) |
waves/B9\charter.md:51:| B9.D | Tier C non-RNDC14 — 16 complex tables | 4 | **B9.D mini-GATE-CLOSE** (FDW 261/261) |
waves/B9\charter.md:52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** — column-by-column model review |
waves/B9\charter.md:53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** — perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\charter.md:54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** — integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\charter.md:55:| B9.H | Manifest extension (66 → 264 FDW entries default; +19 conditional MTL) + consumer audits + final closeout artifacts | 5 | **Final B9 GATE-CLOSE** — full cross-tier consult |
waves/B9\charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
waves/B9\charter.md:63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\charter.md:64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\charter.md:66:| SC-6 | `setup_fdw.sh --verify` 264/264 PASS in both env DBs by default (MTL excluded from FDW per ADVERSARIAL R1 mitigation); conditional 283/283 when `fdb_load_mtl=True` |
waves/B9\charter.md:69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\charter.md:78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\charter.md:79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\charter.md:86:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\charter.md:89:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
waves/B9\charter.md:102:**~39 sessions × 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong — corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\baseline.md:7:This file is the source-of-truth for what was true at the start of B9 execution. Every B9.B..B9.G mini-GATE-CLOSE re-asserts these numbers (or documents the delta).
waves/B9\baseline.md:64:- `setup_fdw.sh --verify` = **132 PASS, 0 FAIL** ✅
waves/B9\baseline.md:65:- Phase 09 row counts unchanged (15,635,770 + 23) ✅
waves/B9\baseline.md:103:Per-phase mini-GATE-CLOSE asserts these counts unchanged (plus or minus weekly delta growth, which would be tracked separately).
waves/B9\baseline.md:105:### ✅ FDW verify — 132 PASS, 0 FAIL
waves/B9\baseline.md:108:bash infrastructure/scripts/setup_fdw.sh --verify
waves/B9\baseline.md:115:Plan invariant `setup_fdw --verify 66/66` satisfied **per env DB** (the script counts per-DB so the cross-DB total is 132). FDW baseline locked at 66 entries per env DB → 264 default / 283 conditional after B9.
waves/B9\baseline.md:129:Per-module breakdown captured in this session's transcript; not enumerated here (volume). The mini-GATE-CLOSE assertion is on the TOTAL + module count, plus node-ID delta (added contract tests should appear, no others should disappear).
waves/B9\baseline.md:147:Per-phase mini-GATE-CLOSE asserts: **failure-count ≤ 195** AND no failing node-ID outside the captured set (except in-phase contract tests whose failures would be in `parse_warning_allowlist.md`).
waves/B9\baseline.md:164:**Practical impact on B9 baseline:** the 1,623 / 126 collection figures EXCLUDE `tests/integration`. When the integration plugin conflict is fixed by a forensic wave, those tests will be added to the baseline. Per-phase mini-GATE-CLOSE asserts on the post-baseline number.
waves/B9\baseline.md:178:7. `bash infrastructure/scripts/setup_fdw.sh --verify` → expect 66/66
waves/B9\baseline.md:197:**Status:** C0 PARTIAL. Disk + test-inventory captured; DB-dependent invariants deferred to next session. B9.A C1-C14 commits remain. This is **not** a B9.A mini-GATE-CLOSE — that requires all C0-C14 evidence + Docker-up DB invariants confirmed.
waves/B9\codex-adversarial-r1.md:34:1. **Session size attack:** Tier A says 12 tables/session. What if a single Tier A table has a hidden complexity (e.g., requires a join, or has > 5 columns despite recon classification)? How does the plan handle a single-session overflow without dragging the wave's 10-session budget?
waves/B9\codex-adversarial-r1.md:35:2. **Migration attack:** A single migration covering 113 tables (Tier A) is large. What if alembic apply fails partway? Is there a rollback strategy? Can a half-applied migration leave the DB in a state that blocks reverse?
waves/B9\codex-adversarial-r1.md:36:3. **FDW manifest attack:** The plan additively grows `expected_reference_tables.txt`. What if two phases both touch this file in parallel sessions? Is there merge-conflict resolution?
waves/B9\codex-adversarial-r1.md:41:6. **B9.E RNDC14 attack:** Plan dedicates 2 sessions to a 68-column model. What if column-by-column codex review surfaces 5+ type-correctness issues? Does the mini-GATE-CLOSE allow iteration, or does it fail outright?
waves/B9\codex-adversarial-r1.md:42:7. **B9.F perf gate attack:** RNP2+RPRDPP0 timed dry-run says ≤ 5 min FDW verify after indexes. What if the actual dry-run takes 20 min? What's the abort criterion? Charter says "abort + escalate if > +1.4 GB" for storage — but no explicit abort for timing.
waves/B9\codex-adversarial-r1.md:43:8. **B9.G MTL FDW attack:** Plan says MTL tables ARE in FDW as foreign-table entries pointing at empty reference tables. What if a downstream query joins to an MTL foreign table? Postgres won't error, but the join returns empty — silent failure mode.
waves/B9\codex-adversarial-r1.md:51:12. **Existing 3-table coverage interaction:** Phase 09 covers RNP3 + RPRDPTD0 + RNPTYPD0. Does B9.A's new TableSpec registry change break these? Migration `0009_fdb_tier_a` is independent of them, but the registry might re-process them.
waves/B9\codex-adversarial-r1.md:52:13. **Test count baseline assumption:** Plan freezes 134 failures. What if those 134 include flaky tests that pass 30% of the time? Then mini-GATE-CLOSE might falsely show 135 failures one session and 132 the next.
waves/B9\codex-adversarial-r1.md:55:14. **adjudication-engine ripple:** Adjudication queries FDB tables via reference DB FDW. If B9 adds 217 new FDB tables, does adjudication's query path change? Plan doesn't audit the consumer side.
waves/B9\codex-adversarial-r1.md:83:<one paragraph: if no HIGH unaddressed → PLAN locks fully, B9.A closes, B9.B opens; if HIGH unaddressed → plan v3 needs <list of required mitigations>; if STRUCTURAL FLAW → escalate to architectural pause>
waves/B9\codex-adversarial-r1.md:98:**Status:** SPEC v3.1 LOCKED â€” SPEC v3 + erratum applied after codex PLAN R2 surfaced arithmetic drift between charter and PLAN v2. Erratum: B9.B closure-gate FDW count `116/116` â†’ `179/179`; B9.D scope "17 complex tables" â†’ "16 complex tables" (19 Tier C minus 3 special-handled). No scope change; arithmetic correction only. See `codex-plan-consult-r2.md`. Ready for PLAN v2 â†’ ADVERSARIAL.
waves/B9\codex-adversarial-r1.md:116:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4â€“5 months with multitasking. |
waves/B9\codex-adversarial-r1.md:122:| W1 | Tier A â€” simple lookups (â‰¤5 columns, generic ingester) | 113 | ~10 sessions |
waves/B9\codex-adversarial-r1.md:126:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
waves/B9\codex-adversarial-r1.md:139:B9 ships incrementally **with mandatory per-phase closure gates** â€” each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-adversarial-r1.md:144:| B9.B | Tier A â€” 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** â€” evidence + row-count manifest + FDW verify 179/179 + ingester contract tests |
waves/B9\codex-adversarial-r1.md:145:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests (FDW 245/245) |
waves/B9\codex-adversarial-r1.md:146:| B9.D | Tier C non-RNDC14 â€” 16 complex tables | 4 | **B9.D mini-GATE-CLOSE** (FDW 261/261) |
waves/B9\codex-adversarial-r1.md:147:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** â€” column-by-column model review |
waves/B9\codex-adversarial-r1.md:148:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** â€” perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-adversarial-r1.md:149:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** â€” integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-adversarial-r1.md:150:| B9.H | Manifest extension (66 â†’ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** â€” full cross-tier consult |
waves/B9\codex-adversarial-r1.md:157:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
waves/B9\codex-adversarial-r1.md:158:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-adversarial-r1.md:159:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-adversarial-r1.md:161:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
waves/B9\codex-adversarial-r1.md:164:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-adversarial-r1.md:173:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-adversarial-r1.md:174:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) â€” 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-adversarial-r1.md:181:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\codex-adversarial-r1.md:184:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
waves/B9\codex-adversarial-r1.md:197:**~39 sessions Ã— 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong â€” corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-adversarial-r1.md:201:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-adversarial-r1.md:215:**Status:** PLAN v2 LOCKED â€” codex PLAN R1 GO-WITH-FIXES (8 fixes) + PLAN R2 GO-WITH-FIXES (charter erratum) + PLAN GATE FINAL VERDICT GO (`codex-plan-consult-r2.md`). Pending codex ADVERSARIAL consult before B9.A closes and B9.B opens.
waves/B9\codex-adversarial-r1.md:227:2. **Per-phase scope, deliverables, success-criteria mapping, gate criteria, est sessions, commit shape** for B9.B..B9.H.
waves/B9\codex-adversarial-r1.md:231:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9\codex-adversarial-r1.md:236:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-adversarial-r1.md:247:2. **B7.2 Phase 11A COMPLETE** â€” `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
waves/B9\codex-adversarial-r1.md:248:3. **Reference DB topology stable** â€” `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-adversarial-r1.md:251:6. **134 pre-existing test failures baseline frozen** â€” at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged Â± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
waves/B9\codex-adversarial-r1.md:252:7. **FDB drop manifest reachable** â€” `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon Â§1.5 verified â€” re-verify at C0).
waves/B9\codex-adversarial-r1.md:262:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
waves/B9\codex-adversarial-r1.md:274:- **`setup_fdw.sh --verify` manifest expansion mechanism** â€” `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline â†’ 179 (after B9.B +113) â†’ 245 (after B9.C +66) â†’ 261 (after B9.D +16) â†’ 262 (after B9.E +1 RNDC14) â†’ 264 (after B9.F +2 pricing) â†’ 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-adversarial-r1.md:275:- **pytest baseline markers** â€” committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
waves/B9\codex-adversarial-r1.md:281:| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
waves/B9\codex-adversarial-r1.md:290:**B9.A mini-GATE-CLOSE criteria (charter SC-9):**
waves/B9\codex-adversarial-r1.md:294:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
waves/B9\codex-adversarial-r1.md:300:### B9.B â€” Tier A: 113 simple lookup tables (â‰¤ 5 columns, generic ingester) (10 sessions)
waves/B9\codex-adversarial-r1.md:302:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier â€” short tables (mostly < 10K rows, all â‰¤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
waves/B9\codex-adversarial-r1.md:307:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon Â§4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
waves/B9\codex-adversarial-r1.md:315:- 1 alembic migration (`0009_fdb_tier_a.py`)
waves/B9\codex-adversarial-r1.md:317:- Loader-orchestration entry: `--mode fdb_tier_a` loads only Tier A
waves/B9\codex-adversarial-r1.md:323:- SC-2 (RECORD_COUNTS reconciliation) â€” every loaded Tier A table: actual Ã· expected within Â±0.1% tolerance (small lookups should be exact)
waves/B9\codex-adversarial-r1.md:324:- SC-6 (FDW verify) â€” partial: 179/179 PASS after B9.B
waves/B9\codex-adversarial-r1.md:325:- SC-7 (weekly idempotency) â€” verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9\codex-adversarial-r1.md:326:- SC-8 (test strategy) â€” contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
waves/B9\codex-adversarial-r1.md:327:- SC-9 (mini-GATE-CLOSE) â€” see below
waves/B9\codex-adversarial-r1.md:329:**B9.B mini-GATE-CLOSE criteria:**
waves/B9\codex-adversarial-r1.md:331:- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` Â± documented tolerance
waves/B9\codex-adversarial-r1.md:332:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9\codex-adversarial-r1.md:333:- All Tier A contract tests green
waves/B9\codex-adversarial-r1.md:334:- Sampled behavioral tests: 10 randomly-picked Tier A tables exercise non-trivial query (FK join, where-clause, sort)
waves/B9\codex-adversarial-r1.md:336:- Weekly delta path: `load_fdb.py --mode fdb_tier_a` re-run produces 0 new rows (idempotent)
waves/B9\codex-adversarial-r1.md:338:- Codex mini-GATE-CLOSE consult: GO
waves/B9\codex-adversarial-r1.md:346:**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.
waves/B9\codex-adversarial-r1.md:348:**Per-session shape (12 sessions = ~5.5 tables/session â€” slower than Tier A because of join-design + FK-target verification per table):**
waves/B9\codex-adversarial-r1.md:351:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-adversarial-r1.md:361:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\codex-adversarial-r1.md:362:- FDW foreign-table count: 179 â†’ 245
waves/B9\codex-adversarial-r1.md:366:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-adversarial-r1.md:387:- FDW foreign-table count: 245 â†’ **261**
waves/B9\codex-adversarial-r1.md:392:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
waves/B9\codex-adversarial-r1.md:400:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" â€” no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-adversarial-r1.md:413:- FDW foreign-table count: 261 â†’ 262
waves/B9\codex-adversarial-r1.md:417:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
waves/B9\codex-adversarial-r1.md:428:- Session 2: Timed full-load dry run for both tables; capture wall-clock + final row count + Postgres index build time; capture `df -h` before/after
waves/B9\codex-adversarial-r1.md:430:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` â†’ 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline
waves/B9\codex-adversarial-r1.md:439:- FDW foreign-table count: 262 â†’ 264
waves/B9\codex-adversarial-r1.md:443:**B9.F mini-GATE-CLOSE criteria â€” DRACONIAN per charter SC-4:**
waves/B9\codex-adversarial-r1.md:448:- FDW + Postgres verify after indexes built: completes within 5 min
waves/B9\codex-adversarial-r1.md:450:- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps
waves/B9\codex-adversarial-r1.md:473:- FDW foreign-table count: 264 â†’ **283** (MTL tables ARE in FDW even though data isn't loaded â€” they exist as foreign-table entries pointing at empty reference tables)
waves/B9\codex-adversarial-r1.md:475:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D â€” 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
waves/B9\codex-adversarial-r1.md:479:**B9.G mini-GATE-CLOSE criteria:**
waves/B9\codex-adversarial-r1.md:484:- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)
waves/B9\codex-adversarial-r1.md:490:**Scope:** Reconcile `infrastructure/scripts/lib/expected_reference_tables.txt` to the true final count, run final FDW verify, produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
waves/B9\codex-adversarial-r1.md:495:- Session 2: Final `setup_fdw.sh --verify` **283/283** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables; published in `waves/B9/evidence.md`
waves/B9\codex-adversarial-r1.md:502:- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
waves/B9\codex-adversarial-r1.md:516:- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
waves/B9\codex-adversarial-r1.md:519:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9\codex-adversarial-r1.md:534:| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
waves/B9\codex-adversarial-r1.md:535:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9\codex-adversarial-r1.md:538:| SC-6 | `setup_fdw.sh --verify` output **283/283** in dev + mock (charter-matched) | B9.H Session 2 |
waves/B9\codex-adversarial-r1.md:541:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
waves/B9\codex-adversarial-r1.md:551:| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon Â§7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
waves/B9\codex-adversarial-r1.md:552:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9\codex-adversarial-r1.md:554:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
waves/B9\codex-adversarial-r1.md:557:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
waves/B9\codex-adversarial-r1.md:558:| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
waves/B9\codex-adversarial-r1.md:559:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
waves/B9\codex-adversarial-r1.md:560:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, Â± in-phase contract tests on the collection number. |
waves/B9\codex-adversarial-r1.md:561:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
waves/B9\codex-adversarial-r1.md:562:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables â€” some tables may require TRUNCATE+INSERT instead of UPSERT (recon Â§7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
waves/B9\codex-adversarial-r1.md:573:| **PLAN R2** | **B9.A** | **Plan v2 with R1 fixes absorbed; verify** | **`codex-plan-consult-r2.md` â€” pending** |
waves/B9\codex-adversarial-r1.md:575:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
waves/B9\codex-adversarial-r1.md:576:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-adversarial-r1.md:577:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
waves/B9\codex-adversarial-r1.md:578:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9\codex-adversarial-r1.md:579:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9\codex-adversarial-r1.md:580:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9\codex-adversarial-r1.md:583:**Total codex consults projected:** 12 (2 SPEC done + PLAN R1 done + PLAN R2 + ADVERSARIAL + 6 mini-GATE-CLOSE + final GATE-CLOSE = 12).
waves/B9\codex-adversarial-r1.md:603:1. **FDW final count: 283 vs 284** â†’ **RESOLVED: 283.** Tier C arithmetic bug (`19 - 3 = 16, not 17`) cascaded to 284. Plan v2 corrects all references: 66 â†’ 179 â†’ 245 â†’ 261 â†’ 262 â†’ 264 â†’ 283.
waves/B9\codex-adversarial-r1.md:604:2. **Migration count: 5 vs 6 vs 9-10** â†’ **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.
waves/B9\codex-adversarial-r1.md:605:3. **Loader-orchestration modes: existing vs new** â†’ **RESOLVED:** existing `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, `fdb_rebase`. B9.A C4 does NOT need to add `fdb_weekly`. It may need to add tier-specific modes (`fdb_tier_a`, `fdb_tier_b`, `fdb_mtl_data`) if per-tier loaders are desired; PLAN v2 leaves that as a B9.A C1 design decision (additive to existing modes).
waves/B9\codex-adversarial-r1.md:611:- **Charter Â§Workstreams view (39 sessions):** counts only productive ingest work â€” W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-adversarial-r1.md:623:- At each mini-GATE-CLOSE: full sign-off sheet committed
waves/B9\codex-adversarial-r1.md:643:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-adversarial-r1.md:644:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion â€” this is a one-time setup change, not per-deployment.
waves/B9\codex-adversarial-r1.md:668:RECORD_COUNTS.TXT                  <- table name -> row count manifest
waves/B9\codex-adversarial-r1.md:703:**RECORD\_COUNTS.TXT:** Present, contains row count for every table name in the drop (verified counts align with zip). Example: `RNPALL|013213617` (all pricing rows), `RNDC14_NDC_MSTR` implied by `RNDCALL|000501107`.
waves/B9\codex-adversarial-r1.md:743:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-adversarial-r1.md:750:- **Tier A** â€” Pure reference/description tables. Typically code â†’ description, â‰¤ 5 columns, < 2 MB uncompressed, name suffix `D0`â€“`D9` pattern or a small static lookup. No NDC normalization, no join design, no money columns.
waves/B9\codex-adversarial-r1.md:774:| RETCNDH0\_ETC\_NDC\_HIST | 7 | 30 MB | ETC NDC history (large row count) |
waves/B9\codex-adversarial-r1.md:798:| D â€” Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-adversarial-r1.md:802:- `0009_fdb_tier_a.py` â€” 113 Tier A tables (all small; one migration is reviewable because models are uniform 2â€“5-col descriptors)
waves/B9\codex-adversarial-r1.md:809:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
waves/B9\codex-adversarial-r1.md:821:| E â€” Generic table-driven ingester | Config file (YAML/dict) maps table names â†’ TableSpec; one ingester loops all tables | RECOMMENDED for Tier A and B |
waves/B9\codex-adversarial-r1.md:827:**For Tier A + B (179 tables):**
waves/B9\codex-adversarial-r1.md:852:| Tier A: 113 tables Ã— 20 min | 37.7h |
waves/B9\codex-adversarial-r1.md:857:| FDW manifest expansion (setup_fdw.sh + testing) | 4h |
waves/B9\codex-adversarial-r1.md:859:| Integration testing (load against real zip, verify row counts vs RECORD\_COUNTS.TXT) | 8h |
waves/B9\codex-adversarial-r1.md:865:- B9.1 (Tier A, 113 tables): ~10 sessions
waves/B9\codex-adversarial-r1.md:872:**Realistic wall-clock:** 3â€“4 months for B9.1 through B9.3. Consider whether B9 is actually two waves (B9 = Tier A+B; B10 = Tier C) for milestone hygiene.
waves/B9\codex-adversarial-r1.md:884:**Risk 3 â€” FDW LIMIT TO list maintenance drift (MEDIUM)**
waves/B9\codex-adversarial-r1.md:885:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-adversarial-r1.md:906:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) â€” implementation-ready spec
waves/B9\codex-adversarial-r1.md:908:- Audit UPD zip structure: verify which tables ship as delta vs. full-replacement
waves/B9\codex-adversarial-r1.md:911:### B9.1 â€” Tier A: 113 simple lookup tables (target ~10 sessions)
waves/B9\codex-adversarial-r1.md:915:- One alembic migration `0009_fdb_tier_a.py`
waves/B9\codex-adversarial-r1.md:917:- Integration test: load against real DB zip, verify row counts vs RECORD\_COUNTS.TXT for all 113 tables
waves/B9\codex-adversarial-r1.md:918:- FDW manifest update: add 113 table names to `setup_fdw.sh` LIMIT TO list
waves/B9\codex-adversarial-r1.md:919:- Gate: 100% tests pass, row counts match RECORD\_COUNTS.TXT within 1%
waves/B9\codex-adversarial-r1.md:927:- Integration test: verify NDC join correctness against existing `fdb_ndc_price_history`
waves/B9\codex-adversarial-r1.md:928:- FDW manifest update: +66 entries
waves/B9\codex-adversarial-r1.md:938:- FDW manifest update: +19 entries
waves/B9\codex-adversarial-r1.md:957:4. **Wave boundary â€” is B9 one wave or two?**: 34 sessions is 3â€“4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-adversarial-r1.md:1224:.\AGENTS [conflicted].md:62:1659 " ⚖️ Ingester architecture: generic TableSpec-driven for Tier A+B (179 tables); per-table services for Tier C
waves/B9\codex-adversarial-r1.md:1231:.\infrastructure\scripts\init-multi-db.sql:71:-- CONNECT on infinityrx_reference for the FDW user mapping (per env's
waves/B9\codex-adversarial-r1.md:1236:.\infrastructure\scripts\init-multi-db.sql:155:-- created by setup_fdw.sh as a FDW import target, NOT here. Module schemas
waves/B9\codex-adversarial-r1.md:1254:.\infrastructure\evidence\p11a\08-loader-run-manifest.txt:28:  Ground-truth row counts (queried from infinityrx_reference)
waves/B9\codex-adversarial-r1.md:1284:.\infrastructure\scripts\setup_fdw.sh:2:# setup_fdw.sh — Wave B7 (Phase 11A) FDW configuration.
waves/B9\codex-adversarial-r1.md:1285:.\infrastructure\scripts\setup_fdw.sh:6:#   2. Idempotently create FDW server pointing at infinityrx_reference
waves/B9\codex-adversarial-r1.md:1290:.\infrastructure\scripts\setup_fdw.sh:154:  echo "  setup_fdw.sh --verify complete"
waves/B9\codex-adversarial-r1.md:1298:.\infrastructure\scripts\setup_fdw.sh:248:          OPTIONS (host '$FDW_HOST', port '5432', dbname 'infinityrx_reference');
waves/B9\codex-adversarial-r1.md:1300:.\infrastructure\scripts\setup_fdw.sh:255:      OPTIONS (SET host '$FDW_HOST', SET port '5432', SET dbname 'infinityrx_reference')"
waves/B9\codex-adversarial-r1.md:1360:.\waves\B7.2\ship.md:30:| W3 | Live cluster REVOKE/re-GRANT (14 `pharmacy_dir.dataq_*` tables) | **CLOSED** — `remaining_deps = 0`; `setup_fdw.sh --verify` 66/66 PASS | `94d5f15` |
waves/B9\codex-adversarial-r1.md:1361:.\waves\B7.2\ship.md:50:- B7: Phase 11A architecture implemented (single `infinityrx_reference` + FDW; 26.5M rows)
waves/B9\codex-adversarial-r1.md:1362:.\waves\B7.2\ship.md:52:- B7.1: Tier 1 RLS migrations env-driven; `setup_fdw.sh --verify` net-new; loader rc; OFAC fix; .sh bits; .gitignore
waves/B9\codex-adversarial-r1.md:1364:.\waves\B7.2\evidence.md:62:**setup_fdw.sh --verify post-W3:**
waves/B9\codex-adversarial-r1.md:1365:.\waves\B7.2\evidence.md:69:  setup_fdw.sh --verify complete
waves/B9\codex-adversarial-r1.md:1645:.\docs\architecture\environments.md:49:forwards to `infinityrx_reference` via the FDW server. Cross-DB JOINs
waves/B9\codex-adversarial-r1.md:1649:.\docs\architecture\environments.md:73:| `DATABASE_URL_SYNC_REFERENCE` | sync URL for `infinityrx_reference` — used by reference-data loaders only; app code reads via FDW |
waves/B9\codex-adversarial-r1.md:1653:.\docs\architecture\environments.md:88:| `ifx_ref_reader`     | read-only on infinityrx_reference + FDW user-mapping target | LOGIN |
waves/B9\codex-adversarial-r1.md:1671:.\docs\audit\wave-41-7-ai-nlp-session-audit.md:113:| F-04 | `tests/integration/test_smoke_real_db.py:56–61, 90–96, 124–136, 165–172, 191–208` | Sync `create_engine` + sync `Session` (via `sessionmaker`) used throughout the integration smoke suite. All production paths are async. | **(c) Intentional — leave as-is** | This is a deliberate architectural choice for the testcontainer ORM-mapping verification suite: sync sessions are simpler for sequential test steps, and the suite explicitly imports `install_rls_session_sync` (the sync RLS hook). No production async path is exercised by these tests; they verify schema/migration/RLS only. Do not change. |
waves/B9\codex-adversarial-r1.md:1675:.\docs\audit\wave-history [conflicted].md:47:| Wave B7.1 | 2026-05-10 | B7+B8 cleanup wave: W2 `setup_fdw.sh --verify` net-new (66/66 PASS dev+mock, closes B7 C9 Phase 2) + SELECT grant on reference foreign tables (round-2 fix); W3 Tier 1 env-drive `ifx_prod_app` in 15 RLS-policy migrations across 9 modules (`init-multi-db.sql` preserved; DROP blocked by `pg_shdepend` 31 dependents → B7.1.1; Tier 2 GRANTs deferred); W4 hygiene bundle (12 loader rc propagation, OFAC CRLF fix, .sh chmod, gitignore patterns); W1 NPPES status doc (~4.9M < 7M target → B7.1.1). **13 commits, `7e9e1ff..e30fdfb`.** SC-2/4/5/6/7/9 PASS, SC-1/SC-3 PARTIAL, SC-8 GO-WITH-FIXES (codex 2 rounds: real SELECT-grant gap fixed; 3 false positives dismissed — Tier 2 GRANTs, claude-mem pattern, wave-history timing). |
waves/B9\codex-adversarial-r1.md:1676:.\docs\audit\wave-history [conflicted].md:50:| Wave B7.2 | 2026-05-10 | **Phase 11A COMPLETE.** Tier 2 architectural GRANT wave: W1 env-drive `ifx_prod_app` in 26 files (25 Tier 2 migrations + `scripts/apply_rls.py`) via `IFX_APP_ROLE`; W2 remove `ifx_prod_app` key from both `_ROLE_PAIRS` dicts (`maxacc_registry_routes.py` + `test_helpers.py`); W3 REVOKE 14 `pharmacy_dir.dataq_*` cluster GRANTs from `ifx_prod_app` + re-GRANT to `ifx_dev_app` (`pg_shdepend = 0`; `setup_fdw.sh --verify` 66/66 PASS); W4 `DROP ROLE ifx_prod_app` (`pg_authid count = 0`). 8-suite test verification: all 8 suites match C0 baseline (no regressions). Script preserved at `infrastructure/scripts/lib/cleanup_tier2_ifx_prod_app_grants.sql`. Wave artifacts at `waves/B7.2/`. **7 commits, `2964ebc..276fd99`.** SC-1..SC-5/SC-7 PASS. Codex: SPEC 2 rounds GO-WITH-FIXES (9 concerns); PLAN + ADVERSARIAL skipped; GATE-CLOSE: R1 NO-GO (artifacts not in repo) → R2 GO-WITH-FIXES → GO (C9 placeholder fill). Deferred: `tests/integration/conftest.py:149` + `shared/config.py:159` (charter v3 explicit, non-load-bearing). `ifx_prod_app` gone from live cluster + all GRANT targets + both runtime dicts. |
waves/B9\codex-adversarial-r1.md:1706:.\docs\runbooks\reference-db-replication.md:4:**Local-tier:** implemented (single `infinityrx_reference` + FDW).
waves/B9\codex-adversarial-r1.md:1715:.\docs\runbooks\reference-db-replication.md:200:- `infrastructure/scripts/setup_fdw.sh` — FDW configuration
waves/B9\codex-adversarial-r1.md:1969:.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:423:    verifying the ON CONFLICT path returns correct inserted/duplicate counts
waves/B9\codex-adversarial-r1.md:4379:# setup_fdw.sh â€” Wave B7 (Phase 11A) FDW configuration.
waves/B9\codex-adversarial-r1.md:4383:#   2. Idempotently create FDW server pointing at infinityrx_reference
waves/B9\codex-adversarial-r1.md:4396:#              (FDW drift mitigation; uses LIMIT TO clause)
waves/B9\codex-adversarial-r1.md:4447:    --verify)  MODE="verify"; shift ;;
waves/B9\codex-adversarial-r1.md:4467:# â”€â”€ --verify mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
waves/B9\codex-adversarial-r1.md:4469:# foreign table is queryable via FDW in each target env DB.
waves/B9\codex-adversarial-r1.md:4471:# PASS = query exits 0 (empty result is fine â€” FDW link is the contract).
waves/B9\codex-adversarial-r1.md:4474:if [ "$MODE" = "verify" ]; then
waves/B9\codex-adversarial-r1.md:4505:    echo "â”€â”€ Verifying FDW foreign tables in ${env_db} â”€â”€"
waves/B9\codex-adversarial-r1.md:4531:  echo "  setup_fdw.sh --verify complete"
waves/B9\codex-adversarial-r1.md:4542:# â”€â”€ end --verify â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
waves/B9\codex-adversarial-r1.md:4554:# Schemas that exist in reference DB but should NOT be FDW-imported.
waves/B9\codex-adversarial-r1.md:4558:# local to the reference DB and don't transfer through FDW. Reference
waves/B9\codex-adversarial-r1.md:4598:  echo "â”€â”€ Setting up FDW in infinityrx_${env} â”€â”€"
waves/B9\codex-adversarial-r1.md:4600:  # Use superuser for FDW setup â€” CREATE EXTENSION requires it, and
waves/B9\codex-adversarial-r1.md:4614:  # Use the docker service name 'postgres' as the FDW host since the
waves/B9\codex-adversarial-r1.md:4618:  FDW_HOST="${FDW_HOST:-postgres}"
waves/B9\codex-adversarial-r1.md:4625:          OPTIONS (host '$FDW_HOST', port '5432', dbname 'infinityrx_reference');
waves/B9\codex-adversarial-r1.md:4632:      OPTIONS (SET host '$FDW_HOST', SET port '5432', SET dbname 'infinityrx_reference')"
waves/B9\codex-adversarial-r1.md:4716:  echo "  OK â€” FDW configured in infinityrx_${env}"
waves/B9\codex-adversarial-r1.md:5145:| 1 | Session size | M | “Next absorbs overflow” is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
waves/B9\codex-adversarial-r1.md:5146:| 2 | Migration | M | Postgres transactional DDL reduces half-applied risk, but 113-table migration failure still creates a large debug blast radius. Reverse/apply gate happens after implementation, not before merge pressure. | PARTIAL | Require generated migration dry-run on disposable DB before commit; capture `alembic upgrade + downgrade + upgrade` evidence per migration before mini-GATE. |
waves/B9\codex-adversarial-r1.md:5147:| 3 | FDW manifest | M | Additive manifest edits across sessions can conflict, and current `setup_fdw.sh --verify` hard-codes `expected 66`, so B9.B verify will fail unless this is changed. | PARTIAL | Make manifest generated or sorted deterministically; replace hard-coded 66 with an expected-count argument or manifest-derived count. |
waves/B9\codex-adversarial-r1.md:5151:| 7 | B9.F perf gate | H | Timing gate says FDW verify must complete within 5 min, but only storage has abort/escalate language. A 20-min verify could be “documented” and still pass. | PARTIAL | Add hard timing abort: if verify or weekly delta exceeds threshold, B9.F fails and requires index/query redesign before B9.G opens. |
waves/B9\codex-adversarial-r1.md:5152:| 8 | B9.G MTL FDW | H | Empty MTL foreign tables create a silent false-negative surface. A downstream join to MTL returns no rows instead of erroring. | NO | Do not expose MTL via FDW by default, or expose guarded views that raise/flag when `fdb_load_mtl=False`; update FDW count accordingly if excluded. |
waves/B9\codex-adversarial-r1.md:5153:| 9 | Calendar slip | M | Charter admits 4-5 months, but plan still gates as one large B9. Overruns can freeze visible delivery for months. | PARTIAL | Add calendar checkpoint every 4 weeks with scope/split decision; allow B9.B/B9.C shipped milestone tags even under single B9 label. |
waves/B9\codex-adversarial-r1.md:5156:| 12 | Existing 3-table coverage | M | The registry expansion could reprocess RNP3/RPRDPTD0/RNPTYPD0, change modes, or duplicate existing TableSpecs. | PARTIAL | Add compatibility tests proving existing Phase 09 modes, row counts, price lookup behavior, and `fdb_price_type_desc` synthesis are unchanged. |
waves/B9\codex-adversarial-r1.md:5158:| 14 | Adjudication ripple | H | Plan does not audit consumer queries. Adding 217 tables may not change paths directly, but new FDW names and pricing tables can alter assumptions, imports, or fallback behavior. | NO | Add consumer audit in B9.H or earlier: adjudication pricing enrichment, TCP publish path, and FDW query smoke tests with B9 data present. |
waves/B9\codex-adversarial-r1.md:5166:| FDW name collision | H | `setup_fdw.sh` imports all source schemas into one `reference` schema. 217 new FDB names could collide with existing reference table names or future schemas; the script fatals on collision. | Preflight generated B9 table names against all reference schemas before B9.B implementation starts. |
waves/B9\codex-adversarial-r1.md:5167:| Manifest semantics drift | M | Current manifest comments say only tables with `>0 rows` are included. B9.G adds empty MTL tables, contradicting the manifest contract. | Update manifest policy explicitly before adding MTL, or keep schema-only tables in a separate FDW schema/manifest. |
waves/B9\codex-adversarial-r1.md:5177:Do not fully lock execution yet. PLAN v3 needs targeted mitigations for: per-table delta semantics, reference-DB write-path enforcement, MTL FDW silent-failure prevention, B9.F timing abort criteria, consumer-side adjudication/reclaimrx audits, and current FDW manifest/script hard-coded count drift. After those are added, B9.A can close and B9.B can open with far less hidden failure surface.
waves/B9\codex-adversarial-r1.md:5188:| 1 | Session size | M | “Next absorbs overflow” is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
waves/B9\codex-adversarial-r1.md:5189:| 2 | Migration | M | Postgres transactional DDL reduces half-applied risk, but 113-table migration failure still creates a large debug blast radius. Reverse/apply gate happens after implementation, not before merge pressure. | PARTIAL | Require generated migration dry-run on disposable DB before commit; capture `alembic upgrade + downgrade + upgrade` evidence per migration before mini-GATE. |
waves/B9\codex-adversarial-r1.md:5190:| 3 | FDW manifest | M | Additive manifest edits across sessions can conflict, and current `setup_fdw.sh --verify` hard-codes `expected 66`, so B9.B verify will fail unless this is changed. | PARTIAL | Make manifest generated or sorted deterministically; replace hard-coded 66 with an expected-count argument or manifest-derived count. |
waves/B9\codex-adversarial-r1.md:5194:| 7 | B9.F perf gate | H | Timing gate says FDW verify must complete within 5 min, but only storage has abort/escalate language. A 20-min verify could be “documented” and still pass. | PARTIAL | Add hard timing abort: if verify or weekly delta exceeds threshold, B9.F fails and requires index/query redesign before B9.G opens. |
waves/B9\codex-adversarial-r1.md:5195:| 8 | B9.G MTL FDW | H | Empty MTL foreign tables create a silent false-negative surface. A downstream join to MTL returns no rows instead of erroring. | NO | Do not expose MTL via FDW by default, or expose guarded views that raise/flag when `fdb_load_mtl=False`; update FDW count accordingly if excluded. |
waves/B9\codex-adversarial-r1.md:5196:| 9 | Calendar slip | M | Charter admits 4-5 months, but plan still gates as one large B9. Overruns can freeze visible delivery for months. | PARTIAL | Add calendar checkpoint every 4 weeks with scope/split decision; allow B9.B/B9.C shipped milestone tags even under single B9 label. |
waves/B9\codex-adversarial-r1.md:5199:| 12 | Existing 3-table coverage | M | The registry expansion could reprocess RNP3/RPRDPTD0/RNPTYPD0, change modes, or duplicate existing TableSpecs. | PARTIAL | Add compatibility tests proving existing Phase 09 modes, row counts, price lookup behavior, and `fdb_price_type_desc` synthesis are unchanged. |
waves/B9\codex-adversarial-r1.md:5201:| 14 | Adjudication ripple | H | Plan does not audit consumer queries. Adding 217 tables may not change paths directly, but new FDW names and pricing tables can alter assumptions, imports, or fallback behavior. | NO | Add consumer audit in B9.H or earlier: adjudication pricing enrichment, TCP publish path, and FDW query smoke tests with B9 data present. |
waves/B9\codex-adversarial-r1.md:5209:| FDW name collision | H | `setup_fdw.sh` imports all source schemas into one `reference` schema. 217 new FDB names could collide with existing reference table names or future schemas; the script fatals on collision. | Preflight generated B9 table names against all reference schemas before B9.B implementation starts. |
waves/B9\codex-adversarial-r1.md:5210:| Manifest semantics drift | M | Current manifest comments say only tables with `>0 rows` are included. B9.G adds empty MTL tables, contradicting the manifest contract. | Update manifest policy explicitly before adding MTL, or keep schema-only tables in a separate FDW schema/manifest. |
waves/B9\codex-adversarial-r1.md:5220:Do not fully lock execution yet. PLAN v3 needs targeted mitigations for: per-table delta semantics, reference-DB write-path enforcement, MTL FDW silent-failure prevention, B9.F timing abort criteria, consumer-side adjudication/reclaimrx audits, and current FDW manifest/script hard-coded count drift. After those are added, B9.A can close and B9.B can open with far less hidden failure surface.
waves/B9\codex-adversarial-r2.md:14:You are codex acting as the ADVERSARIAL R2 reviewer for Wave B9. Your job is to verify whether PLAN v3 absorbed your R1 attack findings.
waves/B9\codex-adversarial-r2.md:28:For each attack, verify the mitigation is present, concrete, and actually closes the failure mode (not papered over):
waves/B9\codex-adversarial-r2.md:33:- A7 perf gate: HARD ABORT criteria with concrete numbers (FDW > 5min, weekly delta > 30s/table)
waves/B9\codex-adversarial-r2.md:34:- A8 MTL FDW silent: MTL excluded from default FDW manifest; charter v3.2 reflects
waves/B9\codex-adversarial-r2.md:36:- A14 adjudication ripple: B9.H Session 3 consumer audit (enrich_pricing + TCP listener + FDW smoke)
waves/B9\codex-adversarial-r2.md:38:- N1 FDW name collision: B9.A C10 preflight scan against all reference schemas
waves/B9\codex-adversarial-r2.md:44:- A3 FDW manifest: hard-coded 66 replaced with manifest-derived count
waves/B9\codex-adversarial-r2.md:51:- N2 manifest semantics: documented in manifest header (now moot — MTL not in FDW)
waves/B9\codex-adversarial-r2.md:68:| A8 MTL FDW silent | H | YES / PARTIAL / NO | <refs> | YES / NO | |
waves/B9\codex-adversarial-r2.md:72:| N1 FDW collision | H | YES / PARTIAL / NO | <refs> | YES / NO | |
waves/B9\codex-adversarial-r2.md:76:| A3 FDW manifest | M | YES / PARTIAL / NO | <refs> | YES / NO | |
waves/B9\codex-adversarial-r2.md:100:<one paragraph: if NO HIGH unaddressed → B9.A closes, B9.B opens; if HIGH unaddressed → plan v4 needed; if STRUCTURAL FLAW → architectural pause>
waves/B9\codex-adversarial-r2.md:132:**Status:** SPEC v3.2 LOCKED â€” erratum chain: (v3.1) arithmetic drift correction surfaced by codex PLAN R2 â†’ B9.B FDW `116/116`â†’`179/179`, B9.D "17 complex"â†’"16 complex"; (v3.2) MTL FDW-exposure policy surfaced by codex ADVERSARIAL R1 â†’ MTL excluded from default FDW manifest to prevent silent false-negative joins, conditional 19 entries added only when `fdb_load_mtl=True` (future MTL activation wave). B9.H final FDW count: **264/264 default, 283/283 conditional**. No scope change. See `codex-plan-consult-r2.md` and `codex-adversarial-r1.md`. Ready for PLAN v3 â†’ ADVERSARIAL R2.
waves/B9\codex-adversarial-r2.md:150:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4â€“5 months with multitasking. |
waves/B9\codex-adversarial-r2.md:156:| W1 | Tier A â€” simple lookups (â‰¤5 columns, generic ingester) | 113 | ~10 sessions |
waves/B9\codex-adversarial-r2.md:160:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
waves/B9\codex-adversarial-r2.md:173:B9 ships incrementally **with mandatory per-phase closure gates** â€” each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-adversarial-r2.md:178:| B9.B | Tier A â€” 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** â€” evidence + row-count manifest + FDW verify 179/179 + ingester contract tests |
waves/B9\codex-adversarial-r2.md:179:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests (FDW 245/245) |
waves/B9\codex-adversarial-r2.md:180:| B9.D | Tier C non-RNDC14 â€” 16 complex tables | 4 | **B9.D mini-GATE-CLOSE** (FDW 261/261) |
waves/B9\codex-adversarial-r2.md:181:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** â€” column-by-column model review |
waves/B9\codex-adversarial-r2.md:182:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** â€” perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-adversarial-r2.md:183:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** â€” integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-adversarial-r2.md:184:| B9.H | Manifest extension (66 â†’ 264 FDW entries default; +19 conditional MTL) + consumer audits + final closeout artifacts | 5 | **Final B9 GATE-CLOSE** â€” full cross-tier consult |
waves/B9\codex-adversarial-r2.md:191:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
waves/B9\codex-adversarial-r2.md:192:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-adversarial-r2.md:193:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-adversarial-r2.md:195:| SC-6 | `setup_fdw.sh --verify` 264/264 PASS in both env DBs by default (MTL excluded from FDW per ADVERSARIAL R1 mitigation); conditional 283/283 when `fdb_load_mtl=True` |
waves/B9\codex-adversarial-r2.md:198:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-adversarial-r2.md:207:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-adversarial-r2.md:208:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) â€” 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-adversarial-r2.md:215:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\codex-adversarial-r2.md:218:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
waves/B9\codex-adversarial-r2.md:231:**~39 sessions Ã— 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong â€” corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-adversarial-r2.md:235:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-adversarial-r2.md:249:**Status:** PLAN v3 DRAFT â€” folds codex ADVERSARIAL R1 mitigations (9 HIGH + 11 MEDIUM). Charter bumped to v3.2 (MTL FDW exposure policy changed). Pending ADVERSARIAL R2 verification before B9.A closes and B9.B opens.
waves/B9\codex-adversarial-r2.md:251:**Iteration history:** PLAN v1 (initial draft) â†’ PLAN R1 codex consult GO-WITH-FIXES (8 fixes) â†’ PLAN v2 (fixes absorbed) â†’ PLAN R2 codex consult GO-WITH-FIXES (charter erratum needed) â†’ charter v3.1 erratum applied â†’ PLAN GATE FINAL VERDICT GO â†’ ADVERSARIAL R1 codex consult HIGH-SEVERITY OBJECTIONS PRESENT (9 HIGH + 11 MED + 4 novel) â†’ PLAN v3 (this version, all mitigations folded in) â†’ charter v3.2 erratum applied (MTL FDW exposure) â†’ ADVERSARIAL R2 (pending).
waves/B9\codex-adversarial-r2.md:263:2. **Per-phase scope, deliverables, success-criteria mapping, gate criteria, est sessions, commit shape** for B9.B..B9.H.
waves/B9\codex-adversarial-r2.md:267:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9\codex-adversarial-r2.md:272:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-adversarial-r2.md:286:| A7 perf gate | H | "Documented" without abort | B9.F hard timing aborts: FDW verify > 5 min â†’ FAIL; per-table weekly delta > 30s â†’ FAIL; total weekly delta > 10 min â†’ FAIL. Charter SC-4 wording strengthened in plan Â§B9.F. See T15. |
waves/B9\codex-adversarial-r2.md:287:| A8 MTL FDW silent | H | Empty FDW foreign tables = silent false-negative joins | MTL excluded from default FDW manifest (charter v3.2 erratum: 264 default / 283 conditional). MTL data activation work â€” including the +19 FDW entries â€” moves to a future wave when licensing flips. See T16. |
waves/B9\codex-adversarial-r2.md:289:| A14 adjudication ripple | H | Consumer audit missing | B9.H Session 3 adds adjudication audit: pricing-enrichment path with B9 data present; TCP listener publish smoke; FDW query smoke with new tables. See T18. |
waves/B9\codex-adversarial-r2.md:291:| N1 FDW name collision | H | `setup_fdw.sh` fatals on duplicate; no preflight | B9.A C10 preflight: generate all 217 B9 table names; scan `infinityrx_reference` schemas (drug_database / drug_db / reference / shared) for collisions; abort if any. See T20. |
waves/B9\codex-adversarial-r2.md:293:| A1 session overflow | M | "Next absorbs overflow" not a control | Per-table escape-hatch: any Tier A table that consumes > 1 hour solo gets reclassified to Tier B/C; removed from `0009_fdb_tier_a.py`; FDW ladder updated; mini-re-plan triggered if session burn > +20%. See T22. |
waves/B9\codex-adversarial-r2.md:294:| A2 migration blast radius | M | 113-table migration failure = wide blast | Each migration requires `alembic upgrade + downgrade + upgrade` evidence captured on a disposable DB before commit; mini-GATE-CLOSE checks evidence file exists. See T23. |
waves/B9\codex-adversarial-r2.md:295:| A3 FDW manifest | M | Hard-coded "expected 66"; concurrent-edit conflicts | B9.A C11 replaces hard-coded 66 in `setup_fdw.sh --verify` with manifest-derived count; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is the source of truth. See T24. |
waves/B9\codex-adversarial-r2.md:296:| A6 RNDC14 iteration | M | 2 sessions fragile if 5+ type issues | B9.E iteration rule: sessions may expand from 2 â†’ up to 4 without borrowing from B9.F budget; mini-GATE-CLOSE will not close on partial column review. See T25. |
waves/B9\codex-adversarial-r2.md:297:| A9 calendar slip | M | 4-5 months freeze of visible delivery | 4-week calendar checkpoint: at week-4 / week-8 / week-12 owner reviews B9.X.* progress + decides whether to ship intermediate milestone tags (B9.B-shipped, B9.C-shipped) under the single B9 label. See T26. |
waves/B9\codex-adversarial-r2.md:299:| A12 Phase 09 compat | M | Existing 3-table coverage might break | B9.A C12 captures Phase 09 baseline: row counts for `fdb_ndc_price_history` + `fdb_price_type_desc`, query latency on representative NDC + price_type lookups, default-mode behavior. Mini-GATE-CLOSE re-runs and asserts unchanged. See T28. |
waves/B9\codex-adversarial-r2.md:302:| N2 manifest semantics | M | `>0 rows` policy contradicts B9.G empty MTL | Resolved by A8 mitigation (MTL not in default FDW). Document the policy explicitly in `infrastructure/scripts/lib/expected_reference_tables.txt` header. See T31. |
waves/B9\codex-adversarial-r2.md:312:2. **B7.2 Phase 11A COMPLETE** â€” `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
waves/B9\codex-adversarial-r2.md:313:3. **Reference DB topology stable** â€” `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-adversarial-r2.md:316:6. **134 pre-existing test failures baseline frozen** â€” at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged Â± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
waves/B9\codex-adversarial-r2.md:317:7. **FDB drop manifest reachable** â€” `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon Â§1.5 verified â€” re-verify at C0).
waves/B9\codex-adversarial-r2.md:327:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
waves/B9\codex-adversarial-r2.md:339:- **`setup_fdw.sh --verify` manifest expansion mechanism** â€” `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline â†’ 179 (after B9.B +113) â†’ 245 (after B9.C +66) â†’ 261 (after B9.D +16) â†’ 262 (after B9.E +1 RNDC14) â†’ 264 (after B9.F +2 pricing) â†’ 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-adversarial-r2.md:340:- **pytest baseline markers** â€” committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
waves/B9\codex-adversarial-r2.md:346:| C0 | Baseline + invariants captured (df, pg_authid, FDW 66/66, pytest node-ID snapshots Ã— 2 runs for flake detection) | `waves/B9/baseline.md`, `waves/B9/test_flake_quarantine.md` |
waves/B9\codex-adversarial-r2.md:356:| **C10** | **FDW name collision preflight â€” generate 217 B9 table names; scan all `infinityrx_reference` schemas; abort on any collision** | `infrastructure/scripts/preflight_b9_name_collision.py`, evidence |
waves/B9\codex-adversarial-r2.md:357:| **C11** | **`setup_fdw.sh --verify` manifest-derived count (replace hard-coded `expected 66`) + deterministic sorted manifest ordering** | `infrastructure/scripts/setup_fdw.sh`, `infrastructure/scripts/lib/expected_reference_tables.txt` |
waves/B9\codex-adversarial-r2.md:358:| **C12** | **Phase 09 compatibility baseline: capture RNP3 + RPRDPTD0 + RNPTYPD0 row counts + query latency + default-mode behavior; mini-GATE-CLOSE re-asserts unchanged at every phase** | `waves/B9/phase09_compat_baseline.md`, compat test |
waves/B9\codex-adversarial-r2.md:362:**B9.A mini-GATE-CLOSE criteria (charter SC-9, expanded for ADVERSARIAL):**
waves/B9\codex-adversarial-r2.md:366:- `setup_fdw.sh --verify` still passes against current manifest-derived count (no FDB tables added yet; expected count == current count).
waves/B9\codex-adversarial-r2.md:369:- FDW name collision preflight returns 0 collisions for all 217 generated B9 names.
waves/B9\codex-adversarial-r2.md:379:### B9.B â€” Tier A: 113 simple lookup tables (â‰¤ 5 columns, generic ingester) (10 sessions)
waves/B9\codex-adversarial-r2.md:381:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier â€” short tables (mostly < 10K rows, all â‰¤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
waves/B9\codex-adversarial-r2.md:386:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon Â§4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
waves/B9\codex-adversarial-r2.md:394:- 1 alembic migration (`0009_fdb_tier_a.py`)
waves/B9\codex-adversarial-r2.md:396:- Loader-orchestration entry: `--mode fdb_tier_a` loads only Tier A
waves/B9\codex-adversarial-r2.md:402:- SC-2 (RECORD_COUNTS reconciliation) â€” every loaded Tier A table: actual Ã· expected within Â±0.1% tolerance (small lookups should be exact)
waves/B9\codex-adversarial-r2.md:403:- SC-6 (FDW verify) â€” partial: 179/179 PASS after B9.B
waves/B9\codex-adversarial-r2.md:404:- SC-7 (weekly idempotency) â€” verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9\codex-adversarial-r2.md:405:- SC-8 (test strategy) â€” contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
waves/B9\codex-adversarial-r2.md:406:- SC-9 (mini-GATE-CLOSE) â€” see below
waves/B9\codex-adversarial-r2.md:408:**B9.B mini-GATE-CLOSE criteria:**
waves/B9\codex-adversarial-r2.md:410:- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` Â± documented tolerance
waves/B9\codex-adversarial-r2.md:411:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9\codex-adversarial-r2.md:412:- All Tier A contract tests green
waves/B9\codex-adversarial-r2.md:413:- Sampled behavioral tests: 10 randomly-picked Tier A tables exercise non-trivial query (FK join, where-clause, sort)
waves/B9\codex-adversarial-r2.md:415:- Weekly delta path: `load_fdb.py --mode fdb_tier_a` re-run produces 0 new rows (idempotent)
waves/B9\codex-adversarial-r2.md:417:- Codex mini-GATE-CLOSE consult: GO
waves/B9\codex-adversarial-r2.md:425:**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.
waves/B9\codex-adversarial-r2.md:427:**Per-session shape (12 sessions = ~5.5 tables/session â€” slower than Tier A because of join-design + FK-target verification per table):**
waves/B9\codex-adversarial-r2.md:430:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-adversarial-r2.md:440:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\codex-adversarial-r2.md:441:- FDW foreign-table count: 179 â†’ 245
waves/B9\codex-adversarial-r2.md:445:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-adversarial-r2.md:466:- FDW foreign-table count: 245 â†’ **261**
waves/B9\codex-adversarial-r2.md:471:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
waves/B9\codex-adversarial-r2.md:479:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" â€” no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-adversarial-r2.md:492:- FDW foreign-table count: 261 â†’ 262
waves/B9\codex-adversarial-r2.md:496:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
waves/B9\codex-adversarial-r2.md:509:- Session 2: Timed full-load dry run for both tables; capture wall-clock + final row count + Postgres index build time; capture `df -h` before/after
waves/B9\codex-adversarial-r2.md:511:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` â†’ 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline; **reclaimrx pricing-protocol tests** (ADVERSARIAL A15): exercise `awp_basis` distribution with populated RNP2 + RPRDPP0 + RNP3; assert no new basis values appear; assert literal-AWP guards still reject correctly
waves/B9\codex-adversarial-r2.md:520:- FDW foreign-table count: 262 â†’ 264
waves/B9\codex-adversarial-r2.md:524:**B9.F mini-GATE-CLOSE criteria â€” DRACONIAN per charter SC-4 + ADVERSARIAL A7 hard aborts:**
waves/B9\codex-adversarial-r2.md:529:- FDW + Postgres verify after indexes built: **HARD ABORT if > 5 minutes**
waves/B9\codex-adversarial-r2.md:532:- Codex mini-GATE-CLOSE consult: GO; codex reviews EXPLAIN ANALYZE for index gaps + reviews reclaimrx test deltas
waves/B9\codex-adversarial-r2.md:544:- Session 1: 19 SQLAlchemy models in `tier_d/`; migration `0014_fdb_mtl_schema.py` (un-gated, lands schema); 19 contract tests asserting tables exist + are queryable + are EMPTY. **MTL tables NOT added to FDW manifest by default** (ADVERSARIAL A8 mitigation â€” prevents silent false-negative joins from downstream queries).
waves/B9\codex-adversarial-r2.md:546:- Session 3: Integration test `test_fdb_mtl_zero_rows_under_default` (from B9.A C4) exercises the live MTL tables â€” asserts zero rows after default load. **Negative test added:** app-role INSERT into MTL table MUST fail with permission error (verifies DB-level guard works). Documentation: `docs/runbooks/fdb-mtl-opt-in.md` explains the FUTURE activation path (FDW manifest expansion to 283 + grant flip + data load) when licensing flips.
waves/B9\codex-adversarial-r2.md:557:- Runbook `docs/runbooks/fdb-mtl-opt-in.md` (covers MTL activation: FDW expansion 264â†’283, grants, loader flag flip)
waves/B9\codex-adversarial-r2.md:558:- FDW foreign-table count: 264 â†’ **264** (unchanged â€” MTL excluded by default per ADVERSARIAL A8 + charter v3.2)
waves/B9\codex-adversarial-r2.md:560:**FDW count derivation (final per charter v3.2):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D â€” 19 Tier C minus 3 special) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + **0 (B9.G MTL â€” schema-only, FDW-excluded)** = **264**. Charter v3.2 SC-6 = 264/264 default; conditional 283/283 if MTL data is later enabled.
waves/B9\codex-adversarial-r2.md:562:**Success criteria:** SC-1 (cum 217/217 â€” MTL schema present even though FDW-excluded), SC-5 (MTL zero-row test green + DB guard verified), SC-6 (264/264 default), SC-9.
waves/B9\codex-adversarial-r2.md:564:**B9.G mini-GATE-CLOSE criteria:**
waves/B9\codex-adversarial-r2.md:569:- FDW manifest verified: MTL tables NOT present (264 entries total)
waves/B9\codex-adversarial-r2.md:571:- Codex mini-GATE-CLOSE consult: GO; codex verifies (a) DB-level guard prevents app-role writes, (b) flipping `fdb_load_mtl=False` after data load DOES NOT delete data, (c) MTL exclusion from FDW is correct for default state
waves/B9\codex-adversarial-r2.md:577:**Scope:** Reconcile `expected_reference_tables.txt` to the final count (264 default), run final FDW verify, audit downstream consumers (adjudication + reclaimrx + TCP listener), produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
waves/B9\codex-adversarial-r2.md:582:- Session 2: Final `setup_fdw.sh --verify` **264/264** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables (217 + 2 existing = 219 DB tables; 264 FDW entries); published in `waves/B9/evidence.md`
waves/B9\codex-adversarial-r2.md:583:- **Session 3 (NEW â€” ADVERSARIAL A14):** Consumer audit. Runs three smoke suites against the populated reference DB: (a) **adjudication pricing-enrichment** path â€” `enrich_pricing()` returns correct WAC/AWP/NADAC + `awp_basis` for representative NDCs across all 5 pricing tables (RNP2/RNP3/RPRDPP0 + NADAC); (b) **TCP listener publish** â€” claim adjudication runs end-to-end, `claim.adjudicated` event publishes with FDB enrichment fields present; (c) **FDW query smoke** â€” adjudication, reclaimrx, network-management each run their top-3 FDB-reading queries; all succeed. Failures here trigger B9.H NO-GO and consumer-side fixes.
waves/B9\codex-adversarial-r2.md:590:- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
waves/B9\codex-adversarial-r2.md:604:- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
waves/B9\codex-adversarial-r2.md:607:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9\codex-adversarial-r2.md:622:| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
waves/B9\codex-adversarial-r2.md:623:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9\codex-adversarial-r2.md:626:| SC-6 | `setup_fdw.sh --verify` output **264/264** in dev + mock default (charter v3.2 matched); conditional 283/283 when `fdb_load_mtl=True` | B9.H Session 2 |
waves/B9\codex-adversarial-r2.md:629:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
waves/B9\codex-adversarial-r2.md:639:| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon Â§7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
waves/B9\codex-adversarial-r2.md:640:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9\codex-adversarial-r2.md:642:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
waves/B9\codex-adversarial-r2.md:645:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
waves/B9\codex-adversarial-r2.md:646:| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
waves/B9\codex-adversarial-r2.md:647:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
waves/B9\codex-adversarial-r2.md:648:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, Â± in-phase contract tests on the collection number. |
waves/B9\codex-adversarial-r2.md:649:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
waves/B9\codex-adversarial-r2.md:650:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables â€” some tables may require TRUNCATE+INSERT instead of UPSERT (recon Â§7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
waves/B9\codex-adversarial-r2.md:651:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) â€” ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
waves/B9\codex-adversarial-r2.md:653:| T15 | B9.F perf gate documented without aborting â€” slow query "passes" â€” ADVERSARIAL A7 | LOW | **HIGH** | HARD ABORT criteria: FDW verify > 5 min, per-table weekly delta > 30s, total weekly delta > 10 min, storage delta > +1.4 GB. Any breach â†’ B9.F fails, design rework required before B9.G opens. |
waves/B9\codex-adversarial-r2.md:654:| T16 | MTL FDW foreign tables empty â†’ silent false-negative downstream joins â€” ADVERSARIAL A8 | MED | **HIGH** | MTL EXCLUDED from default FDW manifest (charter v3.2 erratum). Conditional inclusion (264 â†’ 283) only when MTL data is activated. Downstream join to MTL fails LOUDLY (relation does not exist) instead of silently empty. |
waves/B9\codex-adversarial-r2.md:656:| T18 | Adjudication consumers untested against B9 data; new FDB tables may change pricing-enrichment paths â€” ADVERSARIAL A14 | MED | **HIGH** | B9.H Session 3 runs three consumer audits: (a) `enrich_pricing()` against representative NDCs, (b) TCP listener publish smoke with `claim.adjudicated` event verification, (c) FDW query smoke from adjudication + reclaimrx + network-management top-3 queries |
waves/B9\codex-adversarial-r2.md:658:| T20 | FDW name collision â€” `setup_fdw.sh` fatals on duplicate names across reference schemas â€” ADVERSARIAL N1 | LOW | **HIGH** | B9.A C10: preflight scans 217 generated B9 table names against `drug_database / drug_db / reference / shared` schemas; aborts if any collision. Test in CI per-phase. |
waves/B9\codex-adversarial-r2.md:660:| T22 | Tier A session-size overflow if a misclassified table consumes a full session â€” ADVERSARIAL A1 | MED | MED | Per-table escape-hatch: > 1h solo â†’ reclassify to Tier B/C, remove from `0009`, update FDW ladder; > 20% session burn â†’ trigger mini-replan; charter W1 budget can flex with W2 buffer if needed |
waves/B9\codex-adversarial-r2.md:661:| T23 | 113-table migration failure has large debug blast radius â€” ADVERSARIAL A2 | LOW | MED | Each migration captures `alembic upgrade + downgrade + upgrade` on a disposable DB before commit; evidence file required at mini-GATE-CLOSE; failed migration auto-flagged for codex review |
waves/B9\codex-adversarial-r2.md:662:| T24 | `setup_fdw.sh --verify` hard-codes "expected 66"; B9.B verify fails without script change â€” ADVERSARIAL A3 | LOW | MED | B9.A C11 replaces hard-coded count with manifest-derived; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is source of truth |
waves/B9\codex-adversarial-r2.md:663:| T25 | RNDC14 2-session budget insufficient if column review surfaces multiple issues â€” ADVERSARIAL A6 | MED | MED | B9.E iteration allowance: 2 â†’ up to 4 sessions without borrowing from B9.F; mini-GATE-CLOSE will not close on partial review |
waves/B9\codex-adversarial-r2.md:664:| T26 | 4-5 month wave freezes visible delivery; overruns invisible â€” ADVERSARIAL A9 | MED | MED | 4-week calendar checkpoint at weeks 4/8/12; intermediate milestone tags (B9.B-shipped, B9.C-shipped) under single B9 label; owner reviews scope/split decision at each checkpoint |
waves/B9\codex-adversarial-r2.md:666:| T28 | Existing Phase 09 coverage breaks due to registry expansion or migration interaction â€” ADVERSARIAL A12 | LOW | MED | B9.A C12 captures Phase 09 baseline: RNP3/RPRDPTD0/RNPTYPD0 row counts + query latency + default-mode behavior; per-phase mini-GATE-CLOSE re-asserts unchanged |
waves/B9\codex-adversarial-r2.md:667:| T29 | Flaky test noise drowns real signal in 134-failure baseline â€” ADVERSARIAL A13 | MED | MED | B9.A C0 captures node-ID snapshots Ã— 2 runs (NOT raw counts); known flakes quarantined in `waves/B9/test_flake_quarantine.md`; mini-GATE-CLOSE asserts node-ID delta, not count delta |
waves/B9\codex-adversarial-r2.md:669:| T31 | `expected_reference_tables.txt` `>0 rows` policy contradicts schema-only MTL â€” ADVERSARIAL N2 | LOW | LOW | Resolved by T16 (MTL not in default FDW). Document policy explicitly in manifest file header. |
waves/B9\codex-adversarial-r2.md:681:| PLAN R2 | B9.A | Plan v2 with R1 fixes; verify | `codex-plan-consult-r2.md` â€” GO-WITH-FIXES â†’ charter v3.1 erratum â†’ PLAN GATE FINAL GO |
waves/B9\codex-adversarial-r2.md:683:| **ADVERSARIAL R2** | **B9.A** | **Plan v3 with R1 mitigations absorbed; verify** | **`codex-adversarial-r2.md` â€” pending** |
waves/B9\codex-adversarial-r2.md:684:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
waves/B9\codex-adversarial-r2.md:685:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-adversarial-r2.md:686:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
waves/B9\codex-adversarial-r2.md:687:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9\codex-adversarial-r2.md:688:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9\codex-adversarial-r2.md:689:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9\codex-adversarial-r2.md:692:**Total codex consults projected:** 13 (2 SPEC + 2 PLAN + 2 ADVERSARIAL + 6 mini-GATE-CLOSE + 1 final GATE-CLOSE = 13). Token spend through ADVERSARIAL R1: ~280k. Remaining gate consults: ~50-80k for ADVERSARIAL R2 + ~300k for 6 mini-GATE-CLOSEs + ~40k for final = ~390-420k more codex tokens.
waves/B9\codex-adversarial-r2.md:712:1. **FDW final count: 283 vs 284** â†’ **RESOLVED: 283.** Tier C arithmetic bug (`19 - 3 = 16, not 17`) cascaded to 284. Plan v2 corrects all references: 66 â†’ 179 â†’ 245 â†’ 261 â†’ 262 â†’ 264 â†’ 283.
waves/B9\codex-adversarial-r2.md:713:2. **Migration count: 5 vs 6 vs 9-10** â†’ **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.
waves/B9\codex-adversarial-r2.md:714:3. **Loader-orchestration modes: existing vs new** â†’ **RESOLVED:** existing `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, `fdb_rebase`. B9.A C4 does NOT need to add `fdb_weekly`. It may need to add tier-specific modes (`fdb_tier_a`, `fdb_tier_b`, `fdb_mtl_data`) if per-tier loaders are desired; PLAN v2 leaves that as a B9.A C1 design decision (additive to existing modes).
waves/B9\codex-adversarial-r2.md:720:- **Charter Â§Workstreams view (39 sessions):** counts only productive ingest work â€” W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-adversarial-r2.md:732:- At each mini-GATE-CLOSE: full sign-off sheet committed
waves/B9\codex-adversarial-r2.md:772:1. **Session size attack:** Tier A says 12 tables/session. What if a single Tier A table has a hidden complexity (e.g., requires a join, or has > 5 columns despite recon classification)? How does the plan handle a single-session overflow without dragging the wave's 10-session budget?
waves/B9\codex-adversarial-r2.md:773:2. **Migration attack:** A single migration covering 113 tables (Tier A) is large. What if alembic apply fails partway? Is there a rollback strategy? Can a half-applied migration leave the DB in a state that blocks reverse?
waves/B9\codex-adversarial-r2.md:774:3. **FDW manifest attack:** The plan additively grows `expected_reference_tables.txt`. What if two phases both touch this file in parallel sessions? Is there merge-conflict resolution?
waves/B9\codex-adversarial-r2.md:779:6. **B9.E RNDC14 attack:** Plan dedicates 2 sessions to a 68-column model. What if column-by-column codex review surfaces 5+ type-correctness issues? Does the mini-GATE-CLOSE allow iteration, or does it fail outright?
waves/B9\codex-adversarial-r2.md:780:7. **B9.F perf gate attack:** RNP2+RPRDPP0 timed dry-run says â‰¤ 5 min FDW verify after indexes. What if the actual dry-run takes 20 min? What's the abort criterion? Charter says "abort + escalate if > +1.4 GB" for storage â€” but no explicit abort for timing.
waves/B9\codex-adversarial-r2.md:781:8. **B9.G MTL FDW attack:** Plan says MTL tables ARE in FDW as foreign-table entries pointing at empty reference tables. What if a downstream query joins to an MTL foreign table? Postgres won't error, but the join returns empty â€” silent failure mode.
waves/B9\codex-adversarial-r2.md:789:12. **Existing 3-table coverage interaction:** Phase 09 covers RNP3 + RPRDPTD0 + RNPTYPD0. Does B9.A's new TableSpec registry change break these? Migration `0009_fdb_tier_a` is independent of them, but the registry might re-process them.
waves/B9\codex-adversarial-r2.md:790:13. **Test count baseline assumption:** Plan freezes 134 failures. What if those 134 include flaky tests that pass 30% of the time? Then mini-GATE-CLOSE might falsely show 135 failures one session and 132 the next.
waves/B9\codex-adversarial-r2.md:793:14. **adjudication-engine ripple:** Adjudication queries FDB tables via reference DB FDW. If B9 adds 217 new FDB tables, does adjudication's query path change? Plan doesn't audit the consumer side.
waves/B9\codex-adversarial-r2.md:821:<one paragraph: if no HIGH unaddressed â†’ PLAN locks fully, B9.A closes, B9.B opens; if HIGH unaddressed â†’ plan v3 needs <list of required mitigations>; if STRUCTURAL FLAW â†’ escalate to architectural pause>
waves/B9\codex-adversarial-r2.md:836:**Status:** SPEC v3.1 LOCKED Ã¢â‚¬â€ SPEC v3 + erratum applied after codex PLAN R2 surfaced arithmetic drift between charter and PLAN v2. Erratum: B9.B closure-gate FDW count `116/116` Ã¢â€ â€™ `179/179`; B9.D scope "17 complex tables" Ã¢â€ â€™ "16 complex tables" (19 Tier C minus 3 special-handled). No scope change; arithmetic correction only. See `codex-plan-consult-r2.md`. Ready for PLAN v2 Ã¢â€ â€™ ADVERSARIAL.
waves/B9\codex-adversarial-r2.md:854:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4Ã¢â‚¬â€œ5 months with multitasking. |
waves/B9\codex-adversarial-r2.md:860:| W1 | Tier A Ã¢â‚¬â€ simple lookups (Ã¢â€°Â¤5 columns, generic ingester) | 113 | ~10 sessions |
waves/B9\codex-adversarial-r2.md:864:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
waves/B9\codex-adversarial-r2.md:877:B9 ships incrementally **with mandatory per-phase closure gates** Ã¢â‚¬â€ each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-adversarial-r2.md:882:| B9.B | Tier A Ã¢â‚¬â€ 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** Ã¢â‚¬â€ evidence + row-count manifest + FDW verify 179/179 + ingester contract tests |
waves/B9\codex-adversarial-r2.md:883:| B9.C | Tier B Ã¢â‚¬â€ 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** Ã¢â‚¬â€ same scope + per-tier sampled behavioral tests (FDW 245/245) |
waves/B9\codex-adversarial-r2.md:884:| B9.D | Tier C non-RNDC14 Ã¢â‚¬â€ 16 complex tables | 4 | **B9.D mini-GATE-CLOSE** (FDW 261/261) |
waves/B9\codex-adversarial-r2.md:885:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** Ã¢â‚¬â€ column-by-column model review |
waves/B9\codex-adversarial-r2.md:886:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** Ã¢â‚¬â€ perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-adversarial-r2.md:887:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** Ã¢â‚¬â€ integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-adversarial-r2.md:888:| B9.H | Manifest extension (66 Ã¢â€ â€™ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** Ã¢â‚¬â€ full cross-tier consult |
waves/B9\codex-adversarial-r2.md:895:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Ã‚Â± documented tolerance (MTL excluded Ã¢â‚¬â€ schema-only) |
waves/B9\codex-adversarial-r2.md:896:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-adversarial-r2.md:897:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-adversarial-r2.md:899:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
waves/B9\codex-adversarial-r2.md:902:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-adversarial-r2.md:911:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-adversarial-r2.md:912:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) Ã¢â‚¬â€ 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-adversarial-r2.md:919:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\codex-adversarial-r2.md:922:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
waves/B9\codex-adversarial-r2.md:935:**~39 sessions Ãƒâ€” 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong Ã¢â‚¬â€ corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-adversarial-r2.md:939:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification Ã¢â‚¬â€ preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-adversarial-r2.md:953:**Status:** PLAN v2 LOCKED Ã¢â‚¬â€ codex PLAN R1 GO-WITH-FIXES (8 fixes) + PLAN R2 GO-WITH-FIXES (charter erratum) + PLAN GATE FINAL VERDICT GO (`codex-plan-consult-r2.md`). Pending codex ADVERSARIAL consult before B9.A closes and B9.B opens.
waves/B9\codex-adversarial-r2.md:965:2. **Per-phase scope, deliverables, success-criteria mapping, gate criteria, est sessions, commit shape** for B9.B..B9.H.
waves/B9\codex-adversarial-r2.md:969:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9\codex-adversarial-r2.md:974:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-adversarial-r2.md:985:2. **B7.2 Phase 11A COMPLETE** Ã¢â‚¬â€ `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
waves/B9\codex-adversarial-r2.md:986:3. **Reference DB topology stable** Ã¢â‚¬â€ `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-adversarial-r2.md:989:6. **134 pre-existing test failures baseline frozen** Ã¢â‚¬â€ at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged Ã‚Â± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
waves/B9\codex-adversarial-r2.md:990:7. **FDB drop manifest reachable** Ã¢â‚¬â€ `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon Ã‚Â§1.5 verified Ã¢â‚¬â€ re-verify at C0).
waves/B9\codex-adversarial-r2.md:1000:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
waves/B9\codex-adversarial-r2.md:1012:- **`setup_fdw.sh --verify` manifest expansion mechanism** Ã¢â‚¬â€ `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline Ã¢â€ â€™ 179 (after B9.B +113) Ã¢â€ â€™ 245 (after B9.C +66) Ã¢â€ â€™ 261 (after B9.D +16) Ã¢â€ â€™ 262 (after B9.E +1 RNDC14) Ã¢â€ â€™ 264 (after B9.F +2 pricing) Ã¢â€ â€™ 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-adversarial-r2.md:1013:- **pytest baseline markers** Ã¢â‚¬â€ committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
waves/B9\codex-adversarial-r2.md:1019:| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
waves/B9\codex-adversarial-r2.md:1028:**B9.A mini-GATE-CLOSE criteria (charter SC-9):**
waves/B9\codex-adversarial-r2.md:1032:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
waves/B9\codex-adversarial-r2.md:1038:### B9.B Ã¢â‚¬â€ Tier A: 113 simple lookup tables (Ã¢â€°Â¤ 5 columns, generic ingester) (10 sessions)
waves/B9\codex-adversarial-r2.md:1040:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier Ã¢â‚¬â€ short tables (mostly < 10K rows, all Ã¢â€°Â¤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
waves/B9\codex-adversarial-r2.md:1045:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon Ã‚Â§4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
waves/B9\codex-adversarial-r2.md:1053:- 1 alembic migration (`0009_fdb_tier_a.py`)
waves/B9\codex-adversarial-r2.md:1055:- Loader-orchestration entry: `--mode fdb_tier_a` loads only Tier A
waves/B9\codex-adversarial-r2.md:1061:- SC-2 (RECORD_COUNTS reconciliation) Ã¢â‚¬â€ every loaded Tier A table: actual ÃƒÂ· expected within Ã‚Â±0.1% tolerance (small lookups should be exact)
waves/B9\codex-adversarial-r2.md:1062:- SC-6 (FDW verify) Ã¢â‚¬â€ partial: 179/179 PASS after B9.B
waves/B9\codex-adversarial-r2.md:1063:- SC-7 (weekly idempotency) Ã¢â‚¬â€ verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9\codex-adversarial-r2.md:1064:- SC-8 (test strategy) Ã¢â‚¬â€ contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
waves/B9\codex-adversarial-r2.md:1065:- SC-9 (mini-GATE-CLOSE) Ã¢â‚¬â€ see below
waves/B9\codex-adversarial-r2.md:1067:**B9.B mini-GATE-CLOSE criteria:**
waves/B9\codex-adversarial-r2.md:1069:- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` Ã‚Â± documented tolerance
waves/B9\codex-adversarial-r2.md:1070:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9\codex-adversarial-r2.md:1071:- All Tier A contract tests green
waves/B9\codex-adversarial-r2.md:1072:- Sampled behavioral tests: 10 randomly-picked Tier A tables exercise non-trivial query (FK join, where-clause, sort)
waves/B9\codex-adversarial-r2.md:1074:- Weekly delta path: `load_fdb.py --mode fdb_tier_a` re-run produces 0 new rows (idempotent)
waves/B9\codex-adversarial-r2.md:1076:- Codex mini-GATE-CLOSE consult: GO
waves/B9\codex-adversarial-r2.md:1084:**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.
waves/B9\codex-adversarial-r2.md:1086:**Per-session shape (12 sessions = ~5.5 tables/session Ã¢â‚¬â€ slower than Tier A because of join-design + FK-target verification per table):**
waves/B9\codex-adversarial-r2.md:1089:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-adversarial-r2.md:1099:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\codex-adversarial-r2.md:1100:- FDW foreign-table count: 179 Ã¢â€ â€™ 245
waves/B9\codex-adversarial-r2.md:1104:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-adversarial-r2.md:1125:- FDW foreign-table count: 245 Ã¢â€ â€™ **261**
waves/B9\codex-adversarial-r2.md:1130:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
waves/B9\codex-adversarial-r2.md:1138:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" Ã¢â‚¬â€ no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-adversarial-r2.md:1151:- FDW foreign-table count: 261 Ã¢â€ â€™ 262
waves/B9\codex-adversarial-r2.md:1155:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
waves/B9\codex-adversarial-r2.md:1166:- Session 2: Timed full-load dry run for both tables; capture wall-clock + final row count + Postgres index build time; capture `df -h` before/after
waves/B9\codex-adversarial-r2.md:1168:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` Ã¢â€ â€™ 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline
waves/B9\codex-adversarial-r2.md:1177:- FDW foreign-table count: 262 Ã¢â€ â€™ 264
waves/B9\codex-adversarial-r2.md:1181:**B9.F mini-GATE-CLOSE criteria Ã¢â‚¬â€ DRACONIAN per charter SC-4:**
waves/B9\codex-adversarial-r2.md:1186:- FDW + Postgres verify after indexes built: completes within 5 min
waves/B9\codex-adversarial-r2.md:1188:- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps
waves/B9\codex-adversarial-r2.md:1211:- FDW foreign-table count: 264 Ã¢â€ â€™ **283** (MTL tables ARE in FDW even though data isn't loaded Ã¢â‚¬â€ they exist as foreign-table entries pointing at empty reference tables)
waves/B9\codex-adversarial-r2.md:1213:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D Ã¢â‚¬â€ 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
waves/B9\codex-adversarial-r2.md:1217:**B9.G mini-GATE-CLOSE criteria:**
waves/B9\codex-adversarial-r2.md:1222:- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)
waves/B9\codex-adversarial-r2.md:1228:**Scope:** Reconcile `infrastructure/scripts/lib/expected_reference_tables.txt` to the true final count, run final FDW verify, produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
waves/B9\codex-adversarial-r2.md:1233:- Session 2: Final `setup_fdw.sh --verify` **283/283** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables; published in `waves/B9/evidence.md`
waves/B9\codex-adversarial-r2.md:1240:- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
waves/B9\codex-adversarial-r2.md:1254:- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
waves/B9\codex-adversarial-r2.md:1257:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9\codex-adversarial-r2.md:1272:| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
waves/B9\codex-adversarial-r2.md:1273:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9\codex-adversarial-r2.md:1276:| SC-6 | `setup_fdw.sh --verify` output **283/283** in dev + mock (charter-matched) | B9.H Session 2 |
waves/B9\codex-adversarial-r2.md:1279:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
waves/B9\codex-adversarial-r2.md:1289:| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon Ã‚Â§7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
waves/B9\codex-adversarial-r2.md:1290:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9\codex-adversarial-r2.md:1292:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
waves/B9\codex-adversarial-r2.md:1295:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
waves/B9\codex-adversarial-r2.md:1296:| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
waves/B9\codex-adversarial-r2.md:1297:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
waves/B9\codex-adversarial-r2.md:1298:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, Ã‚Â± in-phase contract tests on the collection number. |
waves/B9\codex-adversarial-r2.md:1299:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
waves/B9\codex-adversarial-r2.md:1300:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables Ã¢â‚¬â€ some tables may require TRUNCATE+INSERT instead of UPSERT (recon Ã‚Â§7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
waves/B9\codex-adversarial-r2.md:1311:| **PLAN R2** | **B9.A** | **Plan v2 with R1 fixes absorbed; verify** | **`codex-plan-consult-r2.md` Ã¢â‚¬â€ pending** |
waves/B9\codex-adversarial-r2.md:1313:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
waves/B9\codex-adversarial-r2.md:1314:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-adversarial-r2.md:1315:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
waves/B9\codex-adversarial-r2.md:1316:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9\codex-adversarial-r2.md:1317:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9\codex-adversarial-r2.md:1318:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9\codex-adversarial-r2.md:1321:**Total codex consults projected:** 12 (2 SPEC done + PLAN R1 done + PLAN R2 + ADVERSARIAL + 6 mini-GATE-CLOSE + final GATE-CLOSE = 12).
waves/B9\codex-adversarial-r2.md:1341:1. **FDW final count: 283 vs 284** Ã¢â€ â€™ **RESOLVED: 283.** Tier C arithmetic bug (`19 - 3 = 16, not 17`) cascaded to 284. Plan v2 corrects all references: 66 Ã¢â€ â€™ 179 Ã¢â€ â€™ 245 Ã¢â€ â€™ 261 Ã¢â€ â€™ 262 Ã¢â€ â€™ 264 Ã¢â€ â€™ 283.
waves/B9\codex-adversarial-r2.md:1342:2. **Migration count: 5 vs 6 vs 9-10** Ã¢â€ â€™ **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.
waves/B9\codex-adversarial-r2.md:1343:3. **Loader-orchestration modes: existing vs new** Ã¢â€ â€™ **RESOLVED:** existing `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, `fdb_rebase`. B9.A C4 does NOT need to add `fdb_weekly`. It may need to add tier-specific modes (`fdb_tier_a`, `fdb_tier_b`, `fdb_mtl_data`) if per-tier loaders are desired; PLAN v2 leaves that as a B9.A C1 design decision (additive to existing modes).
waves/B9\codex-adversarial-r2.md:1349:- **Charter Ã‚Â§Workstreams view (39 sessions):** counts only productive ingest work Ã¢â‚¬â€ W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-adversarial-r2.md:1361:- At each mini-GATE-CLOSE: full sign-off sheet committed
waves/B9\codex-adversarial-r2.md:1381:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-adversarial-r2.md:1382:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion Ã¢â‚¬â€ this is a one-time setup change, not per-deployment.
waves/B9\codex-adversarial-r2.md:1406:RECORD_COUNTS.TXT                  <- table name -> row count manifest
waves/B9\codex-adversarial-r2.md:1441:**RECORD\_COUNTS.TXT:** Present, contains row count for every table name in the drop (verified counts align with zip). Example: `RNPALL|013213617` (all pricing rows), `RNDC14_NDC_MSTR` implied by `RNDCALL|000501107`.
waves/B9\codex-adversarial-r2.md:1481:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-adversarial-r2.md:1488:- **Tier A** Ã¢â‚¬â€ Pure reference/description tables. Typically code Ã¢â€ â€™ description, Ã¢â€°Â¤ 5 columns, < 2 MB uncompressed, name suffix `D0`Ã¢â‚¬â€œ`D9` pattern or a small static lookup. No NDC normalization, no join design, no money columns.
waves/B9\codex-adversarial-r2.md:1512:| RETCNDH0\_ETC\_NDC\_HIST | 7 | 30 MB | ETC NDC history (large row count) |
waves/B9\codex-adversarial-r2.md:1536:| D Ã¢â‚¬â€ Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-adversarial-r2.md:1540:- `0009_fdb_tier_a.py` Ã¢â‚¬â€ 113 Tier A tables (all small; one migration is reviewable because models are uniform 2Ã¢â‚¬â€œ5-col descriptors)
waves/B9\codex-adversarial-r2.md:1547:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
waves/B9\codex-adversarial-r2.md:1559:| E Ã¢â‚¬â€ Generic table-driven ingester | Config file (YAML/dict) maps table names Ã¢â€ â€™ TableSpec; one ingester loops all tables | RECOMMENDED for Tier A and B |
waves/B9\codex-adversarial-r2.md:1565:**For Tier A + B (179 tables):**
waves/B9\codex-adversarial-r2.md:1590:| Tier A: 113 tables Ãƒâ€” 20 min | 37.7h |
waves/B9\codex-adversarial-r2.md:1595:| FDW manifest expansion (setup_fdw.sh + testing) | 4h |
waves/B9\codex-adversarial-r2.md:1597:| Integration testing (load against real zip, verify row counts vs RECORD\_COUNTS.TXT) | 8h |
waves/B9\codex-adversarial-r2.md:1603:- B9.1 (Tier A, 113 tables): ~10 sessions
waves/B9\codex-adversarial-r2.md:1610:**Realistic wall-clock:** 3Ã¢â‚¬â€œ4 months for B9.1 through B9.3. Consider whether B9 is actually two waves (B9 = Tier A+B; B10 = Tier C) for milestone hygiene.
waves/B9\codex-adversarial-r2.md:1622:**Risk 3 Ã¢â‚¬â€ FDW LIMIT TO list maintenance drift (MEDIUM)**
waves/B9\codex-adversarial-r2.md:1623:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-adversarial-r2.md:1644:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) Ã¢â‚¬â€ implementation-ready spec
waves/B9\codex-adversarial-r2.md:1646:- Audit UPD zip structure: verify which tables ship as delta vs. full-replacement
waves/B9\codex-adversarial-r2.md:1649:### B9.1 Ã¢â‚¬â€ Tier A: 113 simple lookup tables (target ~10 sessions)
waves/B9\codex-adversarial-r2.md:1653:- One alembic migration `0009_fdb_tier_a.py`
waves/B9\codex-adversarial-r2.md:1655:- Integration test: load against real DB zip, verify row counts vs RECORD\_COUNTS.TXT for all 113 tables
waves/B9\codex-adversarial-r2.md:1656:- FDW manifest update: add 113 table names to `setup_fdw.sh` LIMIT TO list
waves/B9\codex-adversarial-r2.md:1657:- Gate: 100% tests pass, row counts match RECORD\_COUNTS.TXT within 1%
waves/B9\codex-adversarial-r2.md:1665:- Integration test: verify NDC join correctness against existing `fdb_ndc_price_history`
waves/B9\codex-adversarial-r2.md:1666:- FDW manifest update: +66 entries
waves/B9\codex-adversarial-r2.md:1676:- FDW manifest update: +19 entries
waves/B9\codex-adversarial-r2.md:1695:4. **Wave boundary Ã¢â‚¬â€ is B9 one wave or two?**: 34 sessions is 3Ã¢â‚¬â€œ4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-adversarial-r2.md:1962:.\AGENTS [conflicted].md:62:1659 " âš–ï¸ Ingester architecture: generic TableSpec-driven for Tier A+B (179 tables); per-table services for Tier C
waves/B9\codex-adversarial-r2.md:1969:.\infrastructure\scripts\init-multi-db.sql:71:-- CONNECT on infinityrx_reference for the FDW user mapping (per env's
waves/B9\codex-adversarial-r2.md:1974:.\infrastructure\scripts\init-multi-db.sql:155:-- created by setup_fdw.sh as a FDW import target, NOT here. Module schemas
waves/B9\codex-adversarial-r2.md:1992:.\infrastructure\evidence\p11a\08-loader-run-manifest.txt:28:  Ground-truth row counts (queried from infinityrx_reference)
waves/B9\codex-adversarial-r2.md:2022:.\infrastructure\scripts\setup_fdw.sh:2:# setup_fdw.sh â€” Wave B7 (Phase 11A) FDW configuration.
waves/B9\codex-adversarial-r2.md:2023:.\infrastructure\scripts\setup_fdw.sh:6:#   2. Idempotently create FDW server pointing at infinityrx_reference
waves/B9\codex-adversarial-r2.md:2028:.\infrastructure\scripts\setup_fdw.sh:154:  echo "  setup_fdw.sh --verify complete"
waves/B9\codex-adversarial-r2.md:2036:.\infrastructure\scripts\setup_fdw.sh:248:          OPTIONS (host '$FDW_HOST', port '5432', dbname 'infinityrx_reference');
waves/B9\codex-adversarial-r2.md:2038:.\infrastructure\scripts\setup_fdw.sh:255:      OPTIONS (SET host '$FDW_HOST', SET port '5432', SET dbname 'infinityrx_reference')"
waves/B9\codex-adversarial-r2.md:2098:.\waves\B7.2\ship.md:30:| W3 | Live cluster REVOKE/re-GRANT (14 `pharmacy_dir.dataq_*` tables) | **CLOSED** â€” `remaining_deps = 0`; `setup_fdw.sh --verify` 66/66 PASS | `94d5f15` |
waves/B9\codex-adversarial-r2.md:2099:.\waves\B7.2\ship.md:50:- B7: Phase 11A architecture implemented (single `infinityrx_reference` + FDW; 26.5M rows)
waves/B9\codex-adversarial-r2.md:2100:.\waves\B7.2\ship.md:52:- B7.1: Tier 1 RLS migrations env-driven; `setup_fdw.sh --verify` net-new; loader rc; OFAC fix; .sh bits; .gitignore
waves/B9\codex-adversarial-r2.md:2102:.\waves\B7.2\evidence.md:62:**setup_fdw.sh --verify post-W3:**
waves/B9\codex-adversarial-r2.md:2103:.\waves\B7.2\evidence.md:69:  setup_fdw.sh --verify complete
waves/B9\codex-adversarial-r2.md:2383:.\docs\architecture\environments.md:49:forwards to `infinityrx_reference` via the FDW server. Cross-DB JOINs
waves/B9\codex-adversarial-r2.md:2387:.\docs\architecture\environments.md:73:| `DATABASE_URL_SYNC_REFERENCE` | sync URL for `infinityrx_reference` â€” used by reference-data loaders only; app code reads via FDW |
waves/B9\codex-adversarial-r2.md:2391:.\docs\architecture\environments.md:88:| `ifx_ref_reader`     | read-only on infinityrx_reference + FDW user-mapping target | LOGIN |
waves/B9\codex-adversarial-r2.md:2409:.\docs\audit\wave-41-7-ai-nlp-session-audit.md:113:| F-04 | `tests/integration/test_smoke_real_db.py:56â€“61, 90â€“96, 124â€“136, 165â€“172, 191â€“208` | Sync `create_engine` + sync `Session` (via `sessionmaker`) used throughout the integration smoke suite. All production paths are async. | **(c) Intentional â€” leave as-is** | This is a deliberate architectural choice for the testcontainer ORM-mapping verification suite: sync sessions are simpler for sequential test steps, and the suite explicitly imports `install_rls_session_sync` (the sync RLS hook). No production async path is exercised by these tests; they verify schema/migration/RLS only. Do not change. |
waves/B9\codex-adversarial-r2.md:2413:.\docs\audit\wave-history [conflicted].md:47:| Wave B7.1 | 2026-05-10 | B7+B8 cleanup wave: W2 `setup_fdw.sh --verify` net-new (66/66 PASS dev+mock, closes B7 C9 Phase 2) + SELECT grant on reference foreign tables (round-2 fix); W3 Tier 1 env-drive `ifx_prod_app` in 15 RLS-policy migrations across 9 modules (`init-multi-db.sql` preserved; DROP blocked by `pg_shdepend` 31 dependents â†’ B7.1.1; Tier 2 GRANTs deferred); W4 hygiene bundle (12 loader rc propagation, OFAC CRLF fix, .sh chmod, gitignore patterns); W1 NPPES status doc (~4.9M < 7M target â†’ B7.1.1). **13 commits, `7e9e1ff..e30fdfb`.** SC-2/4/5/6/7/9 PASS, SC-1/SC-3 PARTIAL, SC-8 GO-WITH-FIXES (codex 2 rounds: real SELECT-grant gap fixed; 3 false positives dismissed â€” Tier 2 GRANTs, claude-mem pattern, wave-history timing). |
waves/B9\codex-adversarial-r2.md:2414:.\docs\audit\wave-history [conflicted].md:50:| Wave B7.2 | 2026-05-10 | **Phase 11A COMPLETE.** Tier 2 architectural GRANT wave: W1 env-drive `ifx_prod_app` in 26 files (25 Tier 2 migrations + `scripts/apply_rls.py`) via `IFX_APP_ROLE`; W2 remove `ifx_prod_app` key from both `_ROLE_PAIRS` dicts (`maxacc_registry_routes.py` + `test_helpers.py`); W3 REVOKE 14 `pharmacy_dir.dataq_*` cluster GRANTs from `ifx_prod_app` + re-GRANT to `ifx_dev_app` (`pg_shdepend = 0`; `setup_fdw.sh --verify` 66/66 PASS); W4 `DROP ROLE ifx_prod_app` (`pg_authid count = 0`). 8-suite test verification: all 8 suites match C0 baseline (no regressions). Script preserved at `infrastructure/scripts/lib/cleanup_tier2_ifx_prod_app_grants.sql`. Wave artifacts at `waves/B7.2/`. **7 commits, `2964ebc..276fd99`.** SC-1..SC-5/SC-7 PASS. Codex: SPEC 2 rounds GO-WITH-FIXES (9 concerns); PLAN + ADVERSARIAL skipped; GATE-CLOSE: R1 NO-GO (artifacts not in repo) â†’ R2 GO-WITH-FIXES â†’ GO (C9 placeholder fill). Deferred: `tests/integration/conftest.py:149` + `shared/config.py:159` (charter v3 explicit, non-load-bearing). `ifx_prod_app` gone from live cluster + all GRANT targets + both runtime dicts. |
waves/B9\codex-adversarial-r2.md:2444:.\docs\runbooks\reference-db-replication.md:4:**Local-tier:** implemented (single `infinityrx_reference` + FDW).
waves/B9\codex-adversarial-r2.md:2453:.\docs\runbooks\reference-db-replication.md:200:- `infrastructure/scripts/setup_fdw.sh` â€” FDW configuration
waves/B9\codex-adversarial-r2.md:2707:.\modules\drug-database\tests\unit\test_fdb_pricing_ingester.py:423:    verifying the ON CONFLICT path returns correct inserted/duplicate counts
waves/B9\codex-adversarial-r2.md:5117:# setup_fdw.sh Ã¢â‚¬â€ Wave B7 (Phase 11A) FDW configuration.
waves/B9\codex-adversarial-r2.md:5121:#   2. Idempotently create FDW server pointing at infinityrx_reference
waves/B9\codex-adversarial-r2.md:5134:#              (FDW drift mitigation; uses LIMIT TO clause)
waves/B9\codex-adversarial-r2.md:5185:    --verify)  MODE="verify"; shift ;;
waves/B9\codex-adversarial-r2.md:5205:# Ã¢â€â‚¬Ã¢â€â‚¬ --verify mode Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
waves/B9\codex-adversarial-r2.md:5207:# foreign table is queryable via FDW in each target env DB.
waves/B9\codex-adversarial-r2.md:5209:# PASS = query exits 0 (empty result is fine Ã¢â‚¬â€ FDW link is the contract).
waves/B9\codex-adversarial-r2.md:5212:if [ "$MODE" = "verify" ]; then
waves/B9\codex-adversarial-r2.md:5243:    echo "Ã¢â€â‚¬Ã¢â€â‚¬ Verifying FDW foreign tables in ${env_db} Ã¢â€â‚¬Ã¢â€â‚¬"
waves/B9\codex-adversarial-r2.md:5269:  echo "  setup_fdw.sh --verify complete"
waves/B9\codex-adversarial-r2.md:5280:# Ã¢â€â‚¬Ã¢â€â‚¬ end --verify Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
waves/B9\codex-adversarial-r2.md:5292:# Schemas that exist in reference DB but should NOT be FDW-imported.
waves/B9\codex-adversarial-r2.md:5296:# local to the reference DB and don't transfer through FDW. Reference
waves/B9\codex-adversarial-r2.md:5336:  echo "Ã¢â€â‚¬Ã¢â€â‚¬ Setting up FDW in infinityrx_${env} Ã¢â€â‚¬Ã¢â€â‚¬"
waves/B9\codex-adversarial-r2.md:5338:  # Use superuser for FDW setup Ã¢â‚¬â€ CREATE EXTENSION requires it, and
waves/B9\codex-adversarial-r2.md:5352:  # Use the docker service name 'postgres' as the FDW host since the
waves/B9\codex-adversarial-r2.md:5356:  FDW_HOST="${FDW_HOST:-postgres}"
waves/B9\codex-adversarial-r2.md:5363:          OPTIONS (host '$FDW_HOST', port '5432', dbname 'infinityrx_reference');
waves/B9\codex-adversarial-r2.md:5370:      OPTIONS (SET host '$FDW_HOST', SET port '5432', SET dbname 'infinityrx_reference')"
waves/B9\codex-adversarial-r2.md:5454:  echo "  OK Ã¢â‚¬â€ FDW configured in infinityrx_${env}"
waves/B9\codex-adversarial-r2.md:5883:| 1 | Session size | M | â€œNext absorbs overflowâ€ is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
waves/B9\codex-adversarial-r2.md:5884:| 2 | Migration | M | Postgres transactional DDL reduces half-applied risk, but 113-table migration failure still creates a large debug blast radius. Reverse/apply gate happens after implementation, not before merge pressure. | PARTIAL | Require generated migration dry-run on disposable DB before commit; capture `alembic upgrade + downgrade + upgrade` evidence per migration before mini-GATE. |
waves/B9\codex-adversarial-r2.md:5885:| 3 | FDW manifest | M | Additive manifest edits across sessions can conflict, and current `setup_fdw.sh --verify` hard-codes `expected 66`, so B9.B verify will fail unless this is changed. | PARTIAL | Make manifest generated or sorted deterministically; replace hard-coded 66 with an expected-count argument or manifest-derived count. |
waves/B9\codex-adversarial-r2.md:5889:| 7 | B9.F perf gate | H | Timing gate says FDW verify must complete within 5 min, but only storage has abort/escalate language. A 20-min verify could be â€œdocumentedâ€ and still pass. | PARTIAL | Add hard timing abort: if verify or weekly delta exceeds threshold, B9.F fails and requires index/query redesign before B9.G opens. |
waves/B9\codex-adversarial-r2.md:5890:| 8 | B9.G MTL FDW | H | Empty MTL foreign tables create a silent false-negative surface. A downstream join to MTL returns no rows instead of erroring. | NO | Do not expose MTL via FDW by default, or expose guarded views that raise/flag when `fdb_load_mtl=False`; update FDW count accordingly if excluded. |
waves/B9\codex-adversarial-r2.md:5891:| 9 | Calendar slip | M | Charter admits 4-5 months, but plan still gates as one large B9. Overruns can freeze visible delivery for months. | PARTIAL | Add calendar checkpoint every 4 weeks with scope/split decision; allow B9.B/B9.C shipped milestone tags even under single B9 label. |
waves/B9\codex-adversarial-r2.md:5894:| 12 | Existing 3-table coverage | M | The registry expansion could reprocess RNP3/RPRDPTD0/RNPTYPD0, change modes, or duplicate existing TableSpecs. | PARTIAL | Add compatibility tests proving existing Phase 09 modes, row counts, price lookup behavior, and `fdb_price_type_desc` synthesis are unchanged. |
waves/B9\codex-adversarial-r2.md:5896:| 14 | Adjudication ripple | H | Plan does not audit consumer queries. Adding 217 tables may not change paths directly, but new FDW names and pricing tables can alter assumptions, imports, or fallback behavior. | NO | Add consumer audit in B9.H or earlier: adjudication pricing enrichment, TCP publish path, and FDW query smoke tests with B9 data present. |
waves/B9\codex-adversarial-r2.md:5904:| FDW name collision | H | `setup_fdw.sh` imports all source schemas into one `reference` schema. 217 new FDB names could collide with existing reference table names or future schemas; the script fatals on collision. | Preflight generated B9 table names against all reference schemas before B9.B implementation starts. |
waves/B9\codex-adversarial-r2.md:5905:| Manifest semantics drift | M | Current manifest comments say only tables with `>0 rows` are included. B9.G adds empty MTL tables, contradicting the manifest contract. | Update manifest policy explicitly before adding MTL, or keep schema-only tables in a separate FDW schema/manifest. |
waves/B9\codex-adversarial-r2.md:5915:Do not fully lock execution yet. PLAN v3 needs targeted mitigations for: per-table delta semantics, reference-DB write-path enforcement, MTL FDW silent-failure prevention, B9.F timing abort criteria, consumer-side adjudication/reclaimrx audits, and current FDW manifest/script hard-coded count drift. After those are added, B9.A can close and B9.B can open with far less hidden failure surface.
waves/B9\codex-adversarial-r2.md:5926:| 1 | Session size | M | â€œNext absorbs overflowâ€ is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
waves/B9\codex-adversarial-r2.md:5927:| 2 | Migration | M | Postgres transactional DDL reduces half-applied risk, but 113-table migration failure still creates a large debug blast radius. Reverse/apply gate happens after implementation, not before merge pressure. | PARTIAL | Require generated migration dry-run on disposable DB before commit; capture `alembic upgrade + downgrade + upgrade` evidence per migration before mini-GATE. |
waves/B9\codex-adversarial-r2.md:5928:| 3 | FDW manifest | M | Additive manifest edits across sessions can conflict, and current `setup_fdw.sh --verify` hard-codes `expected 66`, so B9.B verify will fail unless this is changed. | PARTIAL | Make manifest generated or sorted deterministically; replace hard-coded 66 with an expected-count argument or manifest-derived count. |
waves/B9\codex-adversarial-r2.md:5932:| 7 | B9.F perf gate | H | Timing gate says FDW verify must complete within 5 min, but only storage has abort/escalate language. A 20-min verify could be â€œdocumentedâ€ and still pass. | PARTIAL | Add hard timing abort: if verify or weekly delta exceeds threshold, B9.F fails and requires index/query redesign before B9.G opens. |
waves/B9\codex-adversarial-r2.md:5933:| 8 | B9.G MTL FDW | H | Empty MTL foreign tables create a silent false-negative surface. A downstream join to MTL returns no rows instead of erroring. | NO | Do not expose MTL via FDW by default, or expose guarded views that raise/flag when `fdb_load_mtl=False`; update FDW count accordingly if excluded. |
waves/B9\codex-adversarial-r2.md:5934:| 9 | Calendar slip | M | Charter admits 4-5 months, but plan still gates as one large B9. Overruns can freeze visible delivery for months. | PARTIAL | Add calendar checkpoint every 4 weeks with scope/split decision; allow B9.B/B9.C shipped milestone tags even under single B9 label. |
waves/B9\codex-adversarial-r2.md:5937:| 12 | Existing 3-table coverage | M | The registry expansion could reprocess RNP3/RPRDPTD0/RNPTYPD0, change modes, or duplicate existing TableSpecs. | PARTIAL | Add compatibility tests proving existing Phase 09 modes, row counts, price lookup behavior, and `fdb_price_type_desc` synthesis are unchanged. |
waves/B9\codex-adversarial-r2.md:5939:| 14 | Adjudication ripple | H | Plan does not audit consumer queries. Adding 217 tables may not change paths directly, but new FDW names and pricing tables can alter assumptions, imports, or fallback behavior. | NO | Add consumer audit in B9.H or earlier: adjudication pricing enrichment, TCP publish path, and FDW query smoke tests with B9 data present. |
waves/B9\codex-adversarial-r2.md:5947:| FDW name collision | H | `setup_fdw.sh` imports all source schemas into one `reference` schema. 217 new FDB names could collide with existing reference table names or future schemas; the script fatals on collision. | Preflight generated B9 table names against all reference schemas before B9.B implementation starts. |
waves/B9\codex-adversarial-r2.md:5948:| Manifest semantics drift | M | Current manifest comments say only tables with `>0 rows` are included. B9.G adds empty MTL tables, contradicting the manifest contract. | Update manifest policy explicitly before adding MTL, or keep schema-only tables in a separate FDW schema/manifest. |
waves/B9\codex-adversarial-r2.md:5958:Do not fully lock execution yet. PLAN v3 needs targeted mitigations for: per-table delta semantics, reference-DB write-path enforcement, MTL FDW silent-failure prevention, B9.F timing abort criteria, consumer-side adjudication/reclaimrx audits, and current FDW manifest/script hard-coded count drift. After those are added, B9.A can close and B9.B can open with far less hidden failure surface.
waves/B9\codex-adversarial-r2.md:5962:2026-05-11T19:41:29.239613Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md' -Pattern 'A4 idempotency|A5 MTL guard|A7 perf gate|A8 MTL FDW silent|A11 write path|A14 adjudication ripple|A15 reclaimrx pricing|N1 FDW name collision|N4 parse_table skip|A1 session overflow|A2 migration blast|A3 FDW manifest|A6 RNDC14 iteration|A9 calendar slip|A10 codex cadence|A12 Phase 09 compat|A13 flaky baseline|A16 memory consistency|N2 manifest semantics|N3 model-import cost|C8|C9|C10|C11|C12|C13|C14|HARD ABORT|DATABASE_URL_SYNC_REFERENCE|parse_warning_allowlist|status.md|test_flake_quarantine|local_review_checklists|weeks 4/8/12|B9.H Session 3|B9.F Session 4|DELTA_SEMANTICS|REVOKE INSERT|264/264|283/283|Effort math' | ForEach-Object { '{0}: {1}' -f "'$_.LineNumber, $_.Line }'` rejected: blocked by policy
waves/B9\codex-adversarial-r2.md:5964:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md' -Pattern 'A4 idempotency|A5 MTL guard|A7 perf gate|A8 MTL FDW silent|A11 write path|A14 adjudication ripple|A15 reclaimrx pricing|N1 FDW name collision|N4 parse_table skip|A1 session overflow|A2 migration blast|A3 FDW manifest|A6 RNDC14 iteration|A9 calendar slip|A10 codex cadence|A12 Phase 09 compat|A13 flaky baseline|A16 memory consistency|N2 manifest semantics|N3 model-import cost|C8|C9|C10|C11|C12|C13|C14|HARD ABORT|DATABASE_URL_SYNC_REFERENCE|parse_warning_allowlist|status.md|test_flake_quarantine|local_review_checklists|weeks 4/8/12|B9.H Session 3|B9.F Session 4|DELTA_SEMANTICS|REVOKE INSERT|264/264|283/283|Effort math' | ForEach-Object { '{0}: {1}' -f "'$_.LineNumber, $_.Line }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-adversarial-r2.md:5968:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md' -Pattern 'A4 idempotency|A5 MTL guard|A7 perf gate|A8 MTL FDW silent|A11 write path|A14 adjudication ripple|A15 reclaimrx pricing|N1 FDW name collision|N4 parse_table skip|A1 session overflow|A2 migration blast|A3 FDW manifest|A6 RNDC14 iteration|A9 calendar slip|A10 codex cadence|A12 Phase 09 compat|A13 flaky baseline|A16 memory consistency|N2 manifest semantics|N3 model-import cost|C8|C9|C10|C11|C12|C13|C14|HARD ABORT|DATABASE_URL_SYNC_REFERENCE|parse_warning_allowlist|status.md|test_flake_quarantine|local_review_checklists|weeks 4/8/12|B9.H Session 3|B9.F Session 4|DELTA_SEMANTICS|REVOKE INSERT|264/264|283/283|Effort math' | ForEach-Object { '{0}: {1}' -f "'$_.LineNumber, $_.Line }'` rejected: blocked by policy
waves/B9\codex-adversarial-r2.md:5972:2026-05-11T19:41:29.288937Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-adversarial-r1.md' -Pattern 'ADV.*VERDICT|HIGH-SEVERITY|A4|A5|A7|A8|A11|A14|A15|FDW name collision|Field-count|Strongest single objection|Final verdict' | ForEach-Object { '{0}: {1}' -f "'$_.LineNumber, $_.Line }'` rejected: blocked by policy
waves/B9\codex-adversarial-r2.md:5974:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-adversarial-r1.md' -Pattern 'ADV.*VERDICT|HIGH-SEVERITY|A4|A5|A7|A8|A11|A14|A15|FDW name collision|Field-count|Strongest single objection|Final verdict' | ForEach-Object { '{0}: {1}' -f "'$_.LineNumber, $_.Line }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-adversarial-r2.md:5976:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -LiteralPath 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-adversarial-r1.md' -Pattern 'ADV.*VERDICT|HIGH-SEVERITY|A4|A5|A7|A8|A11|A14|A15|FDW name collision|Field-count|Strongest single objection|Final verdict' | ForEach-Object { '{0}: {1}' -f "'$_.LineNumber, $_.Line }'` rejected: blocked by policy
waves/B9\codex-adversarial-r2.md:5979:2026-05-11T19:41:43.675058Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md' -Pattern 'A4 idempotency','A5 MTL guard','A7 perf gate','A8 MTL FDW silent','A11 write path','A14 adjudication ripple','A15 reclaimrx pricing','N1 FDW name collision','N4 parse_table skip','A1 session overflow','A2 migration blast','A3 FDW manifest','A6 RNDC14 iteration','A9 calendar slip','A10 codex cadence','A12 Phase 09 compat','A13 flaky baseline','A16 memory consistency','N2 manifest semantics','N3 model-import cost','C8','C9','C10','C11','C12','C13','C14','HARD ABORT','DATABASE_URL_SYNC_REFERENCE','parse_warning_allowlist','status.md','test_flake_quarantine','local_review_checklists','weeks 4/8/12','B9.H Session 3','B9.F Session 4','DELTA_SEMANTICS','REVOKE INSERT','264/264','283/283','Effort math'"` rejected: blocked by policy
waves/B9\codex-adversarial-r2.md:5981:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md' -Pattern 'A4 idempotency','A5 MTL guard','A7 perf gate','A8 MTL FDW silent','A11 write path','A14 adjudication ripple','A15 reclaimrx pricing','N1 FDW name collision','N4 parse_table skip','A1 session overflow','A2 migration blast','A3 FDW manifest','A6 RNDC14 iteration','A9 calendar slip','A10 codex cadence','A12 Phase 09 compat','A13 flaky baseline','A16 memory consistency','N2 manifest semantics','N3 model-import cost','C8','C9','C10','C11','C12','C13','C14','HARD ABORT','DATABASE_URL_SYNC_REFERENCE','parse_warning_allowlist','status.md','test_flake_quarantine','local_review_checklists','weeks 4/8/12','B9.H Session 3','B9.F Session 4','DELTA_SEMANTICS','REVOKE INSERT','264/264','283/283','Effort math'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-adversarial-r2.md:5983:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md' -Pattern 'A4 idempotency','A5 MTL guard','A7 perf gate','A8 MTL FDW silent','A11 write path','A14 adjudication ripple','A15 reclaimrx pricing','N1 FDW name collision','N4 parse_table skip','A1 session overflow','A2 migration blast','A3 FDW manifest','A6 RNDC14 iteration','A9 calendar slip','A10 codex cadence','A12 Phase 09 compat','A13 flaky baseline','A16 memory consistency','N2 manifest semantics','N3 model-import cost','C8','C9','C10','C11','C12','C13','C14','HARD ABORT','DATABASE_URL_SYNC_REFERENCE','parse_warning_allowlist','status.md','test_flake_quarantine','local_review_checklists','weeks 4/8/12','B9.H Session 3','B9.F Session 4','DELTA_SEMANTICS','REVOKE INSERT','264/264','283/283','Effort math'"` rejected: blocked by policy
waves/B9\codex-adversarial-r2.md:5988:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-adversarial-r1.md' -Pattern 'ADV.*VERDICT','HIGH-SEVERITY','FDW name collision','Field-count','Strongest single objection','Final verdict'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-adversarial-r2.md:5992:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-adversarial-r1.md' -Pattern 'ADV.*VERDICT','HIGH-SEVERITY','FDW name collision','Field-count','Strongest single objection','Final verdict'"` rejected: blocked by policy
waves/B9\codex-adversarial-r2.md:5993:2026-05-11T19:41:43.728614Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-adversarial-r1.md' -Pattern 'ADV.*VERDICT','HIGH-SEVERITY','FDW name collision','Field-count','Strongest single objection','Final verdict'"` rejected: blocked by policy
waves/B9\codex-adversarial-r2.md:5995:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"A4 idempotency|A5 MTL guard|A7 perf gate|A8 MTL FDW silent|A11 write path|A14 adjudication ripple|A15 reclaimrx pricing|N1 FDW name collision|N4 parse_table skip|A1 session overflow|A2 migration blast|A3 FDW manifest|A6 RNDC14 iteration|A9 calendar slip|A10 codex cadence|A12 Phase 09 compat|A13 flaky baseline|A16 memory consistency|N2 manifest semantics|N3 model-import cost|C8|C9|C10|C11|C12|C13|C14|HARD ABORT|DATABASE_URL_SYNC_REFERENCE|parse_warning_allowlist|status\\.md|test_flake_quarantine|local_review_checklists|weeks 4/8/12|B9\\.H Session 3|B9\\.F Session 4|DELTA_SEMANTICS|REVOKE INSERT|264/264|283/283|Effort math\" \"C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-adversarial-r2.md:5999:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"ADV.*VERDICT|HIGH-SEVERITY|FDW name collision|Field-count|Strongest single objection|Final verdict\" \"C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\codex-adversarial-r1.md\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-adversarial-r2.md:6001:3:**Status:** SPEC v3.2 LOCKED — erratum chain: (v3.1) arithmetic drift correction surfaced by codex PLAN R2 → B9.B FDW `116/116`→`179/179`, B9.D "17 complex"→"16 complex"; (v3.2) MTL FDW-exposure policy surfaced by codex ADVERSARIAL R1 → MTL excluded from default FDW manifest to prevent silent false-negative joins, conditional 19 entries added only when `fdb_load_mtl=True` (future MTL activation wave). B9.H final FDW count: **264/264 default, 283/283 conditional**. No scope change. See `codex-plan-consult-r2.md` and `codex-adversarial-r1.md`. Ready for PLAN v3 → ADVERSARIAL R2.
waves/B9\codex-adversarial-r2.md:6003:55:| B9.H | Manifest extension (66 → 264 FDW entries default; +19 conditional MTL) + consumer audits + final closeout artifacts | 5 | **Final B9 GATE-CLOSE** — full cross-tier consult |
waves/B9\codex-adversarial-r2.md:6004:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
waves/B9\codex-adversarial-r2.md:6005:66:| SC-6 | `setup_fdw.sh --verify` 264/264 PASS in both env DBs by default (MTL excluded from FDW per ADVERSARIAL R1 mitigation); conditional 283/283 when `fdb_load_mtl=True` |
waves/B9\codex-adversarial-r2.md:6006:102:**~39 sessions × 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong — corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-adversarial-r2.md:6009:26:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-adversarial-r2.md:6012:40:| A7 perf gate | H | "Documented" without abort | B9.F hard timing aborts: FDW verify > 5 min → FAIL; per-table weekly delta > 30s → FAIL; total weekly delta > 10 min → FAIL. Charter SC-4 wording strengthened in plan §B9.F. See T15. |
waves/B9\codex-adversarial-r2.md:6013:41:| A8 MTL FDW silent | H | Empty FDW foreign tables = silent false-negative joins | MTL excluded from default FDW manifest (charter v3.2 erratum: 264 default / 283 conditional). MTL data activation work — including the +19 FDW entries — moves to a future wave when licensing flips. See T16. |
waves/B9\codex-adversarial-r2.md:6015:43:| A14 adjudication ripple | H | Consumer audit missing | B9.H Session 3 adds adjudication audit: pricing-enrichment path with B9 data present; TCP listener publish smoke; FDW query smoke with new tables. See T18. |
waves/B9\codex-adversarial-r2.md:6017:45:| N1 FDW name collision | H | `setup_fdw.sh` fatals on duplicate; no preflight | B9.A C10 preflight: generate all 217 B9 table names; scan `infinityrx_reference` schemas (drug_database / drug_db / reference / shared) for collisions; abort if any. See T20. |
waves/B9\codex-adversarial-r2.md:6019:47:| A1 session overflow | M | "Next absorbs overflow" not a control | Per-table escape-hatch: any Tier A table that consumes > 1 hour solo gets reclassified to Tier B/C; removed from `0009_fdb_tier_a.py`; FDW ladder updated; mini-re-plan triggered if session burn > +20%. See T22. |
waves/B9\codex-adversarial-r2.md:6020:48:| A2 migration blast radius | M | 113-table migration failure = wide blast | Each migration requires `alembic upgrade + downgrade + upgrade` evidence captured on a disposable DB before commit; mini-GATE-CLOSE checks evidence file exists. See T23. |
waves/B9\codex-adversarial-r2.md:6021:49:| A3 FDW manifest | M | Hard-coded "expected 66"; concurrent-edit conflicts | B9.A C11 replaces hard-coded 66 in `setup_fdw.sh --verify` with manifest-derived count; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is the source of truth. See T24. |
waves/B9\codex-adversarial-r2.md:6022:50:| A6 RNDC14 iteration | M | 2 sessions fragile if 5+ type issues | B9.E iteration rule: sessions may expand from 2 → up to 4 without borrowing from B9.F budget; mini-GATE-CLOSE will not close on partial column review. See T25. |
waves/B9\codex-adversarial-r2.md:6023:51:| A9 calendar slip | M | 4-5 months freeze of visible delivery | 4-week calendar checkpoint: at week-4 / week-8 / week-12 owner reviews B9.X.* progress + decides whether to ship intermediate milestone tags (B9.B-shipped, B9.C-shipped) under the single B9 label. See T26. |
waves/B9\codex-adversarial-r2.md:6025:53:| A12 Phase 09 compat | M | Existing 3-table coverage might break | B9.A C12 captures Phase 09 baseline: row counts for `fdb_ndc_price_history` + `fdb_price_type_desc`, query latency on representative NDC + price_type lookups, default-mode behavior. Mini-GATE-CLOSE re-runs and asserts unchanged. See T28. |
waves/B9\codex-adversarial-r2.md:6028:56:| N2 manifest semantics | M | `>0 rows` policy contradicts B9.G empty MTL | Resolved by A8 mitigation (MTL not in default FDW). Document the policy explicitly in `infrastructure/scripts/lib/expected_reference_tables.txt` header. See T31. |
waves/B9\codex-adversarial-r2.md:6030:67:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-adversarial-r2.md:6031:93:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-adversarial-r2.md:6032:100:| C0 | Baseline + invariants captured (df, pg_authid, FDW 66/66, pytest node-ID snapshots × 2 runs for flake detection) | `waves/B9/baseline.md`, `waves/B9/test_flake_quarantine.md` |
waves/B9\codex-adversarial-r2.md:6037:110:| **C10** | **FDW name collision preflight — generate 217 B9 table names; scan all `infinityrx_reference` schemas; abort on any collision** | `infrastructure/scripts/preflight_b9_name_collision.py`, evidence |
waves/B9\codex-adversarial-r2.md:6038:111:| **C11** | **`setup_fdw.sh --verify` manifest-derived count (replace hard-coded `expected 66`) + deterministic sorted manifest ordering** | `infrastructure/scripts/setup_fdw.sh`, `infrastructure/scripts/lib/expected_reference_tables.txt` |
waves/B9\codex-adversarial-r2.md:6039:112:| **C12** | **Phase 09 compatibility baseline: capture RNP3 + RPRDPTD0 + RNPTYPD0 row counts + query latency + default-mode behavior; mini-GATE-CLOSE re-asserts unchanged at every phase** | `waves/B9/phase09_compat_baseline.md`, compat test |
waves/B9\codex-adversarial-r2.md:6053:283:- FDW + Postgres verify after indexes built: **HARD ABORT if > 5 minutes**
waves/B9\codex-adversarial-r2.md:6056:314:**FDW count derivation (final per charter v3.2):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + **0 (B9.G MTL — schema-only, FDW-excluded)** = **264**. Charter v3.2 SC-6 = 264/264 default; conditional 283/283 if MTL data is later enabled.
waves/B9\codex-adversarial-r2.md:6057:316:**Success criteria:** SC-1 (cum 217/217 — MTL schema present even though FDW-excluded), SC-5 (MTL zero-row test green + DB guard verified), SC-6 (264/264 default), SC-9.
waves/B9\codex-adversarial-r2.md:6058:336:- Session 2: Final `setup_fdw.sh --verify` **264/264** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables (217 + 2 existing = 219 DB tables; 264 FDW entries); published in `waves/B9/evidence.md`
waves/B9\codex-adversarial-r2.md:6061:377:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9\codex-adversarial-r2.md:6062:380:| SC-6 | `setup_fdw.sh --verify` output **264/264** in dev + mock default (charter v3.2 matched); conditional 283/283 when `fdb_load_mtl=True` | B9.H Session 2 |
waves/B9\codex-adversarial-r2.md:6064:405:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) — ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
waves/B9\codex-adversarial-r2.md:6066:407:| T15 | B9.F perf gate documented without aborting — slow query "passes" — ADVERSARIAL A7 | LOW | **HIGH** | HARD ABORT criteria: FDW verify > 5 min, per-table weekly delta > 30s, total weekly delta > 10 min, storage delta > +1.4 GB. Any breach → B9.F fails, design rework required before B9.G opens. |
waves/B9\codex-adversarial-r2.md:6068:410:| T18 | Adjudication consumers untested against B9 data; new FDB tables may change pricing-enrichment paths — ADVERSARIAL A14 | MED | **HIGH** | B9.H Session 3 runs three consumer audits: (a) `enrich_pricing()` against representative NDCs, (b) TCP listener publish smoke with `claim.adjudicated` event verification, (c) FDW query smoke from adjudication + reclaimrx + network-management top-3 queries |
waves/B9\codex-adversarial-r2.md:6070:412:| T20 | FDW name collision — `setup_fdw.sh` fatals on duplicate names across reference schemas — ADVERSARIAL N1 | LOW | **HIGH** | B9.A C10: preflight scans 217 generated B9 table names against `drug_database / drug_db / reference / shared` schemas; aborts if any collision. Test in CI per-phase. |
waves/B9\codex-adversarial-r2.md:6072:416:| T24 | `setup_fdw.sh --verify` hard-codes "expected 66"; B9.B verify fails without script change — ADVERSARIAL A3 | LOW | MED | B9.A C11 replaces hard-coded count with manifest-derived; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is source of truth |
waves/B9\codex-adversarial-r2.md:6073:417:| T25 | RNDC14 2-session budget insufficient if column review surfaces multiple issues — ADVERSARIAL A6 | MED | MED | B9.E iteration allowance: 2 → up to 4 sessions without borrowing from B9.F; mini-GATE-CLOSE will not close on partial review |
waves/B9\codex-adversarial-r2.md:6074:418:| T26 | 4-5 month wave freezes visible delivery; overruns invisible — ADVERSARIAL A9 | MED | MED | 4-week calendar checkpoint at weeks 4/8/12; intermediate milestone tags (B9.B-shipped, B9.C-shipped) under single B9 label; owner reviews scope/split decision at each checkpoint |
waves/B9\codex-adversarial-r2.md:6076:420:| T28 | Existing Phase 09 coverage breaks due to registry expansion or migration interaction — ADVERSARIAL A12 | LOW | MED | B9.A C12 captures Phase 09 baseline: RNP3/RPRDPTD0/RNPTYPD0 row counts + query latency + default-mode behavior; per-phase mini-GATE-CLOSE re-asserts unchanged |
waves/B9\codex-adversarial-r2.md:6077:421:| T29 | Flaky test noise drowns real signal in 134-failure baseline — ADVERSARIAL A13 | MED | MED | B9.A C0 captures node-ID snapshots × 2 runs (NOT raw counts); known flakes quarantined in `waves/B9/test_flake_quarantine.md`; mini-GATE-CLOSE asserts node-ID delta, not count delta |
waves/B9\codex-adversarial-r2.md:6080:440:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
waves/B9\codex-adversarial-r2.md:6081:441:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9\codex-adversarial-r2.md:6093:5166:| FDW name collision | H | `setup_fdw.sh` imports all source schemas into one `reference` schema. 217 new FDB names could collide with existing reference table names or future schemas; the script fatals on collision. | Preflight generated B9 table names against all reference schemas before B9.B implementation starts. |
waves/B9\codex-adversarial-r2.md:6099:5209:| FDW name collision | H | `setup_fdw.sh` imports all source schemas into one `reference` schema. 217 new FDB names could collide with existing reference table names or future schemas; the script fatals on collision. | Preflight generated B9 table names against all reference schemas before B9.B implementation starts. |
waves/B9\codex-adversarial-r2.md:6105:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"T16|MTL EXCLUDED|RNP2 \\+ RPRDPP0|reclaimrx-protocol|Consumer audit|Session 3|Session 4|default FDW manifest|negative test|app-role INSERT|module-level|abort \\+ redesign|manifest file header|Per-table escape-hatch|alembic upgrade\" \"C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-adversarial-r2.md:6107:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"B9\\.G|MTL|FDW count derivation|DB-level guard|fdb_mtl_data|REVOKE|negative\" \"C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-adversarial-r2.md:6111:41:| A8 MTL FDW silent | H | Empty FDW foreign tables = silent false-negative joins | MTL excluded from default FDW manifest (charter v3.2 erratum: 264 default / 283 conditional). MTL data activation work — including the +19 FDW entries — moves to a future wave when licensing flips. See T16. |
waves/B9\codex-adversarial-r2.md:6112:43:| A14 adjudication ripple | H | Consumer audit missing | B9.H Session 3 adds adjudication audit: pricing-enrichment path with B9 data present; TCP listener publish smoke; FDW query smoke with new tables. See T18. |
waves/B9\codex-adversarial-r2.md:6114:47:| A1 session overflow | M | "Next absorbs overflow" not a control | Per-table escape-hatch: any Tier A table that consumes > 1 hour solo gets reclassified to Tier B/C; removed from `0009_fdb_tier_a.py`; FDW ladder updated; mini-re-plan triggered if session burn > +20%. See T22. |
waves/B9\codex-adversarial-r2.md:6115:48:| A2 migration blast radius | M | 113-table migration failure = wide blast | Each migration requires `alembic upgrade + downgrade + upgrade` evidence captured on a disposable DB before commit; mini-GATE-CLOSE checks evidence file exists. See T23. |
waves/B9\codex-adversarial-r2.md:6122:265:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline; **reclaimrx pricing-protocol tests** (ADVERSARIAL A15): exercise `awp_basis` distribution with populated RNP2 + RPRDPP0 + RNP3; assert no new basis values appear; assert literal-AWP guards still reject correctly
waves/B9\codex-adversarial-r2.md:6125:300:- Session 3: Integration test `test_fdb_mtl_zero_rows_under_default` (from B9.A C4) exercises the live MTL tables — asserts zero rows after default load. **Negative test added:** app-role INSERT into MTL table MUST fail with permission error (verifies DB-level guard works). Documentation: `docs/runbooks/fdb-mtl-opt-in.md` explains the FUTURE activation path (FDW manifest expansion to 283 + grant flip + data load) when licensing flips.
waves/B9\codex-adversarial-r2.md:6128:337:- **Session 3 (NEW — ADVERSARIAL A14):** Consumer audit. Runs three smoke suites against the populated reference DB: (a) **adjudication pricing-enrichment** path — `enrich_pricing()` returns correct WAC/AWP/NADAC + `awp_basis` for representative NDCs across all 5 pricing tables (RNP2/RNP3/RPRDPP0 + NADAC); (b) **TCP listener publish** — claim adjudication runs end-to-end, `claim.adjudicated` event publishes with FDB enrichment fields present; (c) **FDW query smoke** — adjudication, reclaimrx, network-management each run their top-3 FDB-reading queries; all succeed. Failures here trigger B9.H NO-GO and consumer-side fixes.
waves/B9\codex-adversarial-r2.md:6135:408:| T16 | MTL FDW foreign tables empty → silent false-negative downstream joins — ADVERSARIAL A8 | MED | **HIGH** | MTL EXCLUDED from default FDW manifest (charter v3.2 erratum). Conditional inclusion (264 → 283) only when MTL data is activated. Downstream join to MTL fails LOUDLY (relation does not exist) instead of silently empty. |
waves/B9\codex-adversarial-r2.md:6136:410:| T18 | Adjudication consumers untested against B9 data; new FDB tables may change pricing-enrichment paths — ADVERSARIAL A14 | MED | **HIGH** | B9.H Session 3 runs three consumer audits: (a) `enrich_pricing()` against representative NDCs, (b) TCP listener publish smoke with `claim.adjudicated` event verification, (c) FDW query smoke from adjudication + reclaimrx + network-management top-3 queries |
waves/B9\codex-adversarial-r2.md:6138:414:| T22 | Tier A session-size overflow if a misclassified table consumes a full session — ADVERSARIAL A1 | MED | MED | Per-table escape-hatch: > 1h solo → reclassify to Tier B/C, remove from `0009`, update FDW ladder; > 20% session burn → trigger mini-replan; charter W1 budget can flex with W2 buffer if needed |
waves/B9\codex-adversarial-r2.md:6139:415:| T23 | 113-table migration failure has large debug blast radius — ADVERSARIAL A2 | LOW | MED | Each migration captures `alembic upgrade + downgrade + upgrade` on a disposable DB before commit; evidence file required at mini-GATE-CLOSE; failed migration auto-flagged for codex review |
waves/B9\codex-adversarial-r2.md:6140:423:| T31 | `expected_reference_tables.txt` `>0 rows` policy contradicts schema-only MTL — ADVERSARIAL N2 | LOW | LOW | Resolved by T16 (MTL not in default FDW). Document policy explicitly in manifest file header. |
waves/B9\codex-adversarial-r2.md:6144:3:**Status:** PLAN v3 DRAFT — folds codex ADVERSARIAL R1 mitigations (9 HIGH + 11 MEDIUM). Charter bumped to v3.2 (MTL FDW exposure policy changed). Pending ADVERSARIAL R2 verification before B9.A closes and B9.B opens.
waves/B9\codex-adversarial-r2.md:6145:5:**Iteration history:** PLAN v1 (initial draft) → PLAN R1 codex consult GO-WITH-FIXES (8 fixes) → PLAN v2 (fixes absorbed) → PLAN R2 codex consult GO-WITH-FIXES (charter erratum needed) → charter v3.1 erratum applied → PLAN GATE FINAL VERDICT GO → ADVERSARIAL R1 codex consult HIGH-SEVERITY OBJECTIONS PRESENT (9 HIGH + 11 MED + 4 novel) → PLAN v3 (this version, all mitigations folded in) → charter v3.2 erratum applied (MTL FDW exposure) → ADVERSARIAL R2 (pending).
waves/B9\codex-adversarial-r2.md:6148:41:| A8 MTL FDW silent | H | Empty FDW foreign tables = silent false-negative joins | MTL excluded from default FDW manifest (charter v3.2 erratum: 264 default / 283 conditional). MTL data activation work — including the +19 FDW entries — moves to a future wave when licensing flips. See T16. |
waves/B9\codex-adversarial-r2.md:6149:56:| N2 manifest semantics | M | `>0 rows` policy contradicts B9.G empty MTL | Resolved by A8 mitigation (MTL not in default FDW). Document the policy explicitly in `infrastructure/scripts/lib/expected_reference_tables.txt` header. See T31. |
waves/B9\codex-adversarial-r2.md:6151:93:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-adversarial-r2.md:6157:298:- Session 1: 19 SQLAlchemy models in `tier_d/`; migration `0014_fdb_mtl_schema.py` (un-gated, lands schema); 19 contract tests asserting tables exist + are queryable + are EMPTY. **MTL tables NOT added to FDW manifest by default** (ADVERSARIAL A8 mitigation — prevents silent false-negative joins from downstream queries).
waves/B9\codex-adversarial-r2.md:6159:300:- Session 3: Integration test `test_fdb_mtl_zero_rows_under_default` (from B9.A C4) exercises the live MTL tables — asserts zero rows after default load. **Negative test added:** app-role INSERT into MTL table MUST fail with permission error (verifies DB-level guard works). Documentation: `docs/runbooks/fdb-mtl-opt-in.md` explains the FUTURE activation path (FDW manifest expansion to 283 + grant flip + data load) when licensing flips.
waves/B9\codex-adversarial-r2.md:6164:311:- Runbook `docs/runbooks/fdb-mtl-opt-in.md` (covers MTL activation: FDW expansion 264→283, grants, loader flag flip)
waves/B9\codex-adversarial-r2.md:6165:312:- FDW foreign-table count: 264 → **264** (unchanged — MTL excluded by default per ADVERSARIAL A8 + charter v3.2)
waves/B9\codex-adversarial-r2.md:6166:314:**FDW count derivation (final per charter v3.2):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + **0 (B9.G MTL — schema-only, FDW-excluded)** = **264**. Charter v3.2 SC-6 = 264/264 default; conditional 283/283 if MTL data is later enabled.
waves/B9\codex-adversarial-r2.md:6167:316:**Success criteria:** SC-1 (cum 217/217 — MTL schema present even though FDW-excluded), SC-5 (MTL zero-row test green + DB guard verified), SC-6 (264/264 default), SC-9.
waves/B9\codex-adversarial-r2.md:6168:318:**B9.G mini-GATE-CLOSE criteria:**
waves/B9\codex-adversarial-r2.md:6170:323:- FDW manifest verified: MTL tables NOT present (264 entries total)
waves/B9\codex-adversarial-r2.md:6172:325:- Codex mini-GATE-CLOSE consult: GO; codex verifies (a) DB-level guard prevents app-role writes, (b) flipping `fdb_load_mtl=False` after data load DOES NOT delete data, (c) MTL exclusion from FDW is correct for default state
waves/B9\codex-adversarial-r2.md:6176:361:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9\codex-adversarial-r2.md:6180:407:| T15 | B9.F perf gate documented without aborting — slow query "passes" — ADVERSARIAL A7 | LOW | **HIGH** | HARD ABORT criteria: FDW verify > 5 min, per-table weekly delta > 30s, total weekly delta > 10 min, storage delta > +1.4 GB. Any breach → B9.F fails, design rework required before B9.G opens. |
waves/B9\codex-adversarial-r2.md:6181:408:| T16 | MTL FDW foreign tables empty → silent false-negative downstream joins — ADVERSARIAL A8 | MED | **HIGH** | MTL EXCLUDED from default FDW manifest (charter v3.2 erratum). Conditional inclusion (264 → 283) only when MTL data is activated. Downstream join to MTL fails LOUDLY (relation does not exist) instead of silently empty. |
waves/B9\codex-adversarial-r2.md:6182:423:| T31 | `expected_reference_tables.txt` `>0 rows` policy contradicts schema-only MTL — ADVERSARIAL N2 | LOW | LOW | Resolved by T16 (MTL not in default FDW). Document policy explicitly in manifest file header. |
waves/B9\codex-adversarial-r2.md:6183:443:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9\codex-adversarial-r2.md:6185:468:3. **Loader-orchestration modes: existing vs new** → **RESOLVED:** existing `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, `fdb_rebase`. B9.A C4 does NOT need to add `fdb_weekly`. It may need to add tier-specific modes (`fdb_tier_a`, `fdb_tier_b`, `fdb_mtl_data`) if per-tier loaders are desired; PLAN v2 leaves that as a B9.A C1 design decision (additive to existing modes).
waves/B9\codex-adversarial-r2.md:6188:40:| A7 perf gate | H | "Documented" without abort | B9.F hard timing aborts: FDW verify > 5 min → FAIL; per-table weekly delta > 30s → FAIL; total weekly delta > 10 min → FAIL. Charter SC-4 wording strengthened in plan §B9.F. See T15. |
waves/B9\codex-adversarial-r2.md:6190:50:| A6 RNDC14 iteration | M | 2 sessions fragile if 5+ type issues | B9.E iteration rule: sessions may expand from 2 → up to 4 without borrowing from B9.F budget; mini-GATE-CLOSE will not close on partial column review. See T25. |
waves/B9\codex-adversarial-r2.md:6193:93:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-adversarial-r2.md:6199:265:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline; **reclaimrx pricing-protocol tests** (ADVERSARIAL A15): exercise `awp_basis` distribution with populated RNP2 + RPRDPP0 + RNP3; assert no new basis values appear; assert literal-AWP guards still reject correctly
waves/B9\codex-adversarial-r2.md:6202:278:**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4 + ADVERSARIAL A7 hard aborts:**
waves/B9\codex-adversarial-r2.md:6204:283:- FDW + Postgres verify after indexes built: **HARD ABORT if > 5 minutes**
waves/B9\codex-adversarial-r2.md:6207:286:- Codex mini-GATE-CLOSE consult: GO; codex reviews EXPLAIN ANALYZE for index gaps + reviews reclaimrx test deltas
waves/B9\codex-adversarial-r2.md:6209:314:**FDW count derivation (final per charter v3.2):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + **0 (B9.G MTL — schema-only, FDW-excluded)** = **264**. Charter v3.2 SC-6 = 264/264 default; conditional 283/283 if MTL data is later enabled.
waves/B9\codex-adversarial-r2.md:6210:331:**Scope:** Reconcile `expected_reference_tables.txt` to the final count (264 default), run final FDW verify, audit downstream consumers (adjudication + reclaimrx + TCP listener), produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
waves/B9\codex-adversarial-r2.md:6211:337:- **Session 3 (NEW — ADVERSARIAL A14):** Consumer audit. Runs three smoke suites against the populated reference DB: (a) **adjudication pricing-enrichment** path — `enrich_pricing()` returns correct WAC/AWP/NADAC + `awp_basis` for representative NDCs across all 5 pricing tables (RNP2/RNP3/RPRDPP0 + NADAC); (b) **TCP listener publish** — claim adjudication runs end-to-end, `claim.adjudicated` event publishes with FDB enrichment fields present; (c) **FDW query smoke** — adjudication, reclaimrx, network-management each run their top-3 FDB-reading queries; all succeed. Failures here trigger B9.H NO-GO and consumer-side fixes.
waves/B9\codex-adversarial-r2.md:6217:394:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9\codex-adversarial-r2.md:6219:407:| T15 | B9.F perf gate documented without aborting — slow query "passes" — ADVERSARIAL A7 | LOW | **HIGH** | HARD ABORT criteria: FDW verify > 5 min, per-table weekly delta > 30s, total weekly delta > 10 min, storage delta > +1.4 GB. Any breach → B9.F fails, design rework required before B9.G opens. |
waves/B9\codex-adversarial-r2.md:6220:410:| T18 | Adjudication consumers untested against B9 data; new FDB tables may change pricing-enrichment paths — ADVERSARIAL A14 | MED | **HIGH** | B9.H Session 3 runs three consumer audits: (a) `enrich_pricing()` against representative NDCs, (b) TCP listener publish smoke with `claim.adjudicated` event verification, (c) FDW query smoke from adjudication + reclaimrx + network-management top-3 queries |
waves/B9\codex-adversarial-r2.md:6222:417:| T25 | RNDC14 2-session budget insufficient if column review surfaces multiple issues — ADVERSARIAL A6 | MED | MED | B9.E iteration allowance: 2 → up to 4 sessions without borrowing from B9.F; mini-GATE-CLOSE will not close on partial review |
waves/B9\codex-adversarial-r2.md:6223:442:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9\codex-adversarial-r2.md:6237:| A8 MTL FDW silent | H | PARTIAL | 41, 93, 298, 312, 314, 323, 408 | NO | Main B9.G text excludes MTL from default FDW, but B9.A infrastructure line 93 still says B9.G adds +19 MTL FDW entries and final verify is 283/283. That stale instruction can reintroduce the exact silent-empty FDW failure. |
waves/B9\codex-adversarial-r2.md:6239:| A14 adjudication ripple | H | YES | 43, 331, 337, 410 | YES | Consumer audit covers `enrich_pricing`, TCP publish, and FDW query smoke. |
waves/B9\codex-adversarial-r2.md:6241:| N1 FDW collision | H | YES | 45, 110, 412 | YES | Preflight scans generated names across all reference schemas and aborts. |
waves/B9\codex-adversarial-r2.md:6245:| A3 FDW manifest | M | YES | 49, 111, 416 | YES | Manifest-derived count and deterministic sorting. |
waves/B9\codex-adversarial-r2.md:6267:| Stale FDW ladder in B9.A | H | PLAN v3 still contains a B9.A infrastructure bullet saying B9.G adds +19 MTL FDW entries and B9.H final verify is 283/283. This conflicts with charter v3.2 and later PLAN v3 sections that say default is 264 and MTL is FDW-excluded. Because this is in cross-cutting infrastructure, it is executable guidance, not harmless prose. |
waves/B9\codex-adversarial-r2.md:6271:PLAN v3 absorbed almost all R1 findings, but A8 is not fully closed because `plan.md:93` still instructs the old MTL FDW behavior. Required PLAN v4 fix is narrow: delete or rewrite that B9.A FDW ladder bullet so it says default ladder stops at 264 after B9.F/B9.G, MTL contributes 0 default FDW entries, and 283 is conditional only under future MTL activation. After that stale line is corrected, B9.A can close and B9.B can open.
waves/B9\codex-adversarial-r2.md:6285:| A8 MTL FDW silent | H | PARTIAL | 41, 93, 298, 312, 314, 323, 408 | NO | Main B9.G text excludes MTL from default FDW, but B9.A infrastructure line 93 still says B9.G adds +19 MTL FDW entries and final verify is 283/283. That stale instruction can reintroduce the exact silent-empty FDW failure. |
waves/B9\codex-adversarial-r2.md:6287:| A14 adjudication ripple | H | YES | 43, 331, 337, 410 | YES | Consumer audit covers `enrich_pricing`, TCP publish, and FDW query smoke. |
waves/B9\codex-adversarial-r2.md:6289:| N1 FDW collision | H | YES | 45, 110, 412 | YES | Preflight scans generated names across all reference schemas and aborts. |
waves/B9\codex-adversarial-r2.md:6293:| A3 FDW manifest | M | YES | 49, 111, 416 | YES | Manifest-derived count and deterministic sorting. |
waves/B9\codex-adversarial-r2.md:6315:| Stale FDW ladder in B9.A | H | PLAN v3 still contains a B9.A infrastructure bullet saying B9.G adds +19 MTL FDW entries and B9.H final verify is 283/283. This conflicts with charter v3.2 and later PLAN v3 sections that say default is 264 and MTL is FDW-excluded. Because this is in cross-cutting infrastructure, it is executable guidance, not harmless prose. |
waves/B9\codex-adversarial-r2.md:6319:PLAN v3 absorbed almost all R1 findings, but A8 is not fully closed because `plan.md:93` still instructs the old MTL FDW behavior. Required PLAN v4 fix is narrow: delete or rewrite that B9.A FDW ladder bullet so it says default ladder stops at 264 after B9.F/B9.G, MTL contributes 0 default FDW entries, and 283 is conditional only under future MTL activation. After that stale line is corrected, B9.A can close and B9.B can open.
waves/B9\codex-adversarial-r2.md:6320:- **Charter Â§Workstreams view (39 sessions):** counts only productive ingest work â€” W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-adversarial-r2.md:6340:The requested line 93 fix is correct, and plan.md:1-5 correctly records v3.1 plus the ADVERSARIAL R2 narrow fix. However, stale FDW ladder language still remains in plan.md near the “Errata resolved by codex PLAN R1” section: it says “RESOLVED: 283” and gives `66 → 179 → 245 → 261 → 262 → 264 → 283` without marking 283 as conditional. That now conflicts with charter v3.2 and the rest of plan v3.1, where the default ladder stops at 264 and 283 is conditional only for future MTL activation.
waves/B9\codex-adversarial-r2.md:6349:The requested line 93 fix is correct, and plan.md:1-5 correctly records v3.1 plus the ADVERSARIAL R2 narrow fix. However, stale FDW ladder language still remains in plan.md near the “Errata resolved by codex PLAN R1” section: it says “RESOLVED: 283” and gives `66 → 179 → 245 → 261 → 262 → 264 → 283` without marking 283 as conditional. That now conflicts with charter v3.2 and the rest of plan v3.1, where the default ladder stops at 264 and 283 is conditional only for future MTL activation.
waves/B9\codex-adversarial-r2.md:6359:- plan.md:~93 — MTL excluded from default FDW; 0 contribution; 283 conditional
waves/B9\codex-adversarial-r2.md:6360:- All FDW count references in plan + charter agree: 264 default / 283 conditional
waves/B9\codex-adversarial-r2.md:6364:B9.A closes. B9.B opens (Tier A — 113 simple lookups via generic table-driven ingester).
waves/B9\codex-adversarial-r2.md:6374:- plan.md:~93 — MTL excluded from default FDW; 0 contribution; 283 conditional
waves/B9\codex-adversarial-r2.md:6375:- All FDW count references in plan + charter agree: 264 default / 283 conditional
waves/B9\codex-adversarial-r2.md:6379:B9.A closes. B9.B opens (Tier A — 113 simple lookups via generic table-driven ingester).
waves/B9\codex-gate-close-r3-prompt.md:1:# Codex B9.A mini-GATE-CLOSE R3 — Final Verification
waves/B9\codex-gate-close-r3-prompt.md:55:- GO — B9.A is officially closed. B9.B opens.
waves/B9\codex-gate-close-r1-prompt.md:1:# Codex B9.A mini-GATE-CLOSE R1 — Consult Prompt
waves/B9\codex-gate-close-r1-prompt.md:11:B9.A laid the cross-cutting infrastructure that B9.B-G (113+66+16+1+2+19
waves/B9\codex-gate-close-r1-prompt.md:14:makes B9.B-G's per-table work mechanical and gate-able.
waves/B9\codex-gate-close-r1-prompt.md:26:c03e37a B9.A C10: FDW name-collision preflight script + test seam
waves/B9\codex-gate-close-r1-prompt.md:82:any SC by itself — it readies the scaffolding so B9.B-G can close
waves/B9\codex-gate-close-r1-prompt.md:99:   that a B9.B per-table test cannot accidentally bypass it?
waves/B9\codex-gate-close-r1-prompt.md:115:   modes use the legacy chain). B9.B-G tier loaders, when built,
waves/B9\codex-gate-close-r1-prompt.md:124:   clear enough that a B9.B operator cannot quietly extend the
waves/B9\codex-gate-close-r1-prompt.md:129:   The intent is to force the refactor decision when B9.B's first
waves/B9\codex-gate-close-r1-prompt.md:143:- **GO** — B9.A closes; B9.B opens.
waves/B9\codex-b9b-gate-close-r1-result.md:14:# Codex B9.B mini-GATE-CLOSE R1 — Consult Prompt
waves/B9\codex-b9b-gate-close-r1-result.md:17:**Phase:** B9.B (Tier A — 113-table simple lookups, recon §3 estimate)
waves/B9\codex-b9b-gate-close-r1-result.md:24:B9.B is the first per-table data wave. Goal per recon §3:
waves/B9\codex-b9b-gate-close-r1-result.md:25:"113 Tier A tables = simple lookup descriptors (≤ 5 cols, < 2 MB)".
waves/B9\codex-b9b-gate-close-r1-result.md:27:**Actual delivered: 107 specs across 11 batches + migration + FDW manifest.**
waves/B9\codex-b9b-gate-close-r1-result.md:39:93c9d8b  B9.B C1 (F4): registry-vs-contract coverage assertion + Tier A charter
waves/B9\codex-b9b-gate-close-r1-result.md:40:2d3e791  B9.B C2: RECORD_COUNTS.TXT parser-format fix + 906-vs-220 discovery
waves/B9\codex-b9b-gate-close-r1-result.md:41:d8af39e  B9.B C3: re-point preflight to DB.zip canonical 220-table namelist
waves/B9\codex-b9b-gate-close-r1-result.md:42:353a04b  B9.B C4: per-table DDL manifest for multi-agent dispatch
waves/B9\codex-b9b-gate-close-r1-result.md:43:50e7a88  B9.B C5: auto-aggregation infrastructure (multi-agent isolation)
waves/B9\codex-b9b-gate-close-r1-result.md:44:79d3416  B9.B C6: Tier A batch_01 (canonical template, 12 id+desc lookups)
waves/B9\codex-b9b-gate-close-r1-result.md:45:7bb9964  B9.B C9: Tier A batch_04 (10 lookup tables) + bundled batch_02 (10)
waves/B9\codex-b9b-gate-close-r1-result.md:46:4a58889  B9.B C8: Tier A batch_03 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-result.md:47:697393c  B9.B C10: Tier A batch_05 (10 lookup tables including 1 DATE coercer)
waves/B9\codex-b9b-gate-close-r1-result.md:48:1d3ffde  B9.B C11: Tier A batch_06 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-result.md:49:6c1ed28  B9.B C12: Tier A batch_07 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-result.md:50:1292c04  B9.B C13: composite-NK template (batch_08, 5 TALL MAN tables)
waves/B9\codex-b9b-gate-close-r1-result.md:51:a4ea4db  B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
waves/B9\codex-b9b-gate-close-r1-result.md:52:86515b5  B9.B C15: Tier A batch_10 (11 link tables — composite+single NK hybrid)
waves/B9\codex-b9b-gate-close-r1-result.md:53:2f226ae  B9.B C16: Tier A batch_11 (11 link tables with DATE columns)
waves/B9\codex-b9b-gate-close-r1-result.md:54:7c1c5e9  B9.B C17+C18: alembic migration 0009_fdb_tier_a + FDW manifest expansion (66 → 173)
waves/B9\codex-b9b-gate-close-r1-result.md:59:### Production code (drug_database/services/fdb_tier_a/)
waves/B9\codex-b9b-gate-close-r1-result.md:66:- `test_fdb_tier_a_batch_01.py` through `test_fdb_tier_a_batch_11.py` — 691 parametrized + sanity tests
waves/B9\codex-b9b-gate-close-r1-result.md:69:### Migration + FDW
waves/B9\codex-b9b-gate-close-r1-result.md:70:- `modules/drug-database/alembic/versions/0009_fdb_tier_a.py` — 1,220 lines auto-generated via `gen_fdb_tier_migration.py`. Creates all 107 tables in `drug_database` schema with proper column types, nullables, GRANTs (env-driven IFX_APP_ROLE pattern), and operator dry-run docstring.
waves/B9\codex-b9b-gate-close-r1-result.md:71:- `infrastructure/scripts/lib/expected_reference_tables.txt` — 66 → 173 entries (+107 Tier A appended in a new section)
waves/B9\codex-b9b-gate-close-r1-result.md:74:- `waves/B9/B9.B-charter.md` — wave charter
waves/B9\codex-b9b-gate-close-r1-result.md:75:- `waves/B9/status.md` — ledger updated to reflect B9.B ready for gate-close
waves/B9\codex-b9b-gate-close-r1-result.md:80:B9.B Tier A unit tests:      691 pass
waves/B9\codex-b9b-gate-close-r1-result.md:97:   agents own per-batch files (`batch_NN.py` + `test_fdb_tier_a_batch_NN.py`)
waves/B9\codex-b9b-gate-close-r1-result.md:132:   tables". Forcing them into Tier A would violate that classification.
waves/B9\codex-b9b-gate-close-r1-result.md:133:   But: does deferring 6 invalidate B9.B as a clean wave boundary,
waves/B9\codex-b9b-gate-close-r1-result.md:134:   or is "Tier A as recon defines it" the right framing?
waves/B9\codex-b9b-gate-close-r1-result.md:164:   `0009_fdb_tier_a.py`. Are the column types reasonable (sa.Integer
waves/B9\codex-b9b-gate-close-r1-result.md:176:GO — B9.B closes; B9.C opens (Tier B — 66 NDC/GCN-keyed joins, plus the 6 reclassified residuals).
waves/B9\codex-b9b-gate-close-r1-result.md:184:I’ll treat this as a gate review: verify the stated artifacts against the repo, sample the migration and tests, then return a GO / GO-WITH-FIXES / NO-GO verdict with concrete findings.
waves/B9\codex-b9b-gate-close-r1-result.md:190:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-ChildItem -Path modules/drug-database/drug_database/services/fdb_tier_a -Filter '*.py' | Select-Object -ExpandProperty Name; Get-ChildItem -Path modules/drug-database/tests/unit -Filter 'test_fdb_tier_a_batch_*.py' | Select-Object -ExpandProperty Name" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:194:"""B9.B C1 â€” F4 from codex GATE-CLOSE R1 MEDIUM 2.
waves/B9\codex-b9b-gate-close-r1-result.md:197:useless if a B9.B-G commit can land a new spec WITHOUT wiring a
waves/B9\codex-b9b-gate-close-r1-result.md:207:The atomic-per-spec PR pattern: a B9.B Tier A commit that adds a
waves/B9\codex-b9b-gate-close-r1-result.md:233:# B9.B C5+ pattern: per-batch test modules declare their own
waves/B9\codex-b9b-gate-close-r1-result.md:235:# across all `test_fdb_tier_a_batch_*.py` modules in the same package.
waves/B9\codex-b9b-gate-close-r1-result.md:247:    starts with `test_fdb_tier_a_batch_`. Imports each, reads its
waves/B9\codex-b9b-gate-close-r1-result.md:264:        if not info.name.startswith("test_fdb_tier_a_batch_"):
waves/B9\codex-b9b-gate-close-r1-result.md:298:        f"B9.B F4 coverage violation: {len(missing)} TableSpec(s) "
waves/B9\codex-b9b-gate-close-r1-result.md:319:        f"B9.B F4: {len(stale)} stale entries in CONTRACT_TESTED_SPECS "
waves/B9\codex-b9b-gate-close-r1-result.md:327:# Empty-baseline canary â€” DELETED on first batch landing (B9.B C6, `50e7a88`).
waves/B9\codex-b9b-gate-close-r1-result.md:329:# file when the first Tier A spec arrived. Now that batch_01 is in, the
waves/B9\codex-b9b-gate-close-r1-result.md:336:- FDW name collision preflight returns 0 collisions for all 217 generated B9 names.
waves/B9\codex-b9b-gate-close-r1-result.md:346:### B9.B â€” Tier A: 113 simple lookup tables (â‰¤ 5 columns, generic ingester) (10 sessions)
waves/B9\codex-b9b-gate-close-r1-result.md:348:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier â€” short tables (mostly < 10K rows, all â‰¤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
waves/B9\codex-b9b-gate-close-r1-result.md:353:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon Â§4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
waves/B9\codex-b9b-gate-close-r1-result.md:361:- 1 alembic migration (`0009_fdb_tier_a.py`)
waves/B9\codex-b9b-gate-close-r1-result.md:363:- Loader-orchestration entry: `--mode fdb_tier_a` loads only Tier A
waves/B9\codex-b9b-gate-close-r1-result.md:369:- SC-2 (RECORD_COUNTS reconciliation) â€” every loaded Tier A table: actual Ã· expected within Â±0.1% tolerance (small lookups should be exact)
waves/B9\codex-b9b-gate-close-r1-result.md:370:- SC-6 (FDW verify) â€” partial: 179/179 PASS after B9.B
waves/B9\codex-b9b-gate-close-r1-result.md:371:- SC-7 (weekly idempotency) â€” verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9\codex-b9b-gate-close-r1-result.md:372:- SC-8 (test strategy) â€” contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
waves/B9\codex-b9b-gate-close-r1-result.md:373:- SC-9 (mini-GATE-CLOSE) â€” see below
waves/B9\codex-b9b-gate-close-r1-result.md:375:**B9.B mini-GATE-CLOSE criteria:**
waves/B9\codex-b9b-gate-close-r1-result.md:377:- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` Â± documented tolerance
waves/B9\codex-b9b-gate-close-r1-result.md:378:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9\codex-b9b-gate-close-r1-result.md:379:- All Tier A contract tests green
waves/B9\codex-b9b-gate-close-r1-result.md:380:- Sampled behavioral tests: 10 randomly-picked Tier A tables exercise non-trivial query (FK join, where-clause, sort)
waves/B9\codex-b9b-gate-close-r1-result.md:382:- Weekly delta path: `load_fdb.py --mode fdb_tier_a` re-run produces 0 new rows (idempotent)
waves/B9\codex-b9b-gate-close-r1-result.md:384:- Codex mini-GATE-CLOSE consult: GO
waves/B9\codex-b9b-gate-close-r1-result.md:392:**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.
waves/B9\codex-b9b-gate-close-r1-result.md:394:**Per-session shape (12 sessions = ~5.5 tables/session â€” slower than Tier A because of join-design + FK-target verification per table):**
waves/B9\codex-b9b-gate-close-r1-result.md:397:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-b9b-gate-close-r1-result.md:418:test_fdb_tier_a_batch_01.py
waves/B9\codex-b9b-gate-close-r1-result.md:419:test_fdb_tier_a_batch_02.py
waves/B9\codex-b9b-gate-close-r1-result.md:420:test_fdb_tier_a_batch_03.py
waves/B9\codex-b9b-gate-close-r1-result.md:421:test_fdb_tier_a_batch_04.py
waves/B9\codex-b9b-gate-close-r1-result.md:422:test_fdb_tier_a_batch_05.py
waves/B9\codex-b9b-gate-close-r1-result.md:423:test_fdb_tier_a_batch_06.py
waves/B9\codex-b9b-gate-close-r1-result.md:424:test_fdb_tier_a_batch_07.py
waves/B9\codex-b9b-gate-close-r1-result.md:425:test_fdb_tier_a_batch_08.py
waves/B9\codex-b9b-gate-close-r1-result.md:426:test_fdb_tier_a_batch_09.py
waves/B9\codex-b9b-gate-close-r1-result.md:427:test_fdb_tier_a_batch_10.py
waves/B9\codex-b9b-gate-close-r1-result.md:428:test_fdb_tier_a_batch_11.py
waves/B9\codex-b9b-gate-close-r1-result.md:437: M infrastructure/scripts/verify_backup.py
waves/B9\codex-b9b-gate-close-r1-result.md:843:7c1c5e9 B9.B C17+C18: alembic migration 0009_fdb_tier_a + FDW manifest expansion (66 → 173)
waves/B9\codex-b9b-gate-close-r1-result.md:844:2f226ae B9.B C16: Tier A batch_11 (11 link tables with DATE columns)
waves/B9\codex-b9b-gate-close-r1-result.md:845:86515b5 B9.B C15: Tier A batch_10 (11 link tables — composite+single NK hybrid)
waves/B9\codex-b9b-gate-close-r1-result.md:846:a4ea4db B9.B C14: APPEND_ONLY history template (batch_09, 8 _HIST tables)
waves/B9\codex-b9b-gate-close-r1-result.md:847:1292c04 B9.B C13: composite-NK template (batch_08, 5 TALL MAN tables)
waves/B9\codex-b9b-gate-close-r1-result.md:848:1d3ffde B9.B C11: Tier A batch_06 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-result.md:849:6c1ed28 B9.B C12: Tier A batch_07 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-result.md:852:7bb9964 B9.B C9: Tier A batch_04 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-result.md:853:697393c B9.B C10: Tier A batch_05 (10 lookup tables including 1 DATE coercer)
waves/B9\codex-b9b-gate-close-r1-result.md:854:4a58889 B9.B C8: Tier A batch_03 (10 lookup tables)
waves/B9\codex-b9b-gate-close-r1-result.md:855:79d3416 B9.B C6: Tier A batch_01 (canonical template, 12 id+desc lookups)
waves/B9\codex-b9b-gate-close-r1-result.md:856:50e7a88 B9.B C5: auto-aggregation infrastructure (multi-agent isolation)
waves/B9\codex-b9b-gate-close-r1-result.md:858:8a477b5 B9.B status ledger: C1–C4 prep ledger + multi-agent dispatch plan
waves/B9\codex-b9b-gate-close-r1-result.md:859:353a04b B9.B C4: per-table DDL manifest for multi-agent dispatch
waves/B9\codex-b9b-gate-close-r1-result.md:860:d8af39e B9.B C3: re-point preflight to DB.zip canonical 220-table namelist
waves/B9\codex-b9b-gate-close-r1-result.md:864:The repo is very dirty outside the B9.B slice, so I’m treating committed `develop` history and the named B9 files as the review surface. The B9.B commits are present at the tip cluster, with unrelated B10 commits interleaved.
waves/B9\codex-b9b-gate-close-r1-result.md:866:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/drug_database/services/fdb_tier_a/__init__.py; Get-Content -Path modules/drug-database/drug_database/services/fdb_specs.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:868:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:870:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/alembic/versions/0009_fdb_tier_a.py -TotalCount 140; Get-Content -Path modules/drug-database/alembic/versions/0009_fdb_tier_a.py -Tail 140' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:874:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4"` rejected: blocked by policy
waves/B9\codex-b9b-gate-close-r1-result.md:877:2026-05-12T14:54:03.000553Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "(Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern '"'^'"\\s*TableSpec\\(').Count; Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py -Pattern 'delta_semantics=DeltaSemantics\\.APPEND_ONLY|UOM_CONVERSION_FACTOR|_parse_fdb_date|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0' -Context 2,4"` rejected: blocked by policy
waves/B9\codex-b9b-gate-close-r1-result.md:880:"""B9.B Tier A â€” Per-batch TableSpec aggregator.
waves/B9\codex-b9b-gate-close-r1-result.md:889:    # drug_database/services/fdb_tier_a/batch_NN.py
waves/B9\codex-b9b-gate-close-r1-result.md:900:            loader_group="fdb_tier_a",
waves/B9\codex-b9b-gate-close-r1-result.md:910:    TIER_A_SPECS         â€” list[TableSpec]    (the canonical Tier A registry)
waves/B9\codex-b9b-gate-close-r1-result.md:976:"""B9.B â€” Registry of FDB TableSpec instances by tier.
waves/B9\codex-b9b-gate-close-r1-result.md:979:platform knows about. B9.B-G populates it tier by tier:
waves/B9\codex-b9b-gate-close-r1-result.md:981:  B9.B â†’ 113 Tier A specs
waves/B9\codex-b9b-gate-close-r1-result.md:1003:from drug_database.services.fdb_tier_a import TIER_A_SPECS
waves/B9\codex-b9b-gate-close-r1-result.md:1006:# Tier A: auto-aggregated from `fdb_tier_a.batch_*` modules so parallel
waves/B9\codex-b9b-gate-close-r1-result.md:1007:# agents do not contend on this file (B9.B C5+ pattern). Each agent
waves/B9\codex-b9b-gate-close-r1-result.md:1018:"""B9 Tier A batch â€” 107 FDB tables (simple lookups, generic ingester).
waves/B9\codex-b9b-gate-close-r1-result.md:1031:`waves/B9/Tier A_dryrun_evidence.md` before committing.
waves/B9\codex-b9b-gate-close-r1-result.md:1033:Revision ID: 0009_fdb_tier_a
waves/B9\codex-b9b-gate-close-r1-result.md:1046:revision: str = "0009_fdb_tier_a"
waves/B9\codex-b9b-gate-close-r1-result.md:1304:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"sa\\.PrimaryKeyConstraint|sa\\.UniqueConstraint|primary_key=True|create_index|unique=True\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py modules/drug-database/alembic/versions/0008_fdb_pricing.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:1306:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "RPEIUC0_UOM_CONVERSION|UOM_CONVERSION_FACTOR|RXRFDDX0|RXRGDFQ0|RXRMDFQ0|RXRPDFQ0|APPEND_ONLY|_parse_fdb_date|Decimal" modules/drug-database/drug_database/services/fdb_tier_a modules/drug-database/tests/unit/test_fdb_tier_a_batch_*.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:1308:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -c \"TableSpec\\(\" modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py; rg -c \"op\\.create_table\\(\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py; rg -c \"op\\.drop_table\\(\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:1312:modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:5:(DOSAGE_FORM_RETIRE_DT) which requires the `_parse_fdb_date` coercer
waves/B9\codex-b9b-gate-close-r1-result.md:1313:modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:28:    _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1314:modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:61:    # DOSAGE_FORM_RETIRE_DT is DATE: uses _parse_fdb_date (YYYYMMDD→date).
waves/B9\codex-b9b-gate-close-r1-result.md:1315:modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:76:            "DOSAGE_FORM_RETIRE_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1316:modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:16:    Decimal money columns and no Date columns (those are Tier B/C).
waves/B9\codex-b9b-gate-close-r1-result.md:1317:modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No Date or Decimal columns
waves/B9\codex-b9b-gate-close-r1-result.md:1318:modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No Date or Decimal columns
waves/B9\codex-b9b-gate-close-r1-result.md:1319:modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No DATE or Decimal columns
waves/B9\codex-b9b-gate-close-r1-result.md:1320:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
waves/B9\codex-b9b-gate-close-r1-result.md:1321:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
waves/B9\codex-b9b-gate-close-r1-result.md:1322:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:16:DATE columns use `_parse_fdb_date` from fdb_adapter (same as
waves/B9\codex-b9b-gate-close-r1-result.md:1323:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:25:    _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1324:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:45:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1325:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1326:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:68:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1327:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1328:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:91:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1329:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1330:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:106:            "HIC_REPL_EFF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1331:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1332:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:125:            "MED_ROUTED_DF_MED_ID_REP_EF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1333:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1334:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:140:            "MED_NAME_ID_REPL_EFF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1335:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1336:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:154:            "MED_MEDID_REPL_EFF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1337:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1338:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:172:            "MED_ROUTED_MED_ID_REPL_EFF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1339:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1340:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:25:    RPEIUC0_UOM_CONVERSION      — (FROM_UOM_MSTR_ID, TO_UOM_MSTR_ID) + UOM_CONVERSION_FACTOR
waves/B9\codex-b9b-gate-close-r1-result.md:1341:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:46:from decimal import Decimal
waves/B9\codex-b9b-gate-close-r1-result.md:1342:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:210:        table_name="RPEIUC0_UOM_CONVERSION",
waves/B9\codex-b9b-gate-close-r1-result.md:1343:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:214:            "UOM_CONVERSION_FACTOR",
waves/B9\codex-b9b-gate-close-r1-result.md:1344:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:219:            "UOM_CONVERSION_FACTOR": Decimal,
waves/B9\codex-b9b-gate-close-r1-result.md:1345:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:287:    "RPEIUC0_UOM_CONVERSION": 2,      # NK=2, conversion factor is 3rd col
waves/B9\codex-b9b-gate-close-r1-result.md:1346:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:14:All DATE columns use `_parse_fdb_date` (YYYYMMDD → datetime.date).
waves/B9\codex-b9b-gate-close-r1-result.md:1347:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:30:    _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1348:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:93:            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1349:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:118:            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1350:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:141:            "EXT_PRODUCT_CD_START_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1351:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:143:            "EXT_PRODUCT_CD_END_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1352:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:173:        table_name="RXRFDDX0_DACN_AGCSP",
waves/B9\codex-b9b-gate-close-r1-result.md:1353:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:184:        record_counts_key="RXRFDDX0",
waves/B9\codex-b9b-gate-close-r1-result.md:1354:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:190:        table_name="RXRGDFQ0_GCDF_SCRIPT_QQ",
waves/B9\codex-b9b-gate-close-r1-result.md:1355:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:201:        record_counts_key="RXRGDFQ0",
waves/B9\codex-b9b-gate-close-r1-result.md:1356:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:207:        table_name="RXRMDFQ0_MEDDOSFM_SCRIPT_QQ",
waves/B9\codex-b9b-gate-close-r1-result.md:1357:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:218:        record_counts_key="RXRMDFQ0",
waves/B9\codex-b9b-gate-close-r1-result.md:1358:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:237:            "OBSOLETE_DATE": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1359:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:248:        table_name="RXRPDFQ0_POEMDOSFM_SCRIPT_QQ",
waves/B9\codex-b9b-gate-close-r1-result.md:1360:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:259:        record_counts_key="RXRPDFQ0",
waves/B9\codex-b9b-gate-close-r1-result.md:1361:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:276:    "RXRFDDX0_DACN_AGCSP": 2,
waves/B9\codex-b9b-gate-close-r1-result.md:1362:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:277:    "RXRGDFQ0_GCDF_SCRIPT_QQ": 2,
waves/B9\codex-b9b-gate-close-r1-result.md:1363:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:278:    "RXRMDFQ0_MEDDOSFM_SCRIPT_QQ": 2,
waves/B9\codex-b9b-gate-close-r1-result.md:1364:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:280:    "RXRPDFQ0_POEMDOSFM_SCRIPT_QQ": 2,
waves/B9\codex-b9b-gate-close-r1-result.md:1365:rg: modules/drug-database/tests/unit/test_fdb_tier_a_batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)
waves/B9\codex-b9b-gate-close-r1-result.md:1377:modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:5:(DOSAGE_FORM_RETIRE_DT) which requires the `_parse_fdb_date` coercer
waves/B9\codex-b9b-gate-close-r1-result.md:1378:modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:28:    _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1379:modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:61:    # DOSAGE_FORM_RETIRE_DT is DATE: uses _parse_fdb_date (YYYYMMDD→date).
waves/B9\codex-b9b-gate-close-r1-result.md:1380:modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:76:            "DOSAGE_FORM_RETIRE_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1381:modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:16:    Decimal money columns and no Date columns (those are Tier B/C).
waves/B9\codex-b9b-gate-close-r1-result.md:1382:modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No Date or Decimal columns
waves/B9\codex-b9b-gate-close-r1-result.md:1383:modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No Date or Decimal columns
waves/B9\codex-b9b-gate-close-r1-result.md:1384:modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:16:Coercer rules: NUMERIC(n) → int; VARCHAR(n) → str. No DATE or Decimal columns
waves/B9\codex-b9b-gate-close-r1-result.md:1385:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
waves/B9\codex-b9b-gate-close-r1-result.md:1386:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
waves/B9\codex-b9b-gate-close-r1-result.md:1387:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:16:DATE columns use `_parse_fdb_date` from fdb_adapter (same as
waves/B9\codex-b9b-gate-close-r1-result.md:1388:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:25:    _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1389:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:45:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1390:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1391:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:68:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1392:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1393:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:91:            "ETC_EFFECTIVE_DATE": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1394:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1395:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:106:            "HIC_REPL_EFF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1396:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1397:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:125:            "MED_ROUTED_DF_MED_ID_REP_EF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1398:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1399:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:140:            "MED_NAME_ID_REPL_EFF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1400:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1401:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:154:            "MED_MEDID_REPL_EFF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1402:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1403:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:172:            "MED_ROUTED_MED_ID_REPL_EFF_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1404:modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1405:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:25:    RPEIUC0_UOM_CONVERSION      — (FROM_UOM_MSTR_ID, TO_UOM_MSTR_ID) + UOM_CONVERSION_FACTOR
waves/B9\codex-b9b-gate-close-r1-result.md:1406:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:46:from decimal import Decimal
waves/B9\codex-b9b-gate-close-r1-result.md:1407:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:210:        table_name="RPEIUC0_UOM_CONVERSION",
waves/B9\codex-b9b-gate-close-r1-result.md:1408:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:214:            "UOM_CONVERSION_FACTOR",
waves/B9\codex-b9b-gate-close-r1-result.md:1409:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:219:            "UOM_CONVERSION_FACTOR": Decimal,
waves/B9\codex-b9b-gate-close-r1-result.md:1410:modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:287:    "RPEIUC0_UOM_CONVERSION": 2,      # NK=2, conversion factor is 3rd col
waves/B9\codex-b9b-gate-close-r1-result.md:1411:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:14:All DATE columns use `_parse_fdb_date` (YYYYMMDD → datetime.date).
waves/B9\codex-b9b-gate-close-r1-result.md:1412:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:30:    _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1413:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:93:            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1414:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:118:            "MED_CONCEPT_OBSDATEC": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1415:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:141:            "EXT_PRODUCT_CD_START_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1416:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:143:            "EXT_PRODUCT_CD_END_DT": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1417:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:173:        table_name="RXRFDDX0_DACN_AGCSP",
waves/B9\codex-b9b-gate-close-r1-result.md:1418:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:184:        record_counts_key="RXRFDDX0",
waves/B9\codex-b9b-gate-close-r1-result.md:1419:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:190:        table_name="RXRGDFQ0_GCDF_SCRIPT_QQ",
waves/B9\codex-b9b-gate-close-r1-result.md:1420:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:201:        record_counts_key="RXRGDFQ0",
waves/B9\codex-b9b-gate-close-r1-result.md:1421:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:207:        table_name="RXRMDFQ0_MEDDOSFM_SCRIPT_QQ",
waves/B9\codex-b9b-gate-close-r1-result.md:1422:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:218:        record_counts_key="RXRMDFQ0",
waves/B9\codex-b9b-gate-close-r1-result.md:1423:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:237:            "OBSOLETE_DATE": _parse_fdb_date,
waves/B9\codex-b9b-gate-close-r1-result.md:1424:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:248:        table_name="RXRPDFQ0_POEMDOSFM_SCRIPT_QQ",
waves/B9\codex-b9b-gate-close-r1-result.md:1425:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:259:        record_counts_key="RXRPDFQ0",
waves/B9\codex-b9b-gate-close-r1-result.md:1426:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:276:    "RXRFDDX0_DACN_AGCSP": 2,
waves/B9\codex-b9b-gate-close-r1-result.md:1427:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:277:    "RXRGDFQ0_GCDF_SCRIPT_QQ": 2,
waves/B9\codex-b9b-gate-close-r1-result.md:1428:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:278:    "RXRMDFQ0_MEDDOSFM_SCRIPT_QQ": 2,
waves/B9\codex-b9b-gate-close-r1-result.md:1429:modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:280:    "RXRPDFQ0_POEMDOSFM_SCRIPT_QQ": 2,
waves/B9\codex-b9b-gate-close-r1-result.md:1430:rg: modules/drug-database/tests/unit/test_fdb_tier_a_batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)
waves/B9\codex-b9b-gate-close-r1-result.md:1529:modules/drug-database/tests/unit\test_fdb_pricing_ingester.py:423:    verifying the ON CONFLICT path returns correct inserted/duplicate counts
waves/B9\codex-b9b-gate-close-r1-result.md:1549:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:10:    (the dominant Tier A pattern — code→desc lookups upsert on the
waves/B9\codex-b9b-gate-close-r1-result.md:1550:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:11:    natural key; weekly delta = corrections).
waves/B9\codex-b9b-gate-close-r1-result.md:1551:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:28:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1552:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:44:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1553:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:54:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1554:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:64:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1555:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:75:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1556:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:88:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1557:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:98:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1558:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1559:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:123:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1560:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:134:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1561:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:145:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1562:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:156:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1563:modules/drug-database/drug_database/services\fdb_tier_a\batch_01.py:166:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1589:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:16:  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
waves/B9\codex-b9b-gate-close-r1-result.md:1590:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:24:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1591:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:43:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1592:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:54:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1593:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:65:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1594:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:81:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1595:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:98:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1596:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1597:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:122:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1598:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:144:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1599:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:157:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1600:modules/drug-database/drug_database/services\fdb_tier_a\batch_02.py:167:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1601:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:12:  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
waves/B9\codex-b9b-gate-close-r1-result.md:1602:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:22:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1603:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:37:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1604:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:47:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1605:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:61:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1606:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:83:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1607:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:93:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1608:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:106:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1609:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:119:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1610:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:132:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1611:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:145:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1612:modules/drug-database/drug_database/services\fdb_tier_a\batch_03.py:155:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1613:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:33:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1614:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:44:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1615:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:121:    natural key is the FIRST column; the second column is the
waves/B9\codex-b9b-gate-close-r1-result.md:1616:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:123:    restores. Correct UPSERT (ON CONFLICT DO UPDATE) passes all four
waves/B9\codex-b9b-gate-close-r1-result.md:1617:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:126:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1618:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:131:    natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1619:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:135:    sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1620:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:138:        natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1621:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:140:        conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1622:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:145:            natural_key={natural_key_col: "key_val_42"},
waves/B9\codex-b9b-gate-close-r1-result.md:1623:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:22:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1624:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:40:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1625:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:53:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1626:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:66:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1627:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:79:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1628:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:81:    # Routed medication (5 columns; natural key = ROUTED_MED_ID, first col)
waves/B9\codex-b9b-gate-close-r1-result.md:1629:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:101:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1630:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:115:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1631:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:128:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1632:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:143:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1633:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:164:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1634:modules/drug-database/drug_database/services\fdb_tier_a\batch_04.py:185:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1635:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1636:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1637:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:109:    natural key is the FIRST column; the second column is the
waves/B9\codex-b9b-gate-close-r1-result.md:1638:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:112:    Correct UPSERT (ON CONFLICT DO UPDATE) passes all four sub-assertions
waves/B9\codex-b9b-gate-close-r1-result.md:1639:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:116:    dict keys into the supplied row for every non-natural-key column, so
waves/B9\codex-b9b-gate-close-r1-result.md:1640:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1641:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:126:    natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1642:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:136:    sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1643:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:139:        natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1644:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:141:        conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1645:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:146:            natural_key={natural_key_col: "key_val_42"},
waves/B9\codex-b9b-gate-close-r1-result.md:1646:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:25:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1647:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:36:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1648:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:112:    Each Tier A table is UPSERT_BY_NATURAL_KEY: the natural key is the
waves/B9\codex-b9b-gate-close-r1-result.md:1649:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:115:    deletes; re-A restores. Correct UPSERT (ON CONFLICT DO UPDATE)
waves/B9\codex-b9b-gate-close-r1-result.md:1650:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:124:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1651:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:129:    natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1652:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:139:    sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1653:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:142:        natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1654:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:144:        conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1655:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:149:            natural_key={natural_key_col: "key_val_42"},
waves/B9\codex-b9b-gate-close-r1-result.md:1656:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1657:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1658:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:109:    natural key is the FIRST column; the second column is the
waves/B9\codex-b9b-gate-close-r1-result.md:1659:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:112:    Correct UPSERT (ON CONFLICT DO UPDATE) passes all four sub-assertions
waves/B9\codex-b9b-gate-close-r1-result.md:1660:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:116:    dict keys into the supplied row for every non-natural-key column, so
waves/B9\codex-b9b-gate-close-r1-result.md:1661:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1662:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:126:    natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1663:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:136:    sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1664:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:139:        natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1665:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:141:        conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1666:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:146:            natural_key={natural_key_col: "key_val_42"},
waves/B9\codex-b9b-gate-close-r1-result.md:1667:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:25:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1668:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:45:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1669:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:58:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1670:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:83:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1671:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:96:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1672:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1673:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:122:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1674:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:135:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1675:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:148:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1676:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:161:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1677:modules/drug-database/drug_database/services\fdb_tier_a\batch_05.py:182:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1678:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1679:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1680:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:109:    natural key is the FIRST column; the second column is the
waves/B9\codex-b9b-gate-close-r1-result.md:1681:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:112:    Correct UPSERT (ON CONFLICT DO UPDATE) passes all four sub-assertions
waves/B9\codex-b9b-gate-close-r1-result.md:1682:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:116:    dict keys into the supplied row for every non-natural-key column, so
waves/B9\codex-b9b-gate-close-r1-result.md:1683:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1684:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:126:    natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1685:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:136:    sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1686:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:139:        natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1687:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:141:        conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1688:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:146:            natural_key={natural_key_col: "key_val_42"},
waves/B9\codex-b9b-gate-close-r1-result.md:1689:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:27:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1690:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:38:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1691:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:115:    natural key is the FIRST column; the second column is used as the
waves/B9\codex-b9b-gate-close-r1-result.md:1692:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:118:    changed_values as required by the SQLite simulator's ON CONFLICT
waves/B9\codex-b9b-gate-close-r1-result.md:1693:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1694:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:126:    natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1695:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:128:    non_key_cols = [c for c in spec.columns if c != natural_key_col]
waves/B9\codex-b9b-gate-close-r1-result.md:1696:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:132:    # the simulator's ON CONFLICT DO UPDATE set_ dict can be constructed
waves/B9\codex-b9b-gate-close-r1-result.md:1697:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:137:    sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1698:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:140:        natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1699:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:142:        conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1700:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:147:            natural_key={natural_key_col: "key_val_42"},
waves/B9\codex-b9b-gate-close-r1-result.md:1710:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:22:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1711:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:40:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1712:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:58:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1713:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:79:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1714:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:98:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1715:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:121:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1716:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:141:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1717:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:160:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1718:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:173:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1719:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:196:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1720:modules/drug-database/drug_database/services\fdb_tier_a\batch_06.py:218:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1721:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:22:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1722:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:41:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1723:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:58:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1724:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:72:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1725:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:86:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1726:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:102:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1727:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:116:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1728:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:130:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1729:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:144:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1730:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:158:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1731:modules/drug-database/drug_database/services\fdb_tier_a\batch_07.py:172:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1732:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:3:The previous batches all used single-column natural keys. Batch 08
waves/B9\codex-b9b-gate-close-r1-result.md:1733:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:10:  1. natural_key dict has multiple entries (all spec.columns except
waves/B9\codex-b9b-gate-close-r1-result.md:1734:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:12:  2. Simulator's `natural_key_columns` is a tuple of those column names.
waves/B9\codex-b9b-gate-close-r1-result.md:1735:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:24:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1736:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1737:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:90:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1738:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:98:    sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1739:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:101:        natural_key_columns=nk_cols,
waves/B9\codex-b9b-gate-close-r1-result.md:1740:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:103:        conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1741:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:106:        # Build natural_key dict — placeholder values for every NK column.
waves/B9\codex-b9b-gate-close-r1-result.md:1742:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:107:        natural_key = {
waves/B9\codex-b9b-gate-close-r1-result.md:1743:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:112:            natural_key=natural_key,
waves/B9\codex-b9b-gate-close-r1-result.md:1744:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:144:    """Every batch_08 spec has multi-column natural key per NATURAL_KEY_COUNT."""
waves/B9\codex-b9b-gate-close-r1-result.md:1745:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:3:This batch mixes single-column and multi-column natural keys:
waves/B9\codex-b9b-gate-close-r1-result.md:1746:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:13:            natural_key dict; last column as the changed value.
waves/B9\codex-b9b-gate-close-r1-result.md:1747:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:15:            col as natural_key; second col as desc; remaining cols as
waves/B9\codex-b9b-gate-close-r1-result.md:1748:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:38:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1749:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:46:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1750:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:105:    """Return a stable placeholder for a natural-key column.
waves/B9\codex-b9b-gate-close-r1-result.md:1751:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:121:    NK >= 2 (composite-NK): natural_key spans the first NK columns;
waves/B9\codex-b9b-gate-close-r1-result.md:1752:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:124:    NK == 1 (single-NK): first column is the natural key; second column
waves/B9\codex-b9b-gate-close-r1-result.md:1753:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:127:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1754:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:139:        sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1755:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:142:            natural_key_columns=nk_cols,
waves/B9\codex-b9b-gate-close-r1-result.md:1756:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:144:            conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1757:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:147:            natural_key = {
waves/B9\codex-b9b-gate-close-r1-result.md:1758:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:153:                # A and C carry the same full-NK row; ON CONFLICT DO NOTHING
waves/B9\codex-b9b-gate-close-r1-result.md:1759:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:157:                    natural_key=natural_key,
waves/B9\codex-b9b-gate-close-r1-result.md:1760:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:186:                    natural_key=natural_key,
waves/B9\codex-b9b-gate-close-r1-result.md:1761:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:199:        natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1762:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:211:        sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1763:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:214:            natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1764:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:216:            conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1765:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:221:                natural_key={natural_key_col: "key_val_42"},
waves/B9\codex-b9b-gate-close-r1-result.md:1766:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:252:def test_spec_natural_key_count_registered(spec) -> None:
waves/B9\codex-b9b-gate-close-r1-result.md:1767:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:269:def test_natural_key_count_covers_all_specs() -> None:
waves/B9\codex-b9b-gate-close-r1-result.md:1768:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1769:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:32:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1770:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:109:    natural key is the FIRST column; the second column is the
waves/B9\codex-b9b-gate-close-r1-result.md:1771:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:112:    Correct UPSERT (ON CONFLICT DO UPDATE) passes all four sub-assertions
waves/B9\codex-b9b-gate-close-r1-result.md:1772:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:116:    dict keys into the supplied row for every non-natural-key column, so
waves/B9\codex-b9b-gate-close-r1-result.md:1773:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1774:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:126:    natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1775:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:136:    sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1776:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:139:        natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1777:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:141:        conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1778:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:146:            natural_key={natural_key_col: "key_val_42"},
waves/B9\codex-b9b-gate-close-r1-result.md:1779:modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:9:                3-column natural key
waves/B9\codex-b9b-gate-close-r1-result.md:1780:modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:23:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1781:modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:48:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1782:modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:63:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1783:modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:85:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1784:modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:105:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1785:modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:125:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1786:modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:130:# Number of natural-key columns per spec — drives the test's
waves/B9\codex-b9b-gate-close-r1-result.md:1787:modules/drug-database/drug_database/services\fdb_tier_a\batch_08.py:132:# is: all columns except the LAST are the natural key; the LAST is
waves/B9\codex-b9b-gate-close-r1-result.md:1789:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:5:simulator uses `append_only=True` (not `conflict_action="upsert"`),
waves/B9\codex-b9b-gate-close-r1-result.md:1790:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:17:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1791:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:25:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1792:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:77:def test_delta_semantics_append_only_for_each_spec(spec, sqlite_engine) -> None:
waves/B9\codex-b9b-gate-close-r1-result.md:1793:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:81:    `make_sqlite_simulator` with `append_only=True` makes every
waves/B9\codex-b9b-gate-close-r1-result.md:1794:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:82:    INSERT a plain INSERT (no ON CONFLICT), and D becomes a tombstone
waves/B9\codex-b9b-gate-close-r1-result.md:1795:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1796:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:91:    # (just count growth); the natural_key is used only for the "find row"
waves/B9\codex-b9b-gate-close-r1-result.md:1797:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:92:    # lookup, which is allowed to return None for append_only tables.
waves/B9\codex-b9b-gate-close-r1-result.md:1798:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:93:    natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1799:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:95:    natural_key = {natural_key_col: "nk_42"}
waves/B9\codex-b9b-gate-close-r1-result.md:1800:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:99:    sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1801:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:102:        natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1802:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:104:        append_only=True,
waves/B9\codex-b9b-gate-close-r1-result.md:1803:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:109:            natural_key=natural_key,
waves/B9\codex-b9b-gate-close-r1-result.md:1804:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:140:def test_spec_uses_append_only_semantics(spec) -> None:
waves/B9\codex-b9b-gate-close-r1-result.md:1805:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
waves/B9\codex-b9b-gate-close-r1-result.md:1806:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:22:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1807:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1808:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1809:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1810:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1811:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1812:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1813:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1814:modules/drug-database/drug_database/services\fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
waves/B9\codex-b9b-gate-close-r1-result.md:1815:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:7:    batch_04 pattern — natural key is columns[0]; extra_cols fills
waves/B9\codex-b9b-gate-close-r1-result.md:1816:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:13:    simulator falls through to `on_conflict_do_nothing` because
waves/B9\codex-b9b-gate-close-r1-result.md:1817:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:19:    batch_08 pattern — first NK cols are the natural key; last column(s)
waves/B9\codex-b9b-gate-close-r1-result.md:1818:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:30:from drug_database.services.fdb_adapter import DeltaSemantics
waves/B9\codex-b9b-gate-close-r1-result.md:1819:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:38:from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402
waves/B9\codex-b9b-gate-close-r1-result.md:1820:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:102:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
waves/B9\codex-b9b-gate-close-r1-result.md:1821:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:107:    natural_key = {col: f"nk_val_{i}" for i, col in enumerate(nk_cols)}
waves/B9\codex-b9b-gate-close-r1-result.md:1822:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:114:        natural_key_col = spec.columns[0]
waves/B9\codex-b9b-gate-close-r1-result.md:1823:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:120:        sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1824:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:123:            natural_key_columns=(natural_key_col,),
waves/B9\codex-b9b-gate-close-r1-result.md:1825:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:125:            conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1826:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:130:                natural_key={natural_key_col: "key_val_42"},
waves/B9\codex-b9b-gate-close-r1-result.md:1827:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:140:        # Pure-link path: ALL columns form the natural key; no non-key
waves/B9\codex-b9b-gate-close-r1-result.md:1828:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:141:        # column exists. The simulator falls back to on_conflict_do_nothing.
waves/B9\codex-b9b-gate-close-r1-result.md:1829:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:145:        sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1830:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:148:            natural_key_columns=nk_cols,
waves/B9\codex-b9b-gate-close-r1-result.md:1831:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:150:            conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1832:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:155:                natural_key=natural_key,
waves/B9\codex-b9b-gate-close-r1-result.md:1833:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:166:        # first nk_count cols are the natural key; last column is the
waves/B9\codex-b9b-gate-close-r1-result.md:1834:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:170:        sim, teardown = make_sqlite_simulator(
waves/B9\codex-b9b-gate-close-r1-result.md:1835:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:173:            natural_key_columns=nk_cols,
waves/B9\codex-b9b-gate-close-r1-result.md:1836:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:175:            conflict_action="upsert",
waves/B9\codex-b9b-gate-close-r1-result.md:1837:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:180:                natural_key=natural_key,
waves/B9\codex-b9b-gate-close-r1-result.md:1838:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:211:def test_natural_key_count_entry_exists(spec) -> None:
waves/B9\codex-b9b-gate-close-r1-result.md:1839:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:34:drops update in-place by natural key; deletion is explicit A/C/D. The
waves/B9\codex-b9b-gate-close-r1-result.md:1840:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:35:link-with-indicator tables update the indicator flag on conflict; pure-
waves/B9\codex-b9b-gate-close-r1-result.md:1841:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:36:link tables have nothing to update on conflict (no-op, correct per the
waves/B9\codex-b9b-gate-close-r1-result.md:1842:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:37:simulator's `on_conflict_do_nothing` fallback for all-NK tables).
waves/B9\codex-b9b-gate-close-r1-result.md:1843:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:40:  value = number of leading columns that form the natural key.
waves/B9\codex-b9b-gate-close-r1-result.md:1844:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:49:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1845:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:72:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1846:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:90:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1847:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:108:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1848:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:128:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1849:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:148:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1850:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:168:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1851:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:186:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1852:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:204:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1853:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:224:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1854:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:245:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1855:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:264:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1856:modules/drug-database/drug_database/services\fdb_tier_a\batch_10.py:269:# Number of natural-key columns per spec — drives the test's ACD cycle
waves/B9\codex-b9b-gate-close-r1-result.md:1859:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:27:    DeltaSemantics,
waves/B9\codex-b9b-gate-close-r1-result.md:1860:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:56:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1861:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:77:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1862:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:99:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1863:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:124:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1864:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:149:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1865:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:168:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1866:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:185:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1867:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:202:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1868:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:219:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1869:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:243:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1870:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:260:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1871:modules/drug-database/drug_database/services\fdb_tier_a\batch_11.py:265:# Number of natural-key columns per spec — drives the test's hybrid
waves/B9\codex-b9b-gate-close-r1-result.md:1872:modules/drug-database/drug_database/services\fdb_tier_a\__init__.py:12:        DeltaSemantics, TableSpec, Tier,
waves/B9\codex-b9b-gate-close-r1-result.md:1873:modules/drug-database/drug_database/services\fdb_tier_a\__init__.py:23:            delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
waves/B9\codex-b9b-gate-close-r1-result.md:1878:rg: modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: IO error for operation on modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)
waves/B9\codex-b9b-gate-close-r1-result.md:2073:    semantics class to verify delta correctness, not just replay safety.
waves/B9\codex-b9b-gate-close-r1-result.md:2114:                          (e.g., "fdb_tier_a" â€” loaders register by group).
waves/B9\codex-b9b-gate-close-r1-result.md:2223:The generator runs ONCE per tier during B9.B-G execution. Its output
waves/B9\codex-b9b-gate-close-r1-result.md:2225:verify the generator produces valid Python with the right structure
waves/B9\codex-b9b-gate-close-r1-result.md:2292:    """A minimal valid Tier A TableSpec for tests."""
waves/B9\codex-b9b-gate-close-r1-result.md:2299:        loader_group="fdb_tier_a",
waves/B9\codex-b9b-gate-close-r1-result.md:2310:        revision_id="0009_fdb_tier_a",
waves/B9\codex-b9b-gate-close-r1-result.md:2322:        revision_id="0009_fdb_tier_a",
waves/B9\codex-b9b-gate-close-r1-result.md:2325:    assert 'revision: str = "0009_fdb_tier_a"' in src
waves/B9\codex-b9b-gate-close-r1-result.md:2339:        revision_id="0009_fdb_tier_a",
waves/B9\codex-b9b-gate-close-r1-result.md:2356:        revision_id="0009_fdb_tier_a",
waves/B9\codex-b9b-gate-close-r1-result.md:2372:            revision_id="0009_fdb_tier_a",
waves/B9\codex-b9b-gate-close-r1-result.md:2389:            revision_id="0009_fdb_tier_a",
waves/B9\codex-b9b-gate-close-r1-result.md:2394:def test_generated_migration_includes_dryrun_reminder() -> None:
waves/B9\codex-b9b-gate-close-r1-result.md:2399:        revision_id="0009_fdb_tier_a",
waves/B9\codex-b9b-gate-close-r1-result.md:2404:    assert "dryrun_evidence.md" in src
waves/B9\codex-b9b-gate-close-r1-result.md:2415:modules/drug-database/tests/unit\test_fdb_delta_semantics.py:9:  * APPEND_ONLY history table                  → PASS (row count grows)
waves/B9\codex-b9b-gate-close-r1-result.md:2443:modules/drug-database/tests/unit\test_fdb_contract_coverage.py:126:        f"B9.B F4: {len(stale)} stale entries in CONTRACT_TESTED_SPECS "
waves/B9\codex-b9b-gate-close-r1-result.md:2445:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:7:  2. Declares `BATCH_TESTED_NAMES: frozenset[str]` — the
waves/B9\codex-b9b-gate-close-r1-result.md:2446:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:9:     CONTRACT_TESTED_SPECS becomes the union of all batch declarations.
waves/B9\codex-b9b-gate-close-r1-result.md:2447:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:41:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2448:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:54:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2449:modules/drug-database/tests/unit\test_fdb_tier_a_batch_01.py:143:        assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2450:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:29:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2451:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:42:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2452:modules/drug-database/tests/unit\test_fdb_tier_a_batch_04.py:144:        assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2453:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:33:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2454:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:46:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2455:modules/drug-database/tests/unit\test_fdb_tier_a_batch_03.py:147:        assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2456:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:29:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2457:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:42:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2458:modules/drug-database/tests/unit\test_fdb_tier_a_batch_02.py:144:        assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2459:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:35:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2460:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:48:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2461:modules/drug-database/tests/unit\test_fdb_tier_a_batch_05.py:145:        assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2462:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:29:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2463:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:42:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2464:modules/drug-database/tests/unit\test_fdb_tier_a_batch_06.py:144:        assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2465:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:30:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2466:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:37:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2467:modules/drug-database/tests/unit\test_fdb_tier_a_batch_08.py:110:        assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2468:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:29:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2469:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:42:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2470:modules/drug-database/tests/unit\test_fdb_tier_a_batch_07.py:144:        assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2471:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:1:"""B9.B C14 — Tier A batch 09 contract tests (APPEND_ONLY history template).
waves/B9\codex-b9b-gate-close-r1-result.md:2472:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:3:batch_09 specs are all `delta_semantics=APPEND_ONLY` — history rows
waves/B9\codex-b9b-gate-close-r1-result.md:2473:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:6:and the contract template's APPEND_ONLY branch asserts row-count
waves/B9\codex-b9b-gate-close-r1-result.md:2474:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:23:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2475:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:30:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2476:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:67:# APPEND_ONLY ACD cycle
waves/B9\codex-b9b-gate-close-r1-result.md:2477:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:78:    """Every batch_09 spec passes the APPEND_ONLY A/C/D/re-A contract.
waves/B9\codex-b9b-gate-close-r1-result.md:2478:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:80:    APPEND_ONLY semantics: every transaction grows the row count.
waves/B9\codex-b9b-gate-close-r1-result.md:2479:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
waves/B9\codex-b9b-gate-close-r1-result.md:2480:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:86:        f"{spec.table_name}: batch_09 invariant — APPEND_ONLY only."
waves/B9\codex-b9b-gate-close-r1-result.md:2481:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:90:    # The template's APPEND_ONLY branch doesn't check state-after-A specifically
waves/B9\codex-b9b-gate-close-r1-result.md:2482:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:107:        assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2483:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:141:    """batch_09 is APPEND_ONLY only — no UPSERTs in history tables."""
waves/B9\codex-b9b-gate-close-r1-result.md:2484:modules/drug-database/tests/unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
waves/B9\codex-b9b-gate-close-r1-result.md:2485:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:36:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2486:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:47:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2487:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:128:            assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2488:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:153:            assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2489:modules/drug-database/tests/unit\test_fdb_tier_a_batch_10.py:178:            assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2490:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:44:    assert_delta_semantics_acd_cycle,
waves/B9\codex-b9b-gate-close-r1-result.md:2491:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:51:BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)
waves/B9\codex-b9b-gate-close-r1-result.md:2492:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:151:            if not non_nk_cols:
waves/B9\codex-b9b-gate-close-r1-result.md:2493:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:155:                assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2494:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:184:                assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2495:modules/drug-database/tests/unit\test_fdb_tier_a_batch_11.py:219:            assert_delta_semantics_acd_cycle(
waves/B9\codex-b9b-gate-close-r1-result.md:2501:idempotent Alembic migration source as a string. Used by B9.B-G to
waves/B9\codex-b9b-gate-close-r1-result.md:2504:    0009_fdb_tier_a              â€” 113 simple lookups (Tier A)
waves/B9\codex-b9b-gate-close-r1-result.md:2512:ONCE per tier during B9.B-G execution; the operator reviews the
waves/B9\codex-b9b-gate-close-r1-result.md:2646:`waves/B9/{tier_label}_dryrun_evidence.md` before committing.
waves/B9\codex-b9b-gate-close-r1-result.md:2701:        revision_id: alembic revision identifier (e.g., "0009_fdb_tier_a").
waves/B9\codex-b9b-gate-close-r1-result.md:2775:The TableSpec layer is parse metadata only; it does not carry natural-key columns. The tests infer keys per batch, but the migration generator does not emit keys or unique constraints, and `rg` found none in `0009_fdb_tier_a.py`. That is now the main risk I’m validating against the stated gate criteria.
waves/B9\codex-b9b-gate-close-r1-result.md:2777:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "fdb_tier_a|loader_group|REGISTERED_SPECS|load_fdb|DeltaSemantics|on_conflict_do_update|on_conflict_do_nothing" scripts modules/drug-database/drug_database modules/drug-database/tests -g "*.py"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:2779:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "fdb_tier_a|Tier A|B9.B|0009_fdb_tier_a|dryrun|mini-GATE|row count|FDW|verify" waves/B9 modules/drug-database infrastructure/scripts/lib/expected_reference_tables.txt -g "*.md" -g "*.txt"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:2780:2026-05-12T14:55:07.391106Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$env:PYTHONPATH='"'modules/drug-database'; "'$env:PYTHONDONTWRITEBYTECODE='"'1'; python -c \"from drug_database.services.fdb_specs import REGISTERED_SPECS; from drug_database.services.fdb_tier_a import discovered_batches; print(len(REGISTERED_SPECS)); print(discovered_batches())\""` rejected: blocked by policy
waves/B9\codex-b9b-gate-close-r1-result.md:2782:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$env:PYTHONPATH='"'modules/drug-database'; "'$env:PYTHONDONTWRITEBYTECODE='"'1'; python -c \"from drug_database.services.fdb_specs import REGISTERED_SPECS; from drug_database.services.fdb_tier_a import discovered_batches; print(len(REGISTERED_SPECS)); print(discovered_batches())\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:2784:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "RAHFSGC1|RATCGC0|RGCN0|RETCNDC0|RGCNINH0|RGCNINS0|Tier B|NDC/GCN|MedID" waves/B9 data/reference/fdb modules/drug-database/drug_database/services/fdb_tier_a -g "*.md" -g "*.py" -g "*.txt"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-b9b-gate-close-r1-result.md:2786:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$env:PYTHONPATH='"'modules/drug-database'; "'$env:PYTHONDONTWRITEBYTECODE='"'1'; python -c \"from drug_database.services.fdb_specs import REGISTERED_SPECS; from drug_database.services.fdb_tier_a import discovered_batches; print(len(REGISTERED_SPECS)); print(discovered_batches())\""` rejected: blocked by policy
waves/B9\codex-gate-close-r2-prompt.md:1:# Codex B9.A mini-GATE-CLOSE R2 — Verification Pass
waves/B9\codex-gate-close-r2-prompt.md:14:B9.A GATE-CLOSE R1 absorption — HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
waves/B9\codex-gate-close-r2-prompt.md:65:Explicitly deferred to B9.B per codex's own remediation language:
waves/B9\codex-gate-close-r2-prompt.md:66:"In B9.B, add a registry-vs-contract coverage test...". Documented
waves/B9\codex-gate-close-r2-prompt.md:67:as a B9.B pre-opening obligation in `waves/B9/status.md` →
waves/B9\codex-gate-close-r2-prompt.md:68:"B9.B pre-opening obligation (F4)".
waves/B9\codex-gate-close-r2-prompt.md:78:## Areas to verify in R2
waves/B9\codex-gate-close-r2-prompt.md:91:4. **F4 deferral**: is the status-ledger row + B9.B pre-opening
waves/B9\codex-gate-close-r2-prompt.md:97:GO — B9.A closes; B9.B opens.
waves/B9\parse_warning_allowlist.md:4:**Audit gate:** every B9.B-G mini-GATE-CLOSE re-reads this file; any
waves/B9\status.md:18:| B9.B | Tier A — **107 specs across 11 batches + migration + FDW manifest** | **READY FOR GATE-CLOSE** | `93c9d8b..<HEAD>` | 6 short of recon's 113 target; the 6 residual are NDC/GCN/MEDID-keyed → reclassified as Tier B (B9.C scope) |
waves/B9\status.md:19:| B9.C | Tier B — 66 NDC/GCN joins | NOT STARTED | — | Blocked on B9.B |
waves/B9\status.md:42:| C10 | FDW name-collision preflight script | `c03e37a` | 16 (107) |
waves/B9\status.md:69:| MEDIUM | Delta-contract bypass risk (B9.B-G omitted from contract) | **F4 — deferred to B9.B opening.** Codex's own suggested fix specifies: "In B9.B, add a registry-vs-contract coverage test proving every new non-UNKNOWN/non-TRUNCATE_RELOAD TableSpec is represented in the delta contract suite." This is a B9.B C1-class commit. |
waves/B9\status.md:71:**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
waves/B9\status.md:137:## B9.B C2 — Real-file lock-in (parser-format fix)
waves/B9\status.md:141:**Defect impact (would have surfaced on first B9.B C3 row-count reconciliation):**
waves/B9\status.md:143:- `assert_row_count_reconciles` would fail every B9.B+ contract test with "no entry for key" — masking the real assertion.
waves/B9\status.md:146:**Fix shipped (same commit as B9.B C2):**
waves/B9\status.md:153:- **B9.B C3 design decision (deferred to next session):** re-point the preflight `load_expected_names` to source from DB.zip namelist instead of RECORD_COUNTS. RECORD_COUNTS remains the row-count reconciliation source for the 220 tables it DOES cover.
waves/B9\status.md:156:This is the kind of defect the recon's "verify against real drop" gate is designed to catch. Surfaced before the multi-agent per-table dispatch could amplify it across 113 specs.
waves/B9\status.md:160:## B9.B prep ledger (C1–C4 — multi-agent dispatch enablement)
waves/B9\status.md:171:With C1–C4 landed, each B9.B per-table builder agent has authoritative inputs:
waves/B9\status.md:178:**B9.B C5 design (next-session first commit):**
waves/B9\status.md:180:Author ONE batch by hand (12 Tier A tables) as the canonical pattern.
waves/B9\status.md:182:- `drug_database/services/fdb_tier_a_batches/batch_01.py` with `BATCH_01: list[TableSpec] = [...]`
waves/B9\status.md:184:- `tests/unit/test_fdb_tier_a_batch_01.py` wires each spec through the 6 contract helpers
waves/B9\status.md:187:**B9.B C6+ multi-agent dispatch (after template proven):**
waves/B9\status.md:203:| ADVERSARIAL R2 | Mitigation verify | GO | `codex-adversarial-r2.md` |
waves/B9\status.md:210:B9.B with the F4 pre-opening obligation as its first commit.
waves/B9\status.md:214:## B9.A mini-GATE-CLOSE checklist (charter SC-9)
waves/B9\status.md:220:- [x] `setup_fdw.sh --verify` still passes (132 PASS, 0 FAIL — captured post-B7.3)
waves/B9\status.md:223:- [x] FDW name-collision preflight script in place + 16/16 tests pass
waves/B9\status.md:227:- [ ] Codex B9.A mini-GATE-CLOSE consult dispatched + verdict captured
waves/B9\status.md:238:| SC-1 | 217 tables have models + migrations + ingester | **+0** (B9.B-G lands actual tables) |
waves/B9\status.md:239:| SC-2 | RECORD_COUNTS reconciliation (within ±0.1%) | Contract template ready (C3); per-table assertions land B9.B+ |
waves/B9\status.md:240:| SC-3 | DELTA_SEMANTICS per table | Enum + contract (C1+C3+C8) ready; per-table assignment B9.B+ |
waves/B9\status.md:241:| SC-4 | Phase 09 untouched (row counts, query latency) | Baseline locked (C12); test runs every gate |
waves/B9\status.md:243:| SC-6 | FDW verify count grows additively | Manifest-derived count (C11) ready; floor 66 |
waves/B9\status.md:246:| SC-9 | Per-phase mini-GATE-CLOSE | This file is the ledger; per-phase entries appear B9.B+ |
waves/B9\status.md:247:| SC-10 | MTL excluded from default load + FDW | Config flag + registry + REVOKE template (C4) ready |
waves/B9\status.md:271:* At every mini-GATE-CLOSE — append the per-phase evidence section.
waves/B9\write_path_enforcement.md:10:B9 FDB loaders write reference tables (Tier A/B/C/RNDC14/pricing/MTL)
waves/B9\write_path_enforcement.md:48:python scripts/load_fdb.py --mode fdb_tier_a --require-reference-db
waves/B9\write_path_enforcement.md:51:The `--require-reference-db` flag is set automatically by every B9.B-G
waves/B9\plan.md:3:**Status:** PLAN v3.1 LOCKED — **ADVERSARIAL GATE FINAL VERDICT: GO** (`codex-adversarial-r2.md` tail). B9.A meta-phase gate cycle CLOSED. Ready for B9.A C0-C14 execution, then B9.B opens (Tier A — 113 simple lookups via generic table-driven ingester).
waves/B9\plan.md:5:**Iteration history:** PLAN v1 → PLAN R1 GO-WITH-FIXES (8 fixes) → PLAN v2 → PLAN R2 GO-WITH-FIXES (charter v3.1 erratum) → PLAN GATE FINAL VERDICT GO → ADVERSARIAL R1 HIGH-SEVERITY OBJECTIONS PRESENT (9 HIGH + 11 MED + 4 novel) → PLAN v3 (all mitigations folded) → charter v3.2 erratum (MTL FDW exposure) → ADVERSARIAL R2 GO-WITH-FIXES (one stale line) → PLAN v3.1 (narrow fix) → ADVERSARIAL R3 first ping (caught one more stale FDW reference) → cleanup → ADVERSARIAL R3 second ping **GO**.
waves/B9\plan.md:17:2. **Per-phase scope, deliverables, success-criteria mapping, gate criteria, est sessions, commit shape** for B9.B..B9.H.
waves/B9\plan.md:21:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9\plan.md:26:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\plan.md:40:| A7 perf gate | H | "Documented" without abort | B9.F hard timing aborts: FDW verify > 5 min → FAIL; per-table weekly delta > 30s → FAIL; total weekly delta > 10 min → FAIL. Charter SC-4 wording strengthened in plan §B9.F. See T15. |
waves/B9\plan.md:41:| A8 MTL FDW silent | H | Empty FDW foreign tables = silent false-negative joins | MTL excluded from default FDW manifest (charter v3.2 erratum: 264 default / 283 conditional). MTL data activation work — including the +19 FDW entries — moves to a future wave when licensing flips. See T16. |
waves/B9\plan.md:43:| A14 adjudication ripple | H | Consumer audit missing | B9.H Session 3 adds adjudication audit: pricing-enrichment path with B9 data present; TCP listener publish smoke; FDW query smoke with new tables. See T18. |
waves/B9\plan.md:45:| N1 FDW name collision | H | `setup_fdw.sh` fatals on duplicate; no preflight | B9.A C10 preflight: generate all 217 B9 table names; scan `infinityrx_reference` schemas (drug_database / drug_db / reference / shared) for collisions; abort if any. See T20. |
waves/B9\plan.md:47:| A1 session overflow | M | "Next absorbs overflow" not a control | Per-table escape-hatch: any Tier A table that consumes > 1 hour solo gets reclassified to Tier B/C; removed from `0009_fdb_tier_a.py`; FDW ladder updated; mini-re-plan triggered if session burn > +20%. See T22. |
waves/B9\plan.md:48:| A2 migration blast radius | M | 113-table migration failure = wide blast | Each migration requires `alembic upgrade + downgrade + upgrade` evidence captured on a disposable DB before commit; mini-GATE-CLOSE checks evidence file exists. See T23. |
waves/B9\plan.md:49:| A3 FDW manifest | M | Hard-coded "expected 66"; concurrent-edit conflicts | B9.A C11 replaces hard-coded 66 in `setup_fdw.sh --verify` with manifest-derived count; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is the source of truth. See T24. |
waves/B9\plan.md:50:| A6 RNDC14 iteration | M | 2 sessions fragile if 5+ type issues | B9.E iteration rule: sessions may expand from 2 → up to 4 without borrowing from B9.F budget; mini-GATE-CLOSE will not close on partial column review. See T25. |
waves/B9\plan.md:51:| A9 calendar slip | M | 4-5 months freeze of visible delivery | 4-week calendar checkpoint: at week-4 / week-8 / week-12 owner reviews B9.X.* progress + decides whether to ship intermediate milestone tags (B9.B-shipped, B9.C-shipped) under the single B9 label. See T26. |
waves/B9\plan.md:53:| A12 Phase 09 compat | M | Existing 3-table coverage might break | B9.A C12 captures Phase 09 baseline: row counts for `fdb_ndc_price_history` + `fdb_price_type_desc`, query latency on representative NDC + price_type lookups, default-mode behavior. Mini-GATE-CLOSE re-runs and asserts unchanged. See T28. |
waves/B9\plan.md:56:| N2 manifest semantics | M | `>0 rows` policy contradicts B9.G empty MTL | Resolved by A8 mitigation (MTL not in default FDW). Document the policy explicitly in `infrastructure/scripts/lib/expected_reference_tables.txt` header. See T31. |
waves/B9\plan.md:66:2. **B7.2 Phase 11A COMPLETE** — `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
waves/B9\plan.md:67:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\plan.md:70:6. **134 pre-existing test failures baseline frozen** — at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged ± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
waves/B9\plan.md:71:7. **FDB drop manifest reachable** — `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon §1.5 verified — re-verify at C0).
waves/B9\plan.md:81:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
waves/B9\plan.md:93:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder (charter v3.2 + ADVERSARIAL A8 mitigation): **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 264 (after B9.G — MTL schema lands but is EXCLUDED from default FDW manifest to prevent silent false-negative joins)**. B9.H final verify: **264/264 default**; conditional 283/283 only if `fdb_load_mtl=True` (future MTL activation wave adds the +19 FDW entries together with data load + grant flip). MTL contributes 0 default FDW entries.
waves/B9\plan.md:94:- **pytest baseline markers** — committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
waves/B9\plan.md:100:| C0 | Baseline + invariants captured (df, pg_authid, FDW 66/66, pytest node-ID snapshots × 2 runs for flake detection) | `waves/B9/baseline.md`, `waves/B9/test_flake_quarantine.md` |
waves/B9\plan.md:110:| **C10** | **FDW name collision preflight — generate 217 B9 table names; scan all `infinityrx_reference` schemas; abort on any collision** | `infrastructure/scripts/preflight_b9_name_collision.py`, evidence |
waves/B9\plan.md:111:| **C11** | **`setup_fdw.sh --verify` manifest-derived count (replace hard-coded `expected 66`) + deterministic sorted manifest ordering** | `infrastructure/scripts/setup_fdw.sh`, `infrastructure/scripts/lib/expected_reference_tables.txt` |
waves/B9\plan.md:112:| **C12** | **Phase 09 compatibility baseline: capture RNP3 + RPRDPTD0 + RNPTYPD0 row counts + query latency + default-mode behavior; mini-GATE-CLOSE re-asserts unchanged at every phase** | `waves/B9/phase09_compat_baseline.md`, compat test |
waves/B9\plan.md:116:**B9.A mini-GATE-CLOSE criteria (charter SC-9, expanded for ADVERSARIAL):**
waves/B9\plan.md:120:- `setup_fdw.sh --verify` still passes against current manifest-derived count (no FDB tables added yet; expected count == current count).
waves/B9\plan.md:123:- FDW name collision preflight returns 0 collisions for all 217 generated B9 names.
waves/B9\plan.md:133:### B9.B — Tier A: 113 simple lookup tables (≤ 5 columns, generic ingester) (10 sessions)
waves/B9\plan.md:135:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier — short tables (mostly < 10K rows, all ≤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
waves/B9\plan.md:140:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon §4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
waves/B9\plan.md:148:- 1 alembic migration (`0009_fdb_tier_a.py`)
waves/B9\plan.md:150:- Loader-orchestration entry: `--mode fdb_tier_a` loads only Tier A
waves/B9\plan.md:156:- SC-2 (RECORD_COUNTS reconciliation) — every loaded Tier A table: actual ÷ expected within ±0.1% tolerance (small lookups should be exact)
waves/B9\plan.md:157:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
waves/B9\plan.md:158:- SC-7 (weekly idempotency) — verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9\plan.md:159:- SC-8 (test strategy) — contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
waves/B9\plan.md:160:- SC-9 (mini-GATE-CLOSE) — see below
waves/B9\plan.md:162:**B9.B mini-GATE-CLOSE criteria:**
waves/B9\plan.md:164:- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` ± documented tolerance
waves/B9\plan.md:165:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9\plan.md:166:- All Tier A contract tests green
waves/B9\plan.md:167:- Sampled behavioral tests: 10 randomly-picked Tier A tables exercise non-trivial query (FK join, where-clause, sort)
waves/B9\plan.md:169:- Weekly delta path: `load_fdb.py --mode fdb_tier_a` re-run produces 0 new rows (idempotent)
waves/B9\plan.md:171:- Codex mini-GATE-CLOSE consult: GO
waves/B9\plan.md:179:**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.
waves/B9\plan.md:181:**Per-session shape (12 sessions = ~5.5 tables/session — slower than Tier A because of join-design + FK-target verification per table):**
waves/B9\plan.md:184:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\plan.md:194:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\plan.md:195:- FDW foreign-table count: 179 → 245
waves/B9\plan.md:199:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\plan.md:220:- FDW foreign-table count: 245 → **261**
waves/B9\plan.md:225:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
waves/B9\plan.md:233:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\plan.md:246:- FDW foreign-table count: 261 → 262
waves/B9\plan.md:250:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
waves/B9\plan.md:263:- Session 2: Timed full-load dry run for both tables; capture wall-clock + final row count + Postgres index build time; capture `df -h` before/after
waves/B9\plan.md:265:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline; **reclaimrx pricing-protocol tests** (ADVERSARIAL A15): exercise `awp_basis` distribution with populated RNP2 + RPRDPP0 + RNP3; assert no new basis values appear; assert literal-AWP guards still reject correctly
waves/B9\plan.md:274:- FDW foreign-table count: 262 → 264
waves/B9\plan.md:278:**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4 + ADVERSARIAL A7 hard aborts:**
waves/B9\plan.md:283:- FDW + Postgres verify after indexes built: **HARD ABORT if > 5 minutes**
waves/B9\plan.md:286:- Codex mini-GATE-CLOSE consult: GO; codex reviews EXPLAIN ANALYZE for index gaps + reviews reclaimrx test deltas
waves/B9\plan.md:298:- Session 1: 19 SQLAlchemy models in `tier_d/`; migration `0014_fdb_mtl_schema.py` (un-gated, lands schema); 19 contract tests asserting tables exist + are queryable + are EMPTY. **MTL tables NOT added to FDW manifest by default** (ADVERSARIAL A8 mitigation — prevents silent false-negative joins from downstream queries).
waves/B9\plan.md:300:- Session 3: Integration test `test_fdb_mtl_zero_rows_under_default` (from B9.A C4) exercises the live MTL tables — asserts zero rows after default load. **Negative test added:** app-role INSERT into MTL table MUST fail with permission error (verifies DB-level guard works). Documentation: `docs/runbooks/fdb-mtl-opt-in.md` explains the FUTURE activation path (FDW manifest expansion to 283 + grant flip + data load) when licensing flips.
waves/B9\plan.md:311:- Runbook `docs/runbooks/fdb-mtl-opt-in.md` (covers MTL activation: FDW expansion 264→283, grants, loader flag flip)
waves/B9\plan.md:312:- FDW foreign-table count: 264 → **264** (unchanged — MTL excluded by default per ADVERSARIAL A8 + charter v3.2)
waves/B9\plan.md:314:**FDW count derivation (final per charter v3.2):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + **0 (B9.G MTL — schema-only, FDW-excluded)** = **264**. Charter v3.2 SC-6 = 264/264 default; conditional 283/283 if MTL data is later enabled.
waves/B9\plan.md:316:**Success criteria:** SC-1 (cum 217/217 — MTL schema present even though FDW-excluded), SC-5 (MTL zero-row test green + DB guard verified), SC-6 (264/264 default), SC-9.
waves/B9\plan.md:318:**B9.G mini-GATE-CLOSE criteria:**
waves/B9\plan.md:323:- FDW manifest verified: MTL tables NOT present (264 entries total)
waves/B9\plan.md:325:- Codex mini-GATE-CLOSE consult: GO; codex verifies (a) DB-level guard prevents app-role writes, (b) flipping `fdb_load_mtl=False` after data load DOES NOT delete data, (c) MTL exclusion from FDW is correct for default state
waves/B9\plan.md:331:**Scope:** Reconcile `expected_reference_tables.txt` to the final count (264 default), run final FDW verify, audit downstream consumers (adjudication + reclaimrx + TCP listener), produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
waves/B9\plan.md:336:- Session 2: Final `setup_fdw.sh --verify` **264/264** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables (217 + 2 existing = 219 DB tables; 264 FDW entries); published in `waves/B9/evidence.md`
waves/B9\plan.md:337:- **Session 3 (NEW — ADVERSARIAL A14):** Consumer audit. Runs three smoke suites against the populated reference DB: (a) **adjudication pricing-enrichment** path — `enrich_pricing()` returns correct WAC/AWP/NADAC + `awp_basis` for representative NDCs across all 5 pricing tables (RNP2/RNP3/RPRDPP0 + NADAC); (b) **TCP listener publish** — claim adjudication runs end-to-end, `claim.adjudicated` event publishes with FDB enrichment fields present; (c) **FDW query smoke** — adjudication, reclaimrx, network-management each run their top-3 FDB-reading queries; all succeed. Failures here trigger B9.H NO-GO and consumer-side fixes.
waves/B9\plan.md:344:- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
waves/B9\plan.md:358:- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
waves/B9\plan.md:361:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9\plan.md:376:| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
waves/B9\plan.md:377:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9\plan.md:380:| SC-6 | `setup_fdw.sh --verify` output **264/264** in dev + mock default (charter v3.2 matched); conditional 283/283 when `fdb_load_mtl=True` | B9.H Session 2 |
waves/B9\plan.md:383:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
waves/B9\plan.md:393:| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon §7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
waves/B9\plan.md:394:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9\plan.md:396:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
waves/B9\plan.md:399:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
waves/B9\plan.md:400:| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
waves/B9\plan.md:401:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
waves/B9\plan.md:402:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, ± in-phase contract tests on the collection number. |
waves/B9\plan.md:403:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
waves/B9\plan.md:404:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
waves/B9\plan.md:405:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) — ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
waves/B9\plan.md:407:| T15 | B9.F perf gate documented without aborting — slow query "passes" — ADVERSARIAL A7 | LOW | **HIGH** | HARD ABORT criteria: FDW verify > 5 min, per-table weekly delta > 30s, total weekly delta > 10 min, storage delta > +1.4 GB. Any breach → B9.F fails, design rework required before B9.G opens. |
waves/B9\plan.md:408:| T16 | MTL FDW foreign tables empty → silent false-negative downstream joins — ADVERSARIAL A8 | MED | **HIGH** | MTL EXCLUDED from default FDW manifest (charter v3.2 erratum). Conditional inclusion (264 → 283) only when MTL data is activated. Downstream join to MTL fails LOUDLY (relation does not exist) instead of silently empty. |
waves/B9\plan.md:410:| T18 | Adjudication consumers untested against B9 data; new FDB tables may change pricing-enrichment paths — ADVERSARIAL A14 | MED | **HIGH** | B9.H Session 3 runs three consumer audits: (a) `enrich_pricing()` against representative NDCs, (b) TCP listener publish smoke with `claim.adjudicated` event verification, (c) FDW query smoke from adjudication + reclaimrx + network-management top-3 queries |
waves/B9\plan.md:412:| T20 | FDW name collision — `setup_fdw.sh` fatals on duplicate names across reference schemas — ADVERSARIAL N1 | LOW | **HIGH** | B9.A C10: preflight scans 217 generated B9 table names against `drug_database / drug_db / reference / shared` schemas; aborts if any collision. Test in CI per-phase. |
waves/B9\plan.md:414:| T22 | Tier A session-size overflow if a misclassified table consumes a full session — ADVERSARIAL A1 | MED | MED | Per-table escape-hatch: > 1h solo → reclassify to Tier B/C, remove from `0009`, update FDW ladder; > 20% session burn → trigger mini-replan; charter W1 budget can flex with W2 buffer if needed |
waves/B9\plan.md:415:| T23 | 113-table migration failure has large debug blast radius — ADVERSARIAL A2 | LOW | MED | Each migration captures `alembic upgrade + downgrade + upgrade` on a disposable DB before commit; evidence file required at mini-GATE-CLOSE; failed migration auto-flagged for codex review |
waves/B9\plan.md:416:| T24 | `setup_fdw.sh --verify` hard-codes "expected 66"; B9.B verify fails without script change — ADVERSARIAL A3 | LOW | MED | B9.A C11 replaces hard-coded count with manifest-derived; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is source of truth |
waves/B9\plan.md:417:| T25 | RNDC14 2-session budget insufficient if column review surfaces multiple issues — ADVERSARIAL A6 | MED | MED | B9.E iteration allowance: 2 → up to 4 sessions without borrowing from B9.F; mini-GATE-CLOSE will not close on partial review |
waves/B9\plan.md:418:| T26 | 4-5 month wave freezes visible delivery; overruns invisible — ADVERSARIAL A9 | MED | MED | 4-week calendar checkpoint at weeks 4/8/12; intermediate milestone tags (B9.B-shipped, B9.C-shipped) under single B9 label; owner reviews scope/split decision at each checkpoint |
waves/B9\plan.md:420:| T28 | Existing Phase 09 coverage breaks due to registry expansion or migration interaction — ADVERSARIAL A12 | LOW | MED | B9.A C12 captures Phase 09 baseline: RNP3/RPRDPTD0/RNPTYPD0 row counts + query latency + default-mode behavior; per-phase mini-GATE-CLOSE re-asserts unchanged |
waves/B9\plan.md:421:| T29 | Flaky test noise drowns real signal in 134-failure baseline — ADVERSARIAL A13 | MED | MED | B9.A C0 captures node-ID snapshots × 2 runs (NOT raw counts); known flakes quarantined in `waves/B9/test_flake_quarantine.md`; mini-GATE-CLOSE asserts node-ID delta, not count delta |
waves/B9\plan.md:423:| T31 | `expected_reference_tables.txt` `>0 rows` policy contradicts schema-only MTL — ADVERSARIAL N2 | LOW | LOW | Resolved by T16 (MTL not in default FDW). Document policy explicitly in manifest file header. |
waves/B9\plan.md:435:| PLAN R2 | B9.A | Plan v2 with R1 fixes; verify | `codex-plan-consult-r2.md` — GO-WITH-FIXES → charter v3.1 erratum → PLAN GATE FINAL GO |
waves/B9\plan.md:437:| **ADVERSARIAL R2** | **B9.A** | **Plan v3 with R1 mitigations absorbed; verify** | **`codex-adversarial-r2.md` — pending** |
waves/B9\plan.md:438:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
waves/B9\plan.md:439:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\plan.md:440:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
waves/B9\plan.md:441:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9\plan.md:442:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9\plan.md:443:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9\plan.md:446:**Total codex consults projected:** 13 (2 SPEC + 2 PLAN + 2 ADVERSARIAL + 6 mini-GATE-CLOSE + 1 final GATE-CLOSE = 13). Token spend through ADVERSARIAL R1: ~280k. Remaining gate consults: ~50-80k for ADVERSARIAL R2 + ~300k for 6 mini-GATE-CLOSEs + ~40k for final = ~390-420k more codex tokens.
waves/B9\plan.md:466:1. **FDW final count: 283 vs 284** → **RESOLVED in PLAN v2: 283** (arithmetic) → **SUPERSEDED in PLAN v3 by ADVERSARIAL A8: 264 default, 283 conditional.** Tier C arithmetic bug (`19 - 3 = 16, not 17`) cascaded to 284; v2 corrected to 283; v3 changed final default to 264 (MTL excluded from default FDW per charter v3.2). Final ladder: 66 → 179 → 245 → 261 → 262 → 264 default; 283 ONLY when `fdb_load_mtl=True` in a future MTL activation wave.
waves/B9\plan.md:467:2. **Migration count: 5 vs 6 vs 9-10** → **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.
waves/B9\plan.md:468:3. **Loader-orchestration modes: existing vs new** → **RESOLVED:** existing `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, `fdb_rebase`. B9.A C4 does NOT need to add `fdb_weekly`. It may need to add tier-specific modes (`fdb_tier_a`, `fdb_tier_b`, `fdb_mtl_data`) if per-tier loaders are desired; PLAN v2 leaves that as a B9.A C1 design decision (additive to existing modes).
waves/B9\plan.md:474:- **Charter §Workstreams view (39 sessions):** counts only productive ingest work — W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\plan.md:486:- At each mini-GATE-CLOSE: full sign-off sheet committed
waves/B9\phase09_compat_baseline.md:8:This file LOCKS the Phase 09 row counts + query latency that every
waves/B9\phase09_compat_baseline.md:9:B9.B-G mini-GATE-CLOSE asserts unchanged (within documented tolerance).
waves/B9\phase09_compat_baseline.md:26:ledger; mini-GATE-CLOSE asserts row count **>= baseline** and that
waves/B9\phase09_compat_baseline.md:55:0 net new rows. Mini-GATE-CLOSE for B9.B-G re-runs this and asserts
waves/B9\phase09_compat_baseline.md:58:## How mini-GATE-CLOSE re-asserts this
waves/B9\phase09_compat_baseline.md:60:Each B9.B-G phase close runs:
waves/B9\phase09_compat_baseline.md:73:Outputs are diffed against this file. Any drift fails the mini-GATE.
waves/B9\phase09_compat_baseline.md:80:   `fdb_ndc_price_history` row count and the delta ledger entry.
waves/B9\phase09_compat_baseline.md:86:   The new row count IS the new baseline; this file is updated in
waves/B9\phase09_compat_baseline.md:92:(added by B9.A C12) re-asserts the row counts against a live Postgres
waves/B9\codex-gate-close-r1-result.md:14:# Codex B9.A mini-GATE-CLOSE R1 — Consult Prompt
waves/B9\codex-gate-close-r1-result.md:24:B9.A laid the cross-cutting infrastructure that B9.B-G (113+66+16+1+2+19
waves/B9\codex-gate-close-r1-result.md:27:makes B9.B-G's per-table work mechanical and gate-able.
waves/B9\codex-gate-close-r1-result.md:39:c03e37a B9.A C10: FDW name-collision preflight script + test seam
waves/B9\codex-gate-close-r1-result.md:95:any SC by itself — it readies the scaffolding so B9.B-G can close
waves/B9\codex-gate-close-r1-result.md:112:   that a B9.B per-table test cannot accidentally bypass it?
waves/B9\codex-gate-close-r1-result.md:128:   modes use the legacy chain). B9.B-G tier loaders, when built,
waves/B9\codex-gate-close-r1-result.md:137:   clear enough that a B9.B operator cannot quietly extend the
waves/B9\codex-gate-close-r1-result.md:142:   The intent is to force the refactor decision when B9.B's first
waves/B9\codex-gate-close-r1-result.md:156:- **GO** — B9.A closes; B9.B opens.
waves/B9\codex-gate-close-r1-result.md:197: M infrastructure/scripts/verify_backup.py
waves/B9\codex-gate-close-r1-result.md:230: M modules/core-platform/src/jobs/verify_audit_chain_job.py
waves/B9\codex-gate-close-r1-result.md:778:c03e37a B9.A C10: FDW name-collision preflight script + test seam
waves/B9\codex-gate-close-r1-result.md:832:modules\drug-database\tests\unit\test_gen_fdb_tier_migration.py:79:        loader_group="fdb_tier_a",
waves/B9\codex-gate-close-r1-result.md:861:modules\drug-database\tests\unit\test_fdb_loader_registry.py:56:    loader_group="fdb_tier_a",
waves/B9\codex-gate-close-r1-result.md:909:modules\drug-database\tests\unit\test_fdb_adapter.py:604:        loader_group="fdb_tier_a",
waves/B9\codex-gate-close-r1-result.md:910:modules\drug-database\tests\unit\test_fdb_adapter.py:609:    assert spec.loader_group == "fdb_tier_a"
waves/B9\codex-gate-close-r1-result.md:1025:Every B9 phase (B9.B Tier A, B9.C Tier B, B9.D Tier C, B9.E RNDC14,
waves/B9\codex-gate-close-r1-result.md:1216:    T1 mitigation: text-heavy Tier A/B tables ship operator-entered
waves/B9\codex-gate-close-r1-result.md:1384:    Sample-bounded: probes first `sample_rows` lines. For Tier A
waves/B9\codex-gate-close-r1-result.md:1431:#   * returns (current row count, current row state for the target key)
waves/B9\codex-gate-close-r1-result.md:1573:"""B9.A C10 â€” FDW name-collision preflight.
waves/B9\codex-gate-close-r1-result.md:1578:B9.B before a single migration runs.
waves/B9\codex-gate-close-r1-result.md:1580:Why this exists: B9.B-G land alembic migrations into the
waves/B9\codex-gate-close-r1-result.md:1583:name matches a B9 table, the migration succeeds but the FDW exposure
waves/B9\codex-gate-close-r1-result.md:1592:    created by a prior B9.B-G migration (alembic_version proves it).
waves/B9\codex-gate-close-r1-result.md:1607:    2  collisions found â€” operator MUST resolve before B9.B
waves/B9\codex-gate-close-r1-result.md:1685:    "reference",  # FDW-fronted; conflicts produce silent wrong-data
waves/B9\codex-gate-close-r1-result.md:1765:        "# B9.A C10 â€” FDW Name-Collision Preflight Evidence",
waves/B9\codex-gate-close-r1-result.md:1773:        lines.append("## Hard collisions â€” MUST resolve before B9.B")
waves/B9\codex-gate-close-r1-result.md:1795:        lines.append("**No collisions found.** B9.B clear to proceed.")
waves/B9\codex-gate-close-r1-result.md:1836:            "verify the FDB drop is on disk.",
waves/B9\codex-gate-close-r1-result.md:1897:    writes Tier A FDB tables into `infinityrx_dev`. They show up in
waves/B9\codex-gate-close-r1-result.md:1898:    the application schema instead of the FDW-fronted reference DB.
waves/B9\codex-gate-close-r1-result.md:2012:# setup_fdw.sh â€” Wave B7 (Phase 11A) FDW configuration.
waves/B9\codex-gate-close-r1-result.md:2016:#   2. Idempotently create FDW server pointing at infinityrx_reference
waves/B9\codex-gate-close-r1-result.md:2029:#              (FDW drift mitigation; uses LIMIT TO clause)
waves/B9\codex-gate-close-r1-result.md:2080:    --verify)  MODE="verify"; shift ;;
waves/B9\codex-gate-close-r1-result.md:2100:# â”€â”€ --verify mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
waves/B9\codex-gate-close-r1-result.md:2102:# foreign table is queryable via FDW in each target env DB.
waves/B9\codex-gate-close-r1-result.md:2104:# PASS = query exits 0 (empty result is fine â€” FDW link is the contract).
waves/B9\codex-gate-close-r1-result.md:2109:# As B9.B-G grow the manifest 66 â†’ 264, the verify step grows with it â€”
waves/B9\codex-gate-close-r1-result.md:2114:if [ "$MODE" = "verify" ]; then
waves/B9\codex-gate-close-r1-result.md:2136:  # Floor â€” manifest must not shrink below the B7 baseline. As B9.B-G
waves/B9\codex-gate-close-r1-result.md:2154:    echo "â”€â”€ Verifying FDW foreign tables in ${env_db} â”€â”€"
waves/B9\codex-gate-close-r1-result.md:2178:  echo "  setup_fdw.sh --verify complete"
waves/B9\codex-gate-close-r1-result.md:2189:# â”€â”€ end --verify â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
waves/B9\codex-gate-close-r1-result.md:2201:# Schemas that exist in reference DB but should NOT be FDW-imported.
waves/B9\codex-gate-close-r1-result.md:2205:# local to the reference DB and don't transfer through FDW. Reference
waves/B9\codex-gate-close-r1-result.md:2245:  echo "â”€â”€ Setting up FDW in infinityrx_${env} â”€â”€"
waves/B9\codex-gate-close-r1-result.md:2247:  # Use superuser for FDW setup â€” CREATE EXTENSION requires it, and
waves/B9\codex-gate-close-r1-result.md:2261:  # Use the docker service name 'postgres' as the FDW host since the
waves/B9\codex-gate-close-r1-result.md:2265:  FDW_HOST="${FDW_HOST:-postgres}"
waves/B9\codex-gate-close-r1-result.md:2272:          OPTIONS (host '$FDW_HOST', port '5432', dbname 'infinityrx_reference');
waves/B9\codex-gate-close-r1-result.md:2279:      OPTIONS (SET host '$FDW_HOST', SET port '5432', SET dbname 'infinityrx_reference')"
waves/B9\codex-gate-close-r1-result.md:2363:  echo "  OK â€” FDW configured in infinityrx_${env}"
waves/B9\codex-gate-close-r1-result.md:2375:Captures the Phase 09 baseline (9 tables on DrugBase.metadata). B9.B's
waves/B9\codex-gate-close-r1-result.md:2386:# Phase 09 baseline. When B9.B-G land FDB models, this number changes:
waves/B9\codex-gate-close-r1-result.md:2404:        f"{PHASE_09_DRUGBASE_TABLE_COUNT}. If a B9.B-G commit added "
waves/B9\codex-gate-close-r1-result.md:2590:Most of the targeted code looks intentionally conservative. One mismatch already surfaced: the prompt lists `waves/B9/...` artifacts, but those paths are not present in this checkout, so I’ll verify whether they exist under a different root or only in the commits/artifact system.
waves/B9\codex-gate-close-r1-result.md:2646:that every B9.B-G phase reuses. These tests cover the helpers
waves/B9\codex-gate-close-r1-result.md:2648:surface BEFORE B9.B starts wiring 113 Tier A tables through it.
waves/B9\codex-gate-close-r1-result.md:3205:  * APPEND_ONLY history table                  â†’ PASS (row count grows)
waves/B9\codex-gate-close-r1-result.md:3585:226:                          (e.g., "fdb_tier_a" — loaders register by group).
waves/B9\codex-gate-close-r1-result.md:3721:56:    loader_group="fdb_tier_a",
waves/B9\codex-gate-close-r1-result.md:3776:154-    """only_groups=['fdb_tier_a'] → only Tier A specs returned."""
waves/B9\codex-gate-close-r1-result.md:3778:156:        _ALL_SPECS, fdb_load_mtl=False, only_groups=["fdb_tier_a"]
waves/B9\codex-gate-close-r1-result.md:3827:219-    B9.B-F: still trivially true (no MTL specs registered).
waves/B9\codex-gate-close-r1-result.md:3871:113-    "reference",  # FDW-fronted; conflicts produce silent wrong-data
waves/B9\codex-gate-close-r1-result.md:3953:"""B9.A C10 â€” Tests for the FDW name-collision preflight.
waves/B9\codex-gate-close-r1-result.md:3957:B9.B integration when a live reference DB is available.
waves/B9\codex-gate-close-r1-result.md:4129:    assert "B9.B clear to proceed" in body
waves/B9\codex-gate-close-r1-result.md:4152:"""B9.A C11 â€” Tests for `setup_fdw.sh --verify` manifest invariants.
waves/B9\codex-gate-close-r1-result.md:4154:The bulk of `setup_fdw.sh` requires a live Postgres + FDW
waves/B9\codex-gate-close-r1-result.md:4169:_SETUP_FDW = _REPO_ROOT / "infrastructure" / "scripts" / "setup_fdw.sh"
waves/B9\codex-gate-close-r1-result.md:4173:    """Same logic as the awk pass in setup_fdw.sh --verify."""
waves/B9\codex-gate-close-r1-result.md:4207:    """B9.A C11 floor: 66 (B7 baseline). B9.B-G grows it; never shrinks."""
waves/B9\codex-gate-close-r1-result.md:4242:    """Duplicates would inflate the verify count and hide failures."""
waves/B9\codex-gate-close-r1-result.md:4260:    body = _SETUP_FDW.read_text(encoding="utf-8")
waves/B9\codex-gate-close-r1-result.md:4271:    body = _SETUP_FDW.read_text(encoding="utf-8")
waves/B9\codex-gate-close-r1-result.md:4278:    body = _SETUP_FDW.read_text(encoding="utf-8")
waves/B9\codex-gate-close-r1-result.md:4370:    loader_group="fdb_tier_a",
waves/B9\codex-gate-close-r1-result.md:4468:    """only_groups=['fdb_tier_a'] â†’ only Tier A specs returned."""
waves/B9\codex-gate-close-r1-result.md:4470:        _ALL_SPECS, fdb_load_mtl=False, only_groups=["fdb_tier_a"]
waves/B9\codex-gate-close-r1-result.md:4533:    B9.B-F: still trivially true (no MTL specs registered).
waves/B9\codex-gate-close-r1-result.md:4590:| MEDIUM | Delta contract coverage | [assert_delta_semantics_acd_cycle](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/tests/_fdb_contract.py:416>) is tight for `UPSERT_BY_NATURAL_KEY` and catches the `DO NOTHING` regression. The remaining bypass risk is omission: a B9.B table can land without a per-table contract invoking it. | In B9.B, add a registry-vs-contract coverage test proving every new non-`UNKNOWN`/non-`TRUNCATE_RELOAD` `TableSpec` is represented in the delta contract suite. |
waves/B9\codex-gate-close-r1-result.md:4612:| MEDIUM | Delta contract coverage | [assert_delta_semantics_acd_cycle](</c/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/tests/_fdb_contract.py:416>) is tight for `UPSERT_BY_NATURAL_KEY` and catches the `DO NOTHING` regression. The remaining bypass risk is omission: a B9.B table can land without a per-table contract invoking it. | In B9.B, add a registry-vs-contract coverage test proving every new non-`UNKNOWN`/non-`TRUNCATE_RELOAD` `TableSpec` is represented in the delta contract suite. |
waves/B9\module_base_profile.md:9:B9.B-G plan to land **217 new SQLAlchemy models** in
waves/B9\module_base_profile.md:32:| After B9.B (+113 Tier A) | 122 | ~1.5 s |
waves/B9\module_base_profile.md:39:have no need for FDB Tier A lookup models.
waves/B9\module_base_profile.md:52:# (drug_database) for alembic / FDW purposes.
waves/B9\module_base_profile.md:64:# Tests that only need Tier A:
waves/B9\module_base_profile.md:83:"I only need Tier A models" and pay only the Tier A cost. The
waves/B9\module_base_profile.md:106:   B9.B-G's first commit lifts this number IF the new tier was
waves/B9\module_base_profile.md:117:**Trigger:** the first B9.B commit that would push
waves/B9\codex-gate-close-r2-result.md:14:# Codex B9.A mini-GATE-CLOSE R2 — Verification Pass
waves/B9\codex-gate-close-r2-result.md:27:B9.A GATE-CLOSE R1 absorption — HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
waves/B9\codex-gate-close-r2-result.md:78:Explicitly deferred to B9.B per codex's own remediation language:
waves/B9\codex-gate-close-r2-result.md:79:"In B9.B, add a registry-vs-contract coverage test...". Documented
waves/B9\codex-gate-close-r2-result.md:80:as a B9.B pre-opening obligation in `waves/B9/status.md` →
waves/B9\codex-gate-close-r2-result.md:81:"B9.B pre-opening obligation (F4)".
waves/B9\codex-gate-close-r2-result.md:91:## Areas to verify in R2
waves/B9\codex-gate-close-r2-result.md:104:4. **F4 deferral**: is the status-ledger row + B9.B pre-opening
waves/B9\codex-gate-close-r2-result.md:110:GO — B9.A closes; B9.B opens.
waves/B9\codex-gate-close-r2-result.md:118:I’ll verify the absorption against the repository state directly: read the R1 result, inspect commit `33e858b`, check the new template/tests/artifacts, and run focused tests if the read-only sandbox allows execution.
waves/B9\codex-gate-close-r2-result.md:126:33e858b (HEAD -> develop) B9.A GATE-CLOSE R1 absorption — HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
waves/B9\codex-gate-close-r2-result.md:186: M infrastructure/scripts/verify_backup.py
waves/B9\codex-gate-close-r2-result.md:219: M modules/core-platform/src/jobs/verify_audit_chain_job.py
waves/B9\codex-gate-close-r2-result.md:772:The checkout has a very dirty tree, but `33e858b` is at `HEAD -> develop`, so I’m treating unrelated unstaged/untracked work as out of scope. The R1 result file named in the prompt is not present at `waves/B9/codex-gate-close-r1-result.md`; I’ll rely on the prompt’s R1 summary and verify the actual R2 artifacts.
waves/B9\codex-gate-close-r2-result.md:1049:that every B9.B-G phase reuses. These tests cover the helpers
waves/B9\codex-gate-close-r2-result.md:1051:surface BEFORE B9.B starts wiring 113 Tier A tables through it.
waves/B9\codex-gate-close-r2-result.md:1606:    """B9.A C3 ships the file empty. B9.B+ may add signed-off entries."""
waves/B9\codex-gate-close-r2-result.md:1654:    """Empty initial file MUST exist â€” every B9.B+ wave ships it."""
waves/B9\codex-gate-close-r2-result.md:1663:Every B9 phase (B9.B Tier A, B9.C Tier B, B9.D Tier C, B9.E RNDC14,
waves/B9\codex-gate-close-r2-result.md:1865:    T1 mitigation: text-heavy Tier A/B tables ship operator-entered
waves/B9\codex-gate-close-r2-result.md:1998:        FileNotFoundError: artifact missing â€” every B9.B+ wave must
waves/B9\codex-gate-close-r2-result.md:2089:    Sample-bounded: probes first `sample_rows` lines. For Tier A
waves/B9\codex-gate-close-r2-result.md:2136:#   * returns (current row count, current row state for the target key)
waves/B9\codex-gate-close-r2-result.md:2313:| B9.B | Tier A â€” 113 simple lookups | NOT STARTED | â€” | Blocked on B9.A gate-close |
waves/B9\codex-gate-close-r2-result.md:2314:| B9.C | Tier B â€” 66 NDC/GCN joins | NOT STARTED | â€” | Blocked on B9.B |
waves/B9\codex-gate-close-r2-result.md:2337:| C10 | FDW name-collision preflight script | `c03e37a` | 16 (107) |
waves/B9\codex-gate-close-r2-result.md:2362:| MEDIUM | Delta-contract bypass risk (B9.B-G omitted from contract) | **F4 â€” deferred to B9.B opening.** Codex's own suggested fix specifies: "In B9.B, add a registry-vs-contract coverage test proving every new non-UNKNOWN/non-TRUNCATE_RELOAD TableSpec is represented in the delta contract suite." This is a B9.B C1-class commit. |
waves/B9\codex-gate-close-r2-result.md:2364:**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
waves/B9\codex-gate-close-r2-result.md:2373:## B9.A mini-GATE-CLOSE checklist (charter SC-9)
waves/B9\codex-gate-close-r2-result.md:2379:- [x] `setup_fdw.sh --verify` still passes (132 PASS, 0 FAIL â€” captured post-B7.3)
waves/B9\codex-gate-close-r2-result.md:2382:- [x] FDW name-collision preflight script in place + 16/16 tests pass
waves/B9\codex-gate-close-r2-result.md:2386:- [ ] Codex B9.A mini-GATE-CLOSE consult dispatched + verdict captured
waves/B9\codex-gate-close-r2-result.md:2397:| SC-1 | 217 tables have models + migrations + ingester | **+0** (B9.B-G lands actual tables) |
waves/B9\codex-gate-close-r2-result.md:2398:| SC-2 | RECORD_COUNTS reconciliation (within Â±0.1%) | Contract template ready (C3); per-table assertions land B9.B+ |
waves/B9\codex-gate-close-r2-result.md:2399:| SC-3 | DELTA_SEMANTICS per table | Enum + contract (C1+C3+C8) ready; per-table assignment B9.B+ |
waves/B9\codex-gate-close-r2-result.md:2400:| SC-4 | Phase 09 untouched (row counts, query latency) | Baseline locked (C12); test runs every gate |
waves/B9\codex-gate-close-r2-result.md:2402:| SC-6 | FDW verify count grows additively | Manifest-derived count (C11) ready; floor 66 |
waves/B9\codex-gate-close-r2-result.md:2405:| SC-9 | Per-phase mini-GATE-CLOSE | This file is the ledger; per-phase entries appear B9.B+ |
waves/B9\codex-gate-close-r2-result.md:2406:| SC-10 | MTL excluded from default load + FDW | Config flag + registry + REVOKE template (C4) ready |
waves/B9\codex-gate-close-r2-result.md:2430:* At every mini-GATE-CLOSE â€” append the per-phase evidence section.
waves/B9\codex-gate-close-r2-result.md:2441:**Audit gate:** every B9.B-G mini-GATE-CLOSE re-reads this file; any
waves/B9\codex-gate-close-r2-result.md:2512:This file LOCKS the Phase 09 row counts + query latency that every
waves/B9\codex-gate-close-r2-result.md:2513:B9.B-G mini-GATE-CLOSE asserts unchanged (within documented tolerance).
waves/B9\codex-gate-close-r2-result.md:2530:ledger; mini-GATE-CLOSE asserts row count **>= baseline** and that
waves/B9\codex-gate-close-r2-result.md:2559:0 net new rows. Mini-GATE-CLOSE for B9.B-G re-runs this and asserts
waves/B9\codex-gate-close-r2-result.md:2562:## How mini-GATE-CLOSE re-asserts this
waves/B9\codex-gate-close-r2-result.md:2564:Each B9.B-G phase close runs:
waves/B9\codex-gate-close-r2-result.md:2577:Outputs are diffed against this file. Any drift fails the mini-GATE.
waves/B9\codex-gate-close-r2-result.md:2584:   `fdb_ndc_price_history` row count and the delta ledger entry.
waves/B9\codex-gate-close-r2-result.md:2590:   The new row count IS the new baseline; this file is updated in
waves/B9\codex-gate-close-r2-result.md:2596:(added by B9.A C12) re-asserts the row counts against a live Postgres
waves/B9\codex-gate-close-r2-result.md:2611:B9 FDB loaders write reference tables (Tier A/B/C/RNDC14/pricing/MTL)
waves/B9\codex-gate-close-r2-result.md:2649:python scripts/load_fdb.py --mode fdb_tier_a --require-reference-db
waves/B9\codex-gate-close-r2-result.md:2652:The `--require-reference-db` flag is set automatically by every B9.B-G
waves/B9\codex-gate-close-r2-result.md:2691:B9.B-G plan to land **217 new SQLAlchemy models** in
waves/B9\codex-gate-close-r2-result.md:2714:| After B9.B (+113 Tier A) | 122 | ~1.5 s |
waves/B9\codex-gate-close-r2-result.md:2721:have no need for FDB Tier A lookup models.
waves/B9\codex-gate-close-r2-result.md:2734:# (drug_database) for alembic / FDW purposes.
waves/B9\codex-gate-close-r2-result.md:2746:# Tests that only need Tier A:
waves/B9\codex-gate-close-r2-result.md:2765:"I only need Tier A models" and pay only the Tier A cost. The
waves/B9\codex-gate-close-r2-result.md:2788:   B9.B-G's first commit lifts this number IF the new tier was
waves/B9\codex-gate-close-r2-result.md:2799:**Trigger:** the first B9.B commit that would push
waves/B9\codex-gate-close-r2-result.md:2810:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\\.{{MTL_TABLES}}\" waves/B9 infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl modules/drug-database/tests" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-gate-close-r2-result.md:2826:    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
waves/B9\codex-gate-close-r2-result.md:2834:    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
waves/B9\codex-gate-close-r2-result.md:2898:waves/B9\codex-gate-close-r2-result.md:772:The checkout has a very dirty tree, but `33e858b` is at `HEAD -> develop`, so I’m treating unrelated unstaged/untracked work as out of scope. The R1 result file named in the prompt is not present at `waves/B9/codex-gate-close-r1-result.md`; I’ll rely on the prompt’s R1 summary and verify the actual R2 artifacts.
waves/B9\codex-gate-close-r2-result.md:2913:F4 deferral is acceptable. I would not add an `xfail` stub in B9.A; the status-ledger pre-opening obligation is explicit enough, assuming B9.B treats it as a first commit gate.
waves/B9\codex-gate-close-r2-result.md:2928:F4 deferral is acceptable. I would not add an `xfail` stub in B9.A; the status-ledger pre-opening obligation is explicit enough, assuming B9.B treats it as a first commit gate.
waves/B9\codex-plan-consult-r2.md:22:| F1 | Correct Tier C non-special count to **16** (not 17). Cascade into all FDW counts and cum totals. |
waves/B9\codex-plan-consult-r2.md:23:| F2 | Reconcile all FDW counts to **283** final (charter SC-6). Correct ladder: 66 → 179 → 245 → 261 → 262 → 264 → 283. |
waves/B9\codex-plan-consult-r2.md:33:Plan v2 (this revision) claims to absorb all of these. Your job in R2 is to verify each fix.
waves/B9\codex-plan-consult-r2.md:54:| F2 | FDW ladder to 283 | YES / PARTIAL / NO | <line refs> | |
waves/B9\codex-plan-consult-r2.md:66:| C1 | Per-phase mini-GATE-CLOSE rows match charter v3 phase table | YES / NO |
waves/B9\codex-plan-consult-r2.md:89:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'; Select-String -Path "'$p -Pattern '"'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-plan-consult-r2.md:91:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; Select-String -Path "'$p -Pattern '"'220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-plan-consult-r2.md:97:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'; Select-String -Path "'$p -Pattern '"'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
waves/B9\codex-plan-consult-r2.md:98:2026-05-11T19:26:56.678129Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'; Select-String -Path "'$p -Pattern '"'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
waves/B9\codex-plan-consult-r2.md:99:2026-05-11T19:26:56.678690Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; Select-String -Path "'$p -Pattern '"'220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
waves/B9\codex-plan-consult-r2.md:101:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$p='"'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'; Select-String -Path "'$p -Pattern '"'220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
waves/B9\codex-plan-consult-r2.md:155:2026-05-11T19:27:12.734157Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\plan.md -Pattern 'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
waves/B9\codex-plan-consult-r2.md:157:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\plan.md -Pattern 'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
waves/B9\codex-plan-consult-r2.md:163:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\recon.md -Pattern '220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
waves/B9\codex-plan-consult-r2.md:165:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\plan.md -Pattern 'Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
waves/B9\codex-plan-consult-r2.md:171:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\recon.md -Pattern '220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
waves/B9\codex-plan-consult-r2.md:174:2026-05-11T19:27:12.736964Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path .\\recon.md -Pattern '220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D' | ForEach-Object { \"{0}:{1}\" -f "'$_.LineNumber,$_.Line }'` rejected: blocked by policy
waves/B9\codex-plan-consult-r2.md:178:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "Tier C|283|66|179|245|261|262|264|migration|part1|part2|part3|fdb_weekly|loader|T12|weekly|TRUNCATE|INSERT|42|39|pg_class|collect-only|pytest|failure|D2|SC-4|SC-5|MTL|mini-GATE|GATE-CLOSE|SC-1|SC-11" plan.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
waves/B9\codex-plan-consult-r2.md:184:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "220|283|Tier C|FDW|source|tables|3 source|2 DB|pg_class|vendor|UPD|weekly|A/C/D" recon.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
waves/B9\codex-plan-consult-r2.md:186:18:Wave B9 = "FDB NDDF Plus 220-table extension". SPEC v3 is locked (you previously approved at SPEC R2 GO-WITH-FIXES → owner applied the stale-D4-row cleanup → v3 LOCKED). The next gate is PLAN v1. The owner drafted `plan.md` v1 (380 lines). Your job in PLAN R1 is to verify whether the plan is sound, complete, and ready for ADVERSARIAL review + execute, OR whether it needs revision.
waves/B9\codex-plan-consult-r2.md:209:709:Wave B9 = "FDB NDDF Plus 220-table extension". Recon was completed 2026-05-11 (`recon.md`). Charter v1 was dispatched for SPEC R1. You returned **GO-WITH-FIXES** with 6 substantive concerns (1 HIGH effort model, 2 HIGH process gates, 3 MEDIUM SPEC tightenings, 1 LOW vendor-name pass). The owner produced charter v2 which claims to absorb all 6 concerns. Your job in R2 is to verify whether v2 actually addresses each concern, and either issue **GO** (proceed to PLAN), **GO-WITH-FIXES** (one more revision needed), or **NO-GO** (structural problem).
waves/B9\codex-plan-consult-r2.md:224:1250:- **`pytest --collect-only` baseline marker** â€” committed to `waves/B9/baseline.md` at C0; every phase mini-GATE-CLOSE re-runs and asserts count unchanged.
waves/B9\codex-plan-consult-r2.md:232:1535:| T10 | Test count baseline drifts (134 pre-existing failures become 135 or 200) | MED | MED | B9.A C0 captures `pytest --collect-only` count; each phase mini-GATE-CLOSE asserts count unchanged Â± new contract tests |
waves/B9\codex-plan-consult-r2.md:237:1930:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"SC-|R[1-7] \\||T[0-9]+|B9\\.[A-H]|FDW|283|284|fdb_weekly|fdb_initial|001[0-9]|migration|mini-GATE|Goal-backward|Threat model|Pre-execute|D2|MTL|RNP2|RPRDPP0|RNDC14|setup_fdw|collect-only|RECORD_COUNTS|session\" 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-plan-consult-r2.md:239:1963:63:- **`pytest --collect-only` baseline marker** — committed to `waves/B9/baseline.md` at C0; every phase mini-GATE-CLOSE re-runs and asserts count unchanged.
waves/B9\codex-plan-consult-r2.md:246:2090:348:| T10 | Test count baseline drifts (134 pre-existing failures become 135 or 200) | MED | MED | B9.A C0 captures `pytest --collect-only` count; each phase mini-GATE-CLOSE asserts count unchanged ± new contract tests |
waves/B9\codex-plan-consult-r2.md:290:5011:| 7 | Pre-execute invariants testable | YES | Invariants have concrete checks: commit/memory references, FDW verify, `df -h`, config flag location, `pytest --collect-only`, manifest parse, consult slots (`plan.md:30-44`). |
waves/B9\codex-plan-consult-r2.md:293:5044:GO-WITH-FIXES. Produce PLAN v2 before ADVERSARIAL: correct Tier C non-special count to 16, reconcile all FDW/SC-1 counts to 283 final FDW entries, lock migrations to the 6 SPEC-approved files, fix the loader-mode erratum, add a real weekly-delta schema/UPD-format guard, and explain the 42-vs-39 session delta or reduce the plan back to the charter budget.
waves/B9\codex-plan-consult-r2.md:296:5061:| 7 | Pre-execute invariants testable | YES | Invariants have concrete checks: commit/memory references, FDW verify, `df -h`, config flag location, `pytest --collect-only`, manifest parse, consult slots (`plan.md:30-44`). |
waves/B9\codex-plan-consult-r2.md:299:5094:GO-WITH-FIXES. Produce PLAN v2 before ADVERSARIAL: correct Tier C non-special count to 16, reconcile all FDW/SC-1 counts to 283 final FDW entries, lock migrations to the 6 SPEC-approved files, fix the loader-mode erratum, add a real weekly-delta schema/UPD-format guard, and explain the 42-vs-39 session delta or reduce the plan back to the charter budget.
waves/B9\codex-plan-consult-r2.md:302:3:**Status:** PLAN v2 DRAFT — codex PLAN R1 GO-WITH-FIXES absorbed (Tier C 17→16, FDW ladder reconciled to 283, migration shape locked to 6 files, loader-mode erratum corrected, T12 schema-drift threat added, pytest baseline clarified, effort math reconciled). Pending codex PLAN R2 verification + codex ADVERSARIAL consult.
waves/B9\codex-plan-consult-r2.md:306:19:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9\codex-plan-consult-r2.md:307:24:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-plan-consult-r2.md:308:35:2. **B7.2 Phase 11A COMPLETE** — `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
waves/B9\codex-plan-consult-r2.md:310:39:6. **134 pre-existing test failures baseline frozen** — at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged ± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
waves/B9\codex-plan-consult-r2.md:311:50:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
waves/B9\codex-plan-consult-r2.md:315:62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-plan-consult-r2.md:316:63:- **pytest baseline markers** — committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
waves/B9\codex-plan-consult-r2.md:317:69:| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
waves/B9\codex-plan-consult-r2.md:320:78:**B9.A mini-GATE-CLOSE criteria (charter SC-9):**
waves/B9\codex-plan-consult-r2.md:323:82:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
waves/B9\codex-plan-consult-r2.md:324:95:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon §4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
waves/B9\codex-plan-consult-r2.md:326:103:- 1 alembic migration (`0009_fdb_tier_a.py`)
waves/B9\codex-plan-consult-r2.md:329:112:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
waves/B9\codex-plan-consult-r2.md:330:113:- SC-7 (weekly idempotency) — verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9\codex-plan-consult-r2.md:331:115:- SC-9 (mini-GATE-CLOSE) — see below
waves/B9\codex-plan-consult-r2.md:332:117:**B9.B mini-GATE-CLOSE criteria:**
waves/B9\codex-plan-consult-r2.md:333:120:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9\codex-plan-consult-r2.md:335:126:- Codex mini-GATE-CLOSE consult: GO
waves/B9\codex-plan-consult-r2.md:342:150:- FDW foreign-table count: 179 → 245
waves/B9\codex-plan-consult-r2.md:344:154:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-plan-consult-r2.md:350:175:- FDW foreign-table count: 245 → **261**
waves/B9\codex-plan-consult-r2.md:353:180:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
waves/B9\codex-plan-consult-r2.md:355:188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-plan-consult-r2.md:358:201:- FDW foreign-table count: 261 → 262
waves/B9\codex-plan-consult-r2.md:360:205:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
waves/B9\codex-plan-consult-r2.md:363:218:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline
waves/B9\codex-plan-consult-r2.md:366:227:- FDW foreign-table count: 262 → 264
waves/B9\codex-plan-consult-r2.md:368:231:**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4:**
waves/B9\codex-plan-consult-r2.md:369:238:- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps
waves/B9\codex-plan-consult-r2.md:378:261:- FDW foreign-table count: 264 → **283** (MTL tables ARE in FDW even though data isn't loaded — they exist as foreign-table entries pointing at empty reference tables)
waves/B9\codex-plan-consult-r2.md:379:263:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
waves/B9\codex-plan-consult-r2.md:381:267:**B9.G mini-GATE-CLOSE criteria:**
waves/B9\codex-plan-consult-r2.md:382:272:- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)
waves/B9\codex-plan-consult-r2.md:383:278:**Scope:** Reconcile `infrastructure/scripts/lib/expected_reference_tables.txt` to the true final count, run final FDW verify, produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
waves/B9\codex-plan-consult-r2.md:385:283:- Session 2: Final `setup_fdw.sh --verify` **283/283** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables; published in `waves/B9/evidence.md`
waves/B9\codex-plan-consult-r2.md:395:307:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9\codex-plan-consult-r2.md:400:323:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9\codex-plan-consult-r2.md:403:326:| SC-6 | `setup_fdw.sh --verify` output **283/283** in dev + mock (charter-matched) | B9.H Session 2 |
waves/B9\codex-plan-consult-r2.md:406:329:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
waves/B9\codex-plan-consult-r2.md:409:339:| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon §7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
waves/B9\codex-plan-consult-r2.md:410:340:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9\codex-plan-consult-r2.md:411:342:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
waves/B9\codex-plan-consult-r2.md:413:345:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
waves/B9\codex-plan-consult-r2.md:414:346:| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
waves/B9\codex-plan-consult-r2.md:415:347:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
waves/B9\codex-plan-consult-r2.md:416:348:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, ± in-phase contract tests on the collection number. |
waves/B9\codex-plan-consult-r2.md:417:349:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
waves/B9\codex-plan-consult-r2.md:418:350:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
waves/B9\codex-plan-consult-r2.md:419:363:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
waves/B9\codex-plan-consult-r2.md:420:364:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-plan-consult-r2.md:421:365:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
waves/B9\codex-plan-consult-r2.md:422:366:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9\codex-plan-consult-r2.md:423:367:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9\codex-plan-consult-r2.md:424:368:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9\codex-plan-consult-r2.md:426:371:**Total codex consults projected:** 12 (2 SPEC done + PLAN R1 done + PLAN R2 + ADVERSARIAL + 6 mini-GATE-CLOSE + final GATE-CLOSE = 12).
waves/B9\codex-plan-consult-r2.md:429:391:1. **FDW final count: 283 vs 284** → **RESOLVED: 283.** Tier C arithmetic bug (`19 - 3 = 16, not 17`) cascaded to 284. Plan v2 corrects all references: 66 → 179 → 245 → 261 → 262 → 264 → 283.
waves/B9\codex-plan-consult-r2.md:430:393:3. **Loader-orchestration modes: existing vs new** → **RESOLVED:** existing `scripts/load_fdb.py` already declares `fdb_initial`, `fdb_weekly`, `fdb_rebase`. B9.A C4 does NOT need to add `fdb_weekly`. It may need to add tier-specific modes (`fdb_tier_a`, `fdb_tier_b`, `fdb_mtl_data`) if per-tier loaders are desired; PLAN v2 leaves that as a B9.A C1 design decision (additive to existing modes).
waves/B9\codex-plan-consult-r2.md:432:399:- **Charter §Workstreams view (39 sessions):** counts only productive ingest work — W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-plan-consult-r2.md:435:411:- At each mini-GATE-CLOSE: full sign-off sheet committed
waves/B9\codex-plan-consult-r2.md:445:31:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
waves/B9\codex-plan-consult-r2.md:449:44:B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-plan-consult-r2.md:452:49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
waves/B9\codex-plan-consult-r2.md:453:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r2.md:454:51:| B9.D | Tier C non-RNDC14 — 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
waves/B9\codex-plan-consult-r2.md:455:52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** — column-by-column model review |
waves/B9\codex-plan-consult-r2.md:456:53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** — perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-plan-consult-r2.md:457:54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** — integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-plan-consult-r2.md:458:55:| B9.H | Manifest extension (66 → 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** — full cross-tier consult |
waves/B9\codex-plan-consult-r2.md:460:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
waves/B9\codex-plan-consult-r2.md:461:63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-plan-consult-r2.md:462:64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-plan-consult-r2.md:464:66:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
waves/B9\codex-plan-consult-r2.md:466:69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-plan-consult-r2.md:473:78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-plan-consult-r2.md:474:79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-plan-consult-r2.md:485:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-plan-consult-r2.md:486:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
waves/B9\codex-plan-consult-r2.md:499:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-plan-consult-r2.md:500:121:- **Tier A** — Pure reference/description tables. Typically code → description, ≤ 5 columns, < 2 MB uncompressed, name suffix `D0`–`D9` pattern or a small static lookup. No NDC normalization, no join design, no money columns.
waves/B9\codex-plan-consult-r2.md:508:169:| D — Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-plan-consult-r2.md:509:173:- `0009_fdb_tier_a.py` — 113 Tier A tables (all small; one migration is reviewable because models are uniform 2–5-col descriptors)
waves/B9\codex-plan-consult-r2.md:513:180:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
waves/B9\codex-plan-consult-r2.md:515:192:| E — Generic table-driven ingester | Config file (YAML/dict) maps table names → TableSpec; one ingester loops all tables | RECOMMENDED for Tier A and B |
waves/B9\codex-plan-consult-r2.md:517:198:**For Tier A + B (179 tables):**
waves/B9\codex-plan-consult-r2.md:523:223:| Tier A: 113 tables × 20 min | 37.7h |
waves/B9\codex-plan-consult-r2.md:527:228:| FDW manifest expansion (setup_fdw.sh + testing) | 4h |
waves/B9\codex-plan-consult-r2.md:528:236:- B9.1 (Tier A, 113 tables): ~10 sessions
waves/B9\codex-plan-consult-r2.md:531:243:**Realistic wall-clock:** 3–4 months for B9.1 through B9.3. Consider whether B9 is actually two waves (B9 = Tier A+B; B10 = Tier C) for milestone hygiene.
waves/B9\codex-plan-consult-r2.md:534:255:**Risk 3 — FDW LIMIT TO list maintenance drift (MEDIUM)**
waves/B9\codex-plan-consult-r2.md:535:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-plan-consult-r2.md:541:279:- Audit UPD zip structure: verify which tables ship as delta vs. full-replacement
waves/B9\codex-plan-consult-r2.md:542:282:### B9.1 — Tier A: 113 simple lookup tables (target ~10 sessions)
waves/B9\codex-plan-consult-r2.md:544:288:- Integration test: load against real DB zip, verify row counts vs RECORD\_COUNTS.TXT for all 113 tables
waves/B9\codex-plan-consult-r2.md:545:289:- FDW manifest update: add 113 table names to `setup_fdw.sh` LIMIT TO list
waves/B9\codex-plan-consult-r2.md:548:299:- FDW manifest update: +66 entries
waves/B9\codex-plan-consult-r2.md:551:309:- FDW manifest update: +19 entries
waves/B9\codex-plan-consult-r2.md:555:328:4. **Wave boundary — is B9 one wave or two?**: 34 sessions is 3–4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-plan-consult-r2.md:562:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "''^'"\\| B9\\.|mini-GATE-CLOSE|Closure gate|Phase|SC-1|SC-2|SC-3|SC-4|SC-5|SC-6|SC-7|SC-8|SC-9|SC-10|SC-11|0009|0010|0011|0012|0013|0014|part\" plan.md charter.md" in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
waves/B9\codex-plan-consult-r2.md:573:charter.md:44:B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-plan-consult-r2.md:576:charter.md:49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
waves/B9\codex-plan-consult-r2.md:577:charter.md:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r2.md:578:charter.md:51:| B9.D | Tier C non-RNDC14 — 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
waves/B9\codex-plan-consult-r2.md:579:charter.md:52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** — column-by-column model review |
waves/B9\codex-plan-consult-r2.md:580:charter.md:53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** — perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-plan-consult-r2.md:581:charter.md:54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** — integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-plan-consult-r2.md:582:charter.md:55:| B9.H | Manifest extension (66 → 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** — full cross-tier consult |
waves/B9\codex-plan-consult-r2.md:584:charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
waves/B9\codex-plan-consult-r2.md:585:charter.md:63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-plan-consult-r2.md:586:charter.md:64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-plan-consult-r2.md:588:charter.md:66:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
waves/B9\codex-plan-consult-r2.md:591:charter.md:69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-plan-consult-r2.md:594:charter.md:78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-plan-consult-r2.md:595:charter.md:79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-plan-consult-r2.md:596:charter.md:89:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
waves/B9\codex-plan-consult-r2.md:598:charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r2.md:601:plan.md:19:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9\codex-plan-consult-r2.md:602:plan.md:24:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-plan-consult-r2.md:603:plan.md:35:2. **B7.2 Phase 11A COMPLETE** — `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
waves/B9\codex-plan-consult-r2.md:604:plan.md:36:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-plan-consult-r2.md:606:plan.md:39:6. **134 pre-existing test failures baseline frozen** — at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged ± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
waves/B9\codex-plan-consult-r2.md:608:plan.md:50:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
waves/B9\codex-plan-consult-r2.md:609:plan.md:62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-plan-consult-r2.md:610:plan.md:63:- **pytest baseline markers** — committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
waves/B9\codex-plan-consult-r2.md:611:plan.md:78:**B9.A mini-GATE-CLOSE criteria (charter SC-9):**
waves/B9\codex-plan-consult-r2.md:612:plan.md:95:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon §4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
waves/B9\codex-plan-consult-r2.md:614:plan.md:103:- 1 alembic migration (`0009_fdb_tier_a.py`)
waves/B9\codex-plan-consult-r2.md:616:plan.md:111:- SC-2 (RECORD_COUNTS reconciliation) — every loaded Tier A table: actual ÷ expected within ±0.1% tolerance (small lookups should be exact)
waves/B9\codex-plan-consult-r2.md:617:plan.md:112:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
waves/B9\codex-plan-consult-r2.md:618:plan.md:113:- SC-7 (weekly idempotency) — verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9\codex-plan-consult-r2.md:619:plan.md:114:- SC-8 (test strategy) — contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
waves/B9\codex-plan-consult-r2.md:620:plan.md:115:- SC-9 (mini-GATE-CLOSE) — see below
waves/B9\codex-plan-consult-r2.md:621:plan.md:117:**B9.B mini-GATE-CLOSE criteria:**
waves/B9\codex-plan-consult-r2.md:622:plan.md:126:- Codex mini-GATE-CLOSE consult: GO
waves/B9\codex-plan-consult-r2.md:623:plan.md:139:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-plan-consult-r2.md:627:plan.md:154:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-plan-consult-r2.md:631:plan.md:180:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
waves/B9\codex-plan-consult-r2.md:632:plan.md:188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-plan-consult-r2.md:636:plan.md:205:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
waves/B9\codex-plan-consult-r2.md:641:plan.md:231:**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4:**
waves/B9\codex-plan-consult-r2.md:642:plan.md:238:- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps
waves/B9\codex-plan-consult-r2.md:647:plan.md:263:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
waves/B9\codex-plan-consult-r2.md:649:plan.md:267:**B9.G mini-GATE-CLOSE criteria:**
waves/B9\codex-plan-consult-r2.md:651:plan.md:272:- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)
waves/B9\codex-plan-consult-r2.md:659:plan.md:304:- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
waves/B9\codex-plan-consult-r2.md:662:plan.md:307:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9\codex-plan-consult-r2.md:668:plan.md:322:| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
waves/B9\codex-plan-consult-r2.md:669:plan.md:323:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9\codex-plan-consult-r2.md:672:plan.md:326:| SC-6 | `setup_fdw.sh --verify` output **283/283** in dev + mock (charter-matched) | B9.H Session 2 |
waves/B9\codex-plan-consult-r2.md:675:plan.md:329:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
waves/B9\codex-plan-consult-r2.md:678:plan.md:340:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9\codex-plan-consult-r2.md:679:plan.md:342:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
waves/B9\codex-plan-consult-r2.md:680:plan.md:345:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
waves/B9\codex-plan-consult-r2.md:681:plan.md:347:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
waves/B9\codex-plan-consult-r2.md:682:plan.md:348:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, ± in-phase contract tests on the collection number. |
waves/B9\codex-plan-consult-r2.md:683:plan.md:349:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
waves/B9\codex-plan-consult-r2.md:684:plan.md:350:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
waves/B9\codex-plan-consult-r2.md:686:plan.md:363:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
waves/B9\codex-plan-consult-r2.md:687:plan.md:364:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-plan-consult-r2.md:688:plan.md:365:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
waves/B9\codex-plan-consult-r2.md:689:plan.md:366:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9\codex-plan-consult-r2.md:690:plan.md:367:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9\codex-plan-consult-r2.md:691:plan.md:368:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9\codex-plan-consult-r2.md:692:plan.md:371:**Total codex consults projected:** 12 (2 SPEC done + PLAN R1 done + PLAN R2 + ADVERSARIAL + 6 mini-GATE-CLOSE + final GATE-CLOSE = 12).
waves/B9\codex-plan-consult-r2.md:694:plan.md:392:2. **Migration count: 5 vs 6 vs 9-10** → **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.
waves/B9\codex-plan-consult-r2.md:696:plan.md:411:- At each mini-GATE-CLOSE: full sign-off sheet committed
waves/B9\codex-plan-consult-r2.md:703:charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
waves/B9\codex-plan-consult-r2.md:707:plan.md:36:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-plan-consult-r2.md:708:plan.md:40:7. **FDB drop manifest reachable** — `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon §1.5 verified — re-verify at C0).
waves/B9\codex-plan-consult-r2.md:710:plan.md:82:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
waves/B9\codex-plan-consult-r2.md:711:plan.md:90:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier — short tables (mostly < 10K rows, all ≤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
waves/B9\codex-plan-consult-r2.md:714:plan.md:188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-plan-consult-r2.md:717:plan.md:350:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
waves/B9\codex-plan-consult-r2.md:723:recon.md:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
waves/B9\codex-plan-consult-r2.md:747:recon.md:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-plan-consult-r2.md:751:recon.md:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-plan-consult-r2.md:755:recon.md:277:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) — implementation-ready spec
waves/B9\codex-plan-consult-r2.md:758:codex-plan-consult-r1.md:18:Wave B9 = "FDB NDDF Plus 220-table extension". SPEC v3 is locked (you previously approved at SPEC R2 GO-WITH-FIXES → owner applied the stale-D4-row cleanup → v3 LOCKED). The next gate is PLAN v1. The owner drafted `plan.md` v1 (380 lines). Your job in PLAN R1 is to verify whether the plan is sound, complete, and ready for ADVERSARIAL review + execute, OR whether it needs revision.
waves/B9\codex-plan-consult-r2.md:763:codex-plan-consult-r1.md:240:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
waves/B9\codex-plan-consult-r2.md:770:codex-plan-consult-r1.md:709:Wave B9 = "FDB NDDF Plus 220-table extension". Recon was completed 2026-05-11 (`recon.md`). Charter v1 was dispatched for SPEC R1. You returned **GO-WITH-FIXES** with 6 substantive concerns (1 HIGH effort model, 2 HIGH process gates, 3 MEDIUM SPEC tightenings, 1 LOW vendor-name pass). The owner produced charter v2 which claims to absorb all 6 concerns. Your job in R2 is to verify whether v2 actually addresses each concern, and either issue **GO** (proceed to PLAN), **GO-WITH-FIXES** (one more revision needed), or **NO-GO** (structural problem).
waves/B9\codex-plan-consult-r2.md:781:codex-plan-consult-r1.md:888:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Ã‚Â± documented tolerance (MTL excluded Ã¢â‚¬â€ schema-only) |
waves/B9\codex-plan-consult-r2.md:783:codex-plan-consult-r1.md:944:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -i "First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14|100-session|34|39|mini-GATE|GATE-CLOSE|EXPLAIN ANALYZE|bespoke|migration" charter.md codex-spec-consult-r1.md recon.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
waves/B9\codex-plan-consult-r2.md:788:codex-plan-consult-r1.md:966:charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
waves/B9\codex-plan-consult-r2.md:795:codex-plan-consult-r1.md:1029:recon.md:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion â€” this is a one-time setup change, not per-deployment.
waves/B9\codex-plan-consult-r2.md:818:codex-plan-consult-r1.md:1070:recon.md:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-plan-consult-r2.md:822:codex-plan-consult-r1.md:1105:recon.md:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-plan-consult-r2.md:826:codex-plan-consult-r1.md:1111:recon.md:277:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) â€” implementation-ready spec
waves/B9\codex-plan-consult-r2.md:833:codex-plan-consult-r1.md:1223:3. **Reference DB topology stable** â€” `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-plan-consult-r2.md:834:codex-plan-consult-r1.md:1227:7. **FDB drop manifest reachable** â€” `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon Â§1.5 verified â€” re-verify at C0).
waves/B9\codex-plan-consult-r2.md:836:codex-plan-consult-r1.md:1269:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
waves/B9\codex-plan-consult-r2.md:837:codex-plan-consult-r1.md:1277:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier â€” short tables (mostly < 10K rows, all â‰¤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
waves/B9\codex-plan-consult-r2.md:840:codex-plan-consult-r1.md:1375:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" â€” no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-plan-consult-r2.md:844:codex-plan-consult-r1.md:1576:1. **FDW final count: 283 vs 284.** Charter says 283; PLAN's tier-additive derivation gives 284 (66 + 113 + 66 + 17 + 1 + 2 + 19 = 284). The charter figure may have netted the 3 already-covered FDB pricing tables differently. Codex PLAN consult should reconcile before B9.B opens.
waves/B9\codex-plan-consult-r2.md:849:codex-plan-consult-r1.md:1608:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion â€” this is a one-time setup change, not per-deployment.
waves/B9\codex-plan-consult-r2.md:873:codex-plan-consult-r1.md:1707:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-plan-consult-r2.md:877:codex-plan-consult-r1.md:1849:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-plan-consult-r2.md:881:codex-plan-consult-r1.md:1870:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) â€” implementation-ready spec
waves/B9\codex-plan-consult-r2.md:885:codex-plan-consult-r1.md:1949:36:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-plan-consult-r2.md:886:codex-plan-consult-r1.md:1953:40:7. **FDB drop manifest reachable** — `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon §1.5 verified — re-verify at C0).
waves/B9\codex-plan-consult-r2.md:888:codex-plan-consult-r1.md:1971:82:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
waves/B9\codex-plan-consult-r2.md:891:codex-plan-consult-r1.md:2013:188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-plan-consult-r2.md:893:codex-plan-consult-r1.md:2105:389:1. **FDW final count: 283 vs 284.** Charter says 283; PLAN's tier-additive derivation gives 284 (66 + 113 + 66 + 17 + 1 + 2 + 19 = 284). The charter figure may have netted the 3 already-covered FDB pricing tables differently. Codex PLAN consult should reconcile before B9.B opens.
waves/B9\codex-plan-consult-r2.md:898:codex-plan-consult-r1.md:2124:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
waves/B9\codex-plan-consult-r2.md:905:codex-plan-consult-r1.md:2142:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-plan-consult-r2.md:907:codex-plan-consult-r1.md:2177:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-plan-consult-r2.md:913:codex-plan-consult-r1.md:2222:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
waves/B9\codex-plan-consult-r2.md:932:codex-plan-consult-r1.md:5020:| FDW count 283 vs 284 | **283 is right.** Recon: 220 FDB source tables, 3 already covered, 217-table gap (`recon.md:11,99`). FDW baseline has 66 entries and B9 adds 217, so 66 + 217 = 283. Plan’s 284 comes from a Tier C arithmetic bug: “19 except RNDC14/RNP2/RPRDPP0” is 16, not 17 (`plan.md:158-160,263-265`). Correct sequence: 66→179→245→261→262→264→283. | `recon.md:11,14,99,114`; `plan.md:62,158-160,261-265,282-283,389`; `charter.md:55,66`. |
waves/B9\codex-plan-consult-r2.md:934:codex-plan-consult-r1.md:5070:| FDW count 283 vs 284 | **283 is right.** Recon: 220 FDB source tables, 3 already covered, 217-table gap (`recon.md:11,99`). FDW baseline has 66 entries and B9 adds 217, so 66 + 217 = 283. Plan’s 284 comes from a Tier C arithmetic bug: “19 except RNDC14/RNP2/RPRDPP0” is 16, not 17 (`plan.md:158-160,263-265`). Correct sequence: 66→179→245→261→262→264→283. | `recon.md:11,14,99,114`; `plan.md:62,158-160,261-265,282-283,389`; `charter.md:55,66`. |
waves/B9\codex-plan-consult-r2.md:938:95:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon §4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
waves/B9\codex-plan-consult-r2.md:939:103:- 1 alembic migration (`0009_fdb_tier_a.py`)
waves/B9\codex-plan-consult-r2.md:951:392:2. **Migration count: 5 vs 6 vs 9-10** → **RESOLVED: 6.** Charter SPEC-locked the 6 files; v2 removes the part-file alternatives. Locked shape: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` (16 tables), `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`.
waves/B9\codex-plan-consult-r2.md:954:3:**Status:** PLAN v2 DRAFT — codex PLAN R1 GO-WITH-FIXES absorbed (Tier C 17→16, FDW ladder reconciled to 283, migration shape locked to 6 files, loader-mode erratum corrected, T12 schema-drift threat added, pytest baseline clarified, effort math reconciled). Pending codex PLAN R2 verification + codex ADVERSARIAL consult.
waves/B9\codex-plan-consult-r2.md:955:39:6. **134 pre-existing test failures baseline frozen** — at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged ± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
waves/B9\codex-plan-consult-r2.md:956:62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-plan-consult-r2.md:957:63:- **pytest baseline markers** — committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
waves/B9\codex-plan-consult-r2.md:958:69:| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
waves/B9\codex-plan-consult-r2.md:961:139:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-plan-consult-r2.md:962:218:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline
waves/B9\codex-plan-consult-r2.md:964:263:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
waves/B9\codex-plan-consult-r2.md:965:348:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, ± in-phase contract tests on the collection number. |
waves/B9\codex-plan-consult-r2.md:978:| F2 | FDW ladder to 283 | YES | `plan.md:62`, `plan.md:106`, `plan.md:150`, `plan.md:175`, `plan.md:201`, `plan.md:227`, `plan.md:261-263`, `plan.md:282-283`, `plan.md:326`, `plan.md:391` | Ladder is now 66 → 179 → 245 → 261 → 262 → 264 → 283. |
waves/B9\codex-plan-consult-r2.md:990:| C1 | Per-phase mini-GATE-CLOSE rows match charter v3 phase table | NO |
waves/B9\codex-plan-consult-r2.md:1002:- MEDIUM: Charter v3 phase table is now stale against the corrected PLAN v2 arithmetic. `charter.md:51` still says “Tier C non-RNDC14 — 17 complex tables,” while PLAN v2 correctly says 16 at `plan.md:158-160`. `charter.md:49` also still says Tier A closure FDW verify `116/116`, while the corrected ladder requires `179/179` after B9.B (`plan.md:106`, `plan.md:120`). This blocks strict charter-vs-plan consistency, even though PLAN v2’s corrected numbers are right.
waves/B9\codex-plan-consult-r2.md:1006:GO-WITH-FIXES. PLAN v2 verifies all eight R1 fixes, but it cannot proceed to ADVERSARIAL while the locked charter phase table still conflicts with the corrected plan on B9.B FDW count and B9.D Tier C count. Required next change: apply a narrow charter v3 erratum or PLAN v3 consistency note that explicitly supersedes `charter.md:49` to `179/179` and `charter.md:51` to 16 Tier C non-RNDC14 tables, then rerun PLAN R2 or proceed if your governance allows documented charter errata.
waves/B9\codex-plan-consult-r2.md:1018:| F2 | FDW ladder to 283 | YES | `plan.md:62`, `plan.md:106`, `plan.md:150`, `plan.md:175`, `plan.md:201`, `plan.md:227`, `plan.md:261-263`, `plan.md:282-283`, `plan.md:326`, `plan.md:391` | Ladder is now 66 → 179 → 245 → 261 → 262 → 264 → 283. |
waves/B9\codex-plan-consult-r2.md:1030:| C1 | Per-phase mini-GATE-CLOSE rows match charter v3 phase table | NO |
waves/B9\codex-plan-consult-r2.md:1042:- MEDIUM: Charter v3 phase table is now stale against the corrected PLAN v2 arithmetic. `charter.md:51` still says “Tier C non-RNDC14 — 17 complex tables,” while PLAN v2 correctly says 16 at `plan.md:158-160`. `charter.md:49` also still says Tier A closure FDW verify `116/116`, while the corrected ladder requires `179/179` after B9.B (`plan.md:106`, `plan.md:120`). This blocks strict charter-vs-plan consistency, even though PLAN v2’s corrected numbers are right.
waves/B9\codex-plan-consult-r2.md:1046:GO-WITH-FIXES. PLAN v2 verifies all eight R1 fixes, but it cannot proceed to ADVERSARIAL while the locked charter phase table still conflicts with the corrected plan on B9.B FDW count and B9.D Tier C count. Required next change: apply a narrow charter v3 erratum or PLAN v3 consistency note that explicitly supersedes `charter.md:49` to `179/179` and `charter.md:51` to 16 Tier C non-RNDC14 tables, then rerun PLAN R2 or proceed if your governance allows documented charter errata.
waves/B9\codex-plan-consult-r2.md:1047:`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md' -Pattern '116/116','179/179','17 complex','16 complex','FDW ladder','66 baseline','Tier C non-RNDC14'"` rejected: blocked by policy
waves/B9\codex-plan-consult-r2.md:1051:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"116/116|179/179|17 complex|16 complex|FDW ladder|66 baseline|Tier C non-RNDC14\" \"C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-plan-consult-r2.md:1053:3:**Status:** PLAN v2 DRAFT — codex PLAN R1 GO-WITH-FIXES absorbed (Tier C 17→16, FDW ladder reconciled to 283, migration shape locked to 6 files, loader-mode erratum corrected, T12 schema-drift threat added, pytest baseline clarified, effort math reconciled). Pending codex PLAN R2 verification + codex ADVERSARIAL consult.
waves/B9\codex-plan-consult-r2.md:1054:62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder: **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 283 (after B9.G +19 MTL schema-only)**. MTL adds foreign-table entries even though no data lands. B9.H final verify: 283/283 (matches charter SC-6).
waves/B9\codex-plan-consult-r2.md:1055:112:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
waves/B9\codex-plan-consult-r2.md:1056:120:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9\codex-plan-consult-r2.md:1058:263:**FDW count derivation (corrected per codex PLAN R1):** 66 baseline + 113 (B9.B) + 66 (B9.C) + 16 (B9.D — 19 Tier C minus 3 special-handled) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = **283**. Matches charter SC-6.
waves/B9\codex-plan-consult-r2.md:1059:365:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
waves/B9\codex-plan-consult-r2.md:1062:3:**Status:** SPEC v3.1 LOCKED — SPEC v3 + erratum applied after codex PLAN R2 surfaced arithmetic drift between charter and PLAN v2. Erratum: B9.B closure-gate FDW count `116/116` → `179/179`; B9.D scope "17 complex tables" → "16 complex tables" (19 Tier C minus 3 special-handled). No scope change; arithmetic correction only. See `codex-plan-consult-r2.md`. Ready for PLAN v2 → ADVERSARIAL.
waves/B9\codex-plan-consult-r2.md:1063:49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 179/179 + ingester contract tests |
waves/B9\codex-plan-consult-r2.md:1064:51:| B9.D | Tier C non-RNDC14 — 16 complex tables | 4 | **B9.D mini-GATE-CLOSE** (FDW 261/261) |
waves/B9\codex-spec-consult-r1.md:7:extension + FDW verify (66 → 283 entries) + closeout | 5 | Wave SHIPPED |
waves/B9\codex-spec-consult-r1.md:15:`infrastructure/scripts/setup_fdw.sh --verify` 283/283 PASS in both env DBs (current 66/66 + 217 new) |
waves/B9\codex-spec-consult-r1.md:23:(1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual 
waves/B9\codex-spec-consult-r1.md:42:   D4 can remain “single B9 milestone,” but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
waves/B9\codex-spec-consult-r1.md:45:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. “Disk free + pg_stat_user_tables monitoring” is not enough for reversing the Phase 09 1.16 GB deferral.
waves/B9\codex-spec-consult-r1.md:48:   The charter says recon’s 34-session estimate was “Tier A only,” but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
waves/B9\codex-spec-consult-r1.md:70:The charter correctly calls out FDW expansion, weekly idempotency, row-count reconciliation, and the need for restored SPEC/PLAN/ADVERSARIAL discipline.
waves/B9\codex-spec-consult-r1.md:86:   D4 can remain “single B9 milestone,” but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
waves/B9\codex-spec-consult-r1.md:89:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. “Disk free + pg_stat_user_tables monitoring” is not enough for reversing the Phase 09 1.16 GB deferral.
waves/B9\codex-spec-consult-r1.md:92:   The charter says recon’s 34-session estimate was “Tier A only,” but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
waves/B9\codex-spec-consult-r1.md:114:The charter correctly calls out FDW expansion, weekly idempotency, row-count reconciliation, and the need for restored SPEC/PLAN/ADVERSARIAL discipline.
waves/B9\codex-spec-consult-r2.md:18:Wave B9 = "FDB NDDF Plus 220-table extension". Recon was completed 2026-05-11 (`recon.md`). Charter v1 was dispatched for SPEC R1. You returned **GO-WITH-FIXES** with 6 substantive concerns (1 HIGH effort model, 2 HIGH process gates, 3 MEDIUM SPEC tightenings, 1 LOW vendor-name pass). The owner produced charter v2 which claims to absorb all 6 concerns. Your job in R2 is to verify whether v2 actually addresses each concern, and either issue **GO** (proceed to PLAN), **GO-WITH-FIXES** (one more revision needed), or **NO-GO** (structural problem).
waves/B9\codex-spec-consult-r2.md:26:## R1 concerns to verify in v2 (use these as your checklist)
waves/B9\codex-spec-consult-r2.md:30:| 1 | HIGH | Single final GATE-CLOSE too late for 220 tables | Per-phase mini-GATE-CLOSE gates between B9.B..B9.G with explicit closure criteria |
waves/B9\codex-spec-consult-r2.md:156:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~34 four-hour sessions elapsed; ~6 months wall-clock. |
waves/B9\codex-spec-consult-r2.md:162:| W1 | Tier A â€” simple lookups (â‰¤5 columns, generic ingester) | 113 | ~10 sessions |
waves/B9\codex-spec-consult-r2.md:166:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
waves/B9\codex-spec-consult-r2.md:179:B9 ships incrementally **with mandatory per-phase closure gates** â€” each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-spec-consult-r2.md:184:| B9.B | Tier A â€” 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** â€” evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
waves/B9\codex-spec-consult-r2.md:185:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests |
waves/B9\codex-spec-consult-r2.md:186:| B9.D | Tier C non-RNDC14 â€” 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
waves/B9\codex-spec-consult-r2.md:187:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** â€” column-by-column model review |
waves/B9\codex-spec-consult-r2.md:188:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** â€” perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-spec-consult-r2.md:189:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** â€” integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-spec-consult-r2.md:190:| B9.H | Manifest extension (66 â†’ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** â€” full cross-tier consult |
waves/B9\codex-spec-consult-r2.md:197:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
waves/B9\codex-spec-consult-r2.md:198:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-spec-consult-r2.md:199:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-spec-consult-r2.md:201:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
waves/B9\codex-spec-consult-r2.md:204:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-spec-consult-r2.md:213:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-spec-consult-r2.md:214:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) â€” 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-spec-consult-r2.md:221:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\codex-spec-consult-r2.md:224:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
waves/B9\codex-spec-consult-r2.md:237:**~39 sessions Ã— 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong â€” corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-spec-consult-r2.md:241:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-spec-consult-r2.md:253:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -i "First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14|100-session|34|39|mini-GATE|GATE-CLOSE|EXPLAIN ANALYZE|bespoke|migration" charter.md codex-spec-consult-r1.md recon.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
waves/B9\codex-spec-consult-r2.md:261:charter.md:21:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~34 four-hour sessions elapsed; ~6 months wall-clock. |
waves/B9\codex-spec-consult-r2.md:266:charter.md:44:B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-spec-consult-r2.md:267:charter.md:49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
waves/B9\codex-spec-consult-r2.md:268:charter.md:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
waves/B9\codex-spec-consult-r2.md:269:charter.md:51:| B9.D | Tier C non-RNDC14 — 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
waves/B9\codex-spec-consult-r2.md:270:charter.md:52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** — column-by-column model review |
waves/B9\codex-spec-consult-r2.md:271:charter.md:53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** — perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-spec-consult-r2.md:272:charter.md:54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** — integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-spec-consult-r2.md:273:charter.md:55:| B9.H | Manifest extension (66 → 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** — full cross-tier consult |
waves/B9\codex-spec-consult-r2.md:275:charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
waves/B9\codex-spec-consult-r2.md:276:charter.md:63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-spec-consult-r2.md:277:charter.md:64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-spec-consult-r2.md:280:charter.md:69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-spec-consult-r2.md:286:charter.md:78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-spec-consult-r2.md:287:charter.md:79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-spec-consult-r2.md:289:charter.md:86:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\codex-spec-consult-r2.md:294:charter.md:102:**~39 sessions × 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong — corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-spec-consult-r2.md:295:charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-spec-consult-r2.md:308:codex-spec-consult-r1.md:42:   D4 can remain “single B9 milestone,” but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
waves/B9\codex-spec-consult-r2.md:309:codex-spec-consult-r1.md:45:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. “Disk free + pg_stat_user_tables monitoring” is not enough for reversing the Phase 09 1.16 GB deferral.
waves/B9\codex-spec-consult-r2.md:310:codex-spec-consult-r1.md:48:   The charter says recon’s 34-session estimate was “Tier A only,” but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
waves/B9\codex-spec-consult-r2.md:321:codex-spec-consult-r1.md:86:   D4 can remain “single B9 milestone,” but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
waves/B9\codex-spec-consult-r2.md:322:codex-spec-consult-r1.md:89:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. “Disk free + pg_stat_user_tables monitoring” is not enough for reversing the Phase 09 1.16 GB deferral.
waves/B9\codex-spec-consult-r2.md:323:codex-spec-consult-r1.md:92:   The charter says recon’s 34-session estimate was “Tier A only,” but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
waves/B9\codex-spec-consult-r2.md:337:recon.md:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-spec-consult-r2.md:338:recon.md:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
waves/B9\codex-spec-consult-r2.md:363:recon.md:74:**RECORD\_COUNTS.TXT:** Present, contains row count for every table name in the drop (verified counts align with zip). Example: `RNPALL|013213617` (all pricing rows), `RNDC14_NDC_MSTR` implied by `RNDCALL|000501107`.
waves/B9\codex-spec-consult-r2.md:379:recon.md:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-spec-consult-r2.md:392:recon.md:169:| D — Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-spec-consult-r2.md:394:recon.md:173:- `0009_fdb_tier_a.py` — 113 Tier A tables (all small; one migration is reviewable because models are uniform 2–5-col descriptors)
waves/B9\codex-spec-consult-r2.md:399:recon.md:180:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
waves/B9\codex-spec-consult-r2.md:414:recon.md:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-spec-consult-r2.md:420:recon.md:277:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) — implementation-ready spec
waves/B9\codex-spec-consult-r2.md:423:recon.md:286:- One alembic migration `0009_fdb_tier_a.py`
waves/B9\codex-spec-consult-r2.md:427:recon.md:298:- Integration test: verify NDC join correctness against existing `fdb_ndc_price_history`
waves/B9\codex-spec-consult-r2.md:438:recon.md:328:4. **Wave boundary — is B9 one wave or two?**: 34 sessions is 3–4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-spec-consult-r2.md:449:| 1 | Per-phase gates | YES | charter.md:44, 49-55, 69, 106 | Mandatory mini-GATE-CLOSE gates are specified for B9.B..B9.G with evidence, reconciliation, migration review, FDW verify, test baseline comparison, and phase-specific criteria. |
waves/B9\codex-spec-consult-r2.md:450:| 2 | D2 perf gate | YES | charter.md:19, 53, 64, 86 | C0/B9.F now requires timed full-load dry run, `EXPLAIN ANALYZE`, FDW/Postgres verify, storage budget verification, and weekly delta timing. |
waves/B9\codex-spec-consult-r2.md:477:| 1 | Per-phase gates | YES | charter.md:44, 49-55, 69, 106 | Mandatory mini-GATE-CLOSE gates are specified for B9.B..B9.G with evidence, reconciliation, migration review, FDW verify, test baseline comparison, and phase-specific criteria. |
waves/B9\codex-spec-consult-r2.md:478:| 2 | D2 perf gate | YES | charter.md:19, 53, 64, 86 | C0/B9.F now requires timed full-load dry run, `EXPLAIN ANALYZE`, FDW/Postgres verify, storage budget verification, and weekly delta timing. |
waves/B9\codex-gate-close-r3-result.md:14:# Codex B9.A mini-GATE-CLOSE R3 — Final Verification
waves/B9\codex-gate-close-r3-result.md:68:- GO — B9.A is officially closed. B9.B opens.
waves/B9\codex-gate-close-r3-result.md:76:I’ll verify this as a repo-local gate review: first checking the referenced artifacts and status links, then sampling the prior fix surfaces to make sure the R2 absorption did not disturb F1/F3/F4.
waves/B9\codex-gate-close-r3-result.md:135: M infrastructure/scripts/verify_backup.py
waves/B9\codex-gate-close-r3-result.md:168: M modules/core-platform/src/jobs/verify_audit_chain_job.py
waves/B9\codex-gate-close-r3-result.md:763:| B9.B | Tier A â€” 113 simple lookups | NOT STARTED | â€” | Blocked on B9.A gate-close |
waves/B9\codex-gate-close-r3-result.md:764:| B9.C | Tier B â€” 66 NDC/GCN joins | NOT STARTED | â€” | Blocked on B9.B |
waves/B9\codex-gate-close-r3-result.md:787:| C10 | FDW name-collision preflight script | `c03e37a` | 16 (107) |
waves/B9\codex-gate-close-r3-result.md:814:| MEDIUM | Delta-contract bypass risk (B9.B-G omitted from contract) | **F4 â€” deferred to B9.B opening.** Codex's own suggested fix specifies: "In B9.B, add a registry-vs-contract coverage test proving every new non-UNKNOWN/non-TRUNCATE_RELOAD TableSpec is represented in the delta contract suite." This is a B9.B C1-class commit. |
waves/B9\codex-gate-close-r3-result.md:816:**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
waves/B9\codex-gate-close-r3-result.md:849:R3 to confirm or proceeding to B9.B with the deferral acknowledged.
waves/B9\codex-gate-close-r3-result.md:853:## B9.A mini-GATE-CLOSE checklist (charter SC-9)
waves/B9\codex-gate-close-r3-result.md:859:- [x] `setup_fdw.sh --verify` still passes (132 PASS, 0 FAIL â€” captured post-B7.3)
waves/B9\codex-gate-close-r3-result.md:862:- [x] FDW name-collision preflight script in place + 16/16 tests pass
waves/B9\codex-gate-close-r3-result.md:866:- [ ] Codex B9.A mini-GATE-CLOSE consult dispatched + verdict captured
waves/B9\codex-gate-close-r3-result.md:877:| SC-1 | 217 tables have models + migrations + ingester | **+0** (B9.B-G lands actual tables) |
waves/B9\codex-gate-close-r3-result.md:878:| SC-2 | RECORD_COUNTS reconciliation (within Â±0.1%) | Contract template ready (C3); per-table assertions land B9.B+ |
waves/B9\codex-gate-close-r3-result.md:879:| SC-3 | DELTA_SEMANTICS per table | Enum + contract (C1+C3+C8) ready; per-table assignment B9.B+ |
waves/B9\codex-gate-close-r3-result.md:880:| SC-4 | Phase 09 untouched (row counts, query latency) | Baseline locked (C12); test runs every gate |
waves/B9\codex-gate-close-r3-result.md:882:| SC-6 | FDW verify count grows additively | Manifest-derived count (C11) ready; floor 66 |
waves/B9\codex-gate-close-r3-result.md:885:| SC-9 | Per-phase mini-GATE-CLOSE | This file is the ledger; per-phase entries appear B9.B+ |
waves/B9\codex-gate-close-r3-result.md:886:| SC-10 | MTL excluded from default load + FDW | Config flag + registry + REVOKE template (C4) ready |
waves/B9\codex-gate-close-r3-result.md:910:* At every mini-GATE-CLOSE â€” append the per-phase evidence section.
waves/B9\codex-gate-close-r3-result.md:949:waves\B9\codex-gate-close-r2-prompt.md:67:as a B9.B pre-opening obligation in `waves/B9/status.md` →
waves/B9\codex-gate-close-r3-result.md:950:waves\B9\codex-gate-close-r2-prompt.md:68:"B9.B pre-opening obligation (F4)".
waves/B9\codex-gate-close-r3-result.md:952:waves\B9\codex-gate-close-r2-prompt.md:91:4. **F4 deferral**: is the status-ledger row + B9.B pre-opening
waves/B9\codex-gate-close-r3-result.md:958:waves\B9\codex-gate-close-r2-result.md:80:as a B9.B pre-opening obligation in `waves/B9/status.md` →
waves/B9\codex-gate-close-r3-result.md:959:waves\B9\codex-gate-close-r2-result.md:81:"B9.B pre-opening obligation (F4)".
waves/B9\codex-gate-close-r3-result.md:961:waves\B9\codex-gate-close-r2-result.md:104:4. **F4 deferral**: is the status-ledger row + B9.B pre-opening
waves/B9\codex-gate-close-r3-result.md:992:waves\B9\codex-gate-close-r2-result.md:2364:**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
waves/B9\codex-gate-close-r3-result.md:995:waves\B9\codex-gate-close-r2-result.md:2810:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\\.{{MTL_TABLES}}\" waves/B9 infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl modules/drug-database/tests" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-gate-close-r3-result.md:996:waves\B9\codex-gate-close-r2-result.md:2826:    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
waves/B9\codex-gate-close-r3-result.md:997:waves\B9\codex-gate-close-r2-result.md:2834:    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
waves/B9\codex-gate-close-r3-result.md:1075:waves\B9\codex-gate-close-r3-result.md:816:**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
waves/B9\codex-gate-close-r3-result.md:1081:waves\B9\status.md:71:**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
waves/B9\codex-gate-close-r3-result.md:1098:# Codex B9.A mini-GATE-CLOSE R2 â€” Verification Pass
waves/B9\codex-gate-close-r3-result.md:1111:B9.A GATE-CLOSE R1 absorption â€” HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
waves/B9\codex-gate-close-r3-result.md:1162:Explicitly deferred to B9.B per codex's own remediation language:
waves/B9\codex-gate-close-r3-result.md:1163:"In B9.B, add a registry-vs-contract coverage test...". Documented
waves/B9\codex-gate-close-r3-result.md:1164:as a B9.B pre-opening obligation in `waves/B9/status.md` â†’
waves/B9\codex-gate-close-r3-result.md:1165:"B9.B pre-opening obligation (F4)".
waves/B9\codex-gate-close-r3-result.md:1175:## Areas to verify in R2
waves/B9\codex-gate-close-r3-result.md:1188:4. **F4 deferral**: is the status-ledger row + B9.B pre-opening
waves/B9\codex-gate-close-r3-result.md:1194:GO â€” B9.A closes; B9.B opens.
waves/B9\codex-gate-close-r3-result.md:1202:Iâ€™ll verify the absorption against the repository state directly: read the R1 result, inspect commit `33e858b`, check the new template/tests/artifacts, and run focused tests if the read-only sandbox allows execution.
waves/B9\codex-gate-close-r3-result.md:1210:33e858b (HEAD -> develop) B9.A GATE-CLOSE R1 absorption â€” HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
waves/B9\codex-gate-close-r3-result.md:1270: M infrastructure/scripts/verify_backup.py
waves/B9\codex-gate-close-r3-result.md:1303: M modules/core-platform/src/jobs/verify_audit_chain_job.py
waves/B9\codex-gate-close-r3-result.md:1856:The checkout has a very dirty tree, but `33e858b` is at `HEAD -> develop`, so Iâ€™m treating unrelated unstaged/untracked work as out of scope. The R1 result file named in the prompt is not present at `waves/B9/codex-gate-close-r1-result.md`; Iâ€™ll rely on the promptâ€™s R1 summary and verify the actual R2 artifacts.
waves/B9\codex-gate-close-r3-result.md:2133:that every B9.B-G phase reuses. These tests cover the helpers
waves/B9\codex-gate-close-r3-result.md:2135:surface BEFORE B9.B starts wiring 113 Tier A tables through it.
waves/B9\codex-gate-close-r3-result.md:2690:    """B9.A C3 ships the file empty. B9.B+ may add signed-off entries."""
waves/B9\codex-gate-close-r3-result.md:2738:    """Empty initial file MUST exist Ã¢â‚¬â€ every B9.B+ wave ships it."""
waves/B9\codex-gate-close-r3-result.md:2747:Every B9 phase (B9.B Tier A, B9.C Tier B, B9.D Tier C, B9.E RNDC14,
waves/B9\codex-gate-close-r3-result.md:2949:    T1 mitigation: text-heavy Tier A/B tables ship operator-entered
waves/B9\codex-gate-close-r3-result.md:3082:        FileNotFoundError: artifact missing Ã¢â‚¬â€ every B9.B+ wave must
waves/B9\codex-gate-close-r3-result.md:3173:    Sample-bounded: probes first `sample_rows` lines. For Tier A
waves/B9\codex-gate-close-r3-result.md:3220:#   * returns (current row count, current row state for the target key)
waves/B9\codex-gate-close-r3-result.md:3397:| B9.B | Tier A Ã¢â‚¬â€ 113 simple lookups | NOT STARTED | Ã¢â‚¬â€ | Blocked on B9.A gate-close |
waves/B9\codex-gate-close-r3-result.md:3398:| B9.C | Tier B Ã¢â‚¬â€ 66 NDC/GCN joins | NOT STARTED | Ã¢â‚¬â€ | Blocked on B9.B |
waves/B9\codex-gate-close-r3-result.md:3421:| C10 | FDW name-collision preflight script | `c03e37a` | 16 (107) |
waves/B9\codex-gate-close-r3-result.md:3446:| MEDIUM | Delta-contract bypass risk (B9.B-G omitted from contract) | **F4 Ã¢â‚¬â€ deferred to B9.B opening.** Codex's own suggested fix specifies: "In B9.B, add a registry-vs-contract coverage test proving every new non-UNKNOWN/non-TRUNCATE_RELOAD TableSpec is represented in the delta contract suite." This is a B9.B C1-class commit. |
waves/B9\codex-gate-close-r3-result.md:3448:**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
waves/B9\codex-gate-close-r3-result.md:3457:## B9.A mini-GATE-CLOSE checklist (charter SC-9)
waves/B9\codex-gate-close-r3-result.md:3463:- [x] `setup_fdw.sh --verify` still passes (132 PASS, 0 FAIL Ã¢â‚¬â€ captured post-B7.3)
waves/B9\codex-gate-close-r3-result.md:3466:- [x] FDW name-collision preflight script in place + 16/16 tests pass
waves/B9\codex-gate-close-r3-result.md:3470:- [ ] Codex B9.A mini-GATE-CLOSE consult dispatched + verdict captured
waves/B9\codex-gate-close-r3-result.md:3481:| SC-1 | 217 tables have models + migrations + ingester | **+0** (B9.B-G lands actual tables) |
waves/B9\codex-gate-close-r3-result.md:3482:| SC-2 | RECORD_COUNTS reconciliation (within Ã‚Â±0.1%) | Contract template ready (C3); per-table assertions land B9.B+ |
waves/B9\codex-gate-close-r3-result.md:3483:| SC-3 | DELTA_SEMANTICS per table | Enum + contract (C1+C3+C8) ready; per-table assignment B9.B+ |
waves/B9\codex-gate-close-r3-result.md:3484:| SC-4 | Phase 09 untouched (row counts, query latency) | Baseline locked (C12); test runs every gate |
waves/B9\codex-gate-close-r3-result.md:3486:| SC-6 | FDW verify count grows additively | Manifest-derived count (C11) ready; floor 66 |
waves/B9\codex-gate-close-r3-result.md:3489:| SC-9 | Per-phase mini-GATE-CLOSE | This file is the ledger; per-phase entries appear B9.B+ |
waves/B9\codex-gate-close-r3-result.md:3490:| SC-10 | MTL excluded from default load + FDW | Config flag + registry + REVOKE template (C4) ready |
waves/B9\codex-gate-close-r3-result.md:3514:* At every mini-GATE-CLOSE Ã¢â‚¬â€ append the per-phase evidence section.
waves/B9\codex-gate-close-r3-result.md:3525:**Audit gate:** every B9.B-G mini-GATE-CLOSE re-reads this file; any
waves/B9\codex-gate-close-r3-result.md:3596:This file LOCKS the Phase 09 row counts + query latency that every
waves/B9\codex-gate-close-r3-result.md:3597:B9.B-G mini-GATE-CLOSE asserts unchanged (within documented tolerance).
waves/B9\codex-gate-close-r3-result.md:3614:ledger; mini-GATE-CLOSE asserts row count **>= baseline** and that
waves/B9\codex-gate-close-r3-result.md:3643:0 net new rows. Mini-GATE-CLOSE for B9.B-G re-runs this and asserts
waves/B9\codex-gate-close-r3-result.md:3646:## How mini-GATE-CLOSE re-asserts this
waves/B9\codex-gate-close-r3-result.md:3648:Each B9.B-G phase close runs:
waves/B9\codex-gate-close-r3-result.md:3661:Outputs are diffed against this file. Any drift fails the mini-GATE.
waves/B9\codex-gate-close-r3-result.md:3668:   `fdb_ndc_price_history` row count and the delta ledger entry.
waves/B9\codex-gate-close-r3-result.md:3674:   The new row count IS the new baseline; this file is updated in
waves/B9\codex-gate-close-r3-result.md:3680:(added by B9.A C12) re-asserts the row counts against a live Postgres
waves/B9\codex-gate-close-r3-result.md:3695:B9 FDB loaders write reference tables (Tier A/B/C/RNDC14/pricing/MTL)
waves/B9\codex-gate-close-r3-result.md:3733:python scripts/load_fdb.py --mode fdb_tier_a --require-reference-db
waves/B9\codex-gate-close-r3-result.md:3736:The `--require-reference-db` flag is set automatically by every B9.B-G
waves/B9\codex-gate-close-r3-result.md:3775:B9.B-G plan to land **217 new SQLAlchemy models** in
waves/B9\codex-gate-close-r3-result.md:3798:| After B9.B (+113 Tier A) | 122 | ~1.5 s |
waves/B9\codex-gate-close-r3-result.md:3805:have no need for FDB Tier A lookup models.
waves/B9\codex-gate-close-r3-result.md:3818:# (drug_database) for alembic / FDW purposes.
waves/B9\codex-gate-close-r3-result.md:3830:# Tests that only need Tier A:
waves/B9\codex-gate-close-r3-result.md:3849:"I only need Tier A models" and pay only the Tier A cost. The
waves/B9\codex-gate-close-r3-result.md:3872:   B9.B-G's first commit lifts this number IF the new tier was
waves/B9\codex-gate-close-r3-result.md:3883:**Trigger:** the first B9.B commit that would push
waves/B9\codex-gate-close-r3-result.md:3894:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\\.{{MTL_TABLES}}\" waves/B9 infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl modules/drug-database/tests" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-gate-close-r3-result.md:3910:    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
waves/B9\codex-gate-close-r3-result.md:3918:    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
waves/B9\codex-gate-close-r3-result.md:3982:waves/B9\codex-gate-close-r2-result.md:772:The checkout has a very dirty tree, but `33e858b` is at `HEAD -> develop`, so Iâ€™m treating unrelated unstaged/untracked work as out of scope. The R1 result file named in the prompt is not present at `waves/B9/codex-gate-close-r1-result.md`; Iâ€™ll rely on the promptâ€™s R1 summary and verify the actual R2 artifacts.
waves/B9\codex-gate-close-r3-result.md:3997:F4 deferral is acceptable. I would not add an `xfail` stub in B9.A; the status-ledger pre-opening obligation is explicit enough, assuming B9.B treats it as a first commit gate.
waves/B9\codex-gate-close-r3-result.md:4012:F4 deferral is acceptable. I would not add an `xfail` stub in B9.A; the status-ledger pre-opening obligation is explicit enough, assuming B9.B treats it as a first commit gate.
waves/B9\codex-gate-close-r3-result.md:4026:waves\B9\charter.md:3:**Status:** SPEC v3.2 LOCKED — erratum chain: (v3.1) arithmetic drift correction surfaced by codex PLAN R2 → B9.B FDW `116/116`→`179/179`, B9.D "17 complex"→"16 complex"; (v3.2) MTL FDW-exposure policy surfaced by codex ADVERSARIAL R1 → MTL excluded from default FDW manifest to prevent silent false-negative joins, conditional 19 entries added only when `fdb_load_mtl=True` (future MTL activation wave). B9.H final FDW count: **264/264 default, 283/283 conditional**. No scope change. See `codex-plan-consult-r2.md` and `codex-adversarial-r1.md`. Ready for PLAN v3 → ADVERSARIAL R2.
waves/B9\codex-gate-close-r3-result.md:4028:waves\B9\charter.md:66:| SC-6 | `setup_fdw.sh --verify` 264/264 PASS in both env DBs by default (MTL excluded from FDW per ADVERSARIAL R1 mitigation); conditional 283/283 when `fdb_load_mtl=True` |
waves/B9\codex-gate-close-r3-result.md:4031:waves\B9\charter.md:102:**~39 sessions × 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong — corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-gate-close-r3-result.md:4032:waves\B9\charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-gate-close-r3-result.md:4041:waves\B9\plan.md:3:**Status:** PLAN v3.1 LOCKED — **ADVERSARIAL GATE FINAL VERDICT: GO** (`codex-adversarial-r2.md` tail). B9.A meta-phase gate cycle CLOSED. Ready for B9.A C0-C14 execution, then B9.B opens (Tier A — 113 simple lookups via generic table-driven ingester).
waves/B9\codex-gate-close-r3-result.md:4042:waves\B9\plan.md:5:**Iteration history:** PLAN v1 → PLAN R1 GO-WITH-FIXES (8 fixes) → PLAN v2 → PLAN R2 GO-WITH-FIXES (charter v3.1 erratum) → PLAN GATE FINAL VERDICT GO → ADVERSARIAL R1 HIGH-SEVERITY OBJECTIONS PRESENT (9 HIGH + 11 MED + 4 novel) → PLAN v3 (all mitigations folded) → charter v3.2 erratum (MTL FDW exposure) → ADVERSARIAL R2 GO-WITH-FIXES (one stale line) → PLAN v3.1 (narrow fix) → ADVERSARIAL R3 first ping (caught one more stale FDW reference) → cleanup → ADVERSARIAL R3 second ping **GO**.
waves/B9\codex-gate-close-r3-result.md:4043:waves\B9\plan.md:21:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9\codex-gate-close-r3-result.md:4052:waves\B9\plan.md:404:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
waves/B9\codex-gate-close-r3-result.md:4055:waves\B9\plan.md:435:| PLAN R2 | B9.A | Plan v2 with R1 fixes; verify | `codex-plan-consult-r2.md` — GO-WITH-FIXES → charter v3.1 erratum → PLAN GATE FINAL GO |
waves/B9\codex-gate-close-r3-result.md:4057:waves\B9\plan.md:437:| **ADVERSARIAL R2** | **B9.A** | **Plan v3 with R1 mitigations absorbed; verify** | **`codex-adversarial-r2.md` — pending** |
waves/B9\codex-gate-close-r3-result.md:4058:waves\B9\plan.md:446:**Total codex consults projected:** 13 (2 SPEC + 2 PLAN + 2 ADVERSARIAL + 6 mini-GATE-CLOSE + 1 final GATE-CLOSE = 13). Token spend through ADVERSARIAL R1: ~280k. Remaining gate consults: ~50-80k for ADVERSARIAL R2 + ~300k for 6 mini-GATE-CLOSEs + ~40k for final = ~390-420k more codex tokens.
waves/B9\codex-gate-close-r3-result.md:4065:waves\B9\codex-gate-close-r2-prompt.md:14:B9.A GATE-CLOSE R1 absorption — HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
waves/B9\codex-gate-close-r3-result.md:4070:waves\B9\codex-gate-close-r2-prompt.md:68:"B9.B pre-opening obligation (F4)".
waves/B9\codex-gate-close-r3-result.md:4074:waves\B9\codex-gate-close-r2-prompt.md:91:4. **F4 deferral**: is the status-ledger row + B9.B pre-opening
waves/B9\codex-gate-close-r3-result.md:4081:waves\B9\codex-gate-close-r2-result.md:27:B9.A GATE-CLOSE R1 absorption — HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
waves/B9\codex-gate-close-r3-result.md:4086:waves\B9\codex-gate-close-r2-result.md:81:"B9.B pre-opening obligation (F4)".
waves/B9\codex-gate-close-r3-result.md:4090:waves\B9\codex-gate-close-r2-result.md:104:4. **F4 deferral**: is the status-ledger row + B9.B pre-opening
waves/B9\codex-gate-close-r3-result.md:4094:waves\B9\codex-gate-close-r2-result.md:126:33e858b (HEAD -> develop) B9.A GATE-CLOSE R1 absorption — HIGH 1, HIGH 2, MEDIUM 1 (F4 deferred to B9.B)
waves/B9\codex-gate-close-r3-result.md:4102:waves\B9\codex-gate-close-r2-result.md:2362:| MEDIUM | Delta-contract bypass risk (B9.B-G omitted from contract) | **F4 â€” deferred to B9.B opening.** Codex's own suggested fix specifies: "In B9.B, add a registry-vs-contract coverage test proving every new non-UNKNOWN/non-TRUNCATE_RELOAD TableSpec is represented in the delta contract suite." This is a B9.B C1-class commit. |
waves/B9\codex-gate-close-r3-result.md:4103:waves\B9\codex-gate-close-r2-result.md:2364:**B9.B pre-opening obligation (F4):** Before B9.B's first Tier A
waves/B9\codex-gate-close-r3-result.md:4104:waves\B9\codex-gate-close-r2-result.md:2810:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\\.{{MTL_TABLES}}\" waves/B9 infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl modules/drug-database/tests" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-gate-close-r3-result.md:4105:waves\B9\codex-gate-close-r2-result.md:2826:    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
waves/B9\codex-gate-close-r3-result.md:4106:waves\B9\codex-gate-close-r2-result.md:2834:    (?:codex-gate-close-r1|B9.B pre-opening|test_delta_contract_coverage|F4|Approved allowlist entries|{{APP_ROLES_QUOTED}}|ON {{MTL_TABLES}}|ON {{SCHEMA}}\.{{MTL_TABLES}})
waves/B9\codex-gate-close-r3-result.md:4111:waves\B9\codex-gate-close-r2-result.md:2913:F4 deferral is acceptable. I would not add an `xfail` stub in B9.A; the status-ledger pre-opening obligation is explicit enough, assuming B9.B treats it as a first commit gate.
waves/B9\codex-gate-close-r3-result.md:4116:waves\B9\codex-gate-close-r2-result.md:2928:F4 deferral is acceptable. I would not add an `xfail` stub in B9.A; the status-ledger pre-opening obligation is explicit enough, assuming B9.B treats it as a first commit gate.
waves/B9\codex-gate-close-r3-result.md:4131:F1, F3, and F4 remain accepted. The MTL REVOKE template still documents/substitutes `{{APP_ROLES_QUOTED}}` and uses `ON {{MTL_TABLES}}`; parse-warning allowlist enforcement is still present; F4 remains explicitly documented as a B9.B pre-opening obligation.
waves/B9\codex-gate-close-r3-result.md:4142:F1, F3, and F4 remain accepted. The MTL REVOKE template still documents/substitutes `{{APP_ROLES_QUOTED}}` and uses `ON {{MTL_TABLES}}`; parse-warning allowlist enforcement is still present; F4 remains explicitly documented as a B9.B pre-opening obligation.
waves/B9\codex-plan-consult-r1.md:18:Wave B9 = "FDB NDDF Plus 220-table extension". SPEC v3 is locked (you previously approved at SPEC R2 GO-WITH-FIXES → owner applied the stale-D4-row cleanup → v3 LOCKED). The next gate is PLAN v1. The owner drafted `plan.md` v1 (380 lines). Your job in PLAN R1 is to verify whether the plan is sound, complete, and ready for ADVERSARIAL review + execute, OR whether it needs revision.
waves/B9\codex-plan-consult-r1.md:28:## What to verify (PLAN gate criteria)
waves/B9\codex-plan-consult-r1.md:34:4. **Mini-GATE-CLOSE criteria are concrete, not vague** — each phase B9.B..B9.G has measurable gate criteria (counts, test outcomes, perf numbers), not just "looks good."
waves/B9\codex-plan-consult-r1.md:40:8. **Session sizing realistic** — Tier A 113 tables / 10 sessions = ~12 tables/session; Tier B 66 / 12 = ~5.5/session. Are these defensible given the per-table work?
waves/B9\codex-plan-consult-r1.md:44:**Plan-errata (the owner surfaced 3 — verify and find more):**
waves/B9\codex-plan-consult-r1.md:45:11. **FDW final count 283 vs 284** — which is right? Recompute from recon's table counts and reconcile.
waves/B9\codex-plan-consult-r1.md:49:**Charter-level (re-verify SPEC R2 verdict still holds against this plan):**
waves/B9\codex-plan-consult-r1.md:50:14. **Per-phase gates honored** — the plan's mini-GATE-CLOSE rows match SPEC v3's locked phase boundary table.
waves/B9\codex-plan-consult-r1.md:82:| FDW count 283 vs 284 | <which is right + why> | <recon table refs> |
waves/B9\codex-plan-consult-r1.md:84:| Loader modes | <verify or add> | <evidence> |
waves/B9\codex-plan-consult-r1.md:108:I’ll read the B9 artifacts and the vendor-reference rule first, then cross-check the plan against the charter and recon counts. Since this is a gate review, I’ll keep edits out of scope and return the requested verdict format only after verifying the cited files.
waves/B9\codex-plan-consult-r1.md:199:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~39 four-hour sessions planned; ~13 weeks at 3 sessions/week, realistically 4â€“5 months with multitasking. |
waves/B9\codex-plan-consult-r1.md:205:| W1 | Tier A â€” simple lookups (â‰¤5 columns, generic ingester) | 113 | ~10 sessions |
waves/B9\codex-plan-consult-r1.md:209:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
waves/B9\codex-plan-consult-r1.md:222:B9 ships incrementally **with mandatory per-phase closure gates** â€” each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-plan-consult-r1.md:227:| B9.B | Tier A â€” 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** â€” evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
waves/B9\codex-plan-consult-r1.md:228:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r1.md:229:| B9.D | Tier C non-RNDC14 â€” 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
waves/B9\codex-plan-consult-r1.md:230:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** â€” column-by-column model review |
waves/B9\codex-plan-consult-r1.md:231:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** â€” perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-plan-consult-r1.md:232:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** â€” integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-plan-consult-r1.md:233:| B9.H | Manifest extension (66 â†’ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** â€” full cross-tier consult |
waves/B9\codex-plan-consult-r1.md:240:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
waves/B9\codex-plan-consult-r1.md:241:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-plan-consult-r1.md:242:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-plan-consult-r1.md:244:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
waves/B9\codex-plan-consult-r1.md:247:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-plan-consult-r1.md:256:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-plan-consult-r1.md:257:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) â€” 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-plan-consult-r1.md:264:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\codex-plan-consult-r1.md:267:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
waves/B9\codex-plan-consult-r1.md:280:**~39 sessions Ã— 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong â€” corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-plan-consult-r1.md:284:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r1.md:659:| T1 | Sed regex misses an indented or multi-line import | C1 verification grep returns hits | Add additional sed pass; re-verify |
waves/B9\codex-plan-consult-r1.md:709:Wave B9 = "FDB NDDF Plus 220-table extension". Recon was completed 2026-05-11 (`recon.md`). Charter v1 was dispatched for SPEC R1. You returned **GO-WITH-FIXES** with 6 substantive concerns (1 HIGH effort model, 2 HIGH process gates, 3 MEDIUM SPEC tightenings, 1 LOW vendor-name pass). The owner produced charter v2 which claims to absorb all 6 concerns. Your job in R2 is to verify whether v2 actually addresses each concern, and either issue **GO** (proceed to PLAN), **GO-WITH-FIXES** (one more revision needed), or **NO-GO** (structural problem).
waves/B9\codex-plan-consult-r1.md:717:## R1 concerns to verify in v2 (use these as your checklist)
waves/B9\codex-plan-consult-r1.md:721:| 1 | HIGH | Single final GATE-CLOSE too late for 220 tables | Per-phase mini-GATE-CLOSE gates between B9.B..B9.G with explicit closure criteria |
waves/B9\codex-plan-consult-r1.md:847:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~34 four-hour sessions elapsed; ~6 months wall-clock. |
waves/B9\codex-plan-consult-r1.md:853:| W1 | Tier A Ã¢â‚¬â€ simple lookups (Ã¢â€°Â¤5 columns, generic ingester) | 113 | ~10 sessions |
waves/B9\codex-plan-consult-r1.md:857:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
waves/B9\codex-plan-consult-r1.md:870:B9 ships incrementally **with mandatory per-phase closure gates** Ã¢â‚¬â€ each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-plan-consult-r1.md:875:| B9.B | Tier A Ã¢â‚¬â€ 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** Ã¢â‚¬â€ evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
waves/B9\codex-plan-consult-r1.md:876:| B9.C | Tier B Ã¢â‚¬â€ 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** Ã¢â‚¬â€ same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r1.md:877:| B9.D | Tier C non-RNDC14 Ã¢â‚¬â€ 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
waves/B9\codex-plan-consult-r1.md:878:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** Ã¢â‚¬â€ column-by-column model review |
waves/B9\codex-plan-consult-r1.md:879:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** Ã¢â‚¬â€ perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-plan-consult-r1.md:880:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** Ã¢â‚¬â€ integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-plan-consult-r1.md:881:| B9.H | Manifest extension (66 Ã¢â€ â€™ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** Ã¢â‚¬â€ full cross-tier consult |
waves/B9\codex-plan-consult-r1.md:888:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Ã‚Â± documented tolerance (MTL excluded Ã¢â‚¬â€ schema-only) |
waves/B9\codex-plan-consult-r1.md:889:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-plan-consult-r1.md:890:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-plan-consult-r1.md:892:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
waves/B9\codex-plan-consult-r1.md:895:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-plan-consult-r1.md:904:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-plan-consult-r1.md:905:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) Ã¢â‚¬â€ 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-plan-consult-r1.md:912:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\codex-plan-consult-r1.md:915:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
waves/B9\codex-plan-consult-r1.md:928:**~39 sessions Ãƒâ€” 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong Ã¢â‚¬â€ corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-plan-consult-r1.md:932:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification Ã¢â‚¬â€ preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r1.md:944:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -i "First Databank|FirstDataBank|FDB|NDDF|MTL|RNP2|RPRDPP0|RNDC14|100-session|34|39|mini-GATE|GATE-CLOSE|EXPLAIN ANALYZE|bespoke|migration" charter.md codex-spec-consult-r1.md recon.md' in C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9
waves/B9\codex-plan-consult-r1.md:952:charter.md:21:| D4 | **Single B9 wave for all 217 tables** | One milestone label; not split into B9/B10/B11. ~34 four-hour sessions elapsed; ~6 months wall-clock. |
waves/B9\codex-plan-consult-r1.md:957:charter.md:44:B9 ships incrementally **with mandatory per-phase closure gates** â€” each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-plan-consult-r1.md:958:charter.md:49:| B9.B | Tier A â€” 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** â€” evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
waves/B9\codex-plan-consult-r1.md:959:charter.md:50:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r1.md:960:charter.md:51:| B9.D | Tier C non-RNDC14 â€” 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
waves/B9\codex-plan-consult-r1.md:961:charter.md:52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** â€” column-by-column model review |
waves/B9\codex-plan-consult-r1.md:962:charter.md:53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** â€” perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-plan-consult-r1.md:963:charter.md:54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** â€” integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-plan-consult-r1.md:964:charter.md:55:| B9.H | Manifest extension (66 â†’ 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** â€” full cross-tier consult |
waves/B9\codex-plan-consult-r1.md:966:charter.md:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected Â± documented tolerance (MTL excluded â€” schema-only) |
waves/B9\codex-plan-consult-r1.md:967:charter.md:63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-plan-consult-r1.md:968:charter.md:64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-plan-consult-r1.md:971:charter.md:69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-plan-consult-r1.md:977:charter.md:78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-plan-consult-r1.md:978:charter.md:79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) â€” 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-plan-consult-r1.md:980:charter.md:86:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\codex-plan-consult-r1.md:985:charter.md:102:**~39 sessions Ã— 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong â€” corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-plan-consult-r1.md:986:charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r1.md:999:codex-spec-consult-r1.md:42:   D4 can remain â€œsingle B9 milestone,â€ but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
waves/B9\codex-plan-consult-r1.md:1000:codex-spec-consult-r1.md:45:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. â€œDisk free + pg_stat_user_tables monitoringâ€ is not enough for reversing the Phase 09 1.16 GB deferral.
waves/B9\codex-plan-consult-r1.md:1001:codex-spec-consult-r1.md:48:   The charter says reconâ€™s 34-session estimate was â€œTier A only,â€ but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
waves/B9\codex-plan-consult-r1.md:1012:codex-spec-consult-r1.md:86:   D4 can remain â€œsingle B9 milestone,â€ but B9.B through B9.F need their own closure gates with evidence, row-count reconciliation, migration review, FDW verify, and test baseline comparison. A single final review across 220 tables will be too late to catch structural drift.
waves/B9\codex-plan-consult-r1.md:1013:codex-spec-consult-r1.md:89:   C0 should include: free disk + projected table/index bloat, timed full-load dry run for `RNP2_NDC_PRICE` and `RPRDPP0_PRODUCT_PRICE`, weekly delta/idempotency timing, representative `EXPLAIN ANALYZE`, and Postgres/FDW verify after indexes. â€œDisk free + pg_stat_user_tables monitoringâ€ is not enough for reversing the Phase 09 1.16 GB deferral.
waves/B9\codex-plan-consult-r1.md:1014:codex-spec-consult-r1.md:92:   The charter says reconâ€™s 34-session estimate was â€œTier A only,â€ but recon estimates ~34 sessions for A+B+C excluding Tier D, and ~39 sessions with review overhead. If B9 is now 100 sessions, that may be valid conservatism, but the charter needs a corrected explanation.
waves/B9\codex-plan-consult-r1.md:1028:recon.md:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-plan-consult-r1.md:1029:recon.md:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion â€” this is a one-time setup change, not per-deployment.
waves/B9\codex-plan-consult-r1.md:1054:recon.md:74:**RECORD\_COUNTS.TXT:** Present, contains row count for every table name in the drop (verified counts align with zip). Example: `RNPALL|013213617` (all pricing rows), `RNDC14_NDC_MSTR` implied by `RNDCALL|000501107`.
waves/B9\codex-plan-consult-r1.md:1070:recon.md:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-plan-consult-r1.md:1083:recon.md:169:| D â€” Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-plan-consult-r1.md:1085:recon.md:173:- `0009_fdb_tier_a.py` â€” 113 Tier A tables (all small; one migration is reviewable because models are uniform 2â€“5-col descriptors)
waves/B9\codex-plan-consult-r1.md:1090:recon.md:180:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
waves/B9\codex-plan-consult-r1.md:1105:recon.md:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-plan-consult-r1.md:1111:recon.md:277:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) â€” implementation-ready spec
waves/B9\codex-plan-consult-r1.md:1114:recon.md:286:- One alembic migration `0009_fdb_tier_a.py`
waves/B9\codex-plan-consult-r1.md:1118:recon.md:298:- Integration test: verify NDC join correctness against existing `fdb_ndc_price_history`
waves/B9\codex-plan-consult-r1.md:1129:recon.md:328:4. **Wave boundary â€” is B9 one wave or two?**: 34 sessions is 3â€“4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-plan-consult-r1.md:1140:| 1 | Per-phase gates | YES | charter.md:44, 49-55, 69, 106 | Mandatory mini-GATE-CLOSE gates are specified for B9.B..B9.G with evidence, reconciliation, migration review, FDW verify, test baseline comparison, and phase-specific criteria. |
waves/B9\codex-plan-consult-r1.md:1141:| 2 | D2 perf gate | YES | charter.md:19, 53, 64, 86 | C0/B9.F now requires timed full-load dry run, `EXPLAIN ANALYZE`, FDW/Postgres verify, storage budget verification, and weekly delta timing. |
waves/B9\codex-plan-consult-r1.md:1168:| 1 | Per-phase gates | YES | charter.md:44, 49-55, 69, 106 | Mandatory mini-GATE-CLOSE gates are specified for B9.B..B9.G with evidence, reconciliation, migration review, FDW verify, test baseline comparison, and phase-specific criteria. |
waves/B9\codex-plan-consult-r1.md:1169:| 2 | D2 perf gate | YES | charter.md:19, 53, 64, 86 | C0/B9.F now requires timed full-load dry run, `EXPLAIN ANALYZE`, FDW/Postgres verify, storage budget verification, and weekly delta timing. |
waves/B9\codex-plan-consult-r1.md:1202:2. **Per-phase scope, deliverables, success-criteria mapping, gate criteria, est sessions, commit shape** for B9.B..B9.H.
waves/B9\codex-plan-consult-r1.md:1206:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9\codex-plan-consult-r1.md:1211:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-plan-consult-r1.md:1222:2. **B7.2 Phase 11A COMPLETE** â€” `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
waves/B9\codex-plan-consult-r1.md:1223:3. **Reference DB topology stable** â€” `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-plan-consult-r1.md:1227:7. **FDB drop manifest reachable** â€” `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon Â§1.5 verified â€” re-verify at C0).
waves/B9\codex-plan-consult-r1.md:1237:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
waves/B9\codex-plan-consult-r1.md:1249:- **`setup_fdw.sh --verify` manifest expansion mechanism** â€” `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Per-phase the line count rises (66 â†’ 179 after B9.B â†’ 245 after B9.C â†’ 264 after B9.D â†’ 265 after B9.E â†’ 267 after B9.F â†’ 267 after B9.G schema-only â€” MTL counted â†’ 283 after B9.H final verify). B9.H reconciles the final count to 283.
waves/B9\codex-plan-consult-r1.md:1250:- **`pytest --collect-only` baseline marker** â€” committed to `waves/B9/baseline.md` at C0; every phase mini-GATE-CLOSE re-runs and asserts count unchanged.
waves/B9\codex-plan-consult-r1.md:1256:| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
waves/B9\codex-plan-consult-r1.md:1265:**B9.A mini-GATE-CLOSE criteria (charter SC-9):**
waves/B9\codex-plan-consult-r1.md:1269:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
waves/B9\codex-plan-consult-r1.md:1275:### B9.B â€” Tier A: 113 simple lookup tables (â‰¤ 5 columns, generic ingester) (10 sessions)
waves/B9\codex-plan-consult-r1.md:1277:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier â€” short tables (mostly < 10K rows, all â‰¤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
waves/B9\codex-plan-consult-r1.md:1282:- 1 batched alembic migration per 25 tables (4 migrations total across B9.B: `0009_fdb_tier_a_part1`..`0009d_fdb_tier_a_part4`) â€” alternative: a single `0009_fdb_tier_a.py` if review is tractable; codex PLAN consult decides
waves/B9\codex-plan-consult-r1.md:1290:- 1-4 alembic migrations (`0009_fdb_tier_a*`)
waves/B9\codex-plan-consult-r1.md:1292:- Loader-orchestration entry: `--mode fdb_tier_a` loads only Tier A
waves/B9\codex-plan-consult-r1.md:1298:- SC-2 (RECORD_COUNTS reconciliation) â€” every loaded Tier A table: actual Ã· expected within Â±0.1% tolerance (small lookups should be exact)
waves/B9\codex-plan-consult-r1.md:1299:- SC-6 (FDW verify) â€” partial: 179/179 PASS after B9.B
waves/B9\codex-plan-consult-r1.md:1300:- SC-7 (weekly idempotency) â€” verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9\codex-plan-consult-r1.md:1301:- SC-8 (test strategy) â€” contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
waves/B9\codex-plan-consult-r1.md:1302:- SC-9 (mini-GATE-CLOSE) â€” see below
waves/B9\codex-plan-consult-r1.md:1304:**B9.B mini-GATE-CLOSE criteria:**
waves/B9\codex-plan-consult-r1.md:1306:- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` Â± documented tolerance
waves/B9\codex-plan-consult-r1.md:1307:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9\codex-plan-consult-r1.md:1308:- All Tier A contract tests green
waves/B9\codex-plan-consult-r1.md:1309:- Sampled behavioral tests: 10 randomly-picked Tier A tables exercise non-trivial query (FK join, where-clause, sort)
waves/B9\codex-plan-consult-r1.md:1311:- Weekly delta path: `load_fdb.py --mode fdb_tier_a` re-run produces 0 new rows (idempotent)
waves/B9\codex-plan-consult-r1.md:1313:- Codex mini-GATE-CLOSE consult: GO
waves/B9\codex-plan-consult-r1.md:1321:**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.
waves/B9\codex-plan-consult-r1.md:1323:**Per-session shape (12 sessions = ~5.5 tables/session â€” slower than Tier A because of join-design + FK-target verification per table):**
waves/B9\codex-plan-consult-r1.md:1326:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-plan-consult-r1.md:1336:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\codex-plan-consult-r1.md:1337:- FDW foreign-table count: 179 â†’ 245
waves/B9\codex-plan-consult-r1.md:1341:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-plan-consult-r1.md:1362:- FDW foreign-table count: 245 â†’ 262
waves/B9\codex-plan-consult-r1.md:1367:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
waves/B9\codex-plan-consult-r1.md:1375:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" â€” no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-plan-consult-r1.md:1388:- FDW foreign-table count: 262 â†’ 263
waves/B9\codex-plan-consult-r1.md:1392:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
waves/B9\codex-plan-consult-r1.md:1403:- Session 2: Timed full-load dry run for both tables; capture wall-clock + final row count + Postgres index build time; capture `df -h` before/after
waves/B9\codex-plan-consult-r1.md:1405:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` â†’ 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline
waves/B9\codex-plan-consult-r1.md:1414:- FDW foreign-table count: 263 â†’ 265
waves/B9\codex-plan-consult-r1.md:1418:**B9.F mini-GATE-CLOSE criteria â€” DRACONIAN per charter SC-4:**
waves/B9\codex-plan-consult-r1.md:1423:- FDW + Postgres verify after indexes built: completes within 5 min
waves/B9\codex-plan-consult-r1.md:1425:- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps
waves/B9\codex-plan-consult-r1.md:1448:- FDW foreign-table count: 265 â†’ 284 (MTL tables ARE in FDW even though data isn't loaded â€” they exist as foreign-table entries pointing at empty reference tables)
waves/B9\codex-plan-consult-r1.md:1450:**Note on FDW count:** 284 not 283. Recon's target was 283 across 220 - 3 already covered tables = wait, re-checking â€” actually B9.A's expansion path showed 283 final count. Let me re-derive: 66 (current) + 113 (B9.B) + 66 (B9.C) + 17 (B9.D) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = 284. **The 283 figure in the charter is wrong by 1; B9.H reconciles to the true 284.** This is a charter erratum to surface to codex PLAN consult.
waves/B9\codex-plan-consult-r1.md:1454:**B9.G mini-GATE-CLOSE criteria:**
waves/B9\codex-plan-consult-r1.md:1459:- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)
waves/B9\codex-plan-consult-r1.md:1465:**Scope:** Reconcile `infrastructure/scripts/lib/expected_reference_tables.txt` to the true final count, run final FDW verify, produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
waves/B9\codex-plan-consult-r1.md:1470:- Session 2: Final `setup_fdw.sh --verify` 284/284 in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables; published in `waves/B9/evidence.md`
waves/B9\codex-plan-consult-r1.md:1477:- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
waves/B9\codex-plan-consult-r1.md:1491:- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
waves/B9\codex-plan-consult-r1.md:1494:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9\codex-plan-consult-r1.md:1509:| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
waves/B9\codex-plan-consult-r1.md:1510:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9\codex-plan-consult-r1.md:1513:| SC-6 | `setup_fdw.sh --verify` output 284/284 in dev + mock (or 283/283 if reconciled to charter count) | B9.H Session 2 |
waves/B9\codex-plan-consult-r1.md:1516:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
waves/B9\codex-plan-consult-r1.md:1526:| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon Â§7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
waves/B9\codex-plan-consult-r1.md:1527:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9\codex-plan-consult-r1.md:1529:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
waves/B9\codex-plan-consult-r1.md:1532:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
waves/B9\codex-plan-consult-r1.md:1533:| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
waves/B9\codex-plan-consult-r1.md:1534:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
waves/B9\codex-plan-consult-r1.md:1535:| T10 | Test count baseline drifts (134 pre-existing failures become 135 or 200) | MED | MED | B9.A C0 captures `pytest --collect-only` count; each phase mini-GATE-CLOSE asserts count unchanged Â± new contract tests |
waves/B9\codex-plan-consult-r1.md:1536:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
waves/B9\codex-plan-consult-r1.md:1548:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
waves/B9\codex-plan-consult-r1.md:1549:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-plan-consult-r1.md:1550:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 17 ingested | `codex-mini-gate-close-D.md` |
waves/B9\codex-plan-consult-r1.md:1551:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9\codex-plan-consult-r1.md:1552:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9\codex-plan-consult-r1.md:1553:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9\codex-plan-consult-r1.md:1576:1. **FDW final count: 283 vs 284.** Charter says 283; PLAN's tier-additive derivation gives 284 (66 + 113 + 66 + 17 + 1 + 2 + 19 = 284). The charter figure may have netted the 3 already-covered FDB pricing tables differently. Codex PLAN consult should reconcile before B9.B opens.
waves/B9\codex-plan-consult-r1.md:1577:2. **Migration count: 5 vs 6.** Charter says "0009..0014" (6 migrations); PLAN sub-counts Tier A and Tier B each into ~3-4 part files, which inflates the migration count to 9-10. Codex PLAN consult should rule on batching shape: single big file per tier OR per-25 part files.
waves/B9\codex-plan-consult-r1.md:1578:3. **Loader-orchestration modes: existing vs new.** Charter implies `--mode fdb_weekly` exists; recon shows existing loader has `--mode fdb_initial` only. PLAN assumes both exist; B9.A C4 must verify or add `--mode fdb_weekly`.
waves/B9\codex-plan-consult-r1.md:1587:- At each mini-GATE-CLOSE: full sign-off sheet committed
waves/B9\codex-plan-consult-r1.md:1607:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-plan-consult-r1.md:1608:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion â€” this is a one-time setup change, not per-deployment.
waves/B9\codex-plan-consult-r1.md:1632:RECORD_COUNTS.TXT                  <- table name -> row count manifest
waves/B9\codex-plan-consult-r1.md:1667:**RECORD\_COUNTS.TXT:** Present, contains row count for every table name in the drop (verified counts align with zip). Example: `RNPALL|013213617` (all pricing rows), `RNDC14_NDC_MSTR` implied by `RNDCALL|000501107`.
waves/B9\codex-plan-consult-r1.md:1707:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-plan-consult-r1.md:1714:- **Tier A** â€” Pure reference/description tables. Typically code â†’ description, â‰¤ 5 columns, < 2 MB uncompressed, name suffix `D0`â€“`D9` pattern or a small static lookup. No NDC normalization, no join design, no money columns.
waves/B9\codex-plan-consult-r1.md:1738:| RETCNDH0\_ETC\_NDC\_HIST | 7 | 30 MB | ETC NDC history (large row count) |
waves/B9\codex-plan-consult-r1.md:1762:| D â€” Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-plan-consult-r1.md:1766:- `0009_fdb_tier_a.py` â€” 113 Tier A tables (all small; one migration is reviewable because models are uniform 2â€“5-col descriptors)
waves/B9\codex-plan-consult-r1.md:1773:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
waves/B9\codex-plan-consult-r1.md:1785:| E â€” Generic table-driven ingester | Config file (YAML/dict) maps table names â†’ TableSpec; one ingester loops all tables | RECOMMENDED for Tier A and B |
waves/B9\codex-plan-consult-r1.md:1791:**For Tier A + B (179 tables):**
waves/B9\codex-plan-consult-r1.md:1816:| Tier A: 113 tables Ã— 20 min | 37.7h |
waves/B9\codex-plan-consult-r1.md:1821:| FDW manifest expansion (setup_fdw.sh + testing) | 4h |
waves/B9\codex-plan-consult-r1.md:1823:| Integration testing (load against real zip, verify row counts vs RECORD\_COUNTS.TXT) | 8h |
waves/B9\codex-plan-consult-r1.md:1829:- B9.1 (Tier A, 113 tables): ~10 sessions
waves/B9\codex-plan-consult-r1.md:1836:**Realistic wall-clock:** 3â€“4 months for B9.1 through B9.3. Consider whether B9 is actually two waves (B9 = Tier A+B; B10 = Tier C) for milestone hygiene.
waves/B9\codex-plan-consult-r1.md:1848:**Risk 3 â€” FDW LIMIT TO list maintenance drift (MEDIUM)**
waves/B9\codex-plan-consult-r1.md:1849:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-plan-consult-r1.md:1870:- Design the `FDBBulkIngester` (generic ingester for Tier A+B) â€” implementation-ready spec
waves/B9\codex-plan-consult-r1.md:1872:- Audit UPD zip structure: verify which tables ship as delta vs. full-replacement
waves/B9\codex-plan-consult-r1.md:1875:### B9.1 â€” Tier A: 113 simple lookup tables (target ~10 sessions)
waves/B9\codex-plan-consult-r1.md:1879:- One alembic migration `0009_fdb_tier_a.py`
waves/B9\codex-plan-consult-r1.md:1881:- Integration test: load against real DB zip, verify row counts vs RECORD\_COUNTS.TXT for all 113 tables
waves/B9\codex-plan-consult-r1.md:1882:- FDW manifest update: add 113 table names to `setup_fdw.sh` LIMIT TO list
waves/B9\codex-plan-consult-r1.md:1883:- Gate: 100% tests pass, row counts match RECORD\_COUNTS.TXT within 1%
waves/B9\codex-plan-consult-r1.md:1891:- Integration test: verify NDC join correctness against existing `fdb_ndc_price_history`
waves/B9\codex-plan-consult-r1.md:1892:- FDW manifest update: +66 entries
waves/B9\codex-plan-consult-r1.md:1902:- FDW manifest update: +19 entries
waves/B9\codex-plan-consult-r1.md:1921:4. **Wave boundary â€” is B9 one wave or two?**: 34 sessions is 3â€“4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-plan-consult-r1.md:1930:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"SC-|R[1-7] \\||T[0-9]+|B9\\.[A-H]|FDW|283|284|fdb_weekly|fdb_initial|001[0-9]|migration|mini-GATE|Goal-backward|Threat model|Pre-execute|D2|MTL|RNP2|RPRDPP0|RNDC14|setup_fdw|collect-only|RECORD_COUNTS|session\" 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\plan.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-plan-consult-r1.md:1932:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"SC-|R[1-7] \\||B9\\.[A-H]|FDW|283|284|fdb_weekly|migration|mini-GATE|D2|MTL|RNP2|RPRDPP0|RNDC14|39 sessions|SPEC-locked\" 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\charter.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-plan-consult-r1.md:1934:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"220|217|113|66|19|MTL|FDW|currently|Current|RNP3|RPRDPTD0|RNPTYPD0|LIMIT TO|Tier classification|Tier C table inventory|Total|Migration|Recommendation|fdb_initial|fdb_weekly|mode\" 'C:\\Users\\MK\\Desktop\\Code Projects\\Werkbench\\projects\\infinityrx-platform\\waves\\B9\\recon.md'" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-plan-consult-r1.md:1938:15:2. **Per-phase scope, deliverables, success-criteria mapping, gate criteria, est sessions, commit shape** for B9.B..B9.H.
waves/B9\codex-plan-consult-r1.md:1942:19:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9\codex-plan-consult-r1.md:1944:24:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-plan-consult-r1.md:1948:35:2. **B7.2 Phase 11A COMPLETE** — `ifx_prod_app` gone; `pg_authid count=0`; `setup_fdw --verify 66/66` PASS in dev + mock. (Memory `project_phase11a_implemented.md`.)
waves/B9\codex-plan-consult-r1.md:1949:36:3. **Reference DB topology stable** — `infinityrx_reference` schemas `drug_database / drug_db / reference / shared` exist; current FDB tables `fdb_ndc_price_history` + `fdb_price_type_desc` present and queryable through FDW. (Phase 11A C9.)
waves/B9\codex-plan-consult-r1.md:1953:40:7. **FDB drop manifest reachable** — `data/reference/fdb/TEL251759D/RECORD_COUNTS.TXT` present and parseable (recon §1.5 verified — re-verify at C0).
waves/B9\codex-plan-consult-r1.md:1956:50:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
waves/B9\codex-plan-consult-r1.md:1962:62:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Per-phase the line count rises (66 → 179 after B9.B → 245 after B9.C → 264 after B9.D → 265 after B9.E → 267 after B9.F → 267 after B9.G schema-only — MTL counted → 283 after B9.H final verify). B9.H reconciles the final count to 283.
waves/B9\codex-plan-consult-r1.md:1963:63:- **`pytest --collect-only` baseline marker** — committed to `waves/B9/baseline.md` at C0; every phase mini-GATE-CLOSE re-runs and asserts count unchanged.
waves/B9\codex-plan-consult-r1.md:1965:69:| C0 | Baseline + invariants captured | `waves/B9/baseline.md`, evidence of `df -h`, `pg_authid`, FDW verify pass, pytest collect count |
waves/B9\codex-plan-consult-r1.md:1968:78:**B9.A mini-GATE-CLOSE criteria (charter SC-9):**
waves/B9\codex-plan-consult-r1.md:1971:82:- `setup_fdw.sh --verify` still 66/66 (no FDB tables added yet).
waves/B9\codex-plan-consult-r1.md:1972:88:### B9.B — Tier A: 113 simple lookup tables (≤ 5 columns, generic ingester) (10 sessions)
waves/B9\codex-plan-consult-r1.md:1975:95:- 1 batched alembic migration per 25 tables (4 migrations total across B9.B: `0009_fdb_tier_a_part1`..`0009d_fdb_tier_a_part4`) — alternative: a single `0009_fdb_tier_a.py` if review is tractable; codex PLAN consult decides
waves/B9\codex-plan-consult-r1.md:1978:103:- 1-4 alembic migrations (`0009_fdb_tier_a*`)
waves/B9\codex-plan-consult-r1.md:1981:111:- SC-2 (RECORD_COUNTS reconciliation) — every loaded Tier A table: actual ÷ expected within ±0.1% tolerance (small lookups should be exact)
waves/B9\codex-plan-consult-r1.md:1982:112:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
waves/B9\codex-plan-consult-r1.md:1983:113:- SC-7 (weekly idempotency) — verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9\codex-plan-consult-r1.md:1984:114:- SC-8 (test strategy) — contract + parity + reconciliation + sampled behavioral for ~10 random Tier A tables
waves/B9\codex-plan-consult-r1.md:1985:115:- SC-9 (mini-GATE-CLOSE) — see below
waves/B9\codex-plan-consult-r1.md:1986:117:**B9.B mini-GATE-CLOSE criteria:**
waves/B9\codex-plan-consult-r1.md:1987:119:- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` ± documented tolerance
waves/B9\codex-plan-consult-r1.md:1988:120:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9\codex-plan-consult-r1.md:1990:126:- Codex mini-GATE-CLOSE consult: GO
waves/B9\codex-plan-consult-r1.md:1993:134:**Scope:** Tables that key on NDC (11-digit National Drug Code) or GCN (Generic Code Number) and join to existing or B9.B tables. Includes drug-form linkages, route-product linkages, manufacturer relationships, dose-form mappings, GCN/GFC clinical linkages.
waves/B9\codex-plan-consult-r1.md:1994:136:**Per-session shape (12 sessions = ~5.5 tables/session — slower than Tier A because of join-design + FK-target verification per table):**
waves/B9\codex-plan-consult-r1.md:1996:139:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-plan-consult-r1.md:1999:150:- FDW foreign-table count: 179 → 245
waves/B9\codex-plan-consult-r1.md:2001:154:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-plan-consult-r1.md:2008:175:- FDW foreign-table count: 245 → 262
waves/B9\codex-plan-consult-r1.md:2010:180:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
waves/B9\codex-plan-consult-r1.md:2013:188:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9\codex-plan-consult-r1.md:2018:201:- FDW foreign-table count: 262 → 263
waves/B9\codex-plan-consult-r1.md:2020:205:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
waves/B9\codex-plan-consult-r1.md:2025:218:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline
waves/B9\codex-plan-consult-r1.md:2028:227:- FDW foreign-table count: 263 → 265
waves/B9\codex-plan-consult-r1.md:2030:231:**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4:**
waves/B9\codex-plan-consult-r1.md:2031:236:- FDW + Postgres verify after indexes built: completes within 5 min
waves/B9\codex-plan-consult-r1.md:2032:238:- Codex mini-GATE-CLOSE consult: GO; codex specifically reviews EXPLAIN ANALYZE output for index gaps
waves/B9\codex-plan-consult-r1.md:2042:261:- FDW foreign-table count: 265 → 284 (MTL tables ARE in FDW even though data isn't loaded — they exist as foreign-table entries pointing at empty reference tables)
waves/B9\codex-plan-consult-r1.md:2043:263:**Note on FDW count:** 284 not 283. Recon's target was 283 across 220 - 3 already covered tables = wait, re-checking — actually B9.A's expansion path showed 283 final count. Let me re-derive: 66 (current) + 113 (B9.B) + 66 (B9.C) + 17 (B9.D) + 1 (B9.E RNDC14) + 2 (B9.F RNP2+RPRDPP0) + 19 (B9.G MTL schema-only) = 284. **The 283 figure in the charter is wrong by 1; B9.H reconciles to the true 284.** This is a charter erratum to surface to codex PLAN consult.
waves/B9\codex-plan-consult-r1.md:2045:267:**B9.G mini-GATE-CLOSE criteria:**
waves/B9\codex-plan-consult-r1.md:2047:272:- Codex mini-GATE-CLOSE consult: GO; codex specifically verifies that flipping `fdb_load_mtl=False` after data load DOES NOT delete data (idempotency direction check)
waves/B9\codex-plan-consult-r1.md:2049:278:**Scope:** Reconcile `infrastructure/scripts/lib/expected_reference_tables.txt` to the true final count, run final FDW verify, produce evidence + ship artifacts + memory updates, dispatch final B9 GATE-CLOSE codex consult.
waves/B9\codex-plan-consult-r1.md:2052:283:- Session 2: Final `setup_fdw.sh --verify` 284/284 in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables; published in `waves/B9/evidence.md`
waves/B9\codex-plan-consult-r1.md:2054:290:- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
waves/B9\codex-plan-consult-r1.md:2061:304:- SC-6: `setup_fdw.sh --verify` final count PASS in dev + mock
waves/B9\codex-plan-consult-r1.md:2064:307:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9\codex-plan-consult-r1.md:2070:322:| SC-2 | `waves/B9/evidence.md` table: per-table actual vs. expected row count, tolerance column, PASS/FAIL column | B9.H Session 2 |
waves/B9\codex-plan-consult-r1.md:2071:323:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9\codex-plan-consult-r1.md:2074:326:| SC-6 | `setup_fdw.sh --verify` output 284/284 in dev + mock (or 283/283 if reconciled to charter count) | B9.H Session 2 |
waves/B9\codex-plan-consult-r1.md:2077:329:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
waves/B9\codex-plan-consult-r1.md:2081:339:| T1 | latin-1 decode failures on text-heavy Tier A/B tables (recon §7 Risk 4) | MED | MED | B9.A C3 contract test includes decode smoke on first 1000 rows of text-heavy tables; failures block the migration |
waves/B9\codex-plan-consult-r1.md:2082:340:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9\codex-plan-consult-r1.md:2084:342:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
waves/B9\codex-plan-consult-r1.md:2087:345:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
waves/B9\codex-plan-consult-r1.md:2088:346:| T8 | Migration batched files become un-reviewable (~25 tables each) | LOW | MED | Generated migration template produces deterministic, ordered, alphabetized output for diff-friendly review; codex PLAN consult specifically asked to verify migration shape |
waves/B9\codex-plan-consult-r1.md:2089:347:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
waves/B9\codex-plan-consult-r1.md:2090:348:| T10 | Test count baseline drifts (134 pre-existing failures become 135 or 200) | MED | MED | B9.A C0 captures `pytest --collect-only` count; each phase mini-GATE-CLOSE asserts count unchanged ± new contract tests |
waves/B9\codex-plan-consult-r1.md:2091:349:| T11 | Reference DB FDW + write semantics conflict (writing to a foreign table) | LOW | HIGH | All writes go to `infinityrx_reference` directly via loader; foreign-table access in env DBs is read-only per Phase 11A pattern. B9.B C1 verifies no INSERT statement targets a foreign table. |
waves/B9\codex-plan-consult-r1.md:2096:361:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
waves/B9\codex-plan-consult-r1.md:2097:362:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-plan-consult-r1.md:2098:363:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 17 ingested | `codex-mini-gate-close-D.md` |
waves/B9\codex-plan-consult-r1.md:2099:364:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9\codex-plan-consult-r1.md:2100:365:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9\codex-plan-consult-r1.md:2101:366:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9\codex-plan-consult-r1.md:2105:389:1. **FDW final count: 283 vs 284.** Charter says 283; PLAN's tier-additive derivation gives 284 (66 + 113 + 66 + 17 + 1 + 2 + 19 = 284). The charter figure may have netted the 3 already-covered FDB pricing tables differently. Codex PLAN consult should reconcile before B9.B opens.
waves/B9\codex-plan-consult-r1.md:2106:390:2. **Migration count: 5 vs 6.** Charter says "0009..0014" (6 migrations); PLAN sub-counts Tier A and Tier B each into ~3-4 part files, which inflates the migration count to 9-10. Codex PLAN consult should rule on batching shape: single big file per tier OR per-25 part files.
waves/B9\codex-plan-consult-r1.md:2107:391:3. **Loader-orchestration modes: existing vs new.** Charter implies `--mode fdb_weekly` exists; recon shows existing loader has `--mode fdb_initial` only. PLAN assumes both exist; B9.A C4 must verify or add `--mode fdb_weekly`.
waves/B9\codex-plan-consult-r1.md:2110:400:- At each mini-GATE-CLOSE: full sign-off sheet committed
waves/B9\codex-plan-consult-r1.md:2123:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-plan-consult-r1.md:2124:15:- The FDW `LIMIT TO` allowlist in `setup_fdw.sh` currently names 2 FDB tables. Adding 217 more requires a structured FDW manifest expansion — this is a one-time setup change, not per-deployment.
waves/B9\codex-plan-consult-r1.md:2142:114:**FDW manifest impact:** `setup_fdw.sh` uses `IMPORT FOREIGN SCHEMA ... LIMIT TO (...)` with a dynamic list. Currently 2 FDB table names are in scope for drug\_database. B9 full coverage would expand this list by 217 entries.
waves/B9\codex-plan-consult-r1.md:2155:173:- `0009_fdb_tier_a.py` — 113 Tier A tables (all small; one migration is reviewable because models are uniform 2–5-col descriptors)
waves/B9\codex-plan-consult-r1.md:2159:180:- Tier A tables are structurally uniform (code/desc pattern); 113 in one migration is reviewable.
waves/B9\codex-plan-consult-r1.md:2165:223:| Tier A: 113 tables × 20 min | 37.7h |
waves/B9\codex-plan-consult-r1.md:2169:228:| FDW manifest expansion (setup_fdw.sh + testing) | 4h |
waves/B9\codex-plan-consult-r1.md:2170:236:- B9.1 (Tier A, 113 tables): ~10 sessions
waves/B9\codex-plan-consult-r1.md:2176:255:**Risk 3 — FDW LIMIT TO list maintenance drift (MEDIUM)**
waves/B9\codex-plan-consult-r1.md:2177:256:`setup_fdw.sh` uses a dynamic `LIMIT TO` allowlist. Adding 217 table names to this list is a one-time change, but the list must stay in sync with the actual schema. If a new FDB drop adds tables, the FDW will silently omit them. Mitigation: Auto-generate the LIMIT TO list from the ORM `metadata.tables` at setup time rather than maintaining a manual list.
waves/B9\codex-plan-consult-r1.md:2184:282:### B9.1 — Tier A: 113 simple lookup tables (target ~10 sessions)
waves/B9\codex-plan-consult-r1.md:2187:288:- Integration test: load against real DB zip, verify row counts vs RECORD\_COUNTS.TXT for all 113 tables
waves/B9\codex-plan-consult-r1.md:2188:289:- FDW manifest update: add 113 table names to `setup_fdw.sh` LIMIT TO list
waves/B9\codex-plan-consult-r1.md:2193:299:- FDW manifest update: +66 entries
waves/B9\codex-plan-consult-r1.md:2195:309:- FDW manifest update: +19 entries
waves/B9\codex-plan-consult-r1.md:2202:328:4. **Wave boundary — is B9 one wave or two?**: 34 sessions is 3–4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-plan-consult-r1.md:2210:31:| W5 | C0 baseline + D2 dry-run perf test + FDW manifest extension + closeout | n/a | ~4 sessions |
waves/B9\codex-plan-consult-r1.md:2212:44:B9 ships incrementally **with mandatory per-phase closure gates** — each phase (B9.B..B9.F) gets its own evidence + row-count reconciliation + migration review + FDW verify + test baseline comparison + mini-GATE-CLOSE consult. A single final GATE-CLOSE across 220 tables would catch drift too late.
waves/B9\codex-plan-consult-r1.md:2214:49:| B9.B | Tier A — 113 simple lookups via generic table-driven ingester | 10 | **B9.B mini-GATE-CLOSE** — evidence + row-count manifest + FDW verify 116/116 + ingester contract tests |
waves/B9\codex-plan-consult-r1.md:2215:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r1.md:2216:51:| B9.D | Tier C non-RNDC14 — 17 complex tables | 4 | **B9.D mini-GATE-CLOSE** |
waves/B9\codex-plan-consult-r1.md:2217:52:| B9.E | RNDC14 dedicated migration (68 cols) | 2 | **B9.E mini-GATE-CLOSE** — column-by-column model review |
waves/B9\codex-plan-consult-r1.md:2218:53:| B9.F | RNP2 + RPRDPP0 + C0 perf gate (D2 reversal) | 4 | **B9.F mini-GATE-CLOSE** — perf test results + EXPLAIN ANALYZE + storage budget verification |
waves/B9\codex-plan-consult-r1.md:2219:54:| B9.G | Tier D MTL schema-only + loader-registration safeguards | 3 | **B9.G mini-GATE-CLOSE** — integration test asserts zero MTL rows after default `load_fdb.py --mode fdb_weekly` |
waves/B9\codex-plan-consult-r1.md:2220:55:| B9.H | Manifest extension (66 → 283 FDW entries) + final closeout artifacts | 4 | **Final B9 GATE-CLOSE** — full cross-tier consult |
waves/B9\codex-plan-consult-r1.md:2222:62:| SC-2 | `RECORD_COUNTS.TXT` reconciliation: every LOADED table's row count matches FDB's expected ± documented tolerance (MTL excluded — schema-only) |
waves/B9\codex-plan-consult-r1.md:2223:63:| SC-3 | RNDC14 ingest covers all 68 columns with column-curation review at B9.E mini-GATE-CLOSE |
waves/B9\codex-plan-consult-r1.md:2224:64:| SC-4 | **D2 performance gate**: timed full-load dry run of RNP2_NDC_PRICE + RPRDPP0_PRODUCT_PRICE measured; representative `EXPLAIN ANALYZE` on indexed query patterns captured; Postgres + FDW verify completes within 5min after indexes built; weekly delta idempotency timing documented |
waves/B9\codex-plan-consult-r1.md:2226:66:| SC-6 | `setup_fdw.sh --verify` 283/283 PASS in both env DBs |
waves/B9\codex-plan-consult-r1.md:2229:69:| SC-9 | Each of B9.B..B9.G passes a mini-GATE-CLOSE consult before next phase opens |
waves/B9\codex-plan-consult-r1.md:2236:78:- **YES** per-phase batched migrations (`0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14`, `0012_fdb_rndc14`, `0013_fdb_pricing_big` for RNP2+RPRDPP0, `0014_fdb_mtl_schema`)
waves/B9\codex-plan-consult-r1.md:2237:79:- **RNDC14 migration MUST be standalone** (`0012_fdb_rndc14`) — 68 cols warrant dedicated review at B9.E mini-GATE-CLOSE
waves/B9\codex-plan-consult-r1.md:2239:86:| R2 | RNP2 + RPRDPP0 (1.16 GB) exhausts dev Postgres disk OR query performance regresses | C0: verify disk free; add indexes per actual query patterns; monitor pg_stat_user_tables size growth |
waves/B9\codex-plan-consult-r1.md:2242:89:| R5 | Tier C complex tables have foreign keys that don't validate after partial ingest | Defer FK constraints to phase-end; verify referential integrity at C8 |
waves/B9\codex-plan-consult-r1.md:2245:102:**~39 sessions × 4h = ~156 productive hours.** At 3 sessions/week: **~13 weeks (~3 months elapsed)**. With multitasking + non-B9 work: realistically 4-5 months elapsed. (Charter v1's 100-session figure was wrong — corrected per codex SPEC R1 #3; recon's actual estimate was always 34 sessions for A+B+C, not "Tier A only".)
waves/B9\codex-plan-consult-r1.md:2246:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r1.md:2975:shared\tests\events\conftest.py:28:    event-bus model tests exist to verify migration DDL, JSONB column
waves/B9\codex-plan-consult-r1.md:3034:modules\ebv-ebi-rtbc\src\api\routes\eligibility.py:41:@router.post("/eligibility/verify", response_model=EligibilityResponse)
waves/B9\codex-plan-consult-r1.md:3198:modules\core-platform\src\auth\api\auth_router.py:152:@router.post("/mfa/verify", response_model=TokenResponse)
waves/B9\codex-plan-consult-r1.md:4056:modules\adjudication-engine\tests\unit\test_listener_metrics_tls.py:150:        assert ctx.verify_mode == ssl.CERT_NONE
waves/B9\codex-plan-consult-r1.md:4057:modules\adjudication-engine\tests\unit\test_listener_metrics_tls.py:169:        assert ctx.verify_mode == ssl.CERT_REQUIRED
waves/B9\codex-plan-consult-r1.md:4331:modules\adjudication-engine\src\services\tcp_listener.py:125:        ctx.verify_mode = ssl.CERT_REQUIRED
waves/B9\codex-plan-consult-r1.md:4336:modules\adjudication-engine\src\services\tcp_listener (conflicted).py:128:        ctx.verify_mode = ssl.CERT_REQUIRED
waves/B9\codex-plan-consult-r1.md:5007:| 3 | Phase boundaries respect SPEC-locked granularity | PARTIAL | RNDC14 standalone is honored (`plan.md:184-205`), but Tier A/B part-file options inflate migrations to 9-10 (`plan.md:95,141,389-390`) despite charter locking per-phase batched migrations `0009..0014` (`charter.md:75-79`). |
waves/B9\codex-plan-consult-r1.md:5008:| 4 | Mini-GATE-CLOSE criteria concrete | YES | B9.B has counts/FDW/tests/idempotency (`plan.md:117-126`); B9.C inherits plus FK integrity (`plan.md:154`); B9.D/E/F/G add measurable audits/tests/perf gates (`plan.md:180,205,231-238,267-272`). |
waves/B9\codex-plan-consult-r1.md:5009:| 5 | D2 perf gate real | YES | B9.F requires timed dry-run, EXPLAIN ANALYZE, storage delta, FDW/Postgres verify under 5min, weekly delta timing (`plan.md:213-238`). |
waves/B9\codex-plan-consult-r1.md:5011:| 7 | Pre-execute invariants testable | YES | Invariants have concrete checks: commit/memory references, FDW verify, `df -h`, config flag location, `pytest --collect-only`, manifest parse, consult slots (`plan.md:30-44`). |
waves/B9\codex-plan-consult-r1.md:5012:| 8 | Session sizing realistic | DEFENSIBLE-BUT-RISKY | Tier A is explicitly aggressive at ~12 tables/session (`plan.md:92-128`); Tier B is more plausible at ~5.5/session with FK checks (`plan.md:136-154`). |
waves/B9\codex-plan-consult-r1.md:5013:| 9 | Commit chains executable | PARTIAL | B9.A C0-C7 in 2-3 sessions is crowded (`plan.md:52-85`), and B9.B/B9.C migration shape is unresolved inside execution (`plan.md:95,141`). |
waves/B9\codex-plan-consult-r1.md:5014:| 10 | Codex iteration plan complete | YES | SPEC R1/R2, PLAN R1, ADVERSARIAL, B9.B-G mini-closes, and final GATE-CLOSE are listed (`plan.md:357-367`). |
waves/B9\codex-plan-consult-r1.md:5020:| FDW count 283 vs 284 | **283 is right.** Recon: 220 FDB source tables, 3 already covered, 217-table gap (`recon.md:11,99`). FDW baseline has 66 entries and B9 adds 217, so 66 + 217 = 283. Plan’s 284 comes from a Tier C arithmetic bug: “19 except RNDC14/RNP2/RPRDPP0” is 16, not 17 (`plan.md:158-160,263-265`). Correct sequence: 66→179→245→261→262→264→283. | `recon.md:11,14,99,114`; `plan.md:62,158-160,261-265,282-283,389`; `charter.md:55,66`. |
waves/B9\codex-plan-consult-r1.md:5021:| Migration batching shape | Use the charter-locked **6 migration files**: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` with 16 tables, `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`. Do not split Tier A/B into 25-table part revisions unless SPEC is amended. | Charter locks this exact shape (`charter.md:75-79`). Recon says one Tier A migration is reviewable because tables are uniform (`recon.md:173-180`). Plan’s 9-10 option is unresolved (`plan.md:95,141,389-390`). |
waves/B9\codex-plan-consult-r1.md:5022:| Loader modes | Existing loader already supports both `fdb_initial` and `fdb_weekly`; B9.A does **not** need to add `fdb_weekly`. It may need to add new tier/MTL modes if the plan keeps `fdb_tier_a`, `fdb_tier_b`, and `fdb_mtl_data`. | `scripts/load_fdb.py:5-9,68-69`; plan erratum is stale at `plan.md:391`. |
waves/B9\codex-plan-consult-r1.md:5037:- HIGH: Tier C arithmetic error: `19 - 3 = 16`, not 17. This causes the false 284 FDW count, `cum 218/217`, and incorrect phase count ladder.
waves/B9\codex-plan-consult-r1.md:5044:GO-WITH-FIXES. Produce PLAN v2 before ADVERSARIAL: correct Tier C non-special count to 16, reconcile all FDW/SC-1 counts to 283 final FDW entries, lock migrations to the 6 SPEC-approved files, fix the loader-mode erratum, add a real weekly-delta schema/UPD-format guard, and explain the 42-vs-39 session delta or reduce the plan back to the charter budget.
waves/B9\codex-plan-consult-r1.md:5057:| 3 | Phase boundaries respect SPEC-locked granularity | PARTIAL | RNDC14 standalone is honored (`plan.md:184-205`), but Tier A/B part-file options inflate migrations to 9-10 (`plan.md:95,141,389-390`) despite charter locking per-phase batched migrations `0009..0014` (`charter.md:75-79`). |
waves/B9\codex-plan-consult-r1.md:5058:| 4 | Mini-GATE-CLOSE criteria concrete | YES | B9.B has counts/FDW/tests/idempotency (`plan.md:117-126`); B9.C inherits plus FK integrity (`plan.md:154`); B9.D/E/F/G add measurable audits/tests/perf gates (`plan.md:180,205,231-238,267-272`). |
waves/B9\codex-plan-consult-r1.md:5059:| 5 | D2 perf gate real | YES | B9.F requires timed dry-run, EXPLAIN ANALYZE, storage delta, FDW/Postgres verify under 5min, weekly delta timing (`plan.md:213-238`). |
waves/B9\codex-plan-consult-r1.md:5061:| 7 | Pre-execute invariants testable | YES | Invariants have concrete checks: commit/memory references, FDW verify, `df -h`, config flag location, `pytest --collect-only`, manifest parse, consult slots (`plan.md:30-44`). |
waves/B9\codex-plan-consult-r1.md:5062:| 8 | Session sizing realistic | DEFENSIBLE-BUT-RISKY | Tier A is explicitly aggressive at ~12 tables/session (`plan.md:92-128`); Tier B is more plausible at ~5.5/session with FK checks (`plan.md:136-154`). |
waves/B9\codex-plan-consult-r1.md:5063:| 9 | Commit chains executable | PARTIAL | B9.A C0-C7 in 2-3 sessions is crowded (`plan.md:52-85`), and B9.B/B9.C migration shape is unresolved inside execution (`plan.md:95,141`). |
waves/B9\codex-plan-consult-r1.md:5064:| 10 | Codex iteration plan complete | YES | SPEC R1/R2, PLAN R1, ADVERSARIAL, B9.B-G mini-closes, and final GATE-CLOSE are listed (`plan.md:357-367`). |
waves/B9\codex-plan-consult-r1.md:5070:| FDW count 283 vs 284 | **283 is right.** Recon: 220 FDB source tables, 3 already covered, 217-table gap (`recon.md:11,99`). FDW baseline has 66 entries and B9 adds 217, so 66 + 217 = 283. Plan’s 284 comes from a Tier C arithmetic bug: “19 except RNDC14/RNP2/RPRDPP0” is 16, not 17 (`plan.md:158-160,263-265`). Correct sequence: 66→179→245→261→262→264→283. | `recon.md:11,14,99,114`; `plan.md:62,158-160,261-265,282-283,389`; `charter.md:55,66`. |
waves/B9\codex-plan-consult-r1.md:5071:| Migration batching shape | Use the charter-locked **6 migration files**: `0009_fdb_tier_a`, `0010_fdb_tier_b`, `0011_fdb_tier_c_minus_rndc14` with 16 tables, `0012_fdb_rndc14`, `0013_fdb_pricing_big`, `0014_fdb_mtl_schema`. Do not split Tier A/B into 25-table part revisions unless SPEC is amended. | Charter locks this exact shape (`charter.md:75-79`). Recon says one Tier A migration is reviewable because tables are uniform (`recon.md:173-180`). Plan’s 9-10 option is unresolved (`plan.md:95,141,389-390`). |
waves/B9\codex-plan-consult-r1.md:5072:| Loader modes | Existing loader already supports both `fdb_initial` and `fdb_weekly`; B9.A does **not** need to add `fdb_weekly`. It may need to add new tier/MTL modes if the plan keeps `fdb_tier_a`, `fdb_tier_b`, and `fdb_mtl_data`. | `scripts/load_fdb.py:5-9,68-69`; plan erratum is stale at `plan.md:391`. |
waves/B9\codex-plan-consult-r1.md:5087:- HIGH: Tier C arithmetic error: `19 - 3 = 16`, not 17. This causes the false 284 FDW count, `cum 218/217`, and incorrect phase count ladder.
waves/B9\codex-plan-consult-r1.md:5094:GO-WITH-FIXES. Produce PLAN v2 before ADVERSARIAL: correct Tier C non-special count to 16, reconcile all FDW/SC-1 counts to 283 final FDW entries, lock migrations to the 6 SPEC-approved files, fix the loader-mode erratum, add a real weekly-delta schema/UPD-format guard, and explain the 42-vs-39 session delta or reduce the plan back to the charter budget.

 succeeded in 655ms:
modules/drug-database/tests\_fdb_delta_semantics.py:5:and asserts post-step state per `DeltaSemantics`. The simulator is
modules/drug-database/tests\_fdb_delta_semantics.py:159:                            stmt = stmt.on_conflict_do_update(
modules/drug-database/tests\_fdb_delta_semantics.py:165:                            stmt = stmt.on_conflict_do_nothing(
modules/drug-database/tests\_fdb_delta_semantics.py:170:                        stmt = stmt.on_conflict_do_nothing(
modules/drug-database/tests\_fdb_contract.py:43:                                    DeltaSemantics class. UNKNOWN +
modules/drug-database/tests\_fdb_contract.py:70:    DeltaSemantics,
modules/drug-database/tests\_fdb_contract.py:540:    if spec.delta_semantics in {DeltaSemantics.UNKNOWN, DeltaSemantics.TRUNCATE_RELOAD}:
modules/drug-database/tests\_fdb_contract.py:559:    if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
modules/drug-database/tests\_fdb_contract.py:567:    if spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY:
modules/drug-database/tests\_fdb_contract.py:594:    if spec.delta_semantics is DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE:
modules/drug-database/tests\unit\test_fdb_adapter.py:46:    DeltaSemantics,
modules/drug-database/tests\unit\test_fdb_adapter.py:559:# B9.A C1 — TableSpec registry expansion: Tier + DeltaSemantics + 4 new fields
modules/drug-database/tests\unit\test_fdb_adapter.py:573:    """DeltaSemantics taxonomy per codex ADVERSARIAL R1 A4 mitigation."""
modules/drug-database/tests\unit\test_fdb_adapter.py:574:    assert DeltaSemantics.APPEND_ONLY.value == "APPEND_ONLY"
modules/drug-database/tests\unit\test_fdb_adapter.py:575:    assert DeltaSemantics.UPSERT_BY_NATURAL_KEY.value == "UPSERT_BY_NATURAL_KEY"
modules/drug-database/tests\unit\test_fdb_adapter.py:576:    assert DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE.value == "UPSERT_WITH_EFFECTIVE_DATE"
modules/drug-database/tests\unit\test_fdb_adapter.py:577:    assert DeltaSemantics.TRUNCATE_RELOAD.value == "TRUNCATE_RELOAD"
modules/drug-database/tests\unit\test_fdb_adapter.py:578:    assert DeltaSemantics.UNKNOWN.value == "UNKNOWN"
modules/drug-database/tests\unit\test_fdb_adapter.py:585:    NOT declare tier / record_counts_key / loader_group /
modules/drug-database/tests\unit\test_fdb_adapter.py:592:        assert spec.loader_group is None, spec.table_name
modules/drug-database/tests\unit\test_fdb_adapter.py:593:        assert spec.delta_semantics is DeltaSemantics.UNKNOWN, spec.table_name
modules/drug-database/tests\unit\test_fdb_adapter.py:597:    """New B9 TableSpecs can declare tier + delta + loader_group + record_counts_key."""
modules/drug-database/tests\unit\test_fdb_adapter.py:604:        loader_group="fdb_tier_a",
modules/drug-database/tests\unit\test_fdb_adapter.py:605:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests\unit\test_fdb_adapter.py:609:    assert spec.loader_group == "fdb_tier_a"
modules/drug-database/tests\unit\test_fdb_adapter.py:610:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY
modules/drug-database/tests\unit\test_fdb_delta_semantics.py:19:    DeltaSemantics,
modules/drug-database/tests\unit\test_fdb_delta_semantics.py:51:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests\unit\test_fdb_delta_semantics.py:72:def test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing(
modules/drug-database/tests\unit\test_fdb_delta_semantics.py:87:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests\unit\test_fdb_delta_semantics.py:122:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests\unit\test_fdb_delta_semantics.py:156:        delta_semantics=DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
modules/drug-database/tests\unit\test_fdb_delta_semantics.py:190:        delta_semantics=DeltaSemantics.UNKNOWN,
modules/drug-database/tests\unit\test_fdb_delta_semantics.py:213:        delta_semantics=DeltaSemantics.TRUNCATE_RELOAD,
modules/drug-database/tests\unit\test_fdb_contract.py:19:    DeltaSemantics,
modules/drug-database/tests\unit\test_fdb_contract.py:53:    delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests\unit\test_fdb_contract.py:452:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests\unit\test_fdb_contract.py:470:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests\unit\test_fdb_contract.py:489:        delta_semantics=DeltaSemantics.UNKNOWN,
modules/drug-database/tests\unit\test_fdb_contract.py:509:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests\unit\test_fdb_contract.py:533:        delta_semantics=DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:8:  REGISTERED_SPECS` whose `delta_semantics` is in the checkable set
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:15:spec to `REGISTERED_SPECS` ALSO appends to `CONTRACT_TESTED_SPECS`
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:26:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:27:from drug_database.services.fdb_specs import REGISTERED_SPECS
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:32:    DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:33:    DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:34:    DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:42:# across all `test_fdb_tier_a_batch_*.py` modules in the same package.
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:46:# REGISTERED_SPECS with delta_semantics=UNKNOWN — they predate the
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:54:    starts with `test_fdb_tier_a_batch_`. Imports each, reads its
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:71:        if not info.name.startswith("test_fdb_tier_a_batch_"):
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:100:        s.table_name for s in REGISTERED_SPECS
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:116:    """A name in CONTRACT_TESTED_SPECS that is NOT in REGISTERED_SPECS = stale.
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:123:    registered_names = {s.table_name for s in REGISTERED_SPECS}
modules/drug-database/tests\unit\test_fdb_contract_coverage.py:127:        f"(in coverage set but NOT in REGISTERED_SPECS): {sorted(stale)}. "
modules/drug-database/tests\unit\test_fdb_pricing_ingester.py:412:def test_replay_uses_on_conflict_do_nothing(initial_drop, db_session):
modules/drug-database/tests\unit\test_fdb_loader_registry.py:8:  2. The `filter_loadable_specs` helper excludes `loader_group="fdb_mtl"`
modules/drug-database/tests\unit\test_fdb_loader_registry.py:15:     `loader_group="fdb_mtl"`, or flips the default flag to True.
modules/drug-database/tests\unit\test_fdb_loader_registry.py:27:    DeltaSemantics,
modules/drug-database/tests\unit\test_fdb_loader_registry.py:47:    delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/tests\unit\test_fdb_loader_registry.py:48:    # loader_group=None — Phase 09 backward-compat
modules/drug-database/tests\unit\test_fdb_loader_registry.py:56:    loader_group="fdb_tier_a",
modules/drug-database/tests\unit\test_fdb_loader_registry.py:64:    loader_group="fdb_tier_b",
modules/drug-database/tests\unit\test_fdb_loader_registry.py:72:    loader_group="fdb_tier_c",
modules/drug-database/tests\unit\test_fdb_loader_registry.py:80:    loader_group=MTL_LOADER_GROUP,
modules/drug-database/tests\unit\test_fdb_loader_registry.py:154:    """only_groups=['fdb_tier_a'] → only Tier A specs returned."""
modules/drug-database/tests\unit\test_fdb_loader_registry.py:156:        _ALL_SPECS, fdb_load_mtl=False, only_groups=["fdb_tier_a"]
modules/drug-database/tests\unit\test_fdb_loader_registry.py:184:    """loader_group=None specs always load (Phase 09 backward-compat)."""
modules/drug-database/tests\unit\test_fdb_loader_registry.py:220:    B9.G: now load-bearing (19 MTL specs registered with loader_group=
modules/drug-database/tests\unit\test_fdb_loader_registry.py:229:    `loader_group="fdb_mtl"` label (which would silently bypass the
modules/drug-database/tests\unit\test_fdb_loader_registry.py:234:    # Tier.D must have loader_group=MTL_LOADER_GROUP, AND under default
modules/drug-database/tests\unit\test_fdb_loader_registry.py:238:        assert spec.loader_group == MTL_LOADER_GROUP, (
modules/drug-database/tests\unit\test_fdb_loader_registry.py:240:            f"loader_group='fdb_mtl' or they bypass the MTL guard."
modules/drug-database/tests\unit\test_fdb_loader_registry.py:247:        "activation wave) or loader_group label is missing on a Tier D spec."
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:9:  test_spec_loader_group_is_fdb_tier_a       — loader_group invariant
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:22:from drug_database.services.fdb_tier_a.batch_02 import SPECS
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:156:# Spec sanity (Tier + loader_group + record_counts_key invariants)
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:170:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:171:    assert spec.loader_group == "fdb_tier_a", (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:172:        f"{spec.table_name}: loader_group={spec.loader_group!r}; "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:173:        f"every Tier A spec MUST set loader_group='fdb_tier_a' so the "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_02.py:174:        f"registry's tier-aware filter includes it on `--mode fdb_tier_a`."
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:3:Mirrors the canonical template in test_fdb_tier_a_batch_01.py.
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:13:  test_spec_loader_group_is_fdb_tier_a      — loader_group correct
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:25:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:26:from drug_database.services.fdb_tier_a.batch_03 import SPECS
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:124:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:159:# Spec sanity (Tier + loader_group + record_counts_key invariants)
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:173:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:174:    assert spec.loader_group == "fdb_tier_a", (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:175:        f"{spec.table_name}: loader_group={spec.loader_group!r}; "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:176:        f"every Tier A spec MUST set loader_group='fdb_tier_a' so the "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_03.py:177:        f"registry's tier-aware filter includes it on `--mode fdb_tier_a`."
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:9:  test_spec_loader_group_is_fdb_tier_a       — loader_group invariant
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:22:from drug_database.services.fdb_tier_a.batch_04 import SPECS
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:156:# Spec sanity (Tier + loader_group + record_counts_key invariants)
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:170:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:171:    assert spec.loader_group == "fdb_tier_a", (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:172:        f"{spec.table_name}: loader_group={spec.loader_group!r}; "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:173:        f"every Tier A spec MUST set loader_group='fdb_tier_a' so the "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_04.py:174:        f"registry's tier-aware filter includes it on `--mode fdb_tier_a`."
modules/drug-database/tests\unit\test_fdb_tier_a_batch_01.py:33:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_01.py:34:from drug_database.services.fdb_tier_a.batch_01 import SPECS
modules/drug-database/tests\unit\test_fdb_tier_a_batch_01.py:126:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_01.py:155:# Spec sanity (Tier + loader_group + record_counts_key invariants)
modules/drug-database/tests\unit\test_fdb_tier_a_batch_01.py:169:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_01.py:170:    assert spec.loader_group == "fdb_tier_a", (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_01.py:171:        f"{spec.table_name}: loader_group={spec.loader_group!r}; "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_01.py:172:        f"every Tier A spec MUST set loader_group='fdb_tier_a' so the "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_01.py:173:        f"registry's tier-aware filter includes it on `--mode fdb_tier_a`."
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:3:Mirrors the canonical pattern in test_fdb_tier_a_batch_01.py. One
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:15:  test_spec_loader_group_is_fdb_tier_a      — loader_group invariant
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:27:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:28:from drug_database.services.fdb_tier_a.batch_05 import SPECS
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:157:# Spec sanity (Tier + loader_group + record_counts_key invariants)
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:171:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:172:    assert spec.loader_group == "fdb_tier_a", (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:173:        f"{spec.table_name}: loader_group={spec.loader_group!r}; "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:174:        f"every Tier A spec MUST set loader_group='fdb_tier_a' so the "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_05.py:175:        f"registry's tier-aware filter includes it on `--mode fdb_tier_a`."
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:9:  test_spec_loader_group_is_fdb_tier_a       — loader_group invariant
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:22:from drug_database.services.fdb_tier_a.batch_06 import SPECS
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:156:# Spec sanity (Tier + loader_group + record_counts_key invariants)
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:170:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:171:    assert spec.loader_group == "fdb_tier_a", (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:172:        f"{spec.table_name}: loader_group={spec.loader_group!r}; "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:173:        f"every Tier A spec MUST set loader_group='fdb_tier_a' so the "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_06.py:174:        f"registry's tier-aware filter includes it on `--mode fdb_tier_a`."
modules/drug-database/tests\integration\test_phase09_compat_baseline.py:54:    # async driver doesn't work for sync engine — mirror load_fdb.py
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:9:  test_spec_loader_group_is_fdb_tier_a       — loader_group invariant
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:21:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:22:from drug_database.services.fdb_tier_a.batch_07 import SPECS
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:121:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:156:# Spec sanity (Tier + loader_group + record_counts_key invariants)
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:170:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:171:    assert spec.loader_group == "fdb_tier_a", (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:172:        f"{spec.table_name}: loader_group={spec.loader_group!r}; "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:173:        f"every Tier A spec MUST set loader_group='fdb_tier_a' so the "
modules/drug-database/tests\unit\test_fdb_tier_a_batch_07.py:174:        f"registry's tier-aware filter includes it on `--mode fdb_tier_a`."
modules/drug-database/tests\unit\test_fdb_tier_a_batch_08.py:24:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_08.py:25:from drug_database.services.fdb_tier_a.batch_08 import SPECS, NATURAL_KEY_COUNT
modules/drug-database/tests\unit\test_fdb_tier_a_batch_08.py:90:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_08.py:133:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_08.py:134:    assert spec.loader_group == "fdb_tier_a"
modules/drug-database/tests\unit\test_fdb_tier_a_batch_09.py:17:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_09.py:18:from drug_database.services.fdb_tier_a.batch_09 import SPECS
modules/drug-database/tests\unit\test_fdb_tier_a_batch_09.py:85:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_09.py:130:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_09.py:131:    assert spec.loader_group == "fdb_tier_a"
modules/drug-database/tests\unit\test_fdb_tier_a_batch_09.py:142:    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY
modules/drug-database/tests\unit\test_fdb_tier_a_batch_10.py:13:    simulator falls through to `on_conflict_do_nothing` because
modules/drug-database/tests\unit\test_fdb_tier_a_batch_10.py:30:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_10.py:31:from drug_database.services.fdb_tier_a.batch_10 import SPECS, NATURAL_KEY_COUNT
modules/drug-database/tests\unit\test_fdb_tier_a_batch_10.py:102:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_10.py:141:        # column exists. The simulator falls back to on_conflict_do_nothing.
modules/drug-database/tests\unit\test_fdb_tier_a_batch_10.py:201:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_10.py:202:    assert spec.loader_group == "fdb_tier_a"
modules/drug-database/tests\unit\test_fdb_tier_a_batch_11.py:38:from drug_database.services.fdb_adapter import DeltaSemantics
modules/drug-database/tests\unit\test_fdb_tier_a_batch_11.py:39:from drug_database.services.fdb_tier_a.batch_11 import SPECS, NATURAL_KEY_COUNT
modules/drug-database/tests\unit\test_fdb_tier_a_batch_11.py:127:    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
modules/drug-database/tests\unit\test_fdb_tier_a_batch_11.py:242:def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
modules/drug-database/tests\unit\test_fdb_tier_a_batch_11.py:243:    assert spec.loader_group == "fdb_tier_a"
modules/drug-database/drug_database\services\fda_supplementary_ingestion.py:165:                stmt = stmt.on_conflict_do_update(
modules/drug-database/drug_database\services\fda_supplementary_ingestion.py:326:                    stmt = stmt.on_conflict_do_update(
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:27:    DeltaSemantics,
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:79:        loader_group="fdb_tier_a",
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:80:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:90:        revision_id="0009_fdb_tier_a",
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:102:        revision_id="0009_fdb_tier_a",
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:105:    assert 'revision: str = "0009_fdb_tier_a"' in src
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:119:        revision_id="0009_fdb_tier_a",
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:136:        revision_id="0009_fdb_tier_a",
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:152:            revision_id="0009_fdb_tier_a",
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:169:            revision_id="0009_fdb_tier_a",
modules/drug-database/tests\unit\test_gen_fdb_tier_migration.py:179:        revision_id="0009_fdb_tier_a",
modules/drug-database/drug_database\services\fdb_adapter.py:168:class DeltaSemantics(Enum):
modules/drug-database/drug_database\services\fdb_adapter.py:225:      loader_group:       tier-loader registration label
modules/drug-database/drug_database\services\fdb_adapter.py:226:                          (e.g., "fdb_tier_a" — loaders register by group).
modules/drug-database/drug_database\services\fdb_adapter.py:243:    loader_group: str | None = None
modules/drug-database/drug_database\services\fdb_adapter.py:244:    delta_semantics: DeltaSemantics = DeltaSemantics.UNKNOWN
modules/drug-database/drug_database\services\fdb_loader_registry.py:3:The registry filters a list of `TableSpec`s by `loader_group` and
modules/drug-database/drug_database\services\fdb_loader_registry.py:7:  loader_group="fdb_mtl"  +  FDB_LOAD_MTL=False (default) → EXCLUDED
modules/drug-database/drug_database\services\fdb_loader_registry.py:8:  loader_group="fdb_mtl"  +  FDB_LOAD_MTL=True            → INCLUDED
modules/drug-database/drug_database\services\fdb_loader_registry.py:9:  loader_group=<anything> +  any flag value               → INCLUDED
modules/drug-database/drug_database\services\fdb_loader_registry.py:25:Phase 09 backward-compat: loader_group is None for the 3 pre-B9
modules/drug-database/drug_database\services\fdb_loader_registry.py:50:            loader_group is in this list. None means "all groups
modules/drug-database/drug_database\services\fdb_loader_registry.py:55:        loader_group=None) are always included unless `only_groups`
modules/drug-database/drug_database\services\fdb_loader_registry.py:65:        if spec.loader_group == MTL_LOADER_GROUP and not fdb_load_mtl:
modules/drug-database/drug_database\services\fdb_loader_registry.py:68:            if spec.loader_group not in only_groups:
modules/drug-database/drug_database\services\fdb_loader_registry.py:81:    return [s for s in specs if s.loader_group == MTL_LOADER_GROUP]
modules/drug-database/drug_database\services\fdb_specs.py:20:  For every spec in REGISTERED_SPECS whose delta_semantics is in
modules/drug-database/drug_database\services\fdb_specs.py:28:from drug_database.services.fdb_tier_a import TIER_A_SPECS
modules/drug-database/drug_database\services\fdb_specs.py:31:# Tier A: auto-aggregated from `fdb_tier_a.batch_*` modules so parallel
modules/drug-database/drug_database\services\fdb_specs.py:37:REGISTERED_SPECS: list[TableSpec] = list(TIER_A_SPECS)
modules/drug-database/drug_database\services\fdb_specs.py:40:__all__ = ["REGISTERED_SPECS"]
modules/drug-database/drug_database\services\fdb_pricing_ingester.py:383:          Postgres — pg_insert().on_conflict_do_nothing(constraint=
modules/drug-database/drug_database\services\fdb_pricing_ingester.py:387:          SQLite   — sqlite_insert().on_conflict_do_nothing(index_elements=
modules/drug-database/drug_database\services\fdb_pricing_ingester.py:431:                .on_conflict_do_nothing(constraint="uq_fdb_ndc_price_history")
modules/drug-database/drug_database\services\fdb_pricing_ingester.py:438:                .on_conflict_do_nothing(index_elements=list(self._UC_COLUMNS))
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:8:  * Each TableSpec sets: tier=Tier.A, loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:28:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:42:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:44:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:52:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:54:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:62:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:64:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:73:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:75:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:86:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:88:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:96:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:98:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:107:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:121:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:123:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:132:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:134:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:143:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:145:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:154:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:156:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:164:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_01.py:166:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:11:  * tier=Tier.A, loader_group="fdb_tier_a"
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:12:  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:22:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:35:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:37:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:45:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:47:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:59:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:61:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:81:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:83:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:91:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:93:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:104:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:106:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:117:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:119:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:130:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:132:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:143:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:145:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:153:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_03.py:155:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:15:  * loader_group="fdb_tier_a"
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:16:  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:24:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:41:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:43:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:52:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:54:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:63:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:65:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:79:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:81:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:96:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:98:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:107:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:120:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:122:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:142:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:144:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:155:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:157:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:165:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_02.py:167:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:22:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:38:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:40:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:51:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:53:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:64:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:66:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:77:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:79:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:99:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:101:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:113:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:115:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:126:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:128:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:141:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:143:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:162:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:164:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:183:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_04.py:185:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:25:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:43:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:45:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:56:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:58:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:81:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:83:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:94:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:96:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:107:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:120:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:122:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:133:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:135:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:146:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:148:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:159:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:161:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:180:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_05.py:182:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:22:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:38:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:40:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:56:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:58:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:77:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:79:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:96:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:98:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:119:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:121:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:139:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:141:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:158:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:160:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:171:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:173:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:194:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:196:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:216:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_06.py:218:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:22:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:39:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:41:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:56:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:58:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:70:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:72:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:84:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:86:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:100:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:102:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:114:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:116:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:128:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:130:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:142:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:144:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:156:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:158:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:170:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_07.py:172:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:23:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:46:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:48:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:61:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:63:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:83:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:85:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:103:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:105:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:123:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_08.py:125:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:37:simulator's `on_conflict_do_nothing` fallback for all-NK tables).
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:49:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:70:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:72:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:88:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:90:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:106:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:108:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:126:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:128:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:146:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:148:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:166:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:168:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:184:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:186:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:202:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:204:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:222:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:224:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:243:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:245:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:262:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_10.py:264:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:22:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:49:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:72:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:95:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:110:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:129:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:143:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:157:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:175:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:27:    DeltaSemantics,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:54:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:56:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:75:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:77:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:97:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:99:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:122:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:124:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:147:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:149:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:166:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:168:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:183:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:185:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:200:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:202:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:217:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:219:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:241:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:243:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:258:        loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\batch_11.py:260:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database\services\fdb_tier_a\__init__.py:10:    # drug_database/services/fdb_tier_a/batch_NN.py
modules/drug-database/drug_database\services\fdb_tier_a\__init__.py:12:        DeltaSemantics, TableSpec, Tier,
modules/drug-database/drug_database\services\fdb_tier_a\__init__.py:21:            loader_group="fdb_tier_a",
modules/drug-database/drug_database\services\fdb_tier_a\__init__.py:23:            delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
scripts\load_fdb.py:18:    python scripts/load_fdb.py --mode fdb_weekly
scripts\load_fdb.py:19:    python scripts/load_fdb.py --mode fdb_initial --dry-run
scripts\load_fdb.py:43:logger = logging.getLogger("load_fdb")

 succeeded in 666ms:
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:16:    Decimal money columns and no Date columns (those are Tier B/C).
waves/B9\B9.B-charter.md:102:B9.B close consult. Next: B9.C — 66 NDC/GCN-keyed joins.
waves/B9\charter.md:28:| W2 | Tier B — NDC/GCN-keyed joins | 66 | ~12 sessions |
waves/B9\charter.md:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests (FDW 245/245) |
waves/B9\charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-adversarial-r1.md:123:| W2 | Tier B â€” NDC/GCN-keyed joins | 66 | ~12 sessions |
waves/B9\codex-adversarial-r1.md:145:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests (FDW 245/245) |
waves/B9\codex-adversarial-r1.md:201:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-adversarial-r1.md:236:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-adversarial-r1.md:344:### B9.C â€” Tier B: 66 NDC/GCN-keyed joins (12 sessions)
waves/B9\codex-adversarial-r1.md:351:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-adversarial-r1.md:353:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
waves/B9\codex-adversarial-r1.md:361:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\codex-adversarial-r1.md:364:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
waves/B9\codex-adversarial-r1.md:366:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-adversarial-r1.md:576:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-adversarial-r1.md:611:- **Charter Â§Workstreams view (39 sessions):** counts only productive ingest work â€” W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-adversarial-r1.md:643:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-adversarial-r1.md:685:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
waves/B9\codex-adversarial-r1.md:738:| RETCNDC0\_ETC\_NDC | 4 | 616K | NDC â†’ ETC classification mapping |
waves/B9\codex-adversarial-r1.md:739:| RMIID1\_MED | 20 | 114K | MedID master â€” routed-drug-level attributes |
waves/B9\codex-adversarial-r1.md:751:- **Tier B** â€” NDC-keyed, GCN-keyed, or MedID-keyed link/crossref tables. Simple join design. May include NDC normalization (re-use existing `normalize_ndc`). 2â€“7 columns typical.
waves/B9\codex-adversarial-r1.md:758:| B â€” NDC/GCN-keyed joins | 66 | 40 min | 44.0h | NDC normalization, join design, larger test fixtures |
waves/B9\codex-adversarial-r1.md:771:| RMIID1\_MED | 20 | 13 MB | MedID master (MEDNAMES module) |
waves/B9\codex-adversarial-r1.md:775:| RETCMDH0\_ETC\_MEDID\_HIST | 7 | 7 MB | ETC MedID history |
waves/B9\codex-adversarial-r1.md:778:| RPEIMS0\_MED\_STR\_LINK | 20 | 4 MB | MedID strength link |
waves/B9\codex-adversarial-r1.md:781:| RMEDNGH0\_NDC\_GEN\_MEDID\_HIST | 12 | 931 KB | NDC generic MedID history |
waves/B9\codex-adversarial-r1.md:782:| RMEDNMH0\_NDC\_MEDID\_HIST | 12 | 925 KB | NDC MedID history |
waves/B9\codex-adversarial-r1.md:798:| D â€” Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-adversarial-r1.md:803:- `0010_fdb_tier_b.py` â€” 66 Tier B tables (NDC/GCN-keyed)
waves/B9\codex-adversarial-r1.md:853:| Tier B: 66 tables Ã— 40 min | 44.0h |
waves/B9\codex-adversarial-r1.md:866:- B9.2 (Tier B, 66 tables): ~12 sessions
waves/B9\codex-adversarial-r1.md:921:### B9.2 â€” Tier B: 66 NDC/GCN-keyed tables (target ~12 sessions)
waves/B9\codex-adversarial-r1.md:957:4. **Wave boundary â€” is B9 one wave or two?**: 34 sessions is 3â€“4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-adversarial-r1.md:5145:| 1 | Session size | M | “Next absorbs overflow” is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
waves/B9\codex-adversarial-r1.md:5188:| 1 | Session size | M | “Next absorbs overflow” is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
waves/B9\codex-b9b-gate-close-r1-prompt.md:17:Tier B per recon §3's own definition — they are NDC/GCN/MEDID-keyed
waves/B9\codex-b9b-gate-close-r1-prompt.md:18:link tables that join to upstream entity IDs (e.g., RAHFSGC1_GCNSEQNO_LINK,
waves/B9\codex-b9b-gate-close-r1-prompt.md:19:RGCN0_GCN_GCNSEQNO_LINK). They will land in B9.C.
waves/B9\codex-b9b-gate-close-r1-prompt.md:114:1. **107 vs 113 — is the Tier B reclassification rationale sound?**
waves/B9\codex-b9b-gate-close-r1-prompt.md:115:   The 6 deferred specs are NDC/GCN/MEDID-keyed (RAHFSGC1_GCNSEQNO_LINK,
waves/B9\codex-b9b-gate-close-r1-prompt.md:116:   RATCGC0_ATC_GCNSEQNO_LINK, RGCN0_GCN_GCNSEQNO_LINK, RETCNDC0_ETC_NDC,
waves/B9\codex-b9b-gate-close-r1-prompt.md:117:   RGCNINH0_GCNSEQNO_INACTV_LINK, RGCNINS0_STUDY_TABLE). Recon §3
waves/B9\codex-b9b-gate-close-r1-prompt.md:118:   explicitly defines Tier B as "NDC/GCN/MedID-keyed link/crossref
waves/B9\codex-b9b-gate-close-r1-prompt.md:163:GO — B9.B closes; B9.C opens (Tier B — 66 NDC/GCN-keyed joins, plus the 6 reclassified residuals).
waves/B9\codex-b9b-gate-close-r1-result.md:30:Tier B per recon §3's own definition — they are NDC/GCN/MEDID-keyed
waves/B9\codex-b9b-gate-close-r1-result.md:31:link tables that join to upstream entity IDs (e.g., RAHFSGC1_GCNSEQNO_LINK,
waves/B9\codex-b9b-gate-close-r1-result.md:32:RGCN0_GCN_GCNSEQNO_LINK). They will land in B9.C.
waves/B9\codex-b9b-gate-close-r1-result.md:127:1. **107 vs 113 — is the Tier B reclassification rationale sound?**
waves/B9\codex-b9b-gate-close-r1-result.md:128:   The 6 deferred specs are NDC/GCN/MEDID-keyed (RAHFSGC1_GCNSEQNO_LINK,
waves/B9\codex-b9b-gate-close-r1-result.md:129:   RATCGC0_ATC_GCNSEQNO_LINK, RGCN0_GCN_GCNSEQNO_LINK, RETCNDC0_ETC_NDC,
waves/B9\codex-b9b-gate-close-r1-result.md:130:   RGCNINH0_GCNSEQNO_INACTV_LINK, RGCNINS0_STUDY_TABLE). Recon §3
waves/B9\codex-b9b-gate-close-r1-result.md:131:   explicitly defines Tier B as "NDC/GCN/MedID-keyed link/crossref
waves/B9\codex-b9b-gate-close-r1-result.md:176:GO — B9.B closes; B9.C opens (Tier B — 66 NDC/GCN-keyed joins, plus the 6 reclassified residuals).
waves/B9\codex-b9b-gate-close-r1-result.md:390:### B9.C â€” Tier B: 66 NDC/GCN-keyed joins (12 sessions)
waves/B9\codex-b9b-gate-close-r1-result.md:397:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-b9b-gate-close-r1-result.md:399:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
waves/B9\codex-b9b-gate-close-r1-result.md:982:  B9.C â†’ 66 Tier B specs
waves/B9\codex-b9b-gate-close-r1-result.md:1011:# Tier B-G: append-here when those waves land (B9.C-G).
waves/B9\codex-b9b-gate-close-r1-result.md:1316:modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:16:    Decimal money columns and no Date columns (those are Tier B/C).
waves/B9\codex-b9b-gate-close-r1-result.md:1381:modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:16:    Decimal money columns and no Date columns (those are Tier B/C).
waves/B9\codex-b9b-gate-close-r1-result.md:2041:      B â€” NDC/GCN-keyed joins (66 tables)
waves/B9\codex-b9b-gate-close-r1-result.md:2505:    0010_fdb_tier_b              â€” 66 NDC/GCN-keyed joins (Tier B)
waves/B9\codex-b9b-gate-close-r1-result.md:2751:        Tier.B: "NDC/GCN-keyed joins",
waves/B9\codex-b9b-gate-close-r1-result.md:2784:"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "RAHFSGC1|RATCGC0|RGCN0|RETCNDC0|RGCNINH0|RGCNINS0|Tier B|NDC/GCN|MedID" waves/B9 data/reference/fdb modules/drug-database/drug_database/services/fdb_tier_a -g "*.md" -g "*.py" -g "*.txt"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
waves/B9\codex-gate-close-r1-result.md:1025:Every B9 phase (B9.B Tier A, B9.C Tier B, B9.D Tier C, B9.E RNDC14,
waves/B9\codex-gate-close-r2-result.md:1663:Every B9 phase (B9.B Tier A, B9.C Tier B, B9.D Tier C, B9.E RNDC14,
waves/B9\codex-gate-close-r2-result.md:2314:| B9.C | Tier B â€” 66 NDC/GCN joins | NOT STARTED | â€” | Blocked on B9.B |
waves/B9\codex-gate-close-r2-result.md:2715:| After B9.C (+66 Tier B) | 188 | ~2.2 s |
waves/B9\codex-adversarial-r2.md:157:| W2 | Tier B â€” NDC/GCN-keyed joins | 66 | ~12 sessions |
waves/B9\codex-adversarial-r2.md:179:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests (FDW 245/245) |
waves/B9\codex-adversarial-r2.md:235:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-adversarial-r2.md:272:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-adversarial-r2.md:293:| A1 session overflow | M | "Next absorbs overflow" not a control | Per-table escape-hatch: any Tier A table that consumes > 1 hour solo gets reclassified to Tier B/C; removed from `0009_fdb_tier_a.py`; FDW ladder updated; mini-re-plan triggered if session burn > +20%. See T22. |
waves/B9\codex-adversarial-r2.md:423:### B9.C â€” Tier B: 66 NDC/GCN-keyed joins (12 sessions)
waves/B9\codex-adversarial-r2.md:430:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-adversarial-r2.md:432:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
waves/B9\codex-adversarial-r2.md:440:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\codex-adversarial-r2.md:443:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
waves/B9\codex-adversarial-r2.md:445:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-adversarial-r2.md:660:| T22 | Tier A session-size overflow if a misclassified table consumes a full session â€” ADVERSARIAL A1 | MED | MED | Per-table escape-hatch: > 1h solo â†’ reclassify to Tier B/C, remove from `0009`, update FDW ladder; > 20% session burn â†’ trigger mini-replan; charter W1 budget can flex with W2 buffer if needed |
waves/B9\codex-adversarial-r2.md:685:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-adversarial-r2.md:720:- **Charter Â§Workstreams view (39 sessions):** counts only productive ingest work â€” W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-adversarial-r2.md:861:| W2 | Tier B Ã¢â‚¬â€ NDC/GCN-keyed joins | 66 | ~12 sessions |
waves/B9\codex-adversarial-r2.md:883:| B9.C | Tier B Ã¢â‚¬â€ 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** Ã¢â‚¬â€ same scope + per-tier sampled behavioral tests (FDW 245/245) |
waves/B9\codex-adversarial-r2.md:939:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification Ã¢â‚¬â€ preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-adversarial-r2.md:974:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-adversarial-r2.md:1082:### B9.C Ã¢â‚¬â€ Tier B: 66 NDC/GCN-keyed joins (12 sessions)
waves/B9\codex-adversarial-r2.md:1089:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-adversarial-r2.md:1091:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
waves/B9\codex-adversarial-r2.md:1099:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\codex-adversarial-r2.md:1102:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
waves/B9\codex-adversarial-r2.md:1104:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-adversarial-r2.md:1314:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-adversarial-r2.md:1349:- **Charter Ã‚Â§Workstreams view (39 sessions):** counts only productive ingest work Ã¢â‚¬â€ W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-adversarial-r2.md:1381:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-adversarial-r2.md:1423:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
waves/B9\codex-adversarial-r2.md:1476:| RETCNDC0\_ETC\_NDC | 4 | 616K | NDC Ã¢â€ â€™ ETC classification mapping |
waves/B9\codex-adversarial-r2.md:1477:| RMIID1\_MED | 20 | 114K | MedID master Ã¢â‚¬â€ routed-drug-level attributes |
waves/B9\codex-adversarial-r2.md:1489:- **Tier B** Ã¢â‚¬â€ NDC-keyed, GCN-keyed, or MedID-keyed link/crossref tables. Simple join design. May include NDC normalization (re-use existing `normalize_ndc`). 2Ã¢â‚¬â€œ7 columns typical.
waves/B9\codex-adversarial-r2.md:1496:| B Ã¢â‚¬â€ NDC/GCN-keyed joins | 66 | 40 min | 44.0h | NDC normalization, join design, larger test fixtures |
waves/B9\codex-adversarial-r2.md:1509:| RMIID1\_MED | 20 | 13 MB | MedID master (MEDNAMES module) |
waves/B9\codex-adversarial-r2.md:1513:| RETCMDH0\_ETC\_MEDID\_HIST | 7 | 7 MB | ETC MedID history |
waves/B9\codex-adversarial-r2.md:1516:| RPEIMS0\_MED\_STR\_LINK | 20 | 4 MB | MedID strength link |
waves/B9\codex-adversarial-r2.md:1519:| RMEDNGH0\_NDC\_GEN\_MEDID\_HIST | 12 | 931 KB | NDC generic MedID history |
waves/B9\codex-adversarial-r2.md:1520:| RMEDNMH0\_NDC\_MEDID\_HIST | 12 | 925 KB | NDC MedID history |
waves/B9\codex-adversarial-r2.md:1536:| D Ã¢â‚¬â€ Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-adversarial-r2.md:1541:- `0010_fdb_tier_b.py` Ã¢â‚¬â€ 66 Tier B tables (NDC/GCN-keyed)
waves/B9\codex-adversarial-r2.md:1591:| Tier B: 66 tables Ãƒâ€” 40 min | 44.0h |
waves/B9\codex-adversarial-r2.md:1604:- B9.2 (Tier B, 66 tables): ~12 sessions
waves/B9\codex-adversarial-r2.md:1659:### B9.2 Ã¢â‚¬â€ Tier B: 66 NDC/GCN-keyed tables (target ~12 sessions)
waves/B9\codex-adversarial-r2.md:1695:4. **Wave boundary Ã¢â‚¬â€ is B9 one wave or two?**: 34 sessions is 3Ã¢â‚¬â€œ4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-adversarial-r2.md:5883:| 1 | Session size | M | â€œNext absorbs overflowâ€ is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
waves/B9\codex-adversarial-r2.md:5926:| 1 | Session size | M | â€œNext absorbs overflowâ€ is not a control. One misclassified Tier A table can consume a full session and hide review debt across the 113-table batch. | PARTIAL | Add a per-table escape hatch: reclassify to Tier B/C, remove from `0009`, update FDW ladder, and require mini re-plan if session burn exceeds +20%. |
waves/B9\codex-adversarial-r2.md:6009:26:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-adversarial-r2.md:6019:47:| A1 session overflow | M | "Next absorbs overflow" not a control | Per-table escape-hatch: any Tier A table that consumes > 1 hour solo gets reclassified to Tier B/C; removed from `0009_fdb_tier_a.py`; FDW ladder updated; mini-re-plan triggered if session burn > +20%. See T22. |
waves/B9\codex-adversarial-r2.md:6114:47:| A1 session overflow | M | "Next absorbs overflow" not a control | Per-table escape-hatch: any Tier A table that consumes > 1 hour solo gets reclassified to Tier B/C; removed from `0009_fdb_tier_a.py`; FDW ladder updated; mini-re-plan triggered if session burn > +20%. See T22. |
waves/B9\codex-adversarial-r2.md:6138:414:| T22 | Tier A session-size overflow if a misclassified table consumes a full session — ADVERSARIAL A1 | MED | MED | Per-table escape-hatch: > 1h solo → reclassify to Tier B/C, remove from `0009`, update FDW ladder; > 20% session burn → trigger mini-replan; charter W1 budget can flex with W2 buffer if needed |
waves/B9\codex-adversarial-r2.md:6320:- **Charter Â§Workstreams view (39 sessions):** counts only productive ingest work â€” W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-plan-consult-r1.md:40:8. **Session sizing realistic** — Tier A 113 tables / 10 sessions = ~12 tables/session; Tier B 66 / 12 = ~5.5/session. Are these defensible given the per-table work?
waves/B9\codex-plan-consult-r1.md:206:| W2 | Tier B â€” NDC/GCN-keyed joins | 66 | ~12 sessions |
waves/B9\codex-plan-consult-r1.md:228:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r1.md:284:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r1.md:854:| W2 | Tier B Ã¢â‚¬â€ NDC/GCN-keyed joins | 66 | ~12 sessions |
waves/B9\codex-plan-consult-r1.md:876:| B9.C | Tier B Ã¢â‚¬â€ 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** Ã¢â‚¬â€ same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r1.md:932:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification Ã¢â‚¬â€ preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r1.md:959:charter.md:50:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r1.md:986:charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r1.md:1028:recon.md:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-plan-consult-r1.md:1045:recon.md:56:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
waves/B9\codex-plan-consult-r1.md:1083:recon.md:169:| D â€” Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-plan-consult-r1.md:1086:recon.md:174:- `0010_fdb_tier_b.py` â€” 66 Tier B tables (NDC/GCN-keyed)
waves/B9\codex-plan-consult-r1.md:1129:recon.md:328:4. **Wave boundary â€” is B9 one wave or two?**: 34 sessions is 3â€“4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-plan-consult-r1.md:1211:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-plan-consult-r1.md:1319:### B9.C â€” Tier B: 66 NDC/GCN-keyed joins (12 sessions)
waves/B9\codex-plan-consult-r1.md:1326:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-plan-consult-r1.md:1336:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\codex-plan-consult-r1.md:1339:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
waves/B9\codex-plan-consult-r1.md:1341:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-plan-consult-r1.md:1549:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-plan-consult-r1.md:1577:2. **Migration count: 5 vs 6.** Charter says "0009..0014" (6 migrations); PLAN sub-counts Tier A and Tier B each into ~3-4 part files, which inflates the migration count to 9-10. Codex PLAN consult should rule on batching shape: single big file per tier OR per-25 part files.
waves/B9\codex-plan-consult-r1.md:1607:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-plan-consult-r1.md:1649:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
waves/B9\codex-plan-consult-r1.md:1702:| RETCNDC0\_ETC\_NDC | 4 | 616K | NDC â†’ ETC classification mapping |
waves/B9\codex-plan-consult-r1.md:1703:| RMIID1\_MED | 20 | 114K | MedID master â€” routed-drug-level attributes |
waves/B9\codex-plan-consult-r1.md:1715:- **Tier B** â€” NDC-keyed, GCN-keyed, or MedID-keyed link/crossref tables. Simple join design. May include NDC normalization (re-use existing `normalize_ndc`). 2â€“7 columns typical.
waves/B9\codex-plan-consult-r1.md:1722:| B â€” NDC/GCN-keyed joins | 66 | 40 min | 44.0h | NDC normalization, join design, larger test fixtures |
waves/B9\codex-plan-consult-r1.md:1735:| RMIID1\_MED | 20 | 13 MB | MedID master (MEDNAMES module) |
waves/B9\codex-plan-consult-r1.md:1739:| RETCMDH0\_ETC\_MEDID\_HIST | 7 | 7 MB | ETC MedID history |
waves/B9\codex-plan-consult-r1.md:1742:| RPEIMS0\_MED\_STR\_LINK | 20 | 4 MB | MedID strength link |
waves/B9\codex-plan-consult-r1.md:1745:| RMEDNGH0\_NDC\_GEN\_MEDID\_HIST | 12 | 931 KB | NDC generic MedID history |
waves/B9\codex-plan-consult-r1.md:1746:| RMEDNMH0\_NDC\_MEDID\_HIST | 12 | 925 KB | NDC MedID history |
waves/B9\codex-plan-consult-r1.md:1762:| D â€” Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-plan-consult-r1.md:1767:- `0010_fdb_tier_b.py` â€” 66 Tier B tables (NDC/GCN-keyed)
waves/B9\codex-plan-consult-r1.md:1817:| Tier B: 66 tables Ã— 40 min | 44.0h |
waves/B9\codex-plan-consult-r1.md:1830:- B9.2 (Tier B, 66 tables): ~12 sessions
waves/B9\codex-plan-consult-r1.md:1885:### B9.2 â€” Tier B: 66 NDC/GCN-keyed tables (target ~12 sessions)
waves/B9\codex-plan-consult-r1.md:1921:4. **Wave boundary â€” is B9 one wave or two?**: 34 sessions is 3â€“4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-plan-consult-r1.md:1944:24:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-plan-consult-r1.md:1992:132:### B9.C — Tier B: 66 NDC/GCN-keyed joins (12 sessions)
waves/B9\codex-plan-consult-r1.md:1996:139:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-plan-consult-r1.md:2000:152:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
waves/B9\codex-plan-consult-r1.md:2001:154:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-plan-consult-r1.md:2097:362:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-plan-consult-r1.md:2106:390:2. **Migration count: 5 vs 6.** Charter says "0009..0014" (6 migrations); PLAN sub-counts Tier A and Tier B each into ~3-4 part files, which inflates the migration count to 9-10. Codex PLAN consult should rule on batching shape: single big file per tier OR per-25 part files.
waves/B9\codex-plan-consult-r1.md:2123:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-plan-consult-r1.md:2146:129:| B — NDC/GCN-keyed joins | 66 | 40 min | 44.0h | NDC normalization, join design, larger test fixtures |
waves/B9\codex-plan-consult-r1.md:2156:174:- `0010_fdb_tier_b.py` — 66 Tier B tables (NDC/GCN-keyed)
waves/B9\codex-plan-consult-r1.md:2166:224:| Tier B: 66 tables × 40 min | 44.0h |
waves/B9\codex-plan-consult-r1.md:2171:237:- B9.2 (Tier B, 66 tables): ~12 sessions
waves/B9\codex-plan-consult-r1.md:2189:292:### B9.2 — Tier B: 66 NDC/GCN-keyed tables (target ~12 sessions)
waves/B9\codex-plan-consult-r1.md:2202:328:4. **Wave boundary — is B9 one wave or two?**: 34 sessions is 3–4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-plan-consult-r1.md:2215:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r1.md:2246:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r1.md:5012:| 8 | Session sizing realistic | DEFENSIBLE-BUT-RISKY | Tier A is explicitly aggressive at ~12 tables/session (`plan.md:92-128`); Tier B is more plausible at ~5.5/session with FK checks (`plan.md:136-154`). |
waves/B9\codex-plan-consult-r1.md:5062:| 8 | Session sizing realistic | DEFENSIBLE-BUT-RISKY | Tier A is explicitly aggressive at ~12 tables/session (`plan.md:92-128`); Tier B is more plausible at ~5.5/session with FK checks (`plan.md:136-154`). |
waves/B9\codex-plan-consult-r2.md:307:24:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-plan-consult-r2.md:336:132:### B9.C — Tier B: 66 NDC/GCN-keyed joins (12 sessions)
waves/B9\codex-plan-consult-r2.md:337:141:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
waves/B9\codex-plan-consult-r2.md:343:152:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
waves/B9\codex-plan-consult-r2.md:344:154:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-plan-consult-r2.md:420:364:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-plan-consult-r2.md:432:399:- **Charter §Workstreams view (39 sessions):** counts only productive ingest work — W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\codex-plan-consult-r2.md:453:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r2.md:485:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-plan-consult-r2.md:501:122:- **Tier B** — NDC-keyed, GCN-keyed, or MedID-keyed link/crossref tables. Simple join design. May include NDC normalization (re-use existing `normalize_ndc`). 2–7 columns typical.
waves/B9\codex-plan-consult-r2.md:508:169:| D — Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-plan-consult-r2.md:510:174:- `0010_fdb_tier_b.py` — 66 Tier B tables (NDC/GCN-keyed)
waves/B9\codex-plan-consult-r2.md:524:224:| Tier B: 66 tables × 40 min | 44.0h |
waves/B9\codex-plan-consult-r2.md:529:237:- B9.2 (Tier B, 66 tables): ~12 sessions
waves/B9\codex-plan-consult-r2.md:546:292:### B9.2 — Tier B: 66 NDC/GCN-keyed tables (target ~12 sessions)
waves/B9\codex-plan-consult-r2.md:555:328:4. **Wave boundary — is B9 one wave or two?**: 34 sessions is 3–4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-plan-consult-r2.md:577:charter.md:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
waves/B9\codex-plan-consult-r2.md:598:charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-plan-consult-r2.md:602:plan.md:24:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\codex-plan-consult-r2.md:623:plan.md:139:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-plan-consult-r2.md:624:plan.md:141:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
waves/B9\codex-plan-consult-r2.md:626:plan.md:152:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
waves/B9\codex-plan-consult-r2.md:627:plan.md:154:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\codex-plan-consult-r2.md:687:plan.md:364:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\codex-plan-consult-r2.md:737:recon.md:56:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
waves/B9\codex-plan-consult-r2.md:809:codex-plan-consult-r1.md:1045:recon.md:56:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
waves/B9\codex-plan-consult-r2.md:863:codex-plan-consult-r1.md:1649:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
waves/B9\codex-plan-consult-r2.md:940:141:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
waves/B9\codex-plan-consult-r2.md:961:139:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\codex-gate-close-r3-result.md:764:| B9.C | Tier B â€” 66 NDC/GCN joins | NOT STARTED | â€” | Blocked on B9.B |
waves/B9\codex-gate-close-r3-result.md:2747:Every B9 phase (B9.B Tier A, B9.C Tier B, B9.D Tier C, B9.E RNDC14,
waves/B9\codex-gate-close-r3-result.md:3398:| B9.C | Tier B Ã¢â‚¬â€ 66 NDC/GCN joins | NOT STARTED | Ã¢â‚¬â€ | Blocked on B9.B |
waves/B9\codex-gate-close-r3-result.md:3799:| After B9.C (+66 Tier B) | 188 | ~2.2 s |
waves/B9\codex-gate-close-r3-result.md:4032:waves\B9\charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-spec-consult-r2.md:163:| W2 | Tier B â€” NDC/GCN-keyed joins | 66 | ~12 sessions |
waves/B9\codex-spec-consult-r2.md:185:| B9.C | Tier B â€” 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** â€” same scope + per-tier sampled behavioral tests |
waves/B9\codex-spec-consult-r2.md:241:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification â€” preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-spec-consult-r2.md:268:charter.md:50:| B9.C | Tier B — 66 NDC/GCN-keyed tables | 12 | **B9.C mini-GATE-CLOSE** — same scope + per-tier sampled behavioral tests |
waves/B9\codex-spec-consult-r2.md:295:charter.md:106:The recon agent's recommendation was to split B9 = Tier A (113 tables, ~10 sessions, 6-week milestone) and B10 = Tier B+C (~22 sessions). The project owner chose full scope as single B9 (D4). Charter v2 preserves D4 single-wave label but adds **mandatory per-phase mini-GATE-CLOSE consults** (codex SPEC R1 #1) so each tier ships with its own evidence + verification — preserving B7-style checkpoint cadence inside the single B9 milestone.
waves/B9\codex-spec-consult-r2.md:337:recon.md:14:- Tier classification: **113 Tier A** (simple desc/lookup), **66 Tier B** (NDC/GCN-keyed joins), **19 Tier C** (complex/large, including the 68-column NDC master and two pricing tables each >500 MB), **19 Tier D** (MTL, pending product decision). Total raw effort estimate: ~120h; with codex review cadence ~156h (~39 four-hour sessions). B9 must be phased across multiple sub-waves.
waves/B9\codex-spec-consult-r2.md:354:recon.md:56:| NDDF MEDNAMES 3.0 | 63 | MedID, routed med, dose form med, search terms |
waves/B9\codex-spec-consult-r2.md:392:recon.md:169:| D — Tiered phasing with batch migrations | One migration per sub-wave (B9.1 = Tier A, B9.2 = Tier B, B9.3 = Tier C) | RECOMMENDED |
waves/B9\codex-spec-consult-r2.md:395:recon.md:174:- `0010_fdb_tier_b.py` — 66 Tier B tables (NDC/GCN-keyed)
waves/B9\codex-spec-consult-r2.md:438:recon.md:328:4. **Wave boundary — is B9 one wave or two?**: 34 sessions is 3–4 months. Consider splitting at the Tier A/B boundary: B9 = Tier A (113 tables, ~10 sessions, quick wins), B10 = Tier B+C (85 tables, ~20 sessions, full coverage). This gives a shippable milestone in ~6 weeks rather than waiting 4 months for the full wave.
waves/B9\codex-spec-consult-r1.md:2:C:\Users\MK\Desktop\Code Projects\Werkbench\projects\infinityrx-platform\waves\B9\charter.md:51:| B9.D | Tier B — 66 
waves/B9\codex-spec-consult-r1.md:3:NDC/GCN-keyed tables | 25 | Coverage 116 → 182 |
waves/B9\module_base_profile.md:33:| After B9.C (+66 Tier B) | 188 | ~2.2 s |
waves/B9\plan.md:26:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9\plan.md:47:| A1 session overflow | M | "Next absorbs overflow" not a control | Per-table escape-hatch: any Tier A table that consumes > 1 hour solo gets reclassified to Tier B/C; removed from `0009_fdb_tier_a.py`; FDW ladder updated; mini-re-plan triggered if session burn > +20%. See T22. |
waves/B9\plan.md:177:### B9.C — Tier B: 66 NDC/GCN-keyed joins (12 sessions)
waves/B9\plan.md:184:- FK relationship verified per table: target table must exist (in Phase 11A baseline or B9.B if Tier B references a Tier A table)
waves/B9\plan.md:186:- **1 alembic migration: `0010_fdb_tier_b.py`** covering all 66 Tier B tables. SPEC-locked single file (`charter.md:75-79`). No part-file split.
waves/B9\plan.md:194:- Loader-orchestration entry: `--mode fdb_tier_b` loads Tier B (depends on Tier A loaded)
waves/B9\plan.md:197:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
waves/B9\plan.md:199:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9\plan.md:414:| T22 | Tier A session-size overflow if a misclassified table consumes a full session — ADVERSARIAL A1 | MED | MED | Per-table escape-hatch: > 1h solo → reclassify to Tier B/C, remove from `0009`, update FDW ladder; > 20% session burn → trigger mini-replan; charter W1 budget can flex with W2 buffer if needed |
waves/B9\plan.md:439:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9\plan.md:474:- **Charter §Workstreams view (39 sessions):** counts only productive ingest work — W1 Tier A (10) + W2 Tier B (12) + W3 Tier C incl. perf gate (10) + W4 Tier D (3) + W5 cross-cutting/closeout (4) = **39**.
waves/B9\status.md:18:| B9.B | Tier A — **107 specs across 11 batches + migration + FDW manifest** | **READY FOR GATE-CLOSE** | `93c9d8b..<HEAD>` | 6 short of recon's 113 target; the 6 residual are NDC/GCN/MEDID-keyed → reclassified as Tier B (B9.C scope) |
waves/B9\status.md:19:| B9.C | Tier B — 66 NDC/GCN joins | NOT STARTED | — | Blocked on B9.B |
data/reference/fdb\README.md:1825:| **GCN ↔ GCN_SEQNO** | `RGCN0_GCN_GCNSEQNO_LINK` (532 KB, ~38k rows) | `(GCN_SEQNO, GCN)` | the canonical link | Phase C |
data/reference/fdb\README.md:1921:CREATE TABLE RGCN0_GCN_GCNSEQNO_LINK (
data/reference/fdb\README.md:2012:ingester.load(adapter.parse_table(drop, RGCN0_GCN_GCNSEQNO_LINK, source="DB"))
data/reference/fdb\README.md:2041:| 3 | `fdb_gcn_seqno_link` | `RGCN0_GCN_GCNSEQNO_LINK` (2 cols) | `(gcn_seqno, gcn)` | 5-digit GCN ↔ 6-digit GCN_SEQNO bridge |
data/reference/fdb\README.md:2198:    """Mirror of RGCN0_GCN_GCNSEQNO_LINK. (gcn_seqno, gcn) composite PK."""
data/reference/fdb\README.md:3693:| `RGCN0_GCN_GCNSEQNO_LINK` | 532 KB | NDC's GCN-5 ↔ GCN_SEQNO-6 (older 5-digit GCN backward-compat) |

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path scripts/load_fdb.py -TotalCount 180' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/tests/_fdb_contract.py | Select-Object -Skip 520 -First 100' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/tests/_fdb_delta_semantics.py | Select-Object -Skip 130 -First 60' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/tests/unit/test_fdb_tier_a_batch_11.py | Select-Object -Skip 130 -First 70' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 477ms:
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

 succeeded in 522ms:
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

 succeeded in 521ms:
                    # Append a tombstone marker â€” same shape, no special col.
                    # Keeps the count growth invariant of APPEND_ONLY.
                    conn.execute(insert(table).values(**row_str))
                else:
                    where_clauses = [
                        table.c[k] == row_str[k] for k in natural_key
                    ]
                    stmt = delete(table)
                    for w in where_clauses:
                        stmt = stmt.where(w)
                    conn.execute(stmt)
            else:
                # A or C â€” both go through INSERT (with or without conflict
                # resolution). Real production paths typically issue 'A'
                # straight as INSERT and 'C' as UPDATE; the FDB UPD format
                # delivers both as INSERT-shaped rows with a leading code,
                # which is why the contract surface is UPSERT-shaped.
                if append_only:
                    conn.execute(insert(table).values(**row_str))
                else:
                    stmt = sqlite_insert(table).values(**row_str)
                    if conflict_action == "upsert":
                        update_cols = {
                            c: row_str[c]
                            for c in all_columns
                            if c not in natural_key
                        }
                        if update_cols:
                            stmt = stmt.on_conflict_do_update(
                                index_elements=list(natural_key),
                                set_=update_cols,
                            )
                        else:
                            # Natural-key-only table; nothing to update on conflict.
                            stmt = stmt.on_conflict_do_nothing(
                                index_elements=list(natural_key)
                            )
                    else:
                        # 'nothing' â†’ the A4 regression scenario.
                        stmt = stmt.on_conflict_do_nothing(
                            index_elements=list(natural_key)
                        )
                    conn.execute(stmt)

        return _count_and_state(row_str)

    def teardown() -> None:
        metadata.drop_all(engine)

    return simulator, teardown


__all__ = ["make_sqlite_simulator"]

 succeeded in 492ms:

    if nk_count >= 2:
        # ----------------------------------------------------------------
        # Composite-NK branch (batch_08 pattern)
        # ----------------------------------------------------------------
        nk_cols = tuple(spec.columns[:nk_count])
        non_nk_cols = list(spec.columns[nk_count:])

        sim, teardown = make_sqlite_simulator(
            sqlite_engine,
            table_name=spec.table_name.lower(),
            natural_key_columns=nk_cols,
            all_columns=spec.columns,
            conflict_action="upsert",
        )
        try:
            natural_key = {
                col: _nk_placeholder(col, i) for i, col in enumerate(nk_cols)
            }

            if not non_nk_cols:
                # All-NK table: pure junction with no mutable columns.
                # A and C carry the same full-NK row; ON CONFLICT DO NOTHING
                # keeps count at 1. initial_row and changed_values are empty.
                assert_delta_semantics_acd_cycle(
                    spec,
                    natural_key=natural_key,
                    initial_row={},
                    changed_values={},
                    simulator=sim,
                )
            else:
                # Table has one or more non-NK mutable columns.
                # Build initial_row and changed_values covering ALL non-NK cols.
                # The last non-NK col is the "desc" that the C-step mutates;
                # earlier non-NK cols get stable placeholders in both rows.
                desc_col = non_nk_cols[-1]
                stable_extra = {}
                for i, col in enumerate(non_nk_cols[:-1]):
                    col_upper = col.upper()
                    if "DATE" in col_upper or col_upper.endswith("_DT") or "DATEC" in col_upper:
                        stable_extra[col] = _DATE_PLACEHOLDER_A
                    else:
                        stable_extra[col] = f"extra_{i}"

                col_upper = desc_col.upper()
                if "DATE" in col_upper or col_upper.endswith("_DT") or "DATEC" in col_upper:
                    initial_desc_val = _DATE_PLACEHOLDER_A
                    changed_desc_val = _DATE_PLACEHOLDER_B
                else:
                    initial_desc_val = "initial description"
                    changed_desc_val = "CHANGED DESCRIPTION"

                assert_delta_semantics_acd_cycle(
                    spec,
                    natural_key=natural_key,
                    initial_row={desc_col: initial_desc_val, **stable_extra},
                    changed_values={desc_col: changed_desc_val, **stable_extra},
                    simulator=sim,
                )
        finally:
            teardown()

    else:
        # ----------------------------------------------------------------
        # Single-NK branch (batch_04 pattern)
        # ----------------------------------------------------------------
        assert nk_count == 1
        natural_key_col = spec.columns[0]
        desc_col = spec.columns[1]

codex
I found a second gate-level gap: `scripts/load_fdb.py` still only exposes `fdb_initial`, `fdb_weekly`, and `fdb_rebase`, and it instantiates only `FDBPricingIngester`. I do not see a production tier-A generic loader path for `loader_group="fdb_tier_a"`, so the specs are registered but not loadable through the operator entrypoint described by the plan.
2026-05-12T14:55:42.453058Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest modules/drug-database/tests/unit/test_fdb_contract_coverage.py -q -p no:cacheprovider'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest modules/drug-database/tests/unit/test_fdb_contract_coverage.py -q -p no:cacheprovider' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'python -m pytest modules/drug-database/tests/unit/test_fdb_contract_coverage.py -q -p no:cacheprovider'` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"choices=\\[|FDBPricingIngester|ingester.run|fdb_tier_a|fdb_weekly\" scripts/load_fdb.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"sa\\.Column|sa\\.PrimaryKeyConstraint|sa\\.UniqueConstraint|primary_key=True|sa\\.Numeric|rpeiuc0_uom_conversion|UOM_CONVERSION_FACTOR|GRANT SELECT\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "table_name: str|columns: Sequence|natural_key|loader_group|delta_semantics" modules/drug-database/drug_database/services/fdb_adapter.py modules/drug-database/scripts/gen_fdb_tier_migration.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "All 113|179|107|173|mini-GATE-CLOSE|row-count|idempot|Migration.*apply|Sampled behavioral" waves/B9/B9.B-charter.md waves/B9/status.md waves/B9/plan.md' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 436ms:
8:  --mode fdb_weekly    routine UPD.zip application (typical ~10k-100k)
18:    python scripts/load_fdb.py --mode fdb_weekly
69:        choices=["fdb_initial", "fdb_weekly", "fdb_rebase"],
89:    from drug_database.services.fdb_pricing_ingester import FDBPricingIngester
103:        ingester = FDBPricingIngester(
108:        result = ingester.run(mode=args.mode, dry_run=args.dry_run)

 succeeded in 446ms:
48:        sa.Column('AHFS8', sa.Integer(), nullable=False),
49:        sa.Column('AHFS_DESC', sa.Text(), nullable=True),
56:        sa.Column('APPL_RELATION_TYPE_ID', sa.Integer(), nullable=False),
57:        sa.Column('APPL_RELATION_TYPE_DESC', sa.Text(), nullable=False),
64:        sa.Column('APPL_TYPE_CD', sa.Integer(), nullable=False),
65:        sa.Column('APPL_TYPE_CD_DESC', sa.Text(), nullable=False),
72:        sa.Column('ATC', sa.Text(), nullable=False),
73:        sa.Column('ATC_DESC', sa.Text(), nullable=True),
80:        sa.Column('BIOLOGIC_NAME_GROUPER_ID', sa.Integer(), nullable=False),
81:        sa.Column('BIOLOGIC_NAME_GROUPER_DESC', sa.Text(), nullable=False),
88:        sa.Column('SUBSTANCE_GROUP_ID', sa.Integer(), nullable=False),
89:        sa.Column('SUBSTANCE_GROUP_DESC', sa.Text(), nullable=False),
96:        sa.Column('DCC', sa.Text(), nullable=False),
97:        sa.Column('DCC_DESC', sa.Text(), nullable=True),
104:        sa.Column('ETC_CHANGE_TYPE_CODE', sa.Text(), nullable=False),
105:        sa.Column('ETC_CHANGE_TYPE_CODE_DESC', sa.Text(), nullable=True),
112:        sa.Column('GTC', sa.Integer(), nullable=False),
113:        sa.Column('GTC_DESC', sa.Text(), nullable=True),
120:        sa.Column('ING_STATUS_CD', sa.Integer(), nullable=False),
121:        sa.Column('ING_STATUS_CD_DESC', sa.Text(), nullable=True),
128:        sa.Column('MED_CONCEPT_ID_TYP', sa.Integer(), nullable=False),
129:        sa.Column('MED_CONCEPT_ID_TYP_DESC', sa.Text(), nullable=True),
136:        sa.Column('MOVE_REASON_CD', sa.Integer(), nullable=False),
137:        sa.Column('MOVE_REASON_CD_DESC', sa.Text(), nullable=False),
144:        sa.Column('APPL_TYPE_ID', sa.Integer(), nullable=False),
145:        sa.Column('APPL_TYPE_ABBREV', sa.Text(), nullable=False),
146:        sa.Column('APPL_TYPE_DESC', sa.Text(), nullable=False),
153:        sa.Column('GCDF', sa.Text(), nullable=False),
154:        sa.Column('DOSE', sa.Text(), nullable=True),
155:        sa.Column('GCDF_DESC', sa.Text(), nullable=True),
162:        sa.Column('HIC1_SEQN', sa.Integer(), nullable=False),
163:        sa.Column('HIC1', sa.Text(), nullable=False),
164:        sa.Column('HIC1_DESC', sa.Text(), nullable=True),
171:        sa.Column('HIC2_SEQN', sa.Integer(), nullable=False),
172:        sa.Column('HIC2', sa.Text(), nullable=False),
173:        sa.Column('HIC2_DESC', sa.Text(), nullable=True),
174:        sa.Column('HIC2_ROOT', sa.Integer(), nullable=True),
181:        sa.Column('HIC3_SEQN', sa.Integer(), nullable=False),
182:        sa.Column('HIC3', sa.Text(), nullable=False),
183:        sa.Column('HIC3_DESC', sa.Text(), nullable=True),
184:        sa.Column('HIC3_GRPN', sa.Integer(), nullable=True),
185:        sa.Column('HIC3_ROOT', sa.Integer(), nullable=True),
192:        sa.Column('LBLRID', sa.Text(), nullable=False),
193:        sa.Column('MFG', sa.Text(), nullable=True),
194:        sa.Column('LBLRIND', sa.Text(), nullable=True),
201:        sa.Column('MEDID_SPECIFICATION_CODE', sa.Integer(), nullable=False),
202:        sa.Column('MEDID_SPECIFICATION_CODE_DESC', sa.Text(), nullable=False),
209:        sa.Column('MEDID', sa.Integer(), nullable=False),
210:        sa.Column('SEARCH_TERM_TYPE_CD', sa.Integer(), nullable=False),
211:        sa.Column('SEARCH_TERM_TEXT', sa.Text(), nullable=False),
212:        sa.Column('MED_MEDID_DESC', sa.Text(), nullable=False),
213:        sa.Column('MEDICAL_SUPPLY_IND', sa.Integer(), nullable=False),
220:        sa.Column('SEARCH_TERM_TYPE_CD', sa.Integer(), nullable=False),
221:        sa.Column('SEARCH_TERM_TYPE_CD_DESC', sa.Text(), nullable=False),
228:        sa.Column('MED_REF_DESI2_IND', sa.Text(), nullable=False),
229:        sa.Column('MED_REF_DESI2_IND_DESC', sa.Text(), nullable=False),
236:        sa.Column('MED_REF_DEA_CD', sa.Text(), nullable=False),
237:        sa.Column('MED_REF_DEA_CD_DESC', sa.Text(), nullable=False),
244:        sa.Column('MED_REF_DESI_IND', sa.Text(), nullable=False),
245:        sa.Column('MED_REF_DESI_IND_DESC', sa.Text(), nullable=False),
252:        sa.Column('MED_DOSAGE_FORM_ID', sa.Integer(), nullable=False),
253:        sa.Column('MED_DOSAGE_FORM_ABBR', sa.Text(), nullable=False),
254:        sa.Column('MED_DOSAGE_FORM_DESC', sa.Text(), nullable=False),
261:        sa.Column('ROUTED_DOSAGE_FORM_MED_ID', sa.Integer(), nullable=False),
262:        sa.Column('ROUTED_MED_ID', sa.Integer(), nullable=False),
263:        sa.Column('MED_DOSAGE_FORM_ID', sa.Integer(), nullable=False),
264:        sa.Column('MED_ROUTED_DF_MED_ID_DESC', sa.Text(), nullable=False),
265:        sa.Column('MED_STATUS_CD', sa.Text(), nullable=False),
272:        sa.Column('MED_GCNSEQNO_ASSIGN_CD', sa.Text(), nullable=False),
273:        sa.Column('MED_GCNSEQNO_ASSIGN_CD_DESC', sa.Text(), nullable=False),
280:        sa.Column('MED_REF_GEN_THERA_EQU_CD', sa.Text(), nullable=False),
281:        sa.Column('MED_REF_GEN_THERA_EQU_CD_DESC', sa.Text(), nullable=False),
288:        sa.Column('MED_REF_GEN_DRUG_NAME_CD', sa.Text(), nullable=False),
289:        sa.Column('MED_REF_GEN_DRUG_NAME_CD_DESC', sa.Text(), nullable=False),
296:        sa.Column('MED_REF_GEN_COMP_PRICE_CD', sa.Text(), nullable=False),
297:        sa.Column('MED_REF_GEN_COMP_PRICE_CD_DESC', sa.Text(), nullable=False),
304:        sa.Column('MED_REF_GEN_SPREAD_CD', sa.Text(), nullable=False),
305:        sa.Column('MED_REF_GEN_SPREAD_CD_DESC', sa.Text(), nullable=False),
312:        sa.Column('MED_REF_INNOV_IND', sa.Text(), nullable=False),
313:        sa.Column('MED_REF_INNOV_IND_DESC', sa.Text(), nullable=False),
320:        sa.Column('MED_REF_FED_LEGEND_IND', sa.Text(), nullable=False),
321:        sa.Column('MED_REF_FED_LEGEND_IND_DESC', sa.Text(), nullable=False),
328:        sa.Column('MED_REF_MULTI_SOURCE_CD', sa.Text(), nullable=False),
329:        sa.Column('MED_REF_MULTI_SOURCE_CD_DESC', sa.Text(), nullable=False),
336:        sa.Column('MED_NAME_SOURCE_CD', sa.Text(), nullable=False),
337:        sa.Column('MED_NAME_SOURCE_CD_DESC', sa.Text(), nullable=False),
344:        sa.Column('MED_NAME_TYPE_CD', sa.Text(), nullable=False),
345:        sa.Column('MED_NAME_TYPE_CD_DESC', sa.Text(), nullable=False),
352:        sa.Column('ROUTED_MED_ID', sa.Integer(), nullable=False),
353:        sa.Column('MED_NAME_ID', sa.Integer(), nullable=False),
354:        sa.Column('MED_ROUTE_ID', sa.Integer(), nullable=False),
355:        sa.Column('MED_ROUTED_MED_ID_DESC', sa.Text(), nullable=False),
356:        sa.Column('MED_STATUS_CD', sa.Text(), nullable=False),
363:        sa.Column('MED_ROUTE_ID', sa.Integer(), nullable=False),
364:        sa.Column('MED_ROUTE_ABBR', sa.Text(), nullable=False),
365:        sa.Column('MED_ROUTE_DESC', sa.Text(), nullable=False),
372:        sa.Column('MED_STATUS_CD', sa.Text(), nullable=False),
373:        sa.Column('MED_STATUS_CD_DESC', sa.Text(), nullable=False),
380:        sa.Column('OBC', sa.Text(), nullable=False),
381:        sa.Column('OBC_SN', sa.Integer(), nullable=False),
382:        sa.Column('OBC_DESC', sa.Text(), nullable=True),
389:        sa.Column('ATTRIBUTE_CODE', sa.Integer(), nullable=False),
390:        sa.Column('ATTRIBUTE_DESC', sa.Text(), nullable=False),
391:        sa.Column('ATTRIBUTE_TYPE_CODE', sa.Integer(), nullable=False),
392:        sa.Column('ATTRIBUTE_GROUP_CODE', sa.Integer(), nullable=True),
399:        sa.Column('ATTRIBUTE_TYPE_CODE', sa.Integer(), nullable=False),
400:        sa.Column('ATTRIBUTE_TYPE_DESC', sa.Text(), nullable=False),
401:        sa.Column('ATTRIBUTE_TYPE_LENGTH', sa.Integer(), nullable=True),
402:        sa.Column('ATTRIBUTE_TYPE_PRECISION', sa.Integer(), nullable=True),
409:        sa.Column('ATTRIBUTE_CODE', sa.Integer(), nullable=False),
410:        sa.Column('ATTRIBUTE_VALUE', sa.Text(), nullable=False),
411:        sa.Column('ATTRIBUTE_VALUE_DESC', sa.Text(), nullable=False),
418:        sa.Column('DOSAGE_FORM_ATTRIBUTE_ID', sa.Integer(), nullable=False),
419:        sa.Column('DOSAGE_FORM_ATTRIBUTE_DESC', sa.Text(), nullable=False),
426:        sa.Column('DOSAGE_FORM_ID', sa.Integer(), nullable=False),
427:        sa.Column('DOSAGE_FORM_DESC_SHORT', sa.Text(), nullable=True),
428:        sa.Column('DOSAGE_FORM_DESC_LONG', sa.Text(), nullable=False),
429:        sa.Column('DOSAGE_FORM_RETIRE_DT', sa.Date(), nullable=True),
430:        sa.Column('UOM_MSTR_ID', sa.Integer(), nullable=True),
437:        sa.Column('DOSAGE_FORM_TYPE_ID', sa.Integer(), nullable=False),
438:        sa.Column('DOSAGE_FORM_TYPE_DESC', sa.Text(), nullable=False),
445:        sa.Column('PATIENT_PARAM_REQ_CD', sa.Integer(), nullable=False),
446:        sa.Column('PATIENT_PARAM_REQ_CD_DESC', sa.Text(), nullable=False),
453:        sa.Column('RT_LABELED_ID', sa.Integer(), nullable=False),
454:        sa.Column('RT_LABELED_DESC', sa.Text(), nullable=False),
461:        sa.Column('STR_CONC_TYPE_ID', sa.Integer(), nullable=False),
462:        sa.Column('STR_CONC_TYPE_DESC', sa.Text(), nullable=False),
469:        sa.Column('UOM_TYPE_CD', sa.Integer(), nullable=False),
470:        sa.Column('UOM_TYPE_CD_DESC', sa.Text(), nullable=False),
477:        sa.Column('CURRENCY_CD', sa.Text(), nullable=False),
478:        sa.Column('CURRENCY_CD_DESC', sa.Text(), nullable=False),
485:        sa.Column('PRICE_ATTRIBUTE_CD', sa.Text(), nullable=False),
486:        sa.Column('PRICE_ATTRIBUTE_DESC', sa.Text(), nullable=False),
487:        sa.Column('PRICE_ATTRIBUTE_TYPE_CD', sa.Text(), nullable=False),
488:        sa.Column('PRICE_ATTRIBUTE_GROUP_CD', sa.Text(), nullable=True),
495:        sa.Column('NDC_ATTRIBUTE_TYPE_CD', sa.Integer(), nullable=False),
496:        sa.Column('NDC_ATTRIBUTE_TYPE_DSC', sa.Text(), nullable=False),
503:        sa.Column('NDC_ATTRIBUTE_TYPE_CD', sa.Integer(), nullable=False),
504:        sa.Column('NDC_ATTRIBUTE_VALUE', sa.Text(), nullable=False),
505:        sa.Column('NDC_ATTRIBUTE_VALUE_DSC', sa.Text(), nullable=False),
512:        sa.Column('PRICE_ATTRIBUTE_TYPE_CD', sa.Text(), nullable=False),
513:        sa.Column('PRICE_ATTRIBUTE_TYPE_DESC', sa.Text(), nullable=False),
514:        sa.Column('PRICE_ATTRIBUTE_TYPE_LENGTH', sa.Integer(), nullable=True),
515:        sa.Column('PRICE_ATTRIBUTE_TYPE_PRECISION', sa.Integer(), nullable=True),
522:        sa.Column('PRICE_ATTRIBUTE_CD', sa.Text(), nullable=False),
523:        sa.Column('PRICE_ATTRIBUTE_VALUE', sa.Text(), nullable=False),
524:        sa.Column('PRICE_ATTRIBUTE_VALUE_DESC', sa.Text(), nullable=True),
531:        sa.Column('EXT_PRODUCT_CD_TYPE_ID', sa.Integer(), nullable=False),
532:        sa.Column('EXT_PRODUCT_CD_DESC', sa.Text(), nullable=False),
533:        sa.Column('EXT_PRODUCT_CD_DATA_TYPE', sa.Text(), nullable=False),
534:        sa.Column('EXT_PRODUCT_CD_FIELD_LENGTH', sa.Integer(), nullable=False),
535:        sa.Column('EXT_PRODUCT_CD_DEFINITION', sa.Text(), nullable=True),
542:        sa.Column('PACKAGE_TYPE_ID', sa.Integer(), nullable=False),
543:        sa.Column('PKG_TYPE_LONG_DESC', sa.Text(), nullable=False),
544:        sa.Column('PKG_TYPE_SHORT_DESC', sa.Text(), nullable=False),
545:        sa.Column('ACTIVELY_USED_IND', sa.Text(), nullable=False),
552:        sa.Column('FDB_PRODUCT_STATUS_CD', sa.Text(), nullable=False),
553:        sa.Column('FDB_PRODUCT_STATUS_DESC', sa.Text(), nullable=False),
554:        sa.Column('FDB_PRODUCT_STATUS_DEFINITION', sa.Text(), nullable=True),
561:        sa.Column('PRICE_UOM_ID', sa.Integer(), nullable=False),
562:        sa.Column('PRICE_UOM_DESC', sa.Text(), nullable=False),
569:        sa.Column('GCRT', sa.Text(), nullable=False),
570:        sa.Column('RT', sa.Text(), nullable=True),
571:        sa.Column('GCRT2', sa.Text(), nullable=True),
572:        sa.Column('GCRT_DESC', sa.Text(), nullable=True),
573:        sa.Column('SYSTEMIC', sa.Text(), nullable=True),
580:        sa.Column('ROUTED_GEN_ID', sa.Integer(), nullable=False),
581:        sa.Column('ROUTED_GEN_DESC', sa.Text(), nullable=False),
582:        sa.Column('GCRT', sa.Text(), nullable=False),
583:        sa.Column('HICL_SEQNO', sa.Integer(), nullable=False),
584:        sa.Column('ROUTED_GEN_STATUS_CD', sa.Text(), nullable=False),
591:        sa.Column('ROUTED_GEN_STATUS_CD', sa.Text(), nullable=False),
592:        sa.Column('ROUTED_GEN_STATUS_CD_DESC', sa.Text(), nullable=False),
599:        sa.Column('STR60', sa.Text(), nullable=False),
600:        sa.Column('STRNUM', sa.Integer(), nullable=True),
601:        sa.Column('VOLNUM', sa.Integer(), nullable=True),
602:        sa.Column('STRUN50', sa.Text(), nullable=True),
603:        sa.Column('VOLUN50', sa.Text(), nullable=True),
610:        sa.Column('STRENGTH_STATUS_CODE', sa.Integer(), nullable=False),
611:        sa.Column('STRENGTH_STATUS_DESC', sa.Text(), nullable=True),
618:        sa.Column('STRENGTH_TYP_CODE', sa.Integer(), nullable=False),
619:        sa.Column('STRENGTH_TYP_DESC', sa.Text(), nullable=True),
626:        sa.Column('UOM_ID', sa.Integer(), nullable=False),
627:        sa.Column('UOM_DESC', sa.Text(), nullable=True),
628:        sa.Column('UOM_ABBR', sa.Text(), nullable=True),
629:        sa.Column('UOM_PREFERRED_DESC', sa.Text(), nullable=True),
636:        sa.Column('TC', sa.Integer(), nullable=False),
637:        sa.Column('TC_DESC', sa.Text(), nullable=True),
644:        sa.Column('TM_NAME_TYPE_ID', sa.Integer(), nullable=False),
645:        sa.Column('TM_NAME_TYPE_DESC', sa.Text(), nullable=False),
652:        sa.Column('TM_GROUP_ID', sa.Integer(), nullable=False),
653:        sa.Column('TM_GROUP_DESC', sa.Text(), nullable=True),
660:        sa.Column('TM_GNN_TYPE_ID', sa.Integer(), nullable=False),
661:        sa.Column('TM_GNN_TYPE_DESC', sa.Text(), nullable=False),
668:        sa.Column('TM_SOURCE_ID', sa.Integer(), nullable=False),
669:        sa.Column('TM_SOURCE_DESC', sa.Text(), nullable=True),
676:        sa.Column('ROUTED_DOSAGE_FORM_MED_ID', sa.Integer(), nullable=False),
677:        sa.Column('TM_SOURCE_ID', sa.Integer(), nullable=False),
678:        sa.Column('TM_IND', sa.Text(), nullable=False),
679:        sa.Column('TM_ALT_ROUTED_DF_MED_ID_DESC', sa.Text(), nullable=False),
686:        sa.Column('MEDID', sa.Integer(), nullable=False),
687:        sa.Column('TM_SOURCE_ID', sa.Integer(), nullable=False),
688:        sa.Column('TM_IND', sa.Text(), nullable=False),
689:        sa.Column('TM_ALT_MEDID_DESC', sa.Text(), nullable=False),
696:        sa.Column('HICL_SEQNO', sa.Integer(), nullable=False),
697:        sa.Column('TM_GNN_TYPE_ID', sa.Integer(), nullable=False),
698:        sa.Column('TM_SOURCE_ID', sa.Integer(), nullable=False),
699:        sa.Column('TM_IND', sa.Text(), nullable=False),
700:        sa.Column('TM_ALT_GNN_DESC', sa.Text(), nullable=False),
707:        sa.Column('MED_NAME_ID', sa.Integer(), nullable=False),
708:        sa.Column('TM_SOURCE_ID', sa.Integer(), nullable=False),
709:        sa.Column('TM_IND', sa.Text(), nullable=False),
710:        sa.Column('TM_ALT_MED_NAME_DESC', sa.Text(), nullable=False),
717:        sa.Column('ROUTED_MED_ID', sa.Integer(), nullable=False),
718:        sa.Column('TM_SOURCE_ID', sa.Integer(), nullable=False),
719:        sa.Column('TM_IND', sa.Text(), nullable=False),
720:        sa.Column('TM_ALT_ROUTED_MED_ID_DESC', sa.Text(), nullable=False),
727:        sa.Column('HIC_SEQN', sa.Integer(), nullable=False),
728:        sa.Column('ETC_ID', sa.Integer(), nullable=False),
729:        sa.Column('ETC_REVISION_SEQNO', sa.Integer(), nullable=False),
730:        sa.Column('ETC_CHANGE_TYPE_CODE', sa.Text(), nullable=True),
731:        sa.Column('ETC_EFFECTIVE_DATE', sa.Date(), nullable=True),
738:        sa.Column('HICL_SEQNO', sa.Integer(), nullable=False),
739:        sa.Column('ETC_ID', sa.Integer(), nullable=False),
740:        sa.Column('ETC_REVISION_SEQNO', sa.Integer(), nullable=False),
741:        sa.Column('ETC_CHANGE_TYPE_CODE', sa.Text(), nullable=True),
742:        sa.Column('ETC_EFFECTIVE_DATE', sa.Date(), nullable=True),
749:        sa.Column('MED_NAME_ID', sa.Integer(), nullable=False),
750:        sa.Column('ETC_ID', sa.Integer(), nullable=False),
751:        sa.Column('ETC_REVISION_SEQNO', sa.Integer(), nullable=False),
752:        sa.Column('ETC_CHANGE_TYPE_CODE', sa.Text(), nullable=True),
753:        sa.Column('ETC_EFFECTIVE_DATE', sa.Date(), nullable=True),
760:        sa.Column('REPL_HIC_SEQN', sa.Integer(), nullable=False),
761:        sa.Column('PREV_HIC_SEQN', sa.Integer(), nullable=False),
762:        sa.Column('HIC_REPL_EFF_DT', sa.Date(), nullable=True),
769:        sa.Column('MED_REPL_ROUTED_DF_MED_ID', sa.Integer(), nullable=False),
770:        sa.Column('MED_PREV_ROUTED_DF_MED_ID', sa.Integer(), nullable=False),
771:        sa.Column('MED_ROUTED_DF_MED_ID_REP_EF_DT', sa.Date(), nullable=True),
778:        sa.Column('MED_REPL_NAME_ID', sa.Integer(), nullable=False),
779:        sa.Column('MED_PREV_NAME_ID', sa.Integer(), nullable=False),
780:        sa.Column('MED_NAME_ID_REPL_EFF_DT', sa.Date(), nullable=False),
787:        sa.Column('MED_REPL_MEDID', sa.Integer(), nullable=False),
788:        sa.Column('MED_PREV_MEDID', sa.Integer(), nullable=False),
789:        sa.Column('MED_MEDID_REPL_EFF_DT', sa.Date(), nullable=False),
796:        sa.Column('MED_REPL_ROUTED_MED_ID', sa.Integer(), nullable=False),
797:        sa.Column('MED_PREV_ROUTED_MED_ID', sa.Integer(), nullable=False),
798:        sa.Column('MED_ROUTED_MED_ID_REPL_EFF_DT', sa.Date(), nullable=False),
805:        sa.Column('ETC_SEARCH_ETC_ID', sa.Integer(), nullable=False),
806:        sa.Column('ETC_PRODUCT_RELATED_ETC_ID', sa.Integer(), nullable=False),
813:        sa.Column('ETC_ID', sa.Integer(), nullable=False),
814:        sa.Column('HIC3_SEQN', sa.Integer(), nullable=False),
821:        sa.Column('DOSAGE_FORM_ID', sa.Integer(), nullable=False),
822:        sa.Column('DOSAGE_FORM_ATTRIBUTE_ID', sa.Integer(), nullable=False),
829:        sa.Column('DOSAGE_FORM_ID', sa.Integer(), nullable=False),
830:        sa.Column('GCDF', sa.Text(), nullable=False),
831:        sa.Column('PREFERRED_DOSAGE_FORM_IND', sa.Integer(), nullable=False),
838:        sa.Column('DOSAGE_FORM_ID', sa.Integer(), nullable=False),
839:        sa.Column('MED_DOSAGE_FORM_ID', sa.Integer(), nullable=False),
840:        sa.Column('PREFERRED_DOSAGE_FORM_IND', sa.Integer(), nullable=False),
847:        sa.Column('DOSAGE_FORM_ID', sa.Integer(), nullable=False),
848:        sa.Column('OVW_DOSAGE_FORM_ID', sa.Integer(), nullable=False),
849:        sa.Column('PREFERRED_DOSAGE_FORM_IND', sa.Integer(), nullable=False),
856:        sa.Column('CONTINUOUS_RT_ID', sa.Integer(), nullable=False),
857:        sa.Column('INTERMITTENT_RT_ID', sa.Integer(), nullable=False),
864:        sa.Column('PARENT_RT_ID', sa.Integer(), nullable=False),
865:        sa.Column('CLINICAL_RT_ID', sa.Integer(), nullable=False),
871:        "rpeiuc0_uom_conversion",
872:        sa.Column('FROM_UOM_MSTR_ID', sa.Integer(), nullable=False),
873:        sa.Column('TO_UOM_MSTR_ID', sa.Integer(), nullable=False),
874:        sa.Column('UOM_CONVERSION_FACTOR', sa.Numeric(16, 5), nullable=False),
881:        sa.Column('DOSING_MODULE_UNIT_ABBREV', sa.Text(), nullable=False),
882:        sa.Column('UNIT_DESC_ABBREV', sa.Text(), nullable=True),
883:        sa.Column('UNIT_DESC_EXPANDED', sa.Text(), nullable=True),
890:        sa.Column('XRF_SOURCE_ID', sa.Integer(), nullable=False),
891:        sa.Column('XRF_SOURCE_DESC', sa.Text(), nullable=True),
898:        sa.Column('BLA_APPL_NBR', sa.Text(), nullable=False),
899:        sa.Column('APPL_TYPE_ID', sa.Integer(), nullable=False),
900:        sa.Column('BIOLOGICS_SN', sa.Integer(), nullable=False),
901:        sa.Column('MULTI_INGREDIENT_SN', sa.Integer(), nullable=False),
902:        sa.Column('HIC_SEQN', sa.Integer(), nullable=False),
909:        sa.Column('PROPRIETARY_NAME_ID', sa.Integer(), nullable=False),
910:        sa.Column('BLA_APPL_NBR', sa.Text(), nullable=False),
911:        sa.Column('APPL_TYPE_ID', sa.Integer(), nullable=False),
912:        sa.Column('PROPRIETARY_NAME', sa.Text(), nullable=False),
919:        sa.Column('MED_CONCEPT_ID', sa.Integer(), nullable=False),
920:        sa.Column('MED_CONCEPT_ID_TYP', sa.Integer(), nullable=False),
921:        sa.Column('GENERIC_MED_CONCEPT_ID', sa.Integer(), nullable=False),
922:        sa.Column('MED_CONCEPT_OBSDATEC', sa.Date(), nullable=True),
929:        sa.Column('MED_CONCEPT_ID', sa.Integer(), nullable=False),
930:        sa.Column('MED_CONCEPT_ID_TYP', sa.Integer(), nullable=False),
931:        sa.Column('HICL_SEQNO', sa.Integer(), nullable=False),
932:        sa.Column('MED_CONCEPT_HICL_SRC_CD', sa.Integer(), nullable=False),
933:        sa.Column('MED_CONCEPT_OBSDATEC', sa.Date(), nullable=True),
940:        sa.Column('FDB_PRODUCT_ID', sa.Integer(), nullable=False),
941:        sa.Column('EXT_PRODUCT_CD_TYPE_ID', sa.Integer(), nullable=False),
942:        sa.Column('EXT_PRODUCT_CD_START_DT', sa.Date(), nullable=False),
943:        sa.Column('EXT_PRODUCT_CD', sa.Text(), nullable=False),
944:        sa.Column('EXT_PRODUCT_CD_END_DT', sa.Date(), nullable=True),
951:        sa.Column('DAM_AGCSP', sa.Integer(), nullable=False),
952:        sa.Column('HIC_SEQN', sa.Integer(), nullable=False),
953:        sa.Column('HIC', sa.Text(), nullable=False),
960:        sa.Column('DACN', sa.Text(), nullable=False),
961:        sa.Column('DAM_AGCSP', sa.Integer(), nullable=False),
968:        sa.Column('GCDF', sa.Text(), nullable=False),
969:        sa.Column('SCRIPT_QQ_ID', sa.Integer(), nullable=False),
976:        sa.Column('MED_DOSAGE_FORM_ID', sa.Integer(), nullable=False),
977:        sa.Column('SCRIPT_QQ_ID', sa.Integer(), nullable=False),
984:        sa.Column('SCRIPT_QQ_ID', sa.Integer(), nullable=False),
985:        sa.Column('SCRIPT_QQ_CD', sa.Text(), nullable=True),
986:        sa.Column('SCRIPT_QQ_DESC', sa.Text(), nullable=True),
987:        sa.Column('XRF_SOURCE_ID', sa.Integer(), nullable=True),
988:        sa.Column('OBSOLETE_DATE', sa.Date(), nullable=True),
995:        sa.Column('POEUNITCDE', sa.Integer(), nullable=False),
996:        sa.Column('SCRIPT_QQ_ID', sa.Integer(), nullable=False),
1094:        "rpeiuc0_uom_conversion",
1110:            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.{_table} TO {_role}")
1127:    op.drop_table("rpeiuc0_uom_conversion", schema=_SCHEMA)

 succeeded in 458ms:
modules/drug-database/drug_database/services/fdb_adapter.py:225:      loader_group:       tier-loader registration label
modules/drug-database/drug_database/services/fdb_adapter.py:228:      delta_semantics:    how weekly delta is applied — per codex
modules/drug-database/drug_database/services/fdb_adapter.py:234:    table_name: str
modules/drug-database/drug_database/services/fdb_adapter.py:235:    columns: Sequence[str]
modules/drug-database/drug_database/services/fdb_adapter.py:243:    loader_group: str | None = None
modules/drug-database/drug_database/services/fdb_adapter.py:244:    delta_semantics: DeltaSemantics = DeltaSemantics.UNKNOWN
modules/drug-database/drug_database/services/fdb_adapter.py:274:        table_name: str,
modules/drug-database/drug_database/services/fdb_adapter.py:323:    zip_path: Path, table_name: str, *, chunk_bytes: int = 2 * 1024 * 1024,
modules/drug-database/drug_database/services/fdb_adapter.py:449:        table_name: str,
modules/drug-database/scripts/gen_fdb_tier_migration.py:114:    return f"""    # {spec.table_name} — tier={spec.tier.value} delta={spec.delta_semantics.value} record_counts_key={rcounts_key}

 succeeded in 480ms:
waves/B9/B9.B-charter.md:5:**Plan reference:** `waves/B9/plan.md:133-173`
waves/B9/B9.B-charter.md:7:**FDW manifest target:** 66 → 179 (+113)
waves/B9/B9.B-charter.md:58:## B9.B mini-GATE-CLOSE criteria
waves/B9/B9.B-charter.md:62:- All 113 Tier A tables row-count-reconciled vs `RECORD_COUNTS.TXT`
waves/B9/B9.B-charter.md:64:- `setup_fdw.sh --verify` PASS 179/179 both env DBs
waves/B9/B9.B-charter.md:65:- All 113 contract tests green (no parse warnings, all spec table
waves/B9/B9.B-charter.md:67:- Sampled behavioral tests: 10 randomly-picked Tier A tables
waves/B9/B9.B-charter.md:69:- Migration `0009_fdb_tier_a.py` apply + reverse + apply: clean
waves/B9/B9.B-charter.md:70:- Weekly delta path idempotent: re-run `load_fdb.py --mode
waves/B9/B9.B-charter.md:75:- Codex B9.B mini-GATE-CLOSE consult: GO
waves/B9/B9.B-charter.md:101:mini-GATE-CLOSE criteria are green, AND codex returns GO on the
waves/B9/status.md:18:| B9.B | Tier A — **107 specs across 11 batches + migration + FDW manifest** | **READY FOR GATE-CLOSE** | `93c9d8b..<HEAD>` | 6 short of recon's 113 target; the 6 residual are NDC/GCN/MEDID-keyed → reclassified as Tier B (B9.C scope) |
waves/B9/status.md:42:| C10 | FDW name-collision preflight script | `c03e37a` | 16 (107) |
waves/B9/status.md:141:**Defect impact (would have surfaced on first B9.B C3 row-count reconciliation):**
waves/B9/status.md:153:- **B9.B C3 design decision (deferred to next session):** re-point the preflight `load_expected_names` to source from DB.zip namelist instead of RECORD_COUNTS. RECORD_COUNTS remains the row-count reconciliation source for the 220 tables it DOES cover.
waves/B9/status.md:214:## B9.A mini-GATE-CLOSE checklist (charter SC-9)
waves/B9/status.md:227:- [ ] Codex B9.A mini-GATE-CLOSE consult dispatched + verdict captured
waves/B9/status.md:242:| SC-5 | Generated migration shape (idempotent up+down+up) | Generator + tests (C2) ready |
waves/B9/status.md:244:| SC-7 | Weekly delta idempotent per tier | Idempotency contract (C3+C8) ready |
waves/B9/status.md:246:| SC-9 | Per-phase mini-GATE-CLOSE | This file is the ledger; per-phase entries appear B9.B+ |
waves/B9/status.md:271:* At every mini-GATE-CLOSE — append the per-phase evidence section.
waves/B9/plan.md:21:6. **Codex iteration cadence** (SPEC R1+R2 done; PLAN v1 consult + ADVERSARIAL pending; mini-GATE-CLOSE consults per phase).
waves/B9/plan.md:26:- Specific column-curation decisions for non-RNDC14 Tier B/C tables (in-phase, codex-reviewed at each mini-GATE-CLOSE).
waves/B9/plan.md:38:| A4 idempotency | H | `ON CONFLICT DO NOTHING` proves replay safety, not delta correctness — mutable lookups silently serve stale data | New `DELTA_SEMANTICS` field on every `TableSpec` (values: APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD). B9.A C8 contract test simulates A/C/D/re-A scenarios per table per delta type. See T13. |
waves/B9/plan.md:48:| A2 migration blast radius | M | 113-table migration failure = wide blast | Each migration requires `alembic upgrade + downgrade + upgrade` evidence captured on a disposable DB before commit; mini-GATE-CLOSE checks evidence file exists. See T23. |
waves/B9/plan.md:49:| A3 FDW manifest | M | Hard-coded "expected 66"; concurrent-edit conflicts | B9.A C11 replaces hard-coded 66 in `setup_fdw.sh --verify` with manifest-derived count; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is the source of truth. See T24. |
waves/B9/plan.md:50:| A6 RNDC14 iteration | M | 2 sessions fragile if 5+ type issues | B9.E iteration rule: sessions may expand from 2 → up to 4 without borrowing from B9.F budget; mini-GATE-CLOSE will not close on partial column review. See T25. |
waves/B9/plan.md:70:6. **134 pre-existing test failures baseline frozen** — at B9.A C0 capture TWO numbers: (a) test inventory via `pytest --collect-only -q | tail -1` (collection count), and (b) failure count via a real `pytest -q --tb=no` run, counting `FAILED`/`ERROR` lines. The 134 figure is the failure count. Each phase mini-GATE-CLOSE asserts: collection count unchanged ± new contract tests added in-phase; failure count unchanged (no regression and no unauthorized fix). Forensic wave handles those failures later (charter `Out of scope` row 3).
waves/B9/plan.md:81:B9 runs as 8 sub-phases. Each phase below specifies its scope, deliverables, success-criteria mapping (`SC-N` refs the charter), mini-GATE-CLOSE criteria, est sessions, and **commit shape** (commits are session-scoped; exact hashes filled in evidence docs as they land).
waves/B9/plan.md:89:- **`TableSpec` registry expansion path** — adds a `TIER`, `RECORD_COUNTS_KEY`, and `LOADER_GROUP` field to existing `TableSpec` so generic ingester can: (a) tier-filter, (b) row-count reconcile, (c) loader-register by tier. Backward-compatible default values mean existing FDB pricing TableSpecs still work.
waves/B9/plan.md:90:- **Generated migration template** — script in `modules/drug-database/scripts/gen_fdb_tier_migration.py` consumes a `TableSpec` list + tier label and emits an idempotent Alembic migration file. Single-tier batched migrations are produced by this template (charter §SPEC-locked migration granularity).
waves/B9/plan.md:91:- **Ingester contract test template** — `modules/drug-database/tests/_fdb_contract.py` reusable test pattern: schema-parity assertion, latin-1 decode smoke, row-count reconciliation skeleton, ON CONFLICT idempotency. Each phase wires concrete `TableSpec` lists into this template.
waves/B9/plan.md:93:- **`setup_fdw.sh --verify` manifest expansion mechanism** — `infrastructure/scripts/lib/expected_reference_tables.txt` grows additively as each phase lands. Correct per-phase ladder (charter v3.2 + ADVERSARIAL A8 mitigation): **66 baseline → 179 (after B9.B +113) → 245 (after B9.C +66) → 261 (after B9.D +16) → 262 (after B9.E +1 RNDC14) → 264 (after B9.F +2 pricing) → 264 (after B9.G — MTL schema lands but is EXCLUDED from default FDW manifest to prevent silent false-negative joins)**. B9.H final verify: **264/264 default**; conditional 283/283 only if `fdb_load_mtl=True` (future MTL activation wave adds the +19 FDW entries together with data load + grant flip). MTL contributes 0 default FDW entries.
waves/B9/plan.md:94:- **pytest baseline markers** — committed to `waves/B9/baseline.md` at C0: collection count AND failure count, captured by the commands in invariant #6. Every phase mini-GATE-CLOSE re-runs both and asserts no regression.
waves/B9/plan.md:103:| C3 | Ingester contract test template (parity + decode + count + idempotency + **A/C/D/re-A simulation** + parse-warning-fails-test policy) | `modules/drug-database/tests/_fdb_contract.py`, `waves/B9/parse_warning_allowlist.md` (empty initial) |
waves/B9/plan.md:112:| **C12** | **Phase 09 compatibility baseline: capture RNP3 + RPRDPTD0 + RNPTYPD0 row counts + query latency + default-mode behavior; mini-GATE-CLOSE re-asserts unchanged at every phase** | `waves/B9/phase09_compat_baseline.md`, compat test |
waves/B9/plan.md:116:**B9.A mini-GATE-CLOSE criteria (charter SC-9, expanded for ADVERSARIAL):**
waves/B9/plan.md:135:**Scope:** All 113 Tier A tables ingested via generic `TableSpec`-driven adapter with no per-table custom code. These are recon's "simple desc/lookup" tier — short tables (mostly < 10K rows, all ≤ 5 columns) covering brand/route/strength/form/manufacturer descriptors and small lookup tables across NDDF BASICS, MEDNAMES, ETC, TALL MAN PLUS, XRF.
waves/B9/plan.md:140:- **1 alembic migration: `0009_fdb_tier_a.py`** covering all 113 Tier A tables. Charter SPEC-locks this granularity (`charter.md:75-79`); recon §4 confirms tables are uniform enough for single-file review (`recon.md:173-180`). No part-file split.
waves/B9/plan.md:141:- 12 contract-test wirings per session (each table gets the parity + decode + count + idempotency test set)
waves/B9/plan.md:151:- `setup_fdw.sh` foreign-table count: 66 → 179
waves/B9/plan.md:157:- SC-6 (FDW verify) — partial: 179/179 PASS after B9.B
waves/B9/plan.md:158:- SC-7 (weekly idempotency) — verified for Tier A only at B9.B mini-GATE-CLOSE
waves/B9/plan.md:160:- SC-9 (mini-GATE-CLOSE) — see below
waves/B9/plan.md:162:**B9.B mini-GATE-CLOSE criteria:**
waves/B9/plan.md:164:- All 113 Tier A tables: row count reconciled against `RECORD_COUNTS.TXT` ± documented tolerance
waves/B9/plan.md:165:- `setup_fdw.sh --verify` 179/179 PASS both env DBs
waves/B9/plan.md:167:- Sampled behavioral tests: 10 randomly-picked Tier A tables exercise non-trivial query (FK join, where-clause, sort)
waves/B9/plan.md:168:- Migration apply + reverse + apply: clean
waves/B9/plan.md:169:- Weekly delta path: `load_fdb.py --mode fdb_tier_a` re-run produces 0 new rows (idempotent)
waves/B9/plan.md:171:- Codex mini-GATE-CLOSE consult: GO
waves/B9/plan.md:195:- FDW foreign-table count: 179 → 245
waves/B9/plan.md:197:**Success criteria:** SC-1 (partial: +66, cum 179/217), SC-2, SC-6 (245/245), SC-7 (Tier B idempotent), SC-8 (per-tier sampled behavioral), SC-9.
waves/B9/plan.md:199:**B9.C mini-GATE-CLOSE criteria:** As B9.B + FK-integrity assertion green for every Tier B table.
waves/B9/plan.md:225:**B9.D mini-GATE-CLOSE criteria:** As prior + money-path audit signed off + column-curation decisions documented per table.
waves/B9/plan.md:233:**Why standalone:** 68 columns warrant column-by-column review at mini-GATE-CLOSE. Charter D1 locks "full 68-column ingest" — no column triage / no curation; every column lands. The review focuses on type correctness, NULL semantics, and naming (Python-snake_case from FDB upper-case).
waves/B9/plan.md:250:**B9.E mini-GATE-CLOSE criteria:** Column-by-column model review (codex consult walks all 68); type correctness audit; money-path audit; NDC normalization tests green.
waves/B9/plan.md:265:- Session 4: Weekly delta idempotency timing (re-run `load_fdb.py --mode fdb_weekly` → 0 new rows + timing); FDW verify; storage budget verification against B9.A C0 baseline; **reclaimrx pricing-protocol tests** (ADVERSARIAL A15): exercise `awp_basis` distribution with populated RNP2 + RPRDPP0 + RNP3; assert no new basis values appear; assert literal-AWP guards still reject correctly
waves/B9/plan.md:278:**B9.F mini-GATE-CLOSE criteria — DRACONIAN per charter SC-4 + ADVERSARIAL A7 hard aborts:**
waves/B9/plan.md:286:- Codex mini-GATE-CLOSE consult: GO; codex reviews EXPLAIN ANALYZE for index gaps + reviews reclaimrx test deltas
waves/B9/plan.md:318:**B9.G mini-GATE-CLOSE criteria:**
waves/B9/plan.md:325:- Codex mini-GATE-CLOSE consult: GO; codex verifies (a) DB-level guard prevents app-role writes, (b) flipping `fdb_load_mtl=False` after data load DOES NOT delete data, (c) MTL exclusion from FDW is correct for default state
waves/B9/plan.md:336:- Session 2: Final `setup_fdw.sh --verify` **264/264** in both env DBs; full row-count reconciliation against `RECORD_COUNTS.TXT` for all loaded tables (217 + 2 existing = 219 DB tables; 264 FDW entries); published in `waves/B9/evidence.md`
waves/B9/plan.md:344:- `waves/B9/evidence.md` with row-count reconciliation table, FDW verify output, storage delta vs. C0
waves/B9/plan.md:359:- SC-7: Weekly delta idempotent across all 220 tables (verified at B9.H by running `--mode fdb_weekly` → 0 new rows in all 217 + already-covered 3)
waves/B9/plan.md:361:- SC-9: All B9.B..B9.G mini-GATE-CLOSE consults passed
waves/B9/plan.md:377:| SC-3 | RNDC14 SQLAlchemy model has 68 columns; codex column-by-column review verdict captured in B9.E mini-GATE-CLOSE consult | B9.E |
waves/B9/plan.md:382:| SC-8 | Test counts per category in evidence.md: 217 contract tests + 220 schema-parity + 217 row-count assertions + N sampled behavioral + dedicated Tier C suite | B9.H Session 2 |
waves/B9/plan.md:383:| SC-9 | All 6 mini-GATE-CLOSE consult docs present (`waves/B9/codex-mini-gate-close-{B,C,D,E,F,G}.md`) with GO verdicts | continuously |
waves/B9/plan.md:394:| T2 | Money-path columns typed as `float`/`numeric` lose Decimal discipline (rules `financial-precision.md`) | MED | HIGH | B9.D money-path audit; B9.E + B9.F mandatory `Decimal` audit; codex mini-GATE-CLOSE flags any `Float` or non-explicit `Numeric` on money columns |
waves/B9/plan.md:396:| T4 | Per-phase mini-GATE-CLOSE consults skipped under time pressure | LOW | HIGH | Each phase's commit chain explicitly lists the consult commit; gate-check tool refuses to advance the wave state if the consult file is missing |
waves/B9/plan.md:399:| T7 | Weekly delta idempotency broken on a specific table (ON CONFLICT clause incorrect) | MED | MED | Each phase's mini-GATE-CLOSE re-runs weekly delta; 0 new rows is the gate; per-tier sampled idempotency tests |
waves/B9/plan.md:401:| T9 | FDW manifest expansion drifts from actual reference DB state | LOW | MED | `setup_fdw.sh --verify` at each phase mini-GATE-CLOSE catches drift before next phase opens |
waves/B9/plan.md:402:| T10 | Test count baseline drifts (collection growth unexplained; or 134 pre-existing failures become 135+) | MED | MED | B9.A C0 captures TWO baselines (per invariant #6): collection count via `pytest --collect-only -q | tail -1` AND failure count via `pytest -q --tb=no` line-count of `FAILED`/`ERROR`. Each phase mini-GATE-CLOSE asserts no regression in either, ± in-phase contract tests on the collection number. |
waves/B9/plan.md:404:| T12 | Weekly FDB UPD delta format isn't uniformly A/C/D across all 220 tables — some tables may require TRUNCATE+INSERT instead of UPSERT (recon §7 risk implied; codex PLAN R1 surfaced) | MED | HIGH | B9.A C3 contract template includes a UPD-format probe: for each table, verify the first column of the table's `.UPD` file matches the expected A/C/D code. Tables that fail the probe are flagged as TRUNCATE+INSERT and routed through a separate idempotent reload path. Per-phase mini-GATE-CLOSE re-asserts the probe + weekly delta rerun. Charter R4 ("weekly delta breaks because NEW columns") is covered by the same probe plus a column-set parity check against the live model. |
waves/B9/plan.md:405:| T13 | Per-table delta semantics ambiguous; `ON CONFLICT DO NOTHING` serves stale data on mutable lookups (D-then-re-A with changed values silently ignored) — ADVERSARIAL A4 | MED | **HIGH** | New `DELTA_SEMANTICS` field on every `TableSpec` with 4 values (APPEND_ONLY / UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE / TRUNCATE_RELOAD); B9.A C8 contract test simulates A/C/D/re-A per table per semantics class; mini-GATE-CLOSE re-asserts |
waves/B9/plan.md:413:| T21 | `parse_table` silently skips field-count errors; large tables can systematically drop rows masked by row-count tolerance — ADVERSARIAL N4 | MED | **HIGH** | Contract test policy: ANY `parse_table` warning fails the test unless explicitly allowlisted in `waves/B9/parse_warning_allowlist.md` with documented count-impact + reviewer sign-off |
waves/B9/plan.md:415:| T23 | 113-table migration failure has large debug blast radius — ADVERSARIAL A2 | LOW | MED | Each migration captures `alembic upgrade + downgrade + upgrade` on a disposable DB before commit; evidence file required at mini-GATE-CLOSE; failed migration auto-flagged for codex review |
waves/B9/plan.md:416:| T24 | `setup_fdw.sh --verify` hard-codes "expected 66"; B9.B verify fails without script change — ADVERSARIAL A3 | LOW | MED | B9.A C11 replaces hard-coded count with manifest-derived; manifest sorted deterministically; per-phase mini-GATE-CLOSE confirms manifest is source of truth |
waves/B9/plan.md:417:| T25 | RNDC14 2-session budget insufficient if column review surfaces multiple issues — ADVERSARIAL A6 | MED | MED | B9.E iteration allowance: 2 → up to 4 sessions without borrowing from B9.F; mini-GATE-CLOSE will not close on partial review |
waves/B9/plan.md:420:| T28 | Existing Phase 09 coverage breaks due to registry expansion or migration interaction — ADVERSARIAL A12 | LOW | MED | B9.A C12 captures Phase 09 baseline: RNP3/RPRDPTD0/RNPTYPD0 row counts + query latency + default-mode behavior; per-phase mini-GATE-CLOSE re-asserts unchanged |
waves/B9/plan.md:421:| T29 | Flaky test noise drowns real signal in 134-failure baseline — ADVERSARIAL A13 | MED | MED | B9.A C0 captures node-ID snapshots × 2 runs (NOT raw counts); known flakes quarantined in `waves/B9/test_flake_quarantine.md`; mini-GATE-CLOSE asserts node-ID delta, not count delta |
waves/B9/plan.md:438:| mini-GATE-CLOSE B9.B | B9.B | After Tier A all 113 tables ingested | `codex-mini-gate-close-B.md` |
waves/B9/plan.md:439:| mini-GATE-CLOSE B9.C | B9.C | After Tier B all 66 tables ingested | `codex-mini-gate-close-C.md` |
waves/B9/plan.md:440:| mini-GATE-CLOSE B9.D | B9.D | After Tier C non-RNDC14 all 16 ingested | `codex-mini-gate-close-D.md` |
waves/B9/plan.md:441:| mini-GATE-CLOSE B9.E | B9.E | After RNDC14 column-by-column review | `codex-mini-gate-close-E.md` |
waves/B9/plan.md:442:| mini-GATE-CLOSE B9.F | B9.F | After D2 perf gate evidence captured | `codex-mini-gate-close-F.md` |
waves/B9/plan.md:443:| mini-GATE-CLOSE B9.G | B9.G | After MTL schema-only + guards ship | `codex-mini-gate-close-G.md` |
waves/B9/plan.md:446:**Total codex consults projected:** 13 (2 SPEC + 2 PLAN + 2 ADVERSARIAL + 6 mini-GATE-CLOSE + 1 final GATE-CLOSE = 13). Token spend through ADVERSARIAL R1: ~280k. Remaining gate consults: ~50-80k for ADVERSARIAL R2 + ~300k for 6 mini-GATE-CLOSEs + ~40k for final = ~390-420k more codex tokens.
waves/B9/plan.md:466:1. **FDW final count: 283 vs 284** → **RESOLVED in PLAN v2: 283** (arithmetic) → **SUPERSEDED in PLAN v3 by ADVERSARIAL A8: 264 default, 283 conditional.** Tier C arithmetic bug (`19 - 3 = 16, not 17`) cascaded to 284; v2 corrected to 283; v3 changed final default to 264 (MTL excluded from default FDW per charter v3.2). Final ladder: 66 → 179 → 245 → 261 → 262 → 264 default; 283 ONLY when `fdb_load_mtl=True` in a future MTL activation wave.
waves/B9/plan.md:486:- At each mini-GATE-CLOSE: full sign-off sheet committed

codex
GO-WITH-FIXES

| Severity | Area | Issue | Suggested fix |
|---|---|---|---|
| HIGH | Loader path | B9.B gate requires `load_fdb.py --mode fdb_tier_a` idempotency, but [scripts/load_fdb.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/scripts/load_fdb.py:69) only accepts `fdb_initial`, `fdb_weekly`, `fdb_rebase`, and still instantiates only `FDBPricingIngester` at line 89. Tier A specs are registered but not operator-loadable through the planned path. | Add/verify the generic TableSpec tier loader and `fdb_tier_a` mode, then capture row-count reconciliation and replay-idempotency evidence. |
| HIGH | Migration / delta semantics | [0009_fdb_tier_a.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:48) creates columns but no PK/unique constraints. `rg` found no `PrimaryKeyConstraint`, `UniqueConstraint`, `primary_key=True`, or unique indexes in the migration. Without a DB uniqueness surface, `UPSERT_BY_NATURAL_KEY` is not enforceable in Postgres. | Add explicit natural-key metadata, emit matching PK/unique constraints or unique indexes, and add generator tests that fail if checkable specs lack DB conflict targets. |
| MEDIUM | Scope accounting | The 107 vs 113 reclassification is defensible: the six deferred tables match the Tier B NDC/GCN/MedID-keyed definition. But the charter/plan gate still says 113 and FDW 179, while delivered status says 107 and manifest 173. | Amend B9.B/B9.C ladder explicitly: B9.B closes at 107 / 173; B9.C becomes 72 tables if it absorbs the six residuals, preserving the later cumulative count. |
| MEDIUM | Numeric precision | `RPEIUC0_UOM_CONVERSION.UOM_CONVERSION_FACTOR` is described as `NUMERIC(16,6)`, but the migration emits `sa.Numeric(16, 5)` at [0009_fdb_tier_a.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:874). This comes from the generator’s global Decimal mapping. | Add per-column precision metadata or a special coercer mapping and regenerate this column as `sa.Numeric(16, 6)`. |
| MEDIUM | Gate evidence | Several mini-GATE-CLOSE criteria are not evidenced in the provided artifacts: live FDW verify, migration upgrade/downgrade/upgrade, row-count reconciliation, sampled behavioral tests, and tier replay idempotency. Unit tests alone do not close those gates. | Capture or link the missing evidence before declaring B9.B closed. |

Other judgments:

The APPEND_ONLY A/C/D/re-A test shape is directionally correct: a collapsing UPSERT path should fail the row-growth assertions. The all-natural-key junction-table handling is acceptable as an interim pattern, but it should be named separately from mutable `UPSERT_BY_NATURAL_KEY` so future reviewers do not assume the C-step validates an update.

I could not run pytest in this sandbox because the command was rejected by policy, so this verdict is based on source inspection.
tokens used
113,424
GO-WITH-FIXES

| Severity | Area | Issue | Suggested fix |
|---|---|---|---|
| HIGH | Loader path | B9.B gate requires `load_fdb.py --mode fdb_tier_a` idempotency, but [scripts/load_fdb.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/scripts/load_fdb.py:69) only accepts `fdb_initial`, `fdb_weekly`, `fdb_rebase`, and still instantiates only `FDBPricingIngester` at line 89. Tier A specs are registered but not operator-loadable through the planned path. | Add/verify the generic TableSpec tier loader and `fdb_tier_a` mode, then capture row-count reconciliation and replay-idempotency evidence. |
| HIGH | Migration / delta semantics | [0009_fdb_tier_a.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:48) creates columns but no PK/unique constraints. `rg` found no `PrimaryKeyConstraint`, `UniqueConstraint`, `primary_key=True`, or unique indexes in the migration. Without a DB uniqueness surface, `UPSERT_BY_NATURAL_KEY` is not enforceable in Postgres. | Add explicit natural-key metadata, emit matching PK/unique constraints or unique indexes, and add generator tests that fail if checkable specs lack DB conflict targets. |
| MEDIUM | Scope accounting | The 107 vs 113 reclassification is defensible: the six deferred tables match the Tier B NDC/GCN/MedID-keyed definition. But the charter/plan gate still says 113 and FDW 179, while delivered status says 107 and manifest 173. | Amend B9.B/B9.C ladder explicitly: B9.B closes at 107 / 173; B9.C becomes 72 tables if it absorbs the six residuals, preserving the later cumulative count. |
| MEDIUM | Numeric precision | `RPEIUC0_UOM_CONVERSION.UOM_CONVERSION_FACTOR` is described as `NUMERIC(16,6)`, but the migration emits `sa.Numeric(16, 5)` at [0009_fdb_tier_a.py](/C:/Users/MK/Desktop/Code%20Projects/InfinityRx/infinityrx-platform/modules/drug-database/alembic/versions/0009_fdb_tier_a.py:874). This comes from the generator’s global Decimal mapping. | Add per-column precision metadata or a special coercer mapping and regenerate this column as `sa.Numeric(16, 6)`. |
| MEDIUM | Gate evidence | Several mini-GATE-CLOSE criteria are not evidenced in the provided artifacts: live FDW verify, migration upgrade/downgrade/upgrade, row-count reconciliation, sampled behavioral tests, and tier replay idempotency. Unit tests alone do not close those gates. | Capture or link the missing evidence before declaring B9.B closed. |

Other judgments:

The APPEND_ONLY A/C/D/re-A test shape is directionally correct: a collapsing UPSERT path should fail the row-growth assertions. The all-natural-key junction-table handling is acceptable as an interim pattern, but it should be named separately from mutable `UPSERT_BY_NATURAL_KEY` so future reviewers do not assume the C-step validates an update.

I could not run pytest in this sandbox because the command was rejected by policy, so this verdict is based on source inspection.
