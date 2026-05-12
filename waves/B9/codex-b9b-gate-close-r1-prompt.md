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
