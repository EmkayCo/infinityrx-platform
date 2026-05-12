# B9 Write-Path Enforcement Policy

**Charter section:** §SPEC-locked reference-DB invariants
**Plan reference:** C9 (`waves/B9/plan.md:109`)
**Code:** `shared/db/write_path_guard.py`, `scripts/load_fdb.py`
**Status:** ACTIVE — B9.A C9 onward

## The rule

B9 FDB loaders write reference tables (Tier A/B/C/RNDC14/pricing/MTL)
to `infinityrx_reference` and ONLY to `infinityrx_reference`. The
loader refuses to start unless BOTH conditions hold:

1. **Env-var:** `DATABASE_URL_SYNC_REFERENCE` is set to a Postgres
   URL pointing at the reference DB. Phase 09's fallback chain
   (`DATABASE_URL_SYNC_REFERENCE → DATABASE_URL_SYNC → DATABASE_URL`)
   is REMOVED in B9 strict mode. No fallback. Operator must export
   the variable explicitly via `switch_env.sh`.

2. **SQL assertion:** before the first write, the loader issues
   `SELECT current_database()` against the open connection. If the
   result is not `infinityrx_reference`, the loader RuntimeErrors
   with a message naming both the actual + expected DBs and the
   `switch_env.sh` fix-it path.

## Why both layers

Either layer alone is insufficient:

- **Env-var only.** Operator runs `switch_env.sh dev` (correctly sets
  `DATABASE_URL_SYNC_REFERENCE` to point at the reference DB on the
  dev cluster). They later edit their shell to point at a different
  Postgres cluster for an unrelated task — `DATABASE_URL_SYNC_REFERENCE`
  is still set but now resolves to the WRONG cluster's reference DB.
  The env-var rule alone passes; the SQL assertion catches it.
- **SQL assertion only.** Belt without suspenders. The env-var rule
  catches the typo BEFORE the engine even connects, saving a
  Postgres connection per failed attempt and giving a faster error.

## Phase 09 backward compatibility

The Phase 09 modes `fdb_initial / fdb_weekly / fdb_rebase` keep the
LEGACY fallback chain to avoid breaking existing operator runbooks
(commit `7e9e1ff` introduced the chain; operators have it in their
shell history). B9 loaders opt IN via:

```bash
python scripts/load_fdb.py --mode fdb_tier_a --require-reference-db
```

The `--require-reference-db` flag is set automatically by every B9.B-G
tier loader wrapper. Operators running Phase 09 modes by hand do not
need to know about the flag.

## Failure modes

| Failure | Exit code | Operator action |
|---|---|---|
| `DATABASE_URL_SYNC_REFERENCE` unset | 1 | `source infrastructure/scripts/switch_env.sh dev` |
| Env var set, but Postgres reports current_database() != 'infinityrx_reference' | 3 | Inspect `switch_env.sh`; confirm `DATABASE_URL_SYNC_REFERENCE` was exported to the reference DB URL, not the operational one. |
| FDB drop root missing | 2 | Verify `data/reference/fdb/TEL251759D/` exists or set `FDB_DROP_ROOT`. |

## Test seam

`assert_reference_db_write_path` accepts an injected `resolver=`
callable. Unit tests pass a lambda to bypass the real SQL roundtrip
without needing Postgres. Production callers leave `resolver=None` and
the default `SELECT current_database()` path runs.

Covered by `shared/tests/db/test_write_path_guard.py` (12 tests),
exit-code paths exercised by `scripts/load_fdb.py` integration.

## When to relax this rule

Never silently. If a future wave genuinely needs to write FDB-shaped
tables to an operational DB (e.g., a tenant-specific override schema),
the change is a new wave with a charter that explicitly names the
exception, NOT a quiet edit to the env-var resolver.
