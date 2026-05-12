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
