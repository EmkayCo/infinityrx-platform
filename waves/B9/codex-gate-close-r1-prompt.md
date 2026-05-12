# Codex B9.A mini-GATE-CLOSE R1 — Consult Prompt

**Wave:** B9 (FDB NDDF Plus 217-table extension)
**Phase:** B9.A (cross-cutting infra; pre-Tier-A work)
**Verdict requested:** GO / GO-WITH-FIXES / NO-GO
**Charter version:** v3.2 LOCKED
**Plan version:** v3.1 LOCKED

## What you are reviewing

B9.A laid the cross-cutting infrastructure that B9.B-G (113+66+16+1+2+19
= 217 tables) will consume. No FDB models have landed yet. The work
is contract / registry / preflight / lock-in — the SCAFFOLD that
makes B9.B-G's per-table work mechanical and gate-able.

## Commits in scope (9 commits on `develop`)

```
503cd7b B7.3: restore Phase 11A ground truth (ifx_prod_app regression repair)
9b19457 B9.A C1: TableSpec registry expansion — Tier + DeltaSemantics + 4 fields
e54425f B9.A C2: generated migration template for FDB tier batches
3ead3bd B9.A C3: ingester contract test template + N4/A4/T12 mitigations
33a2fb3 B9.A C4: FDB MTL config flag + loader registry + DB-level guard template
d6cefd8 B9.A C8: SQLite-backed DELTA_SEMANTICS simulator + A4 regression detector
2b1f2b9 B9.A C9: reference-DB write-path guard (env-var strict + SQL assertion)
c03e37a B9.A C10: FDW name-collision preflight script + test seam
60c6cc0 B9.A C11: setup_fdw.sh manifest-derived count + deterministic sort
9b61d6d B9.A C12+C13: Phase 09 compat baseline + module base profile lock-in
```

(C5-C7 are administrative — codex consults captured pre-session and
plan v-bump; no code.)

## Files added / modified

### New helpers + registries
- `modules/drug-database/scripts/gen_fdb_tier_migration.py` (C2)
- `modules/drug-database/drug_database/services/fdb_loader_registry.py` (C4)
- `modules/drug-database/drug_database/services/fdb_adapter.py` (C1 — Tier + DeltaSemantics enums + 4 TableSpec fields)
- `shared/db/write_path_guard.py` (C9)
- `infrastructure/scripts/preflight_b9_name_collision.py` (C10)
- `infrastructure/scripts/setup_fdw.sh` (C11 — manifest-derived count)
- `infrastructure/scripts/lib/fdb_mtl_revoke.sql.tmpl` (C4 — DB-level MTL guard)
- `shared/config.py` (C4 — `FDB_LOAD_MTL: bool = False`)

### New test surface (116 unit + 3 integration)
- `modules/drug-database/tests/_fdb_contract.py` (C3 — reusable contract helpers)
- `modules/drug-database/tests/_fdb_delta_semantics.py` (C8 — SQLite simulator)
- `modules/drug-database/tests/unit/test_fdb_adapter.py` (C1 — 24 tests)
- `modules/drug-database/tests/unit/test_gen_fdb_tier_migration.py` (C2 — 12)
- `modules/drug-database/tests/unit/test_fdb_contract.py` (C3 — 22)
- `modules/drug-database/tests/unit/test_fdb_loader_registry.py` (C4 — 14)
- `modules/drug-database/tests/unit/test_fdb_delta_semantics.py` (C8 — 8)
- `modules/drug-database/tests/unit/test_module_base_profile.py` (C13 — 3)
- `modules/drug-database/tests/integration/test_phase09_compat_baseline.py` (C12 — 3 DB-skip)
- `shared/tests/db/test_write_path_guard.py` (C9 — 11)
- `shared/tests/db/test_preflight_b9_name_collision.py` (C10 — 16)
- `shared/tests/db/test_setup_fdw_manifest.py` (C11 — 9)

### Wave artifacts (Werkbench)
- `waves/B9/phase09_compat_baseline.md` (C12)
- `waves/B9/module_base_profile.md` (C13)
- `waves/B9/write_path_enforcement.md` (C9)
- `waves/B9/parse_warning_allowlist.md` (C3 — empty initial)
- `waves/B9/status.md` (C14 — ledger)

## Test result

```
cumulative B9.A: 116 unit pass + 3 integration skip
drug-database unit suite:        326 → 329 PASS, no regression
shared/tests/db (new files):     45/45 PASS in isolation
```

Pre-existing baseline failures (195, per `waves/B9/baseline.md`) are
out of B9 scope per charter §Out-of-scope.

## Charter SC coverage

See `waves/B9/status.md` → "Charter / SC mapping" section. All 10
charter SCs have an explicit B9.A status row. B9.A does not CLOSE
any SC by itself — it readies the scaffolding so B9.B-G can close
SC-1 through SC-10 incrementally with the same template.

## Areas to scrutinize

1. **`fdb_loader_registry.filter_loadable_specs`**: the load-bearing
   assertion that `loader_group="fdb_mtl"` is excluded under
   `FDB_LOAD_MTL=False` regardless of `only_groups`. Test
   `test_filter_only_groups_mtl_still_denied_under_default_flag`
   pins this. Is there a code path that bypasses this guard?

2. **`assert_delta_semantics_acd_cycle`**: the A4 mitigation.
   Verifies UPSERT correctness via simulated INSERT...ON CONFLICT DO
   UPDATE. The SQLite simulator at C8 reproduces the exact regression
   (DO NOTHING) and asserts the contract catches it
   (`test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing`).
   Is the abstract surface (`_fdb_contract.py:421-509`) tight enough
   that a B9.B per-table test cannot accidentally bypass it?

3. **`scan_for_collisions` in C10**: hard / soft / unknown-schema
   triage. Unknown schemas are treated as HARD (fail-safe). Is the
   `_OWNED_SCHEMAS` / `_HARD_COLLISION_SCHEMAS` frozenset coverage
   complete vs the current `infinityrx_reference` schema list (per
   `baseline.md`: core, drug_database, drug_db, pharmacy_dir,
   prescriber_dir, public, reference, shared)?

4. **`setup_fdw.sh` C11 floor 66**: replaces `-ne 66` with `-lt 66`.
   Is the floor protection equivalent? (Truncation to < 66 still
   fails; expansion >= 66 succeeds — which is the B9 growth path.)

5. **C9 strict env-var resolution**: `resolve_reference_db_url`
   removes the Phase 09 fallback chain. Phase 09's existing
   `scripts/load_fdb.py` is UNCHANGED (kept untracked / Phase 09
   modes use the legacy chain). B9.B-G tier loaders, when built,
   will import the strict resolver directly. Is this split (strict
   for B9, legacy for Phase 09) a reasonable backward-compat
   pattern, or should B9.A have also migrated Phase 09 to strict
   mode?

6. **Contract template `assert_no_parse_warnings`**: defaults to
   zero tolerance. Allowlist requires CONSULT-ROUND sign-off
   (documented in `parse_warning_allowlist.md`). Is the policy
   clear enough that a B9.B operator cannot quietly extend the
   allowlist without going through the gate?

7. **Module base profile C13**: the test asserts
   `len(DrugBase.metadata.tables) == 9` as an EQUALITY (not floor).
   The intent is to force the refactor decision when B9.B's first
   misplaced model bumps the count. Is this too brittle (might
   trip on unrelated drug-database PRs) or appropriately strict?

8. **MTL REVOKE template `fdb_mtl_revoke.sql.tmpl`**: substitution
   placeholders `{{SCHEMA}}`, `{{MTL_TABLES}}`, `{{APP_ROLES}}`,
   `{{APP_ROLES_QUOTED}}`. The verification block uses
   `{{APP_ROLES_QUOTED}}` which the docstring doesn't list. Is
   that a documentation gap, or a real bug?

## Verdict format

Return either:

- **GO** — B9.A closes; B9.B opens.
- **GO-WITH-FIXES** — list of HIGH / MEDIUM concerns; B9.A re-opens
  for a fix cycle, then re-consults.
- **NO-GO** — fundamental issue requires charter or plan revision.

For GO-WITH-FIXES, return concerns in the format:

```
| Severity | Area | Issue | Suggested fix |
```
