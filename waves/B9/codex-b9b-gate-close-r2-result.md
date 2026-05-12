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
session id: 019e1cc4-2026-79b0-9444-101402b50712
--------
user
# Codex B9.B mini-GATE-CLOSE R2 — Verification of R1 absorption

**Wave:** B9 (FDB NDDF Plus 217-table extension)
**Phase:** B9.B close (verification round)
**Verdict requested:** GO / GO-WITH-FIXES / NO-GO
**R1 result:** GO-WITH-FIXES (2 HIGH + 3 MEDIUM) → R1 prompt + result at
`waves/B9/codex-b9b-gate-close-r1-{prompt,result}.md`

## What changed since R1

One absorption commit: `18dcb20`.

### HIGH 1 — Generic Tier A loader path (`load_fdb.py --mode fdb_tier_a`)

New module `modules/drug-database/drug_database/services/fdb_tier_loader.py`:

- `load_tier_group(session, adapter, drop, *, group, dry_run, ...) -> TierLoadResult`
- Reads `REGISTERED_SPECS` via `fdb_loader_registry.filter_loadable_specs`
  with `only_groups=[group]` + MTL guard.
- Dispatches per-spec on `delta_semantics`:
  - UPSERT_BY_NATURAL_KEY / UPSERT_WITH_EFFECTIVE_DATE → `INSERT ... ON CONFLICT (natural_key) DO UPDATE` (or `DO NOTHING` for all-NK junctions)
  - APPEND_ONLY → plain INSERT (every row appends)
  - UNKNOWN / TRUNCATE_RELOAD → log + skip (specialized loaders handle in B9.D / B9.F)

`scripts/load_fdb.py` accepts `--mode fdb_tier_a` and dispatches to
the new loader; Phase 09 modes (initial/weekly/rebase) continue to
dispatch to `FDBPricingIngester` unchanged.

5 unit tests in `tests/unit/test_fdb_tier_loader.py`:
- group filter (skips non-fdb_tier_a specs)
- dry-run (parse but no write)
- unsupported semantics → skip with warning
- UPSERT without natural_key → ValueError
- TierLoadResult aggregates per-table summaries

### HIGH 2 — PK constraints in migration (load-bearing)

`TableSpec` gained a `natural_key: tuple[str, ...]` field (default empty).
**All 99 UPSERT specs across 11 batches were patched** to declare it
(programmatic patch via existing `NATURAL_KEY_COUNT` dicts + single-NK
default for batches 01-07).

Generator validation:

```python
if spec.delta_semantics in {UPSERT_BY_NATURAL_KEY, UPSERT_WITH_EFFECTIVE_DATE} \
   and not spec.natural_key:
    raise ValueError(...)
```

Generator now emits inside each `op.create_table(...)`:

```python
sa.PrimaryKeyConstraint('col_a', 'col_b', name='pk_<table>'),
```

**Regenerated migration `0009_fdb_tier_a.py`:**
- 1,432 lines (was 1,220)
- **99 PrimaryKeyConstraint entries** confirmed via grep
- **1 Numeric(16, 6)** confirmed (UOM_CONVERSION_FACTOR — see MEDIUM 2)

The 8 APPEND_ONLY history specs do not need natural_key — they have
no conflict target.

### MEDIUM 1 — Scope accounting

`waves/B9/status.md` updated:
- Ledger row says "107 specs / FDW 173" (was "113 / 179")
- New section: "B9.B GATE-CLOSE R1 — verdict & absorption" captures each fix
- Plan adjustment noted: B9.C absorbs 6 NDC/GCN/MEDID-keyed reclassifieds (66 → 72)

### MEDIUM 2 — UOM precision

New `decimal_16_6` coercer in `fdb_adapter.py`. Generator's
`_sql_type_for_coercer` now maps it to `sa.Numeric(16, 6)`. `batch_10`
RPEIUC0_UOM_CONVERSION.UOM_CONVERSION_FACTOR switched from `Decimal`
to `decimal_16_6`. Regenerated migration confirms the single
`Numeric(16, 6)` emission.

### MEDIUM 3 — Live-DB evidence

Explicitly deferred to a Docker-up follow-on session. Unit-test
layer is gate-close-ready; live FDW verify / migration up+down+up /
row-count reconciliation are separate-gate concerns. The status
ledger documents this.

## Test result

```
1,080 / 1,081 unit pass
The 1 failure (test_fdb_pricing_models.test_type_desc_pk_rejects_duplicate)
is a pre-existing SAWarning flake unrelated to B9.B (passes cleanly
in isolation; ordering-dependent in full-suite collection). Out of
B9 scope per charter §Out-of-scope row 3.
```

## Areas to verify in R2

1. **HIGH 1 fix completeness** — does `load_tier_group` actually
   implement the gate criterion "`load_fdb.py --mode fdb_tier_a`
   re-run produces 0 net new rows"? Inspect:
   - The UPSERT path: `INSERT ... ON CONFLICT (natural_key) DO UPDATE SET col=excluded.col` semantics.
   - The all-NK junction handling: `ON CONFLICT (natural_key) DO NOTHING` is correct.
   - The dispatcher's behavior on UNKNOWN/TRUNCATE_RELOAD: skip + log warning is the right call for B9.B (those semantics are out-of-scope for this wave).

2. **HIGH 2 fix completeness** — verify `0009_fdb_tier_a.py` has
   `PrimaryKeyConstraint` in every CREATE TABLE block for UPSERT
   specs, and that the generator now rejects UPSERT specs without
   natural_key.

3. **MEDIUM 2 fix correctness** — verify the migration emits
   `sa.Numeric(16, 6)` exactly once (UOM_CONVERSION_FACTOR), and
   all other Decimal columns still emit `sa.Numeric(16, 5)`.

4. **Are there any UPSERT specs that still lack natural_key** —
   the programmatic patcher claimed 99 patched; verify by:
   ```python
   from drug_database.services.fdb_tier_a import TIER_A_SPECS
   from drug_database.services.fdb_adapter import DeltaSemantics
   bad = [s.table_name for s in TIER_A_SPECS
          if s.delta_semantics == DeltaSemantics.UPSERT_BY_NATURAL_KEY
          and not s.natural_key]
   assert bad == [], f"{len(bad)} specs missing natural_key"
   ```

5. **MEDIUM 3 deferral defensibility** — is the deferral framing
   sound for a B9.B close, or should some live-DB evidence be
   present before declaring the wave closed?

## Verdict format

GO — B9.B officially closes; B9.C opens (now 72 Tier B tables).
GO-WITH-FIXES — list residual concerns.
NO-GO — fundamental issue.

For GO-WITH-FIXES, return concerns as:
| Severity | Area | Issue | Suggested fix |

codex
I’ll verify this in a review posture: inspect the R1 docs, the absorption commit, loader/generator/spec changes, and run read-only checks where possible. Since this sandbox is read-only, I can validate by reading files and executing non-mutating commands, but I won’t edit anything.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show --stat --oneline --decorate --name-only 18dcb20' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git rev-parse --show-toplevel; git rev-parse HEAD' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path waves/B9/codex-b9b-gate-close-r1-result.md -TotalCount 240' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
2026-05-12T15:18:09.975473Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git rev-parse --show-toplevel; git rev-parse HEAD'` rejected: blocked by policy
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git rev-parse --show-toplevel; git rev-parse HEAD'` rejected: blocked by policy
 succeeded in 436ms:
18dcb20 (HEAD -> develop) B9.B GATE-CLOSE R1 absorption: HIGH 1 + HIGH 2 + MEDIUM 1 + MEDIUM 2 (M3 deferred)
modules/drug-database/alembic/versions/0009_fdb_tier_a.py
modules/drug-database/drug_database/services/fdb_adapter.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_01.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_02.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_03.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_04.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_05.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_06.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_07.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_08.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_10.py
modules/drug-database/drug_database/services/fdb_tier_a/batch_11.py
modules/drug-database/drug_database/services/fdb_tier_loader.py
modules/drug-database/scripts/gen_fdb_tier_migration.py
modules/drug-database/tests/unit/test_fdb_tier_loader.py
modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py
scripts/load_fdb.py
waves/B9/status.md

 succeeded in 473ms:
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
# Codex B9.B mini-GATE-CLOSE R1 â€” Consult Prompt

**Wave:** B9 (FDB NDDF Plus 217-table extension)
**Phase:** B9.B (Tier A â€” 113-table simple lookups, recon Â§3 estimate)
**Verdict requested:** GO / GO-WITH-FIXES / NO-GO
**Predecessor:** B9.A CLOSED â€” `a114303` with 3 rounds of codex review absorbed
**Plan reference:** `waves/B9/plan.md:133-173`

## Scope

B9.B is the first per-table data wave. Goal per recon Â§3:
"113 Tier A tables = simple lookup descriptors (â‰¤ 5 cols, < 2 MB)".

**Actual delivered: 107 specs across 11 batches + migration + FDW manifest.**

Diff vs recon estimate: 6 short. The 6 residual were reclassified as
Tier B per recon Â§3's own definition â€” they are NDC/GCN/MEDID-keyed
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
86515b5  B9.B C15: Tier A batch_10 (11 link tables â€” composite+single NK hybrid)
2f226ae  B9.B C16: Tier A batch_11 (11 link tables with DATE columns)
7c1c5e9  B9.B C17+C18: alembic migration 0009_fdb_tier_a + FDW manifest expansion (66 â†’ 173)
```

## Files added / modified

### Production code (drug_database/services/fdb_tier_a/)
- `__init__.py` â€” pkgutil-based auto-aggregator (C5)
- `batch_01.py` through `batch_11.py` â€” 107 TableSpec instances total
- `fdb_specs.py` (parent module) â€” `REGISTERED_SPECS = list(TIER_A_SPECS)`

### Tests (tests/unit/)
- `test_fdb_contract_coverage.py` â€” F4 coverage canary (loads BATCH_TESTED_NAMES via pkgutil)
- `test_fdb_tier_a_batch_01.py` through `test_fdb_tier_a_batch_11.py` â€” 691 parametrized + sanity tests
- `test_fdb_contract.py`, `test_fdb_delta_semantics.py` â€” unchanged from B9.A

### Migration + FDW
- `modules/drug-database/alembic/versions/0009_fdb_tier_a.py` â€” 1,220 lines auto-generated via `gen_fdb_tier_migration.py`. Creates all 107 tables in `drug_database` schema with proper column types, nullables, GRANTs (env-driven IFX_APP_ROLE pattern), and operator dry-run docstring.
- `infrastructure/scripts/lib/expected_reference_tables.txt` â€” 66 â†’ 173 entries (+107 Tier A appended in a new section)

### Wave artifacts
- `waves/B9/B9.B-charter.md` â€” wave charter
- `waves/B9/status.md` â€” ledger updated to reflect B9.B ready for gate-close

## Test result

```
B9.B Tier A unit tests:      691 pass
B9.A inherited unit tests:   ~130 pass (unchanged)
Integration:                 3 skipped (live-DB only)
drug-database total:         326 â†’ 1000+, no regression
```

Per-batch test counts (after the hybrid pattern shake-out):
batch_01: 60 + batch_02: 61 + batch_03: 61 + batch_04: 61 +
batch_05: 61 + batch_06: 61 + batch_07: 61 + batch_08: 36 +
batch_09: 57 + batch_10: 78 + batch_11: 79 + coverage: 2 = 678

(Discrepancy with 691 is a few schema-parity tests duplicated across
the auto-aggregator vs per-batch â€” both green either way.)

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

1. **107 vs 113 â€” is the Tier B reclassification rationale sound?**
   The 6 deferred specs are NDC/GCN/MEDID-keyed (RAHFSGC1_GCNSEQNO_LINK,
   RATCGC0_ATC_GCNSEQNO_LINK, RGCN0_GCN_GCNSEQNO_LINK, RETCNDC0_ETC_NDC,
   RGCNINH0_GCNSEQNO_INACTV_LINK, RGCNINS0_STUDY_TABLE). Recon Â§3
   explicitly defines Tier B as "NDC/GCN/MedID-keyed link/crossref
   tables". Forcing them into Tier A would violate that classification.
   But: does deferring 6 invalidate B9.B as a clean wave boundary,
   or is "Tier A as recon defines it" the right framing?

2. **All-NK junction tables in batch_11** (RXRFDDX0, RXRGDFQ0,
   RXRMDFQ0, RXRPDFQ0). Every column is part of the natural key â€”
   there are no non-key columns for the C step to toggle. The agent
   correctly identified this and used `if not non_nk_cols:` to
   short-circuit the ACD assertion. Is treating "no-op C" as valid
   UPSERT_BY_NATURAL_KEY the right call, or should these be a new
   `JUNCTION_TABLE` delta semantic?

3. **Decimal coercer in batch_10** for `RPEIUC0_UOM_CONVERSION.
   UOM_CONVERSION_FACTOR` (NUMERIC(16,6)). The agent applied
   `.claude/rules/financial-precision.md` aggressively â€” even
   though UOM conversion isn't money. Is this overreach, or correct
   conservative defaulting? (Phase 09 used Decimal for RNP3.PRICE
   per the same rule.)

4. **APPEND_ONLY ACD test pattern** in batch_09. The contract
   template's APPEND_ONLY branch asserts count >= 4 after A/C/D/re-A
   (every step appends). The test passes string placeholder DATE
   values; coercion is deferred to parse time. Does the test
   adequately catch a regression where the loader collapses
   history rows via UPSERT?

5. **Alembic migration scale** â€” 1,220 lines for 107 tables in one
   file. The recon recommends single-tier batched migrations
   (`charter.md:75-79`). Is the file size still reviewable by a
   human reviewer, or should it split into part-files?

6. **Generator output quality** â€” sample first/last 100 lines of
   `0009_fdb_tier_a.py`. Are the column types reasonable (sa.Integer
   for NUMERIC, sa.Text for VARCHAR, sa.Date for DATE)? Note: the
   generator does NOT map VARCHAR(n) to sa.String(n) â€” it uses
   sa.Text uniformly. This is fine for Postgres (TEXT vs VARCHAR(n)
   has no storage difference) but loses the DDL-documented width.

7. **F4 coverage canary** still green at 107 specs. Confirm by
   reading `modules/drug-database/tests/unit/test_fdb_contract_coverage.py`
   â€” the pkgutil walk picks up all 11 batch test modules' BATCH_TESTED_NAMES.

## Verdict format

GO â€” B9.B closes; B9.C opens (Tier B â€” 66 NDC/GCN-keyed joins, plus the 6 reclassified residuals).
GO-WITH-FIXES â€” list residual HIGH / MEDIUM concerns.
NO-GO â€” fundamental issue requiring charter or plan revision.

For GO-WITH-FIXES, return concerns as:
| Severity | Area | Issue | Suggested fix |

codex
Iâ€™ll treat this as a gate review: verify the stated artifacts against the repo, sample the migration and tests, then return a GO / GO-WITH-FIXES / NO-GO verdict with concrete findings.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path waves/B9/plan.md -TotalCount 190 | Select-Object -Skip 120' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git log --oneline -18' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-ChildItem -Path modules/drug-database/drug_database/services/fdb_tier_a -Filter '*.py' | Select-Object -ExpandProperty Name; Get-ChildItem -Path modules/drug-database/tests/unit -Filter 'test_fdb_tier_a_batch_*.py' | Select-Object -ExpandProperty Name" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/tests/unit/test_fdb_contract_coverage.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 617ms:
"""B9.B C1 Ã¢â‚¬â€ F4 from codex GATE-CLOSE R1 MEDIUM 2.

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

UNKNOWN and TRUNCATE_RELOAD specs are intentionally excluded Ã¢â‚¬â€
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
# REGISTERED_SPECS with delta_semantics=UNKNOWN Ã¢â‚¬â€ they predate the
# contract template and are out of scope for this assertion.

codex
The absorption commit is present at `HEAD` and touches the expected loader, generator, migration, specs, tests, and status files. I’m drilling into the actual idempotency path now, because that is the main difference between a cosmetic close and a real gate close.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/drug_database/services/fdb_tier_loader.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/scripts/gen_fdb_tier_migration.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/drug_database/services/fdb_adapter.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/tests/unit/test_fdb_tier_loader.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 567ms:
"""B9.B C19 â€” Generic Tier-driven FDB loader (TableSpec â†’ Postgres).

The Phase 09 `fdb_pricing_ingester` was hand-coded for 3 tables.
B9.B+ needs a SPEC-driven path that ingests any TableSpec registered
in `fdb_specs.REGISTERED_SPECS` filtered by `loader_group`. This
module IS that path.

Per codex B9.B GATE-CLOSE R1 HIGH 1: the gate criterion says
`load_fdb.py --mode fdb_tier_a` re-run produces 0 net new rows.
That mode now lives in `scripts/load_fdb.py` and dispatches into
`load_tier_group()` below.

Public surface:

    load_tier_group(
        session,
        adapter,
        drop,
        *,
        group: str,
        dry_run: bool = False,
        ingestion_run_id: str | None = None,
    ) -> TierLoadResult

The loader uses INSERT ... ON CONFLICT (natural_key) DO UPDATE for
UPSERT_BY_NATURAL_KEY semantics, ON CONFLICT (natural_key) DO NOTHING
for all-NK junction tables, and plain INSERT for APPEND_ONLY.

The first weekly delta replay against the same drop produces 0 net
new rows for every spec (the SC-7 idempotency contract).
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import (
    Column,
    MetaData,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    FDBAdapter,
    FDBDrop,
    TableSpec,
)
from drug_database.services.fdb_loader_registry import filter_loadable_specs

_log = logging.getLogger(__name__)


@dataclass
class TierLoadResult:
    """Per-tier load summary returned by `load_tier_group`."""

    group: str
    drop_date: Any
    dry_run: bool
    table_summaries: dict[str, "TableLoadSummary"] = field(default_factory=dict)

    @property
    def total_inserted(self) -> int:
        return sum(s.inserted for s in self.table_summaries.values())

    @property
    def total_updated(self) -> int:
        return sum(s.updated for s in self.table_summaries.values())

    @property
    def total_skipped(self) -> int:
        return sum(s.skipped for s in self.table_summaries.values())


@dataclass
class TableLoadSummary:
    """Per-table load summary inside a TierLoadResult."""

    table_name: str
    rows_parsed: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


def load_tier_group(
    session: Session,
    adapter: FDBAdapter,
    drop: FDBDrop,
    *,
    group: str,
    dry_run: bool = False,
    fdb_load_mtl: bool = False,
    schema: str = "drug_database",
    specs: Sequence[TableSpec] | None = None,
) -> TierLoadResult:
    """Load every TableSpec in `group` from the drop into Postgres.

    Args:
        session: SQLAlchemy session bound to the reference DB.
        adapter: concrete FDBAdapter (typically FDBLocalDropAdapter).
        drop: target FDBDrop.
        group: `loader_group` filter (e.g., "fdb_tier_a"). Specs
            whose loader_group != group are skipped.
        dry_run: parse + count only; no writes.
        fdb_load_mtl: passed through to the MTL guard (see
            `fdb_loader_registry`). Default False excludes MTL.
        schema: target Postgres schema (default "drug_database").
        specs: override the registry-driven discovery (test seam).
            None â†’ import from `fdb_specs.REGISTERED_SPECS`.

    Returns:
        TierLoadResult with per-table counters.
    """
    if specs is None:
        from drug_database.services.fdb_specs import REGISTERED_SPECS
        specs = REGISTERED_SPECS

    eligible = filter_loadable_specs(
        specs, fdb_load_mtl=fdb_load_mtl, only_groups=[group]
    )
    if not eligible:
        _log.warning(
            "load_tier_group_no_specs group=%s â€” registry has no specs "
            "with loader_group=%s under fdb_load_mtl=%s",
            group, group, fdb_load_mtl,
        )

    result = TierLoadResult(group=group, drop_date=drop.drop_date, dry_run=dry_run)

    md = MetaData(schema=schema)
    for spec in eligible:
        summary = TableLoadSummary(table_name=spec.table_name)
        result.table_summaries[spec.table_name] = summary

        # Bind a generic Table reflecting only column names (all TEXT-typed
        # at the binding layer; coercion happens at parse time).
        table = Table(
            spec.table_name.lower(),
            md,
            *(Column(c, String) for c in spec.columns),
            extend_existing=True,
        )

        for row in adapter.parse_table(drop, spec):
            summary.rows_parsed += 1
            if dry_run:
                continue

            # Stringify Decimal / date values so they pass through generic
            # String columns; Postgres NUMERIC + DATE coerce from text.
            row_str = {
                k: (str(v) if v is not None else None)
                for k, v in row.items()
                if k in {c.name for c in table.columns}
            }

            stmt = pg_insert(table).values(**row_str)

            if spec.delta_semantics is DeltaSemantics.APPEND_ONLY:
                # Every row appends â€” no conflict resolution.
                session.execute(stmt)
                summary.inserted += 1
            elif spec.delta_semantics in {
                DeltaSemantics.UPSERT_BY_NATURAL_KEY,
                DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
            }:
                if not spec.natural_key:
                    raise ValueError(
                        f"{spec.table_name}: UPSERT semantics requires "
                        f"natural_key; got empty."
                    )
                non_key_cols = [
                    c for c in spec.columns if c not in spec.natural_key
                ]
                if non_key_cols:
                    update_set = {
                        c: row_str[c] for c in non_key_cols if c in row_str
                    }
                    stmt = stmt.on_conflict_do_update(
                        index_elements=list(spec.natural_key),
                        set_=update_set,
                    )
                else:
                    # All-NK junction table â€” DO NOTHING is the correct
                    # semantic (there's nothing to update).
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=list(spec.natural_key)
                    )
                session.execute(stmt)
                # Per-row insert-vs-update accounting requires RETURNING
                # xmax/xmin which is dialect-specific. The wave's
                # post-load reconciliation comes from row-count diffs,
                # not from this counter.
                summary.inserted += 1
            else:
                # UNKNOWN / TRUNCATE_RELOAD â€” out of scope for this
                # generic loader. Log + skip; specialized loaders
                # handle these in B9.D / B9.F.
                _log.warning(
                    "load_tier_group_unsupported_semantics table=%s "
                    "semantics=%s",
                    spec.table_name, spec.delta_semantics.value,
                )
                summary.skipped += 1

        if not dry_run:
            session.commit()
        _log.info(
            "load_tier_group_table_done table=%s parsed=%d inserted=%d "
            "updated=%d skipped=%d",
            spec.table_name,
            summary.rows_parsed,
            summary.inserted,
            summary.updated,
            summary.skipped,
        )

    return result


__all__ = ["TierLoadResult", "TableLoadSummary", "load_tier_group"]

 succeeded in 566ms:
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
    # B9.B GATE-CLOSE R1 MEDIUM 2 mitigation â€” per-precision Decimal coercers
    if name == "decimal_16_6":
        return "sa.Numeric(16, 6)"

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
    """Generate the op.create_table(...) call for one table.

    When `spec.natural_key` is non-empty, emits a PrimaryKeyConstraint
    over those columns so Postgres `ON CONFLICT (natural_key)` upserts
    have a unique surface to bind to.  Per codex B9.B GATE-CLOSE R1
    HIGH 2.
    """
    table_name = spec.table_name.lower()  # FDB names are upper; DB tables snake_case
    rcounts_key = spec.record_counts_key or spec.table_name
    pk_line = ""
    if spec.natural_key:
        pk_cols = ", ".join(repr(c) for c in spec.natural_key)
        pk_line = (
            f'\n        sa.PrimaryKeyConstraint({pk_cols}, '
            f'name="pk_{table_name}"),'
        )
    return f"""    # {spec.table_name} â€” tier={spec.tier.value} delta={spec.delta_semantics.value} record_counts_key={rcounts_key}
    op.create_table(
        "{table_name}",
{_column_block(spec)}{pk_line}
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
    # Import here to avoid a circular: fdb_adapter imports nothing from
    # this module, but `generate_tier_migration` is itself invoked by
    # scripts that import fdb_adapter via the registry.
    from drug_database.services.fdb_adapter import DeltaSemantics  # noqa: E402

    _checkable = {
        DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
    }
    for spec in specs:
        if spec.tier is not tier:
            raise ValueError(
                f"Spec {spec.table_name!r} has tier {spec.tier.value} "
                f"but generator was invoked for tier {tier.value}."
            )
        # B9.B GATE-CLOSE R1 HIGH 2: every UPSERT spec MUST declare a
        # natural_key so the migration can emit a PRIMARY KEY for
        # Postgres ON CONFLICT to bind to. Without this the migration
        # creates columns but no uniqueness surface â€” upsert fails at
        # runtime with `there is no unique or exclusion constraint`.
        if spec.delta_semantics in _checkable and not spec.natural_key:
            raise ValueError(
                f"Spec {spec.table_name!r} has delta_semantics="
                f"{spec.delta_semantics.value} but natural_key is empty. "
                f"Set natural_key=(<key col(s)>,) on the TableSpec so the "
                f"generated migration emits a PRIMARY KEY for ON CONFLICT "
                f"to bind to (B9.B GATE-CLOSE R1 HIGH 2)."
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

 succeeded in 622ms:
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


def decimal_16_6(raw: str) -> Decimal:
    """Decimal coercer for NUMERIC(16,6) columns (UOM_CONVERSION_FACTOR).

    Default `Decimal` coercer is generator-mapped to `sa.Numeric(16, 5)`
    (FDB pricing precision). Some non-money columns ship with NUMERIC(16,6)
    in the DDL â€” most notably `RPEIUC0_UOM_CONVERSION.UOM_CONVERSION_FACTOR`.
    Using this named coercer signals the generator to emit `Numeric(16, 6)`
    instead, preserving DDL precision exactly.

    Codex B9.B GATE-CLOSE R1 MEDIUM 2 mitigation.
    """
    return Decimal(raw)


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
      natural_key:        tuple of column names that form the table's
                          natural key (PRIMARY KEY in the emitted DDL).
                          Required for `UPSERT_BY_NATURAL_KEY` /
                          `UPSERT_WITH_EFFECTIVE_DATE` semantics â€”
                          Postgres `ON CONFLICT` needs a matching
                          unique constraint surface. Empty default
                          preserves Phase 09 specs (RNP3 uses a
                          composite unique covered separately by the
                          0008 migration).  Codex B9.B GATE-CLOSE
                          R1 HIGH 2 mitigation.
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
    natural_key: tuple[str, ...] = ()


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

 succeeded in 558ms:
"""B9.B C19 â€” Unit tests for the generic Tier-driven FDB loader.

Tests the `load_tier_group` dispatcher against an in-memory SQLite
engine. Real Postgres integration runs at B9.B mini-GATE-CLOSE
follow-on.

Specifically validates the codex B9.B GATE-CLOSE R1 HIGH 1 mitigation:
the generic loader dispatches on `delta_semantics` (UPSERT vs
APPEND_ONLY) and replays cleanly (0 net new rows on second run).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import Session

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    FDBAdapter,
    FDBDrop,
    TableSpec,
    Tier,
)


# ---------------------------------------------------------------------------
# Fake adapter â€” returns canned rows per spec
# ---------------------------------------------------------------------------


class _FakeAdapter(FDBAdapter):
    """In-memory adapter; returns rows from a dict keyed by table_name."""

    def __init__(self, rows_by_table: dict[str, list[dict]]) -> None:
        self._rows = rows_by_table

    def discover_latest_drop(self) -> FDBDrop:
        return FDBDrop(
            drop_date=date(2026, 5, 6),
            license_code="TEL000000T",
            db_zip_path=Path("/dev/null"),
            ddl_zip_path=Path("/dev/null"),
            upd_zip_path=Path("/dev/null"),
            highlights_zip_path=Path("/dev/null"),
            record_counts_path=Path("/dev/null"),
        )

    def open_table(self, drop, table_name, *, source="DB"):  # pragma: no cover
        return iter([])

    def parse_table(self, drop, spec, *, source="DB"):
        for row in self._rows.get(spec.table_name, []):
            yield row


@pytest.fixture
def sqlite_engine():
    return create_engine("sqlite:///:memory:", future=True)


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------


_UPSERT_SPEC = TableSpec(
    table_name="RFOO_TEST",
    columns=("code", "desc_text"),
    coercers={"code": str, "desc_text": str},
    tier=Tier.A,
    loader_group="fdb_tier_a",
    record_counts_key="RFOO",
    delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    natural_key=("code",),
)

_APPEND_ONLY_SPEC = TableSpec(
    table_name="RBAR_HIST",
    columns=("repl_id", "prev_id"),
    coercers={"repl_id": int, "prev_id": int},
    tier=Tier.A,
    loader_group="fdb_tier_a",
    record_counts_key="RBAR",
    delta_semantics=DeltaSemantics.APPEND_ONLY,
)


def _setup_sqlite_tables(engine, specs: list[TableSpec], schema_name: str) -> None:
    """Create empty SQLite tables matching each spec (column names only)."""
    md = MetaData()
    for spec in specs:
        Table(
            spec.table_name.lower(),
            md,
            *(Column(c, String) for c in spec.columns),
            extend_existing=True,
        )
    md.create_all(engine)


# ---------------------------------------------------------------------------
# load_tier_group behaviors
# ---------------------------------------------------------------------------


def test_load_tier_group_filters_by_group(sqlite_engine) -> None:
    """Only specs whose loader_group matches `group` are loaded."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    other_spec = TableSpec(
        table_name="RBAZ_OTHER",
        columns=("x",),
        coercers={"x": str},
        tier=Tier.A,
        loader_group="fdb_tier_b",  # not in fdb_tier_a
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=("x",),
    )
    adapter = _FakeAdapter({"RBAZ_OTHER": [{"x": "skipped"}]})
    drop = adapter.discover_latest_drop()
    with Session(sqlite_engine) as session:
        result = load_tier_group(
            session, adapter, drop,
            group="fdb_tier_a", specs=[other_spec], dry_run=True,
        )
    # No specs eligible â†’ empty result.
    assert result.group == "fdb_tier_a"
    assert result.table_summaries == {}


def test_load_tier_group_dry_run_parses_but_does_not_write(sqlite_engine) -> None:
    """dry_run=True increments rows_parsed but inserted=0."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    adapter = _FakeAdapter({
        "RFOO_TEST": [{"code": "a", "desc_text": "alpha"}],
    })
    drop = adapter.discover_latest_drop()
    with Session(sqlite_engine) as session:
        result = load_tier_group(
            session, adapter, drop,
            group="fdb_tier_a", specs=[_UPSERT_SPEC], dry_run=True,
        )
    summary = result.table_summaries["RFOO_TEST"]
    assert summary.rows_parsed == 1
    assert summary.inserted == 0


def test_load_tier_group_unsupported_semantics_skipped(sqlite_engine) -> None:
    """UNKNOWN / TRUNCATE_RELOAD specs are skipped with a warning."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    unknown_spec = TableSpec(
        table_name="RBAZ_UNKNOWN",
        columns=("x",),
        coercers={"x": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.UNKNOWN,
    )
    _setup_sqlite_tables(sqlite_engine, [unknown_spec], "drug_database")
    adapter = _FakeAdapter({"RBAZ_UNKNOWN": [{"x": "1"}]})
    drop = adapter.discover_latest_drop()
    with Session(sqlite_engine) as session:
        result = load_tier_group(
            session, adapter, drop,
            group="fdb_tier_a", specs=[unknown_spec], dry_run=False,
        )
    summary = result.table_summaries["RBAZ_UNKNOWN"]
    assert summary.rows_parsed == 1
    assert summary.skipped == 1


def test_load_tier_group_upsert_requires_natural_key() -> None:
    """UPSERT_BY_NATURAL_KEY spec without natural_key raises at runtime."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    bad_spec = TableSpec(
        table_name="RBAD_TEST",
        columns=("x",),
        coercers={"x": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        # natural_key=() â€” empty, the regression
    )
    adapter = _FakeAdapter({"RBAD_TEST": [{"x": "1"}]})
    drop = adapter.discover_latest_drop()
    engine = create_engine("sqlite:///:memory:", future=True)
    _setup_sqlite_tables(engine, [bad_spec], "drug_database")
    with Session(engine) as session:
        with pytest.raises(ValueError, match="natural_key"):
            load_tier_group(
                session, adapter, drop,
                group="fdb_tier_a", specs=[bad_spec], dry_run=False,
            )


def test_load_tier_group_summary_aggregates_per_table(sqlite_engine) -> None:
    """TierLoadResult sums inserted/skipped across multiple specs."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    spec_b = TableSpec(
        table_name="RFOO2_TEST",
        columns=("code", "desc_text"),
        coercers={"code": str, "desc_text": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=("code",),
    )
    adapter = _FakeAdapter({
        "RFOO_TEST": [{"code": "a", "desc_text": "alpha"}],
        "RFOO2_TEST": [{"code": "b", "desc_text": "beta"}, {"code": "c", "desc_text": "gamma"}],
    })
    drop = adapter.discover_latest_drop()
    with Session(sqlite_engine) as session:
        result = load_tier_group(
            session, adapter, drop,
            group="fdb_tier_a", specs=[_UPSERT_SPEC, spec_b], dry_run=True,
        )
    assert len(result.table_summaries) == 2
    assert result.table_summaries["RFOO_TEST"].rows_parsed == 1
    assert result.table_summaries["RFOO2_TEST"].rows_parsed == 2

codex
The loader implements `ON CONFLICT` for UPSERT specs, but I’m checking one important edge case: Tier A includes APPEND_ONLY history specs, and the current loader intentionally plain-inserts them. That may conflict with the stated “re-run produces 0 net new rows” criterion unless the criterion is scoped to UPSERT specs only.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n \"PrimaryKeyConstraint|Numeric\\(16, 6\\)|Numeric\\(16, 5\\)|op.create_table\\(\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "natural_key=|delta_semantics=DeltaSemantics|APPEND_ONLY|UPSERT" modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path scripts/load_fdb.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
2026-05-12T15:18:51.402031Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.5 seconds
Output:
rg: modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: IO error for operation on modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)

 exited 1 in 494ms:
rg: modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: IO error for operation on modules/drug-database/drug_database/services/fdb_tier_a/batch_*.py: The filename, directory name, or volume label syntax is incorrect. (os error 123)

 succeeded in 495ms:
46:    op.create_table(
50:        sa.PrimaryKeyConstraint('AHFS8', name="pk_rahfsd1_desc"),
55:    op.create_table(
59:        sa.PrimaryKeyConstraint('APPL_RELATION_TYPE_ID', name="pk_raplrt0_appl_relation_type"),
64:    op.create_table(
68:        sa.PrimaryKeyConstraint('APPL_TYPE_CD', name="pk_rappltd0_fda_appl_type"),
73:    op.create_table(
77:        sa.PrimaryKeyConstraint('ATC', name="pk_ratcd0_atc_desc"),
82:    op.create_table(
86:        sa.PrimaryKeyConstraint('BIOLOGIC_NAME_GROUPER_ID', name="pk_rblang0_name_grp_desc"),
91:    op.create_table(
95:        sa.PrimaryKeyConstraint('SUBSTANCE_GROUP_ID', name="pk_rblasg0_substance_grp_desc"),
100:    op.create_table(
104:        sa.PrimaryKeyConstraint('DCC', name="pk_rdccd0_drug_cat_desc"),
109:    op.create_table(
113:        sa.PrimaryKeyConstraint('ETC_CHANGE_TYPE_CODE', name="pk_retcctd0_etc_change_type_desc"),
118:    op.create_table(
122:        sa.PrimaryKeyConstraint('GTC', name="pk_rgtcd0_gen_therap_class_desc"),
127:    op.create_table(
131:        sa.PrimaryKeyConstraint('ING_STATUS_CD', name="pk_rhicscd0_ing_stat_cd_desc"),
136:    op.create_table(
140:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID_TYP', name="pk_rmedcd0_med_concept_typ_desc"),
145:    op.create_table(
149:        sa.PrimaryKeyConstraint('MOVE_REASON_CD', name="pk_rmedmrd0_move_reason_desc"),
154:    op.create_table(
159:        sa.PrimaryKeyConstraint('APPL_TYPE_ID', name="pk_raplt0_appl_type"),
164:    op.create_table(
169:        sa.PrimaryKeyConstraint('GCDF', name="pk_rdosed2_dose_desc"),
174:    op.create_table(
179:        sa.PrimaryKeyConstraint('HIC1_SEQN', name="pk_rhic1d2_hic_organ_sys_desc"),
184:    op.create_table(
190:        sa.PrimaryKeyConstraint('HIC2_SEQN', name="pk_rhic2d3_hic_rx_class_desc"),
195:    op.create_table(
202:        sa.PrimaryKeyConstraint('HIC3_SEQN', name="pk_rhic3d3_hic_therap_class_desc"),
207:    op.create_table(
212:        sa.PrimaryKeyConstraint('LBLRID', name="pk_rlblrid3_lblr_desc"),
217:    op.create_table(
221:        sa.PrimaryKeyConstraint('MEDID_SPECIFICATION_CODE', name="pk_rmedspd0_specification_desc"),
226:    op.create_table(
233:        sa.PrimaryKeyConstraint('MEDID', name="pk_rmedst0_medid_search_term"),
238:    op.create_table(
242:        sa.PrimaryKeyConstraint('SEARCH_TERM_TYPE_CD', name="pk_rmedstd0_search_term_type_desc"),
247:    op.create_table(
251:        sa.PrimaryKeyConstraint('MED_REF_DESI2_IND', name="pk_rmide2d1_ref_desi2_ind_desc"),
256:    op.create_table(
260:        sa.PrimaryKeyConstraint('MED_REF_DEA_CD', name="pk_rmidead1_ref_fed_dea_desc"),
265:    op.create_table(
269:        sa.PrimaryKeyConstraint('MED_REF_DESI_IND', name="pk_rmidesd1_ref_desi_ind_desc"),
274:    op.create_table(
279:        sa.PrimaryKeyConstraint('MED_DOSAGE_FORM_ID', name="pk_rmidfd1_dose_form"),
284:    op.create_table(
291:        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', name="pk_rmidfid1_routed_dose_form_med"),
296:    op.create_table(
300:        sa.PrimaryKeyConstraint('MED_GCNSEQNO_ASSIGN_CD', name="pk_rmigcnd1_gcnseqno_assgn_desc"),
305:    op.create_table(
309:        sa.PrimaryKeyConstraint('MED_REF_GEN_THERA_EQU_CD', name="pk_rmigecd1_ref_gen_therap_desc"),
314:    op.create_table(
318:        sa.PrimaryKeyConstraint('MED_REF_GEN_DRUG_NAME_CD', name="pk_rmigncd1_ref_gen_name_desc"),
323:    op.create_table(
327:        sa.PrimaryKeyConstraint('MED_REF_GEN_COMP_PRICE_CD', name="pk_rmigpcd1_ref_gen_prc_desc"),
332:    op.create_table(
336:        sa.PrimaryKeyConstraint('MED_REF_GEN_SPREAD_CD', name="pk_rmigscd1_ref_gen_prc_sprd_desc"),
341:    op.create_table(
345:        sa.PrimaryKeyConstraint('MED_REF_INNOV_IND', name="pk_rmiinnd1_ref_innov_ind_desc"),
350:    op.create_table(
354:        sa.PrimaryKeyConstraint('MED_REF_FED_LEGEND_IND', name="pk_rmilgnd1_ref_fed_lgnd_desc"),
359:    op.create_table(
363:        sa.PrimaryKeyConstraint('MED_REF_MULTI_SOURCE_CD', name="pk_rmimltd1_ref_multi_src_desc"),
368:    op.create_table(
372:        sa.PrimaryKeyConstraint('MED_NAME_SOURCE_CD', name="pk_rminamd1_name_src_desc"),
377:    op.create_table(
381:        sa.PrimaryKeyConstraint('MED_NAME_TYPE_CD', name="pk_rminmd1_med_name_type_desc"),
386:    op.create_table(
393:        sa.PrimaryKeyConstraint('ROUTED_MED_ID', name="pk_rmirmid1_routed_med"),
398:    op.create_table(
403:        sa.PrimaryKeyConstraint('MED_ROUTE_ID', name="pk_rmirtd1_route"),
408:    op.create_table(
412:        sa.PrimaryKeyConstraint('MED_STATUS_CD', name="pk_rmiscd1_status_desc"),
417:    op.create_table(
422:        sa.PrimaryKeyConstraint('OBC', name="pk_robcd0_obc_desc"),
427:    op.create_table(
433:        sa.PrimaryKeyConstraint('ATTRIBUTE_CODE', name="pk_rpeiad0_attribute_desc"),
438:    op.create_table(
444:        sa.PrimaryKeyConstraint('ATTRIBUTE_TYPE_CODE', name="pk_rpeiat0_attribute_type_desc"),
449:    op.create_table(
454:        sa.PrimaryKeyConstraint('ATTRIBUTE_CODE', name="pk_rpeiav0_attribute_value_desc"),
459:    op.create_table(
463:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ATTRIBUTE_ID', name="pk_rpeidfa0_dosage_form_attribute"),
468:    op.create_table(
475:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', name="pk_rpeidm0_dosage_form_mstr"),
480:    op.create_table(
484:        sa.PrimaryKeyConstraint('DOSAGE_FORM_TYPE_ID', name="pk_rpeidt0_dosage_form_type"),
489:    op.create_table(
493:        sa.PrimaryKeyConstraint('PATIENT_PARAM_REQ_CD', name="pk_rpeipp0_patient_param_req_desc"),
498:    op.create_table(
502:        sa.PrimaryKeyConstraint('RT_LABELED_ID', name="pk_rpeirl0_rt_labeled_desc"),
507:    op.create_table(
511:        sa.PrimaryKeyConstraint('STR_CONC_TYPE_ID', name="pk_rpeist0_str_conc_type"),
516:    op.create_table(
520:        sa.PrimaryKeyConstraint('UOM_TYPE_CD', name="pk_rpeiut0_uom_type_desc"),
525:    op.create_table(
529:        sa.PrimaryKeyConstraint('CURRENCY_CD', name="pk_rprdcc0_currency_cd_desc"),
534:    op.create_table(
540:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_CD', name="pk_rprdpad0_price_attr_desc"),
545:    op.create_table(
549:        sa.PrimaryKeyConstraint('NDC_ATTRIBUTE_TYPE_CD', name="pk_rndctd0_ndc_attribute_typ_dsc"),
554:    op.create_table(
559:        sa.PrimaryKeyConstraint('NDC_ATTRIBUTE_TYPE_CD', name="pk_rndcvd0_ndc_attribute_valu_dsc"),
564:    op.create_table(
570:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_TYPE_CD', name="pk_rprdpat0_price_attr_type_desc"),
575:    op.create_table(
580:        sa.PrimaryKeyConstraint('PRICE_ATTRIBUTE_CD', name="pk_rprdpav0_price_attr_value_desc"),
585:    op.create_table(
592:        sa.PrimaryKeyConstraint('EXT_PRODUCT_CD_TYPE_ID', name="pk_rprdpcd0_ext_product_cd_desc"),
597:    op.create_table(
603:        sa.PrimaryKeyConstraint('PACKAGE_TYPE_ID', name="pk_rprdpkd0_package_desc"),
608:    op.create_table(
613:        sa.PrimaryKeyConstraint('FDB_PRODUCT_STATUS_CD', name="pk_rprdsd0_product_status_desc"),
618:    op.create_table(
622:        sa.PrimaryKeyConstraint('PRICE_UOM_ID', name="pk_rprduom0_price_qty_uom"),
627:    op.create_table(
634:        sa.PrimaryKeyConstraint('GCRT', name="pk_rrouted3_route_desc"),
639:    op.create_table(
646:        sa.PrimaryKeyConstraint('ROUTED_GEN_ID', name="pk_rrtgn0_routed_gen_mstr"),
651:    op.create_table(
655:        sa.PrimaryKeyConstraint('ROUTED_GEN_STATUS_CD', name="pk_rrtgnsd0_rtd_gen_status_dsc"),
660:    op.create_table(
667:        sa.PrimaryKeyConstraint('STR60', name="pk_rstr1_strngth_desc"),
672:    op.create_table(
676:        sa.PrimaryKeyConstraint('STRENGTH_STATUS_CODE', name="pk_rstrscd0_strength_status_desc"),
681:    op.create_table(
685:        sa.PrimaryKeyConstraint('STRENGTH_TYP_CODE', name="pk_rstrtd0_strength_typ_desc"),
690:    op.create_table(
696:        sa.PrimaryKeyConstraint('UOM_ID', name="pk_rstruom0_strength_uom"),
701:    op.create_table(
705:        sa.PrimaryKeyConstraint('TC', name="pk_rtcd0_std_therap_class_desc"),
710:    op.create_table(
714:        sa.PrimaryKeyConstraint('TM_NAME_TYPE_ID', name="pk_rtmdt0_tm_name_type"),
719:    op.create_table(
723:        sa.PrimaryKeyConstraint('TM_GROUP_ID', name="pk_rtmgrpd1_tm_group_desc"),
728:    op.create_table(
732:        sa.PrimaryKeyConstraint('TM_GNN_TYPE_ID', name="pk_rtmngt0_tm_gnn_type"),
737:    op.create_table(
741:        sa.PrimaryKeyConstraint('TM_SOURCE_ID', name="pk_rtmsrcd1_tm_source_desc"),
746:    op.create_table(
752:        sa.PrimaryKeyConstraint('ROUTED_DOSAGE_FORM_MED_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmdfid1_tm_routed_df_med"),
757:    op.create_table(
763:        sa.PrimaryKeyConstraint('MEDID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmmid1_tm_med"),
768:    op.create_table(
775:        sa.PrimaryKeyConstraint('HICL_SEQNO', 'TM_GNN_TYPE_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmngn0_tm_gnn"),
780:    op.create_table(
786:        sa.PrimaryKeyConstraint('MED_NAME_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmnmid1_tm_med_name"),
791:    op.create_table(
797:        sa.PrimaryKeyConstraint('ROUTED_MED_ID', 'TM_SOURCE_ID', 'TM_IND', name="pk_rtmrmid1_tm_routed_med"),
802:    op.create_table(
813:    op.create_table(
824:    op.create_table(
835:    op.create_table(
844:    op.create_table(
853:    op.create_table(
862:    op.create_table(
871:    op.create_table(
880:    op.create_table(
884:        sa.PrimaryKeyConstraint('ETC_SEARCH_ETC_ID', 'ETC_PRODUCT_RELATED_ETC_ID', name="pk_retcsch0_etc_search"),
889:    op.create_table(
893:        sa.PrimaryKeyConstraint('ETC_ID', 'HIC3_SEQN', name="pk_retcxrf0_etc_hic3_etc"),
898:    op.create_table(
902:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'DOSAGE_FORM_ATTRIBUTE_ID', name="pk_rpeial0_df_attribute_link"),
907:    op.create_table(
912:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'GCDF', name="pk_rpeigl0_gen_df_mstr_link"),
917:    op.create_table(
922:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'MED_DOSAGE_FORM_ID', name="pk_rpeiml0_med_df_mstr_link"),
927:    op.create_table(
932:        sa.PrimaryKeyConstraint('DOSAGE_FORM_ID', 'OVW_DOSAGE_FORM_ID', name="pk_rpeiol0_ovw_df_mstr_link"),
937:    op.create_table(
941:        sa.PrimaryKeyConstraint('CONTINUOUS_RT_ID', 'INTERMITTENT_RT_ID', name="pk_rpeirer0_related_rt"),
946:    op.create_table(
950:        sa.PrimaryKeyConstraint('PARENT_RT_ID', 'CLINICAL_RT_ID', name="pk_rpeirh0_rt_hierarchy"),
955:    op.create_table(
959:        sa.Column('UOM_CONVERSION_FACTOR', sa.Numeric(16, 6), nullable=False),
960:        sa.PrimaryKeyConstraint('FROM_UOM_MSTR_ID', 'TO_UOM_MSTR_ID', name="pk_rpeiuc0_uom_conversion"),
965:    op.create_table(
970:        sa.PrimaryKeyConstraint('DOSING_MODULE_UNIT_ABBREV', name="pk_runitsd0_units_desc"),
975:    op.create_table(
979:        sa.PrimaryKeyConstraint('XRF_SOURCE_ID', name="pk_rxrnsrc0_source_desc"),
984:    op.create_table(
991:        sa.PrimaryKeyConstraint('BLA_APPL_NBR', 'APPL_TYPE_ID', 'BIOLOGICS_SN', 'MULTI_INGREDIENT_SN', name="pk_rblahic0_ingredients"),
996:    op.create_table(
1002:        sa.PrimaryKeyConstraint('PROPRIETARY_NAME_ID', name="pk_rblapn0_proprietary_name"),
1007:    op.create_table(
1013:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'GENERIC_MED_CONCEPT_ID', name="pk_rmedmgl0_med_generic_med_link"),
1018:    op.create_table(
1025:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'HICL_SEQNO', name="pk_rmedmhl0_med_hiclseqno_link"),
1030:    op.create_table(
1037:        sa.PrimaryKeyConstraint('FDB_PRODUCT_ID', 'EXT_PRODUCT_CD_TYPE_ID', 'EXT_PRODUCT_CD_START_DT', 'EXT_PRODUCT_CD', name="pk_rprdpc0_ext_product_cd"),
1042:    op.create_table(
1047:        sa.PrimaryKeyConstraint('DAM_AGCSP', 'HIC_SEQN', name="pk_rxrfahx0_agcsp_hicseqn"),
1052:    op.create_table(
1056:        sa.PrimaryKeyConstraint('DACN', 'DAM_AGCSP', name="pk_rxrfddx0_dacn_agcsp"),
1061:    op.create_table(
1065:        sa.PrimaryKeyConstraint('GCDF', 'SCRIPT_QQ_ID', name="pk_rxrgdfq0_gcdf_script_qq"),
1070:    op.create_table(
1074:        sa.PrimaryKeyConstraint('MED_DOSAGE_FORM_ID', 'SCRIPT_QQ_ID', name="pk_rxrmdfq0_meddosfm_script_qq"),
1079:    op.create_table(
1086:        sa.PrimaryKeyConstraint('SCRIPT_QQ_ID', name="pk_rxrncqq0_qq_mstr"),
1091:    op.create_table(
1095:        sa.PrimaryKeyConstraint('POEUNITCDE', 'SCRIPT_QQ_ID', name="pk_rxrpdfq0_poemdosfm_script_qq"),

 succeeded in 492ms:
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
    """A minimal valid Tier A TableSpec for tests.

    B9.B GATE-CLOSE R1 HIGH 2: UPSERT specs MUST declare natural_key
    so the generator can emit a PRIMARY KEY constraint. Without it
    the generator raises ValueError.
    """
    return TableSpec(
        table_name=name,
        columns=("med_name_id", "med_name"),
        coercers={"med_name_id": int, "med_name": str},
        tier=Tier.A,
        record_counts_key=name.split("_")[0],
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=("med_name_id",),
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

 succeeded in 515ms:
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
        choices=["fdb_initial", "fdb_weekly", "fdb_rebase", "fdb_tier_a"],
        required=True,
        help=(
            "ingestion mode. Phase 09: fdb_initial / fdb_weekly / "
            "fdb_rebase (pricing-only via FDBPricingIngester). B9.B+: "
            "fdb_tier_a (generic TableSpec-driven loader; reads "
            "fdb_specs.REGISTERED_SPECS filtered by loader_group='fdb_tier_a')."
        ),
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

        if args.mode == "fdb_tier_a":
            # B9.B C19: generic TableSpec-driven loader.
            from drug_database.services.fdb_tier_loader import load_tier_group
            drop = adapter.discover_latest_drop()
            tier_result = load_tier_group(
                session, adapter, drop,
                group="fdb_tier_a", dry_run=args.dry_run,
            )
            logger.info(
                "fdb_ingest_summary mode=%s drop_date=%s "
                "tables_loaded=%d total_inserted=%d total_skipped=%d "
                "dry_run=%s",
                args.mode, tier_result.drop_date,
                len(tier_result.table_summaries),
                tier_result.total_inserted,
                tier_result.total_skipped,
                tier_result.dry_run,
            )
            return 0

        # Phase 09 modes â€” fdb_initial / fdb_weekly / fdb_rebase
        from drug_database.services.fdb_pricing_ingester import FDBPricingIngester
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

exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -g "batch_*.py" "natural_key=|delta_semantics=DeltaSemantics|APPEND_ONLY|UPSERT" modules/drug-database/drug_database/services/fdb_tier_a' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -o "PrimaryKeyConstraint" modules/drug-database/alembic/versions/0009_fdb_tier_a.py | Measure-Object | Select-Object -ExpandProperty Count' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -o \"Numeric\\(16, 6\\)\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py | Measure-Object | Select-Object -ExpandProperty Count" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -o \"Numeric\\(16, 5\\)\" modules/drug-database/alembic/versions/0009_fdb_tier_a.py | Measure-Object | Select-Object -ExpandProperty Count" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 510ms:
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:12:  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:37:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:38:        natural_key=('MED_REF_DEA_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:48:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:49:        natural_key=('MED_REF_DESI_IND',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:63:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:64:        natural_key=('MED_DOSAGE_FORM_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:86:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:87:        natural_key=('ROUTED_DOSAGE_FORM_MED_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:97:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:98:        natural_key=('MED_GCNSEQNO_ASSIGN_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:111:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:112:        natural_key=('MED_REF_GEN_THERA_EQU_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:125:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:126:        natural_key=('MED_REF_GEN_DRUG_NAME_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:139:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:140:        natural_key=('MED_REF_GEN_COMP_PRICE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:153:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:154:        natural_key=('MED_REF_GEN_SPREAD_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:164:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_03.py:165:        natural_key=('MED_REF_INNOV_IND',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:40:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:41:        natural_key=('NDC_ATTRIBUTE_TYPE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:59:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:60:        natural_key=('NDC_ATTRIBUTE_TYPE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:81:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:82:        natural_key=('PRICE_ATTRIBUTE_TYPE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:101:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:102:        natural_key=('PRICE_ATTRIBUTE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:125:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:126:        natural_key=('EXT_PRODUCT_CD_TYPE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:146:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:147:        natural_key=('PACKAGE_TYPE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:166:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:167:        natural_key=('FDB_PRODUCT_STATUS_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:180:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:181:        natural_key=('PRICE_UOM_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:204:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:205:        natural_key=('GCRT',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:227:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_06.py:228:        natural_key=('ROUTED_GEN_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:45:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:46:        natural_key=('ATTRIBUTE_CODE',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:59:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:60:        natural_key=('DOSAGE_FORM_ATTRIBUTE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:85:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:86:        natural_key=('DOSAGE_FORM_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:99:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:100:        natural_key=('DOSAGE_FORM_TYPE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:113:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:114:        natural_key=('PATIENT_PARAM_REQ_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:127:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:128:        natural_key=('RT_LABELED_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:141:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:142:        natural_key=('STR_CONC_TYPE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:155:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:156:        natural_key=('UOM_TYPE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:169:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:170:        natural_key=('CURRENCY_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:191:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_05.py:192:        natural_key=('PRICE_ATTRIBUTE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:9:    record_counts_key=<FDB key>, delta_semantics=UPSERT_BY_NATURAL_KEY
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:44:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:45:        natural_key=('AHFS8',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:55:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:56:        natural_key=('APPL_RELATION_TYPE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:66:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:67:        natural_key=('APPL_TYPE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:78:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:79:        natural_key=('ATC',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:92:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:93:        natural_key=('BIOLOGIC_NAME_GROUPER_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:103:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:104:        natural_key=('SUBSTANCE_GROUP_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:115:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:116:        natural_key=('DCC',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:130:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:131:        natural_key=('ETC_CHANGE_TYPE_CODE',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:142:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:143:        natural_key=('GTC',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:154:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:155:        natural_key=('ING_STATUS_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:166:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:167:        natural_key=('MED_CONCEPT_ID_TYP',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:177:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_01.py:178:        natural_key=('MOVE_REASON_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:16:  * delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:43:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:44:        natural_key=('APPL_TYPE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:55:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:56:        natural_key=('GCDF',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:67:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:68:        natural_key=('HIC1_SEQN',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:84:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:85:        natural_key=('HIC2_SEQN',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:102:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:103:        natural_key=('HIC3_SEQN',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:114:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:115:        natural_key=('LBLRID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:128:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:129:        natural_key=('MEDID_SPECIFICATION_CODE',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:151:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:152:        natural_key=('MEDID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:165:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:166:        natural_key=('SEARCH_TERM_TYPE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:176:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_02.py:177:        natural_key=('MED_REF_DESI2_IND',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:40:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:41:        natural_key=('MED_REF_FED_LEGEND_IND',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:54:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:55:        natural_key=('MED_REF_MULTI_SOURCE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:68:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:69:        natural_key=('MED_NAME_SOURCE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:82:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:83:        natural_key=('MED_NAME_TYPE_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:105:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:106:        natural_key=('ROUTED_MED_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:120:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:121:        natural_key=('MED_ROUTE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:134:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:135:        natural_key=('MED_STATUS_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:150:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:151:        natural_key=('OBC',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:172:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:173:        natural_key=('ATTRIBUTE_CODE',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:194:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_04.py:195:        natural_key=('ATTRIBUTE_TYPE_CODE',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:16:Delta semantics: still UPSERT_BY_NATURAL_KEY. A change to the desc
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:48:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:49:        natural_key=('ROUTED_DOSAGE_FORM_MED_ID', 'TM_SOURCE_ID', 'TM_IND'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:64:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:65:        natural_key=('MEDID', 'TM_SOURCE_ID', 'TM_IND'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:87:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:88:        natural_key=('HICL_SEQNO', 'TM_GNN_TYPE_ID', 'TM_SOURCE_ID', 'TM_IND'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:108:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:109:        natural_key=('MED_NAME_ID', 'TM_SOURCE_ID', 'TM_IND'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:129:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_08.py:130:        natural_key=('ROUTED_MED_ID', 'TM_SOURCE_ID', 'TM_IND'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY history template, 8 tables).
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:3:Every B9.B batch so far has used `UPSERT_BY_NATURAL_KEY`. The
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle assert that every
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:51:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:74:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:97:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:112:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:131:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:145:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:159:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_09.py:177:        delta_semantics=DeltaSemantics.APPEND_ONLY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:10:  still toggled in the C step of the ACD cycle per the UPSERT contract.
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:33:Delta semantics: all 11 tables are UPSERT_BY_NATURAL_KEY. Weekly FDB
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:71:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:72:        natural_key=('ETC_SEARCH_ETC_ID', 'ETC_PRODUCT_RELATED_ETC_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:90:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:91:        natural_key=('ETC_ID', 'HIC3_SEQN'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:109:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:110:        natural_key=('DOSAGE_FORM_ID', 'DOSAGE_FORM_ATTRIBUTE_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:130:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:131:        natural_key=('DOSAGE_FORM_ID', 'GCDF'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:151:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:152:        natural_key=('DOSAGE_FORM_ID', 'MED_DOSAGE_FORM_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:172:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:173:        natural_key=('DOSAGE_FORM_ID', 'OVW_DOSAGE_FORM_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:191:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:192:        natural_key=('CONTINUOUS_RT_ID', 'INTERMITTENT_RT_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:210:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:211:        natural_key=('PARENT_RT_ID', 'CLINICAL_RT_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:231:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:232:        natural_key=('FROM_UOM_MSTR_ID', 'TO_UOM_MSTR_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:253:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:254:        natural_key=('DOSING_MODULE_UNIT_ABBREV',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:273:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_10.py:274:        natural_key=('XRF_SOURCE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:41:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:42:        natural_key=('ROUTED_GEN_STATUS_CD',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:59:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:60:        natural_key=('STR60',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:74:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:75:        natural_key=('STRENGTH_STATUS_CODE',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:89:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:90:        natural_key=('STRENGTH_TYP_CODE',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:106:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:107:        natural_key=('UOM_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:121:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:122:        natural_key=('TC',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:136:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:137:        natural_key=('TM_NAME_TYPE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:151:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:152:        natural_key=('TM_GROUP_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:166:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:167:        natural_key=('TM_GNN_TYPE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:181:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_07.py:182:        natural_key=('TM_SOURCE_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:22:Delta semantics: UPSERT_BY_NATURAL_KEY throughout.
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:56:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:57:        natural_key=('BLA_APPL_NBR', 'APPL_TYPE_ID', 'BIOLOGICS_SN', 'MULTI_INGREDIENT_SN'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:78:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:79:        natural_key=('PROPRIETARY_NAME_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:101:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:102:        natural_key=('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'GENERIC_MED_CONCEPT_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:127:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:128:        natural_key=('MED_CONCEPT_ID', 'MED_CONCEPT_ID_TYP', 'HICL_SEQNO'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:153:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:154:        natural_key=('FDB_PRODUCT_ID', 'EXT_PRODUCT_CD_TYPE_ID', 'EXT_PRODUCT_CD_START_DT', 'EXT_PRODUCT_CD'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:173:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:174:        natural_key=('DAM_AGCSP', 'HIC_SEQN'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:191:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:192:        natural_key=('DACN', 'DAM_AGCSP'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:209:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:210:        natural_key=('GCDF', 'SCRIPT_QQ_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:227:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:228:        natural_key=('MED_DOSAGE_FORM_ID', 'SCRIPT_QQ_ID'),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:252:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:253:        natural_key=('SCRIPT_QQ_ID',),
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:270:        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules/drug-database/drug_database/services/fdb_tier_a\batch_11.py:271:        natural_key=('POEUNITCDE', 'SCRIPT_QQ_ID'),

 succeeded in 557ms:
99

 succeeded in 555ms:
1

2026-05-12T15:19:08.625460Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.6 seconds
Output:
0

 exited 1 in 565ms:
0

codex
The migration has 99 primary-key constraints and exactly one `Numeric(16, 6)`. It has zero `Numeric(16, 5)` occurrences, so I’m checking whether Tier A actually has any remaining plain `Decimal` coercers; if not, that part of the requested check is vacuously satisfied rather than a regression.
2026-05-12T15:19:39.487698Z ERROR codex_core::tools::router: error=`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import sys
from pathlib import Path
root = Path(r'C:\\Users\\MK\\Desktop\\Code Projects\\InfinityRx\\infinityrx-platform')
sys.path.insert(0, str(root / 'modules' / 'drug-database'))
from decimal import Decimal
from drug_database.services.fdb_tier_a import TIER_A_SPECS
from drug_database.services.fdb_adapter import DeltaSemantics
upsert = [s for s in TIER_A_SPECS if s.delta_semantics in {DeltaSemantics.UPSERT_BY_NATURAL_KEY, DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE}]
append = [s for s in TIER_A_SPECS if s.delta_semantics is DeltaSemantics.APPEND_ONLY]
bad = [s.table_name for s in upsert if not s.natural_key]
plain_decimal = [(s.table_name, c) for s in TIER_A_SPECS for c, f in s.coercers.items() if f is Decimal]
print('specs', len(TIER_A_SPECS))
print('upsert', len(upsert))
print('append', len(append))
print('bad', bad)
print('plain_decimal', plain_decimal)
print('decimal_16_6', [(s.table_name, c) for s in TIER_A_SPECS for c, f in s.coercers.items() if getattr(f, '__name__', '') == 'decimal_16_6'])
'@ | python -"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import sys
from pathlib import Path
root = Path(r'C:\\Users\\MK\\Desktop\\Code Projects\\InfinityRx\\infinityrx-platform')
sys.path.insert(0, str(root / 'modules' / 'drug-database'))
from decimal import Decimal
from drug_database.services.fdb_tier_a import TIER_A_SPECS
from drug_database.services.fdb_adapter import DeltaSemantics
upsert = [s for s in TIER_A_SPECS if s.delta_semantics in {DeltaSemantics.UPSERT_BY_NATURAL_KEY, DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE}]
append = [s for s in TIER_A_SPECS if s.delta_semantics is DeltaSemantics.APPEND_ONLY]
bad = [s.table_name for s in upsert if not s.natural_key]
plain_decimal = [(s.table_name, c) for s in TIER_A_SPECS for c, f in s.coercers.items() if f is Decimal]
print('specs', len(TIER_A_SPECS))
print('upsert', len(upsert))
print('append', len(append))
print('bad', bad)
print('plain_decimal', plain_decimal)
print('decimal_16_6', [(s.table_name, c) for s in TIER_A_SPECS for c, f in s.coercers.items() if getattr(f, '__name__', '') == 'decimal_16_6'])
'@ | python -" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "B9.B GATE-CLOSE R1|107 specs|FDW 173|72|live|Docker|defer|deferred" waves/B9/status.md' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 declined in 0ms:
`"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "@'
import sys
from pathlib import Path
root = Path(r'C:\\Users\\MK\\Desktop\\Code Projects\\InfinityRx\\infinityrx-platform')
sys.path.insert(0, str(root / 'modules' / 'drug-database'))
from decimal import Decimal
from drug_database.services.fdb_tier_a import TIER_A_SPECS
from drug_database.services.fdb_adapter import DeltaSemantics
upsert = [s for s in TIER_A_SPECS if s.delta_semantics in {DeltaSemantics.UPSERT_BY_NATURAL_KEY, DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE}]
append = [s for s in TIER_A_SPECS if s.delta_semantics is DeltaSemantics.APPEND_ONLY]
bad = [s.table_name for s in upsert if not s.natural_key]
plain_decimal = [(s.table_name, c) for s in TIER_A_SPECS for c, f in s.coercers.items() if f is Decimal]
print('specs', len(TIER_A_SPECS))
print('upsert', len(upsert))
print('append', len(append))
print('bad', bad)
print('plain_decimal', plain_decimal)
print('decimal_16_6', [(s.table_name, c) for s in TIER_A_SPECS for c, f in s.coercers.items() if getattr(f, '__name__', '') == 'decimal_16_6'])
'@ | python -"` rejected: blocked by policy
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/drug_database/services/fdb_tier_a/__init__.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content -Path modules/drug-database/drug_database/services/fdb_loader_registry.py' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 450ms:
18:| B9.B | Tier A — **107 specs / FDW 173 / migration with PKs / generic loader** | **R1 ABSORBED — pending R2** | `93c9d8b..<HEAD>` | Scope amended: B9.B closes at 107 (not 113); B9.C absorbs the 6 NDC/GCN/MEDID-keyed reclassifieds (now 72 tables, not 66) |
36:| C4  | MTL config flag + loader registry + DB REVOKE template | `33a2fb3` | 14 (72) |
48:**Cumulative B9.A new unit tests: 116 pass; 3 integration tests skip without live DB.**
69:| MEDIUM | Delta-contract bypass risk (B9.B-G omitted from contract) | **F4 — deferred to B9.B opening.** Codex's own suggested fix specifies: "In B9.B, add a registry-vs-contract coverage test proving every new non-UNKNOWN/non-TRUNCATE_RELOAD TableSpec is represented in the delta contract suite." This is a B9.B C1-class commit. |
137:## B9.B GATE-CLOSE R1 — verdict & absorption
151:| MEDIUM 3 | Live-DB evidence (FDW verify, migration up/down/up, row-count reconciliation) missing | Deferred to Docker-up follow-on session. Unit-test layer is gate-close-ready; live verification is a separate gate. |
172:- New integration test `tests/integration/test_fdb_record_counts_real_file.py` (4 tests) runs against the live FDB drop when present; skips otherwise.
176:- The canonical 220 B9 schema-driving tables live in `NDDF Plus DB.zip` namelist (220 files exactly).
177:- **B9.B C3 design decision (deferred to next session):** re-point the preflight `load_expected_names` to source from DB.zip namelist instead of RECORD_COUNTS. RECORD_COUNTS remains the row-count reconciliation source for the 220 tables it DOES cover.
275:## Known deferrals from baseline
284:3. **Second-run flake snapshot** — DEFERRED to next Docker-up session.

 succeeded in 473ms:
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

 succeeded in 474ms:
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

codex
The generator guard is real: it raises on UPSERT specs without `natural_key`, and the registered batch files show natural keys on all UPSERT entries I inspected through search. I’m now turning that into a concise verdict, with the one concern that affects the requested R2 gate semantics.
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Select-String -Path modules/drug-database/drug_database/services/fdb_tier_loader.py -Pattern "APPEND_ONLY|on_conflict_do_update|on_conflict_do_nothing|summary.inserted|unsupported_semantics|session.commit"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path modules/drug-database/scripts/gen_fdb_tier_migration.py -Pattern \"natural_key|PrimaryKeyConstraint|Numeric\\(16, 6\\)|Numeric\\(16, 5\\)|raises ValueError\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path modules/drug-database/alembic/versions/0009_fdb_tier_a.py -Pattern \"APPEND_ONLY|Numeric\\(16, 6\\)|PrimaryKeyConstraint\" | Select-Object -First 20" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Select-String -Path waves/B9/status.md -Pattern "107 specs|MEDIUM 3|Live-DB|Deferred|72 tables"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 555ms:

modules\drug-database\scripts\gen_fdb_tier_migration.py:56:    Raises ValueError if the coercer isn't recognized. 
Extend this
modules\drug-database\scripts\gen_fdb_tier_migration.py:72:        return "sa.Numeric(16, 5)"  # FDB pricing 
precision; override per-table if different
modules\drug-database\scripts\gen_fdb_tier_migration.py:85:        return "sa.Numeric(16, 6)"
modules\drug-database\scripts\gen_fdb_tier_migration.py:116:    When `spec.natural_key` is non-empty, emits a 
PrimaryKeyConstraint
modules\drug-database\scripts\gen_fdb_tier_migration.py:117:    over those columns so Postgres `ON CONFLICT 
(natural_key)` upserts
modules\drug-database\scripts\gen_fdb_tier_migration.py:124:    if spec.natural_key:
modules\drug-database\scripts\gen_fdb_tier_migration.py:125:        pk_cols = ", ".join(repr(c) for c in 
spec.natural_key)
modules\drug-database\scripts\gen_fdb_tier_migration.py:127:            f'\n        sa.PrimaryKeyConstraint({pk_cols}, 
'
modules\drug-database\scripts\gen_fdb_tier_migration.py:242:        DeltaSemantics.UPSERT_BY_NATURAL_KEY,
modules\drug-database\scripts\gen_fdb_tier_migration.py:252:        # natural_key so the migration can emit a PRIMARY 
KEY for
modules\drug-database\scripts\gen_fdb_tier_migration.py:256:        if spec.delta_semantics in _checkable and not 
spec.natural_key:
modules\drug-database\scripts\gen_fdb_tier_migration.py:259:                f"{spec.delta_semantics.value} but 
natural_key is empty. "
modules\drug-database\scripts\gen_fdb_tier_migration.py:260:                f"Set natural_key=(<key col(s)>,) on the 
TableSpec so the "



 succeeded in 556ms:

modules\drug-database\drug_database\services\fdb_tier_loader.py:27:for all-NK junction tables, and plain INSERT for 
APPEND_ONLY.
modules\drug-database\drug_database\services\fdb_tier_loader.py:167:            if spec.delta_semantics is 
DeltaSemantics.APPEND_ONLY:
modules\drug-database\drug_database\services\fdb_tier_loader.py:170:                summary.inserted += 1
modules\drug-database\drug_database\services\fdb_tier_loader.py:187:                    stmt = 
stmt.on_conflict_do_update(
modules\drug-database\drug_database\services\fdb_tier_loader.py:194:                    stmt = 
stmt.on_conflict_do_nothing(
modules\drug-database\drug_database\services\fdb_tier_loader.py:202:                summary.inserted += 1
modules\drug-database\drug_database\services\fdb_tier_loader.py:208:                    
"load_tier_group_unsupported_semantics table=%s "
modules\drug-database\drug_database\services\fdb_tier_loader.py:215:            session.commit()
modules\drug-database\drug_database\services\fdb_tier_loader.py:221:            summary.inserted,



 succeeded in 548ms:

modules\drug-database\alembic\versions\0009_fdb_tier_a.py:50:        sa.PrimaryKeyConstraint('AHFS8', 
name="pk_rahfsd1_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:59:        sa.PrimaryKeyConstraint('APPL_RELATION_TYPE_ID', 
name="pk_raplrt0_appl_relation_type"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:68:        sa.PrimaryKeyConstraint('APPL_TYPE_CD', 
name="pk_rappltd0_fda_appl_type"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:77:        sa.PrimaryKeyConstraint('ATC', 
name="pk_ratcd0_atc_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:86:        
sa.PrimaryKeyConstraint('BIOLOGIC_NAME_GROUPER_ID', name="pk_rblang0_name_grp_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:95:        sa.PrimaryKeyConstraint('SUBSTANCE_GROUP_ID', 
name="pk_rblasg0_substance_grp_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:104:        sa.PrimaryKeyConstraint('DCC', 
name="pk_rdccd0_drug_cat_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:113:        sa.PrimaryKeyConstraint('ETC_CHANGE_TYPE_CODE', 
name="pk_retcctd0_etc_change_type_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:122:        sa.PrimaryKeyConstraint('GTC', 
name="pk_rgtcd0_gen_therap_class_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:131:        sa.PrimaryKeyConstraint('ING_STATUS_CD', 
name="pk_rhicscd0_ing_stat_cd_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:140:        sa.PrimaryKeyConstraint('MED_CONCEPT_ID_TYP', 
name="pk_rmedcd0_med_concept_typ_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:149:        sa.PrimaryKeyConstraint('MOVE_REASON_CD', 
name="pk_rmedmrd0_move_reason_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:159:        sa.PrimaryKeyConstraint('APPL_TYPE_ID', 
name="pk_raplt0_appl_type"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:169:        sa.PrimaryKeyConstraint('GCDF', 
name="pk_rdosed2_dose_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:179:        sa.PrimaryKeyConstraint('HIC1_SEQN', 
name="pk_rhic1d2_hic_organ_sys_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:190:        sa.PrimaryKeyConstraint('HIC2_SEQN', 
name="pk_rhic2d3_hic_rx_class_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:202:        sa.PrimaryKeyConstraint('HIC3_SEQN', 
name="pk_rhic3d3_hic_therap_class_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:212:        sa.PrimaryKeyConstraint('LBLRID', 
name="pk_rlblrid3_lblr_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:221:        
sa.PrimaryKeyConstraint('MEDID_SPECIFICATION_CODE', name="pk_rmedspd0_specification_desc"),
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:233:        sa.PrimaryKeyConstraint('MEDID', 
name="pk_rmedst0_medid_search_term"),



 succeeded in 548ms:

waves\B9\status.md:18:| B9.B | Tier A — **107 specs / FDW 173 / migration with PKs / generic loader** | **R1 ABSORBED 
— pending R2** | `93c9d8b..<HEAD>` | Scope amended: B9.B closes at 107 (not 113); B9.C absorbs the 6 
NDC/GCN/MEDID-keyed reclassifieds (now 72 tables, not 66) |
waves\B9\status.md:69:| MEDIUM | Delta-contract bypass risk (B9.B-G omitted from contract) | **F4 — deferred to B9.B 
opening.** Codex's own suggested fix specifies: "In B9.B, add a registry-vs-contract coverage test proving every new 
non-UNKNOWN/non-TRUNCATE_RELOAD TableSpec is represented in the delta contract suite." This is a B9.B C1-class commit. 
|
waves\B9\status.md:151:| MEDIUM 3 | Live-DB evidence (FDW verify, migration up/down/up, row-count reconciliation) 
missing | Deferred to Docker-up follow-on session. Unit-test layer is gate-close-ready; live verification is a 
separate gate. |
waves\B9\status.md:177:- **B9.B C3 design decision (deferred to next session):** re-point the preflight 
`load_expected_names` to source from DB.zip namelist instead of RECORD_COUNTS. RECORD_COUNTS remains the row-count 
reconciliation source for the 220 tables it DOES cover.
waves\B9\status.md:284:3. **Second-run flake snapshot** — DEFERRED to next Docker-up session.



exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Select-String -Path modules/drug-database/alembic/versions/0009_fdb_tier_a.py -Pattern \"Numeric\\(16, 6\\)|Numeric\\(16, 5\\)|APPEND_ONLY\"" in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Select-String -Path modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py -Pattern "APPEND_ONLY|TableSpec|table_name"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
exec
"C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Select-String -Path modules/drug-database/tests/unit/test_fdb_tier_loader.py -Pattern "replays cleanly|APPEND_ONLY|on second run|plain|inserted"' in C:\Users\MK\Desktop\Code Projects\InfinityRx\infinityrx-platform
 succeeded in 540ms:

modules\drug-database\alembic\versions\0009_fdb_tier_a.py:801:    # RETCHCH0_ETC_HICSEQN_HIST — tier=A 
delta=APPEND_ONLY record_counts_key=RETCHCH0
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:812:    # RETCHLH0_ETC_HICLSEQNO_HIST — tier=A 
delta=APPEND_ONLY record_counts_key=RETCHLH0
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:823:    # RETCNMH0_ETC_MED_NAME_ID_HIST — tier=A 
delta=APPEND_ONLY record_counts_key=RETCNMH0
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:834:    # RHICRH0_ING_HIST — tier=A delta=APPEND_ONLY 
record_counts_key=RHICRH0
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:843:    # RMIDFRH1_ROUTED_DOSE_FORM_HIST — tier=A 
delta=APPEND_ONLY record_counts_key=RMIDFRH1
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:852:    # RMINMRH1_MED_NAME_HIST — tier=A delta=APPEND_ONLY 
record_counts_key=RMINMRH1
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:861:    # RMIRH1_MED_HIST — tier=A delta=APPEND_ONLY 
record_counts_key=RMIRH1
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:870:    # RMIRMRH1_ROUTED_MED_HIST — tier=A 
delta=APPEND_ONLY record_counts_key=RMIRMRH1
modules\drug-database\alembic\versions\0009_fdb_tier_a.py:959:        sa.Column('UOM_CONVERSION_FACTOR', 
sa.Numeric(16, 6), nullable=False),



 succeeded in 555ms:

modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:1:"""B9.B C14 — Tier A batch 09 (APPEND_ONLY 
history template, 8 tables).
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:7:`APPEND_ONLY`, and the simulator + ACD cycle 
assert that every
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:23:    TableSpec,
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:29:SPECS: list[TableSpec] = [
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:31:    TableSpec(
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:32:        table_name="RETCHCH0_ETC_HICSEQN_HIST",
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:51:        
delta_semantics=DeltaSemantics.APPEND_ONLY,
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:54:    TableSpec(
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:55:        
table_name="RETCHLH0_ETC_HICLSEQNO_HIST",
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:74:        
delta_semantics=DeltaSemantics.APPEND_ONLY,
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:77:    TableSpec(
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:78:        
table_name="RETCNMH0_ETC_MED_NAME_ID_HIST",
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:97:        
delta_semantics=DeltaSemantics.APPEND_ONLY,
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:100:    TableSpec(
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:101:        table_name="RHICRH0_ING_HIST",
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:112:        
delta_semantics=DeltaSemantics.APPEND_ONLY,
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:115:    TableSpec(
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:116:        
table_name="RMIDFRH1_ROUTED_DOSE_FORM_HIST",
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:131:        
delta_semantics=DeltaSemantics.APPEND_ONLY,
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:134:    TableSpec(
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:135:        table_name="RMINMRH1_MED_NAME_HIST",
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:145:        
delta_semantics=DeltaSemantics.APPEND_ONLY,
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:148:    TableSpec(
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:149:        table_name="RMIRH1_MED_HIST",
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:159:        
delta_semantics=DeltaSemantics.APPEND_ONLY,
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:162:    TableSpec(
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:163:        table_name="RMIRMRH1_ROUTED_MED_HIST",
modules\drug-database\drug_database\services\fdb_tier_a\batch_09.py:177:        
delta_semantics=DeltaSemantics.APPEND_ONLY,



 succeeded in 548ms:

modules\drug-database\tests\unit\test_fdb_tier_loader.py:9:APPEND_ONLY) and replays cleanly (0 net new rows on second 
run).
modules\drug-database\tests\unit\test_fdb_tier_loader.py:82:_APPEND_ONLY_SPEC = TableSpec(
modules\drug-database\tests\unit\test_fdb_tier_loader.py:89:    delta_semantics=DeltaSemantics.APPEND_ONLY,
modules\drug-database\tests\unit\test_fdb_tier_loader.py:137:    """dry_run=True increments rows_parsed but 
inserted=0."""
modules\drug-database\tests\unit\test_fdb_tier_loader.py:151:    assert summary.inserted == 0
modules\drug-database\tests\unit\test_fdb_tier_loader.py:205:    """TierLoadResult sums inserted/skipped across 
multiple specs."""



codex
**Verdict: GO-WITH-FIXES**

| Severity | Area | Issue | Suggested fix |
|---|---|---|---|
| HIGH | Generic Tier A loader idempotency | `load_tier_group` does not satisfy the stated full-mode gate criterion that `load_fdb.py --mode fdb_tier_a` re-run produces `0` net new rows. The UPSERT path is structurally correct, but the 8 APPEND_ONLY batch 09 history specs are included in Tier A and are loaded with plain `INSERT`, with no primary key or duplicate guard. Re-running the same drop will append duplicate rows for those tables. See [fdb_tier_loader.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_loader.py:167>) and [batch_09.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:1>). | Either narrow the gate criterion to UPSERT-only tables and explicitly exclude/defer APPEND_ONLY history from `fdb_tier_a`, or add an idempotency surface for APPEND_ONLY same-drop replay, such as a provenance/dedupe key, then add a real second-run loader test proving row counts do not grow on replay. |

Everything else I checked is acceptable for R2:

- `--mode fdb_tier_a` dispatch exists in [load_fdb.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/scripts/load_fdb.py:60>).
- UPSERT dispatch uses `ON CONFLICT (...) DO UPDATE`; all-NK junctions use `DO NOTHING`; UNKNOWN/TRUNCATE_RELOAD skip with warning, which is fine for B9.B scope.
- Generator now rejects UPSERT specs without `natural_key` and emits `PrimaryKeyConstraint` when present in [gen_fdb_tier_migration.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/scripts/gen_fdb_tier_migration.py:256>).
- Migration has `99` `PrimaryKeyConstraint` entries.
- Migration has exactly one `sa.Numeric(16, 6)`, on `UOM_CONVERSION_FACTOR`; I found zero `Numeric(16, 5)` entries in Tier A migration, so there do not appear to be other Tier A `Decimal` columns to preserve as `16,5`.
- Scope/status accounting is updated to `107 specs / FDW 173`, with B9.C at `72` tables.
- Live-DB evidence deferral is defensible as a separate Docker-up gate, but it does not cover the APPEND_ONLY replay gap above.

So: not a fundamental NO-GO, but I would not mark B9.B officially closed until the APPEND_ONLY replay/idempotency framing is corrected.
tokens used
57,469
**Verdict: GO-WITH-FIXES**

| Severity | Area | Issue | Suggested fix |
|---|---|---|---|
| HIGH | Generic Tier A loader idempotency | `load_tier_group` does not satisfy the stated full-mode gate criterion that `load_fdb.py --mode fdb_tier_a` re-run produces `0` net new rows. The UPSERT path is structurally correct, but the 8 APPEND_ONLY batch 09 history specs are included in Tier A and are loaded with plain `INSERT`, with no primary key or duplicate guard. Re-running the same drop will append duplicate rows for those tables. See [fdb_tier_loader.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_loader.py:167>) and [batch_09.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/drug_database/services/fdb_tier_a/batch_09.py:1>). | Either narrow the gate criterion to UPSERT-only tables and explicitly exclude/defer APPEND_ONLY history from `fdb_tier_a`, or add an idempotency surface for APPEND_ONLY same-drop replay, such as a provenance/dedupe key, then add a real second-run loader test proving row counts do not grow on replay. |

Everything else I checked is acceptable for R2:

- `--mode fdb_tier_a` dispatch exists in [load_fdb.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/scripts/load_fdb.py:60>).
- UPSERT dispatch uses `ON CONFLICT (...) DO UPDATE`; all-NK junctions use `DO NOTHING`; UNKNOWN/TRUNCATE_RELOAD skip with warning, which is fine for B9.B scope.
- Generator now rejects UPSERT specs without `natural_key` and emits `PrimaryKeyConstraint` when present in [gen_fdb_tier_migration.py](</c:/Users/MK/Desktop/Code Projects/InfinityRx/infinityrx-platform/modules/drug-database/scripts/gen_fdb_tier_migration.py:256>).
- Migration has `99` `PrimaryKeyConstraint` entries.
- Migration has exactly one `sa.Numeric(16, 6)`, on `UOM_CONVERSION_FACTOR`; I found zero `Numeric(16, 5)` entries in Tier A migration, so there do not appear to be other Tier A `Decimal` columns to preserve as `16,5`.
- Scope/status accounting is updated to `107 specs / FDW 173`, with B9.C at `72` tables.
- Live-DB evidence deferral is defensible as a separate Docker-up gate, but it does not cover the APPEND_ONLY replay gap above.

So: not a fundamental NO-GO, but I would not mark B9.B officially closed until the APPEND_ONLY replay/idempotency framing is corrected.
