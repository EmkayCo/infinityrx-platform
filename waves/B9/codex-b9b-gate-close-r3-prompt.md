# Codex B9.B mini-GATE-CLOSE R3 — Final verification

**Wave:** B9 (FDB NDDF Plus 217-table extension)
**Phase:** B9.B close (R3 = verification of R2 absorption)
**Verdict requested:** GO / GO-WITH-FIXES / NO-GO
**R2 result:** GO-WITH-FIXES (1 HIGH residual on APPEND_ONLY replay)

## What changed since R2

One absorption commit: `82617b9`.

### HIGH (R2 residual) — APPEND_ONLY history replay idempotency

R2 flagged that the 8 batch_09 APPEND_ONLY specs had no PK/unique
surface, so the loader's plain-INSERT path would duplicate rows on
same-drop replay. The fix has three coordinated parts:

1. **All 8 APPEND_ONLY specs gained `natural_key=`** covering their
   non-nullable identifying columns. The natural_key is the immutable
   identifying tuple (e.g., `(REPL_HIC_SEQN, PREV_HIC_SEQN)` for
   `RHICRH0_ING_HIST`, or `(HIC_SEQN, ETC_ID, ETC_REVISION_SEQNO)` for
   `RETCHCH0_ETC_HICSEQN_HIST`). Nullable DATE columns are
   intentionally excluded from the unique surface.

2. **Generator now distinguishes** the uniqueness constraint shape
   by `delta_semantics`:
   - `UPSERT_BY_NATURAL_KEY` / `UPSERT_WITH_EFFECTIVE_DATE`
     → `sa.PrimaryKeyConstraint(*natural_key, name="pk_<table>")`
   - `APPEND_ONLY`
     → `sa.UniqueConstraint(*natural_key, name="uq_<table>")`

   PK is for live-row update target (UPSERT path). UNIQUE is for
   history-row dedupe target (same logical fact can re-appear
   across drops and must `DO NOTHING`, not error).

3. **Loader's APPEND_ONLY path** now branches on `spec.natural_key`:
   - If non-empty: `INSERT ... ON CONFLICT (natural_key) DO NOTHING`
     (matches the UNIQUE constraint the migration emits)
   - If empty: plain INSERT, with a code comment that those will
     duplicate on replay (legacy specs only — batch_09 has none)

### New replay-idempotency test

`tests/unit/test_fdb_tier_loader.py::test_append_only_replay_with_natural_key_does_not_duplicate`:

- Builds a SQLite table with `UniqueConstraint` over `(repl_id,
  prev_id, eff_dt)`
- Constructs a fake adapter that yields one row
- Calls `load_tier_group` twice with the same fake drop
- Asserts row count is 1 after both loads (idempotent)

The loader gained a `schema=""` override for test fixtures (Postgres
default `schema="drug_database"` is unchanged for production).

## Regenerated migration `0009_fdb_tier_a.py`

```
PrimaryKeyConstraint: 99    (every UPSERT spec has a PK target)
UniqueConstraint:       8   (every APPEND_ONLY spec has a UNIQUE target)
Numeric(16, 6):         1   (UOM_CONVERSION_FACTOR — R1 MEDIUM 2 unchanged)
```

107 tables, 107 uniqueness surfaces. No bare-INSERT-without-dedupe
specs remain in Tier A.

## Test result

```
787 unit tests pass
- Tier A batches 01-11: 690 parametrized + sanity tests
- Coverage canary, loader registry, delta semantics, contract template, MTL revoke, adapter: ~97
- New tier loader: 6 tests (including the replay-idempotency one)
- Generator: 12 (fixture updated for natural_key requirement)
```

No regression elsewhere.

## Areas to verify in R3

1. **Replay idempotency** — confirm:
   - `0009_fdb_tier_a.py` emits exactly 8 `UniqueConstraint` (for
     batch_09 specs only).
   - Loader's APPEND_ONLY path uses `on_conflict_do_nothing` when
     `spec.natural_key` is non-empty.
   - The replay-idempotency unit test runs the load twice and
     asserts unchanged count.

2. **Uniqueness-surface completeness across all 107 Tier A tables** —
   every spec now has either:
   - PrimaryKeyConstraint (99 UPSERT specs), or
   - UniqueConstraint (8 APPEND_ONLY specs).
   No table is left with bare columns.

3. **Generator hardening** — UPSERT specs without natural_key still
   raise (as enforced in R1). APPEND_ONLY without natural_key now
   does NOT raise (legacy compatibility) but the loader logs/skips
   the dedupe-key opt-in. Is the asymmetry defensible?

4. **MEDIUM 3 (live-DB evidence)** — still deferred. Same defense
   as R2: unit-test layer is gate-close-ready; live FDW verify /
   migration up+down+up / row-count reconciliation are separate-gate
   concerns (Docker-up follow-on session).

## Verdict format

GO — B9.B officially closes; B9.C opens (72 Tier B tables).
GO-WITH-FIXES — list residual concerns.
NO-GO — fundamental issue.

For GO-WITH-FIXES, return concerns as:
| Severity | Area | Issue | Suggested fix |
